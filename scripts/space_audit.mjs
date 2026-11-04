#!/usr/bin/env node
/**
 * Space-use audit: flags dashboard cards that leave most of their area empty.
 *
 * The design review rule (docs/REDESIGN_DIRECTION_2026-10.md, "Space use") in
 * script form. Loads each page at a desktop width, finds every card, and
 * measures what share of the card's inner width is covered by visible content
 * (text, SVG/canvas/img, and filled shapes such as bars), and how much empty
 * space sits below the content. Prints a table and saves a screenshot of each
 * flagged card so a reviewer can look before a design PR.
 *
 * It is a prompt for a human look, not a gate: a deliberately airy card can be
 * waved through. It catches the case that prompted it (2026-11-04): a
 * three-bar city/county/metro chart given a full-width card, using about a
 * third of it.
 *
 * Usage (needs Playwright; run from a dashboard repo with its dev server up):
 *   node node_modules/civic-dashboard-kit/scripts/space_audit.mjs http://localhost:3000/ [more urls]
 *     [--selector .stat-card] [--width 1280] [--min-width-share 0.6]
 *     [--max-empty-below 0.35] [--out space-audit]
 * Exit code 0 always; read the table.
 */
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(path.join(process.cwd(), 'noop.js'));
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  if (i === -1) return fallback;
  const value = args[i + 1];
  args.splice(i, 2);
  return value;
};
const selector = opt('selector', '.stat-card');
const width = Number(opt('width', '1280'));
const minWidthShare = Number(opt('min-width-share', '0.6'));
const maxEmptyBelow = Number(opt('max-empty-below', '0.35'));
const outDir = opt('out', 'space-audit');
const urls = args;
if (!urls.length) {
  console.error('usage: space_audit.mjs <url> [url...] [--selector .stat-card] [--width 1280]');
  process.exit(2);
}

/** Runs in the page: per-card coverage numbers. */
function measure(sel) {
  const filled = (el) => {
    const s = getComputedStyle(el);
    const bg = s.backgroundColor;
    return bg && bg !== 'transparent' && !/rgba\(.*,\s*0\)$/.test(bg);
  };
  const visible = (r) => r.width > 0.5 && r.height > 0.5;
  return [...document.querySelectorAll(sel)].map((card, index) => {
    const box = card.getBoundingClientRect();
    const s = getComputedStyle(card);
    const left = box.left + parseFloat(s.paddingLeft);
    const right = box.right - parseFloat(s.paddingRight);
    const top = box.top + parseFloat(s.paddingTop);
    const bottom = box.bottom - parseFloat(s.paddingBottom);
    const rects = [];
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.textContent.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        rects.push(...[...range.getClientRects()].filter(visible));
      } else if (['svg', 'canvas', 'img', 'video'].includes(node.localName)) {
        // A chart SVG counts by its drawn marks, not its (always full-width) box.
        if (node.localName === 'svg') {
          for (const mark of node.querySelectorAll('path, line, rect, circle, polyline, text')) {
            const r = mark.getBoundingClientRect();
            if (r.width > 0.5 || r.height > 0.5) rects.push(r);
          }
        } else {
          rects.push(node.getBoundingClientRect());
        }
      } else if (node !== card && filled(node) && !node.children.length) {
        rects.push(node.getBoundingClientRect());
      }
    }
    const spans = rects
      .map((r) => [Math.max(left, r.left), Math.min(right, r.right)])
      .filter(([a, b]) => b > a)
      .sort((a, b) => a[0] - b[0]);
    let covered = 0;
    let end = -Infinity;
    for (const [a, b] of spans) {
      if (b <= end) continue;
      covered += b - Math.max(a, end);
      end = b;
    }
    const contentBottom = Math.max(top, ...rects.map((r) => r.bottom));
    const title = (card.querySelector('h1,h2,h3,h4')?.textContent ?? card.textContent).trim().slice(0, 70);
    return {
      index,
      title,
      widthShare: (right - left) > 0 ? covered / (right - left) : 1,
      emptyBelow: (bottom - top) > 0 ? Math.max(0, bottom - contentBottom) / (bottom - top) : 0,
      cardWidth: Math.round(box.width),
      cardHeight: Math.round(box.height),
    };
  });
}

mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height: 900 } });
let flaggedTotal = 0;
for (const url of urls) {
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const cards = await page.evaluate(measure, selector);
  const slug = new URL(url).pathname.replace(/\W+/g, '-').replace(/^-|-$/g, '') || 'home';
  console.log(`\n${url} — ${cards.length} cards at ${width}px`);
  for (const c of cards) {
    const reasons = [];
    if (c.widthShare < minWidthShare) reasons.push(`content covers ${Math.round(c.widthShare * 100)}% of width`);
    if (c.emptyBelow > maxEmptyBelow) reasons.push(`${Math.round(c.emptyBelow * 100)}% empty below content`);
    if (!reasons.length) continue;
    flaggedTotal += 1;
    const file = path.join(outDir, `${slug}-card${c.index}.png`);
    await page.locator(selector).nth(c.index).screenshot({ path: file });
    console.log(`  FLAG #${c.index} ${c.cardWidth}x${c.cardHeight} "${c.title}": ${reasons.join('; ')} -> ${file}`);
  }
}
await browser.close();
console.log(`\n${flaggedTotal} card(s) flagged. Each is a prompt to look, not a failure.`);
