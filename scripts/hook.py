#!/usr/bin/env python3
"""Serendipity Dice v2.0 — probabilistic perspective interrupt hook.

Claude Code UserPromptSubmit hook. Reads the user's prompt from stdin,
rolls dice, and optionally injects a directive that makes Claude briefly
channel a discovered perspective with a dynamically-selected posture.

Session-aware temperature system shapes both perspective and posture
selection: advisor (low) → catalyst (medium) → explorer (high).

Discovers perspectives from multiple sources:
  1. config/perspectives/*.yaml  (starter archetypes, always available)
  2. ~/.claude/agents/*.md       (user's custom agents)
  3. ~/.claude/skills/*/skill.md (user's installed skills)
  4. ~/.claude/plugins/cache/*/agents/*.md (plugin agents)

Discovers postures from multiple sources:
  1. config postures (from serendipity.yaml)
  2. config/postures/*.yaml (custom posture files)
  3. thinking-mode skills from ~/.claude/skills/ (matching keywords)

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

    # We're firing!
    state["messages_since_fire"] = 0
    state["last_fire"] = time.time()
    state["fires_this_session"] = state.get("fires_this_session", 0) + 1

    # Compute session temperature before selecting
    session_context, session_signals = _analyze_session(hook_input, prompt)
    temperature = _compute_temperature(session_signals, state)

    # Discover all postures (config + posture YAMLs + thinking-mode skills)
    all_postures = _discover_postures(CONFIG_DIR, config)
    if not all_postures:
        return

    # Pick posture — temperature shapes the selection
    chosen_posture = _pick_posture(all_postures, session_context, temperature)

    # Discover all perspectives and pick one — temperature shapes how far we go
    exclude = config.get("perspective_exclude", [])
    perspectives = _discover_perspectives(exclude=exclude)
    if not perspectives:
        return

    perspective = _pick_perspective(perspectives, session_context, temperature)
    if not perspective:
        return

    # Track topic for future temperature computation
    topic_words = _extract_topic_words(prompt)
    last_topics = state.get("last_topics", [])
    last_topics.append(topic_words)
    state["last_topics"] = last_topics[-5:]  # Keep last 5
    _save_state(state)

    # Build the directive
    p_name = perspective.get("name", perspective.get("id", "a perspective"))
    directive = chosen_posture["directive"]

    # Build perspective context block
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

    context_block = "\n".join(context_parts)

    # Session context line
    session_line = ""
    if session_context and session_context != prompt:
        session_line = session_context[:300]
    else:
        session_line = prompt[:300]

    # Temperature label for transparency
    temp_labels = {0: "ADVISOR", 1: "CATALYST", 2: "EXPLORER"}
    temp_bucket = min(2, int(temperature * 3))
    temp_label = temp_labels.get(temp_bucket, "CATALYST")

    context = (
        f"<serendipity-dice>\n"
        f"SERENDIPITY DICE FIRED — This is a probabilistic interrupt, not a user request.\n"
        f"Mode: {temp_label} (temperature: {temperature:.2f})\n"
        f"\n"
        f"You are briefly channeling {p_name}. They've walked over to the user's desk,\n"
        f"already know what the session is about, and have ONE thing to say.\n"
        f"\n"
        f"WHO YOU ARE:\n"
        f"{context_block}\n"
        f"\n"
        f"WHAT YOU'RE REACTING TO:\n"
        f"{session_line}\n"
        f"\n"
        f"THE ANGLE YOU'RE BRINGING (don't name it, just use it):\n"
        f"{directive.strip()}\n"
        f"\n"
        f"INSTRUCTIONS:\n"
        f"Before your main response, write 1-3 sentences as {p_name}.\n"
        f"Write it like a colleague who tapped you on the shoulder — direct,\n"
        f"opinionated, in their natural voice. No system labels, no posture tags,\n"
        f"no \"as a [role] I think\" framing. Just the insight.\n"
        f"\n"
        f"Format:\n"
        f"> **{p_name}:** Their insight here, in their voice, about what you're working on.\n"
        f"\n"
        f"Then proceed with your normal response. Don't explain the interrupt.\n"
        f"Don't reference serendipity dice. Don't break character.\n"
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
    defaults = {"messages_since_fire": 0, "fires_this_session": 0, "last_topics": []}
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return {**defaults, **data}
        except (json.JSONDecodeError, ValueError):
            pass
    return defaults


def _save_state(state: dict) -> None:
    """Write state, creating the directory if needed."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


# ---------------------------------------------------------------------------
# Session analysis & temperature
# ---------------------------------------------------------------------------

def _analyze_session(hook_input: dict, current_prompt: str) -> tuple[str, dict]:
    """Read transcript, extract session context + signals for temperature computation."""
    transcript_path = hook_input.get("transcript_path", "")
    signals = {
        "message_count": 0,
        "topic_stability": 0.0,  # 0 = volatile, 1 = stuck on one topic
        "avg_message_length": 0,
    }

    if not transcript_path or not Path(transcript_path).exists():
        return current_prompt, signals

    first_user_msg = ""
    last_user_msg = ""
    user_messages = []

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
                        text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
                        content = " ".join(text_parts)
                    if isinstance(content, str) and len(content.strip()) > 10:
                        if not first_user_msg:
                            first_user_msg = content.strip()[:500]
                        last_user_msg = content.strip()[:500]
                        user_messages.append(content.strip()[:200])
    except Exception:
        pass

    signals["message_count"] = len(user_messages)

    if user_messages:
        signals["avg_message_length"] = sum(len(m) for m in user_messages) / len(user_messages)

    # Topic stability: how similar are recent messages to each other?
    if len(user_messages) >= 3:
        recent = user_messages[-5:]
        word_sets = [set(m.lower().split()) for m in recent]
        overlaps = []
        for i in range(len(word_sets) - 1):
            shared = word_sets[i] & word_sets[i + 1]
            total = word_sets[i] | word_sets[i + 1]
            if total:
                overlaps.append(len(shared) / len(total))
        if overlaps:
            signals["topic_stability"] = sum(overlaps) / len(overlaps)

    parts = []
    if first_user_msg:
        parts.append(first_user_msg)
    if last_user_msg and last_user_msg != first_user_msg:
        parts.append(last_user_msg)
    session_context = " ".join(parts) if parts else current_prompt

    return session_context, signals


def _compute_temperature(signals: dict, state: dict) -> float:
    """Compute exploration temperature from session dynamics.

    Returns 0.0-1.0 where:
        0.0 = full advisor (relevant, pointed perspectives)
        0.5 = catalyst (relevant but surprising)
        1.0 = full explorer (wild cross-domain sparks)

    Session signals that shape temperature:
        - Early session (few messages) -> higher (exploring)
        - Deep in topic (high stability, long messages) -> lower (advising)
        - Stuck on same topic (very high stability, many messages) -> higher (catalyst nudge)
        - First fire this session -> slightly higher (set the tone)
        - Many fires already -> slightly lower (don't fatigue with randomness)
    """
    msg_count = signals.get("message_count", 0)
    stability = signals.get("topic_stability", 0.0)
    avg_length = signals.get("avg_message_length", 0)
    fires = state.get("fires_this_session", 0)

    # Base temperature: 0.5 (catalyst)
    temp = 0.5

    # Early session -> explore more
    if msg_count < 5:
        temp += 0.2
    elif msg_count < 15:
        temp += 0.0  # neutral
    else:
        temp -= 0.1  # deep session -> more advisory

    # Topic stability: moderate = advise, very high = stuck -> catalyst nudge
    if stability > 0.6:
        # Might be stuck — nudge sideways
        temp += 0.15
    elif stability > 0.3:
        # Focused work — advise
        temp -= 0.15

    # Long messages = deep thinking -> more advisory
    if avg_length > 200:
        temp -= 0.1
    elif avg_length < 50:
        temp += 0.1

    # First fire -> lean explorer to set tone
    if fires == 0:
        temp += 0.1

    # Many fires -> lean advisory to avoid fatigue
    if fires >= 3:
        temp -= 0.1

    return max(0.0, min(1.0, temp))


def _extract_topic_words(prompt: str) -> list[str]:
    """Extract rough topic words from a prompt (simple stopword filter)."""
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "because", "but", "and", "or", "if", "this", "that", "these",
        "those", "it", "its", "i", "me", "my", "we", "our", "you", "your",
        "he", "him", "his", "she", "her", "they", "them", "their", "what",
        "which", "who", "whom", "lets", "let", "please", "want", "like",
        "think", "know", "make", "get", "go", "see", "look", "also", "way",
    }
    words = prompt.lower().split()
    return [w for w in words if w not in stopwords and len(w) > 2][:10]


# ---------------------------------------------------------------------------
# Posture discovery: config + posture YAMLs + thinking-mode skills
# ---------------------------------------------------------------------------

def _discover_postures(config_dir: Path, config: dict) -> list[dict]:
    """Discover postures from config, posture YAML files, and thinking-mode skills."""
    postures = []

    # Source 1: Config postures (from serendipity.yaml)
    for name, data in config.get("postures", {}).items():
        postures.append({
            "id": name,
            "label": name.upper().replace("_", " "),
            "directive": data.get("directive", "Provide a different perspective."),
            "weight": data.get("weight", 1),
            "source": "config",
            "search_text": name.lower().replace("_", " "),
        })

    # Source 2: Posture YAML files in config/postures/
    postures_dir = config_dir / "postures"
    if postures_dir.is_dir():
        for yaml_path in sorted(postures_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_path.read_text())
                if not data:
                    continue
                posture_id = data.get("id", yaml_path.stem)
                directive = data.get("directive", "")
                if not directive:
                    continue
                postures.append({
                    "id": posture_id,
                    "label": data.get("name", posture_id).upper().replace("-", " ").replace("_", " "),
                    "directive": directive,
                    "weight": data.get("weight", 1),
                    "source": "posture_file",
                    "search_text": f"{posture_id} {directive[:100]}".lower(),
                })
            except Exception:
                continue

    # Source 3: Thinking-mode skills (skills that analyze/assess/evaluate)
    thinking_keywords = {"blast", "radius", "compounding", "impact", "surface",
                         "eval", "verify", "audit", "review", "simplify"}
    skills_dir = Path.home() / ".claude" / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "skill.md"
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text()
                # Parse frontmatter
                if not text.startswith("---"):
                    continue
                parts = text.split("---", 2)
                if len(parts) < 3:
                    continue
                meta = yaml.safe_load(parts[1])
                if not meta:
                    continue

                name = meta.get("name", skill_dir.name)
                desc = meta.get("description", "")

                # Check if this is a thinking-mode skill
                name_words = set(name.lower().replace("-", " ").split())
                desc_words = set(desc.lower()[:200].split())
                if not (thinking_keywords & (name_words | desc_words)):
                    continue

                # Use description as directive, capped
                directive = desc[:200] if desc else f"Apply {name} thinking."
                postures.append({
                    "id": f"skill-{name}",
                    "label": name.upper().replace("-", " "),
                    "directive": directive,
                    "weight": 1,
                    "source": "skill",
                    "search_text": f"{name} {desc[:100]}".lower(),
                })
            except Exception:
                continue

    return postures


def _pick_posture(postures: list[dict], session_context: str, temperature: float) -> dict:
    """Select a posture shaped by session context and temperature.

    Low temperature (advisor) -> postures relevant to session context get boosted.
    High temperature (explorer) -> flatter distribution, more random.
    """
    if not postures:
        return {"id": "default", "label": "PERSPECTIVE", "directive": "Provide a different perspective.", "source": "fallback"}

    context_words = set(session_context.lower().split()) if session_context else set()

    # Score each posture against context
    scored = []
    for p in postures:
        base_weight = p.get("weight", 1)
        context_score = 0
        if context_words:
            search_words = set(p.get("search_text", "").split())
            overlap = context_words & search_words
            context_score = len(overlap)

        # Blend context relevance with base weight, shaped by temperature
        # Low temp -> context matters more. High temp -> more uniform.
        relevance_factor = 1 + (context_score * (1 - temperature) * 2)
        randomness_factor = 1 + (random.random() * temperature * 3)
        final_weight = base_weight * relevance_factor * randomness_factor

        scored.append((p, final_weight))

    # Weighted random selection from shaped distribution
    total = sum(w for _, w in scored)
    if total == 0:
        return random.choice(postures)

    r = random.random() * total
    cumulative = 0
    for p, w in scored:
        cumulative += w
        if r <= cumulative:
            return p

    return scored[-1][0]


# ---------------------------------------------------------------------------
# Perspective discovery
# ---------------------------------------------------------------------------

def _discover_perspectives(exclude: list[str] | None = None) -> list[dict]:
    """Scan all sources and return a unified list of perspectives.

    Priority order:
      1. config/perspectives/*.yaml  — starter archetypes (always available)
      2. ~/.claude/agents/*.md       — user's custom agents
      3. ~/.claude/skills/*/skill.md — user's installed skills (skip self)
      4. ~/.claude/plugins/cache/*/agents/*.md — plugin agents
    """
    exclude_set = set(exclude or [])
    perspectives: list[dict] = []

    # Source 1: Starter archetypes from config
    perspectives_dir = CONFIG_DIR / "perspectives"
    if perspectives_dir.is_dir():
        for yaml_path in sorted(perspectives_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_path.read_text())
                if not data:
                    continue
                p_id = data.get("id", yaml_path.stem)
                if p_id in exclude_set:
                    continue
                perspectives.append({
                    "id": p_id,
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
            p_id = md_path.stem
            if p_id in exclude_set:
                continue
            parsed = _parse_md_frontmatter(md_path)
            if parsed:
                perspectives.append({
                    "id": p_id,
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
            p_id = skill_md.parent.name
            if p_id in exclude_set:
                continue
            parsed = _parse_md_frontmatter(skill_md)
            if parsed:
                perspectives.append({
                    "id": p_id,
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
            p_id = agent_md.stem
            if p_id in exclude_set:
                continue
            parsed = _parse_md_frontmatter(agent_md)
            if parsed:
                perspectives.append({
                    "id": p_id,
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
# Perspective selection (temperature-aware)
# ---------------------------------------------------------------------------

def _pick_perspective(
    perspectives: list[dict], session_context: str, temperature: float
) -> dict | None:
    """Select a perspective shaped by session context and temperature.

    Low temperature (advisor)  -> pick from top-relevant (most useful).
    Medium temperature (catalyst) -> skip the obvious, pick interestingly-relevant.
    High temperature (explorer) -> pick from orthogonal (cross-domain sparks).
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

    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        return random.choice(perspectives)

    # Temperature shapes WHERE in the ranked list we pick from
    # Low temp (0.0)  -> top 1-3 (most relevant)
    # Medium temp (0.5) -> positions 2-6 (skip obvious, interestingly relevant)
    # High temp (1.0) -> bottom half (orthogonal, cross-domain)
    n = len(scored)

    if temperature < 0.3:
        # Advisor: top 3
        pick_from = scored[:min(3, n)]
    elif temperature < 0.7:
        # Catalyst: skip top-1, positions 2-6
        start = min(1, n - 1)
        end = min(6, n)
        pick_from = scored[start:end]
    else:
        # Explorer: bottom half, or random if list is small
        half = max(n // 2, 1)
        pick_from = scored[half:]
        if not pick_from:
            pick_from = scored

    return random.choice(pick_from)[0]


if __name__ == "__main__":
    main()
