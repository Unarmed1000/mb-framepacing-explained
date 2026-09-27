---
title: Pacing 30 fps
eyebrow: Half rate
---

# How to pace 30 fps

At 30 fps on a 60 Hz display every frame should stay on screen for exactly two refreshes, and the animation step 33.3 ms each
time. Rendering in time is not enough: the display shows a frame at the first vsync after it is presented, so something has to
hold it back until its second refresh. A game that caps its frame rate with its own clock instead gets frames held for three
refreshes and then one. Digital Foundry keep finding 30 fps caps like that. Bloodborne had it together with real performance
drops, and a fan patch that only changes how often frames are flipped fixes its pacing.

:::video pair fast 60-diagram-half-rate-even 60-diagram-half-rate-bad-pacing chart

Top: half rate, evenly paced, every frame held for two refreshes. Bottom: bad frame pacing, frames held for three and one
refreshes. Both are 30 fps on average; only the bottom one stutters.

:::

:::figures

![Evenly paced: each frame held for two refreshes, as intended.](../../../doc/images/timing-half-rate-even.svg)

![Bad frame pacing: frames held for 3 and 1 refreshes instead of 2, although every frame renders in time.](../../../doc/images/timing-half-rate-bad-pacing.svg)

:::

:::card Three ways to hold a frame for two refreshes

- **Swap interval:** every frame held for a whole number of refreshes, counted from the previous flip, where the platform has one
  (below).
- **Scheduled present:** the frame says when it should appear, where the platform has an API for it (below).
- **Sleep, then present:** works anywhere, but the thread wakes up a little late, differently every time. Unity: "Always use
  vSyncCount > 0 when smooth frame pacing is needed".

Whichever holds the frames, step the animation by two refreshes, counted as the [vsync timer](#/vsync-timer) does, so each frame
shows the moment it is on screen. {.note}

:::

:::card Swap intervals per platform

| Platform          | API                                                                                                                           | What it does                                                                                                                                                                                                            |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows, DXGI     | [`Present(SyncInterval)`](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgiswapchain-present)            | 1 to 4: the frame stays "for at least _n_ vertical blanks" (flip model). Given with every present, so it can change per frame                                                                                           |
| OpenGL, Windows   | [`wglSwapIntervalEXT`](https://registry.khronos.org/OpenGL/extensions/EXT/WGL_EXT_swap_control.txt)                           | "the minimum number of video frames that are displayed before a buffer swap"                                                                                                                                            |
| OpenGL, Linux X11 | [`glXSwapIntervalEXT`](https://registry.khronos.org/OpenGL/extensions/EXT/EXT_swap_control.txt)                               | The same: "a value of two means that the color buffers will be swapped at most every other video frame"                                                                                                                 |
| EGL, Android      | [`eglSwapInterval`](https://registry.khronos.org/EGL/sdk/docs/man/html/eglSwapInterval.xhtml)                                 | The same, clamped to the implementation's `EGL_MAX_SWAP_INTERVAL`                                                                                                                                                       |
| Android, Swappy   | [`SwappyGL_setSwapIntervalNS`](https://developer.android.com/games/sdk/reference/frame-pacing/group/swappy-g-l)               | A minimum interval in nanoseconds (`SWAPPY_SWAP_30FPS`); in its auto mode Swappy may still go slower                                                                                                                    |
| Vulkan            | None in core                                                                                                                  | FIFO "is equivalent to … a swap interval of 1": hold a frame longer by presenting it twice, or with a scheduled present                                                                                                 |
| Wayland           | [`wp_fifo_v1`](https://wayland.app/protocols/fifo-v1)                                                                         | An interval of 1 only: an update stays "for at least one refresh cycle"                                                                                                                                                 |
| Apple             | None                                                                                                                          | A display link's [`preferredFrameRateRange`](https://developer.apple.com/documentation/quartzcore/cadisplaylink/preferredframeraterange) sets how often the app is asked for a frame; to hold one, schedule its present |
| Engines           | [`vSyncCount`](https://docs.unity3d.com/ScriptReference/QualitySettings-vSyncCount.html) (Unity), `rhi.SyncInterval` (Unreal) | Unity: 0 to 4, the refresh rate divided by `vSyncCount`; Unreal's frame pacer sets `rhi.SyncInterval` from the display's refresh rate                                                                                   |

:::

:::card Scheduled presents per platform

| Platform       | API                                                                                                                                                                                                                                                                               | The frame gives                                                                                                                    |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Vulkan         | [`VK_EXT_present_timing`](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_present_timing.html)                                                                                                                                                                     | A target time, absolute or relative to the previous frame                                                                          |
| Vulkan, older  | [`VK_GOOGLE_display_timing`](https://docs.vulkan.org/refpages/latest/refpages/source/VK_GOOGLE_display_timing.html)                                                                                                                                                               | A desired present time (not ratified)                                                                                              |
| Android        | [`eglPresentationTimeANDROID`](https://registry.khronos.org/EGL/extensions/ANDROID/EGL_ANDROID_presentation_time.txt), [`ASurfaceTransaction_setDesiredPresentTime`](https://developer.android.com/ndk/reference/group/native-activity#asurfacetransaction_setdesiredpresenttime) | A desired presentation time, per frame or per surface transaction                                                                  |
| Apple, Metal   | [`present(at:)`](<https://developer.apple.com/documentation/metal/mtldrawable/present(at:)>), [`present(afterMinimumDuration:)`](<https://developer.apple.com/documentation/metal/mtldrawable/present(afterminimumduration:)>)                                                    | A host time, or how long the previous frame stays on screen at least                                                               |
| Windows        | [`IPresentationManager::SetTargetTime`](https://learn.microsoft.com/en-us/windows/win32/api/presentation/nf-presentation-ipresentationmanager-settargettime)                                                                                                                      | A target time for the next present (composition swapchain, Windows 11)                                                             |
| Linux, X11     | [`glXSwapBuffersMscOML`](https://registry.khronos.org/OpenGL/extensions/OML/GLX_OML_sync_control.txt)                                                                                                                                                                             | A target vblank count, not a time                                                                                                  |
| Linux, Wayland | [`wp_commit_timing_v1`](https://wayland.app/protocols/commit-timing-v1)                                                                                                                                                                                                           | A time the update is shown "as closely as possible to, but not before" (staging; KWin, Mutter, Sway, Weston, gamescope and others) |

Plain DXGI and core Vulkan have none: there a swap interval, or presenting each frame twice, holds a frame. {.note}

:::

[Holding a frame for more than one refresh](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/frame-pacing-strategies.md#holding-a-frame-for-more-than-one-refresh) {.more}
