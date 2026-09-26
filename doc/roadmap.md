# Roadmap

Future ideas and next steps, so nothing lives only in a conversation. Tick an item off (`[x]`) when it is done, and add new ideas
here as they come up.

## The web page

A self-guided, slide-style page that starts with a blind test built from the generated videos, then takes the visitor through
the topics interactively. Notes: [the web page](web-page.md).

- [x] Phase 1, vertical slice: the page shell (navigation, one slide, the card look), the viewing check card and the best
      viewing guide, and the warm-up trial with its reveal chart. Stop for review of the look and feel.
- [ ] Phase 2 (built, in review): the full blind test (warm-up first, then 23 questions in random order: each pair in each of
      its movements and with each mode on top; categories, score, saved anonymised and versioned result with export). The results list has one row per trial with its verdict ("Correct", "There was a difference", …);
      clicking a row folds it out to show that trial's video again, which box was which, and its animation error chart.
- [ ] Phase 3 (built, in review): the explanation slides after the blind test, including "measure it yourself" with
      mb-framepacing. Review the wording.
- [x] Phase 4: the GitHub Pages workflow (generate and web-encode the clips, build, deploy), live at
      <https://unarmed1000.github.io/mb-framepacing-explained/>.
- [ ] Remove the "Unfinished work in progress" notice from the first slide (`.wip` in `web/src/main.ts` and `styles.css`) when the page is ready.
- [x] Video tool: a `--web` encoding (H.264 4:2:0) and generating an exact list of pairs (`--pairs`).
- [ ] Later: central collection of the anonymised results (opt-in submit), a shareable result link, a canvas renderer for extra
      conditions.
- [ ] Later: classify each clip's animation sequence from its animation error: how much of it has stutter, and the other
      categories (jitter, hitches, ...), which can overlap; show it as shares of the sequence and as marked stretches on the chart.

## Videos

- [ ] A vsync timer mode: the naive wall-clock reading rounded to whole refreshes, next to the naive timer, plus a wake-up late
      by more than half a refresh (where it fails).
- [x] Late and held frames as the timing diagrams show them: `RATE-diagram-NAME` replays a diagram's frames exactly.
- [ ] Not simulated yet: random late frames and long hitches, dropped and runt frames, tearing, VRR, input lag.
- [ ] VRR on video: frames between refreshes need a finer video (about 240 fps) and a display that shows it.
- [ ] 40 fps on 120 Hz.
- [x] A slow box speed (the normal timing on a quarter of the path), better suited to 20 Hz (`--speed slow`). The blind test
      dropped its 20 fps questions, so it is unused there for now.

## Diagrams

Sample first each time.

- [x] The vsync timer rounding (`timing-vsync-timer.svg`, on the strategies page and the web page's vsync timer slide).
- [ ] The vsync timer's failure: a wake-up late by more than half a refresh.
- [ ] Finish the web page's draft slides (frame pacing, VRR, input latency, further reading), then remove their work-in-progress
      notices and the notice slide before them.
- [ ] Drift as a chart: the nominal rate, paying the error back in whole refreshes (a sawtooth), slewing.
- [ ] Presenting each frame twice on FIFO for half rate.
- [ ] A refresh rate change mid-run (144 to 60 Hz).
- [ ] 60 fps on a 144 Hz display (2- and 3-refresh judder), for the web page's 60 Hz check.

## Docs and research

- [ ] VRR and vsync off: the right approach is still open ([strategies](frame-pacing-strategies.md#still-open-vrr-and-vsync-off)).
- [ ] Drift table: audio time stamps on Linux (PipeWire, ALSA) and Apple (Core Audio), verified.
- [ ] Name the platforms where `wl_surface.frame` misbehaves.
- [ ] Test whether DWM's `qpcRefreshPeriod` is measured or only nominal.
- [ ] Check the Glaiel vsync snapping wording against the article (Medium blocked the automated fetch).
- [ ] [Measured in real games](measured-errors.md): check Digital Foundry's Elden Ring stutter figure (250 ms) and Croteam's
      Talos numbers on the original pages (only second-hand and a mirror so far); find per-game animation error from Digital
      Foundry's PresentMon runs and CapFrameX.
- [ ] Appendix A candidates: Linux KMS/DRM page-flip events and `drmWaitVBlank`; plain EGL, where a blocking `eglSwapBuffers`
      is the only signal.

## mb-framepacing

Ideas for the sister project, from [charts](charts.md#ideas-for-mb-framepacing).

- [ ] Synced playback: a click on a chart spike opens that captured frame, and a playhead follows the recording.
- [ ] Gamers Nexus's summaries by their names: error per frame, percent error.
- [ ] A refresh strip (FCAT-style), a stutter share (CapFrameX-style), SVG export of its charts.
- [ ] The same classification as the web page's, on measured captures: from the animation error, how much of a run has stutter and
      the other categories (jitter, hitches, ...), which can overlap; as shares in the report and marked stretches on its charts.
      Build it once and share the rules, so both projects label a sequence the same way.
