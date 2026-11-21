# Sparky Tools

Unofficial, community-made tools for people who use [SparkyFitness](https://github.com/CodeWithCJ/SparkyFitness), the self-hosted fitness and nutrition tracker.

Each tool solves one practical problem that SparkyFitness itself doesn't cover, such as bringing your history over from another app. The tools run on your own computer, and your data is never uploaded anywhere.

> [!NOTE]
> This repository is not part of the SparkyFitness project and is not affiliated with it, or with any app the tools read data from. If something in SparkyFitness itself is broken, report it to the [SparkyFitness repository](https://github.com/CodeWithCJ/SparkyFitness/issues).

## Tools

| Tool | What it does | Use it | Requires |
| --- | --- | --- | --- |
| [Hevy to SparkyFitness](tools/hevy-to-sparkyfitness/) | Moves your Hevy workout history (free or Pro accounts) into SparkyFitness, keeping sets, units and exercise types. | [Easy version, in your browser](https://zeusal.github.io/sparky-tools/hevy-to-sparkyfitness/) · [command-line version](https://zeusal.github.io/sparky-tools/hevy-to-sparkyfitness/command-line/) | A web browser (or Python 3.8+ for the command line) |

Each tool's folder has a `README.md` with its full documentation. Tools with a guide or an in-browser version also have pages on the [Sparky Tools website](https://zeusal.github.io/sparky-tools/).

## How the tools are built

- **Your data stays on your device.** A tool reads the files you give it and writes new files next to them. It makes no network requests unless that is its whole purpose, and then its README says so. In-browser versions run the same script inside your browser, so nothing is uploaded there either.
- **Few requirements.** Tools use the Python standard library where possible, so there is nothing to install besides Python, and some can run in the browser with nothing installed at all.
- **Safe by default.** A tool never overwrites the file you gave it, and it stops with a clear message instead of guessing when its input is ambiguous.
- **Documented and tested.** Every tool has a README, a changelog and automated tests that run on Python 3.8 (the oldest supported) and a current Python release, on Linux and Windows.

## Using a tool

1. If the tool has an in-browser version, open it on the [website](https://zeusal.github.io/sparky-tools/) and follow the page.
2. Otherwise, open the tool's folder under [`tools/`](tools/) and read its README, or follow its guide on the website.
3. Download the tool's script from its guide page, or open it in the tool's folder and press *Download raw file*, then run it as its README describes.

Always keep a copy of your original export. If a tool's output doesn't look right, don't import it; [open an issue](https://github.com/zeusal/sparky-tools/issues/new/choose) instead.

## Repository layout

```text
.
├── tools/                   One folder per tool
│   └── <tool-name>/
│       ├── tool.json        Name, summary and entry script, used by the website
│       ├── README.md        The tool's documentation
│       ├── CHANGELOG.md     What changed in each version
│       ├── <script>.py      The tool itself
│       ├── site/            Optional website pages: a guide, an in-browser version
│       └── tests/           Automated tests and synthetic test files (tests/web/ for pages)
├── site/                    The website's home page and shared styles
├── scripts/                 Repository helpers (run tests, build the website, pinned Pyodide)
└── .github/                 CI, website deployment, issue and PR templates
```

## Contributing

Ideas, bug reports and new tools are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before you start, and please never attach your real exports to issues or pull requests: they contain personal health data.

To run every check locally (on Windows, use `py` instead of `python3`):

```bash
python3 scripts/run_tests.py
python3 scripts/build_site.py --check
```

The in-browser tools also have browser tests; see [CONTRIBUTING.md](CONTRIBUTING.md#in-browser-tools).

## License

The tools are free to use, modify and share for **non-commercial purposes**, under the same terms SparkyFitness uses. See [LICENSE](LICENSE).
