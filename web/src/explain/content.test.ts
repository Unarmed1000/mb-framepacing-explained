import { describe, expect, it } from "vitest";
import { expandDirectives, frontMatter, slideModule } from "../../build/slide-markdown";
import topicData from "../../content/topics.json";
import clips from "./clips.json";

// The slides' Markdown as text (?raw: not through the slide plugin)
const SOURCES = import.meta.glob<string>("../../content/slides/*.md", { query: "?raw", import: "default", eager: true });
const FILES = new Map(Object.entries(SOURCES).map(([path, source]) => [path.replace(/^.*\/|\.md$/g, ""), source]));
/** The slides that are not in a topic: the topics page, the notice before the drafts, the page before the set-aside ones. */
const PAGES = ["topics", "not-ready", "parked"];

describe("the slides' content", () => {
  it("has a file for every slide of the topics, and every file is shown", () => {
    const listed = [...topicData.topics.flatMap((topic) => topic.slides), ...topicData.parked.slides, ...PAGES];
    expect(new Set(listed).size).toBe(listed.length);
    expect([...FILES.keys()].sort()).toEqual([...listed].sort());
  });

  it("turns every file into a slide", () => {
    for (const [id, source] of FILES) {
      expect(() => slideModule(source), id).not.toThrow();
      expect(frontMatter(source).body, id).toMatch(/^\s*# /);
    }
  });

  it("asks only for clips the export makes", () => {
    const made = new Set(clips.pairs.map(([top, bottom]) => `${clips.motion} ${top ?? ""} ${bottom ?? ""}`));
    const rendered = new Set(clips.rendered.map((video) => video.name));
    for (const [id, source] of FILES) {
      for (const [, name] of source.matchAll(/^:::video file (\S+)/gm)) expect(rendered, `${id}: ${name}`).toContain(name);
    }
    for (const [id, source] of FILES) {
      for (const [, motion, top, bottom] of source.matchAll(/^:::video (?:single|pair) (\S+) (\S+) (\S+)/gm)) {
        expect(made, `${id}: ${motion} ${top} ${bottom}`).toContain(`${motion} ${top} ${bottom}`);
      }
    }
  });
});

describe("the slide Markdown", () => {
  const html = (body: string): string => {
    const code = slideModule(`---\ntitle: T\neyebrow: E\n---\n\n${body}`);
    return JSON.parse(/export const html = (".*");/.exec(code)?.[1] ?? '""') as string;
  };

  it("has the eyebrow, the title and the lead", () => {
    expect(html("# Title\n\nFirst.\n\nSecond.")).toBe(
      '<p class="eyebrow">E</p>\n<h1>Title</h1>\n<p class="lead">First.</p>\n<p>Second.</p>\n',
    );
  });

  it("marks notes, rows of links, diagrams, lists and tables", () => {
    expect(html("A note. {.note}")).toBe('<p class="eyebrow">E</p>\n<p class="note">A note.</p>\n');
    expect(html("[A](https://a.example) [B](#/b) {.more}")).toContain(
      '<p class="more"><a href="https://a.example" target="_blank" rel="noopener">A ↗</a> <a href="#/b">B ↗</a></p>',
    );
    expect(html("![A diagram.](https://a.example/d.svg)")).toContain(
      '<figure class="diagram"><img src="https://a.example/d.svg" alt="A diagram." loading="lazy" /></figure>',
    );
    expect(html("- one\n- two")).toContain('<ul class="points">');
    expect(html("| a |\n| - |\n| b |")).toContain('<table class="ways">');
  });

  it("imports local images, so the build copies them", () => {
    const code = slideModule("---\ntitle: T\neyebrow: E\n---\n\n![D.](../d.svg)");
    expect(code).toContain('import image0 from "../d.svg?url";');
    expect(code).toContain("+ image0 +");
  });

  it("expands blocks, and refuses unknown or unclosed ones", () => {
    expect(expandDirectives(":::card Heading\n\ntext\n\n:::")).toContain('<div class="card"><h2>Heading</h2>');
    expect(expandDirectives("::strip 120 40")).toContain('<div data-live="strip" data-args="120 40"></div>');
    expect(() => expandDirectives(":::box")).toThrow(/no block named/);
    expect(() => expandDirectives(":::card")).toThrow(/not closed/);
    expect(() => expandDirectives(":::")).toThrow(/closes no block/);
  });
});
