import "./styles.css";

import { blindTestSlide } from "./blind-test/test-slide";
import { warmupSlide } from "./blind-test/warmup";
import { viewingCheckCard } from "./checks/viewing";
import { startSlides, type Slide } from "./slides";

/** The clips are 1280 x 384 video pixels (the two boxes and a margin, no labels), shown at 1:1 device pixels. */
const VIDEO = { width: 1280, height: 384 };

const welcome: Slide = {
  id: "welcome",
  title: "Welcome",
  render() {
    const body = document.createElement("div");
    body.className = "slide-body";
    body.innerHTML = `
      <p class="wip" role="note"><strong>Unfinished work in progress.</strong> Slides, wording and the test may still change.</p>
      <p class="eyebrow">An interactive explanation</p>
      <h1>Frame pacing, explained</h1>
      <p class="lead">
        A game can run at a perfect 60 fps and still stutter. This page shows why, with videos you compare yourself, and ends in
        a blind test. First, a quick check that your screen shows the videos the way they are meant to be seen.
      </p>`;
    body.append(viewingCheckCard(VIDEO));
    const start = document.createElement("a");
    start.className = "button";
    start.href = "#/best-viewing";
    start.textContent = "Start →";
    body.append(start);
    return body;
  },
};

const bestViewing: Slide = {
  id: "best-viewing",
  title: "Best viewing",
  render() {
    const body = document.createElement("div");
    body.className = "slide-body";
    body.innerHTML = `
      <p class="eyebrow">Before you start</p>
      <h1>Give your eyes the best chance</h1>
      <p class="lead">The differences are milliseconds. Your display, browser and settings can hide them, or add their own.</p>
      <div class="guide">
        <ul class="card checklist">
          <li><strong>60 Hz or a multiple.</strong> Set the display to 60, 120, 180 or 240 Hz in the display settings. Turn VRR
            (G-SYNC, FreeSync) off for the test.</li>
          <li><strong>100 % zoom.</strong> Reset the browser zoom (Ctrl/Cmd + 0) and pinch zoom. Other display scaling is fine:
            the page compensates, as long as the video fits.</li>
          <li><strong>Fullscreen,</strong> on the monitor you watch. Do not move the window between monitors with different
            refresh rates.</li>
          <li><strong>On a TV:</strong> game or PC mode, motion smoothing and interpolation off.</li>
          <li><strong>On a laptop:</strong> plugged in, with the browser's hardware acceleration on.</li>
          <li><strong>Nothing else heavy running:</strong> close other video tabs and busy apps, no screen sharing or remote
            desktop.</li>
          <li><strong>Watch the whole motion</strong> at a normal distance, not one box edge.</li>
        </ul>
      </div>`;
    body.querySelector(".guide")!.append(viewingCheckCard(VIDEO));
    const next = document.createElement("a");
    next.className = "button";
    next.href = "#/warm-up";
    next.textContent = "Continue to the warm-up →";
    body.append(next);
    return body;
  },
};

const warmup: Slide = { id: "warm-up", title: "Warm-up", render: warmupSlide };
const blindTest: Slide = { id: "blind-test", title: "Blind test", render: blindTestSlide };

startSlides(document.querySelector<HTMLElement>("#app")!, [welcome, bestViewing, warmup, blindTest]);
