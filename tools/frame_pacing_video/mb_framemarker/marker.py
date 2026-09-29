# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: BSD-3-Clause

"""The marker format and geometry: constants, sizing and placement, the payload wire format, encoding the marker (generate_modules) and
drawing it from the modules as quads, triangles or indexed triangles. The same API as the C# library (MB.FrameMarker) and the C++ library
(MB::FrameMarker), in Python's naming; the specification is doc/marker-format.md.

Every output walks the marker in the same order: the light background (symbol + quiet zone) first, then one dark quad per horizontal
run of dark modules. Draw it in that order, last in the frame (after post effects and UI), without blending, in pure black and white.
"""

import struct
from datetime import UTC, datetime, timedelta
from typing import cast

from .structures import (
    SEQUENCE_ID_BYTE_COUNT,
    MarkerFlags,
    MarkerKind,
    ModuleMatrix,
    Options,
    Payload,
    Point,
    Quad,
    SequenceId,
    StartMetadata,
    Vertex,
    packed_module_byte_count,
)
from .third_party.qrcodegen import encode as _encode_qr

QR_VERSION = 6
"""Every main marker (frame, start and end) is QR version 6 (41x41 modules), error correction level M, byte mode, so the marker never
changes size."""
QR_MODULE_COUNT = (4 * QR_VERSION) + 17
QR_CAPACITY_BYTES = 106
"""Version 6-M holds 106 bytes: a frame or end marker uses PAYLOAD_BYTE_COUNT of them, a start marker START_PAYLOAD_BYTE_COUNT; the rest
is room for future fields."""

SYNC_QR_VERSION = 2
"""The sync marker (MarkerKind.SYNC) is QR version 2 (25x25 modules), error correction level M: magic | format version | kind | frame
index u64."""
SYNC_QR_MODULE_COUNT = (4 * SYNC_QR_VERSION) + 17
SYNC_PAYLOAD_BYTE_COUNT = 12

PAYLOAD_BYTE_COUNT = 53
"""Payload header, shared by every marker kind (little endian): magic "MF" | format version | kind | frame index u64 | animation
ticks i64 | run id u32 | intended display ticks i64 | target frame ticks u32 | CPU start ticks i64 | CPU busy ticks u32 | preferred frame
ticks u32 | flags u8. Start and end markers carry the values of the frame that shows them."""
PAYLOAD_MAGIC = b"MF"
PAYLOAD_FORMAT_VERSION = 1

ON_DEMAND_FRAME_TICKS = 0xFFFF_FFFF
"""The target and preferred frame time of a renderer that presents only when something changes: there is no interval to aim for."""

START_PAYLOAD_BYTE_COUNT = PAYLOAD_BYTE_COUNT + 8 + SEQUENCE_ID_BYTE_COUNT
"""Start marker payload: header | start time UTC i64 | sequence id (16 bytes)."""
MAX_ENCODED_PAYLOAD_BYTE_COUNT = START_PAYLOAD_BYTE_COUNT
"""The longest payload of any kind: the start marker's."""

TICKS_PER_SECOND = 10_000_000
"""TimeSpan / DateTime resolution."""
UNIX_EPOCH_DATE_TIME_TICKS = 621_355_968_000_000_000
"""DateTime ticks (since 0001-01-01) at the Unix epoch."""

RECOMMENDED_INSET_PX = 32
"""Recommended distance in source pixels between the marker and the edge of the frame."""

MIN_MODULE_SIZE_PX = 1
MAX_MODULE_SIZE_PX = 1024
MAX_QUIET_ZONE_MODULES = 16
RECOMMENDED_QUIET_ZONE_MODULES = 4

MAX_QUAD_COUNT = 1 + (QR_MODULE_COUNT * ((QR_MODULE_COUNT + 1) // 2))
"""Upper bound on the number of quads for any marker: one background quad plus at most one quad per dark run."""

MAX_PACKED_MODULE_BYTE_COUNT = packed_module_byte_count(QR_MODULE_COUNT)
"""The packed module matrix of the largest symbol: 211 bytes for 41x41."""

MAX_GRID_VERTEX_COUNT = 4 + ((QR_MODULE_COUNT + 1) ** 2)
"""Vertices of the main marker's static grid (grid_vertices): 1768; the sync marker's is 680. Both fit 16-bit indices."""

_HEADER = struct.Struct("<2sBBQqIqIqIIB")
_SYNC = struct.Struct("<2sBBQ")
_START_FIELDS = struct.Struct(f"<q{SEQUENCE_ID_BYTE_COUNT}s")
_DATE_TIME_EPOCH = datetime(1, 1, 1, tzinfo=UTC)


def is_valid(options: Options) -> bool:
    return MIN_MODULE_SIZE_PX <= options.module_size_px <= MAX_MODULE_SIZE_PX and 0 <= options.quiet_zone_modules <= MAX_QUIET_ZONE_MODULES


def qr_module_count_for(kind: MarkerKind) -> int:
    """Modules per side of a marker's symbol: the main marker (frame, start and end) or the smaller sync marker."""
    return SYNC_QR_MODULE_COUNT if kind == MarkerKind.SYNC else QR_MODULE_COUNT


def marker_size_px(options: Options, kind: MarkerKind = MarkerKind.FRAME) -> int:
    """Width and height in source pixels of a marker (symbol + quiet zone). Frame, start and end markers have one size, the sync marker
    is smaller."""
    return (qr_module_count_for(kind) + (2 * options.quiet_zone_modules)) * options.module_size_px


def minimum_module_size_px(source_height: int, stored_height: int) -> int:
    """Hard minimum module size: 2 stored pixels per module after all scaling (source -> capture -> stored)."""
    return _module_size_for_stored_px(2, source_height, stored_height)


def recommend_module_size_px(source_height: int, stored_height: int, mjpeg: bool = False) -> int:
    """Recommended module size: 3 stored pixels per module, or 4 when the capture card delivers MJPEG."""
    return _module_size_for_stored_px(4 if mjpeg else 3, source_height, stored_height)


def recommended_origin(kind: MarkerKind, source_width: int, source_height: int, options: Options, align_px: int = 1) -> Point:
    """Recommended origin of a marker: the main marker (frame, start and end) top-left, the sync marker bottom-left. `align_px` should
    be the integer downscale ratio (1 if none) so module edges land on stored pixel edges."""
    del source_width  # the markers sit at the left edge; the width is part of the API as in the C# and C++ libraries
    inset = _align_up(RECOMMENDED_INSET_PX, align_px)
    if kind == MarkerKind.SYNC:
        return Point(inset, _align_down(source_height - inset - marker_size_px(options, kind), align_px))
    return Point(inset, inset)


def to_date_time_ticks(time: datetime) -> int:
    """Convert a wall clock time to DateTime UTC ticks (the StartMetadata.utc_ticks format); a naive time counts as local time."""
    return (time.astimezone(UTC) - _DATE_TIME_EPOCH) // timedelta(microseconds=1) * 10


def seconds_to_ticks(seconds: float) -> int:
    """Convert seconds (for example an animation clock) to TimeSpan ticks, rounded to the nearest tick (half to even, like the C#
    library's Math.Round)."""
    return round(seconds * TICKS_PER_SECOND)


def encode_payload(payload: Payload, metadata: StartMetadata | None = None) -> bytes:
    """Serialize the payload. Start markers append the metadata, other kinds ignore it; a sync marker is SYNC_PAYLOAD_BYTE_COUNT bytes
    (the start of the header, up to the frame index) and ignores the other fields. Raises ValueError when an encoded field is out of its
    range."""
    if payload.kind == MarkerKind.SYNC:
        try:
            return _SYNC.pack(PAYLOAD_MAGIC, PAYLOAD_FORMAT_VERSION, payload.kind, payload.frame_index)
        except struct.error as error:
            raise ValueError(f"payload out of range: {payload}") from error
    try:
        header = _HEADER.pack(
            PAYLOAD_MAGIC,
            PAYLOAD_FORMAT_VERSION,
            payload.kind,
            payload.frame_index,
            payload.animation_ticks,
            payload.run_id,
            payload.intended_display_ticks,
            payload.target_frame_ticks,
            payload.cpu_start_ticks,
            payload.cpu_busy_ticks,
            payload.preferred_frame_ticks,
            payload.flags,
        )
    except struct.error as error:
        raise ValueError(f"payload out of range: {payload}") from error
    if payload.kind != MarkerKind.SEQUENCE_START:
        return header
    start = metadata or StartMetadata()
    try:
        fields = _START_FIELDS.pack(start.utc_ticks, start.sequence_id.data)
    except struct.error as error:
        raise ValueError(f"start time out of range: {start.utc_ticks}") from error
    return header + fields


def try_decode_payload(data: bytes) -> tuple[Payload, StartMetadata | None] | None:
    """Parse the wire format: the payload and, for a start marker, its metadata. None on a wrong length, magic, format version or an
    unknown kind. A sync payload (exactly SYNC_PAYLOAD_BYTE_COUNT bytes) decodes to its frame index with the other fields 0."""
    if len(data) < SYNC_PAYLOAD_BYTE_COUNT:
        return None
    magic, version, kind, frame_index = cast(tuple[bytes, int, int, int], _SYNC.unpack_from(data))
    if magic != PAYLOAD_MAGIC or version != PAYLOAD_FORMAT_VERSION or kind > max(MarkerKind):
        return None
    if kind == MarkerKind.SYNC:
        return (Payload(frame_index, 0, 0, MarkerKind.SYNC), None) if len(data) == SYNC_PAYLOAD_BYTE_COUNT else None
    if len(data) < PAYLOAD_BYTE_COUNT:
        return None
    fields = cast(tuple[bytes, int, int, int, int, int, int, int, int, int, int, int], _HEADER.unpack_from(data))
    _, _, _, _, animation_ticks, run_id, intended_display_ticks, target_frame_ticks, cpu_start_ticks, cpu_busy_ticks, preferred, flags = fields
    payload = Payload(
        frame_index,
        animation_ticks,
        run_id,
        MarkerKind(kind),
        intended_display_ticks,
        target_frame_ticks,
        cpu_start_ticks,
        cpu_busy_ticks,
        preferred,
        # Every value is accepted: bits without a name are reserved and kept
        MarkerFlags(flags),
    )
    if payload.kind != MarkerKind.SEQUENCE_START:
        return (payload, None) if len(data) == PAYLOAD_BYTE_COUNT else None
    if len(data) != START_PAYLOAD_BYTE_COUNT:
        return None
    utc_ticks, sequence_id = cast(tuple[int, bytes], _START_FIELDS.unpack_from(data, PAYLOAD_BYTE_COUNT))
    return payload, StartMetadata(utc_ticks, SequenceId(sequence_id))


def generate_modules(payload: Payload, metadata: StartMetadata | None = None) -> ModuleMatrix:
    """Encode a marker: the payload's QR symbol as a packed module matrix, the one step every drawing output starts from (the metadata is
    only used by start markers). Draw it with modules_to_quads, modules_to_triangles, modules_to_indexed or modules_to_bitmap; one matrix
    can feed several. Raises ValueError when an encoded field is out of its range."""
    data = encode_payload(payload, metadata)
    # Every kind is pinned to one version, so the symbol never changes size between frames
    version = SYNC_QR_VERSION if payload.kind == MarkerKind.SYNC else QR_VERSION
    symbol = _encode_qr(data, version, version)
    if symbol is None:  # every payload encode_payload accepts fits the version
        raise ValueError(f"the payload does not fit QR version {version}: {payload}")
    # Pack the symbol: row-major, most significant bit first, continuous across rows
    bits = bytearray(packed_module_byte_count(symbol.size))
    for index, dark in enumerate(dark for row in symbol.modules for dark in row):
        if dark:
            bits[index >> 3] |= 0x80 >> (index & 7)
    return ModuleMatrix(symbol.size, bytes(bits))


def modules_to_quads(matrix: ModuleMatrix, options: Options, origin: Point) -> list[Quad]:
    """The marker as quads, for renderers that fill rectangles: the light background (symbol + quiet zone) first, then one dark quad per
    horizontal run of dark modules. Raises ValueError if the options are invalid."""
    if not is_valid(options):
        raise ValueError(f"invalid options: {options}")
    return _walk(matrix, options, origin)


def modules_to_triangles(matrix: ModuleMatrix, options: Options, origin: Point) -> list[Vertex]:
    """The marker as a triangle list: 6 vertices per quad (see modules_to_quads for the order), (TL, TR, BL) (BL, TR, BR), clockwise on
    screen, every vertex on a pixel corner."""
    vertices: list[Vertex] = []
    for quad in modules_to_quads(matrix, options, origin):
        top_left, top_right, bottom_right, bottom_left = _corners(quad)
        vertices += (top_left, top_right, bottom_left, bottom_left, top_right, bottom_right)
    return vertices


def modules_to_indexed(matrix: ModuleMatrix, options: Options, origin: Point, base_vertex: int = 0) -> tuple[list[Vertex], list[int]]:
    """The marker as an indexed triangle list: 4 vertices (TL, TR, BR, BL) and 6 indices (0,1,3)(3,1,2) per quad, clockwise on screen.
    `base_vertex` is added to every index."""
    vertices: list[Vertex] = []
    indices: list[int] = []
    for index, quad in enumerate(modules_to_quads(matrix, options, origin)):
        vertices += _corners(quad)
        first = base_vertex + (index * 4)
        indices += (first, first + 1, first + 3, first + 3, first + 1, first + 2)
    return vertices, indices


def grid_vertex_count(kind: MarkerKind) -> int:
    """Vertices of a marker kind's static grid: 4 for the light background, then every module corner, (N + 1)^2."""
    return 4 + ((qr_module_count_for(kind) + 1) ** 2)


def grid_vertices(kind: MarkerKind, options: Options, origin: Point) -> list[Vertex]:
    """The marker's static grid, for drawing it with per-frame indices only (modules_to_grid_indices): the vertices stay the same while the
    kind's symbol size, the options and the origin do. Vertices 0..3 are the light background (TL, TR, BR, BL, luma 255); then the corners
    of the modules, dark (luma 0), row-major: corner (column, row) is vertex 4 + row x (N + 1) + column, N the kind's modules per side.
    Raises ValueError if the options are invalid."""
    if not is_valid(options):
        raise ValueError(f"invalid options: {options}")
    modules = qr_module_count_for(kind)
    size = marker_size_px(options, kind)
    left = origin.x + (options.quiet_zone_modules * options.module_size_px)
    top = origin.y + (options.quiet_zone_modules * options.module_size_px)
    vertices = [
        Vertex(origin.x, origin.y, 255),
        Vertex(origin.x + size, origin.y, 255),
        Vertex(origin.x + size, origin.y + size, 255),
        Vertex(origin.x, origin.y + size, 255),
    ]
    for row in range(modules + 1):
        for column in range(modules + 1):
            vertices.append(Vertex(left + (column * options.module_size_px), top + (row * options.module_size_px), 0))
    return vertices


def modules_to_grid_indices(matrix: ModuleMatrix, base_vertex: int = 0) -> list[int]:
    """The per-frame part of the grid drawing: the indices of the background, (0,1,3)(3,1,2), then 6 per horizontal run of dark modules,
    (TL, TR, BL) (BL, TR, BR) of the run's grid corners, clockwise on screen. Use the grid of the matrix's kind. `base_vertex` is added to
    every index."""
    corners = matrix.size + 1
    indices = [base_vertex + i for i in (0, 1, 3, 3, 1, 2)]
    # With 1 px modules at the origin, a run's quad is its columns and row
    for run in _walk(matrix, Options(1, 0), Point(0, 0))[1:]:
        top_left = base_vertex + 4 + (run.top * corners) + run.left
        top_right = base_vertex + 4 + (run.top * corners) + run.right
        indices += (top_left, top_right, top_left + corners, top_left + corners, top_right, top_right + corners)
    return indices


def _corners(quad: Quad) -> tuple[Vertex, Vertex, Vertex, Vertex]:
    """TL, TR, BR, BL."""
    luma = 0 if quad.dark else 255
    return (
        Vertex(quad.left, quad.top, luma),
        Vertex(quad.right, quad.top, luma),
        Vertex(quad.right, quad.bottom, luma),
        Vertex(quad.left, quad.bottom, luma),
    )


def _walk(matrix: ModuleMatrix, options: Options, origin: Point) -> list[Quad]:
    """The marker in draw order: the background quad, then every horizontal run of dark modules, row by row."""
    module_size = options.module_size_px
    marker_size = (matrix.size + (2 * options.quiet_zone_modules)) * module_size
    symbol_left = origin.x + (options.quiet_zone_modules * module_size)
    symbol_top = origin.y + (options.quiet_zone_modules * module_size)

    quads = [Quad(origin.x, origin.y, origin.x + marker_size, origin.y + marker_size, False)]
    for y in range(matrix.size):
        top = symbol_top + (y * module_size)
        x = 0
        while x < matrix.size:
            if not matrix.is_dark(x, y):
                x += 1
                continue
            run_start = x
            while x < matrix.size and matrix.is_dark(x, y):
                x += 1
            quads.append(Quad(symbol_left + (run_start * module_size), top, symbol_left + (x * module_size), top + module_size, True))
    return quads


def _divide(numerator: int, denominator: int) -> int:
    """Integer division truncating toward zero, as in C# and C++ (Python's // floors)."""
    quotient = abs(numerator) // abs(denominator)
    return quotient if (numerator >= 0) == (denominator > 0) else -quotient


def _ceil_divide(numerator: int, denominator: int) -> int:
    return _divide(numerator + denominator - 1, denominator)


def _align_down(value: int, alignment: int) -> int:
    return value if alignment <= 1 else _divide(value, alignment) * alignment


def _align_up(value: int, alignment: int) -> int:
    return value if alignment <= 1 else _ceil_divide(value, alignment) * alignment


def _module_size_for_stored_px(stored_px_per_module: int, source_height: int, stored_height: int) -> int:
    if source_height <= 0 or stored_height <= 0:
        return stored_px_per_module
    # module_size_px = ceil(stored_px_per_module / s) where s = stored_height / source_height
    return max(stored_px_per_module, _ceil_divide(stored_px_per_module * source_height, stored_height))
