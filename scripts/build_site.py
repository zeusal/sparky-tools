#!/usr/bin/env python3
"""Build the Sparky Tools website, or check the tool folders and the website.

    python3 scripts/build_site.py --out _site                  # build into _site/
    python3 scripts/build_site.py --out _site --with-pyodide   # also add Pyodide
    python3 scripts/build_site.py --check                      # validate only (CI)

The website is site/ (home page and shared styles) plus, for each tool with a
site/ folder, its pages at /<tool-name>/ with the tool's script next to them,
so a page can offer it for download or run it in the browser. tool.json lists
the pages the home page links to, in order ("pages": [{"path", "label"}]). Placeholders
filled in at build time:

    site/index.html             {{TOOLS}} {{REPO_URL}}
    tools/<name>/site/**.html   {{VERSION}} {{SCRIPT}} {{TOOL_URL}} {{REPO_URL}}

Pages that run a tool in the browser load Pyodide from vendor/pyodide/. With
--with-pyodide, the release pinned in scripts/pyodide.json is downloaded (and
cached in .cache/pyodide/), its SHA-256 checked, and the files copied there.
Without it, the rest of the website builds and links into vendor/pyodide/ are
not checked.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/zeusal/sparky-tools"
MANIFEST_KEYS = ("name", "summary", "script", "requires", "status")
STATUSES = ("stable", "beta", "deprecated")
PYODIDE_DIR = "vendor/pyodide"
MARKER = ".sparky-tools-build"


class Problems(list):
    def add(self, where, message):
        self.append(f"{where}: {message}")


def load_tools(problems):
    tools = []
    for folder in sorted(p for p in (ROOT / "tools").iterdir() if p.is_dir()):
        where = f"tools/{folder.name}"
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", folder.name):
            problems.add(where, "folder names are lowercase words joined by hyphens")
        for required in ("tool.json", "README.md", "CHANGELOG.md"):
            if not (folder / required).is_file():
                problems.add(where, f"missing {required}")
        if not any((folder / "tests").glob("test_*.py")):
            problems.add(where, "missing tests/test_*.py")
        if not (folder / "tool.json").is_file():
            continue
        try:
            manifest = json.loads((folder / "tool.json").read_text(encoding="utf-8"))
        except ValueError as error:
            problems.add(f"{where}/tool.json", f"not valid JSON ({error})")
            continue
        missing = [k for k in MANIFEST_KEYS if not manifest.get(k)]
        if missing:
            problems.add(f"{where}/tool.json", "missing " + ", ".join(missing))
            continue
        if manifest["status"] not in STATUSES:
            problems.add(f"{where}/tool.json", "status must be one of " + ", ".join(STATUSES))
        pages = manifest.get("pages", [])
        if not isinstance(pages, list):
            problems.add(f"{where}/tool.json", "pages must be a list")
            pages = []
        for page in list(pages):
            if not (isinstance(page, dict) and isinstance(page.get("path"), str)
                    and page.get("label")):
                problems.add(f"{where}/tool.json", 'each page needs "path" and "label"')
                pages.remove(page)
            elif not (folder / "site" / page["path"] / "index.html").is_file():
                problems.add(f"{where}/tool.json", f"page site/{page['path']} has no index.html")
                pages.remove(page)
        script = folder / manifest["script"]
        version = None
        if not script.is_file():
            problems.add(where, f"script {manifest['script']} not found")
        else:
            m = re.search(r'^VERSION = "([^"]+)"', script.read_text(encoding="utf-8"), re.M)
            if not m:
                problems.add(f"{where}/{manifest['script']}", 'no VERSION = "x.y" line')
            else:
                version = m.group(1)
                changelog = folder / "CHANGELOG.md"
                if changelog.is_file() and not re.search(
                        r"^## \[?" + re.escape(version) + r"\]?\b",
                        changelog.read_text(encoding="utf-8"), re.M):
                    problems.add(f"{where}/CHANGELOG.md", f"no section for version {version}")
        tools.append({
            "slug": folder.name,
            "folder": folder,
            "manifest": manifest,
            "pages": pages,
            "version": version,
        })
    if not tools:
        problems.add("tools", "no tools found")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bug_form = (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(encoding="utf-8")
    for tool in tools:
        if f"(tools/{tool['slug']}/)" not in readme:
            problems.add("README.md", f"the tools table doesn't link tools/{tool['slug']}/")
        name = tool["manifest"].get("name", "")
        if name and not re.search(r"^\s*- " + re.escape(name) + r"\s*$", bug_form, re.M):
            problems.add(".github/ISSUE_TEMPLATE/bug_report.yml",
                         f"the Tool list doesn't include {name}")
    return tools


def tool_cards(tools):
    cards = []
    for tool in tools:
        m = tool["manifest"]
        source = f"{REPO_URL}/tree/main/tools/{tool['slug']}"
        links = []
        for i, page in enumerate(tool["pages"]):
            kind = "primary" if i == 0 else "secondary"
            links.append(f'<a class="btn {kind}" href="{tool["slug"]}/{page["path"]}">'
                         f'{html.escape(page["label"])}</a>')
        links.append(f'<a class="btn secondary" href="{source}">Documentation and code</a>')
        cards.append(
            '<article class="tool-card">\n'
            f'  <h3>{html.escape(m["name"])}</h3>\n'
            f'  <p>{html.escape(m["summary"])}</p>\n'
            f'  <p class="meta">Version {html.escape(tool["version"] or "?")} · '
            f'{html.escape(m["requires"])} · {html.escape(m["status"].capitalize())}</p>\n'
            f'  <div class="actions">{"".join(links)}</div>\n'
            '</article>'
        )
    return "\n".join(cards)


def render(text, values):
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def add_pyodide(out, cache):
    """Download the pinned Pyodide release once, check it, copy its files."""
    config = json.loads((ROOT / "scripts" / "pyodide.json").read_text(encoding="utf-8"))
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / config["url"].rsplit("/", 1)[1]
    if not archive.is_file():
        print(f"Downloading Pyodide {config['version']}...", flush=True)
        partial = archive.with_suffix(".part")
        with urllib.request.urlopen(config["url"], timeout=120) as response, \
                open(partial, "wb") as f:
            shutil.copyfileobj(response, f)
        partial.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != config["sha256"]:
        archive.unlink()
        sys.exit(f"Pyodide download has SHA-256 {digest}, expected {config['sha256']}")
    target = out / PYODIDE_DIR
    target.mkdir(parents=True)
    with tarfile.open(archive, "r:bz2") as tar:
        for name in config["files"]:
            member = tar.getmember(f"pyodide/{name}")
            if not member.isfile():
                sys.exit(f"Pyodide archive: pyodide/{name} is not a file")
            with tar.extractfile(member) as src, open(target / name, "wb") as dst:
                shutil.copyfileobj(src, dst)
    python = json.loads((target / "pyodide-lock.json").read_text(encoding="utf-8"))["info"]["python"]
    python_minor = ".".join(python.split(".")[:2])
    (target / "NOTICE.txt").write_text(
        f"Pyodide {config['version']} (https://pyodide.org), Mozilla Public License 2.0:\n"
        f"{config['license_url']}\n"
        f"Source code: https://github.com/pyodide/pyodide/tree/{config['version']}\n"
        "These are unmodified files from the official pyodide-core release.\n\n"
        f"pyodide.asm.wasm and python_stdlib.zip contain CPython {python}, Copyright (c) 2001\n"
        "Python Software Foundation; All Rights Reserved, under the PSF License Agreement,\n"
        "with the software it incorporates under the licenses listed at\n"
        f"https://docs.python.org/{python_minor}/license.html\n\n"
        "pyodide.asm.js and pyodide.asm.wasm also contain the Emscripten runtime (MIT):\n"
        "https://github.com/emscripten-core/emscripten/blob/main/LICENSE\n",
        encoding="utf-8")


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for name in ("href", "src", "data-pyodide", "data-script"):
            if attrs.get(name):
                self.links.append(attrs[name])


def check_site(out, problems, with_pyodide):
    vendored = (out / PYODIDE_DIR).resolve()
    for page in sorted(out.rglob("*.html")):
        where = str(page.relative_to(out))
        text = page.read_text(encoding="utf-8")
        leftover = re.findall(r"\{\{[A-Z_]+\}\}", text)
        if leftover:
            problems.add(f"site/{where}", "unfilled placeholders " + ", ".join(sorted(set(leftover))))
        parser = LinkCollector()
        parser.feed(text)
        for link in parser.links:
            if re.match(r"^[a-z]+:", link) or link.startswith("//"):
                continue
            path, _, fragment = link.partition("#")
            if not path:
                if fragment and fragment not in parser.ids:
                    problems.add(f"site/{where}", f"link to missing #{fragment}")
                continue
            target = (page.parent / path).resolve()
            if not with_pyodide and (target == vendored or vendored in target.parents):
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                problems.add(f"site/{where}", f"broken link {link}")


def build(out, problems, with_pyodide, cache):
    tools = load_tools(problems)
    if out.exists():
        # Only ever delete a folder this script built, never the repository or
        # some other folder passed by mistake.
        if not (out / MARKER).is_file() and any(out.iterdir()):
            sys.exit(f"{out} exists and wasn't built by this script; choose another --out")
        shutil.rmtree(out)
    shutil.copytree(ROOT / "site", out)
    (out / MARKER).write_text("Built by scripts/build_site.py\n", encoding="utf-8")
    home = out / "index.html"
    home.write_text(render(home.read_text(encoding="utf-8"),
                           {"TOOLS": tool_cards(tools), "REPO_URL": REPO_URL}),
                    encoding="utf-8")
    for tool in tools:
        if not (tool["folder"] / "site").is_dir():
            continue
        target = out / tool["slug"]
        shutil.copytree(tool["folder"] / "site", target)
        script = tool["manifest"]["script"]
        shutil.copy2(tool["folder"] / script, target / script)
        values = {
            "VERSION": tool["version"] or "",
            "SCRIPT": script,
            "TOOL_URL": f"{REPO_URL}/tree/main/tools/{tool['slug']}",
            "REPO_URL": REPO_URL,
        }
        for page in target.rglob("*.html"):
            page.write_text(render(page.read_text(encoding="utf-8"), values), encoding="utf-8")
    if with_pyodide:
        add_pyodide(out, cache)
    check_site(out, problems, with_pyodide)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="folder to build the website into")
    group.add_argument("--check", action="store_true", help="validate without keeping the build")
    parser.add_argument("--with-pyodide", action="store_true",
                        help="add Pyodide so in-browser tools work (downloads it once)")
    parser.add_argument("--pyodide-cache", type=Path, default=ROOT / ".cache" / "pyodide",
                        help="where to keep the downloaded Pyodide release")
    args = parser.parse_args()
    problems = Problems()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            build(Path(tmp) / "_site", problems, args.with_pyodide, args.pyodide_cache)
    else:
        build(args.out.resolve(), problems, args.with_pyodide, args.pyodide_cache)
    if problems:
        sys.exit("Problems found:\n  " + "\n  ".join(problems))
    print("Website built." if args.out else "Tool folders and website are OK.")


if __name__ == "__main__":
    main()
