import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@openbuild/types": path.resolve(
        __dirname,
        "../../packages/types/src/index.ts"
      ),
      "@openbuild/ui": path.resolve(
        __dirname,
        "../../packages/ui/src/index.ts"
      ),
      "@openbuild/pdf-engine": path.resolve(
        __dirname,
        "../../packages/pdf-engine/src/index.ts"
      ),
      "@openbuild/cost-codes": path.resolve(
        __dirname,
        "../../packages/cost-codes/src/index.ts"
      ),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
    },
  },
});
