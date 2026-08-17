import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxy = {
  target: "http://127.0.0.1:8010",
  changeOrigin: true,
  rewrite: (path: string) => path.replace(/^\/api/, "")
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": apiProxy
    }
  },
  preview: {
    host: "127.0.0.1",
    proxy: {
      "/api": apiProxy
    }
  }
});
