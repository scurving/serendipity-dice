#!/usr/bin/env python3
"""Serendipity Dice — probabilistic perspective interrupt hook.

Claude Code UserPromptSubmit hook. Reads the user's prompt from stdin,
rolls dice, and optionally injects a directive that makes Claude briefly
channel a discovered perspective with a random posture.

Discovers perspectives from multiple sources:
  1. config/perspectives/*.yaml  (starter archetypes, always available)
  2. ~/.claude/agents/*.md       (user's custom agents)
  3. ~/.claude/skills/*/skill.md (user's installed skills)
  4. ~/.claude/plugins/cache/*/agents/*.md (plugin agents)

Uses structured JSON output (hookSpecificOutput.additionalContext) for
clean context injection.
"""

import json
import random
import re
import sys
import time
from pathlib import Path

import yaml

# Resolve config relative to script location:
# scripts/hook.py -> parent.parent / config
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
STATE_DIR = Path.home() / ".claude" / "dice"
STATE_FILE = STATE_DIR / ".serendipity-state.json"


def main():
    config_path = CONFIG_DIR / "serendipity.yaml"
    if not config_path.exists():
        return  # No config = silently disabled

    config = yaml.safe_load(config_path.read_text())
    if not config.get("enabled", False):
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    prompt = hook_input.get("prompt", "")

    # Skip short prompts
    min_length = config.get("min_prompt_length", 20)
    if len(prompt.strip()) < min_length:
        return

    # Skip slash commands
    if prompt.strip().startswith("/"):
        return

    # Cooldown check
    state = _load_state()
    cooldown = config.get("cooldown_messages", 4)
    if state.get("messages_since_fire", 0) < cooldown:
        state["messages_since_fire"] = state.get("messages_since_fire", 0) + 1
        _save_state(state)
        return

    # Roll: should we fire?
    fire_rate = config.get("fire_rate", 0.15)
    if random.random() > fire_rate:
        state["messages_since_fire"] = state.get("messages_since_fire", 0) + 1
        _save_state(state)
        return

    # Firing — reset cooldown
    state["messages_since_fire"] = 0
    state["last_fire"] = time.time()
    _save_state(state)

    # Pick posture
    postures = config.get("postures", {})
    if not postures:
        return

    posture_names = list(postures.keys())
    posture_weights = [postures[n].get("weight", 1) for n in posture_names]
    chosen_posture_name = random.choices(posture_names, weights=posture_weights, k=1)[0]
    chosen_posture = postures[chosen_posture_name]

    # Discover all perspectives and pick one
    perspectives = _discover_perspectives()
    if not perspectives:
        return

    session_context = _get_session_context(hook_input)
    perspective = _pick_perspective(perspectives, session_context)
    if not perspective:
        return

    # Build the directive
    directive = chosen_posture.get("directive", "Provide a different perspective.")
    p_name = perspective.get("name", perspective.get("id", "a perspective"))
    p_role = perspective.get("role", "")
    posture_label = chosen_posture_name.upper().replace("_", " ")

    # Build perspective context — layered
    context_parts = []

    caps = perspective.get("capabilities", [])
    if caps:
        context_parts.append(f"Capabilities: {', '.join(caps[:6])}")

    identity = perspective.get("identity", "")
    if identity:
        context_parts.append(f"Identity: {identity.strip()}")

    voice = perspective.get("voice", "")
    if voice:
        context_parts.append(f"Voice: {voice.strip()}")

    source = perspective.get("source", "")
    if source:
        context_parts.append(f"Source: {source}")

    perspective_block = "\n".join(context_parts)

    # Session context line
    session_line = ""
    if session_context and session_context != prompt:
        session_line = f"\nSession context: {session_context[:300]}\n"

    context = (
        f"<serendipity-dice>\n"
        f"SERENDIPITY DICE FIRED — This is a probabilistic interrupt, not a user request.\n"
        f"\n"
        f"Perspective: {p_name} ({p_role})\n"
        f"{perspective_block}\n"
        f"{session_line}\n"
        f"Posture: {posture_label}\n"
        f"Directive: {directive.strip()}\n"
        f"\n"
        f"INSTRUCTIONS: Before your main response, write a brief (2-3 sentence) insight\n"
        f"channeling {p_name}'s expertise and voice through the posture above.\n"
        f"Format it as:\n"
        f"\n"
        f"> **[{p_name} — {posture_label}]:** Your insight here.\n"
        f"\n"
        f"Then proceed with your normal response to the user's message.\n"
        f"Keep the serendipity insight sharp and specific to the session context.\n"
        f"Do NOT explain what serendipity dice is or why this appeared.\n"
        f"</serendipity-dice>"
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    """Load state from ~/.claude/dice/.serendipity-state.json."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"messages_since_fire": 0}


def _save_state(state: dict) -> None:
    """Write state, creating the directory if needed."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------

def _get_session_context(hook_input: dict) -> str:
    """Extract first + last user messages from transcript for perspective selection.

    Falls back to the current prompt if transcript is unavailable.
    """
    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path or not Path(transcript_path).exists():
        return hook_input.get("prompt", "")

    first_user_msg = ""
    last_user_msg = ""

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if evt.get("type") == "human":
                    content = evt.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        text_parts = [
                            b.get("text", "")
                            for b in content
                            if b.get("type") == "text"
                        ]
                        content = " ".join(text_parts)
                    if isinstance(content, str) and len(content.strip()) > 10:
                        if not first_user_msg:
                            first_user_msg = content.strip()[:500]
                        last_user_msg = content.strip()[:500]
    except Exception:
        pass

    parts = []
    if first_user_msg:
        parts.append(first_user_msg)
    if last_user_msg and last_user_msg != first_user_msg:
        parts.append(last_user_msg)
    return " ".join(parts) if parts else hook_input.get("prompt", "")


# ---------------------------------------------------------------------------
# Perspective discovery
# ---------------------------------------------------------------------------

def _discover_perspectives() -> list[dict]:
    """Scan all sources and return a unified list of perspectives.

    Priority order:
      1. config/perspectives/*.yaml  — starter archetypes (always available)
      2. ~/.claude/agents/*.md       — user's custom agents
      3. ~/.claude/skills/*/skill.md — user's installed skills (skip self)
      4. ~/.claude/plugins/cache/*/agents/*.md — plugin agents
    """
    perspectives: list[dict] = []

    # Source 1: Starter archetypes from config
    perspectives_dir = CONFIG_DIR / "perspectives"
    if perspectives_dir.is_dir():
        for yaml_path in sorted(perspectives_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_path.read_text())
                if not data:
                    continue
                perspectives.append({
                    "id": data.get("id", yaml_path.stem),
                    "name": data.get("name", yaml_path.stem),
                    "role": data.get("role", ""),
                    "source": "archetype",
                    "capabilities": data.get("capabilities", []),
                    "identity": data.get("identity", ""),
                    "voice": data.get("voice", ""),
                })
            except Exception:
                continue

    # Source 2: User's custom agents
    agents_dir = Path.home() / ".claude" / "agents"
    if agents_dir.is_dir():
        for md_path in sorted(agents_dir.glob("*.md")):
            parsed = _parse_md_frontmatter(md_path)
            if parsed:
                perspectives.append({
                    "id": md_path.stem,
                    "name": parsed.get("name", md_path.stem),
                    "role": parsed.get("description", ""),
                    "source": "agent",
                    "capabilities": [],
                    "identity": "",
                    "voice": "",
                })

    # Source 3: User's installed skills (skip self)
    skills_dir = Path.home() / ".claude" / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("*/skill.md")):
            # Skip the serendipity-dice skill itself
            if skill_md.parent.name == "serendipity-dice":
                continue
            parsed = _parse_md_frontmatter(skill_md)
            if parsed:
                perspectives.append({
                    "id": skill_md.parent.name,
                    "name": parsed.get("name", skill_md.parent.name),
                    "role": parsed.get("description", ""),
                    "source": "skill",
                    "capabilities": [],
                    "identity": "",
                    "voice": "",
                })

    # Source 4: Plugin agents
    plugins_cache = Path.home() / ".claude" / "plugins" / "cache"
    if plugins_cache.is_dir():
        for agent_md in sorted(plugins_cache.glob("*/agents/*.md")):
            parsed = _parse_md_frontmatter(agent_md)
            if parsed:
                perspectives.append({
                    "id": agent_md.stem,
                    "name": parsed.get("name", agent_md.stem),
                    "role": parsed.get("description", ""),
                    "source": "plugin",
                    "capabilities": [],
                    "identity": "",
                    "voice": "",
                })

    return perspectives


def _parse_md_frontmatter(md_path: Path) -> dict | None:
    """Parse YAML frontmatter from a markdown file.

    Expects frontmatter between --- markers at the top of the file.
    Returns dict with parsed fields, or None if no valid frontmatter.
    """
    try:
        text = md_path.read_text()
    except Exception:
        return None

    # Match frontmatter: starts with ---, ends with ---
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None

    try:
        data = yaml.safe_load(match.group(1))
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Perspective selection
# ---------------------------------------------------------------------------

def _pick_perspective(
    perspectives: list[dict], session_context: str
) -> dict | None:
    """Select a perspective with cross-domain serendipity.

    Strategy: score all perspectives against session context via keyword
    overlap, then skip the most obvious match and pick from positions 2-5.
    If nothing is relevant, fall back to random.
    """
    if not perspectives:
        return None

    if not session_context:
        return random.choice(perspectives)

    context_words = set(session_context.lower().split())

    scored: list[tuple[dict, int]] = []
    for p in perspectives:
        score = 0
        # Score from capabilities
        for cap in p.get("capabilities", []):
            cap_words = set(cap.lower().replace("-", " ").split())
            overlap = cap_words & context_words
            if overlap:
                score += len(overlap)

        # Score from role text
        role = p.get("role", "")
        if role:
            role_words = set(role.lower().replace("-", " ").split())
            overlap = role_words & context_words
            if overlap:
                score += len(overlap)

        # Score from identity text
        identity = p.get("identity", "")
        if identity:
            identity_words = set(identity.lower().replace("-", " ").split())
            overlap = identity_words & context_words
            if overlap:
                score += len(overlap)

        # Mild boost for cross-domain perspectives
        if p.get("source", "") != "archetype":
            score += 1

        scored.append((p, score))

    # Filter to perspectives with some relevance
    relevant = [(p, s) for p, s in scored if s > 0]

    if not relevant:
        return random.choice(perspectives)

    # Sort by score descending
    relevant.sort(key=lambda x: x[1], reverse=True)

    if len(relevant) <= 3:
        return random.choice(relevant)[0]

    # Skip the top-1 most obvious match, pick from positions 2-5
    interesting_slice = relevant[1:min(5, len(relevant))]
    return random.choice(interesting_slice)[0]


if __name__ == "__main__":
    main()
