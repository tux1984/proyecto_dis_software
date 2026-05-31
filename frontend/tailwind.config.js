/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        javeriana: { 50: '#eef2fb', 600: '#1e3c78', 700: '#16305f', 900: '#0d1e3c' },
      },
    },
  },
  plugins: [],
}
