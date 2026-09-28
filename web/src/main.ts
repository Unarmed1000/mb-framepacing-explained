import "./styles.css";

import { blindTestSlide } from "./blind-test/test-slide";
import { viewingCheckCard } from "./checks/viewing";
import { EXPLANATION_SLIDES } from "./explain/slides";
import { menuSlide } from "./menu";
import { startSlides, type Slide } from "./slides";
import { motionSwitch } from "./video/motion";

/** Who made the page: on the welcome page and in the top bar. */
const AUTHOR = "Rene Thrane";
const AUTHOR_LINK = "https://www.linkedin.com/in/ren%C3%A9-thrane-7163a17";
const ORGANISATION = "Mana Battery";
const ORGANISATION_LINK = "https://manabattery.com/";

/** The clips are 1280 x 384 video pixels (the two boxes and a margin, no labels), shown at 1:1 device pixels. */
const VIDEO = { width: 1280, height: 384 };

const welcome: Slide = {
  id: "welcome",
  title: "Welcome",
  render() {
    const body = document.createElement("div");
    body.className = "slide-body";
    body.innerHTML = `
      <p class="wip draft-notice" role="note"><strong>A draft.</strong> The slides, wording, diagrams, videos and the blind tests may
        still change, and a few parts are unfinished.</p>
      <p class="eyebrow">An interactive explanation</p>
      <h1>Frame pacing, explained</h1>
      <p class="byline">By <a href="${AUTHOR_LINK}" target="_blank" rel="noopener">${AUTHOR}</a> ·
        <a href="${ORGANISATION_LINK}" target="_blank" rel="noopener">${ORGANISATION}</a></p>
      <p class="lead">
        A game, an interface or any real-time animation can run at a perfect 60 fps and still stutter. This page starts with two blind tests: videos you compare yourself,
        before knowing what to look for. Then it explains what you saw, and how apps and games get it right. First, a quick check that your
        screen shows the videos the way they are meant to be seen.
      </p>
      <p class="note screen-note">Made for a larger display: a computer monitor, a laptop or a TV. The videos are 1280 pixels wide
        and shown pixel for pixel, which a phone screen cannot do. On a phone, it is well worth coming back on a bigger screen.</p>
      <div class="contribute">
        <p class="contribute-title">Know this field? Help improve it</p>
        <p class="note">Found something wrong, or know a topic that belongs here? Corrections and suggestions from people who work
          on this are very welcome, ideally with a source:
          <a href="https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/CONTRIBUTING.md" target="_blank"
            rel="noopener">open an issue or a pull request</a> on GitHub.</p>
      </div>`;
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
          <li><strong>An older or slower monitor</strong> can make some examples harder to see. Slow pixel response
            (grey-to-grey time) smears moving edges into a blur of its own, which can hide small stutters or look like the
            ghosting and blur on the upscaler slides. Strong overdrive can instead add bright or dark halos behind moving edges.
            A fast monitor, with overdrive at its normal setting, shows the examples best.</li>
          <li><strong>Nothing else heavy running:</strong> close other video tabs and busy apps, no screen sharing or remote
            desktop.</li>
          <li><strong>Watch the whole motion</strong> at a normal distance, not one box edge.</li>
        </ul>
      </div>`;
    body.querySelector(".guide")!.append(viewingCheckCard(VIDEO));
    const next = document.createElement("a");
    next.className = "button";
    next.href = "#/menu";
    next.textContent = "Continue →";
    body.append(next);
    return body;
  },
};

// The blind test comes before the explanations, so they cannot give its answers away
startSlides(
  document.querySelector<HTMLElement>("#app")!,
  [welcome, bestViewing, menuSlide, blindTestSlide, ...EXPLANATION_SLIDES],
  [
    { href: "#/menu", label: "Menu" },
    { href: "#/topics", label: "Topics" },
  ],
  `by <a href="${AUTHOR_LINK}" target="_blank" rel="noopener">${AUTHOR}</a>, ` +
    `<a href="${ORGANISATION_LINK}" target="_blank" rel="noopener">${ORGANISATION}</a>`,
  [motionSwitch()],
);
