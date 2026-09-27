---
title: Recovering
eyebrow: After a spike
draft: true
---

# Back to full rate after one slow frame

One frame, a shader compile or a streaming spike, takes longer than a refresh, and every frame after it fits again. Switching to
half rate recovers safely but holds the next frames for two refreshes each. Giving each frame its own target brings the game back
a frame sooner, with the same single late frame, where the API can schedule each present.

:::video pair fast 60-diagram-recovery-half-rate-every-1s 60-diagram-recovery-targeting-every-1s chart

Top: recovering at half rate. Bottom: at full rate with per-frame targets, back a frame sooner. Each plays its diagram once, in
the middle of every move.

:::

:::figures

![Recovering at half rate: the frames after the spike held for two refreshes.](../../../doc/images/timing-recovery-half-rate.svg)

![Per-frame targets: back at full rate a frame sooner.](../../../doc/images/timing-recovery-targeting.svg)

:::

[Recovering from an overshoot](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/frame-pacing-strategies.md#recovering-from-an-overshoot) {.more}
