import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#0A0A0F", surface: "#111118", elevated: "#1A1A24" },
        profit: "#22C55E",
        loss: "#EF4444",
        warning: "#F59E0B",
        info: "#3B82F6",
        purple: "#8B5CF6",
        txt: { DEFAULT: "#F0F0F5", secondary: "#888899", muted: "#555566" },
      },
    },
  },
  plugins: [],
};
export default config;
