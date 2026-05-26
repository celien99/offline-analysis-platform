/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        "primary-hover": "var(--color-primary-hover)",
        "primary-active": "var(--color-primary-active)",
        defect: "var(--color-defect)",
        "false-alarm": "var(--color-false-alarm)",
        pending: "var(--color-pending)",
        neutral: "var(--color-neutral)",
        "sider-bg": "var(--sider-bg)",
      },
      boxShadow: {
        "card-sm": "var(--shadow-sm)",
        "card-md": "var(--shadow-md)",
        "card-lg": "var(--shadow-lg)",
      },
      borderRadius: {
        card: "var(--radius-md)",
        "card-lg": "var(--radius-lg)",
      },
    },
  },
  plugins: [],
};
