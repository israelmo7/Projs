/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        nevo: {
          bg: '#0f1419',
          card: '#1a2332',
          accent: '#00d4aa',
          wake: '#ff6b35',
          muted: '#8899aa',
        },
      },
    },
  },
  plugins: [],
}
