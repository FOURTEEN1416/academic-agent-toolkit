# Academic Figure Skill — Claude Code Installation

The Claude Code skill is at `fig-academic/`. Install via symlink:

```bash
ln -s $(pwd)/fig-academic ~/.claude/skills/fig-academic
```

Or copy:
```bash
cp -r fig-academic ~/.claude/skills/fig-academic
```

After installation, Claude Code auto-triggers on: "make a volcano plot", "画个热图",
"review this figure for Nature", etc.

The skill checks `fig-academic/assets/figures/<type>/` for production scripts before
generating any code. Add your own scripts there to extend figure type coverage.

Generated: 2026-09-23 10:50 UTC
