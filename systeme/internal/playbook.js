// Playbooks are the house rules for a particular kind of funnel: markdown
// files in systeme/playbooks/, handed to Claude on top of the general brief.
//
// They exist because the generic advice for a landing page ("6-10 rich
// sections, testimonials, an FAQ, a stats band") is wrong for some jobs. An
// opt-in page converts better with one field and nothing else on it. Rather
// than argue with the general guidance, a playbook overrides it.
//
// Add your own by dropping a .md file in that folder - no code change.

const fs = require("fs");
const path = require("path");

const PLAYBOOK_DIR = path.join(__dirname, "..", "playbooks");

function list() {
  try {
    return fs
      .readdirSync(PLAYBOOK_DIR)
      .filter((f) => f.endsWith(".md"))
      .map((f) => f.replace(/\.md$/, ""))
      .sort();
  } catch {
    return [];
  }
}

// Accepts "lead-magnet" or "lead-magnet.md"; also accepts a path to a file
// somewhere else entirely, so a one-off brief doesn't have to be checked in.
function load(name) {
  const wanted = String(name || "").trim();
  if (!wanted) throw new Error("Which playbook? Available: " + (list().join(", ") || "none"));

  const candidates = [
    path.join(PLAYBOOK_DIR, `${wanted.replace(/\.md$/, "")}.md`),
    path.resolve(wanted),
  ];
  for (const file of candidates) {
    if (fs.existsSync(file) && fs.statSync(file).isFile()) {
      return { name: path.basename(file, ".md"), text: fs.readFileSync(file, "utf8").trim() };
    }
  }

  const available = list();
  throw new Error(
    `No playbook called "${wanted}". ` +
      (available.length
        ? `Available: ${available.join(", ")} (or give a path to a .md file).`
        : `The ${PLAYBOOK_DIR} folder has no .md files in it yet.`)
  );
}

module.exports = { PLAYBOOK_DIR, list, load };
