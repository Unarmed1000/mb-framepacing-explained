---
title: Better upscalers
eyebrow: Appendix
---

# Render scale with a better upscaler

The same lower render resolution, scaled up with more than the current frame. A plain scale up, as in the
[render scale](#/render-scale) videos, can only spread the pixels it has. DLSS and FSR also use the frames before: DLSS "samples
multiple lower-resolution images and uses motion data and feedback from prior frames to construct high-quality images"
([NVIDIA](https://www.nvidia.com/en-us/geforce/technologies/dlss/)).

This is a rough overview: upscaling is a complex topic, and every upscaler, and how each game uses it, differs in the details.
{.note}

:::video file upscaler-fsr1

Both halves at 50 % per axis: above scaled up with a plain bilinear filter, below with AMD's FSR 1 (its upscale and sharpening
passes, AMD's own code). The edges and the mortar lines are crisper; FSR 1 has only the current frame, so it cannot bring back
detail the way the temporal upscalers below do.

:::

![A temporal upscaler, roughly: this frame's jittered colour, depth and motion vectors at the render resolution and the last output at the display resolution go into the upscaler, which moves the history along the motion vectors, rejects what no longer fits and blends in the new samples; its output is kept as the next frame's history.](../../../doc/images/upscaler.svg)

:::guide

:::card DLSS and FSR

- **DLSS** (NVIDIA): a trained neural network, now a "Transformer AI model". It runs on GeForce RTX graphics cards, "which
  contain the Tensor Cores" it needs ([NVIDIA](https://www.nvidia.com/en-us/geforce/technologies/dlss/)).
- **FSR 1** (AMD): "a spatial upscaler: it works by taking the current anti-aliased frame and upscaling it to display resolution
  without relying on other data such as frame history or motion vectors"
  ([AMD](https://gpuopen.com/fidelityfx-superresolution/)); it "runs on a large variety of GPUs".
- **FSR 2 and 3:** temporal and "analytical", hand-written rules instead of a network: FSR 2 "uses temporal feedback to reconstruct
  high-resolution images" ([AMD](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-temporal/)).
- **FSR 4** (now FSR Upscaling): "uses neural networks to reconstruct visuals from lower-resolution frames", on AMD's RDNA 3 and
  4 graphics cards, and falls back to FSR 3 on older ones ([AMD](https://gpuopen.com/amd-fsr-upscaling/)).

:::

:::card What the game provides

- **Colour, depth and motion vectors** at the render resolution, with the camera shifted by a different fraction of a pixel
  every frame, the jitter ([AMD](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-temporal/)).
- **The upscaler runs before most post-processing and the UI,** which are drawn at the display resolution, as with any
  [render scale](#/render-scale). Effects such as screen-space reflections and ambient occlusion can run before it, at the lower
  resolution; film grain, bloom, depth of field and tonemapping after it
  ([AMD](https://github.com/GPUOpen-Effects/FidelityFX-FSR2#placement-in-the-frame)).
- **It replaces the game's anti-aliasing.** A temporal upscaler does what temporal anti-aliasing does, and more: with FSR 2
  "there is no longer any need to include a separate TAA pass"
  ([AMD](https://github.com/GPUOpen-Effects/FidelityFX-FSR2#temporal-antialiasing)). At 100 %, with no upscale, DLSS is
  anti-aliasing only, DLAA
  ([Unity HDRP](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/deep-learning-super-sampling-in-hdrp.html)).
  FSR 1 does not anti-alias: it takes "the current anti-aliased frame".

:::

:::

:::card The cost

- **The upscale pass takes time of its own.** FSR 2 at a 4K output in its Quality mode takes 0.7 ms on a Radeon RX 7900 XTX and
  5.4 ms on an RX 590; at 1080p 0.2 to 1.3 ms
  ([AMD](https://github.com/GPUOpen-Effects/FidelityFX-FSR2#performance)). The rendering it saves has to be worth more than that,
  and at a lower output resolution there is less to save.
- **It needs memory.** FSR 2 at 4K in its Quality mode uses about 448 MB, 354 MB of it kept from frame to frame; at 1080p about
  115 MB ([AMD](https://github.com/GPUOpen-Effects/FidelityFX-FSR2#memory-requirements), measured on an RX 6700 XT).
- **Artifacts.** Built partly from older frames, every temporal upscaler shows the same kinds of
  [artifacts](#/upscaler-artifacts).

:::

:::card Before them, and in the engines

- **Checkerboard rendering:** "rendering half of the target pixels per frame in an alternating checkerboard pattern", the other
  half picked from the previous frame along the motion vectors; it "was popularized by the PS4 Pro and their launch titles"
  ([Google](https://github.com/googlestadia/PorQue4K/blob/main/docs/CHECKERBOARD.md)). Guerrilla on Horizon Zero Dawn: "even
  though you only render 50 per cent of the pixels on each frame, after two frames you do get the detail level"
  ([Game Developer, 2017](https://www.gamedeveloper.com/design/how-guerrilla-bent-the-rules-to-turn-i-horizon-i-into-a-4k-masterpiece)).
- **The engines' own:** Unreal's TSR is "a platform-agnostic Temporal Upscaler", on any desktop graphics card with Shader Model
  5 and on PlayStation 5 and Xbox Series, after Unreal Engine 4's temporal upsampling (TAAU)
  ([Unreal](https://dev.epicgames.com/documentation/en-us/unreal-engine/temporal-super-resolution-in-unreal-engine)).

:::

:::card The quality modes

| Mode              | Render resolution per axis | FSR ([AMD](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-temporal/)) | DLSS ([Unity HDRP](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/deep-learning-super-sampling-in-hdrp.html)) |
| ----------------- | -------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Quality           | 67 %                       | 1.5x                                                                                          | 1.5x                                                                                                                                                    |
| Balanced          | 58 to 59 %                 | 1.7x                                                                                          | 1.72x                                                                                                                                                   |
| Performance       | 50 %                       | 2x                                                                                            | 2x                                                                                                                                                      |
| Ultra Performance | 33 %                       | 3x                                                                                            | 3x                                                                                                                                                      |

What each mode renders, for a 4K and a 1080p output:

| Mode              | 4K output (3840 x 2160)         | 1080p output (1920 x 1080)    |
| ----------------- | ------------------------------- | ----------------------------- |
| Native            | 3840 x 2160                     | 1920 x 1080                   |
| Quality           | 2560 x 1440                     | 1280 x 720                    |
| Balanced          | 2259 x 1271 (DLSS: 2233 x 1256) | 1129 x 635 (DLSS: 1116 x 628) |
| Performance       | 1920 x 1080                     | 960 x 540                     |
| Ultra Performance | 1280 x 720                      | 640 x 360                     |

:::
