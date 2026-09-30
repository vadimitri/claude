import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [svelte()],
  server: { port: 5199, strictPort: true },
  build: {
    rollupOptions: {
      input: { index: resolve(__dirname, 'index.html'), test: resolve(__dirname, 'test.html') },
    },
  },
});
