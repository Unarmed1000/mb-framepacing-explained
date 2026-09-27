---
title: Upscaler artifacts
eyebrow: Appendix
---

# Temporal upscaler artifacts

Every temporal upscaler builds the frame partly from older frames, so they all show the same kinds of artifacts; the newer ones
show fewer, not none.

**The artifacts in these videos are exaggerated, to make them easy to see.** They come from a simple temporal upscaler of our own,
set up to show each one plainly; in games, DLSS and FSR show them far more subtly. {.note}

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

## Disocclusion

"Artifacts that happen from areas of the frame becoming visible from behind areas of the frame closer to the camera": the uncovered
area has no history yet
([Unreal](https://dev.epicgames.com/documentation/en-us/unreal-engine/temporal-super-resolution-in-unreal-engine)). {.note}

:::video file upscaler-disocclusion

Above, the wall behind the moving cube as it should look; below, the wall the cube uncovers is blocky and blurred at first, and
sharpens over the next frames.

:::

In games: [Digital Foundry, God of War FSR 2.0 vs DLSS, at 5:10](https://www.youtube.com/watch?v=ZNJT6i8zpHQ&t=310s)
[Hardware Unboxed, FSR 4 at 1440p, at 13:15](https://www.youtube.com/watch?v=H38a0vjQbJg&t=795s) {.more}

## Blur in motion

"TSR and other temporal upscalers have to interpolate the previous frame's pixels, which introduces blur"; they "can look like they
have a resolution of 540p when displaying at 1080p while movement is happening" (Unreal, the same). {.note}

:::video file upscaler-blur

Above, the cube as it should look; below, it softens while it moves, and is sharp again as soon as it stops.

:::

In games: [Hardware Unboxed, upscaling at 1080p, at 2:24](https://www.youtube.com/watch?v=M6nuDOqzY1U&t=144s) {.more}

## Flicker and moiré

On small, thin or repeating details and bright highlights. AMD lists that with FSR 4 "Flickering is reduced on small, thin features
and high specular surfaces" compared with FSR 3.1 ([AMD](https://gpuopen.com/amd-fsr-upscaling/)); moiré "often happens with
repetitive details" (Unreal, the same). {.note}

:::video file upscaler-flicker

Above, a still wall of thin lines as it should look; below, the lines shimmer from frame to frame and form moiré bands, though
nothing moves.

:::

In games: [Digital Foundry, God of War FSR 2.0 vs DLSS, at 2:19](https://www.youtube.com/watch?v=ZNJT6i8zpHQ&t=139s)
[Hardware Unboxed, DLSS 4.5 vs FSR 4, stability at 5:08](https://www.youtube.com/watch?v=T3MjSxysft0&t=308s) [and fences at 18:03](https://www.youtube.com/watch?v=T3MjSxysft0&t=1083s) {.more}

## Soft transparent edges

"Translucent materials never draw velocities, or at most they draw one" (Unreal, the same). {.note}

:::video file upscaler-transparent

Above, a glass pane in front of a wall as it should look; below, the glass smears as it moves, while the wall seen through it
stays sharp.

:::

In games: [Digital Foundry, God of War FSR 2.0 vs DLSS, at 11:23](https://www.youtube.com/watch?v=ZNJT6i8zpHQ&t=683s)
[Hardware Unboxed, DLSS 4.5 vs FSR 4, particles at 13:20](https://www.youtube.com/watch?v=T3MjSxysft0&t=800s) [and transparency at 14:54](https://www.youtube.com/watch?v=T3MjSxysft0&t=894s) {.more}
