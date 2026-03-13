import { resolve } from "path";
import { defineConfig } from "vite";

/**
 * Vite config for Phantex frontend.
 *
 * Outputs flat files into phantex/static/dist/ so Flask can serve them
 * via url_for('static'). No content hashing -- predictable filenames.
 *
 * Add new module entry points under rollupOptions.input as the project grows.
 */
export default defineConfig({
  root: resolve(__dirname, "frontend"),
  build: {
    outDir: resolve(__dirname, "phantex/static/dist"),
    emptyOutDir: true,
    cssCodeSplit: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "frontend/src/css/main.css"),
        bte: resolve(__dirname, "frontend/src/js/bte.js"),
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: "[name][extname]",
        chunkFileNames: "[name].js",
      },
    },
    minify: false,
  },
});
