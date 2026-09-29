---
title: Test clips: idle frames
eyebrow: Measure it yourself
---

# Idle frames: static, on demand, or 1 fps at rest

**Static at rest:** the naive timer again, with the frames where the box rests marked static. Nothing moves there, so their jitter is
not judged.

![mb-framepacing's report of the 60-naive-5ms-static-rests clip](../../../doc/images/test-clip-60-naive-5ms-static-rests.svg)

**On demand:** nothing is presented while the box rests, so a frame stays up for several refreshes. There is no target frame time, so
none of it is late.

![mb-framepacing's report of the 60-on-demand clip](../../../doc/images/test-clip-60-on-demand.svg)

**On demand, paused clock:** the same, but the animation clock stops while nothing moves, so the first moving frame after a rest
would look 100 ms late. The static flag keeps that step from being judged.

![mb-framepacing's report of the 60-on-demand-paused-clock clip](../../../doc/images/test-clip-60-on-demand-paused-clock.svg)

**Idle at 1 fps:** a device saving power while the box rests three seconds: a frame a second, at the rate it wants then, so nothing
is late. Only the wait before the first moving frame counts as longer than the game prefers: that frame wants 60 fps again.

![mb-framepacing's report of the 60-idle-1fps clip](../../../doc/images/test-clip-60-idle-1fps.svg)
