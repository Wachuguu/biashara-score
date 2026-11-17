import type { Config } from "tailwindcss";

/**
 * Biashara Score tokens — "painted duka signboard".
 * Colours are high-contrast for outdoor/sunlight reading on low-end screens.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F7F2", // cool exercise-book white (page background)
        card: "#FFFFFF",
        ink: {
          DEFAULT: "#14213D", // primary text + panel borders
          soft: "#3D4A66", // secondary text (>= 7:1 on paper)
          faint: "#6B7590", // tertiary, large text only
        },
        rule: "#C9D6EA", // exercise-book ruled lines / dividers
        maize: { DEFAULT: "#F2C230", deep: "#D9A514", soft: "#FCF1C7" }, // signboard yellow
        cobalt: { DEFAULT: "#2340A8", deep: "#1A3185", soft: "#E3E9F8" }, // actions
        leaf: { DEFAULT: "#17663D", soft: "#DDF0E3" }, // money in / profit
        chili: { DEFAULT: "#B42A23", soft: "#F8DEDB" }, // owed / loss / margin line
      },
      fontFamily: {
        display: ["var(--font-display)", "Impact", "Arial Narrow", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      fontSize: {
        // ~1.25 scale, body bumped to 17px for readability
        xs: ["0.8125rem", { lineHeight: "1.25rem" }],
        sm: ["0.9375rem", { lineHeight: "1.4rem" }],
        base: ["1.0625rem", { lineHeight: "1.6rem" }],
        lg: ["1.25rem", { lineHeight: "1.75rem" }],
        xl: ["1.5rem", { lineHeight: "1.9rem" }],
        "2xl": ["1.875rem", { lineHeight: "2.2rem" }],
        "3xl": ["2.375rem", { lineHeight: "2.6rem" }],
        "4xl": ["3rem", { lineHeight: "1" }],
        sign: ["4.5rem", { lineHeight: "0.9" }],
      },
      borderRadius: {
        sign: "4px", // painted board
        sm: "6px", // chips
        md: "10px", // buttons, inputs
        lg: "16px", // panels, sheets
      },
      borderWidth: { 3: "3px" },
      boxShadow: {
        board: "4px 4px 0 0 #14213D", // signboard offset — hero only
        sheet: "0 -8px 32px rgba(20, 33, 61, 0.18)",
      },
      minHeight: { tap: "44px" },
      minWidth: { tap: "44px" },
      spacing: { nav: "4.25rem" },
      maxWidth: { app: "40rem" },
    },
  },
  plugins: [],
};

export default config;
