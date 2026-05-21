"""Skill discovery and loading for `.skills/` folders."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: Path


class SkillLoader:
    """Loads skill metadata at startup and full instructions on demand."""

    def __init__(self, skills_dir: str | None = None, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        configured = skills_dir or os.environ.get("SKILLS_DIR") or ".skills"
        path = Path(configured)
        self.skills_dir = path if path.is_absolute() else self.project_root / path
        self._skills = self._discover()

    def list_skills(self) -> list[SkillMetadata]:
        return list(self._skills)

    def select_for_query(self, query: str, ethical_mode: bool = False) -> list[SkillMetadata]:
        selected = []
        lowered = query.lower()
        for skill in self._skills:
            haystack = f"{skill.name} {skill.description}".lower()
            if skill.name == "ethical_shopping" and ethical_mode:
                selected.append(skill)
            elif any(token in haystack for token in _query_tokens(lowered)):
                selected.append(skill)

        wanted = {"taxonomy_search", "product_reranking"}
        selected_names = {skill.name for skill in selected}
        selected.extend(skill for skill in self._skills if skill.name in wanted - selected_names)
        return selected

    def load_skill(self, name: str) -> str:
        for skill in self._skills:
            if skill.name == name:
                return skill.path.read_text(encoding="utf-8")
        raise KeyError(f"Unknown skill: {name}")

    def load_selected_instructions(self, query: str, ethical_mode: bool = False) -> dict[str, str]:
        return {
            skill.name: self.load_skill(skill.name)
            for skill in self.select_for_query(query, ethical_mode=ethical_mode)
        }

    def _discover(self) -> list[SkillMetadata]:
        if not self.skills_dir.exists():
            return []

        skills = []
        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            frontmatter = _parse_frontmatter(text)
            name = frontmatter.get("name") or skill_file.parent.name
            description = frontmatter.get("description") or ""
            skills.append(SkillMetadata(name=name, description=description, path=skill_file))
        return skills


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---", text, flags=re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def _query_tokens(query: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", query) if len(token) > 3}

