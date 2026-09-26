import { defineConfig } from "vitest/config";

// Relative asset paths, so the built page works under any path (GitHub Pages serves it from /<repository>/)
export default defineConfig({
  base: "./",
  build: { target: "es2022" },
  // The explanation slides use the timing diagrams of doc/images, outside web/
  server: { fs: { allow: [".."] } },
  test: { environment: "node" },
});
