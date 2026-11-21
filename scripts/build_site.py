#!/usr/bin/env python3
"""Build the Sparky Tools website, or check the tool folders and the website.

    python scripts/build_site.py --out _site    # build into _site/
    python scripts/build_site.py --check        # validate only (used by CI)

The website is site/ (home page and shared styles) plus, for each tool with a
site/index.html, a page at /<tool-name>/ with the tool's script next to it so
the page can offer it for download. Placeholders filled in at build time:

    site/index.html             {{TOOLS}}  the list of tools from tool.json
    tools/<name>/site/*.html    {{VERSION}} {{SCRIPT}} {{TOOL_URL}} {{REPO_URL}}
"""
import argparse
import html
import json
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/zeusal/sparky-tools"
MANIFEST_KEYS = ("name", "summary", "script", "requires", "status")
STATUSES = ("stable", "beta", "deprecated")


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
            "version": version,
            "has_site": (folder / "site" / "index.html").is_file(),
        })
    if not tools:
        problems.add("tools", "no tools found")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for tool in tools:
        if f"(tools/{tool['slug']}/)" not in readme:
            problems.add("README.md", f"the tools table doesn't link tools/{tool['slug']}/")
    return tools


def tool_cards(tools):
    cards = []
    for tool in tools:
        m = tool["manifest"]
        source = f"{REPO_URL}/tree/main/tools/{tool['slug']}"
        links = []
        if tool["has_site"]:
            links.append(f'<a class="btn primary" href="{tool["slug"]}/">Step-by-step guide</a>')
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


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for name in ("href", "src"):
            if attrs.get(name):
                self.links.append(attrs[name])


def check_site(out, problems):
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
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                problems.add(f"site/{where}", f"broken link {link}")


MARKER = ".sparky-tools-build"


def build(out, problems):
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
        if not tool["has_site"]:
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
    check_site(out, problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="folder to build the website into")
    group.add_argument("--check", action="store_true", help="validate without keeping the build")
    args = parser.parse_args()
    problems = Problems()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            build(Path(tmp) / "_site", problems)
    else:
        build(args.out.resolve(), problems)
    if problems:
        sys.exit("Problems found:\n  " + "\n  ".join(problems))
    print("Website built." if args.out else "Tool folders and website are OK.")


if __name__ == "__main__":
    main()
