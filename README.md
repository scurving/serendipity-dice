# Serendipity Dice

A Claude Code skill that gives you fresh thinking angles — on demand or probabilistically during your sessions. It channels perspectives from your own agents, skills, and starter archetypes through dynamically-discovered postures.

Like a colleague who glances at your screen, sees what you're working on, and says the one thing you weren't thinking about.

## Quick Start

```bash
# Clone to your Claude Code skills directory
git clone https://github.com/scurving/serendipity-dice ~/.claude/skills/serendipity-dice

# Run /dice — the setup wizard handles the rest
```

## How It Works

Every roll combines two axes:

**Perspective** — who's weighing in:
- 5 starter archetypes: The Skeptic, The Builder, The Risk Analyst, The Systems Thinker, The End User
- Auto-discovers your installed agents (`~/.claude/agents/`) and skills (`~/.claude/skills/`)
- The more you've built in your Claude Code environment, the richer the pool

**Posture** — the angle they're bringing:
- 4 starter postures: Contrarian, Decision Type, Builds, Robustness
- Auto-discovers your thinking-mode skills (blast-radius, eval, compounding-impact, etc.)
- Add your own as YAML files in `config/postures/`

**Temperature** — how the dice reads the room:
- Early in a session → **Explorer** (cross-domain sparks)
- Deep in focused work → **Advisor** (relevant, pointed)
- Stuck on the same topic → **Catalyst** (nudge sideways)
- Computed per-roll from your session dynamics. No configuration needed.

## What It Feels Like

> **The Skeptic:** You're treating these config layers like they're independent, but they share a silent dependency on initialization order. Has anyone tested what happens when layer 3 loads before layer 1?

No system labels. No `[Name — POSTURE]:` formatting. Just the insight, in their voice, about your work.

## Two Modes

**`/dice`** — manual. Roll anytime you want a fresh angle. Always Explorer mode.

**Automatic hook** — register the `UserPromptSubmit` hook and the dice fires probabilistically. It reads your conversation, picks a perspective × posture combination that matches the moment, and delivers it as a brief aside before your normal response continues.

## Setup

First `/dice` triggers a setup wizard:

1. **Scan** — discovers your agents, skills, and available postures
2. **Demo** — shows an example roll so you see what you're getting
3. **Work context** — solo dev, team lead, researcher, or creative (adjusts posture weights)
4. **Frequency** — subtle (10%), balanced (15%), or frequent (25%)
5. **Hook** — optionally registers the automatic hook

## Extending

**Add a perspective** — drop a YAML in `config/perspectives/`:

```yaml
id: architect
name: The Architect
role: System designer
capabilities: [api-design, data-modeling, separation-of-concerns]
identity: >
  Thinks in interfaces and boundaries. Good architecture makes
  the right thing easy and the wrong thing hard.
voice: >
  Phrases: "What's the contract here?", "Where's the seam?"
```

**Add a posture** — drop a YAML in `config/postures/`:

```yaml
id: threat-model
label: THREAT MODEL
weight: 1
directive: >
  Who would attack this? What's the attack surface?
  Think like an adversary.
```

Or just add agents to `~/.claude/agents/` and skills to `~/.claude/skills/` — the dice discovers them automatically. Both axes grow with your environment.

## Configuration

After setup, edit `~/.claude/dice/config.yaml`:

- `fire_rate` — probability of firing per message (0.0–1.0)
- `cooldown_messages` — minimum messages between fires
- `perspective_exclude` — skip specific perspective IDs
- `enabled` — pause without uninstalling

## Architecture

```
serendipity-dice/
  skill.md                  # Skill definition + setup wizard
  config/
    serendipity.yaml        # Fire rate, cooldown, base posture weights
    perspectives/           # Starter archetypes (YAML)
    postures/               # Starter postures (YAML, extensible)
  scripts/
    hook.py                 # UserPromptSubmit hook (automatic + temperature)
    roll.py                 # Manual /dice
```

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Python 3.10+
- PyYAML (`pip install pyyaml`)

## License

MIT
