# Contributing

Corrections, missing details and new topics are very welcome, especially from people who work on game engines, graphics drivers,
displays, operating systems or measurement tools. The page and the docs are only as good as their sources, so the most useful
contribution is a correction with a link to where it can be checked.

## What helps most

- **Corrections:** a claim that is wrong, outdated or missing a condition, with a source that shows it.
- **Platform and API details:** how a platform, API or engine really behaves (swap intervals, scheduled presents, vsync
  signals, VRR), ideally from its official documentation or source code.
- **Measurements:** animation error or frame pacing measured in real games and apps, with how it was measured.
- **Missing topics:** something the page should explain, or explains in the wrong order.
- **Clearer wording:** anything that is hard to follow.

## How

- **An issue** is enough for most of the above: no code needed. Describe what is wrong or missing, and link the source.
  [Open an issue](https://github.com/Unarmed1000/mb-framepacing-explained/issues).
- **A pull request** for a change you want to make yourself. The slides are Markdown files, so a wording fix can be made in
  GitHub's own editor, without cloning anything. For anything larger than a fix, open an issue first, so we can agree
  on the direction before you spend the time.

## Sources

- Every claim links to where it can be checked. Prefer primary sources: official documentation, specifications, source code,
  papers, and the talk or video itself (with a timestamp) over articles about it.
- Quotes are exact, and say where they come from. A paraphrase is not put in quotation marks.
- Say where a statement goes beyond its sources, for example a suggestion of our own or a conclusion drawn from how something
  works.
- Sponsored or vendor material is fine, but say so.

## Where things are

| What                                | Where                                                                                  |
| ----------------------------------- | -------------------------------------------------------------------------------------- |
| The page's explanation slides       | [`web/content`](web/content): a Markdown file per slide ([how](web/content/README.md)) |
| The docs                            | [`doc/`](doc) and the [README](README.md)                                              |
| The timing diagrams and charts      | [`tools/timing_diagrams`](tools/timing_diagrams)                                       |
| The videos and the simulated timers | [`tools/frame_pacing_video`](tools/frame_pacing_video)                                 |
| The clips the page uses             | [`tools/web_export`](tools/web_export)                                                 |

## Checks

The [pages workflow](.github/workflows/pages.yml) runs these on every push to master; please run them before a pull request:

- Python tools: `setup.cmd` (Windows) or `./setup.sh` once, then `python -m unittest discover -s tools/frame_pacing_video` and
  `-s tools/web_export`, `ruff check tools`, `ruff format --check tools` and `basedpyright tools`, in the `.venv`.
- The page, in `web/`: `npm ci`, then `npm run format:check`, `npm test` and `npm run build`. `npm run dev` serves it locally.
- Markdown and JSON are formatted with Prettier (`npx prettier --write` on the files you changed).

## License

The repository is licensed under [CC BY-NC-SA 4.0](LICENSE) by Mana Battery ApS. By submitting a contribution (an issue's text, a
pull request or any other material), you confirm that you have the right to submit it, and you agree that it is published under
the repository's license and that Mana Battery ApS may use, change and publish it as part of this project. Contributors are
credited in the Git history.
