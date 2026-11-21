#!/usr/bin/env node
// Adds a content hash to the asset URLs in index.html (recipes.js -> recipes.js?v=1a2b3c4d5e).
//
// nginx serves .js and .css as `immutable` for a day, and Cloudflare caches them at the edge.
// With fixed filenames, a deploy kept serving the old recipes until those copies expired.
// A new hash means a new URL, so every deploy is picked up on the next page load.
//
// Runs in the Docker build on the built copy, so the committed index.html stays unstamped.
// Safe to run more than once: an existing ?v= is replaced.
//
// Usage: node scripts/stamp-assets.js [website-dir]

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ASSETS = ['styles.css', 'recipes.js', 'app.js'];

const websiteDir = path.resolve(process.argv[2] || path.join(__dirname, '..', 'website'));
const indexPath = path.join(websiteDir, 'index.html');
let html = fs.readFileSync(indexPath, 'utf-8');

for (const asset of ASSETS) {
  const hash = crypto
    .createHash('sha256')
    .update(fs.readFileSync(path.join(websiteDir, asset)))
    .digest('hex')
    .slice(0, 10);

  const escaped = asset.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const ref = new RegExp(`((?:src|href)=")(/?)${escaped}(?:\\?v=[0-9a-f]+)?"`, 'g');
  const matches = html.match(ref);
  if (!matches) {
    console.error(`stamp-assets: no reference to ${asset} in index.html`);
    process.exit(1);
  }

  html = html.replace(ref, `$1$2${asset}?v=${hash}"`);
  console.log(`${asset}?v=${hash}`);
}

fs.writeFileSync(indexPath, html);
