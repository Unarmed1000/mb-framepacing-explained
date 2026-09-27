---
title: Slow frames
eyebrow: The second cause of stutter
---

# When a frame misses its refresh

With the animation time right, stutter has one more cause: frames that reach the screen late or unevenly (**frame pacing**). A
frame over its budget, the 16.7 ms between two refreshes at 60 fps, shows a refresh late, a **hitch**: the previous frame is held,
the late frame shows a moment that has already passed, and the next one jumps ahead. The flipbook's pages are drawn evenly, but
flipped at an uneven tempo.

:::video single fast 60 60-diagram-slow-frames-every-1s bottom chart

In the middle of every move two frames miss their refresh, as B and E in the diagram: the previous frame is held, the late one
shows a moment already past, and the next one jumps ahead. The chart shows each frame's animation error.

:::

![Slow frames: the previous frame is held, the late frame shows a past moment and the next one jumps ahead.](../../../doc/images/timing-slow-frames.svg)
