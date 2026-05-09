import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";

const outDir = path.resolve(import.meta.dirname, "../static/visual/dist");

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir,
    emptyOutDir: true,
    sourcemap: false,
    assetsDir: "",
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "app.[hash].js",
        assetFileNames: ({ name }) => {
          if (name && name.endsWith(".css")) {
            return "app.css";
          }
          return "assets/[name]-[hash][extname]";
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
});
