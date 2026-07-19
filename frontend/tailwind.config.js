/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // A deliberate "engineering tool" palette, not the generic
        // AI-chat purple/teal defaults: deep ink-navy surfaces with a
        // warm amber accent (evokes a terminal / query-log aesthetic,
        // fitting for a SQL tool).
        ink: {
          950: "#0b0f14",
          900: "#11161d",
          850: "#161c25",
          800: "#1c2430",
          700: "#2a3441",
          600: "#3c4a5b",
          500: "#57697d",
          400: "#7c8fa3",
          300: "#a7b6c6",
          200: "#d1dae2",
          100: "#eef1f4",
        },
        amber: {
          600: "#b4750f",
          500: "#d3910f",
          400: "#e8a934",
          300: "#f2c463",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
