---
name: refero-styles
description:
  Browse and download curated design references from styles.refero.design
  (DESIGN.md, Tailwind v4, plain CSS, design tokens) into a local reference
  folder so they can be used as design guidance for UI work. Use when the user
  asks to "use the X style", "fetch a refero design", "pull a design system from
  refero", "list refero styles", or wants to seed an agent with a brand's visual
  language.
---

# Refero Styles

A small CLI for [styles.refero.design](https://styles.refero.design) — a curated
library of design references where each entry exposes four artifacts:

- `DESIGN.md` — the canonical, agent-facing markdown brief (colors, typography,
  spacing, components, dos/don'ts, similar brands).
- `tailwind.css` — a Tailwind v4 `@theme { ... }` block.
- `styles.css` — plain `:root { ... }` CSS custom properties.
- `tokens.json` — structured design tokens (colors, raw extraction, full
  design-system JSON).

The CLI is `refero.py` and ships **inside this skill folder** (next to
`SKILL.md`). It is a single-file Python script using PEP 723 inline metadata, so
`uv` resolves dependencies on first run — no install step.

When this skill is installed at `~/.claude/skills/refero-styles/`, invoke the
CLI by its absolute path:

```bash
~/.claude/skills/refero-styles/refero.py list
~/.claude/skills/refero-styles/refero.py pull elevenlabs
```

If a `./refero.py` exists at the project root (development checkout), prefer
it over the installed copy.

## When to use this skill

Invoke it whenever the user wants to **bring a real-world brand's visual
language into the project as a reference**. Typical phrasings:

- "Pull the Linear design"
- "Add ElevenLabs as a style reference"
- "List trending refero styles"
- "Fetch the Mercury tokens"

Prefer this over generic web-fetching — `refero.py pull` produces a stable
layout
(`reference/<slug>/{DESIGN.md,tailwind.css,styles.css,tokens.json,metadata.json}`)
that is easy to point at later from CLAUDE.md, prompts, or component scaffolds.

## Commands

Run from the project root. Outputs are written under `reference/<slug>/` by
default.

### List styles

```bash
~/.claude/skills/refero-styles/refero.py list                  # first page of trending styles
~/.claude/skills/refero-styles/refero.py list -n 50            # cap rows
~/.claude/skills/refero-styles/refero.py list -q stripe        # search (brand / keyword / URL)
~/.claude/skills/refero-styles/refero.py list --format ids     # machine-readable: just UUIDs
~/.claude/skills/refero-styles/refero.py list --format json    # full JSON summaries
```

Output columns: `<id>  <siteName>  <url>`.

### Inspect one style

```bash
~/.claude/skills/refero-styles/refero.py show <id-or-url-or-name>
```

Prints the full JSON record for a single style, including
`fullResult.designSystem` (dos/don'ts, components, theme, layout, etc.). Use
this to peek at metadata before pulling.

### Pull a style into the reference folder

```bash
~/.claude/skills/refero-styles/refero.py pull <id-or-url-or-name>            # writes ./reference/<slug>/
~/.claude/skills/refero-styles/refero.py pull elevenlabs -d docs/styles      # custom destination root
~/.claude/skills/refero-styles/refero.py pull elevenlabs --slug eleven-labs  # custom slug
~/.claude/skills/refero-styles/refero.py pull elevenlabs --force             # overwrite existing files
```

Identifiers accepted, in order of preference:

1. UUID (e.g. `031056ff-7af1-46db-8daa-115f731c5d26`) — exact match, no network
   search.
2. URL (e.g. `https://stripe.com`) — passed to the search endpoint, top hit
   wins.
3. Brand or keyword (e.g. `linear`, `vercel`) — same search endpoint.

The command writes five files into `<dest>/<slug>/`:

| File            | Source                                                                   |
| --------------- | ------------------------------------------------------------------------ |
| `DESIGN.md`     | The `<pre><code>` block on `/style/<id>` — verbatim markdown.            |
| `tailwind.css`  | The `### Tailwind v4` fenced block extracted from `DESIGN.md`.           |
| `styles.css`    | The `### CSS Custom Properties` fenced block extracted from `DESIGN.md`. |
| `tokens.json`   | `fullResult.{designSystem,raw,meta}` from `/api/styles/<id>`.            |
| `metadata.json` | `id`, `siteName`, `url`, `industry`, `colorScheme`, source URL.          |

## How to use the pulled files

Once a style is pulled, point downstream work at it:

- **For Tailwind v4 projects:** copy `tailwind.css` into the project's main
  stylesheet and import Tailwind alongside it; the `@theme` block is
  plug-and-play.
- **For non-Tailwind projects:** use `styles.css` — same tokens, exposed as
  plain CSS variables under `:root`.
- **For agent prompting / design-decision context:** reference `DESIGN.md`. It
  is the curated brief the website is built around and is written to be read by
  an LLM.
- **For scripted pipelines (e.g. generating a component library, mapping tokens
  to JS):** parse `tokens.json`.

## Notes for the agent

- Always run from the project root so the relative `reference/` path is
  consistent.
- `refero.py` only reads from the public website; no auth or env vars are
  required.
- The list endpoint paginates 20-at-a-time; `--limit` stops early. The search
  endpoint returns a single ranked batch (no pagination needed).
- If `tailwind.css` or `styles.css` come out empty, that style's DESIGN.md is
  missing the corresponding fenced block — fall back to deriving values from
  `tokens.json`.
- Don't re-pull on every turn — the artifacts are stable. Re-pull only when the
  user explicitly asks for a refresh, in which case pass `--force`.
