/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        // The cookbook's green since 2025 (#2d5a27).
        herb: { 50: '#f0f7ef', 100: '#e8f5e9', 200: '#c8e2c4', 400: '#5b8f53', 600: '#2d5a27', 700: '#1e3d1a', 800: '#162e13' },
        amazon: { 500: '#ff9900', 600: '#e68a00' },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
