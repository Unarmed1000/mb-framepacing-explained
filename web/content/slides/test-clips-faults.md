---
title: Test clips: dropped and out-of-order frames
eyebrow: Measure it yourself
---

# Dropped and out-of-order frames: rendered, but not shown as rendered

**Dropped frames:** the perfect storm with runs of 1 to 4 frames rendered but never shown. The frame before is held up to 83 ms and the
events panel marks the 40 dropped frames, but the animation error stays small: the next frame shows the right moment, only late.

![mb-framepacing's report of the dropped frames clip](../../../doc/images/test-clip-60-naive-5ms-diagram-slow-frames-every-1s-dropped-frames.svg)

**Frames out of order:** the perfect storm with pairs and blocks of frames shown in the wrong order. Where the box goes back in time,
the animation error jumps both ways, and the events panel marks each refresh that showed an older frame.

![mb-framepacing's report of the out-of-order clip](../../../doc/images/test-clip-60-naive-5ms-diagram-slow-frames-every-1s-out-of-order.svg)
