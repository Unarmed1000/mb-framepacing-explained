---
title: Two clocks
eyebrow: Stutter at a steady frame rate
---

# Every frame shows a moment

Motion can stutter even when the frame rate never drops, because every frame is timed by two clocks and the frame rate only
looks at one of them.

Every frame a game shows is a picture of one moment of game time, its **animation time**, and it stays on screen for some
**display time**. Motion looks smooth when the two advance together: when the game moves on 16.7 ms from one frame to the next,
the first one stays on screen for 16.7 ms. **Animation error** is how far the two disagree, frame by frame: the next slide shows
it at work. We say _game_ for anything that animates in real time: games, user interfaces, video playback, VR, simulators.

:::video single fast 60 60 top chart

60 fps with the perfect timer: every frame shows exactly the moment it is on screen. The chart shows each frame's animation
error, following the video: always 0.

:::

![Perfect timer: every frame shows the moment it is displayed, so the animation error is 0.](../../../doc/images/timing-perfect-timer.svg)

:::card Reading the diagrams

- A **60 Hz display**, a refresh every 16.7 ms, as in the videos.
- **Render:** each box is one frame, as wide as it takes to render, labelled with its **predicted display time**, when the game
  expects it to be shown. That becomes its animation time.
- The **arrow** is where the game presents it: the frame is done and waits for the next vsync.
- **Display:** which frame is on screen at each refresh. The rows below compute the animation error the way PresentMon does:
  positive is shown too soon, negative too late.

:::
