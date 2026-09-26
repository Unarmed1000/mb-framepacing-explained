# Input latency

Input lag is how long it takes from pressing a button or moving the mouse until the result is on screen. It is a separate problem
from frame pacing: a game can be perfectly paced and still feel slow, or respond quickly and stutter. The two meet in the frame
queue and in vsync, which is why it is here. The videos in this repository do not simulate latency.

## How much it matters

It depends on how directly the input moves what is on screen:

- **Less critical: indirect input.** A TV interface driven by a remote control, a media player: a little more latency goes
  unnoticed, while uneven motion stays visible. Here smooth pacing can win over the last milliseconds, for example with a deeper
  frame queue or half rate.
- **Critical: direct control.** Playing a game with a mouse, keyboard or gamepad (aiming, steering, timing a jump), or dragging and
  scrolling with a finger, where the image has to follow the hand: every frame of latency is felt. These need the latency kept
  low, even at some cost to pacing, and a short frame queue or the low-latency modes below.

## What it is called and how it is measured

| Name                                        | Where                                                                                                                               | What it covers                                                                                         |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| End-to-end system latency, click-to-display | [NVIDIA](https://developer.nvidia.com/blog/understanding-and-measuring-pc-latency/)                                                 | Peripheral latency + PC latency + display latency                                                      |
| PC latency (PCL)                            | NVIDIA; `MsPCLatency` in [PresentMon](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md#csv-columns) | From the PC receiving the input until the frame is sent to the display                                 |
| Click-to-photon                             | `MsClickToPhotonLatency`, `MsAllInputToPhotonLatency` (PresentMon)                                                                  | From the earliest mouse click (or any input) that contributed to a frame until that frame is displayed |
| Button to pixel                             | [Digital Foundry](https://www.youtube.com/watch?v=TuVAMvbFCW4)                                                                      | The same idea, measured on screen                                                                      |

PresentMon's numbers are estimates from software events; `MsPCLatency` needs a game that sends Reflex-style latency markers
(`--track_pc_latency`). Hardware tools measure the photons: NVIDIA's LDAT, or a high-speed camera filming a click and the screen.

## Where it comes from

- **The frame queue.** When the GPU is the bottleneck, the CPU keeps preparing frames and they queue up in front of the GPU; each
  frame in the queue is input that is that much older when it reaches the screen
  ([NVIDIA Reflex](https://www.nvidia.com/en-us/geforce/news/reflex-low-latency-platform/)).
- **Vsync.** Frames wait for the display's refresh, and with a full queue the whole pipeline waits: NVIDIA's "back pressure" (see
  [vsync](display-sync.md#vsync)).
- **The display** adds its own processing and pixel response time.

## Reducing it

| Technology                                                                                                                    | What it does                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [NVIDIA Reflex](https://www.nvidia.com/en-us/geforce/news/reflex-low-latency-platform/)                                       | Keeps the CPU from running ahead of the GPU, so the render queue stays empty; with G-SYNC and vsync on it also caps the frame rate just under the refresh rate                                                |
| [NVIDIA Reflex 2 Frame Warp](https://www.nvidia.com/en-us/geforce/news/reflex-2-even-lower-latency-gameplay-with-frame-warp/) | Updates the rendered frame "based on the latest mouse input right before it is sent to the display"                                                                                                           |
| [AMD Anti-Lag 2](https://gpuopen.com/anti-lag-2/)                                                                             | "CPU frames are prevented from running too far ahead of GPU frames" ([SDK guide](https://gpuopen.com/learn/integrating-amd-radeon-anti-lag-2-sdk-in-your-game/)): the game waits just before it samples input |
| [Intel XeLL](https://www.intel.com/content/www/us/en/developer/articles/technical/xell-developer-guide.html)                  | Intel's latency reduction SDK for the same purpose                                                                                                                                                            |

These SDKs also mark when each frame's simulation starts. PresentMon uses that as the frame's `AnimationTime`, which makes its
animation error exact instead of estimated from the CPU start (see the [vocabulary](vocabulary.md)).

## Frame generation

Frame generation (DLSS 3 and later, FSR 3) inserts generated frames between rendered ones. It raises the displayed frame rate, but
not how often the game reads input, and it holds a rendered frame back to generate the one before it. AMD's advice: run at least
60 fps before frame generation ([FSR 3](https://gpuopen.com/news/fsr3-announce/)), and "sub-30fps pre-interpolation should be
absolutely avoided" ([FSR frame generation](https://gpuopen.com/amd-fsr-framegeneration/)). Digital Foundry measured it in their
[DLSS 3 analysis](https://www.youtube.com/watch?v=92ZqYaPXxas).

## Latency and pacing

The two often pull the same way: a short queue and a frame rate cap just under the refresh rate lower the latency and also keep
the frame times even, and Battle(non)sense measured how much each kind of cap costs
([G-Sync & V-Sync](https://www.youtube.com/watch?v=rs0PYCpBJjc),
[NVIDIA's limiter vs. RTSS and in-engine](https://www.youtube.com/watch?v=W66pTe8YM2s)). Where they pull apart, a deeper queue
absorbs uneven frametimes and smooths delivery, at the price of older input on screen.
