---
title: Test clips: a static flag lost
eyebrow: Measure it yourself
---

# When a static flag is lost

A static flag travels in one frame's marker. When that frame is dropped, the flag never reaches the display, or it arrives about a
frame nobody saw. mb-framepacing then guesses: where a dropped frame follows a long hold across which the animation clock stood
still, it assumes the held frame was static and does not judge the step. The card says how many it assumed. The first three clips
lose the flag each way; the last two look like a lost rest and are not one. Without the guess (`analyze --no-static-guess`), each of
the first three shows one step of −100 ms.

**The rest's frame dropped, flagged in hindsight:** the first rest's frame is rendered and never shown. The frame that wakes up says
static before about a frame nobody saw. mb-framepacing takes the frame that held the rest as the static one: assumed, not judged.

![mb-framepacing's report of the 60-on-demand-paused-clock-hindsight-dropped-before-wake clip](../../../doc/images/test-clip-60-on-demand-paused-clock-hindsight-dropped-before-wake.svg)

**The wake-up frame dropped, flagged in hindsight:** here the frame that wakes up after the first rest is the one never shown, and its
static before flag never reaches the display. The clock stood still across the hold, so the rest is assumed static.

![mb-framepacing's report of the 60-on-demand-paused-clock-hindsight-dropped-wake clip](../../../doc/images/test-clip-60-on-demand-paused-clock-hindsight-dropped-wake.svg)

**The rest's frame dropped, flagged in advance:** the rest's frame carries static after itself and is never shown, so the flag is lost
with it. The frame before it holds the rest without a flag; the clock stood still, and it is assumed static.

![mb-framepacing's report of the 60-on-demand-paused-clock-dropped-before-wake clip](../../../doc/images/test-clip-60-on-demand-paused-clock-dropped-before-wake.svg)

**Frames dropped in the motion:** 40 frames dropped in runs of 1 to 4 while the box moves. The frame before each run stays up to 83 ms,
but the clock ran on and the next frame shows the right moment: no animation error, and nothing is assumed static.

![mb-framepacing's report of the 60-on-demand-paused-clock-hindsight-dropped-frames clip](../../../doc/images/test-clip-60-on-demand-paused-clock-hindsight-dropped-frames.svg)

**A stall, then a dropped frame:** in the middle of the motion the game renders nothing for 7 refreshes, and the next frame is dropped.
One frame stays 133 ms and one frame index is missing, exactly as with a dropped wake-up frame. But the clock ran on, and the next frame
is 8 frames further: no animation error, and no guess. Only the animation time tells this stall from a rest.

![mb-framepacing's report of the 60-on-demand-paused-clock-hindsight-dropped-after-stall clip](../../../doc/images/test-clip-60-on-demand-paused-clock-hindsight-dropped-after-stall.svg)
