---
title: Artifacts: blur in motion
eyebrow: Appendix
---

# Upscaler artifacts: blur in motion

"TSR and other temporal upscalers have to interpolate the previous frame's pixels, which introduces blur"; they "can look like they
have a resolution of 540p when displaying at 1080p while movement is happening"
([Unreal](https://dev.epicgames.com/documentation/en-us/unreal-engine/temporal-super-resolution-in-unreal-engine)).

Exaggerated, to make it easy to see: from a simple temporal upscaler of our own; in games, DLSS and FSR show it far
more subtly. {.note}

:::video file upscaler-blur

Above, the cube as it should look; below, it softens while it moves, and is sharp again as soon as it stops.

:::

In games: [Hardware Unboxed, upscaling at 1080p, at 2:24](https://www.youtube.com/watch?v=M6nuDOqzY1U&t=144s) {.more}
