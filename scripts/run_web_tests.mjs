#!/usr/bin/env node
// Run the browser tests of every tool against a built website.
//
//   python scripts/build_site.py --out _site --with-pyodide
//   node scripts/run_web_tests.mjs _site
//
// Serves the build under /sparky-tools/, as GitHub Pages does, and runs each
// tools/*/tests/web/*.test.mjs. A test module exports a default async
// function ({ browser, baseUrl, toolDir }) that throws on failure.
// Needs Playwright (npm install playwright, then npx playwright install chromium).
import { createServer } from 'node:http';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = path.resolve(process.argv[2] || '_site');
const PREFIX = '/sparky-tools/';
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json', '.wasm': 'application/wasm', '.zip': 'application/zip',
  '.py': 'text/plain; charset=utf-8', '.txt': 'text/plain; charset=utf-8',
};

function serve() {
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (!url.pathname.startsWith(PREFIX)) { res.writeHead(404); res.end(); return; }
      let file = path.join(SITE, decodeURIComponent(url.pathname.slice(PREFIX.length)));
      if (!file.startsWith(SITE)) { res.writeHead(403); res.end(); return; }
      if ((await stat(file).catch(() => null))?.isDirectory()) file = path.join(file, 'index.html');
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
      res.end(body);
    } catch {
      res.writeHead(404); res.end();
    }
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

async function main() {
  const require = createRequire(path.join(process.cwd(), 'noop.js'));
  const { chromium } = require('playwright');
  const tests = [];
  for (const tool of (await readdir(path.join(ROOT, 'tools'))).sort()) {
    const dir = path.join(ROOT, 'tools', tool, 'tests', 'web');
    const files = await readdir(dir).catch(() => []);
    for (const f of files.filter((f) => f.endsWith('.test.mjs')).sort()) {
      tests.push({ tool, toolDir: path.join(ROOT, 'tools', tool), file: path.join(dir, f) });
    }
  }
  if (!tests.length) { console.log('No browser tests found.'); return; }
  const server = await serve();
  const baseUrl = `http://127.0.0.1:${server.address().port}${PREFIX}`;
  const browser = await chromium.launch();
  let failed = 0;
  try {
    for (const t of tests) {
      const name = `${t.tool}/${path.basename(t.file)}`;
      const started = Date.now();
      try {
        const mod = await import(pathToFileURL(t.file).href);
        await mod.default({ browser, baseUrl, toolDir: t.toolDir });
        console.log(`ok    ${name} (${((Date.now() - started) / 1000).toFixed(1)} s)`);
      } catch (error) {
        failed++;
        console.log(`FAIL  ${name}\n${error && error.stack ? error.stack : error}`);
      }
    }
  } finally {
    await browser.close();
    server.close();
  }
  if (failed) process.exit(1);
}

main().catch((error) => { console.error(error); process.exit(1); });
