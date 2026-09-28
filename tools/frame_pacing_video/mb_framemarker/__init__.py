# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""mb_framemarker: the frame marker of mb-framepacing, in Python.

Draw a QR marker with the frame index, the animation time, the run id and (optionally) the frame pacer's intended display time and
target frame time, the CPU start time and CPU busy into every frame of an application, so mb-framepacing can measure the animation
error on the real display output. It draws exactly the same pixels as the C++ and C# libraries: the tests check
it against the golden images the C++ library writes (test-data/markers). The format is specified in doc/marker-format.md.

    from mb_framemarker import MarkerKind, Options, Payload, PixelFormat, generate_modules, modules_to_bitmap, recommended_origin, seconds_to_ticks

    options = Options(module_size_px=3)
    origin = recommended_origin(MarkerKind.FRAME, width, height, options)
    matrix = generate_modules(Payload(frame_index, seconds_to_ticks(animation_seconds), run_id=1))   # encode once
    modules_to_bitmap(matrix, options, origin, rgb24_frame, width, height, PixelFormat.RGB24)       # draw it

    # Optional (required for camera capture): the small sync marker, bottom-left, with the same frame index
    sync_origin = recommended_origin(MarkerKind.SYNC, width, height, options)
    sync = generate_modules(Payload(frame_index, 0, kind=MarkerKind.SYNC))
    modules_to_bitmap(sync, options, sync_origin, rgb24_frame, width, height, PixelFormat.RGB24)

Standard library only, Python 3.11 or later.
"""

from .bitmap import modules_to_bitmap
from .marker import (
    MAX_ENCODED_PAYLOAD_BYTE_COUNT,
    MAX_GRID_VERTEX_COUNT,
    MAX_MODULE_SIZE_PX,
    MAX_PACKED_MODULE_BYTE_COUNT,
    MAX_QUAD_COUNT,
    MAX_QUIET_ZONE_MODULES,
    MIN_MODULE_SIZE_PX,
    PAYLOAD_BYTE_COUNT,
    PAYLOAD_FORMAT_VERSION,
    PAYLOAD_MAGIC,
    QR_CAPACITY_BYTES,
    QR_MODULE_COUNT,
    QR_VERSION,
    RECOMMENDED_INSET_PX,
    RECOMMENDED_QUIET_ZONE_MODULES,
    START_PAYLOAD_BYTE_COUNT,
    SYNC_PAYLOAD_BYTE_COUNT,
    SYNC_QR_MODULE_COUNT,
    SYNC_QR_VERSION,
    TICKS_PER_SECOND,
    UNIX_EPOCH_DATE_TIME_TICKS,
    encode_payload,
    generate_modules,
    grid_vertex_count,
    grid_vertices,
    is_valid,
    marker_size_px,
    minimum_module_size_px,
    modules_to_grid_indices,
    modules_to_indexed,
    modules_to_quads,
    modules_to_triangles,
    qr_module_count_for,
    recommend_module_size_px,
    recommended_origin,
    seconds_to_ticks,
    to_date_time_ticks,
    try_decode_payload,
)
from .structures import (
    SEQUENCE_ID_BYTE_COUNT,
    MarkerKind,
    ModuleMatrix,
    Options,
    Payload,
    PixelFormat,
    Point,
    Quad,
    SequenceId,
    StartMetadata,
    Vertex,
    packed_module_byte_count,
)

__version__ = "0.1.0"

__all__ = [
    "MAX_ENCODED_PAYLOAD_BYTE_COUNT",
    "MAX_GRID_VERTEX_COUNT",
    "MAX_MODULE_SIZE_PX",
    "MAX_PACKED_MODULE_BYTE_COUNT",
    "MAX_QUAD_COUNT",
    "MAX_QUIET_ZONE_MODULES",
    "MIN_MODULE_SIZE_PX",
    "PAYLOAD_BYTE_COUNT",
    "PAYLOAD_FORMAT_VERSION",
    "PAYLOAD_MAGIC",
    "QR_CAPACITY_BYTES",
    "QR_MODULE_COUNT",
    "QR_VERSION",
    "RECOMMENDED_INSET_PX",
    "RECOMMENDED_QUIET_ZONE_MODULES",
    "SEQUENCE_ID_BYTE_COUNT",
    "START_PAYLOAD_BYTE_COUNT",
    "SYNC_PAYLOAD_BYTE_COUNT",
    "SYNC_QR_MODULE_COUNT",
    "SYNC_QR_VERSION",
    "TICKS_PER_SECOND",
    "UNIX_EPOCH_DATE_TIME_TICKS",
    "MarkerKind",
    "ModuleMatrix",
    "Options",
    "Payload",
    "PixelFormat",
    "Point",
    "Quad",
    "SequenceId",
    "StartMetadata",
    "Vertex",
    "encode_payload",
    "generate_modules",
    "grid_vertex_count",
    "grid_vertices",
    "is_valid",
    "marker_size_px",
    "minimum_module_size_px",
    "modules_to_bitmap",
    "modules_to_grid_indices",
    "modules_to_indexed",
    "modules_to_quads",
    "modules_to_triangles",
    "packed_module_byte_count",
    "qr_module_count_for",
    "recommend_module_size_px",
    "recommended_origin",
    "seconds_to_ticks",
    "to_date_time_ticks",
    "try_decode_payload",
]
