/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#005c55",
        "primary-container": "#0f766e",
        background: "#f8fafc",
        "surface-bright": "#f7f9fb",
        "surface-white": "#FFFFFF",
        "text-primary": "#0F172A",
        "text-secondary": "#64748B",
        "border-subtle": "#E2E8F0",
        "compliance-amber": "#D97706",
        error: "#ba1a1a",
      },
      maxWidth: {
        chat: "720px",
      },
      boxShadow: {
        soft: "0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05)",
        sticky: "0 10px 15px -3px rgb(0 0 0 / 0.05), 0 4px 6px -4px rgb(0 0 0 / 0.05)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
