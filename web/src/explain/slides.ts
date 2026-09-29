// SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// The explanation slides, after the blind test. Their text lives in web/content: a Markdown file per slide in content/slides,
// turned into HTML when the page is built (build/slide-markdown.ts), and the topics in content/topics.json. This file puts the
// slides in order, adds each one's topic line and draft notice, and fills in the live parts: the videos, the refresh strips and
// the topics page's cards.

import topicData from "../../content/topics.json";
import type { SlideMeta } from "../../build/slide-markdown";
import type { Slide } from "../slides";
import { liveComparison, renderedClip, singleBox } from "./live";
import { refreshStrip } from "./strips";

interface Topic {
  name: string;
  about: string;
  slides: readonly string[];
  /** After the explanation, behind the appendix page. */
  appendix?: boolean;
}

const FILES = import.meta.glob<{ meta: SlideMeta; html: string }>("../../content/slides/*.md", { eager: true });
/** Every slide's content by id, the file's name. */
const CONTENT = new Map(Object.entries(FILES).map(([path, content]) => [path.replace(/^.*\/|\.md$/g, ""), content]));

function content(id: string): { meta: SlideMeta; html: string } {
  const found = CONTENT.get(id);
  if (!found) throw new Error(`no slide web/content/slides/${id}.md`);
  return found;
}

const TOPICS: readonly Topic[] = topicData.topics;
const PARKED: Topic = topicData.parked;

/** A topic's description: plain text with **bold**, from topics.json. */
const about = (text: string): string => text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

/** The topics' cards, on the topics page and the appendix page: each one link to its topic's first slide, marked when some of
 * its slides are drafts, and, with `tagAppendix`, when it is in the appendix. */
function topicCards(topics: readonly Topic[], tagAppendix: boolean): HTMLElement {
  const grid = document.createElement("div");
  grid.className = "topics";
  for (const topic of topics) {
    const card = document.createElement("a");
    card.className = "card topic-card";
    card.href = `#/${topic.slides[0] ?? ""}`;
    const drafts = topic.slides.filter((id) => content(id).meta.draft).length;
    const mark =
      drafts === 0
        ? ""
        : `<span class="topic-wip">${drafts === topic.slides.length ? "Work in progress" : "Partly work in progress"}</span>`;
    const tag = tagAppendix && topic.appendix ? `<span class="topic-tag">Appendix</span>` : "";
    card.innerHTML = `<h2></h2>${tag}${mark}<p></p><span class="topic-start">Start →</span>`;
    card.querySelector("h2")!.textContent = topic.name;
    // Static text of topics.json, with the causes of stutter marked
    card.querySelector("p")!.innerHTML = about(topic.about);
    grid.append(card);
  }
  return grid;
}

/** A `:::video` block's clip: `single MOTION TOP BOTTOM [top|bottom] [chart]` shows one box of the clip, `pair MOTION TOP BOTTOM
 * [nochart] [frames] [controls] [nomodes]` both, `file NAME` a rendered video, each with the block's text as the caption. The
 * clips are listed in clips.json, for the export. */
function video(args: readonly string[], caption: string): HTMLElement {
  const [kind, motion = "", top = "", bottom = "", ...flags] = args;
  if (kind === "single")
    return singleBox(motion, top, bottom, flags.includes("top") ? "top" : "bottom", caption, flags.includes("chart"));
  if (kind === "pair") {
    const [chart, frames, controls] = [!flags.includes("nochart"), flags.includes("frames"), flags.includes("controls")];
    return liveComparison(motion, top, bottom, caption, chart, frames, controls, !flags.includes("nomodes"));
  }
  if (kind === "file") {
    // After the name: a height (a number) and flags, in any order
    const rest = [top, bottom, ...flags].filter(Boolean);
    const height = rest.find((arg) => /^\d+$/.test(arg));
    return renderedClip(motion, caption, height ? Number(height) : undefined, rest.includes("controls"));
  }
  throw new Error(`a video is single, pair or file, not ${kind ?? "nothing"}`);
}

/** The live parts of a slide's HTML, filled in: videos, refresh strips, the topics' cards, the link to the first draft, and each
 * card of links as a list of links out of the page, each with its note. */
function fill(element: HTMLElement): void {
  for (const holder of element.querySelectorAll<HTMLElement>("[data-live]")) {
    const args = (holder.dataset["args"] ?? "").split(/\s+/).filter(Boolean);
    switch (holder.dataset["live"]) {
      case "video":
        holder.replaceWith(video(args, (holder.textContent ?? "").replace(/\s+/g, " ").trim()));
        break;
      case "strip":
        holder.outerHTML = refreshStrip(Number(args[0]), Number(args[1]));
        break;
      case "topics":
        // `::topics appendix`: only the appendix's topics
        holder.replaceWith(
          args[0] === "appendix"
            ? topicCards(
                TOPICS.filter((topic) => topic.appendix),
                false,
              )
            : topicCards(TOPICS, true),
        );
        break;
    }
  }
  for (const list of element.querySelectorAll("[data-links] ul")) {
    list.className = "links";
    for (const item of list.querySelectorAll("li")) {
      const link = item.querySelector("a");
      if (!link) continue;
      link.append(" ↗");
      const note = document.createElement("span");
      note.textContent = (item.textContent ?? "").slice(link.textContent.length).replace(/\s+/g, " ").trim();
      item.replaceChildren(link, note);
    }
  }
}

/** The slide in web/content/slides/`id`.md. */
function markdownSlide(id: string): Slide {
  const { meta, html } = content(id);
  return {
    id,
    title: meta.title,
    render() {
      const element = document.createElement("div");
      element.className = "slide-body explain";
      element.innerHTML = html;
      fill(element);
      return element;
    },
  };
}

/** A topic's slide with a line above its heading (the topic and where in it this slide is, linking back to the topics) and its
 * work-in-progress notice when it is a draft. */
function withTopic(id: string, topic: Topic, position: number): Slide {
  const slide = markdownSlide(id);
  return {
    ...slide,
    render() {
      const element = slide.render();
      const line = Object.assign(document.createElement("a"), {
        className: "topic-line",
        href: "#/topics",
        textContent: `‹ ${topic.name} · ${position + 1} of ${topic.slides.length}`,
      });
      if (content(id).meta.draft) {
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

/** Every slide of the topics, in order, each with its topic line. */
const slidesOf = (topics: readonly Topic[]): Slide[] =>
  topics.flatMap((topic) => topic.slides.map((id, position) => withTopic(id, topic, position)));

/** The explanation slides, in order: the topics first, then every topic's slides, the appendix page before the appendix's
 * topics, and the set-aside slides last. */
export const EXPLANATION_SLIDES: readonly Slide[] = [
  markdownSlide("topics"),
  ...slidesOf(TOPICS.filter((topic) => !topic.appendix)),
  markdownSlide("appendix"),
  ...slidesOf(TOPICS.filter((topic) => topic.appendix)),
  markdownSlide("parked"),
  ...PARKED.slides.map((id, position) => withTopic(id, PARKED, position)),
];
