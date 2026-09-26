import { defineConfig } from "vitest/config";

// Relative asset paths, so the built page works under any path (GitHub Pages serves it from /<repository>/)
export default defineConfig({
  base: "./",
  build: { target: "es2022" },
  test: { environment: "node" },
});
