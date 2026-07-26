const { chromium } = require("playwright");
const path = require("path");
const CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });

  // 1. the checklist itself, at true A4 proportions
  const doc = await browser.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 3 });
  await doc.goto("file://" + path.join(__dirname, "checklist.html"));
  await doc.waitForTimeout(700);
  await doc.pdf({ path: "Doctor-Visit-Prep-Checklist.pdf", format: "A4", printBackground: true });
  await doc.screenshot({ path: "checklist-page.png" });
  await doc.close();

  // 2. mockups built from that render
  const mock = await browser.newPage({ viewport: { width: 1800, height: 1200 }, deviceScaleFactor: 1 });
  await mock.goto("file://" + path.join(__dirname, "mockup.html"));
  await mock.waitForTimeout(700);
  await (await mock.$("#hero")).screenshot({ path: "mockup-hero.png" });
  await (await mock.$("#square")).screenshot({ path: "mockup-square.png" });
  await mock.close();

  console.log("rendered");
  await browser.close();
})().catch(e => { console.log("ERR", e.message); process.exit(1); });
