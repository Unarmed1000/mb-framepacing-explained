# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""PCG32: the random number generator of the frame pacing videos.

Our own generator, so the draws never change with the Python version (Python only keeps random.Random.random() stable, not randint or
choice) and can be reproduced in any language: PCG32, the XSH RR 64/32 generator of https://www.pcg-random.org (Melissa O'Neill),
with its reference seeding (pcg32_srandom_r). Pcg32(42, 54) gives the reference output of pcg32-demo: 0xa15c02b7 0x7b47f409 ...
This is our own implementation of the published algorithm; the reference C implementation it is checked against is (c) Melissa
O'Neill, Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0).

Seeded from a text, the state and stream are the first and second 8 bytes (little endian) of the text's SHA-256 (UTF-8). The draws:
- next_u32: the next 32-bit output;
- randint(low, high): an integer from low to high, every one equally likely (a 32-bit draw below (2^32 - n) mod n is rejected,
  then value mod n, for n = high - low + 1);
- random(): a float in [0, 1), a 32-bit draw / 2^32;
- choice(values): values[randint(0, len - 1)].
"""

import hashlib
from collections.abc import Sequence
from typing import ClassVar


class Pcg32:
    """PCG32 (XSH RR 64/32) with its reference seeding; see the module docstring."""

    MULTIPLIER: ClassVar[int] = 6364136223846793005
    MASK: ClassVar[int] = (1 << 64) - 1

    def __init__(self, state: int, stream: int) -> None:
        self._increment: int = ((stream << 1) | 1) & self.MASK
        self._state: int = 0
        _ = self.next_u32()
        self._state = (self._state + state) & self.MASK
        _ = self.next_u32()

    @classmethod
    def from_text(cls, text: str) -> Pcg32:
        """A generator seeded from a text: its SHA-256's first 8 bytes are the state, the next 8 the stream (both little endian)."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return cls(int.from_bytes(digest[:8], "little"), int.from_bytes(digest[8:16], "little"))

    def next_u32(self) -> int:
        old = self._state
        self._state = (old * self.MULTIPLIER + self._increment) & self.MASK
        xorshifted = (((old >> 18) ^ old) >> 27) & 0xFFFFFFFF
        rotation = old >> 59
        return ((xorshifted >> rotation) | (xorshifted << ((-rotation) & 31))) & 0xFFFFFFFF

    def randint(self, low: int, high: int) -> int:
        """An integer from `low` to `high`, both included, every one equally likely."""
        bound = high - low + 1
        if not 1 <= bound <= 1 << 32:
            raise ValueError(f"randint needs 1 to 2^32 values, got {low}..{high}")
        threshold = ((1 << 32) - bound) % bound
        while True:
            value = self.next_u32()
            if value >= threshold:
                return low + value % bound

    def random(self) -> float:
        """A float from 0 up to (not including) 1."""
        return self.next_u32() / (1 << 32)

    def choice[T](self, values: Sequence[T]) -> T:
        return values[self.randint(0, len(values) - 1)]
