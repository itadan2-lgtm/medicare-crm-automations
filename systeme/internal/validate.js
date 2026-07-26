// Checks a page design against systeme.io's rules before it's sent.
//
// Worth having because the failure is expensive and quiet: a design that
// breaks a rule is rejected after you've already paid for the thinking that
// produced it, and the message you get back doesn't say which row was wrong.
//
// Every rule here was read off systeme.io's own describe_funnel_page_schema
// output, one call per page type. If they change the schema, that call is
// the source of truth and this file is what needs updating.

const ALL_BLOCKS = [
  "Headline",
  "Text",
  "Button",
  "Image",
  "BulletList",
  "Stat",
  "Form",
  "Menu",
  "Card",
  "Testimonial",
  "Faq",
  "Countdown",
  "Video",
  "HorizontalLine",
];

const EMBEDDED = {
  minSections: 1,
  maxSections: 2,
  tones: ["plain", "footer"],
  blocks: ["Headline", "Text", "Form", "Image", "BulletList", "HorizontalLine"],
  maxForm: 1,
  h1: "never",
};

const RULES = {
  squeeze: {
    minSections: 1,
    maxSections: 12,
    tones: [
      "hero",
      "feature",
      "pain",
      "testimonials",
      "social-proof",
      "faq",
      "logos",
      "cta-final",
      "footer",
      "plain",
    ],
    blocks: ALL_BLOCKS,
    maxForm: 1,
    maxFaq: 1,
    h1: "hero-only",
  },
  opt_in_thank_you_page: {
    minSections: 1,
    maxSections: 3,
    tones: ["hero", "footer", "plain"],
    blocks: [
      "Headline",
      "Text",
      "Button",
      "Image",
      "BulletList",
      "Stat",
      "Menu",
      "Card",
      "Video",
      "HorizontalLine",
    ],
    maxButton: 1,
    h1: "hero-only",
  },
  link_in_bio: {
    minSections: 1,
    maxSections: 1,
    tones: ["hero", "plain"],
    blocks: ["Image", "Headline", "Text", "Button", "HorizontalLine"],
    h1: "hero-only",
  },
  info_page: {
    minSections: 2,
    maxSections: 12,
    tones: ["hero", "plain", "footer"],
    blocks: ["Headline", "Text", "BulletList", "Image", "Button", "Menu"],
    h1: "hero-only",
    backgroundMustBeNull: true,
  },
  inline: EMBEDDED,
  popup: EMBEDDED,
};

const PALETTE_KEYS = [
  "background",
  "surface",
  "accent",
  "accentText",
  "mutedText",
  "cornerStyle",
  "fontPair",
];
const CORNER_STYLES = ["sharp", "soft", "rounded"];
const FONT_PAIRS = ["modern-sans", "editorial", "friendly", "corporate", "techy"];

// Fields each block type must carry. systeme.io requires every listed
// property to be present - including the nullable ones, which have to be
// explicitly null rather than left out.
const REQUIRED_FIELDS = {
  Headline: ["text", "level"],
  Text: ["textAlign", "html"],
  Button: ["text", "subText"],
  Image: ["imageDescription"],
  BulletList: ["items"],
  Stat: ["text", "statLabel"],
  Form: ["formFields", "formSubmitText"],
  Menu: ["menuItems"],
  Card: ["text", "html", "imageDescription", "subText"],
  Testimonial: ["quote", "authorName", "authorRole", "avatarDescription", "rating"],
  Faq: ["items"],
  Countdown: ["targetDateTime"],
  Video: ["url"],
  HorizontalLine: [],
};

function validate(design, pageType) {
  const rules = RULES[pageType];
  if (!rules) {
    return [`"${pageType}" isn't a systeme.io page type (${Object.keys(RULES).join(", ")}).`];
  }

  const problems = [];
  const counts = {};

  const palette = design?.palette;
  if (!palette || typeof palette !== "object") {
    problems.push("palette is missing.");
  } else {
    for (const key of PALETTE_KEYS) {
      if (palette[key] === undefined) problems.push(`palette.${key} is missing.`);
    }
    if (palette.cornerStyle && !CORNER_STYLES.includes(palette.cornerStyle)) {
      problems.push(`palette.cornerStyle "${palette.cornerStyle}" isn't one of ${CORNER_STYLES.join(", ")}.`);
    }
    if (palette.fontPair && !FONT_PAIRS.includes(palette.fontPair)) {
      problems.push(`palette.fontPair "${palette.fontPair}" isn't one of ${FONT_PAIRS.join(", ")}.`);
    }
  }

  const sections = design?.sections;
  if (!Array.isArray(sections)) return problems.concat("sections is missing or isn't a list.");

  if (sections.length < rules.minSections || sections.length > rules.maxSections) {
    problems.push(
      `${sections.length} section${sections.length === 1 ? "" : "s"} - ${pageType} allows ` +
        `${rules.minSections}-${rules.maxSections}.`
    );
  }

  sections.forEach((section, s) => {
    const where = `section ${s + 1}`;
    if (!rules.tones.includes(section.tone)) {
      problems.push(`${where}: tone "${section.tone}" isn't allowed on ${pageType}.`);
    }
    if (!("backgroundImageDescription" in section)) {
      problems.push(`${where}: backgroundImageDescription is missing (use null for no image).`);
    } else if (rules.backgroundMustBeNull && section.backgroundImageDescription !== null) {
      problems.push(`${where}: ${pageType} needs backgroundImageDescription to be null.`);
    }

    const rows = section.rows;
    if (!Array.isArray(rows) || rows.length === 0) {
      problems.push(`${where}: has no rows.`);
      return;
    }
    if (rows.length > 2) {
      problems.push(`${where}: ${rows.length} rows - a section takes 1-2. Split it.`);
    }

    rows.forEach((row, r) => {
      const rowWhere = `${where}, row ${r + 1}`;
      const columns = row.columns;
      if (!Array.isArray(columns) || columns.length === 0) {
        problems.push(`${rowWhere}: has no columns.`);
        return;
      }
      if (columns.length > 3) {
        problems.push(`${rowWhere}: ${columns.length} columns - a row takes 1-3.`);
      }
      const total = columns.reduce((sum, c) => sum + (Number(c.size) || 0), 0);
      if (total !== 12) {
        problems.push(
          `${rowWhere}: column sizes add up to ${total}, not 12 ` +
            `(${columns.map((c) => c.size).join(" + ")}).`
        );
      }

      columns.forEach((column, c) => {
        const blocks = column.blocks;
        if (!Array.isArray(blocks)) {
          problems.push(`${rowWhere}, column ${c + 1}: blocks is missing.`);
          return;
        }
        blocks.forEach((block, b) => {
          const blockWhere = `${rowWhere}, column ${c + 1}, block ${b + 1}`;
          if (!rules.blocks.includes(block.type)) {
            problems.push(`${blockWhere}: ${block.type} isn't allowed on ${pageType}.`);
            return;
          }
          counts[block.type] = (counts[block.type] || 0) + 1;

          for (const field of REQUIRED_FIELDS[block.type] || []) {
            if (!(field in block)) problems.push(`${blockWhere} (${block.type}): ${field} is missing.`);
          }

          if (block.type === "Headline" && block.level === "h1") {
            if (rules.h1 === "never") {
              problems.push(`${blockWhere}: h1 isn't allowed on ${pageType} at all.`);
            } else if (section.tone !== "hero") {
              problems.push(`${blockWhere}: h1 is only allowed in a hero section.`);
            }
          }
        });
      });
    });
  });

  if (rules.maxForm && (counts.Form || 0) > rules.maxForm) {
    problems.push(`${counts.Form} Form blocks - a page takes at most ${rules.maxForm}.`);
  }
  if (rules.maxFaq && (counts.Faq || 0) > rules.maxFaq) {
    problems.push(`${counts.Faq} Faq blocks - a page takes at most ${rules.maxFaq}.`);
  }
  if (rules.maxButton && (counts.Button || 0) > rules.maxButton) {
    problems.push(`${counts.Button} Button blocks - ${pageType} takes at most ${rules.maxButton}.`);
  }
  if ((counts.Headline || 0) > 0) {
    const h1s = sections
      .flatMap((s) => s.rows || [])
      .flatMap((r) => r.columns || [])
      .flatMap((c) => c.blocks || [])
      .filter((b) => b.type === "Headline" && b.level === "h1").length;
    if (h1s > 1) problems.push(`${h1s} h1 headlines - a page takes exactly one.`);
  }

  return problems;
}

module.exports = { validate, RULES, PAGE_TYPES: Object.keys(RULES) };
