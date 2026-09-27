// The explanation slides, after the blind test: what the visitor just saw, in the order of the docs (the README's overview, then
// display sync, the strategies and input latency), with the timing diagrams of doc/images and a live clip where one helps.

import averageHalfRate from "../../../doc/images/chart-average-half-rate.svg?url";
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
import vsyncTimerDiagram from "../../../doc/images/timing-vsync-timer.svg?url";
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
      "Stutter at a steady frame rate",
      "Every frame shows a moment",
      `Motion can stutter even when the frame rate never drops, because every frame is timed by two clocks and the frame rate only
      looks at one of them. Every frame a game shows is a picture of one moment of game time, its <strong>animation time</strong>, and it
      stays on screen for some <strong>display time</strong>. Motion looks smooth when the two advance together: a frame that shows 16.7 ms more of
      the game stays on screen for 16.7 ms. <strong>Animation error</strong> is how far they disagree, per frame, in milliseconds,
      as PresentMon measures it. A high average frame rate says nothing about it. We say <em>game</em> for anything that animates in real time: games, user interfaces, video playback, VR, simulators.`,
      `<div class="single-holder"></div>
      ${figure(perfectTimer, "Perfect timer: every frame shows the moment it is displayed, so the animation error is 0.")}
      <div class="card">
        <h2>Reading the diagrams</h2>
        <ul class="points">
          <li>A <strong>60 Hz display</strong>, a refresh every 16.7 ms, as in the videos.</li>
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
        singleBox(
          "fast",
          "60",
          "60",
          "top",
          "60 fps with the perfect timer: every frame shows exactly the moment it is on screen. The chart shows each frame's " +
            "animation error, following the video: always 0.",
          true,
        ),
      );
    return element;
  },
};

const timerJitterSlide: Slide = {
  id: "timer-jitter",
  title: "Delta time jitter",
  render() {
    const element = body(
      "The first cause of stutter",
      "On time, but showing the wrong moment",
      `Frames reach the screen perfectly evenly, but the animation time advances unevenly: the game reads its wall clock a little
      early or late after each flip, and renders the frame for that reading (<strong>delta time jitter</strong>). Gamers Nexus
      compare it to a flipbook with unevenly drawn pages, flipped at a steady tempo.`,
      `<div class="single-holder"></div>
      ${figure(timerJitter, "Delta time jitter: frames reach the screen on time, but each shows a moment a little off.")}`,
    );
    element
      .querySelector(".single-holder")!
      .replaceWith(
        singleBox(
          "fast",
          "60",
          "60-naive-5ms",
          "bottom",
          "60 fps with a naive timer that reads the clock up to 5 ms early or late: every frame on screen on time, but showing a " +
            "moment a little off. The chart shows each frame's animation error, following the video.",
          true,
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
      "Delta time jitter",
      "Same frame rate, same frame times, different motion",
      `<strong>Delta time jitter</strong> is invisible to the usual numbers. Frame rate, frametime, display time and a frame-time graph are identical to
      the perfect timer's: every frame is on screen for exactly one refresh. The eye still sees slightly uneven motion, and only
      <strong>animation error</strong> shows why, because only it looks at the moment each frame shows.`,
      `${figure(perfectVsJitter, "Same frame rate, same frametimes, different motion: only the animation error differs.")}`,
    );
    // The video above the diagram, as on the slides before
    element
      .querySelector(".lead")!
      .after(
        liveComparison(
          "fast",
          "60",
          "60-naive-5ms",
          "The same two timers live: both boxes at 60 fps, every frame on screen for exactly one refresh, and still the bottom one " +
            "stutters.",
          false,
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
      "The fix for delta time jitter",
      "Fix the animation time before the pacing",
      `A game that renders its frames for the wrong moment has animation error on every frame, however well it paces them. On a
      fixed refresh display with vsync on, every frame appears a whole number of refreshes after the previous one, so the animation
      time only has to advance in whole refreshes. That needs no modern API or extension. It is for vsync on: with VRR or vsync
      off there is no refresh grid to round to, and they need other solutions or the more modern APIs that report when frames
      appear.`,
      `${figure(vsyncTimerDiagram, "The vsync timer: the same uneven clock as with delta time jitter, each measured frame time rounded to whole refreshes, so the animation error is 0.")}
      <div class="guide">
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
      "The second cause of stutter",
      "When a frame misses its refresh",
      `With the animation time right, stutter has one more cause: frames that reach the screen late or unevenly (<strong>frame
      pacing</strong>). A frame over its budget shows a refresh late, a <strong>hitch</strong>: the previous frame is held, the late frame shows a
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
      "Half rate",
      "Holding every frame for two refreshes",
      `At half rate, 30 fps on a 60 Hz display, every frame should stay on screen for exactly two refreshes. A game that caps its
      frame rate with its own clock instead, and shows each frame at the next vsync once it is done, gets frames held for three
      refreshes and then one: every frame renders in time, and only the pacing is wrong. Digital Foundry keep finding 30 fps caps
      like that. Bloodborne had it together with real performance drops, and a fan patch that only changes how often frames are
      flipped fixes its pacing.`,
      `<div class="figures">
        ${figure(halfRateEven, "Evenly paced: each frame held for two refreshes, as intended.")}
        ${figure(halfRateBad, "Bad frame pacing: frames held for 3 and 1 refreshes instead of 2, although every frame renders in time.")}
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
      `Everything so far assumed a fixed refresh rate with vsync on. VRR removes the refresh grid: the display refreshes when the
      frame is ready, instead of the frame waiting for the display. Inside
      the display's range there is no tearing and no rounding to whole refreshes. But it changes <em>when</em> a frame appears, not
      <em>which animation time</em> the game rendered it for.`,
      `${figure(vrrSlowFrames, "The same slow frames on VRR: the errors shrink from 16.7 to 4.2 ms, but the frames are still late.")}
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

const PRESENTMON = "https://github.com/GameTechDev/PresentMon";

const measure: Slide = {
  id: "measure",
  title: "Measuring it",
  render: () =>
    body(
      "Measure it yourself",
      "How to measure animation error",
      `<a href="#/two-clocks">Animation error</a> needs two clocks for every frame: the moment it shows (its animation time) and
      when it reached the screen (its display time). The ways to measure it differ in where they get each, and so in what they
      can catch.`,
      `<h2 class="section-title">Why the usual numbers miss it</h2>
      <p class="note">The average frame rate is the same for evenly and badly paced 30 fps, and frame times are the same for a
        perfect and a <a href="#/invisible">jittery timer</a>: only animation error tells them apart.</p>
      ${figure(averageHalfRate, "Same 30 fps on average, different motion: 60 Hz, two refreshes every time, or three and then one.")}
      <h2 class="section-title">Ways to measure it</h2>
      <div class="card">
        <table class="ways">
          <thead>
            <tr><th>Way</th><th>Needs</th><th>Animation time</th><th>Display time</th><th>Catches</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><a href="${PRESENTMON}" target="_blank" rel="noopener"><strong>PresentMon</strong></a>, also as Intel's overlay</td>
              <td>Any app on Windows, games included, nothing changed</td>
              <td>Estimated: when the CPU starts the frame; exact when it sends Reflex, XeLL or Anti-Lag 2 markers</td>
              <td>Estimated from software events</td>
              <td>Both causes, approximately</td>
            </tr>
            <tr>
              <td><strong>The app's own log</strong></td>
              <td>The source code, and the platform's presentation feedback</td>
              <td>Exact: the app knows it</td>
              <td>As the platform reports it (DXGI frame statistics, Vulkan present timing, Android's Choreographer, Wayland
                presentation-time, Metal)</td>
              <td>Both causes</td>
            </tr>
            <tr>
              <td><a href="${SISTER}" target="_blank" rel="noopener"><strong>mb-framepacing</strong></a></td>
              <td>The source code (a marker drawn into every frame) and a capture card</td>
              <td>Exact: written into the frame</td>
              <td>Measured on the display signal</td>
              <td>Both causes, on the real output</td>
            </tr>
            <tr>
              <td><strong>Capture or camera only</strong>: an FCAT-style overlay, a high-speed camera</td>
              <td>Any app</td>
              <td>None</td>
              <td>Measured</td>
              <td>Late and uneven frames only: blind to delta time jitter</td>
            </tr>
          </tbody>
        </table>
      </div>
      <h2 class="section-title">mb-framepacing: measured on the display</h2>
      <div class="guide">
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
          <p class="note">It needs the application's source code: it cannot measure an application you cannot rebuild.</p>
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
        <a href="${PRESENTMON}/blob/main/README-ConsoleApplication.md#csv-columns" target="_blank" rel="noopener">PresentMon's columns ↗</a>
        <a href="${SISTER}#readme" target="_blank" rel="noopener">mb-framepacing ↗</a>
        <a href="${SISTER}/blob/master/doc/integrating.md" target="_blank" rel="noopener">Integrating the marker ↗</a>
        <a href="${doc("doc/measured-errors.md")}" target="_blank" rel="noopener">Measured in real games ↗</a>
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
            "Unity: delta time jitter, and the fix",
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

/** The topics, each a group of slides: the page before the first one links to each topic's first slide. `about` is HTML. */
const TOPICS: readonly { name: string; about: string; slides: readonly Slide[] }[] = [
  {
    name: "Stutter at a steady frame rate",
    about: "Animation error, and the first cause of stutter: <strong>delta time jitter</strong>.",
    slides: [twoClocks, timerJitterSlide, invisible],
  },
  {
    name: "Fixing delta time jitter",
    about: "The vsync timer: round each measured frame time to whole refreshes, so every frame shows the moment it is on screen.",
    slides: [vsyncTimer],
  },
  {
    name: "Stutter from late frames",
    about:
      "The second cause of stutter, <strong>bad frame pacing</strong>: frames that reach the screen late or unevenly, and how engines hold and switch rates.",
    slides: [slowFramesSlide, halfRate, switching, recovery],
  },
  {
    name: "Beyond vsync: VRR and input latency",
    about: "What VRR changes, and how pacing meets input latency.",
    slides: [vrr, inputLatency],
  },
  { name: "Go further", about: "How to measure animation error, and where to read more.", slides: [measure, furtherReading] },
];

const topics: Slide = {
  id: "topics",
  title: "Topics",
  render() {
    const element = body(
      "How it works",
      "Pick a topic",
      `<strong>Stutter</strong> is what you see: motion that jumps or hangs instead of gliding. It has two causes,
      <strong>delta time jitter</strong> and bad <strong>frame pacing</strong>, and one measurement that catches both:
      <strong>animation error</strong>. Go through the slides in order with Next, or jump straight to a topic.`,
      `<div class="topics"></div>`,
    );
    const grid = element.querySelector(".topics")!;
    for (const topic of TOPICS) {
      // The whole card is one link, to the topic's first slide
      const card = document.createElement("a");
      card.className = "card topic-card";
      card.href = `#/${topic.slides[0]?.id ?? ""}`;
      const drafts = topic.slides.filter((slide) => WORK_IN_PROGRESS.has(slide)).length;
      const mark =
        drafts === 0
          ? ""
          : `<span class="topic-wip">${drafts === topic.slides.length ? "Work in progress" : "Partly work in progress"}</span>`;
      card.innerHTML = `<h2></h2>${mark}<p></p><span class="topic-start">Start →</span>`;
      card.querySelector("h2")!.textContent = topic.name;
      // Static text of this file, with the causes of stutter marked
      card.querySelector("p")!.innerHTML = topic.about;
      grid.append(card);
    }
    return element;
  },
};

/** The slides that are not ready yet: each carries a work-in-progress notice, and so does its topic's card. */
const WORK_IN_PROGRESS: ReadonlySet<Slide> = new Set([halfRate, switching, recovery, vrr, inputLatency, furtherReading]);

/** The notice before the slides that are not ready yet: continue anyway, or go to the measuring slide, which is. */
const notReady: Slide = {
  id: "not-ready",
  title: "Work in progress",
  render: () =>
    body(
      "Work in progress",
      "The rest is not ready yet",
      `The slides after this one, on half rate, switching rates, VRR, input latency and further reading, are drafts: their text,
      diagrams and videos are still changing, and some videos are missing. The slide on measuring animation error is ready.`,
      `<div class="menu-actions">
        <a class="button" href="#/half-rate">Continue anyway →</a>
        <a class="button ghost" href="#/measure">How to measure animation error →</a>
        <a class="button ghost" href="#/topics">Back to the topics</a>
      </div>`,
    ),
};

/** The frame pacing slides' videos: each diagram replayed exactly (the video tool's diagram modes), at the fast movement, right
 * under the slide's lead. The clips are listed in clips.json, for the export. */
const CLIPS: ReadonlyMap<Slide, () => HTMLElement> = new Map([
  [
    slowFramesSlide,
    () =>
      singleBox(
        "fast",
        "60",
        "60-diagram-slow-frames-every-1s",
        "bottom",
        "In the middle of every move two frames miss their refresh, as B and E in the diagram: the previous frame is held, the " +
          "late one shows a moment already past, and the next one jumps ahead. The chart shows each frame's animation error.",
        true,
      ),
  ],
  [
    halfRate,
    () =>
      liveComparison(
        "fast",
        "60-diagram-half-rate-even",
        "60-diagram-half-rate-bad-pacing",
        "Top: half rate, evenly paced, every frame held for two refreshes. Bottom: bad frame pacing, frames held for three and " +
          "one refreshes. Both are 30 fps on average; only the bottom one stutters.",
      ),
  ],
  [
    switching,
    () =>
      liveComparison(
        "fast",
        "60-diagram-switching-naive-every-1s",
        "60-diagram-switching-hysteresis-every-1s",
        "Top: back to full rate after the first fast frame. Bottom: with hysteresis, back up only after three fast frames in a " +
          "row. Each plays its diagram once, in the middle of every move.",
      ),
  ],
  [
    recovery,
    () =>
      liveComparison(
        "fast",
        "60-diagram-recovery-half-rate-every-1s",
        "60-diagram-recovery-targeting-every-1s",
        "Top: recovering at half rate. Bottom: at full rate with per-frame targets, back a frame sooner. Each plays its diagram " +
          "once, in the middle of every move.",
      ),
  ],
]);

/** A topic's slide with a line above its heading (the topic and where in it this slide is, linking back to the topics), its
 * video when it has one, and its work-in-progress notice when it is a draft. */
function withTopic(slide: Slide, topic: (typeof TOPICS)[number], position: number): Slide {
  return {
    ...slide,
    render() {
      const element = slide.render();
      const line = Object.assign(document.createElement("a"), {
        className: "topic-line",
        href: "#/topics",
        textContent: `‹ ${topic.name} · ${position + 1} of ${topic.slides.length}`,
      });
      const clip = CLIPS.get(slide);
      if (clip) element.querySelector(".lead")?.after(clip());
      if (WORK_IN_PROGRESS.has(slide)) {
        const notice = Object.assign(document.createElement("p"), { className: "wip", role: "note" });
        notice.innerHTML =
          "<strong>Work in progress.</strong> This slide is a draft: its text, diagrams and videos may still change.";
        element.prepend(notice);
      }
      element.prepend(line);
      return element;
    },
  };
}

/** The explanation slides, in order: the topics first, then every topic's slides, with the notice before the first one that is
 * not ready yet. */
const topicSlides = TOPICS.flatMap((topic) =>
  topic.slides.map((slide, position) => ({ slide, placed: withTopic(slide, topic, position) })),
);
const firstNotReady = topicSlides.findIndex(({ slide }) => WORK_IN_PROGRESS.has(slide));
export const EXPLANATION_SLIDES: readonly Slide[] = [
  topics,
  ...topicSlides.slice(0, firstNotReady).map(({ placed }) => placed),
  notReady,
  ...topicSlides.slice(firstNotReady).map(({ placed }) => placed),
];
