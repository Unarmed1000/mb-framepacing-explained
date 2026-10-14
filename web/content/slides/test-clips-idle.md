---
title: Test clips: idle frames
eyebrow: Measure it yourself
---

# Idle frames: static, on demand, or 1 fps at rest

**Static at rest:** the naive timer again, with the frames where the box rests marked static. Nothing moves while they are on
screen, so their jitter is not judged; the step into each rest still is.

![mb-framepacing's report of the 60-naive-5ms-static-rests clip](../../../doc/images/test-clip-60-naive-5ms-static-rests.svg)

**On demand:** nothing is presented while the box rests, so a frame stays up for several refreshes. There is no target frame time, so
none of it is late.

![mb-framepacing's report of the 60-on-demand clip](../../../doc/images/test-clip-60-on-demand.svg)

**Idle at 1 fps:** a device saving power while the box rests three seconds: a frame a second, at the rate it wants then, so nothing
is late. The frames of the rest are static, so their time on screen is not held against the 60 fps the game prefers once it moves.

![mb-framepacing's report of the 60-idle-1fps clip](../../../doc/images/test-clip-60-idle-1fps.svg)
