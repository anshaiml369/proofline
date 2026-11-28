/** Build: npx tailwindcss@3.4.17 -c tailwind/tailwind.config.js -i tailwind/input.css -o static/tailwind.css --minify */
module.exports = {
  content: ["./templates/**/*.html", "./static/app.js"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Noto Sans", "Noto Sans Devanagari", "Roboto", "sans-serif"],
      },
    },
  },
};
