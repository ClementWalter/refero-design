# refero-design

A Claude Code **skill** + CLI for downloading curated design references from
[styles.refero.design](https://styles.refero.design) into a local
`reference/<slug>/` folder for use as design guidance in agent-driven UI work.

This repo is itself a Claude Code skill: `SKILL.md` lives at the root next to
the `refero.py` CLI it wraps. Drop the folder into your Claude skills directory
and Claude will pick it up automatically.

## Install

### Recommended: `npx skills` ([vercel-labs/skills](https://github.com/vercel-labs/skills))

```bash
# user-scope (all projects)
npx skills add clementwalter/refero-design -a claude-code -g

# project-scope (current repo only)
npx skills add clementwalter/refero-design -a claude-code
```

`npx skills` is the open agent-skills CLI; `-a claude-code` targets Claude Code
specifically (it can also install for Cursor, Codex, Gemini CLI, etc.), `-g`
installs to `~/.claude/skills/` instead of `./.claude/skills/`. Add `-y` for
non-interactive mode (CI, etc.). Add `--list` first if you'd like to see what's
in a repo before installing.

### Manual (no extra tooling)

A Claude Code skill is just a folder with a `SKILL.md`, so `git clone` straight
into the skills directory works:

```bash
# user-scope
git clone https://github.com/clementwalter/refero-design ~/.claude/skills/refero-styles

# project-scope
git clone https://github.com/clementwalter/refero-design .claude/skills/refero-styles

# or symlink an existing checkout
ln -s "$PWD" ~/.claude/skills/refero-styles
```

### Requirements

- [`uv`](https://docs.astral.sh/uv/) — `refero.py` declares its deps with PEP
  723 inline metadata, so `uv` fetches `httpx` and `click` on first run. Nothing
  else to install.

## Quick start

```bash
# List trending styles (top of the homepage feed)
./refero.py list

# Search by brand / keyword / URL
./refero.py list -q linear

# Pull all four website tabs (DESIGN.md, Tailwind v4, CSS, Design Tokens)
./refero.py pull elevenlabs
# → reference/elevenlabs/{DESIGN.md, tailwind.css, styles.css, tokens.json, metadata.json}
```

`pull` accepts a UUID, a URL (`https://stripe.com`), or a brand name — the top
search hit wins for the latter two.

See `SKILL.md` for the full command surface and the conventions Claude follows
when invoking the CLI on your behalf.
