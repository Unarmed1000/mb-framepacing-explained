# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""Drawing the marker into a pixel buffer: a bytearray of grey, rgb24 or rgba32 pixels, PIL's Image.tobytes, a numpy array's memory. It
draws exactly what the GPU draws from the geometry, and what marker-render draws for the golden images."""

from .marker import is_valid, modules_to_quads
from .structures import ModuleMatrix, Options, PixelFormat, Point


def modules_to_bitmap(
    matrix: ModuleMatrix,
    options: Options,
    origin: Point,
    buffer: bytearray | memoryview,
    width: int,
    height: int,
    pixel_format: PixelFormat = PixelFormat.GRAY8,
    stride: int | None = None,
) -> None:
    """Draw the marker into `buffer`: `width` x `height` pixels in `pixel_format` (see PixelFormat for the byte layout), rows `stride`
    bytes apart (default width x bytes per pixel). The light background (symbol + quiet zone), then the dark modules, 0 (dark) or 255
    (light) in every colour channel, alpha 255. The marker is clipped to the buffer; other pixels are left as they are. With a module size
    of 1 and origin (0,0) this is a module-resolution image (a texture to scale up with point filtering). Raises ValueError, writing
    nothing, for invalid options, a stride shorter than a row or a too-small buffer."""
    if not is_valid(options) or width < 0 or height < 0:
        raise ValueError(f"invalid options or size: {options}, {width} x {height}")
    bytes_per_pixel = pixel_format.bytes_per_pixel
    row_bytes = width * bytes_per_pixel
    stride = row_bytes if stride is None else stride
    needed = 0 if height == 0 else (stride * (height - 1)) + row_bytes
    if stride < row_bytes or len(buffer) < needed:
        raise ValueError(f"a buffer of {len(buffer)} bytes is too small for {width} x {height} {pixel_format.name} pixels, stride {stride}")
    for quad in modules_to_quads(matrix, options, origin):
        left, right = max(quad.left, 0), min(quad.right, width)
        top, bottom = max(quad.top, 0), min(quad.bottom, height)
        if left >= right or top >= bottom:
            continue
        luma = 0 if quad.dark else 255
        pixel = bytes([luma, luma, luma, 255][:bytes_per_pixel]) if bytes_per_pixel == 4 else bytes([luma]) * bytes_per_pixel
        run = pixel * (right - left)
        for y in range(top, bottom):
            start = (y * stride) + (left * bytes_per_pixel)
            buffer[start : start + len(run)] = run
