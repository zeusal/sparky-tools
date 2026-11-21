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
| `tool.json` | Yes | `name`, `summary`, `script`, `requires` and `status`. The website lists tools from these files. |
| `README.md` | Yes | Full documentation (see below). |
| `CHANGELOG.md` | Yes | One section per version, newest first, headed `## <version>`. |
| `<script>.py` | Yes | The tool. It defines `VERSION = "x.y"` near the top. |
| `tests/` | Yes | `test_*.py` files run with `unittest`, plus synthetic test files. |
| `site/index.html` | No | A step-by-step guide page, published at `https://zeusal.github.io/sparky-tools/<tool-name>/`. |

A tool's README covers, in this order: what it does and why, requirements, quick start, every option, what the output contains and what it leaves out, troubleshooting, privacy, and how to run its tests.

Add the tool to the table in the root [README.md](README.md). `python scripts/build_site.py --check` fails if a tool is missing from it.

## Conventions

- **English** for code, documentation, commit messages, issues and pull requests.
- **Python 3.8 or newer**, standard library only, unless the tool can't work without a dependency. If it needs one, say so in its README and in `tool.json`.
- **Local only.** A tool reads the files it is given and writes new ones. It never uploads data, never phones home, and never overwrites its input.
- **Fail clearly.** When the input is ambiguous or unsupported, stop with a message that says what to do, rather than guessing.
- **Versions.** Bump `VERSION` and add a `CHANGELOG.md` entry for every change users can notice. Use `x.y`: raise `y` for fixes and additions, `x` when the output or the options change in a way that breaks existing use.
- **Commits** follow [Conventional Commits](https://www.conventionalcommits.org/), with the tool's folder name as the scope, for example `fix(hevy-to-sparkyfitness): read Dutch month names`. Sign off your commits (`git commit -s`).

## Tests

Every tool has automated tests. Golden tests compare the tool's output for a synthetic input with a stored expected file. When you change a tool's output on purpose, regenerate the expected file and check the difference line by line before committing it.

Run them locally:

```bash
python scripts/run_tests.py            # every tool
python scripts/build_site.py --check   # tool folders, manifests and website
```

CI runs the tests on Python 3.8 and on the newest Python, and checks the website.

To preview the website:

```bash
python scripts/build_site.py --out _site
python -m http.server --directory _site 8000
```

Then open <http://localhost:8000>.

## Pull requests

Fill in the pull request template. Keep one tool per pull request when you can, and include the tests that show the change works.

## License

By contributing, you agree that your contribution is covered by the [LICENSE](LICENSE), including its contributor assignment clause.
