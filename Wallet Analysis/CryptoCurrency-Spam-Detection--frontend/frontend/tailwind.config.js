/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        sidebar: {
          bg: '#0a0a0f',
          border: 'rgba(255,255,255,0.07)',
          active: 'rgba(124,58,237,0.18)',
          hover: 'rgba(255,255,255,0.05)',
        },
        surface: {
          DEFAULT: 'rgba(255,255,255,0.04)',
          hover: 'rgba(255,255,255,0.07)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        glass: '0 0 0 1px rgba(255,255,255,0.06), 0 10px 30px rgba(0,0,0,0.35)',
        glow: '0 0 20px rgba(124,58,237,0.25)',
        'glow-sm': '0 0 10px rgba(124,58,237,0.15)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-in': 'slideIn 0.25s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
