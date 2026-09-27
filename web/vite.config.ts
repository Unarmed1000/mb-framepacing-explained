import { defineConfig } from "vitest/config";
import { slideMarkdown } from "./build/slide-markdown.ts";

// Relative asset paths, so the built page works under any path (GitHub Pages serves it from /<repository>/)
export default defineConfig({
  base: "./",
  build: { target: "es2022" },
  // The explanation slides are Markdown files in content/, turned into HTML when the page is built
  plugins: [slideMarkdown()],
  // The explanation slides use the timing diagrams of doc/images, outside web/
  server: { fs: { allow: [".."] } },
  test: { environment: "node" },
});
