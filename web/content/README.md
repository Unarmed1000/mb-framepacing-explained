# The page's slides

The explanation slides of the page are Markdown: one file per slide in [`slides/`](slides), named after the slide's address
(`slides/slow-frames.md` is `#/slow-frames`). [`topics.json`](topics.json) lists the topics, their descriptions and which slides
each one has, in order (`"appendix": true` puts a topic after the appendix page, [`slides/appendix.md`](slides/appendix.md)); the slides set aside at the end are under `parked`. The page turns the Markdown into HTML when it is
built, so fixing a sentence is editing a Markdown file. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for how to send a change.

## A slide

```markdown
---
title: Slow frames
eyebrow: The second cause of stutter
draft: true
---

# When a frame misses its refresh

The first paragraph is the lead, in larger text.

The rest is Markdown: **bold**, _italic_, `code`, [links](https://example.com), lists and tables.
```

- `title` is the slide's short name, shown in the navigation; `eyebrow` is the small heading above the title.
- `draft: true` marks a slide that is not ready: it gets a work-in-progress notice.
- A link to another slide is its address: `[the vsync timer](#/vsync-timer)`. Links to other sites open in a new tab.
- A paragraph with only an image is a diagram: `![Its description.](../../../doc/images/timing-slow-frames.svg)`. The timing
  diagrams are made by [tools/timing_diagrams](../../tools/timing_diagrams).
- `## Heading` is a section title between the cards.

## Additions to Markdown

| Syntax                                         | What it gives                                                                                                                                                                         |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `:::card Heading` … `:::`                      | A card with that heading (leave it out for a card without one)                                                                                                                        |
| `:::fold Heading` … `:::`                      | A card that shows only its heading until it is clicked, then folds out                                                                                                                |
| `:::guide` … `:::`                             | The cards inside side by side                                                                                                                                                         |
| `:::figures` … `:::`                           | The diagrams inside side by side                                                                                                                                                      |
| `:::links Heading` … `:::`                     | A card of links, a list of `- [Title](https://…) what it is`                                                                                                                          |
| `:::video single MOTION TOP BOTTOM …` `:::`    | A live clip: one box of the clip with `TOP` above and `BOTTOM` below (`top` or `bottom`, `chart` for its animation error chart), the text inside as its caption                       |
| `:::video file NAME [HEIGHT] [controls]` `:::` | A rendered video (clips.json's `rendered`), the text inside as its caption; HEIGHT when it is not 384 pixels; `controls` playback controls                                            |
| `:::video pair MOTION TOP BOTTOM …` `:::`      | Both boxes of the clip, with their chart unless `nochart`; `frames` adds a display time step chart; `controls` playback controls; `nomodes` leaves the modes' names out of the charts |
| `::strip HZ FPS`                               | A refresh strip: `FPS` on an `HZ` display                                                                                                                                             |
| `A paragraph. {.note}`                         | A note, in smaller text                                                                                                                                                               |
| `[A](…) [B](…) {.more}`                        | A row of links to read more                                                                                                                                                           |

Put a blank line before and after each `:::` line. A clip's modes are the video tool's (`60`, `60-naive-5ms`,
`60-diagram-slow-frames-every-1s`, …, see [tools/frame_pacing_video](../../tools/frame_pacing_video)); every clip a slide uses
must be listed in [`src/explain/clips.json`](../src/explain/clips.json), which a test checks.

## Seeing it

In `web/`: `npm ci` once, then `npm run dev` serves the page with every change as you save it. The text and diagrams show right
away; where a clip has not been generated, the slide says so. To generate the clips, run
`python tools/web_export/build_blind_test.py` from the repository root in its `.venv`, with FFmpeg (see the
[README](../../README.md#what-is-in-this-repository) for the setup).
