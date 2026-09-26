# Further reading

Articles and videos behind the [vocabulary](vocabulary.md) and the topic pages, grouped by subject. The YouTube titles and channels
were checked through YouTube's oEmbed; timestamps come from the videos' chapter lists. Pages that are no longer online link to a
Wayback Machine copy. The research was AI assisted; see [about the research](../README.md#about-the-research).

## Animation error

- [The Problem with GPU Benchmarks: Animation Error Methodology White Paper](https://gamersnexus.net/gpus-gn-extras-cpus/problem-gpu-benchmarks-reality-vs-numbers-animation-error-methodology-white)
  (Gamers Nexus, Steve Burke, 2025-10-28, [video](https://www.youtube.com/watch?v=qDnXe6N8h_c)): the formula, the sign, the charts
- [FPS Benchmarks Are Flawed: Introducing Animation Error](https://gamersnexus.net/gpus-cpus-deep-dive/fps-benchmarks-are-flawed-introducing-animation-error-engineering-discussion)
  (Gamers Nexus with Intel's Tom Petersen, [video](https://www.youtube.com/watch?v=C_RO8bJop8o), 2024-03-12: chapters
  [Animation Error & Stutter](https://www.youtube.com/watch?v=C_RO8bJop8o&t=238s) and
  [What is Simulation Time?](https://www.youtube.com/watch?v=C_RO8bJop8o&t=658s))
- [Intel's Major Overhaul for CPU & GPU Benchmarking: "GPU Busy" & Pipeline Technical Discussion](https://www.youtube.com/watch?v=5hAy5V91Hr4)
  (Gamers Nexus with Tom Petersen, 2023-08-18)
- [Inside Intel: The Future Of PC Performance, Panther Lake, Multi-Frame Gen](https://www.youtube.com/watch?v=8ydfKE1dffo)
  (Digital Foundry, Tom Petersen interview, 2026-01-08: chapters
  [stuttering: animation error, shader compilation stutter](https://www.youtube.com/watch?v=8ydfKE1dffo&t=509s) and
  [frame pacing analysis](https://www.youtube.com/watch?v=8ydfKE1dffo&t=1489s))
- [PresentMon](https://github.com/GameTechDev/PresentMon): [CSV columns](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md#csv-columns),
  [capture application](https://github.com/GameTechDev/PresentMon/blob/main/README-CaptureApplication.md),
  [releases](https://github.com/GameTechDev/PresentMon/releases),
  [animation error experiment app (issue #580)](https://github.com/GameTechDev/PresentMon/issues/580),
  [Intel PresentMon](https://game.intel.com/story/intel-presentmon/)

## Digital Foundry

Frame pacing:

- [Performance Analysis: Bloodborne](https://www.digitalfoundry.net/articles/digitalfoundry-2015-bloodborne-performance-analysis)
  (Thomas Morgan, 2015-03-28): the classic case of bad 30 fps frame pacing, frame times swinging "between 16ms and 66ms"
- [From Software's Notorious 30FPS Stutter Fixed - But Only For Hacked PS4s](https://www.youtube.com/watch?v=M7bWbWUKHmM)
  (2022-07-01): "a stuttering 30fps - what we call inconsistent/'bad' frame-pacing"
- [30FPS 'Bad' Frame-Pacing: Why Do So Many Games Get It Wrong?](https://www.youtube.com/watch?v=tvzdJh3bvAs) (DF Clips,
  2024-04-13), from [DF Direct Weekly #157](https://www.youtube.com/watch?v=Ae6xoN2fGJ0) (2024-04-08), which also has
  [Alex's PresentMon experiments](https://www.youtube.com/watch?v=Ae6xoN2fGJ0&t=3123s),
  [incorrect 30fps frame-rate caps](https://www.youtube.com/watch?v=Ae6xoN2fGJ0&t=5717s) and
  [low frame-rate compensation on PS5](https://www.youtube.com/watch?v=Ae6xoN2fGJ0&t=6216s)
- [Why Ratchet and Clank: Rift Apart's 40fps Fidelity Mode Is A Big Deal For Consoles](https://www.youtube.com/watch?v=QXi7uO7wxdc)
  (2021-07-20): 40 fps at 120 Hz, "the same consistency but smoother"

Recommendations for developers:

- [13 Ways To End Lousy PC Ports in 2023](https://www.youtube.com/watch?v=Kr7RGkFuPdQ) (Alex Battaglia, 2023-01-11): 13 best
  practices, among them [no shader compilation stutter](https://www.youtube.com/watch?v=Kr7RGkFuPdQ&t=60s),
  [refresh rate and resolution as separate options](https://www.youtube.com/watch?v=Kr7RGkFuPdQ&t=418s),
  [variable aspect ratio and variable framerate](https://www.youtube.com/watch?v=Kr7RGkFuPdQ&t=522s),
  [1/2, 1/3 and 1/4 v-sync options](https://www.youtube.com/watch?v=Kr7RGkFuPdQ&t=583s) and
  [dynamic resolution if it is also used on console](https://www.youtube.com/watch?v=Kr7RGkFuPdQ&t=746s)

Shader compilation and traversal stutter (#StutterStruggle):

- [Elden Ring PC Performance Simply Isn't Good Enough](https://www.youtube.com/watch?v=5EtcrUrsl38) (2022-02-26)
- [The Callisto Protocol: The DF Tech Review + PC #StutterStruggle Analysis](https://www.youtube.com/watch?v=Psetdjz01mI) (2022-12-02)
- [Dead Space Remake PC: DF Tech Review: The #StutterStruggle Continues](https://www.youtube.com/watch?v=MvQl7EDPRC4) (2023-02-09),
  chapter [traversal stutter](https://www.youtube.com/watch?v=MvQl7EDPRC4&t=267s)
- [Star Wars Jedi Survivor PC Review](https://www.youtube.com/watch?v=uI6eAVvvmg0) (2023-04-29): "shader compilation stutter,
  traversal stutter, nonsensical CPU limitations"
- [Unreal Engine 5.2: Next-Gen Evolves: And A 'Cure' For Stutter?](https://www.youtube.com/watch?v=XnhCt9SQ2Y0) (Alex Battaglia,
  2023-07-11)
- [Why Don't Console Games Have Shader Compilation Stutter?](https://www.youtube.com/watch?v=nFk7RMsRBnA) (DF Clips, 2024-01-15)
- [Here's How Epic Will Deal With UE5 #StutterStruggle](https://www.youtube.com/watch?v=Zs3ny7cuyMk) (DF Clips, 2025-02-17)

VRR and latency:

- [PS5 VRR System Update Tested and Discussed: Is It a Game-Changer?](https://www.youtube.com/watch?v=3v2aks-su2s) (2022-05-03)
- [Confirmed: PlayStation 5 and PS5 Pro Have VRR Stuttering Problems](https://www.youtube.com/watch?v=z2smFwG3Xkc) (2025-03-29)
- [Nvidia Reflex: PC vs PlayStation 5 Input Lag](https://www.youtube.com/watch?v=TuVAMvbFCW4) (2022-07-12, sponsored by NVIDIA)
- [Nvidia DLSS 3 Analysis: Image Quality, Latency, V-Sync + Testing Methodology](https://www.youtube.com/watch?v=92ZqYaPXxas)
  (2022-10-12)

How they measure: [Inside Digital Foundry: How We Measure Console Frame-Rate](https://www.youtube.com/watch?v=KVg19CbkXR4) and
[How We Measure PC Performance](https://www.youtube.com/watch?v=fAVxmfNUuRs).

## Frame times before animation error

- [Inside the second: A new look at game benchmarking](http://web.archive.org/web/20140209073051/http://techreport.com/review/21516/inside-the-second-a-new-look-at-game-benchmarking)
  (The Tech Report, Scott Wasson, 2011-09-08, Wayback copy), with
  [multi-GPU micro-stuttering](http://web.archive.org/web/20131014012307/http://techreport.com/review/21516/inside-the-second-a-new-look-at-game-benchmarking/11)
- [Frame Rating Dissected: Full Details on Capture-based Graphics Performance Testing](https://pcper.com/2013/03/frame-rating-dissected-full-details-on-capture-based-graphics-performance-testing/)
  (PC Perspective, Ryan Shrout, 2013-03-27): [the FCAT overlay](https://pcper.com/2013/03/frame-rating-dissected-full-details-on-capture-based-graphics-performance-testing/2/),
  [runts, drops and observed FPS](https://pcper.com/2013/03/frame-rating-dissected-full-details-on-capture-based-graphics-performance-testing/4/)
- [Frame Rating: Catalyst 13.8 Brings Frame Pacing to AMD Radeon](https://pcper.com/2013/08/frame-rating-catalyst-13-8-brings-frame-pacing-to-amd-radeon/)
  (PC Perspective, 2013-08-01)
- [FCAT: The Evolution of Frame Interval Benchmarking, Part 1](http://web.archive.org/web/20141209223623/http://www.anandtech.com/show/6862/fcat-the-evolution-of-frame-interval-benchmarking-part-1)
  (AnandTech, Ryan Smith, 2013-03-27, Wayback copy)
- [Micro stuttering](https://en.wikipedia.org/wiki/Micro_stuttering) (Wikipedia)

## Game loop timing

- [Fixing Time.deltaTime in Unity 2020.2 for smoother gameplay](https://unity.com/blog/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay)
  (Unity, Tautvydas Zilys, 2020-10-01)
- [The Elusive Frame Timing](https://medium.com/@alen.ladavac/the-elusive-frame-timing-168f899aec92) (Alen Ladavac, Croteam;
  [GDC 2018](https://www.gdcvault.com/play/1025407/Advanced-Graphics-Techniques-Tutorial-The))
- [Swapchains and frame pacing](https://raphlinus.github.io/ui/graphics/gpu/2021/10/22/swapchain-frame-pacing.html) (Raph Levien)
- [How to make your game run at 60fps](https://medium.com/@tglaiel/how-to-make-your-game-run-at-60fps-24c61210fe75) (Tyler Glaiel),
  [Fix Your Timestep!](https://gafferongames.com/post/fix_your_timestep/) (Gaffer On Games),
  [Time Delta Smoothing](https://frankforce.com/frame-rate-delta-buffering/) (Frank Force)

## Engines and platforms

- [Frame Pacing library](https://developer.android.com/games/sdk/frame-pacing) (Android): short and long frames, stuffed buffers
- [Stat Commands in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/stat-commands-in-unreal-engine)
  (Epic): `stat unit`, `t.HitchFrameTimeThreshold`, `stat DumpHitches`
- [Game engines and shader stuttering: Unreal Engine's solution to the problem](https://www.unrealengine.com/tech-blog/game-engines-and-shader-stuttering-unreal-engines-solution-to-the-problem)
  (Epic, 2025) and [PSO Precaching](https://dev.epicgames.com/documentation/en-us/unreal-engine/pso-precaching-for-unreal-engine)
- [Unreal Engine Optimization Guide: Profiling Fundamentals](https://www.intel.com/content/www/us/en/developer/articles/technical/unreal-engine-optimization-profiling-fundamentals.html)
  (Intel; hitches)
- [Missed frames and frame recovery](https://developers.meta.com/horizon/documentation/unity/os-missed-frames/) (Meta: stale
  frames, judder) and [Asynchronous Timewarp on Oculus Rift](https://developers.meta.com/horizon/blog/asynchronous-timewarp-on-oculus-rift/)
- [What Is Judder? Stutter and Frame-Rate Artifacts](https://www.forasoft.com/learn/video-quality/articles-vqm/judder-stutter-frame-rate-artifacts)
  (Fora Soft)

## Vsync and VRR

- [VkPresentModeKHR](https://docs.vulkan.org/refpages/latest/refpages/source/VkPresentModeKHR.html) (Khronos): FIFO, IMMEDIATE,
  MAILBOX
- [For best performance, use DXGI flip model](https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model)
  (Microsoft)
- [Introducing NVIDIA G-SYNC](https://www.nvidia.com/en-us/geforce/news/introducing-nvidia-g-sync-revolutionary-ultra-smooth-stutter-free-gaming/)
  (NVIDIA, 2013-10-18): why vsync stutters and tears
- [AMD FreeSync](https://www.amd.com/en/products/graphics/technologies/freesync.html) (AMD): Adaptive-Sync, HDMI VRR, low
  framerate compensation
- [G-SYNC 101: Input Lag & Optimal Settings](https://blurbusters.com/gsync/gsync101-input-lag-tests-and-settings/) (Blur Busters)
- [FPS Limiter Lag Analysis For G-Sync & V-Sync](https://www.youtube.com/watch?v=rs0PYCpBJjc) (Battle(non)sense, 2017-01-20) and
  [NVIDIA's NEW FPS Limiter vs. RTSS & In-Engine Limiters](https://www.youtube.com/watch?v=W66pTe8YM2s) (Battle(non)sense,
  2020-01-11)

## Input latency

- [Understanding and Measuring PC Latency](https://developer.nvidia.com/blog/understanding-and-measuring-pc-latency/) (NVIDIA,
  Seth Schneider, 2023-05-05)
- [Introducing NVIDIA Reflex](https://www.nvidia.com/en-us/geforce/news/reflex-low-latency-platform/) (NVIDIA, 2020-09-01) and
  [How To Reduce Lag: A Guide To Better System Latency](https://www.nvidia.com/en-us/geforce/guides/gfecnt/202010/system-latency-optimization-guide/)
  (NVIDIA, 2020)
- [NVIDIA Reflex 2 With New Frame Warp Technology](https://www.nvidia.com/en-us/geforce/news/reflex-2-even-lower-latency-gameplay-with-frame-warp/)
  (NVIDIA, 2025)
- [AMD Radeon Anti-Lag 2](https://gpuopen.com/anti-lag-2/) and
  [Integrating AMD Radeon Anti-Lag 2 SDK in your game](https://gpuopen.com/learn/integrating-amd-radeon-anti-lag-2-sdk-in-your-game/)
  (AMD GPUOpen)
- [Intel Xe Low Latency (XeLL) Developer Guide](https://www.intel.com/content/www/us/en/developer/articles/technical/xell-developer-guide.html)
  (Intel, 2025)
- [AMD FSR 3 announcement](https://gpuopen.com/news/fsr3-announce/) (2023-08-25) and
  [AMD FSR frame generation](https://gpuopen.com/amd-fsr-framegeneration/) (AMD GPUOpen): the frame rate needed before frame
  generation

## Charts and tools

- [CapFrameX](https://github.com/CXWorld/CapFrameX) ([features](https://www.capframex.com/features)): frametime graphs,
  L-shapes, stutter and variance charts
- [TestUFO: stutter](https://testufo.com/stutter) and [animation time graph](https://testufo.com/animation-time-graph) (Blur Busters)
