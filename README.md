# Sparky Tools

Unofficial, community-made tools for people who use [SparkyFitness](https://github.com/CodeWithCJ/SparkyFitness), the self-hosted fitness and nutrition tracker.

Each tool solves one practical problem that SparkyFitness itself doesn't cover, such as bringing your history over from another app. The tools run on your own computer, and your data is never uploaded anywhere.

> [!NOTE]
> This repository is not part of the SparkyFitness project and is not affiliated with it, or with any app the tools read data from. If something in SparkyFitness itself is broken, report it to the [SparkyFitness repository](https://github.com/CodeWithCJ/SparkyFitness/issues).

## Tools

| Tool | What it does | Guide | Requires |
| --- | --- | --- | --- |
| [Hevy to SparkyFitness](tools/hevy-to-sparkyfitness/) | Converts a Hevy workout export (CSV, free or Pro accounts) into a file that SparkyFitness's Workout History importer reads, keeping sets, units and exercise types. | [Step-by-step guide](https://zeusal.github.io/sparky-tools/hevy-to-sparkyfitness/) | Python 3.8+ |

Each tool's folder has a `README.md` with its full documentation. Tools with a step-by-step guide also have a page on the [Sparky Tools website](https://zeusal.github.io/sparky-tools/).

## How the tools are built

- **Your data stays on your computer.** A tool reads the files you give it and writes new files next to them. It makes no network requests unless that is its whole purpose, and then its README says so.
- **Few requirements.** Tools use the Python standard library where possible, so there is nothing to install besides Python.
- **Safe by default.** A tool never overwrites the file you gave it, and it stops with a clear message instead of guessing when its input is ambiguous.
- **Documented and tested.** Every tool has a README, a changelog and automated tests that run on the oldest and newest supported Python versions.

## Using a tool

1. Open the tool's folder under [`tools/`](tools/) and read its README, or follow its guide on the website.
2. Download the tool's script from its folder (or from the guide page).
3. Run it as its README describes.

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
│       ├── site/            Optional step-by-step guide page
│       └── tests/           Automated tests and synthetic test files
├── site/                    The website's home page and shared styles
├── scripts/                 Repository helpers (run tests, build the website)
└── .github/                 CI, website deployment, issue and PR templates
```

## Contributing

Ideas, bug reports and new tools are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before you start, and please never attach your real exports to issues or pull requests: they contain personal health data.

To run every check locally:

```bash
python scripts/run_tests.py
python scripts/build_site.py --check
```

## License

The tools are free to use, modify and share for **non-commercial purposes**, under the same terms SparkyFitness uses. See [LICENSE](LICENSE).
