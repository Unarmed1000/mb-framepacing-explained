# The web page

A self-guided, slide-style page in [`web/`](../web) (TypeScript and Vite, no framework) that explains frame pacing with the videos
playing live, and starts with two blind tests. It is a draft, live at <https://unarmed1000.github.io/mb-framepacing-explained/>; the [roadmap](roadmap.md) tracks what is left.

## The slides

1. **Welcome**, then **best viewing**: the viewing check (once, on the best viewing slide) and a checklist to fix what it finds (below).
2. **Menu**: take the blind tests, then start the explanation ("How it works", from its first slide), or go straight to
   animation error and how to measure it ("Measure it", the mb-framepacing slide).
3. **Blind tests**: pick one of two, one for each cause of stutter; each card also opens that test's previous results kept in
   this browser (disabled when there are none), stepping between them with older and newer buttons. A result's questions can be
   watched again; one changed in a later test version plays today's version of its clip, and one that is gone lists its answer
   without the video. A test starts with a practice warm-up, an easy pair answered and revealed with its animation error chart,
   as often as wanted and not saved; the test itself then starts with a scored warm-up question. Every question asks "Which box
   has the smoother movement?", in random order after the warm-up, each pair at the normal and the fast movement and with each
   of its modes on top.
   - **Jitter**, 16 questions after the warm-up (a perfect 60 against a ±5 ms timer, the worst measured timer error, on every
     frame, at the fast movement): perfect 60 against a bad 60 and against a perfect 30, a perfect 30 against a bad 60, and 60
     and 30 each against itself. Marked as harder to spot than late frames.
   - **Late frames**, 14 questions after the warm-up (a perfect 60 against slow frames back to back, at the fast movement):
     perfect 60 against a 60 whose frames miss their refresh (the slow frames diagram, once a second), adapting the rate against
     staying at full rate through a busy stretch (fast only), and, with no right answer, that 60 against a perfect 30 and
     against a perfect 20 (three groups of slow frames in every move, around 30 %, 50 % and 70 % of it). The page asks to watch
     at least one whole move before answering.

   The questions, their categories and the clips they need are in [`trials.json`](../web/src/blind-test/trials.json). A result
   is scored per category (preferences are not scored), and each answer can be opened again to watch its pair with the
   reveal. The bad timers go wrong on nearly every frame, so a few seconds
   are enough; the page says that this is harsher than a typical game, and [why it is still fair](measured-errors.md#the-blind-test). The result is kept anonymised and versioned in the browser only, and can
   be downloaded or copied as JSON.

4. **What you saw, explained**: a topics page (stutter, its two causes and how it is measured; each topic a link to its first slide), then the two clocks, delta time jitter (live, with its chart following the video), why frame rate cannot see
   it, the vsync timer, slow frames, half rate, measuring it on a
   real display with [mb-framepacing](https://github.com/Unarmed1000/mb-framepacing), and two appendices: staying within the frame budget, and further reading. The diagrams are the
   ones in [`images`](images).

The blind tests come before the explanations, so they cannot give their answers away.

## Running it

From the repository root, with the `.venv` set up (`setup.cmd` or `./setup.sh`) and Node.js 24:

```sh
python tools/web_export/build_blind_test.py   # the clips, web-encoded, into web/public/videos (git-ignored)
cd web
npm install
npm run dev        # or: npm run build, then npm run preview
npm test           # vitest; npm run format:check for Prettier
```

`build_blind_test.py` generates exactly the clips `trials.json` asks for (the single box, never the rows, never two bad timers),
one folder per movement with its `manifest.json`. Regenerating replaces the clips of an open page: reload it afterwards.

The [pages workflow](../.github/workflows/pages.yml) does the same on every push to `master` and publishes `web/dist` on GitHub
Pages. It needs Pages enabled with **GitHub Actions** as the source (Settings > Pages).

## Videos only on the web page

The Markdown docs link to the videos' topics but do not embed them. GitHub's README renderer does not play looping video: a
`<video>` tag's `loop`, `autoplay` and `muted` attributes are stripped, and videos can only be attached as uploads of at most 10 MB
on a free plan, stored outside the repository
([GitHub: attaching files](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files),
[community request](https://github.com/dear-github/dear-github/issues/389)). An animated GIF is no substitute: its frame delays
come in 10 ms steps, so it cannot show 60 Hz frame pacing at all. The web page plays them with a normal looping `<video>` element.

## What the page checks

A page about frame pacing is only honest if the viewer's own display and browser do not add pacing errors or blur of their own.

- **60 Hz compatibility.** The clips are made at 60 fps. The page measures the display's refresh rate from the intervals between
  `requestAnimationFrame` callbacks and says so when it is not a whole multiple of 60 Hz, for example 144 Hz or a VRR display
  running at another rate: there every clip judders, the perfect one too, and a comparison or blind test would be meaningless.
- **Playback health.** During every clip, `requestVideoFrameCallback` reports each presented video frame; the page counts frames
  dropped, late or early against the 60 fps rhythm. It is the browser's own estimate, not a measurement of the screen, so the
  page words it that way.
- **Browser zoom and display scaling.** The clips must be shown at 1:1 device pixels (see the
  [tool's README](../tools/frame_pacing_video/README.md)): scaling blurs the sub-pixel steps they are meant to show. The page reads
  `window.devicePixelRatio` (browser zoom times the operating system's display scaling) and `visualViewport.scale` (pinch zoom),
  sizes each video at its pixel size divided by the ratio in CSS pixels, snaps it to whole device pixels, and shows the result
  under the video. It asks the viewer to reset the zoom when the video cannot be shown sharp.

The blind test's result records the conditions it was taken under: refresh rate and stability, device pixel ratio, fullscreen and
the browser family.

## Other notes

- **Web encoding.** The generator's default is lossless H.264 4:4:4, which browsers do not play; `--web` encodes H.264 High 4:2:0
  (near-lossless) in `.mp4` instead. The neutral grey palette was chosen to survive 4:2:0.
- **Size.** Git warns at 50 MiB per file, blocks files over 100 MiB and recommends repositories under 1 GB
  ([GitHub: large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)).
  The web clips are generated at build time, not committed.
- **Canvas instead of video** is worth trying later: drawing the boxes each refresh from the same timing data (`manifest.json`)
  avoids video decoding altogether and gives exact control of every refresh.
- **Charts next to the videos**, synced to playback: see [charts](charts.md).
- **Pausing every video.** Moving boxes next to the text distract some readers while they read. A switch in the top bar (and the
  P key) pauses or plays every video on the page, remembered in the browser; a paused video shows a button to play them again. A
  reader whose system asks for reduced motion starts paused. A video's own play button still plays that one while the rest stay
  paused.
