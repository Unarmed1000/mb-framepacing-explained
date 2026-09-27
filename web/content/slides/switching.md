---
title: Switching rates
eyebrow: Graceful degradation
draft: true
---

# Do not switch back after the first fast frame

A game that cannot hold full rate everywhere can drop to half rate, and go back up when frames fit again. A naive engine goes back
after the first frame that fits: in a busy stretch the next slow frame misses its refresh again, and every switch costs a late
frame and a jump. With **hysteresis** it goes back up only after several fast frames in a row.

:::video pair fast 60-diagram-switching-naive-every-1s 60-diagram-switching-hysteresis-every-1s chart

Top: back to full rate after the first fast frame. Bottom: with hysteresis, back up only after three fast frames in a row. Each
plays its diagram once, in the middle of every move.

:::

:::figures

![Without hysteresis: every switch back up costs a late frame.](../../../doc/images/timing-switching-naive.svg)

![With hysteresis (three fast frames): only the first slow frame is late.](../../../doc/images/timing-switching-hysteresis.svg)

:::

Android's Frame Pacing library (Swappy) does this on its own: it decides over 2 s of frame times, drops to a longer swap interval
when more than 10 % of the frames missed, and goes back only when none did, with 1 ms to spare. {.note}

[Switching between full and half rate](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/frame-pacing-strategies.md#switching-between-full-and-half-rate) {.more}
