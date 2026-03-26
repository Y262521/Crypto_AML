import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      'zustand/traditional': path.resolve('./node_modules/zustand/traditional.js'),
      'zustand/shallow': path.resolve('./node_modules/zustand/shallow.js'),
      'zustand/vanilla': path.resolve('./node_modules/zustand/vanilla.js'),
      'zustand/middleware': path.resolve('./node_modules/zustand/middleware.js'),
      'zustand/react': path.resolve('./node_modules/zustand/react.js'),
    }
  }
})
