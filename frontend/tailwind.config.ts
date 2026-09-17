import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: { primary: "#FAFAF7", dark: "#0F172A" },
        text: { primary: "#0F172A", muted: "#64748B" },
        accent: { DEFAULT: "#0EA5A4", hover: "#0D9488" },
        clash: { hard: "#DC2626", soft: "#F59E0B" },
        pass: "#10B981",
        border: "#E2E8F0",
      },
      fontFamily: {
        display: ["Inter", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        h1: ["56px", { lineHeight: "64px" }],
        h2: ["40px", { lineHeight: "48px" }],
        h3: ["24px", { lineHeight: "32px" }],
        eyebrow: ["12px", { lineHeight: "16px", letterSpacing: "0.1em" }],
      },
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
