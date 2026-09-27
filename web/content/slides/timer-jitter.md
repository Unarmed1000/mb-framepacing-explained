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

![Delta time jitter: frames reach the screen on time, but each shows a moment a little off.](../../../doc/images/timing-timer-jitter.svg)
