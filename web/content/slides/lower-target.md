---
title: A lower target
eyebrow: Strategy 2
---

# Run at a lower target frame rate

For when optimizing cannot get the app to hold the higher target, and frames would miss it often rather than in a rare spike. This
strategy then avoids the miss instead of handling it: run at a frame rate every frame can hold with room to spare, and hold
it. If 60 fps on a 60 Hz display does not fit, 30 fps gives every frame twice the time. A 120 Hz display has steps in between: 60
and 40 fps. Below, the price: the same motion at 60 and at 30 fps, both perfectly paced.

:::video pair fast 60 30 nochart

Top: 60 fps. Bottom: 30 fps. Both perfectly paced, every frame showing the moment it is on screen: the bottom one only moves in
steps twice as far.

:::

:::guide

:::card When it fits

- **Optimizing is not enough:** the app cannot hold the higher rate, and the misses would be frequent. A rare spike is better
  handled by one of the other strategies than paid for on every frame.
- **The app and its audience accept it:** a 30 fps mode is familiar on consoles, but given the choice most console players pick the
  higher frame rate (below). PC players are rarely happy with less than 60 fps, and many expect more.
- **The frames fit the lower rate with room to spare,** spikes included, measured on the real content.
- **Steady matters more than fast:** slower motion, and input that does not need every frame of latency back.
- **The platform can hold a frame** for a whole number of refreshes, and for 40 fps the display runs at 120 Hz.

:::

:::card What it costs

- **Smoothness:** at 30 fps every step of the motion is twice as far.
- **Input latency:** each frame takes longer, and waits longer to be shown.
- **Unused headroom:** most frames could have run faster.
- **A frame over even the lower budget still misses,** and then one of the other strategies has to handle it.

:::

:::

What high-end devices do shows what the best experience looks like: there, hardware limits matter least, so the choices of their
makers and players are about the experience itself. {.note}

:::guide

:::card What players choose

Players notice the cost. Presenting the PS5 Pro in September 2024, Sony's Mark Cerny said that when asked to decide on a mode, PS5
players choose performance over fidelity about three quarters of the time
([PS5 Pro Technical Presentation, 2:52](https://www.youtube.com/watch?v=X24BzyzQQ-8&t=172s)). A performance mode is usually
60 fps and a fidelity mode 30 fps, though not in every game, and Sony has not published the data behind the figure. {.note}

:::

:::card What high-end PC gaming chose

Gaming monitors keep climbing: 500 Hz and more are sold, up to 750 Hz, and 1000 Hz monitors were announced for 2026
([FlatpanelsHD, 2025](https://www.flatpanelshd.com/news.php?subaction=showfull&id=1762337599)). In a study of 101 gamers at 60,
144 and 360 Hz, they told 60 from 360 Hz apart but not 144 from 360 Hz, and their aim improved from 60 Hz up, with smaller gains
at the top
([Toth et al., 2026](https://research.nvidia.com/publication/2026-06_monitor-refresh-rate-impacts-fps-video-gamers-perceptions-display-smoothness)).
Earlier NVIDIA research found that much of that gain is the lower latency that comes with the higher rate
([Spjut et al., 2019](https://research.nvidia.com/publication/2019-11_latency-30-ms-benefits-first-person-targeting-tasks-more-refresh-rate-above-60)).
To see it tried: Linus Tech Tips had Shroud and other players compete at 60, 144 and 240 fps
([Does High FPS make you a better gamer?](https://www.youtube.com/watch?v=OX31kZbAXsA), 2019, sponsored by NVIDIA). {.note}

:::

:::card What phone makers chose

High-end phones moved to 90 and 120 Hz displays for "smoother animations, lower latency, and an overall nicer user experience"
([Google, 2020](https://android-developers.googleblog.com/2020/04/high-refresh-rate-rendering-on-android.html)), "making the touch
experience faster and more responsive"
([Apple, iPhone 13 Pro, 2021](https://www.apple.com/newsroom/2021/09/apple-unveils-iphone-13-pro-and-iphone-13-pro-max-more-pro-than-ever-before/)).
Users see it: in a study of 76 people scrolling at 60, 90 and 120 Hz, both higher rates looked smoother than 60 Hz, with little
difference between 90 and 120 Hz ([Li et al., 2025](https://www.tandfonline.com/doi/full/10.1080/0144929X.2025.2462266)). {.note}

:::

:::card What TV boxes chose

A remote is indirect input, and even the Apple TV 4K stays at 60 Hz: it outputs "up to 4K 60Hz"
([FlatpanelsHD](https://www.flatpanelshd.com/review.php?subaction=showfull&id=1668063491)). What it adds is pacing: Match Frame
Rate switches the TV to the content's own rate, doubling 25 and 30 fps to 50 and 60 Hz "while preserving a fluid user interface"
([Apple](https://support.apple.com/en-us/102277)). Android TV does the same, as a mismatch gives "unpleasant motion judder"
([Android](https://developer.android.com/training/tv/playback/adjust-display-settings)). {.note}

:::

:::

Games and phones are also about input latency. A gamepad and a finger on a touch screen are direct input, and at a higher rate
the result of every press or swipe reaches the screen sooner: a frame lasts 33.3 ms at 30 fps and 16.7 ms at 60 fps. Google
names "lower latency" among its reasons. A TV box, driven by a remote, puts even pacing first. More under
[input latency](#/input-latency). {.note}

And it has to be paced right: the next slides show how. {.note}
