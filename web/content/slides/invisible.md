---
title: Invisible to the numbers
eyebrow: Delta time jitter
---

# Same frame rate, same frame times, different motion

**Delta time jitter** is invisible to the usual numbers. Frame rate, frametime, display time and a frame-time graph are identical
to the perfect timer's: every frame is on screen for exactly one refresh. The eye still sees slightly uneven motion, and only
**animation error** shows why, because only it looks at the moment each frame shows.

:::video pair fast 60 60-naive-5ms nochart

The same two timers live: both boxes at 60 fps, every frame on screen for exactly one refresh, and still the bottom one stutters.

:::

![Same frame rate, same frametimes, different motion: only the animation error differs.](../../../doc/images/timing-perfect-vs-jitter.svg)
