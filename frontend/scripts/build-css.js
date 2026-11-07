const fs = require("fs");
const path = require("path");
const { compile } = require("@tailwindcss/node");
const { Scanner } = require("@tailwindcss/oxide");

async function buildCSS() {
  const rootDir = path.resolve(__dirname, "..");
  const inputFile = path.join(rootDir, "src", "app", "input.css");
  const outputFile = path.join(rootDir, "src", "app", "globals.css");

  const css = fs.readFileSync(inputFile, "utf8");

  const compiled = await compile(css, {
    base: rootDir,
    onDependency: () => {},
  });

  const scanner = new Scanner({
    sources: [
      {
        base: path.join(rootDir, "src"),
        pattern: "**/*.{ts,tsx,js,jsx}",
        negated: false,
      },
    ],
  });

  const candidates = scanner.scan();
  const builtCss = compiled.build(candidates);

  fs.writeFileSync(outputFile, builtCss, "utf8");
  console.log(`[build-css] Successfully built Tailwind CSS to ${outputFile} (${builtCss.length} bytes, ${candidates.length} candidates scanned)`);
}

buildCSS().catch((err) => {
  console.error("[build-css] Error compiling CSS:", err);
  process.exit(1);
});

