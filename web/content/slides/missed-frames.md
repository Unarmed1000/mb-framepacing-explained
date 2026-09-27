---
title: Missed frames
eyebrow: Missed frames
---

# Rule one: do not miss the frame target

A game that never misses its frame target has no pacing problem to solve. In reality it will miss now and then. Some misses are
its own, a shader compile or a streaming spike. Others are outside its control: the host operating system, a driver or another
program taking the CPU or GPU for a moment. No amount of optimising removes those, so every game needs a strategy for the missed
frame, chosen in advance: it cannot be shown on time any more, only at a later refresh. There is no easy fix: every choice costs
something, and which cost is acceptable depends on the game, the platform and the player, and on what the app's own animation
error shows.

:::card First, do not miss

- **Pick a target every frame can hold, with room to spare.** If 60 fps does not fit, a steady 30 fps on 60 Hz or 40 fps on
  120 Hz may, [paced right](#/half-rate).
- **Keep the frame cost steady:** [dynamic resolution](#/dynamic-resolution) lowers the render resolution under load, at some cost to image quality.
- **Remove the spikes the game causes itself:** compile shaders ahead of time, stream assets in before they are needed.

:::

:::guide

:::card When it happens anyway

- **Take the hitch:** stay at full rate and show the late frame a refresh late. Costs a visible jump every time.
- **[Adapt the rate](#/adapt-rate):** drop to half rate through a busy stretch, and back up when the frames fit again. Costs smoothness while
  there, and deciding when to switch.
- **Let the display wait:** [VRR](#/vrr) shows the frame when it is ready, vsync off shows it at once. Needs a VRR display, or
  tears.

:::

:::card What the choice depends on

- **What the app actually does:** [measure its animation error](#/measure) before choosing. It shows how often and by how much
  frames miss, whether as rare spikes or whole busy stretches, in which scenes, and whether the cause is pacing or delta time
  jitter.
- **How much latency matters:** a fast game played with a mouse or gamepad, or a menu, a map, a video.
- **The display:** fixed refresh or VRR and its range, 60 Hz or 120 Hz.
- **The platform:** only plain vsync, or also a swap interval, scheduled presents and feedback on when frames appeared.
- **The player:** some prefer a steady 30 fps, others a higher but uneven rate, which is why many games offer a quality and a
  performance mode.

:::

:::

Whichever way a game goes, the animation time has to be right first (the [vsync timer](#/vsync-timer)): otherwise even the
frames that do arrive on time show the wrong moment. The next slides go through the strategies one at a time, to pick the one
that fits the application. {.note}
