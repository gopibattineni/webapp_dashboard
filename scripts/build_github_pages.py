"""Build static dashboard into /docs for GitHub Pages."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "app" / "static"
DOCS = REPO_ROOT / "docs"
ASSETS = DOCS / "assets"
DATA = DOCS / "data"

# GitHub project site: https://<user>.github.io/<repo>/
GITHUB_PAGES_BASE = "/webapp_dashboard/"
GITHUB_REPO = "https://github.com/gopibattineni/webapp_dashboard"

COPY_FILES = [
    "styles.css",
    "dashboard.css",
    "utils.js",
    "dashboard-charts.js",
    "dashboard.js",
    "lero-logo.png",
    "bds-logo.png",
]


def run_export() -> None:
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "export_dashboard_data.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def patch_dashboard_html(html: str) -> str:
    html = html.replace("/static/", f"{GITHUB_PAGES_BASE}assets/")
    html = html.replace('href="/"', f'href="{GITHUB_REPO}"')
    html = html.replace(
        'href="/dashboard"',
        f'href="{GITHUB_PAGES_BASE}"',
    )
    html = re.sub(
        r'<body([^>]*)>',
        rf'<body\1 data-static="true">',
        html,
        count=1,
    )
    if 'github-pages-base' not in html:
        html = html.replace(
            "<head>",
            f'<head>\n  <meta name="github-pages-base" content="{GITHUB_PAGES_BASE}" />',
            1,
        )
    # Hide local-only experiment link nav item on static site
    html = html.replace(
        f'<a href="{GITHUB_REPO}" class="nav-link">Run Experiment</a>',
        f'<a href="{GITHUB_REPO}" class="nav-link" target="_blank" rel="noopener">Web App (local)</a>',
    )
    html = html.replace(
        '<a href="/dashboard" class="nav-link active">Results Dashboard</a>',
        f'<a href="{GITHUB_PAGES_BASE}" class="nav-link active">Results Dashboard</a>',
    )
    return html


def build() -> Path:
    run_export()

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    ASSETS.mkdir()
    DATA.mkdir()

    audit_src = STATIC / "data" / "audit"
    for name in ["datasets.json", "overview.json"]:
        shutil.copy2(audit_src / name, DATA / name)
    shutil.copytree(audit_src / "datasets", DATA / "datasets")

    for fname in COPY_FILES:
        src = STATIC / fname
        if not src.is_file():
            raise FileNotFoundError(f"Missing static asset: {src}")
        shutil.copy2(src, ASSETS / fname)

    html = (STATIC / "dashboard.html").read_text(encoding="utf-8")
    (DOCS / "index.html").write_text(patch_dashboard_html(html), encoding="utf-8")

    print(f"GitHub Pages site built at {DOCS}")
    print(f"Live URL (after deploy): https://gopibattineni.github.io{GITHUB_PAGES_BASE}")
    return DOCS


if __name__ == "__main__":
    build()
