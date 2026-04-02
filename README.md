# Serendipity Dice

Fresh perspectives, on demand. A Claude Code skill that probabilistically interrupts your sessions with insights from different thinking angles — channeling your own agents and skills through structured postures.

## Quick Start

```bash
# Clone to your Claude Code skills directory
git clone https://github.com/scurving/serendipity-dice ~/.claude/skills/serendipity-dice

# First time? Just run /dice — the setup wizard handles the rest
```

## How It Works

The dice rolls two axes every time it fires:

**WHO** (Perspective) — the lens applied to your work:
- 5 starter perspectives ship out of the box: The Skeptic, The Builder, The Risk Analyst, The Systems Thinker, The End User
- Automatically discovers your installed agents (`~/.claude/agents/`) and skills (`~/.claude/skills/`)
- The more you've built, the more diverse the perspectives

**HOW** (Posture) — the angle of the interrupt:
- **CONTRARIAN** — challenges the direction, finds unexamined assumptions
- **DECISION TYPE** — one-way door or two-way door?
- **BUILDS** — where does this go 2-3 steps from now?
- **ROBUSTNESS** — what breaks when this ships?

## Two Modes

### Manual: `/dice`

Run `/dice` anytime you want a fresh angle. Pure random roll — no context needed.

### Automatic: Hook

Register the `UserPromptSubmit` hook and the dice fires probabilistically during your sessions. It reads your conversation context and picks perspectives that are *interestingly relevant* — not the most obvious match, but one that cross-pollinates.

## Setup

The first time you run `/dice`, a setup wizard walks you through:

1. **Environment scan** — discovers your agents, skills, and starter perspectives
2. **Example roll** — shows what a dice interrupt looks like
3. **Work context** — solo dev, team lead, researcher, or creative (tunes posture weights)
4. **Fire rate** — how often you want interrupts:
   - Subtle (10%) — ~1 per 12 messages
   - Balanced (15%) — ~1 per 8 messages
   - Frequent (25%) — ~1 per 5 messages
5. **Hook registration** — optionally adds the automatic hook to your settings

## Configuration

After setup, your config lives at `~/.claude/dice/config.yaml`. Edit directly to:

- Adjust `fire_rate` and `cooldown_messages`
- Change posture `weight` values (higher = more likely to roll)
- Edit posture `directive` text
- Set `enabled: false` to pause without uninstalling

## Adding Your Own Perspectives

Drop a YAML file in `config/perspectives/`:

```yaml
id: my-perspective
name: The Architect
role: System designer
capabilities:
  - api-design
  - data-modeling
  - separation-of-concerns
identity: >
  Thinks in interfaces and boundaries. Every system is a set of
  contracts between components. Good architecture makes the right
  thing easy and the wrong thing hard.
voice: >
  Style: Precise, boundary-focused.
  Phrases: "What's the contract here?", "Where's the seam?",
  "This coupling will cost you later."
```

Or just add agents to `~/.claude/agents/` — the dice discovers them automatically.

## Architecture

```
serendipity-dice/
  skill.md              # Skill definition (normal + setup wizard modes)
  config/
    serendipity.yaml    # Postures, fire rate, cooldown
    perspectives/       # Starter archetypes (YAML)
  scripts/
    hook.py             # UserPromptSubmit hook (automatic fires)
    roll.py             # Manual /dice rolls
```

**No dependencies** beyond PyYAML and a Claude Code installation.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI, desktop app, or IDE extension
- Python 3.10+
- PyYAML (`pip install pyyaml`)

## License

MIT
