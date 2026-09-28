from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ManagedSkillInventory:
    public_entry_skills: tuple[str, ...]
    starter_skill_names: tuple[str, ...]
    optional_skill_names: tuple[str, ...]

    @property
    def default_managed_skill_names(self) -> tuple[str, ...]:
        return self.public_entry_skills + self.starter_skill_names

    @property
    def desired_managed_skill_names(self) -> tuple[str, ...]:
        return self.default_managed_skill_names + self.optional_skill_names


def canonical_vibe_skill_name(packaging: dict) -> str:
    relpath = str(
        packaging.get('canonical_vibe_payload', {}).get('target_relpath')
        or packaging.get('canonical_vibe_mirror', {}).get('target_relpath')
        or 'skills/vibe'
    )
    return Path(relpath).name


def _normalize_skill_names(values: object) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in values or []:
        name = str(raw).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return tuple(normalized)


def load_managed_skill_inventory(packaging: dict) -> ManagedSkillInventory:
    inventory = packaging.get('managed_skill_inventory')
    if not isinstance(inventory, dict):
        raise SystemExit('Runtime-core packaging manifest missing managed_skill_inventory contract.')

    canonical_vibe = canonical_vibe_skill_name(packaging)
    public_entries = list(_normalize_skill_names(inventory.get('public_entry_skills')))
    if canonical_vibe not in public_entries:
        public_entries.insert(0, canonical_vibe)

    public_entry_tuple = tuple(public_entries)
    starter_skill_tuple = tuple(
        name for name in _normalize_skill_names(inventory.get('starter_skill_names'))
        if name not in public_entry_tuple
    )
    optional_skill_tuple = tuple(
        name for name in _normalize_skill_names(inventory.get('optional_skill_names'))
        if name not in public_entry_tuple and name not in starter_skill_tuple
    )

    return ManagedSkillInventory(
        public_entry_skills=public_entry_tuple,
        starter_skill_names=starter_skill_tuple,
        optional_skill_names=optional_skill_tuple,
    )


def allowlisted_bundled_skill_names(packaging: dict) -> tuple[str, ...]:
    canonical_vibe = canonical_vibe_skill_name(packaging)
    return tuple(
        name
        for name in load_managed_skill_inventory(packaging).desired_managed_skill_names
        if name != canonical_vibe
    )


def internal_corpus_resident_skill_names(packaging: dict) -> tuple[str, ...]:
    corpus = packaging.get('internal_skill_corpus')
    if not isinstance(corpus, dict):
        return ()
    canonical_vibe = canonical_vibe_skill_name(packaging)
    return tuple(
        name
        for name in _normalize_skill_names(corpus.get('resident_skill_names'))
        if name != canonical_vibe
    )
