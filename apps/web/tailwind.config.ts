import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // RYX Brand
        ryx: {
          primary: "#0EA5E9",    // sky-500 — bleu médical
          secondary: "#10B981",  // emerald-500 — vert sécurité
          danger: "#EF4444",     // red-500 — alerte critique
          warning: "#F59E0B",    // amber-500 — alerte modérée
          muted: "#6B7280",      // gray-500
        },
        // Criticality colors
        critical: "#DC2626",
        high: "#EA580C",
        moderate: "#D97706",
        low: "#059669",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
