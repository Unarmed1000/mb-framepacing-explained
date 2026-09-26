// The explanation slides, after the blind test: what the visitor just saw, in the order of the docs (the README's overview, then
// display sync, the strategies and input latency), with the timing diagrams of doc/images and a live clip where one helps.

import halfRateBad from "../../../doc/images/timing-half-rate-bad-pacing.svg?url";
import halfRateEven from "../../../doc/images/timing-half-rate-even.svg?url";
import perfectTimer from "../../../doc/images/timing-perfect-timer.svg?url";
import perfectVsJitter from "../../../doc/images/timing-perfect-vs-jitter.svg?url";
import recoveryHalfRate from "../../../doc/images/timing-recovery-half-rate.svg?url";
import recoveryTargeting from "../../../doc/images/timing-recovery-targeting.svg?url";
import slowFrames from "../../../doc/images/timing-slow-frames.svg?url";
import switchingHysteresis from "../../../doc/images/timing-switching-hysteresis.svg?url";
import switchingNaive from "../../../doc/images/timing-switching-naive.svg?url";
import timerJitter from "../../../doc/images/timing-timer-jitter.svg?url";
import vrrSlowFrames from "../../../doc/images/timing-vrr-slow-frames.svg?url";
import type { Slide } from "../slides";
import { liveComparison, singleBox } from "./live";

const REPOSITORY = "https://github.com/Unarmed1000/mb-framepacing-explained";
const SISTER = "https://github.com/Unarmed1000/mb-framepacing";
/** A page of this repository's docs on GitHub. */
const doc = (path: string): string => `${REPOSITORY}/blob/master/${path}`;
/** The Analyze page of mb-framepacing: linked from its repository, not copied. */
const ANALYZE_SCREENSHOT = "https://raw.githubusercontent.com/Unarmed1000/mb-framepacing/master/doc/images/gui-analysis.png";

/** A slide body: eyebrow, heading and lead from the arguments, then the rest of the HTML (static content only). */
function body(eyebrow: string, heading: string, lead: string, rest: string): HTMLElement {
  const element = document.createElement("div");
  element.className = "slide-body explain";
  element.innerHTML = `
    <p class="eyebrow">${eyebrow}</p>
    <h1>${heading}</h1>
    <p class="lead">${lead}</p>
    ${rest}`;
  return element;
}

/** A timing diagram, its caption as the alt text: each diagram has its own title, description and dark grey card. */
const figure = (src: string, caption: string): string =>
  `<figure class="diagram"><img src="${src}" alt="${caption}" loading="lazy" /></figure>`;

const more = (href: string, text: string): string =>
  `<p class="more"><a href="${href}" target="_blank" rel="noopener">${text} ↗</a></p>`;

const twoClocks: Slide = {
  id: "two-clocks",
  title: "Two clocks",
  render() {
    const element = body(
      "What you just saw",
      "Every frame shows a moment",
      `Every frame a game shows is a picture of one moment of game time, its <strong>animation time</strong>, and it stays on screen
      for some <strong>display time</strong>. Motion looks smooth when the two advance together: a frame that shows 16.7 ms more of
      the game stays on screen for 16.7 ms. <strong>Animation error</strong> is how far they disagree, per frame, in milliseconds,
      as PresentMon measures it. A high average frame rate says nothing about it.`,
      `<div class="single-holder"></div>
      ${figure(perfectTimer, "Perfect timer: every frame shows the moment it is displayed, so the animation error is 0.")}
      <div class="card">
        <h2>Reading the diagrams</h2>
        <ul class="points">
          <li>A <strong>10 Hz display</strong>, a refresh every 100 ms: chosen so the steps are easy to see and the numbers easy to work
            with.</li>
          <li><strong>Render:</strong> each box is one frame, as wide as it takes to render, labelled with its
            <strong>predicted display time</strong>, when the game expects it to be shown. That becomes its animation time.</li>
          <li>The <strong>arrow</strong> is where the game presents it: the frame is done and waits for the next vsync.</li>
          <li><strong>Display:</strong> which frame is on screen at each refresh. The rows below compute the animation error the way
            PresentMon does: positive is shown too soon, negative too late.</li>
        </ul>
      </div>`,
    );
    element
      .querySelector(".single-holder")!
      .replaceWith(
        singleBox("normal", "60", "60 fps with the perfect timer: every frame shows exactly the moment it is on screen."),
      );
    return element;
  },
};

const timerJitterSlide: Slide = {
  id: "timer-jitter",
  title: "Timer jitter",
  render() {
    const element = body(
      "Two ways it goes wrong · 1",
      "On time, but showing the wrong moment",
      `Frames reach the screen perfectly evenly, but the animation time advances unevenly: the game reads its wall clock a little
      early or late after each flip, and renders the frame for that reading (<strong>delta time jitter</strong>). Gamers Nexus
      compare it to a flipbook with unevenly drawn pages, flipped at a steady tempo.`,
      `<div class="live-holder"></div>
      ${figure(timerJitter, "Timer jitter: frames reach the screen on time, but each shows a moment a little off.")}`,
    );
    element
      .querySelector(".live-holder")!
      .replaceWith(
        liveComparison(
          "normal",
          "60",
          "60-naive-4ms",
          "Top: the perfect timer. Bottom: the same 60 fps with a naive timer that reads the clock up to 4 ms early or late. Every frame of both is on " +
            "screen for exactly one refresh; the chart shows each frame's animation error, following the video.",
        ),
      );
    return element;
  },
};

const invisible: Slide = {
  id: "invisible",
  title: "Invisible to the numbers",
  render() {
    const element = body(
      "Why frame rate cannot see it",
      "Same frame rate, same frame times, different motion",
      `Timer jitter is invisible to the usual numbers. Frame rate, frametime, display time and a frame-time graph are identical to
      the perfect timer's: every frame is on screen for exactly one refresh. The eye still sees slightly uneven motion, and only
      animation error shows why, because only it looks at the moment each frame shows.`,
      `${figure(perfectVsJitter, "Same frame rate, same frametimes, different motion: only the animation error differs.")}`,
    );
    element.append(
      liveComparison(
        "normal",
        "60",
        "60-naive-4ms",
        "The same two timers live: both boxes at 60 fps, every frame on screen for exactly one refresh. Only the animation error, " +
          "in the chart, shows why the bottom one stutters.",
      ),
    );
    return element;
  },
};

const vsyncTimer: Slide = {
  id: "vsync-timer",
  title: "The vsync timer",
  render: () =>
    body(
      "First things first",
      "Fix the animation time before the pacing",
      `A game that renders its frames for the wrong moment has animation error on every frame, however well it paces them. On a
      fixed refresh display with vsync on, every frame appears a whole number of refreshes after the previous one, so the animation
      time only has to advance in whole refreshes. That needs no modern API or extension. It is for vsync on: with VRR or vsync
      off there is no refresh grid to round to, and they need other solutions or the more modern APIs that report when frames
      appear.`,
      `<div class="guide">
        <div class="card">
          <h2>The vsync timer</h2>
          <ol class="points">
            <li><strong>Know the refresh period:</strong> a hard-coded value to start, then the display mode where the platform
              reports it, or the average time between the loop's own frames (59.94 Hz is not 60 Hz).</li>
            <li><strong>Measure the time since the previous frame</strong> with the wall clock, as the naive timer does, and
              <strong>round it to whole refreshes</strong>: at least the swap interval.</li>
            <li><strong>Render the frame for its predicted display time:</strong> the previous frame's display time plus that many
              refreshes.</li>
          </ol>
        </div>
        <div class="card">
          <h2>What it relies on</h2>
          <ul class="points">
            <li>Rounding removes wake-up jitter under <strong>half a refresh</strong>: 8.3 ms at 60 Hz, but only 2.1 ms at
              240 Hz.</li>
            <li>A missed vsync still costs one late frame, but it shows up as a whole extra refresh in the next measurement, so the
              frame after it catches up exactly.</li>
            <li>Vsync on, a fixed refresh rate and a loop paced by vsync.</li>
            <li><strong>Watch for drift.</strong> The timer counts refreshes, so it runs on the display's clock: take 60 Hz for a
              59.94 Hz display and it is 0.1 % off, about 3.6 s per hour. The picture stays smooth, but audio and a game server run on
              other clocks and slowly disagree. Measure the period over many frames and slew towards the clock that matters in tiny
              steps; paying it back in whole refreshes is a visible hitch.</li>
            <li>It is the perfect timer of every diagram here and the ideal timer of the videos.</li>
          </ul>
        </div>
      </div>
      <p class="more">
        <a href="${doc("doc/frame-pacing-strategies.md#first-get-the-animation-time-right")}" target="_blank" rel="noopener">Getting the animation time right ↗</a>
        <a href="${doc("doc/frame-pacing-strategies.md#appendix-a-vsync-signals-per-platform")}" target="_blank" rel="noopener">Vsync signals per platform ↗</a>
        <a href="${doc("doc/frame-pacing-strategies.md#appendix-b-drift")}" target="_blank" rel="noopener">Drift ↗</a>
      </p>`,
    ),
};

const slowFramesSlide: Slide = {
  id: "slow-frames",
  title: "Slow frames",
  render: () =>
    body(
      "Two ways it goes wrong · 2",
      "When a frame misses its refresh",
      `The other way round: the animation time advances evenly, but frames reach the screen unevenly (<strong>frame pacing</strong>).
      A frame over its budget shows a refresh late, a <strong>hitch</strong>: the previous frame is held, the late frame shows a
      moment that has already passed, and the next one jumps ahead. The flipbook's pages are drawn evenly, but flipped at an uneven
      tempo.`,
      `${figure(slowFrames, "Slow frames: the previous frame is held, the late frame shows a past moment and the next one jumps ahead.")}`,
    ),
};

const halfRate: Slide = {
  id: "half-rate",
  title: "Half rate",
  render: () =>
    body(
      "Frame rate targets",
      "30 fps, done right and done wrong",
      `A fixed target that divides the refresh rate gives even pacing: 60 or 30 fps on 60 Hz, 40 fps on 120 Hz. But a cap only
      helps if every frame is held for the same number of refreshes. A frame that is ready early and not held back appears after
      one refresh, and the next one stays for three: Digital Foundry keep finding 30 fps caps like that, and in Bloodborne they
      swung "between 16ms and 66ms".`,
      `<div class="figures">
        ${figure(halfRateEven, "Evenly paced: each frame held for two refreshes, as intended.")}
        ${figure(halfRateBad, "Bad frame pacing: frames held for 1 and 3 refreshes instead of 2.")}
      </div>
      <div class="card">
        <h2>Holding a frame for two refreshes</h2>
        <ul class="points">
          <li><strong>Swap interval:</strong> <code>Present(SyncInterval)</code>, <code>eglSwapInterval</code>, Unity's
            <code>vSyncCount</code>. Whole refreshes, counted from the previous flip.</li>
          <li><strong>Scheduled present:</strong> the frame says when it should appear (<code>VK_EXT_present_timing</code>,
            Android's presentation time, Metal's <code>present(afterMinimumDuration:)</code>).</li>
          <li><strong>Sleep, then present:</strong> works anywhere, but the thread wakes up a little late, differently every time.
            Unity: "Always use vSyncCount &gt; 0 when smooth frame pacing is needed".</li>
        </ul>
      </div>
      ${more(doc("doc/frame-pacing-strategies.md#holding-a-frame-for-more-than-one-refresh"), "Holding a frame for more than one refresh")}`,
    ),
};

const switching: Slide = {
  id: "switching",
  title: "Switching rates",
  render: () =>
    body(
      "Graceful degradation",
      "Do not switch back after the first fast frame",
      `A game that cannot hold full rate everywhere can drop to half rate, and go back up when frames fit again. A naive engine goes
      back after the first frame that fits: in a busy stretch the next slow frame misses its refresh again, and every switch costs a
      late frame and a jump. With <strong>hysteresis</strong> it goes back up only after several fast frames in a row.`,
      `<div class="figures">
        ${figure(switchingNaive, "Without hysteresis: every switch back up costs a late frame.")}
        ${figure(switchingHysteresis, "With hysteresis (three fast frames): only the first slow frame is late.")}
      </div>
      <p class="note">Android's Frame Pacing library (Swappy) does this on its own: it decides over 2 s of frame times, drops to a
      longer swap interval when more than 10 % of the frames missed, and goes back only when none did, with 1 ms to spare.</p>
      ${more(doc("doc/frame-pacing-strategies.md#switching-between-full-and-half-rate"), "Switching between full and half rate")}`,
    ),
};

const recovery: Slide = {
  id: "recovery",
  title: "Recovering",
  render: () =>
    body(
      "After a spike",
      "Back to full rate after one slow frame",
      `One frame, a shader compile or a streaming spike, takes longer than a refresh, and every frame after it fits again. Switching
      to half rate recovers safely but holds the next frames for two refreshes each. Giving each frame its own target brings the
      game back a frame sooner, with the same single late frame, where the API can schedule each present.`,
      `<div class="figures">
        ${figure(recoveryHalfRate, "Recovering at half rate: the frames after the spike held for two refreshes.")}
        ${figure(recoveryTargeting, "Per-frame targets: back at full rate a frame sooner.")}
      </div>
      ${more(doc("doc/frame-pacing-strategies.md#recovering-from-an-overshoot"), "Recovering from an overshoot")}`,
    ),
};

const vrr: Slide = {
  id: "vrr",
  title: "VRR",
  render: () =>
    body(
      "G-SYNC, FreeSync",
      "VRR changes when, not which moment",
      `With variable refresh rate the display refreshes when the frame is ready, instead of the frame waiting for the display. Inside
      the display's range there is no tearing and no rounding to whole refreshes. But it changes <em>when</em> a frame appears, not
      <em>which animation time</em> the game rendered it for.`,
      `${figure(vrrSlowFrames, "The same slow frames on VRR: the errors shrink from 100 to 25 ms, but the frames are still late.")}
      <div class="card">
        <h2>What VRR does not fix</h2>
        <ul class="points">
          <li><strong>Delta time jitter stays:</strong> a frame rendered for the wrong moment is wrong however well it is shown.</li>
          <li><strong>Hitches stay:</strong> an 80 ms frame is still an 80 ms frame; VRR only shows it as soon as it is ready.</li>
          <li><strong>Uneven frame times reach the screen:</strong> without vsync's grid, the animation time step has to match the
            game's own frame times.</li>
        </ul>
        <p class="note">How best to pace with VRR or vsync off is still an open question here.</p>
      </div>
      ${more(doc("doc/display-sync.md"), "Vsync, VRR and frame rate targets")}`,
    ),
};

const inputLatency: Slide = {
  id: "input-latency",
  title: "Input latency",
  render: () =>
    body(
      "A separate problem",
      "Smooth is not the same as responsive",
      `Input lag is the time from pressing a button or moving the mouse until the result is on screen. A game can be perfectly
      paced and still feel slow, or respond quickly and stutter. The two meet in the frame queue and in vsync.`,
      `<div class="guide">
        <div class="card">
          <h2>How much it matters</h2>
          <ul class="points">
            <li><strong>Less critical: indirect input.</strong> A TV interface driven by a remote: a little more latency goes
              unnoticed, uneven motion does not. Smooth pacing can win here.</li>
            <li><strong>Critical: direct control.</strong> Mouse, keyboard or gamepad, or a finger dragging: every frame of latency
              is felt, so keep the queue short, even at some cost to pacing.</li>
          </ul>
        </div>
        <div class="card">
          <h2>Where it comes from</h2>
          <ul class="points">
            <li><strong>The frame queue:</strong> frames prepared ahead carry older input. NVIDIA Reflex, AMD Anti-Lag 2 and Intel
              XeLL keep the CPU from running ahead of the GPU.</li>
            <li><strong>Vsync:</strong> frames wait for the refresh, and a full queue makes the whole pipeline wait.</li>
            <li><strong>Frame generation</strong> raises the displayed frame rate, not how often the game reads input.</li>
          </ul>
        </div>
      </div>
      ${more(doc("doc/input-latency.md"), "Input latency")}`,
    ),
};

const measure: Slide = {
  id: "measure",
  title: "Measure it yourself",
  render: () =>
    body(
      "The sister project",
      "Measure it on a real display: mb-framepacing",
      `The videos here are simulated. <a href="${SISTER}" target="_blank" rel="noopener">mb-framepacing</a> measures animation error
      on the real display output, frame by frame, with the goal of making it easy to measure. It is a cooperative tool: the
      application writes its frame index and exact animation time into every frame, so neither clock is estimated.`,
      `<div class="guide">
        <div class="card">
          <h2>How it works</h2>
          <ol class="points">
            <li><strong>Once: add the marker.</strong> A small library (C++, C#, or a Unity package) draws a marker with the frame
              index and animation time as the last thing in every frame.</li>
            <li><strong>Record:</strong> a capture card records the display signal with its own clock, at the display's refresh
              rate (or import a video from a high-speed camera).</li>
            <li><strong>Analyse:</strong> it reads the marker back from every captured frame and compares the animation time with
              when the frame really appeared: animation error, display times, dropped and torn frames, as a GUI, CSV or JSON.</li>
          </ol>
          <p class="note">It needs the application's source code: it cannot measure a game you cannot rebuild.</p>
        </div>
        <figure class="screenshot">
          <a href="${SISTER}#readme" target="_blank" rel="noopener">
            <img src="${ANALYZE_SCREENSHOT}" alt="The Analyze page of mb-framepacing: every presented frame, its animation error and the headline numbers" loading="lazy" />
          </a>
          <figcaption>The Analyze page: every presented frame, its animation error and the headline numbers (from the
            mb-framepacing repository).</figcaption>
        </figure>
      </div>
      <p class="more">
        <a href="${SISTER}#readme" target="_blank" rel="noopener">README ↗</a>
        <a href="${SISTER}/blob/master/doc/integrating.md" target="_blank" rel="noopener">Integrating the marker ↗</a>
        <a href="${SISTER}/blob/master/doc/unity.md" target="_blank" rel="noopener">Unity ↗</a>
        <a href="${SISTER}/blob/master/doc/usage.md" target="_blank" rel="noopener">Using mb-framepacing ↗</a>
      </p>`,
    ),
};

/** A group of links: [title, href, note]. */
function links(title: string, items: readonly [string, string, string][]): string {
  const rows = items
    .map(([text, href, note]) => `<li><a href="${href}" target="_blank" rel="noopener">${text} ↗</a><span>${note}</span></li>`)
    .join("");
  return `<div class="card"><h2>${title}</h2><ul class="links">${rows}</ul></div>`;
}

const furtherReading: Slide = {
  id: "further-reading",
  title: "Further reading",
  render: () =>
    body(
      "Go deeper",
      "Further reading",
      `The docs of this project go into more detail, with every source linked. Much of the research was AI-assisted: sources were
      fetched and quotes checked, but check the linked source before relying on a detail.`,
      `<div class="guide">
        ${links("This project", [
          ["Overview and quick vocabulary", `${REPOSITORY}#readme`, "Frame pacing in one minute"],
          ["Vocabulary", doc("doc/vocabulary.md"), "Every term and its other names (PresentMon, Digital Foundry, engines)"],
          ["Vsync, VRR and frame rate targets", doc("doc/display-sync.md"), "Present modes, G-SYNC, FreeSync, fixed or adaptive"],
          [
            "Advanced frame pacing strategies",
            doc("doc/frame-pacing-strategies.md"),
            "The vsync timer, half rate, switching, recovery",
          ],
          ["Input latency", doc("doc/input-latency.md"), "Measuring it, Reflex, Anti-Lag 2, frame generation"],
          ["Measured in real games", doc("doc/measured-errors.md"), "Animation error in real games, next to the videos' timers"],
          ["All the articles and videos", doc("doc/further-reading.md"), "Grouped by subject"],
        ])}
        ${links("Sources to start with", [
          [
            "Animation Error Methodology",
            "https://gamersnexus.net/gpus-gn-extras-cpus/problem-gpu-benchmarks-reality-vs-numbers-animation-error-methodology-white",
            "Gamers Nexus: the metric and the flipbook",
          ],
          ["PresentMon", "https://github.com/GameTechDev/PresentMon", "Intel: MsAnimationError and the other columns"],
          [
            "30FPS 'Bad' Frame-Pacing",
            "https://www.youtube.com/watch?v=tvzdJh3bvAs",
            "Digital Foundry: why so many games get it wrong",
          ],
          [
            "Fixing Time.deltaTime in Unity 2020.2",
            "https://unity.com/blog/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay",
            "Unity: timer jitter, and the fix",
          ],
          [
            "Frame Pacing library",
            "https://developer.android.com/games/sdk/frame-pacing",
            "Android (Swappy): short and long frames",
          ],
          ["TestUFO: stutter", "https://testufo.com/stutter", "Blur Busters: see it in your browser"],
        ])}
      </div>
      <p class="note">© 2026 Mana Battery ApS ·
        <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/" target="_blank" rel="noopener">CC BY-NC-ND 4.0</a> ·
        <a href="${REPOSITORY}" target="_blank" rel="noopener">mb-framepacing-explained on GitHub</a></p>`,
    ),
};

/** The explanation slides, in order. */
export const EXPLANATION_SLIDES: readonly Slide[] = [
  twoClocks,
  timerJitterSlide,
  invisible,
  vsyncTimer,
  slowFramesSlide,
  halfRate,
  switching,
  recovery,
  vrr,
  inputLatency,
  measure,
  furtherReading,
];
