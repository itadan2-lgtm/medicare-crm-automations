// `npm run store:designs` - checks every page design in systeme/designs/
// against systeme.io's rules, offline and free.
//
// Page designs written by hand (or edited after Claude wrote them) are easy
// to get subtly wrong: a row whose columns add up to 11, an h1 outside the
// hero, a block type that page type doesn't accept. systeme.io rejects the
// save, and the error doesn't tell you which row. This does.
//
// Filenames carry the page type: <name>.<page_type>.json

const fs = require("fs");
const path = require("path");

const { validate, PAGE_TYPES } = require("./internal/validate");

const DESIGN_DIR = path.join(__dirname, "designs");

function pageTypeOf(filename) {
  const parts = path.basename(filename, ".json").split(".");
  return parts.length > 1 ? parts[parts.length - 1] : null;
}

function main() {
  const files = fs.existsSync(DESIGN_DIR)
    ? fs.readdirSync(DESIGN_DIR).filter((f) => f.endsWith(".json")).sort()
    : [];

  if (files.length === 0) {
    console.log(`\nNo designs in ${DESIGN_DIR} yet.\n`);
    return;
  }

  console.log("");
  let bad = 0;

  for (const file of files) {
    const pageType = pageTypeOf(file);
    if (!PAGE_TYPES.includes(pageType)) {
      console.log(`  ✖ ${file}`);
      console.log(
        `      Can't tell the page type from the name. Rename it to ` +
          `<name>.<type>.json, where type is one of: ${PAGE_TYPES.join(", ")}.`
      );
      bad++;
      continue;
    }

    let design;
    try {
      design = JSON.parse(fs.readFileSync(path.join(DESIGN_DIR, file), "utf8"));
    } catch (err) {
      console.log(`  ✖ ${file}`);
      console.log(`      Not valid JSON: ${err.message}`);
      bad++;
      continue;
    }

    const problems = validate(design, pageType);
    if (problems.length === 0) {
      const sections = design.sections.length;
      console.log(`  ✔ ${file} (${pageType}, ${sections} section${sections === 1 ? "" : "s"})`);
    } else {
      console.log(`  ✖ ${file}`);
      for (const problem of problems) console.log(`      ${problem}`);
      bad++;
    }
  }

  console.log("");
  if (bad === 0) {
    console.log(`${files.length} design${files.length === 1 ? "" : "s"} ready to save.\n`);
  } else {
    console.log(`${bad} of ${files.length} need fixing.\n`);
    process.exitCode = 1;
  }
}

if (require.main === module) main();

module.exports = { pageTypeOf, DESIGN_DIR };
