#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "click>=8.1"]
# ///
"""CLI for fetching design references from https://styles.refero.design.

Lists curated design systems and downloads any single style as the four
artifacts shown on the website (DESIGN.md, Tailwind v4 CSS, plain CSS custom
properties, design tokens JSON) into a local reference folder so an agent can
use them as style guidance.
"""

from __future__ import annotations

import html
import json
import logging
import re
import sys
from pathlib import Path
from typing import Iterator

import click
import httpx

# Why module-level: a single base URL is referenced from multiple commands and
# centralising it makes the override trivial in tests or staging.
BASE_URL = "https://styles.refero.design"
PAGE_SIZE = 20

logger = logging.getLogger("refero")


# ---------- HTTP helpers ----------------------------------------------------


def _client() -> httpx.Client:
    # Why a shared User-Agent: the upstream API gates anonymous traffic loosely
    # but identifying the tool helps when debugging server logs.
    return httpx.Client(
        base_url=BASE_URL,
        timeout=30.0,
        headers={"User-Agent": "refero-cli/0.1 (+https://styles.refero.design)"},
        follow_redirects=True,
    )


def fetch_page(client: httpx.Client, page: int) -> dict:
    r = client.get("/api/styles", params={"page": page})
    r.raise_for_status()
    return r.json()


def search_styles(client: httpx.Client, query: str) -> list[dict]:
    """Server-side search by brand/keyword/URL.

    Why a separate endpoint: `/api/styles?q=` ignores the query and returns the
    paginated trending feed; `/api/styles/search` is the dedicated endpoint
    used by the website's search bar and returns ranked matches.
    """
    r = client.get("/api/styles/search", params={"q": query})
    r.raise_for_status()
    return r.json().get("styles") or []


def iter_styles(query: str | None = None, limit: int | None = None) -> Iterator[dict]:
    """Yield style summary dicts. Search hits are returned in one batch; the
    full feed paginates."""
    with _client() as client:
        if query:
            for s in search_styles(client, query)[:limit]:
                yield s
            return
        seen = 0
        page = 1
        while True:
            data = fetch_page(client, page)
            styles = data.get("styles") or []
            if not styles:
                return
            for s in styles:
                yield s
                seen += 1
                if limit is not None and seen >= limit:
                    return
            next_page = data.get("nextPage")
            if not next_page:
                return
            page = next_page


def fetch_style(client: httpx.Client, style_id: str) -> dict:
    r = client.get(f"/api/styles/{style_id}")
    r.raise_for_status()
    return r.json()["style"]


def fetch_design_md(client: httpx.Client, style_id: str) -> str:
    """Return the raw DESIGN.md content from the rendered style page.

    Why scrape: the JSON API exposes structured fields but not the curated
    markdown. The website server-renders DESIGN.md inside a single
    `<pre><code>...</code></pre>` block on `/style/<id>`, so we extract it
    directly. It is the canonical artifact and contains both the Tailwind v4
    and CSS Custom Properties code blocks we slice out below.
    """
    r = client.get(f"/style/{style_id}")
    r.raise_for_status()
    m = re.search(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", r.text, re.S)
    if not m:
        raise RuntimeError(f"DESIGN.md block not found on /style/{style_id}")
    return html.unescape(m.group(1))


# ---------- Markdown slicing -----------------------------------------------


def extract_fenced_block(markdown: str, heading_pattern: str) -> str:
    """Return the first fenced ```...``` block that follows a heading match.

    `heading_pattern` is a regex matched against a single line. The function
    finds the next fenced code block after that line (any language). If no
    block is found, returns an empty string.
    """
    h = re.search(heading_pattern, markdown, re.M)
    if not h:
        return ""
    fence = re.search(r"```[^\n]*\n(.*?)\n```", markdown[h.end():], re.S)
    return fence.group(1) if fence else ""


def design_tokens_from_style(style: dict) -> dict:
    """Build a Design Tokens JSON document from the API's `designSystem` block.

    Why we recompute this: the website's "Design Tokens" tab is rendered
    client-side from the same structured payload returned by `/api/styles/{id}`.
    Persisting the structured data verbatim gives the agent a stable,
    machine-readable companion to DESIGN.md.
    """
    full = style.get("fullResult") or {}
    return {
        "siteName": style.get("siteName"),
        "url": style.get("url"),
        "designSystem": full.get("designSystem"),
        "raw": full.get("raw"),
        "meta": full.get("meta"),
    }


# ---------- Slug + lookup ---------------------------------------------------


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "style"


def resolve_style_id(client: httpx.Client, identifier: str) -> dict:
    """Return a style summary dict for an id, URL, or fuzzy name match."""
    # UUID-shaped identifiers go straight to the detail endpoint.
    if re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", identifier):
        return fetch_style(client, identifier)

    needle = identifier.strip().lower()
    # Search-then-match: delegate ranking to the dedicated search endpoint and
    # only break ties locally.
    candidates = search_styles(client, needle)

    def score(s: dict) -> tuple[int, int]:
        site = (s.get("siteName") or "").lower()
        url = (s.get("url") or "").lower()
        if needle == site or needle == url:
            return (0, 0)
        if needle in site or needle in url:
            return (1, len(site))
        return (2, len(site))

    if not candidates:
        raise click.ClickException(f"No style matches {identifier!r}")
    candidates.sort(key=score)
    return candidates[0]


# ---------- CLI -------------------------------------------------------------


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """Browse and download styles from styles.refero.design."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    # Why: httpx logs every request at INFO level; that adds noise to a CLI
    # whose own logs already describe what's happening. Keep it WARNING unless
    # the user explicitly asked for verbose output.
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


@cli.command("list")
@click.option("--search", "-q", default=None, help="Filter by brand/keyword/URL.")
@click.option("--limit", "-n", type=int, default=None, help="Max results to print.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json", "ids"]),
    default="table",
    help="Output format.",
)
def list_cmd(search: str | None, limit: int | None, fmt: str) -> None:
    """List available styles, optionally filtered."""
    rows = list(iter_styles(query=search, limit=limit))
    if fmt == "json":
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if fmt == "ids":
        for s in rows:
            click.echo(s["id"])
        return
    # Default: terse table.
    name_w = max((len(s.get("siteName") or "") for s in rows), default=10)
    for s in rows:
        click.echo(
            f"{s['id']}  {s.get('siteName',''):<{name_w}}  {s.get('url','')}"
        )
    click.echo(f"\n{len(rows)} style(s).", err=True)


@cli.command("show")
@click.argument("identifier")
def show_cmd(identifier: str) -> None:
    """Print the JSON record for a single style (id, URL, or name)."""
    with _client() as client:
        style = resolve_style_id(client, identifier)
        # If we got a summary back, fetch the full record for completeness.
        if "fullResult" not in style:
            style = fetch_style(client, style["id"])
        click.echo(json.dumps(style, indent=2, ensure_ascii=False))


@cli.command("pull")
@click.argument("identifier")
@click.option(
    "--dest",
    "-d",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("reference"),
    show_default=True,
    help="Reference root directory; a per-style subfolder is created inside it.",
)
@click.option(
    "--slug",
    default=None,
    help="Override the slug (default: derived from siteName).",
)
@click.option(
    "--force/--no-force",
    default=False,
    help="Overwrite existing files.",
)
def pull_cmd(identifier: str, dest: Path, slug: str | None, force: bool) -> None:
    """Download a style as DESIGN.md + tailwind.css + styles.css + tokens.json.

    The four files match the four tabs on the website. They are written to
    `<dest>/<slug>/` so a skill can reference them at a stable path.
    """
    with _client() as client:
        summary = resolve_style_id(client, identifier)
        style = fetch_style(client, summary["id"])
        site_name = style.get("siteName") or summary.get("siteName") or "style"
        target_slug = slug or slugify(site_name)
        out_dir = dest / target_slug
        out_dir.mkdir(parents=True, exist_ok=True)

        design_md = fetch_design_md(client, style["id"])
        tailwind_css = extract_fenced_block(design_md, r"^###\s+Tailwind\s+v4\b.*$")
        css_props = extract_fenced_block(
            design_md, r"^###\s+CSS\s+Custom\s+Properties\b.*$"
        )
        tokens = design_tokens_from_style(style)

        files = {
            "DESIGN.md": design_md,
            "tailwind.css": tailwind_css,
            "styles.css": css_props,
            "tokens.json": json.dumps(tokens, indent=2, ensure_ascii=False),
            "metadata.json": json.dumps(
                {
                    "id": style["id"],
                    "siteName": site_name,
                    "url": style.get("url"),
                    "industry": style.get("industry"),
                    "colorScheme": style.get("colorScheme"),
                    "createdAt": style.get("createdAt"),
                    "source": f"{BASE_URL}/style/{style['id']}",
                },
                indent=2,
                ensure_ascii=False,
            ),
        }

        for name, content in files.items():
            path = out_dir / name
            if path.exists() and not force:
                logger.warning("skip %s (exists; use --force)", path)
                continue
            if not content:
                # Some styles may not include every fenced block; persist an
                # empty file so consumers see the gap explicitly rather than
                # silently get a missing path.
                logger.warning("%s is empty for %s", name, site_name)
            path.write_text(content if content.endswith("\n") else content + "\n")
            logger.info("wrote %s", path)

        click.echo(str(out_dir))


if __name__ == "__main__":
    cli()
