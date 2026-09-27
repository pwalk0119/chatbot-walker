import { defineConfig } from "vitest/config";

export default defineConfig({
  build: {
    // Library build: a single self-contained script PNW pages can load with one <script> tag.
    lib: {
      entry: "src/widget/index.ts",
      name: "PnwChatbot",
      formats: ["iife"],
      fileName: () => "pnw-chatbot.js",
    },
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
  },
});
