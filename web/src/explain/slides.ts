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

/** An API name in code style, linked to its documentation. */
const api = (href: string, name: string): string => `<a href="${href}" target="_blank" rel="noopener"><code>${name}</code></a>`;

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

const missedFrames: Slide = {
  id: "missed-frames",
  title: "Missed frames",
  render: () =>
    body(
      "Missed frames",
      "Rule one: do not miss the frame target",
      `A game that never misses its frame target has no pacing problem to solve. In reality it will miss now and then. Some misses
      are its own, a shader compile or a streaming spike. Others are outside its control: the host operating system, a driver or
      another program taking the CPU or GPU for a moment. No amount of optimising removes those, so every game needs a strategy
      for the missed frame, chosen in advance: it cannot be shown on time any more, only at a later refresh. There is no easy fix:
      every choice costs something, and which cost is acceptable depends on the game, the platform and the player, and on what the
      app's own animation error shows.`,
      `<div class="card">
        <h2>First, do not miss</h2>
        <ul class="points">
          <li><strong>Pick a target every frame can hold, with room to spare.</strong> If 60 fps does not fit, a steady 30 fps on
            60 Hz or 40 fps on 120 Hz may, <a href="#/half-rate">paced right</a>.</li>
          <li><strong>Keep the frame cost steady:</strong> dynamic resolution lowers the render resolution under load, at some
            cost to image quality.</li>
          <li><strong>Remove the spikes the game causes itself:</strong> compile shaders ahead of time, stream assets in before
            they are needed.</li>
        </ul>
      </div>
      <div class="guide">
        <div class="card">
          <h2>When it happens anyway</h2>
          <ul class="points">
            <li><strong>Take the hitch:</strong> stay at full rate and show the late frame a refresh late. Costs a visible jump
              every time.</li>
            <li><strong>Queue frames ahead:</strong> a frame that is ready in advance covers for a slow one, as long as the frames
              fit on average. Costs input latency on every frame.</li>
            <li><strong>Switch rates:</strong> drop to half rate through a busy stretch. Costs smoothness while there, and
              deciding when to go back up.</li>
            <li><strong>Let the display wait:</strong> <a href="#/vrr">VRR</a> shows the frame when it is ready, vsync off shows it
              at once. Needs a VRR display, or tears.</li>
          </ul>
        </div>
        <div class="card">
          <h2>What the choice depends on</h2>
          <ul class="points">
            <li><strong>What the app actually does:</strong> <a href="#/measure">measure its animation error</a> before choosing.
              It shows how often and by how much frames miss, whether as rare spikes or whole busy stretches, in which scenes,
              and whether the cause is pacing or delta time jitter.</li>
            <li><strong>How much latency matters:</strong> a fast game played with a mouse or gamepad, or a menu, a map, a
              video.</li>
            <li><strong>The display:</strong> fixed refresh or VRR and its range, 60 Hz or 120 Hz.</li>
            <li><strong>The platform:</strong> only plain vsync, or also a swap interval, scheduled presents and feedback on when
              frames appeared.</li>
            <li><strong>The player:</strong> some prefer a steady 30 fps, others a higher but uneven rate, which is why many games
              offer a quality and a performance mode.</li>
          </ul>
        </div>
      </div>
      <p class="note">Whichever way a game goes, the animation time has to be right first (the
        <a href="#/vsync-timer">vsync timer</a>): otherwise even the frames that do arrive on time show the wrong moment. The
        next slides go through the strategies one at a time, to pick the one that fits the application.</p>`,
    ),
};

const lowerTarget: Slide = {
  id: "lower-target",
  title: "A lower target",
  render: () =>
    body(
      "Strategy 1",
      "Run at a lower target frame rate",
      `For when optimizing cannot get the app to hold the higher target, and frames would miss it often rather than in a rare
      spike. The first strategy then avoids the miss instead of handling it: run at a frame rate every frame can hold with room
      to spare, and hold it. If 60 fps on a 60 Hz display does not fit, 30 fps gives every frame twice the time. A 120 Hz display has steps
      in between: 60 and 40 fps. Below, the price: the same motion at 60 and at 30 fps, both perfectly paced.`,
      `<div class="guide">
        <div class="card">
          <h2>When it fits</h2>
          <ul class="points">
            <li><strong>Optimizing is not enough:</strong> the app cannot hold the higher rate, and the misses would be frequent.
              A rare spike is better handled by one of the other strategies than paid for on every frame.</li>
            <li><strong>The app and its audience accept it:</strong> a 30 fps mode is familiar on consoles, but PC players are
              rarely happy with less than 60 fps, and many expect more.</li>
            <li><strong>The frames fit the lower rate with room to spare,</strong> spikes included, measured on the real
              content.</li>
            <li><strong>Steady matters more than fast:</strong> slower motion, and input that does not need every frame of
              latency back.</li>
            <li><strong>The platform can hold a frame</strong> for a whole number of refreshes, and for 40 fps the display runs at
              120 Hz.</li>
          </ul>
        </div>
        <div class="card">
          <h2>What it costs</h2>
          <ul class="points">
            <li><strong>Smoothness:</strong> at 30 fps every step of the motion is twice as far.</li>
            <li><strong>Input latency:</strong> each frame takes longer, and waits longer to be shown.</li>
            <li><strong>Unused headroom:</strong> most frames could have run faster.</li>
            <li><strong>A frame over even the lower budget still misses,</strong> and then one of the other strategies has to
              handle it.</li>
          </ul>
        </div>
      </div>
      <div class="card">
        <h2>What players choose</h2>
        <p class="note">Players notice the cost. Presenting the PS5 Pro in September 2024, Sony's Mark Cerny said that when asked
          to decide on a mode, PS5 players choose performance over fidelity about three quarters of the time
          (<a href="https://www.youtube.com/watch?v=X24BzyzQQ-8&amp;t=172s" target="_blank" rel="noopener">PS5 Pro Technical
            Presentation, 2:52</a>). A performance mode is usually 60 fps and a fidelity mode 30 fps, though not in every game,
          and Sony has not published the data behind the figure.</p>
      </div>
      <p class="note">And it has to be paced right: the next slides show how.</p>`,
    ),
};

const halfRate: Slide = {
  id: "half-rate",
  title: "Pacing 30 fps",
  render: () =>
    body(
      "Half rate",
      "How to pace 30 fps",
      `At 30 fps on a 60 Hz display every frame should stay on screen for exactly two refreshes, and the animation step 33.3 ms
      each time. Rendering in time is not enough: the display shows a frame at the first vsync after it is presented, so something
      has to hold it back until its second refresh. A game that caps its frame rate with its own clock instead gets frames held
      for three refreshes and then one. Digital Foundry keep finding 30 fps caps like that. Bloodborne had it together with real
      performance drops, and a fan patch that only changes how often frames are flipped fixes its pacing.`,
      `<div class="figures">
        ${figure(halfRateEven, "Evenly paced: each frame held for two refreshes, as intended.")}
        ${figure(halfRateBad, "Bad frame pacing: frames held for 3 and 1 refreshes instead of 2, although every frame renders in time.")}
      </div>
      <div class="card">
        <h2>Three ways to hold a frame for two refreshes</h2>
        <ul class="points">
          <li><strong>Swap interval:</strong> every frame held for a whole number of refreshes, counted from the previous
            flip, where the platform has one (below).</li>
          <li><strong>Scheduled present:</strong> the frame says when it should appear, where the platform has an API for it
            (below).</li>
          <li><strong>Sleep, then present:</strong> works anywhere, but the thread wakes up a little late, differently every time.
            Unity: "Always use vSyncCount &gt; 0 when smooth frame pacing is needed".</li>
        </ul>
        <p class="note">Whichever holds the frames, step the animation by two refreshes, counted as the
          <a href="#/vsync-timer">vsync timer</a> does, so each frame shows the moment it is on screen.</p>
      </div>
      <div class="card">
        <h2>Swap intervals per platform</h2>
        <table class="ways">
          <thead>
            <tr><th>Platform</th><th>API</th><th>What it does</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Windows, DXGI</td>
              <td>${api("https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgiswapchain-present", "Present(SyncInterval)")}</td>
              <td>1 to 4: the frame stays "for at least <em>n</em> vertical blanks" (flip model). Given with every present, so it
                can change per frame</td>
            </tr>
            <tr>
              <td>OpenGL, Windows</td>
              <td>${api("https://registry.khronos.org/OpenGL/extensions/EXT/WGL_EXT_swap_control.txt", "wglSwapIntervalEXT")}</td>
              <td>"the minimum number of video frames that are displayed before a buffer swap"</td>
            </tr>
            <tr>
              <td>OpenGL, Linux X11</td>
              <td>${api("https://registry.khronos.org/OpenGL/extensions/EXT/EXT_swap_control.txt", "glXSwapIntervalEXT")}</td>
              <td>The same: "a value of two means that the color buffers will be swapped at most every other video frame"</td>
            </tr>
            <tr>
              <td>EGL, Android</td>
              <td>${api("https://registry.khronos.org/EGL/sdk/docs/man/html/eglSwapInterval.xhtml", "eglSwapInterval")}</td>
              <td>The same, clamped to the implementation's <code>EGL_MAX_SWAP_INTERVAL</code></td>
            </tr>
            <tr>
              <td>Android, Swappy</td>
              <td>${api("https://developer.android.com/games/sdk/reference/frame-pacing/group/swappy-g-l", "SwappyGL_setSwapIntervalNS")}</td>
              <td>A minimum interval in nanoseconds (<code>SWAPPY_SWAP_30FPS</code>); in its auto mode Swappy may still go
                slower</td>
            </tr>
            <tr>
              <td>Vulkan</td>
              <td>None in core</td>
              <td>FIFO "is equivalent to … a swap interval of 1": hold a frame longer by presenting it twice, or with a scheduled
                present</td>
            </tr>
            <tr>
              <td>Wayland</td>
              <td>${api("https://wayland.app/protocols/fifo-v1", "wp_fifo_v1")}</td>
              <td>An interval of 1 only: an update stays "for at least one refresh cycle"</td>
            </tr>
            <tr>
              <td>Apple</td>
              <td>None</td>
              <td>A display link's
                ${api("https://developer.apple.com/documentation/quartzcore/cadisplaylink/preferredframeraterange", "preferredFrameRateRange")}
                sets how often the app is asked for a frame; to hold one, schedule its present</td>
            </tr>
            <tr>
              <td>Engines</td>
              <td>${api("https://docs.unity3d.com/ScriptReference/QualitySettings-vSyncCount.html", "vSyncCount")} (Unity),
                <code>rhi.SyncInterval</code> (Unreal)</td>
              <td>Unity: 0 to 4, the refresh rate divided by <code>vSyncCount</code>; Unreal's frame pacer sets
                <code>rhi.SyncInterval</code> from the display's refresh rate</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <h2>Scheduled presents per platform</h2>
        <table class="ways">
          <thead>
            <tr><th>Platform</th><th>API</th><th>The frame gives</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Vulkan</td>
              <td>${api("https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_present_timing.html", "VK_EXT_present_timing")}</td>
              <td>A target time, absolute or relative to the previous frame</td>
            </tr>
            <tr>
              <td>Vulkan, older</td>
              <td>${api("https://docs.vulkan.org/refpages/latest/refpages/source/VK_GOOGLE_display_timing.html", "VK_GOOGLE_display_timing")}</td>
              <td>A desired present time (not ratified)</td>
            </tr>
            <tr>
              <td>Android</td>
              <td>${api("https://registry.khronos.org/EGL/extensions/ANDROID/EGL_ANDROID_presentation_time.txt", "eglPresentationTimeANDROID")},
                ${api("https://developer.android.com/ndk/reference/group/native-activity#asurfacetransaction_setdesiredpresenttime", "ASurfaceTransaction_setDesiredPresentTime")}</td>
              <td>A desired presentation time, per frame or per surface transaction</td>
            </tr>
            <tr>
              <td>Apple, Metal</td>
              <td>${api("https://developer.apple.com/documentation/metal/mtldrawable/present(at:)", "present(at:)")},
                ${api("https://developer.apple.com/documentation/metal/mtldrawable/present(afterminimumduration:)", "present(afterMinimumDuration:)")}</td>
              <td>A host time, or how long the previous frame stays on screen at least</td>
            </tr>
            <tr>
              <td>Windows</td>
              <td>${api("https://learn.microsoft.com/en-us/windows/win32/api/presentation/nf-presentation-ipresentationmanager-settargettime", "IPresentationManager::SetTargetTime")}</td>
              <td>A target time for the next present (composition swapchain, Windows 11)</td>
            </tr>
            <tr>
              <td>Linux, X11</td>
              <td>${api("https://registry.khronos.org/OpenGL/extensions/OML/GLX_OML_sync_control.txt", "glXSwapBuffersMscOML")}</td>
              <td>A target vblank count, not a time</td>
            </tr>
            <tr>
              <td>Linux, Wayland</td>
              <td>${api("https://wayland.app/protocols/commit-timing-v1", "wp_commit_timing_v1")}</td>
              <td>A time the update is shown "as closely as possible to, but not before" (staging; KWin, Mutter, Sway, Weston,
                gamescope and others)</td>
            </tr>
          </tbody>
        </table>
        <p class="note">Plain DXGI and core Vulkan have none: there a swap interval, or presenting each frame twice, holds a
          frame.</p>
      </div>
      ${more(doc("doc/frame-pacing-strategies.md#holding-a-frame-for-more-than-one-refresh"), "Holding a frame for more than one refresh")}`,
    ),
};

/** A refresh strip of the first 1/6 s of `fps` on a `hz` display, one cell per refresh, the shade changing with each new frame
 * (after the average chart's strips), and how many refreshes each frame is held. A frame is shown at the first refresh at or after
 * the moment it is due, as with plain vsync; the rows share one time scale, so the strips line up (a refresh rate that 1/6 s does
 * not divide, like 500 Hz, ends in a part of a cell). */
function refreshStrip(hz: number, fps: number): string {
  const refreshes = hz / 6;
  const flips: number[] = [];
  // Integers throughout: k x hz / fps is exact whenever it is whole
  for (let frame = 0; Math.ceil((frame * hz) / fps) < refreshes; frame++) flips.push(Math.ceil((frame * hz) / fps));
  const cells: string[] = [];
  let shade = 0;
  for (let refresh = 0; refresh < refreshes; refresh++) {
    if (refresh > 0 && flips.includes(refresh)) shade ^= 1;
    const part = refreshes - refresh < 1 ? ` style="flex: ${(refreshes - refresh).toFixed(3)}"` : "";
    cells.push(`<span${shade ? ' class="b"' : ""}${part}></span>`);
  }
  const holds = flips.slice(1).map((flip, index) => flip - (flips[index] ?? 0));
  const even = holds.every((hold) => hold === holds[0]);
  const shown = even
    ? `every frame ${holds[0]} refreshes, ${((1000 * (holds[0] ?? 0)) / hz).toFixed(1).replace(/\.0$/, "")} ms`
    : `${holds.slice(0, 5).join(", ")} … refreshes: uneven`;
  return `<div class="strip-row">
      <div class="strip-label"><strong>${fps} fps on ${hz} Hz</strong><span>${shown}</span></div>
      <div class="refresh-strip">${cells.join("")}</div>
    </div>`;
}

const otherRates: Slide = {
  id: "other-rates",
  title: "Other rates",
  render: () =>
    body(
      "Other rates",
      "Any rate that divides the refresh rate",
      `Half rate is one case of a general rule: a frame rate can be paced evenly when it divides the display's refresh rate, so
      every frame is held for the same whole number of refreshes, the same way as at 30 fps. On a 120 Hz display that gives 60,
      40 and 30 fps. Digital Foundry on
      <a href="https://www.youtube.com/watch?v=QXi7uO7wxdc" target="_blank" rel="noopener">Ratchet &amp; Clank's 40 fps mode</a>:
      "the same consistency but smoother" than 30 fps on 60 Hz. A rate that does not divide, like 60 fps on 144 Hz or 40 fps on
      60 Hz, cannot be even however well it is paced: its frames alternate between two hold lengths.`,
      `<div class="card">
        <h2>Even: the rate divides the refresh rate</h2>
        ${refreshStrip(60, 30)}
        ${refreshStrip(120, 60)}
        ${refreshStrip(120, 40)}
        ${refreshStrip(120, 30)}
        ${refreshStrip(144, 72)}
        ${refreshStrip(144, 48)}
        ${refreshStrip(240, 120)}
        ${refreshStrip(240, 60)}
        ${refreshStrip(500, 250)}
        ${refreshStrip(500, 100)}
      </div>
      <div class="card">
        <h2>Uneven: it does not</h2>
        ${refreshStrip(144, 60)}
        ${refreshStrip(60, 40)}
        ${refreshStrip(500, 60)}
      </div>
      <p class="note">Every strip is the same 1/6 s: one cell per refresh, the shade changing with each new frame. A 40 fps mode
        needs a display running at 120 Hz: on 60 Hz the same game is uneven. With VRR a steady rate inside the display's range is
        even without dividing anything, as long as the frame times stay steady.</p>
      ${more(doc("doc/display-sync.md#fixed-or-adaptive-frame-rate"), "Fixed or adaptive frame rate")}`,
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

const averageFrameRate: Slide = {
  id: "average-frame-rate",
  title: "Average frame rate",
  render: () =>
    body(
      "Why the usual numbers miss it",
      "The average frame rate hides stutter",
      `An average frame rate counts frames, not when they reach the screen. Both rows below are 30 fps on a 60 Hz display, 30
      frames every second, and every frame renders in time: the top one holds each frame for two refreshes, the bottom one for
      three and then one, and only the top one is smooth. The average cannot tell them apart.`,
      `${figure(averageHalfRate, "Same 30 fps on average, different motion: 60 Hz, two refreshes every time, or three and then one.")}
      <div class="card">
        <h2>What each number sees</h2>
        <table class="ways">
          <thead>
            <tr><th>Number</th><th>Bad frame pacing</th><th><a href="#/invisible">Delta time jitter</a></th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Average frame rate</strong></td>
              <td>30 fps, the same as evenly paced</td>
              <td>60 fps, the same as a perfect timer</td>
            </tr>
            <tr>
              <td><strong>Display time per frame</strong></td>
              <td>Uneven: 50 and 16.7 ms instead of 33.3 ms</td>
              <td>Even: 16.7 ms, the same as a perfect timer</td>
            </tr>
            <tr>
              <td><strong>Animation error</strong></td>
              <td>±16.7 ms</td>
              <td>Up to ±5 ms in the videos</td>
            </tr>
          </tbody>
        </table>
        <p class="note">A graph of display times catches bad pacing, but only animation error catches both causes of stutter,
          because only it looks at the moment each frame shows.</p>
      </div>`,
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
      `<h2 class="section-title">Ways to measure it</h2>
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
      "The second cause of stutter, <strong>bad frame pacing</strong>: frames that reach the screen late or unevenly, why missed frames have no easy fix, and the strategies for them, starting with a lower target frame rate.",
    slides: [slowFramesSlide, missedFrames, lowerTarget, halfRate, otherRates],
  },
  {
    name: "Beyond vsync: VRR and input latency",
    about: "What VRR changes, and how pacing meets input latency.",
    slides: [vrr, inputLatency],
  },
  {
    name: "Go further",
    about: "Why the average frame rate hides stutter, how to measure animation error, and where to read more.",
    slides: [averageFrameRate, measure, furtherReading],
  },
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
const WORK_IN_PROGRESS: ReadonlySet<Slide> = new Set([switching, recovery, vrr, inputLatency, furtherReading]);

/** The notice before the slides that are not ready yet: continue anyway, or go to the measuring slide, which is. */
const notReady: Slide = {
  id: "not-ready",
  title: "Work in progress",
  render: () =>
    body(
      "Work in progress",
      "The rest is not ready yet",
      `The slides after this one, on VRR, input latency and further reading, are drafts: their text, diagrams and
      videos are still changing, and some videos are missing. The slides on measuring animation error are ready.`,
      `<div class="menu-actions">
        <a class="button" href="#/${topicSlides[firstNotReady]?.slide.id ?? "topics"}">Continue anyway →</a>
        <a class="button ghost" href="#/average-frame-rate">Measuring animation error →</a>
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
    lowerTarget,
    () =>
      liveComparison(
        "fast",
        "60",
        "30",
        "Top: 60 fps. Bottom: 30 fps. Both perfectly paced, every frame showing the moment it is on screen: the bottom one only " +
          "moves in steps twice as far.",
        false,
      ),
  ],
  [
    averageFrameRate,
    () =>
      liveComparison(
        "fast",
        "60-diagram-half-rate-even",
        "60-diagram-half-rate-bad-pacing",
        "Both boxes at 30 fps, 30 frames every second. Top: every frame held for two refreshes. Bottom: for three and then one.",
        false,
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

/** Slides set aside to be reworked later: after every topic, not on the topics page. */
const PARKED: (typeof TOPICS)[number] = {
  name: "Stuff we might use",
  about: "Set aside to be reworked later.",
  slides: [switching, recovery],
};

const parked: Slide = {
  id: "parked",
  title: "Stuff we might use",
  render: () =>
    body(
      "Set aside",
      "Stuff we might use",
      `The explanation ends before this slide. The slides after it are set aside, to be merged or rewritten later: when a game
      that dropped to half rate should go back to full rate, in a busy stretch and after a single slow frame.`,
      `<div class="menu-actions">
        <a class="button" href="#/switching">Show them anyway →</a>
        <a class="button ghost" href="#/topics">Back to the topics</a>
      </div>`,
    ),
};

/** The explanation slides, in order: the topics first, then every topic's slides, with the notice before the first one that is
 * not ready yet, and the set-aside slides last. */
const topicSlides = TOPICS.flatMap((topic) =>
  topic.slides.map((slide, position) => ({ slide, placed: withTopic(slide, topic, position) })),
);
const firstNotReady = topicSlides.findIndex(({ slide }) => WORK_IN_PROGRESS.has(slide));
export const EXPLANATION_SLIDES: readonly Slide[] = [
  topics,
  ...topicSlides.slice(0, firstNotReady).map(({ placed }) => placed),
  notReady,
  ...topicSlides.slice(firstNotReady).map(({ placed }) => placed),
  parked,
  ...PARKED.slides.map((slide, position) => withTopic(slide, PARKED, position)),
];
