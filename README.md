# Serendipity Dice

Fresh perspectives, on demand. A Claude Code skill that probabilistically interrupts your sessions with insights from different thinking angles — channeling your own agents and skills through dynamically-discovered postures.

## Quick Start

```bash
# Clone to your Claude Code skills directory
git clone https://github.com/scurving/serendipity-dice ~/.claude/skills/serendipity-dice

# First time? Just run /dice — the setup wizard handles the rest
```

## How It Works

The dice rolls two dynamic axes every time it fires:

**WHO** (Perspective) — the lens applied to your work:
- 5 starter perspectives ship out of the box: The Skeptic, The Builder, The Risk Analyst, The Systems Thinker, The End User
- Automatically discovers your installed agents (`~/.claude/agents/`) and skills (`~/.claude/skills/`)
- The more you've built, the more diverse the perspectives

**HOW** (Posture) — the angle of the interrupt:
- 4 starter postures: Contrarian, Decision Type, Builds, Robustness
- Automatically discovers your thinking-mode skills (like blast-radius, eval, compounding-impact) as additional postures
- Add your own postures as YAML files in `config/postures/`
- Both axes grow with your environment

**TEMPERATURE** — the dice reads the room:
- Early in a session → **Explorer** mode (wild cross-domain sparks)
- Deep in focused work → **Advisor** mode (relevant, pointed perspectives)
- Stuck on the same topic → **Catalyst** mode (nudge sideways)
- Temperature is computed per-roll from your session dynamics — no configuration needed

## Two Modes

### Manual: `/dice`

Run `/dice` anytime you want a fresh angle. Pure random roll — always Explorer mode.

### Automatic: Hook

Register the `UserPromptSubmit` hook and the dice fires probabilistically during your sessions. It reads your conversation context, computes temperature from session dynamics, and picks perspective × posture combinations that match the moment.

## What It Feels Like

The dice doesn't announce itself with system labels. It feels like a colleague tapping you on the shoulder:

> **The Skeptic:** You're treating these config layers like they're independent, but they share a silent dependency on initialization order. Has anyone tested what happens when layer 3 loads before layer 1?

Not:

> **[The Skeptic — CONTRARIAN]:** As a devil's advocate, I would suggest examining the initialization order of your configuration layers.

## Setup

The first time you run `/dice`, a setup wizard walks you through:

1. **Environment scan** — discovers your agents, skills, perspectives, and postures
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
- Set `perspective_exclude` to skip specific perspectives
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

Or add agents to `~/.claude/agents/` — the dice discovers them automatically.

## Adding Your Own Postures

Drop a YAML file in `config/postures/`:

```yaml
id: threat-model
label: THREAT MODEL
weight: 1
directive: >
  Who would attack this? What's the attack surface?
  What's the cheapest exploit? Think like an adversary.
```

Your thinking-mode skills are also auto-discovered as postures.

## Architecture

```
serendipity-dice/
  skill.md              # Skill definition (normal + setup wizard modes)
  config/
    serendipity.yaml    # Fire rate, cooldown, base posture weights
    perspectives/       # Starter perspectives (YAML)
    postures/           # Starter postures (YAML, extensible)
  scripts/
    hook.py             # UserPromptSubmit hook (automatic fires + temperature)
    roll.py             # Manual /dice rolls
```

**No dependencies** beyond PyYAML and a Claude Code installation.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI, desktop app, or IDE extension
- Python 3.10+
- PyYAML (`pip install pyyaml`)

## License

MIT
