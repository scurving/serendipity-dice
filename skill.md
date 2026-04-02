---
name: dice
description: Roll the serendipity dice — get a fresh perspective on whatever you're working on. Probabilistic perspective interrupts from your own agents and skills.
---

# Serendipity Dice

## Normal Mode

**When:** `~/.claude/dice/.serendipity-state.json` exists.

1. Run `python3 <skill-dir>/scripts/roll.py`
2. Read the JSON output — it contains `name`, `posture`, `posture_directive`, and `identity`
3. Deliver a **2-3 sentence insight** that channels the rolled perspective through the rolled posture
   - Inhabit the perspective's voice and identity
   - Apply the posture's directive as your angle of attack
   - Ground it in whatever the user is currently working on
4. Format:

```
> **[{name} — {POSTURE}]:** Your insight here.
```

5. Then continue with whatever was happening before the roll

## First-Run Setup Wizard

**When:** `~/.claude/dice/.serendipity-state.json` does NOT exist. Ask one question at a time.

### Step 1 — Scan environment

Discover what's installed:
- Count agents: `~/.claude/agents/*.md`
- Count skills: `~/.claude/skills/*/skill.md`
- Starter perspectives: `<skill-dir>/config/perspectives/*.yaml` (always 5)

Report: `"Found X agents, Y skills, 5 starter perspectives."`

If zero agents and zero skills:
`"Using 5 starter perspectives. Add your own agents at ~/.claude/agents/ to personalize."`

### Step 2 — Show example roll

Run `python3 <skill-dir>/scripts/roll.py` and display the output so the user sees what a roll looks like before answering any questions.

### Step 3 — Ask Q1: Work context

> What's your primary work context?
> - Solo dev / Team lead / Researcher / Creative / Other

Store the answer. This adjusts posture weights:
- Researcher → boost `builds` weight
- Team lead → boost `decision_type` weight
- Other contexts → keep defaults from `config/serendipity.yaml`

### Step 4 — Ask Q2: Fire rate

> How often do you want fresh perspectives?
> - **Subtle** (10%, ~1 per 12 messages)
> - **Balanced** (15%, ~1 per 8 messages) — recommended
> - **Frequent** (25%, ~1 per 5 messages)
> - **Custom** (enter %)

### Step 5 — Generate config

Write `~/.claude/dice/config.yaml` with chosen fire rate and adjusted posture weights.

### Step 6 — Offer hook registration

Offer to add the `UserPromptSubmit` hook to `~/.claude/settings.json`. Show exactly what will be added. Do not add it without confirmation.

### Step 7 — First real roll

Run `python3 <skill-dir>/scripts/roll.py` with the new config and deliver the first real perspective using the Normal Mode format.

## Reference

- Config: `config/serendipity.yaml` — posture weights, fire rate presets, cooldown
- Perspectives: `config/perspectives/*.yaml` — starter perspective definitions
- State: `~/.claude/dice/.serendipity-state.json` — roll history, cooldown tracking
- Scripts: `scripts/roll.py` — all roll logic lives here
