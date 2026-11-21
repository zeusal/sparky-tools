# Contributing to Sparky Tools

Thanks for helping. This repository collects small, unofficial tools for [SparkyFitness](https://github.com/CodeWithCJ/SparkyFitness) users. Changes to SparkyFitness itself belong in the SparkyFitness repository, not here.

## Before you start

- **Bug in a tool:** open a [bug report](https://github.com/zeusal/sparky-tools/issues/new?template=bug_report.yml).
- **New tool or a bigger change:** open a [tool idea](https://github.com/zeusal/sparky-tools/issues/new?template=tool_idea.yml) first and wait for a reply, so nobody builds something that won't be merged.
- **Never share real personal data.** Exports from fitness apps contain health data. Use synthetic files in tests, issues and pull requests, or a few rows with the values changed.

## What a tool looks like

Each tool lives in its own folder under `tools/`, named in lowercase with hyphens (`tools/<tool-name>/`):

| Path | Required | Purpose |
| --- | --- | --- |
| `tool.json` | Yes | `name`, `summary`, `script`, `requires` and `status` (`stable`, `beta` or `deprecated`), and optionally `pages`: the tool's website pages, in order, as `{"path": "", "label": "..."}` (the first becomes the main button on the home page). The website lists tools from these files. |
| `README.md` | Yes | Full documentation (see below). |
| `CHANGELOG.md` | Yes | One section per version, newest first, headed `## <version>`. |
| `<script>.py` | Yes | The tool. It defines `VERSION = "x.y"` near the top. |
| `tests/` | Yes | `test_*.py` files run with `unittest`, plus synthetic test files. |
| `site/` | No | Website pages, published at `https://zeusal.github.io/sparky-tools/<tool-name>/`. For people who don't use the command line, the main page (`site/index.html`) should be an in-browser version (see [In-browser tools](#in-browser-tools)); a command-line guide can live next to it (for example `site/command-line/index.html`). |

A tool's README covers, in this order: what it does and why, requirements, quick start, every option, what the output contains and what it leaves out, troubleshooting, privacy, and how to run its tests.

A guide page can use `{{VERSION}}`, `{{SCRIPT}}`, `{{TOOL_URL}}` and `{{REPO_URL}}`: the build fills them in and copies the script next to the page, so `<a href="{{SCRIPT}}" download>` offers it for download.

Add the tool to the table in the root [README.md](README.md) and to the **Tool** list in [`.github/ISSUE_TEMPLATE/bug_report.yml`](.github/ISSUE_TEMPLATE/bug_report.yml). `python3 scripts/build_site.py --check` fails if either is missing.

## Conventions

- **English** for code, documentation, commit messages, issues and pull requests.
- **Python 3.8 or newer, standard library only.** If a tool can't work without a third-party package, open a tool idea first, so the tests and CI can be set up for it.
- **Local only.** A tool reads the files it is given and writes new ones. It never uploads data, never phones home, and never overwrites its input.
- **Fail clearly.** When the input is ambiguous or unsupported, stop with a message that says what to do, rather than guessing.
- **Versions.** Bump `VERSION` and add a `CHANGELOG.md` entry for every change users can notice. Use `x.y`: raise `y` for fixes and additions, `x` when the output or the options change in a way that breaks existing use.
- **Commits** follow [Conventional Commits](https://www.conventionalcommits.org/), with the tool's folder name as the scope, for example `fix(hevy-to-sparkyfitness): read Dutch month names`. Sign off your commits (`git commit -s`).

## In-browser tools

Most people who need these tools don't use the command line, so a tool should also run in the browser when it can. The page runs the tool's own Python script with [Pyodide](https://pyodide.org) (Python compiled to WebAssembly), so there is only one implementation and both give identical results. The user's files are read in the browser and never uploaded.

- Make it the tool's main page (`site/index.html`) and list it first in `pages` in `tool.json`. Write it for someone who has never used a terminal: no command-line options or Python in its text, and every step of the job on one page (getting the file, using the tool, and what to do with the result).
- Load Pyodide from `vendor/pyodide/pyodide.js` (relative to the website root) and the script from the tool's folder: the build copies both. The Pyodide release is pinned in `scripts/pyodide.json`, with its SHA-256.
- Never send the user's data anywhere, and don't load anything from other websites.
- Add browser tests in `tests/web/*.test.mjs` that use the page as a person would and compare its downloads with the command line's expected files.

Build the website with Pyodide and run the browser tests (needs Node.js and [Playwright](https://playwright.dev/)):

```bash
python3 scripts/build_site.py --out _site --with-pyodide
npm install --no-save playwright && npx playwright install chromium
node scripts/run_web_tests.mjs _site
```

## Tests

Every tool has automated tests. Golden tests compare the tool's output for a synthetic input with a stored expected file. When you change a tool's output on purpose, regenerate the expected file and check the difference line by line before committing it.

Run them locally (on Windows, use `py` instead of `python3`):

```bash
python3 scripts/run_tests.py            # every tool
python3 scripts/build_site.py --check   # tool folders, manifests and website
```

CI runs the tests on Python 3.8 (the oldest supported) and a current Python release (set in `.github/workflows/ci.yml`), on Linux and Windows, checks the website, and runs the browser tests. The website is published only after CI passes on `main`.

To preview the website:

```bash
python3 scripts/build_site.py --out _site --with-pyodide
python3 -m http.server --directory _site 8000
```

Then open <http://localhost:8000>. Without `--with-pyodide` the website builds faster, but in-browser tools can't start.

## Pull requests

Fill in the pull request template. Keep one tool per pull request when you can, and include the tests that show the change works.

## License

By contributing, you agree that your contribution is covered by the [LICENSE](LICENSE), including its contributor assignment clause.
