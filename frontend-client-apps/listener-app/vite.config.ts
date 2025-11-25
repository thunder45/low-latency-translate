import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    visualizer({
      filename: './dist/stats.html',
      open: false,
      gzipSize: true,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': path.resolve(__dirname, '../shared'),
      // Polyfill Node.js 'events' module for browser compatibility
      // Required by amazon-kinesis-video-streams-webrtc
      'events': path.resolve(__dirname, '../node_modules/events/events.js'),
    },
  },
  define: {
    // Polyfill Node.js globals for browser
    'process.env': {},
    'global': 'globalThis',
  },
  build: {
    target: 'es2020',
    minify: 'terser',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'state-vendor': ['zustand'],
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'zustand',
      'events', // Polyfill for amazon-kinesis-video-streams-webrtc
      'amazon-kinesis-video-streams-webrtc',
    ],
    esbuildOptions: {
      // Define Node.js globals for dependency pre-bundling
      define: {
        global: 'globalThis',
      },
    },
  },
  server: {
    port: 3001,
    open: true,
  },
});
