# SPDX-License-Identifier: MIT
# Copyright (c) Project Nayuki (the QR Code generator library)
# Copyright (c) 2026, Mana Battery ApS (this port)

"""QR code encoder for the marker: byte mode, error correction level M, versions 1-6, automatic mask selection.

Third-party code under its own license (MIT, qrcodegen-LICENSE.txt next to this file): a port of the C# library's QrEncoder
(marker/csharp/source/QrEncoder.cs), itself a port of the QR Code generator the C++ library vendors (marker/cpp/third_party/qrcodegen),
limited to what the marker uses, so all of them produce exactly the same symbols; the tests check it module by module against
test-data/markers/modules.csv.

Based on the QR Code generator library, https://www.nayuki.io/page/qr-code-generator-library
Copyright (c) Project Nayuki. (MIT License)
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to
the following conditions:
- The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
- The Software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of
  merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable
  for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection
  with the Software or the use or other dealings in the Software.
"""

MIN_VERSION = 1
MAX_VERSION = 6

# Error correction level M, indexed by version (index 0 unused). From the QR specification, as in qrcodegen.
_ECC_CODEWORDS_PER_BLOCK = (-1, 10, 16, 26, 18, 24, 16)
_ERROR_CORRECTION_BLOCKS = (-1, 1, 1, 1, 2, 2, 4)

# Level M is 0 in the format information bits
_FORMAT_BITS_LEVEL_M = 0
_MODE_INDICATOR_BYTE = 0x4
_BYTE_MODE_COUNT_BITS = 8  # versions 1-9

_PENALTY_N1 = 3
_PENALTY_N2 = 3
_PENALTY_N3 = 40
_PENALTY_N4 = 10


def _raw_data_modules(version: int) -> int:
    result = ((16 * version) + 128) * version + 64
    if version >= 2:
        num_align = (version // 7) + 2
        result -= (((25 * num_align) - 10) * num_align) - 55
        if version >= 7:
            result -= 36
    return result


def _raw_codewords(version: int) -> int:
    return _raw_data_modules(version) // 8


def _data_codewords(version: int) -> int:
    return _raw_codewords(version) - (_ECC_CODEWORDS_PER_BLOCK[version] * _ERROR_CORRECTION_BLOCKS[version])


def _reed_solomon_multiply(x: int, y: int) -> int:
    # Russian peasant multiplication in GF(2^8/0x11D)
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _reed_solomon_compute_divisor(degree: int) -> list[int]:
    result = [0] * degree
    result[degree - 1] = 1  # start with the monomial x^0
    root = 1
    for _ in range(degree):
        # Multiply the current product by (x - r^i)
        for j in range(degree):
            result[j] = _reed_solomon_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _reed_solomon_multiply(root, 0x02)
    return result


def _reed_solomon_compute_remainder(data: list[int], divisor: list[int]) -> list[int]:
    degree = len(divisor)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = [*remainder[1:], 0]
        for i in range(degree):
            remainder[i] ^= _reed_solomon_multiply(divisor[i], factor)
    return remainder


_DIVISORS = {version: _reed_solomon_compute_divisor(_ECC_CODEWORDS_PER_BLOCK[version]) for version in range(MIN_VERSION, MAX_VERSION + 1)}


def _get_bit(value: int, index: int) -> bool:
    return ((value >> index) & 1) != 0


def _masked(mask: int, x: int, y: int) -> bool:
    match mask:
        case 0:
            return (x + y) % 2 == 0
        case 1:
            return y % 2 == 0
        case 2:
            return x % 3 == 0
        case 3:
            return (x + y) % 3 == 0
        case 4:
            return ((x // 3) + (y // 2)) % 2 == 0
        case 5:
            return ((x * y) % 2) + ((x * y) % 3) == 0
        case 6:
            return (((x * y) % 2) + ((x * y) % 3)) % 2 == 0
        case _:
            return (((x + y) % 2) + ((x * y) % 3)) % 2 == 0


class QrSymbol:
    """One encoded symbol: `size` modules per side, `modules[y][x]` True for dark."""

    def __init__(self, version: int) -> None:
        self.size: int = (4 * version) + 17
        self.modules: list[list[bool]] = [[False] * self.size for _ in range(self.size)]
        self._is_function: list[list[bool]] = [[False] * self.size for _ in range(self.size)]
        self._version: int = version

    def is_dark(self, x: int, y: int) -> bool:
        return self.modules[y][x]

    def _set_function_module(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self._is_function[y][x] = True

    def draw_function_patterns(self) -> None:
        size = self.size
        # Timing patterns
        for i in range(size):
            self._set_function_module(6, i, i % 2 == 0)
            self._set_function_module(i, 6, i % 2 == 0)

        # Finder patterns in three corners (overwrite some timing modules)
        self._draw_finder_pattern(3, 3)
        self._draw_finder_pattern(size - 4, 3)
        self._draw_finder_pattern(3, size - 4)

        # Alignment patterns: versions 2-6 have one at (size - 7, size - 7), the others would overlap the finders
        if self._version >= 2:
            num_align = (self._version // 7) + 2
            step = ((self._version * 8) + (num_align * 3) + 5) // ((num_align * 4) - 4) * 2
            for i in range(num_align):
                for j in range(num_align):
                    if (i == 0 and j == 0) or (i == 0 and j == num_align - 1) or (i == num_align - 1 and j == 0):
                        continue
                    self._draw_alignment_pattern(self._alignment_position(i, num_align, step), self._alignment_position(j, num_align, step))

        # Format bits with a dummy mask (overwritten after the mask is chosen); versions below 7 have no version information
        self.draw_format_bits(0)

    def _alignment_position(self, index: int, num_align: int, step: int) -> int:
        return 6 if index == 0 else self.size - 7 - ((num_align - 1 - index) * step)

    def _draw_finder_pattern(self, center_x: int, center_y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                distance = max(abs(dx), abs(dy))  # Chebyshev distance
                x = center_x + dx
                y = center_y + dy
                if 0 <= x < self.size and 0 <= y < self.size:
                    self._set_function_module(x, y, distance not in (2, 4))

    def _draw_alignment_pattern(self, center_x: int, center_y: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._set_function_module(center_x + dx, center_y + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format_bits(self, mask: int) -> None:
        # Error correction level and mask, then a BCH(15,5) code and the fixed XOR pattern
        data = (_FORMAT_BITS_LEVEL_M << 3) | mask
        remainder = data
        for _ in range(10):
            remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
        bits = ((data << 10) | remainder) ^ 0x5412
        size = self.size

        # First copy
        for i in range(6):
            self._set_function_module(8, i, _get_bit(bits, i))
        self._set_function_module(8, 7, _get_bit(bits, 6))
        self._set_function_module(8, 8, _get_bit(bits, 7))
        self._set_function_module(7, 8, _get_bit(bits, 8))
        for i in range(9, 15):
            self._set_function_module(14 - i, 8, _get_bit(bits, i))

        # Second copy
        for i in range(8):
            self._set_function_module(size - 1 - i, 8, _get_bit(bits, i))
        for i in range(8, 15):
            self._set_function_module(8, size - 15 + i, _get_bit(bits, i))
        self._set_function_module(8, size - 8, True)  # always dark

    def draw_codewords(self, codewords: list[int]) -> None:
        # The zigzag scan: column pairs from the right, alternating up and down, skipping the vertical timing column
        size = self.size
        bit_index = 0
        total_bits = len(codewords) * 8
        right = size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vertical in range(size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = size - 1 - vertical if upward else vertical
                    if not self._is_function[y][x] and bit_index < total_bits:
                        self.modules[y][x] = _get_bit(codewords[bit_index >> 3], 7 - (bit_index & 7))
                        bit_index += 1
                    # Remainder bits (0 to 7) stay light
            right -= 2

    def apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            row = self.modules[y]
            function_row = self._is_function[y]
            for x in range(self.size):
                if not function_row[x] and _masked(mask, x, y):
                    row[x] = not row[x]

    def penalty_score(self) -> int:
        size = self.size
        modules = self.modules
        result = 0

        # Adjacent modules in a row with the same color, and finder-like patterns; then the same for columns
        for y in range(size):
            result += self._line_penalty(modules[y])
        for x in range(size):
            result += self._line_penalty([modules[y][x] for y in range(size)])

        # 2x2 blocks of modules with the same color
        for y in range(size - 1):
            for x in range(size - 1):
                color = modules[y][x]
                if color == modules[y][x + 1] and color == modules[y + 1][x] and color == modules[y + 1][x + 1]:
                    result += _PENALTY_N2

        # Balance of dark and light modules: the smallest k >= 0 with (45-5k)% <= dark/total <= (55+5k)%
        dark = sum(row.count(True) for row in modules)
        total = size * size
        k = ((abs((dark * 20) - (total * 10)) + total - 1) // total) - 1
        result += k * _PENALTY_N4
        return result

    def _line_penalty(self, line: list[bool]) -> int:
        result = 0
        run_color = False
        run_length = 0
        history = [0] * 7
        for color in line:
            if color == run_color:
                run_length += 1
                if run_length == 5:
                    result += _PENALTY_N1
                elif run_length > 5:
                    result += 1
            else:
                self._finder_penalty_add_history(history, run_length)
                if not run_color:
                    result += self._finder_penalty_count_patterns(history) * _PENALTY_N3
                run_color = color
                run_length = 1
        result += self._finder_penalty_terminate_and_count(history, run_color, run_length) * _PENALTY_N3
        return result

    @staticmethod
    def _finder_penalty_count_patterns(history: list[int]) -> int:
        n = history[1]
        core = n > 0 and history[2] == n and history[3] == n * 3 and history[4] == n and history[5] == n
        return (1 if core and history[0] >= n * 4 and history[6] >= n else 0) + (1 if core and history[6] >= n * 4 and history[0] >= n else 0)

    def _finder_penalty_terminate_and_count(self, history: list[int], current_run_color: bool, current_run_length: int) -> int:
        if current_run_color:
            # Terminate the dark run
            self._finder_penalty_add_history(history, current_run_length)
            current_run_length = 0
        current_run_length += self.size  # add the light border to the final run
        self._finder_penalty_add_history(history, current_run_length)
        return self._finder_penalty_count_patterns(history)

    def _finder_penalty_add_history(self, history: list[int], current_run_length: int) -> None:
        if history[0] == 0:
            current_run_length += self.size  # add the light border to the initial run
        history[1:] = history[:-1]
        history[0] = current_run_length


def _add_ecc_and_interleave(data_codewords: list[int], version: int) -> list[int]:
    num_blocks = _ERROR_CORRECTION_BLOCKS[version]
    block_ecc_length = _ECC_CODEWORDS_PER_BLOCK[version]
    raw_codewords = _raw_codewords(version)
    num_short_blocks = num_blocks - (raw_codewords % num_blocks)
    short_block_length = raw_codewords // num_blocks
    block_stride = short_block_length + 1
    divisor = _DIVISORS[version]

    # Split the data into blocks and append the ECC to each block (short blocks keep one unused padding byte)
    blocks: list[list[int]] = []
    data_offset = 0
    for i in range(num_blocks):
        data_length = short_block_length - block_ecc_length + (0 if i < num_short_blocks else 1)
        data = data_codewords[data_offset : data_offset + data_length]
        block = data + [0] * (block_stride - data_length - block_ecc_length) + _reed_solomon_compute_remainder(data, divisor)
        blocks.append(block)
        data_offset += data_length

    # Interleave (not concatenate) the bytes of every block into one sequence
    result: list[int] = []
    for i in range(block_stride):
        for j in range(num_blocks):
            if i != short_block_length - block_ecc_length or j >= num_short_blocks:
                result.append(blocks[j][i])
    return result


def encode(data: bytes, min_version: int, max_version: int) -> QrSymbol | None:
    """Encode `data` in byte mode with error correction level M, using the smallest version in [min_version, max_version] that fits
    and the mask with the lowest penalty. None when the data does not fit (or the version range is outside 1-6)."""
    if min_version < MIN_VERSION or max_version > MAX_VERSION or min_version > max_version:
        return None

    used_bits = 4 + _BYTE_MODE_COUNT_BITS + (8 * len(data))
    version = min_version
    while used_bits > _data_codewords(version) * 8:
        if version >= max_version:
            return None
        version += 1

    # Data codewords: mode, character count, data, terminator, bit padding, then alternating pad bytes
    capacity_bits = _data_codewords(version) * 8
    bits: list[int] = []

    def append_bits(value: int, count: int) -> None:
        bits.extend((value >> i) & 1 for i in range(count - 1, -1, -1))

    append_bits(_MODE_INDICATOR_BYTE, 4)
    append_bits(len(data), _BYTE_MODE_COUNT_BITS)
    for byte in data:
        append_bits(byte, 8)
    append_bits(0, min(4, capacity_bits - len(bits)))
    append_bits(0, (8 - (len(bits) % 8)) % 8)
    pad_byte = 0xEC
    while len(bits) < capacity_bits:
        append_bits(pad_byte, 8)
        pad_byte ^= 0xEC ^ 0x11
    data_codewords = [int("".join(map(str, bits[i : i + 8])), 2) for i in range(0, len(bits), 8)]

    symbol = QrSymbol(version)
    symbol.draw_function_patterns()
    symbol.draw_codewords(_add_ecc_and_interleave(data_codewords, version))

    best_mask = 0
    min_penalty: int | None = None
    for mask in range(8):
        symbol.apply_mask(mask)
        symbol.draw_format_bits(mask)
        penalty = symbol.penalty_score()
        if min_penalty is None or penalty < min_penalty:
            best_mask = mask
            min_penalty = penalty
        symbol.apply_mask(mask)  # undoes the mask (XOR)
    symbol.apply_mask(best_mask)
    symbol.draw_format_bits(best_mask)
    return symbol
