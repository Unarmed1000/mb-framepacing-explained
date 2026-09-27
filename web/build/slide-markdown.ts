// Turns a slide's Markdown file (web/content/slides/*.md) into a module when the page is built: its front matter as `meta`, and
// its body as the slide's HTML with the page's classes, so the published page needs no Markdown code. A slide is plain Markdown
// (see web/content/README.md), plus:
// - front matter: `title` (the short name, in the navigation), `eyebrow` (the small heading above the title), `draft: true`;
// - blocks, `:::name args` to `:::`: card (a card, args its heading), links (a card of links), guide (cards side by side),
//   figures (diagrams side by side), video (a live clip, args `single|pair MOTION TOP BOTTOM [top|bottom] [chart|nochart]`, its
//   caption inside);
// - lines filled in when the slide is shown: `::strip HZ FPS` (a refresh strip) and `::topics` (the topics page's cards);
// - `{.note}` or `{.more}` at the end of a paragraph: a note, or a row of links to read more.
// The first paragraph after the title is the lead, and a paragraph with only an image is a diagram.

import MarkdownIt from "markdown-it";
import type { Plugin } from "vite";

export interface SlideMeta {
  title: string;
  eyebrow: string;
  draft: boolean;
}

const escape = (text: string): string =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** The front matter (`key: value` lines between `---` lines) and the Markdown after it. */
export function frontMatter(source: string): { meta: SlideMeta; body: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/.exec(source);
  if (!match) throw new Error("a slide starts with its front matter, between two --- lines");
  const fields = new Map<string, string>();
  for (const line of (match[1] ?? "").split(/\r?\n/)) {
    const field = /^(\w+):\s*(.*)$/.exec(line);
    if (field) fields.set(field[1] ?? "", (field[2] ?? "").trim());
  }
  const title = fields.get("title");
  const eyebrow = fields.get("eyebrow");
  if (!title || !eyebrow) throw new Error("a slide's front matter needs a title and an eyebrow");
  return { meta: { title, eyebrow, draft: fields.get("draft") === "true" }, body: source.slice(match[0].length) };
}

const BLOCKS: Readonly<Record<string, (args: string) => string>> = {
  card: (args) => `<div class="card">${args ? `<h2>${escape(args)}</h2>` : ""}`,
  links: (args) => `<div class="card" data-links>${args ? `<h2>${escape(args)}</h2>` : ""}`,
  guide: () => `<div class="guide">`,
  figures: () => `<div class="figures">`,
  video: (args) => `<div data-live="video" data-args="${escape(args)}">`,
};

/** The blocks and live lines as HTML, with blank lines around each tag so that the Markdown between them stays Markdown. */
export function expandDirectives(body: string): string {
  const open: string[] = [];
  const lines = body.split(/\r?\n/).flatMap((line, index) => {
    const block = /^:::(\w+)\s*(.*)$/.exec(line);
    if (block) {
      const name = block[1] ?? "";
      const start = BLOCKS[name];
      if (!start) throw new Error(`line ${index + 1}: no block named :::${name}`);
      open.push(name);
      return ["", start((block[2] ?? "").trim()), ""];
    }
    if (/^:::\s*$/.test(line)) {
      if (open.pop() === undefined) throw new Error(`line ${index + 1}: this ::: closes no block`);
      return ["", "</div>", ""];
    }
    const live = /^::(strip|topics)\s*(.*)$/.exec(line);
    if (live) return ["", `<div data-live="${live[1] ?? ""}" data-args="${escape((live[2] ?? "").trim())}"></div>`, ""];
    return [line];
  });
  if (open.length > 0) throw new Error(`:::${open.at(-1) ?? ""} is not closed`);
  return lines.join("\n");
}

/** Markdown with the page's classes; images other than web addresses are collected in `images` and stand as placeholders. */
function markdown(images: string[]) {
  const md = new MarkdownIt({ html: true });
  md.core.ruler.push("slide_classes", (state) => {
    const tokens = state.tokens;
    let afterTitle = false;
    tokens.forEach((token, index) => {
      if (token.type === "heading_open") {
        // Headings in the Markdown are section titles; a card's heading comes from its block
        if (token.tag === "h2") token.attrJoin("class", "section-title");
        afterTitle = token.tag === "h1";
        return;
      }
      if (token.type === "bullet_list_open" || token.type === "ordered_list_open") token.attrJoin("class", "points");
      if (token.type === "table_open") token.attrJoin("class", "ways");
      if (token.type !== "paragraph_open") return;
      const inline = tokens[index + 1];
      const close = tokens[index + 2];
      const children = inline?.children;
      if (!inline || !close || !children) return;
      const last = children.at(-1);
      const marker = last?.type === "text" ? /\s*\{\.(note|more)\}\s*$/.exec(last.content) : null;
      if (last && marker) {
        last.content = last.content.slice(0, marker.index);
        const kind = marker[1] ?? "";
        token.attrJoin("class", kind);
        if (kind === "more") {
          // Every link in a row of "more" links points out of the page
          inline.children = children.flatMap((child) => {
            if (child.type !== "link_close") return [child];
            const arrow = new state.Token("text", "", 0);
            arrow.content = " ↗";
            return [arrow, child];
          });
        }
      } else if (children.length === 1 && children[0]?.type === "image") {
        token.tag = close.tag = "figure";
        token.attrJoin("class", "diagram");
      } else if (afterTitle) {
        token.attrJoin("class", "lead");
      }
      afterTitle = false;
    });
  });
  md.renderer.rules.image = (tokens, index) => {
    const token = tokens[index];
    const src = String(token?.attrGet("src") ?? "");
    const alt = token?.children ? md.renderer.renderInlineAsText(token.children, md.options, {}) : "";
    let url = src;
    if (!/^https?:/.test(src)) {
      images.push(src);
      url = `\u0000IMAGE${images.length - 1}\u0000`;
    }
    return `<img src="${escape(url)}" alt="${escape(alt)}" loading="lazy" />`;
  };
  md.renderer.rules.link_open = (tokens, index, options, _env, self) => {
    const token = tokens[index];
    if (token && /^https?:/.test(String(token.attrGet("href") ?? ""))) {
      token.attrSet("target", "_blank");
      token.attrSet("rel", "noopener");
    }
    return self.renderToken(tokens, index, options);
  };
  return md;
}

/** A slide's module: `meta`, and `html` with each local image imported (so the build copies it) in place of its placeholder. */
export function slideModule(source: string): string {
  const { meta, body } = frontMatter(source);
  const images: string[] = [];
  const html = `<p class="eyebrow">${escape(meta.eyebrow)}</p>\n` + markdown(images).render(expandDirectives(body));
  const parts = html.split(/\u0000IMAGE(\d+)\u0000/);
  const expression = parts.map((part, index) => (index % 2 === 1 ? `image${part}` : JSON.stringify(part))).join(" + ");
  const imports = images.map((src, index) => `import image${index} from ${JSON.stringify(`${src}?url`)};`).join("\n");
  return `${imports}\nexport const meta = ${JSON.stringify(meta)};\nexport const html = ${expression};\n`;
}

/** The Vite plugin: every imported .md file is a slide. */
export function slideMarkdown(): Plugin {
  return {
    name: "slide-markdown",
    enforce: "pre",
    transform(source, id) {
      if (!id.endsWith(".md")) return null;
      try {
        return { code: slideModule(source), map: null };
      } catch (error) {
        throw new Error(`${id}: ${error instanceof Error ? error.message : String(error)}`, { cause: error });
      }
    },
  };
}
