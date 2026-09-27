---
title: VRR
eyebrow: G-SYNC, FreeSync
draft: true
---

# VRR changes when, not which moment

Everything so far assumed a fixed refresh rate with vsync on. VRR removes the refresh grid: the display refreshes when the frame
is ready, instead of the frame waiting for the display. Inside the display's range there is no tearing and no rounding to whole
refreshes. But it changes _when_ a frame appears, not _which animation time_ the game rendered it for.

![The same slow frames on VRR: the errors shrink from 16.7 to 4.2 ms, but the frames are still late.](../../../doc/images/timing-vrr-slow-frames.svg)

:::card What VRR does not fix

- **Delta time jitter stays:** a frame rendered for the wrong moment is wrong however well it is shown.
- **Hitches stay:** an 80 ms frame is still an 80 ms frame; VRR only shows it as soon as it is ready.
- **Uneven frame times reach the screen:** without vsync's grid, the animation time step has to match the game's own frame
  times.

How best to pace with VRR or vsync off is still an open question here. {.note}

:::

[Vsync, VRR and frame rate targets](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/display-sync.md) {.more}
