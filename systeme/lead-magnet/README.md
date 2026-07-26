# The lead magnet, and the images of it

The checklist itself, and the product mockups made from it. Everything here
renders offline from HTML — no design tool, no stock photos.

```bash
cd systeme/lead-magnet
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i playwright @fontsource/fraunces @fontsource/karla
node render.js
```

Out come four files:

| File | What it's for |
|---|---|
| `Doctor-Visit-Prep-Checklist.pdf` | The download itself. Upload to systeme.io under Contacts → Files, then paste its URL into email 1. |
| `checklist-page.png` | The flat page render, at 3x. Source for the mockups. |
| `mockup-hero.png` | 1800×1200 — the opt-in page hero |
| `mockup-square.png` | 1200×1200 — cards, Pinterest, Etsy listing |

These are kept out of the main `package.json` on purpose: Playwright is a
large install and nothing else in this repo needs it.

## Editing

`checklist.html` is the checklist — A4, print-ready, styled to the same
palette as the funnel pages (`#FDFBF7` paper, `#A83E22` accent, Fraunces
over Karla). Change the copy there and re-run `render.js`; the mockups
rebuild from the new render automatically.

Two things to change before you publish: the `yourbrand.com` mark in the
footer, and whether the four-row symptom table is the right length for your
audience.

## Getting them onto the pages

By hand — there's no way to do it through the API. systeme.io's page tools
have no file upload, and an Image block carries only keywords for a stock
lookup, not a URL you supply. So: page editor, upload, swap.
