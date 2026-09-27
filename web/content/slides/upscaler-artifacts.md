---
title: Upscaler artifacts
eyebrow: Appendix
---

# Temporal upscaler artifacts

Every temporal upscaler builds the frame partly from older frames, so they all show the same kinds of artifacts; the newer ones
show fewer, not none.

**The artifacts in the videos on this and the next slides are exaggerated, to make them easy to see.** They come from a simple
temporal upscaler of our own, set up to show each one plainly; in games, DLSS and FSR show them far more subtly. {.note}

How an upscaler fights them: [AMD at GDC 2023, Temporal Upscaling: Past, Present, and Future](https://www.youtube.com/watch?v=UMj1VdxZLaA)
{.more}

## Ghosting and smearing

Trails behind moving objects, where old detail is kept that should have been dropped. Particles and alpha-blended objects often
"do not write depth or motion vectors", so the upscaler cannot tell where they moved; FSR 2 asks the game for a mask of them
([AMD](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-temporal/)). AMD lists that FSR 4 "reduces ghosting
on moving objects" compared with FSR 3.1 ([AMD](https://gpuopen.com/amd-fsr-upscaling/)). {.note}

:::video file upscaler-ghosting

Above, the moving cube as it should look; below, the same cube with ghosting: old frames trail behind it.

:::

In games: [Hardware Unboxed, DLSS 4.5 vs FSR 4, at 10:18](https://www.youtube.com/watch?v=T3MjSxysft0&t=618s) {.more}
