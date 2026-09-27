---
title: Jitter up close
eyebrow: Appendix
---

# Delta time jitter, up close

A camera that follows a moving object hides its motion and leaves only its timing error. Unity showed its
[Time.deltaTime fix](https://unity.com/blog/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay) this way:
every box moves fast, an eighth of the width per frame, and the camera follows a perfectly timed box, so that box stands still
between the two red lines. The others have a naive timer on a machine with a light, a typical and a heavy load, and each leaves the
lines by its own timing error: at this speed 1 ms is about 10 pixels.

:::video file follow-jitter 480

Top: the ideal timer, standing still. Below it the naive timer under a light, a typical and a heavy system load, at realistic
rates: most frames on time, 4, 9 and 20 % of them about 1 or up to 2 ms off, and under heavy load a rare spike of 4 to 8 ms. Single
frames in the first half, spells of several frames in the second.

:::

Seen in normal motion, the same errors are the uneven motion of [delta time jitter](#/timer-jitter): a frame showing a moment a few
milliseconds off. The [vsync timer](#/vsync-timer) keeps every box between the lines. {.note}
