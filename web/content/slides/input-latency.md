---
title: Input latency
eyebrow: A separate problem
draft: true
---

# Smooth is not the same as responsive

Input lag is the time from pressing a button or moving the mouse until the result is on screen. A game can be perfectly paced and
still feel slow, or respond quickly and stutter. The two meet in the frame queue and in vsync.

:::guide

:::card How much it matters

- **Less critical: indirect input.** A TV interface driven by a remote: a little more latency goes unnoticed, uneven motion does
  not. Smooth pacing can win here.
- **Critical: direct control.** Mouse, keyboard or gamepad, or a finger dragging: every frame of latency is felt, so keep the
  queue short, even at some cost to pacing.

:::

:::card Where it comes from

- **The frame queue:** frames prepared ahead carry older input. NVIDIA Reflex, AMD Anti-Lag 2 and Intel XeLL keep the CPU from
  running ahead of the GPU.
- **Vsync:** frames wait for the refresh, and a full queue makes the whole pipeline wait.
- **Frame generation** raises the displayed frame rate, not how often the game reads input.

:::

:::

[Input latency](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/input-latency.md) {.more}
