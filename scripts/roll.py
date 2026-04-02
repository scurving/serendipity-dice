#!/usr/bin/env python3
"""Roll the serendipity dice — manual /dice invocation.

Picks a random perspective from all discovered sources and a weighted-random
posture from config/serendipity.yaml. Pure random — no context-awareness.
"""

import random
import sys
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CLAUDE_DIR = Path.home() / ".claude"


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file (between --- markers)."""
    try:
        text = path.read_text()
    except Exception:
        return {}
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break
    if end < 0:
        return {}
    try:
        return yaml.safe_load("\n".join(lines[1:end])) or {}
    except Exception:
        return {}


def _extract_body_section(text: str, heading: str) -> str:
    """Extract the first markdown section matching ## heading (case-insensitive)."""
    lines = text.split("\n")
    capture = False
    result = []
    target = heading.lower()
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(f"## {target}") or stripped.lower().startswith(f"### {target}"):
            capture = True
            continue
        if capture and (stripped.startswith("## ") or stripped.startswith("### ")):
            break
        if capture:
            result.append(line)
    return "\n".join(result).strip()[:600] if result else ""


# -- Perspective discovery from 4 sources --


def _discover_archetypes() -> list[dict]:
    """Source 1: config/perspectives/*.yaml — starter archetypes shipped with the repo."""
    perspectives_dir = CONFIG_DIR / "perspectives"
    if not perspectives_dir.is_dir():
        return []
    results = []
    for p in sorted(perspectives_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text())
            if not data:
                continue
            results.append({
                "id": data.get("id", p.stem),
                "name": data.get("name", p.stem),
                "role": data.get("role", ""),
                "source": "archetype",
                "capabilities": data.get("capabilities", []),
                "identity": data.get("identity", "").strip(),
                "voice": data.get("voice", "").strip(),
            })
        except Exception:
            continue
    return results


def _discover_user_agents() -> list[dict]:
    """Source 2: ~/.claude/agents/*.md — user-defined agents with YAML frontmatter."""
    agents_dir = CLAUDE_DIR / "agents"
    if not agents_dir.is_dir():
        return []
    results = []
    for p in sorted(agents_dir.glob("*.md")):
        fm = _parse_frontmatter(p)
        if not fm:
            continue
        try:
            text = p.read_text()
        except Exception:
            text = ""
        name = fm.get("name", p.stem)
        desc = fm.get("description", "")
        # Truncate long descriptions to a usable summary
        if isinstance(desc, str) and len(desc) > 200:
            desc = desc[:200].rsplit(" ", 1)[0] + "..."
        identity = _extract_body_section(text, "identity") if text else ""
        voice = _extract_body_section(text, "voice") or _extract_body_section(text, "personality")
        results.append({
            "id": p.stem,
            "name": name,
            "role": desc if isinstance(desc, str) else str(desc),
            "source": "agent",
            "capabilities": [],
            "identity": identity,
            "voice": voice,
        })
    return results


def _discover_user_skills() -> list[dict]:
    """Source 3: ~/.claude/skills/*/skill.md — user skills with YAML frontmatter.

    Skips serendipity-dice itself to avoid self-reference.
    """
    skills_dir = CLAUDE_DIR / "skills"
    if not skills_dir.is_dir():
        return []
    results = []
    for skill_md in sorted(skills_dir.glob("*/skill.md")):
        skill_id = skill_md.parent.name
        if skill_id == "serendipity-dice":
            continue
        fm = _parse_frontmatter(skill_md)
        if not fm:
            continue
        name = fm.get("name", skill_id)
        desc = fm.get("description", "")
        if isinstance(desc, str) and len(desc) > 200:
            desc = desc[:200].rsplit(" ", 1)[0] + "..."
        results.append({
            "id": skill_id,
            "name": name,
            "role": desc if isinstance(desc, str) else str(desc),
            "source": "skill",
            "capabilities": [],
            "identity": "",
            "voice": "",
        })
    return results


def _discover_plugin_agents() -> list[dict]:
    """Source 4: ~/.claude/plugins/cache/*/agents/*.md — plugin agents."""
    plugins_cache = CLAUDE_DIR / "plugins" / "cache"
    if not plugins_cache.is_dir():
        return []
    results = []
    # Plugins may nest: cache/<plugin>/<version>/agents/ or cache/<plugin>/agents/
    for md in sorted(plugins_cache.rglob("agents/*.md")):
        fm = _parse_frontmatter(md)
        if not fm:
            continue
        try:
            text = md.read_text()
        except Exception:
            text = ""
        name = fm.get("name", md.stem)
        desc = fm.get("description", "")
        if isinstance(desc, str) and len(desc) > 200:
            desc = desc[:200].rsplit(" ", 1)[0] + "..."
        identity = _extract_body_section(text, "identity") if text else ""
        voice = _extract_body_section(text, "voice") or _extract_body_section(text, "personality")
        results.append({
            "id": md.stem,
            "name": name,
            "role": desc if isinstance(desc, str) else str(desc),
            "source": "plugin",
            "capabilities": [],
            "identity": identity,
            "voice": voice,
        })
    return results


def discover_all_perspectives() -> list[dict]:
    """Gather perspectives from all 4 sources. Deduplicate by id (first wins)."""
    seen = set()
    all_perspectives = []
    for fn in (_discover_archetypes, _discover_user_agents, _discover_user_skills, _discover_plugin_agents):
        for p in fn():
            if p["id"] not in seen:
                seen.add(p["id"])
                all_perspectives.append(p)
    return all_perspectives


def main():
    # Load postures from config
    config_path = CONFIG_DIR / "serendipity.yaml"
    if not config_path.exists():
        print(f"No serendipity config found at {config_path}", file=sys.stderr)
        sys.exit(1)

    config = yaml.safe_load(config_path.read_text())

    postures = config.get("postures", {})
    if not postures:
        print("No postures defined in config", file=sys.stderr)
        sys.exit(1)

    # Roll posture (weighted)
    names = list(postures.keys())
    weights = [postures[n].get("weight", 1) for n in names]
    chosen_name = random.choices(names, weights=weights, k=1)[0]
    chosen_posture = postures[chosen_name]

    # Discover and roll perspective (uniform)
    perspectives = discover_all_perspectives()
    if not perspectives:
        print("No perspectives found in any source", file=sys.stderr)
        sys.exit(1)

    perspective = random.choice(perspectives)

    # Format output — only print lines with content
    posture_label = chosen_name.upper().replace("_", " ")
    directive = chosen_posture.get("directive", "Provide a different perspective.").strip()

    print(f"AGENT: {perspective['name']} ({perspective['role']})" if perspective.get("role")
          else f"AGENT: {perspective['name']}")
    print(f"SOURCE: {perspective['source']}")
    if perspective.get("capabilities"):
        print(f"CAPABILITIES: {', '.join(perspective['capabilities'][:6])}")
    if perspective.get("identity"):
        print(f"IDENTITY: {perspective['identity']}")
    if perspective.get("voice"):
        print(f"VOICE: {perspective['voice']}")
    print(f"POSTURE: {posture_label}")
    print(f"DIRECTIVE: {directive}")


if __name__ == "__main__":
    main()
