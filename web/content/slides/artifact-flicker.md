---
title: Artifacts: flicker and moiré
eyebrow: Appendix
---

# Upscaler artifacts: flicker and moiré

On small, thin or repeating details and bright highlights. AMD lists that with FSR 4 "Flickering is reduced on small, thin features
and high specular surfaces" compared with FSR 3.1 ([AMD](https://gpuopen.com/amd-fsr-upscaling/)); moiré "often happens with
repetitive details"
([Unreal](https://dev.epicgames.com/documentation/en-us/unreal-engine/temporal-super-resolution-in-unreal-engine)).

Exaggerated, to make it easy to see: from a simple temporal upscaler of our own; in games, DLSS and FSR show it far
more subtly. {.note}

:::video file upscaler-flicker

Above, a still wall of thin lines as it should look; below, the lines shimmer from frame to frame and form moiré bands, though
nothing moves.

:::

In games: [Digital Foundry, God of War FSR 2.0 vs DLSS, at 2:19](https://www.youtube.com/watch?v=ZNJT6i8zpHQ&t=139s)
[Hardware Unboxed, DLSS 4.5 vs FSR 4, stability at 5:08](https://www.youtube.com/watch?v=T3MjSxysft0&t=308s) [and fences at 18:03](https://www.youtube.com/watch?v=T3MjSxysft0&t=1083s) {.more}
