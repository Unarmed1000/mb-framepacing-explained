---
title: Test clips: late frames
eyebrow: Measure it yourself
---

# Late frames: missed refreshes and uneven half rate

**Slow frames:** twice a second a frame takes longer than a refresh to render and misses its refresh. The frame before is held 33 ms,
the late frame is a refresh behind and the next one catches up: 16 late frames, a steady 3.5 %.

![mb-framepacing's report of the 60-diagram-slow-frames-every-1s clip](../../../doc/images/test-clip-60-diagram-slow-frames-every-1s.svg)

**Half rate, even:** 30 fps on a 60 Hz display, every frame held two refreshes: slower, but even.

![mb-framepacing's report of the 60-diagram-half-rate-even clip](../../../doc/images/test-clip-60-diagram-half-rate-even.svg)

**Half rate, bad pacing:** the same 30 fps on average, but frames held one refresh, then three.

![mb-framepacing's report of the 60-diagram-half-rate-bad-pacing clip](../../../doc/images/test-clip-60-diagram-half-rate-bad-pacing.svg)

**The perfect storm:** the naive timer's jitter and the slow frames at once, as a real measurement usually shows them.

![mb-framepacing's report of the 60-naive-5ms-diagram-slow-frames-every-1s clip](../../../doc/images/test-clip-60-naive-5ms-diagram-slow-frames-every-1s.svg)
