import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#131448",
        lilac: "#d8d9ff",
        canvas: "#f7f8fc"
      },
      boxShadow: {
        soft: "0 18px 50px rgba(28, 35, 91, .08)"
      }
    }
  },
  plugins: []
};

export default config;
