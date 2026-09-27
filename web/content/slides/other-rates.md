---
title: Other rates
eyebrow: Other rates
---

# Any rate that divides the refresh rate

Half rate is one case of a general rule: a frame rate can be paced evenly when it divides the display's refresh rate, so every
frame is held for the same whole number of refreshes, the same way as at 30 fps. On a 120 Hz display that gives 60, 40 and
30 fps. Digital Foundry on [Ratchet & Clank's 40 fps mode](https://www.youtube.com/watch?v=QXi7uO7wxdc): "the same consistency
but smoother" than 30 fps on 60 Hz. A rate that does not divide, like 60 fps on 144 Hz or 40 fps on 60 Hz, cannot be even
however well it is paced: its frames alternate between two hold lengths.

:::card Even: the rate divides the refresh rate

::strip 60 30
::strip 120 60
::strip 120 40
::strip 120 30
::strip 144 72
::strip 144 48
::strip 240 120
::strip 240 60
::strip 500 250
::strip 500 100

:::

:::card Uneven: it does not

::strip 144 60
::strip 60 40
::strip 500 60

:::

Every strip is the same 1/6 s: one cell per refresh, the shade changing with each new frame. A 40 fps mode needs a display running
at 120 Hz: on 60 Hz the same game is uneven. With VRR a steady rate inside the display's range is even without dividing anything,
as long as the frame times stay steady. {.note}

[Fixed or adaptive frame rate](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/display-sync.md#fixed-or-adaptive-frame-rate) {.more}
