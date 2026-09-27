---
title: Delta time jitter
eyebrow: The first cause of stutter
---

# On time, but showing the wrong moment

Frames reach the screen perfectly evenly, but the animation time advances unevenly: the game reads its wall clock a little early
or late after each flip, and renders the frame for that reading (**delta time jitter**). Gamers Nexus compare it to a flipbook
with unevenly drawn pages, flipped at a steady tempo.

:::video single fast 60 60-naive-5ms bottom chart

60 fps with a naive timer that reads the clock up to 5 ms early or late: every frame on screen on time, but showing a moment a
little off. The chart shows each frame's animation error, following the video.

:::

:::card What animation error is

**Animation error** is how far the two clocks disagree, for each frame, in milliseconds: how far the game moved on since the
previous frame, minus how long the previous frame was on screen. It is the number PresentMon reports as `MsAnimationError`.

In the chart above, every frame is on screen for exactly 16.7 ms. But the game moves on by the difference of two clock readings,
this frame's and the previous one's, each up to 5 ms off: anywhere from about 7 to 27 ms. So each bar lands up to about 10 ms
from 0.

- **Above 0, shown too soon:** the game moved on more than 16.7 ms. The box jumps a little ahead.
- **Below 0, shown too late:** the game moved on less than 16.7 ms. The box lags a little behind.

The eye follows a moving object and expects it to move at the pace time passes. Animation error is how far each frame breaks
that pace: at 0 the motion is smooth, and the further and the more often it strays from 0, the more the motion stutters. The
frame rate says nothing about it. {.note}

:::

![Delta time jitter: frames reach the screen on time, but each shows a moment a little off.](../../../doc/images/timing-timer-jitter.svg)
