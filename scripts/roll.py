#!/usr/bin/env python3
"""Roll the serendipity dice — manual /dice invocation (v2.0).

Picks a random perspective from all discovered sources and a random posture
from 3 posture sources. Pure random — no temperature (that's the hook's job).
"""

import random
import sys
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CLAUDE_DIR = Path.home() / ".claude"

# Skills whose thinking-mode keywords qualify them as posture-like
_SKILL_POSTURE_KEYWORDS = frozenset({
    "blast", "radius", "compounding", "impact", "surface",
    "eval", "verify", "audit", "review", "simplify",
})


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


# ---------------------------------------------------------------------------
# Perspective discovery (4 sources)
# ---------------------------------------------------------------------------


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


def discover_all_perspectives(exclude: set[str] | None = None) -> list[dict]:
    """Gather perspectives from all 4 sources. Deduplicate by id (first wins)."""
    exclude = exclude or set()
    seen: set[str] = set()
    all_perspectives: list[dict] = []
    for fn in (_discover_archetypes, _discover_user_agents, _discover_user_skills, _discover_plugin_agents):
        for p in fn():
            pid = p["id"]
            if pid in seen or pid in exclude:
                continue
            seen.add(pid)
            all_perspectives.append(p)
    return all_perspectives


# ---------------------------------------------------------------------------
# Posture discovery (3 sources)
# ---------------------------------------------------------------------------


def _postures_from_config(config: dict) -> list[dict]:
    """Source 1: postures defined inline in serendipity.yaml."""
    postures = config.get("postures", {})
    results = []
    for name, body in postures.items():
        results.append({
            "label": name.upper().replace("_", " "),
            "directive": body.get("directive", "Provide a different perspective.").strip(),
            "weight": body.get("weight", 1),
            "source": "config",
        })
    return results


def _postures_from_files() -> list[dict]:
    """Source 2: config/postures/*.yaml — standalone posture definition files."""
    postures_dir = CONFIG_DIR / "postures"
    if not postures_dir.is_dir():
        return []
    results = []
    for p in sorted(postures_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text())
            if not data:
                continue
            results.append({
                "label": data.get("label", p.stem.upper().replace("-", " ").replace("_", " ")),
                "directive": data.get("directive", "").strip(),
                "weight": data.get("weight", 1),
                "source": "posture-file",
            })
        except Exception:
            continue
    return results


def _postures_from_skills() -> list[dict]:
    """Source 3: thinking-mode skills at ~/.claude/skills/ matching posture keywords."""
    skills_dir = CLAUDE_DIR / "skills"
    if not skills_dir.is_dir():
        return []
    results = []
    for skill_md in sorted(skills_dir.glob("*/skill.md")):
        skill_id = skill_md.parent.name
        if skill_id == "serendipity-dice":
            continue
        # Check if the skill name/ID or description matches any posture keyword
        name_lower = skill_id.lower().replace("-", " ").replace("_", " ")
        matched = any(kw in name_lower for kw in _SKILL_POSTURE_KEYWORDS)
        fm = _parse_frontmatter(skill_md)
        if not matched:
            desc_lower = str(fm.get("description", "")).lower()
            matched = any(kw in desc_lower for kw in _SKILL_POSTURE_KEYWORDS)
        if not matched:
            continue
        name = fm.get("name", skill_id)
        desc = fm.get("description", "")
        if isinstance(desc, str) and len(desc) > 200:
            desc = desc[:200].rsplit(" ", 1)[0] + "..."
        results.append({
            "label": name.upper() if isinstance(name, str) else skill_id.upper(),
            "directive": desc if isinstance(desc, str) else str(desc),
            "weight": 1,
            "source": "skill",
        })
    return results


def discover_all_postures(config: dict) -> list[dict]:
    """Gather postures from all 3 sources."""
    all_postures: list[dict] = []
    for fn in (
        lambda: _postures_from_config(config),
        _postures_from_files,
        _postures_from_skills,
    ):
        all_postures.extend(fn())
    return all_postures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    config_path = CONFIG_DIR / "serendipity.yaml"
    if not config_path.exists():
        print(f"No serendipity config found at {config_path}", file=sys.stderr)
        sys.exit(1)

    config = yaml.safe_load(config_path.read_text())

    # Perspective exclusion list
    exclude_ids = set(config.get("perspective_exclude", []) or [])

    # Discover postures from 3 sources
    postures = discover_all_postures(config)
    if not postures:
        print("No postures found in any source", file=sys.stderr)
        sys.exit(1)

    # Roll posture (weighted)
    weights = [p["weight"] for p in postures]
    chosen_posture = random.choices(postures, weights=weights, k=1)[0]

    # Discover and roll perspective (uniform)
    perspectives = discover_all_perspectives(exclude=exclude_ids)
    if not perspectives:
        print("No perspectives found in any source", file=sys.stderr)
        sys.exit(1)

    perspective = random.choice(perspectives)

    # Format output — only print lines with content
    print(f"PERSPECTIVE: {perspective['name']} ({perspective['role']})" if perspective.get("role")
          else f"PERSPECTIVE: {perspective['name']}")
    print(f"SOURCE: {perspective['source']}")
    if perspective.get("capabilities"):
        print(f"CAPABILITIES: {', '.join(perspective['capabilities'][:6])}")
    if perspective.get("identity"):
        print(f"IDENTITY: {perspective['identity']}")
    if perspective.get("voice"):
        print(f"VOICE: {perspective['voice']}")
    print(f"POSTURE: {chosen_posture['label']}")
    print(f"POSTURE SOURCE: {chosen_posture['source']}")
    print(f"DIRECTIVE: {chosen_posture['directive']}")


if __name__ == "__main__":
    main()
