import animate from "tailwindcss-animate";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          teal: "#2DD4BF",
          blue: "#0EA5E9",
          indigo: "#6366F1",
        },
        ink: {
          900: "#0F172A",
          800: "#1E293B",
          700: "#334155",
        },
        risk: {
          low: "#22C55E",
          mid: "#F59E0B",
          high: "#EF4444",
        },
      },
      fontFamily: {
        sans: ["Noto Sans SC", "Noto Sans", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 32px rgba(45, 212, 191, 0.35)",
        "glow-blue": "0 0 32px rgba(14, 165, 233, 0.35)",
        "glow-red": "0 0 36px rgba(239, 68, 68, 0.45)",
        card: "0 18px 48px -20px rgba(0, 0, 0, 0.75)",
      },
      keyframes: {
        floaty: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        pulseRing: {
          "0%": { opacity: "0.7", transform: "scale(0.9)" },
          "70%": { opacity: "0", transform: "scale(1.6)" },
          "100%": { opacity: "0", transform: "scale(1.6)" },
        },
        scanline: {
          "0%": { transform: "translateY(-110%)" },
          "100%": { transform: "translateY(410%)" },
        },
      },
      animation: {
        floaty: "floaty 5s ease-in-out infinite",
        shimmer: "shimmer 2.4s linear infinite",
        pulseRing: "pulseRing 1.8s ease-out infinite",
        scanline: "scanline 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [animate],
};
