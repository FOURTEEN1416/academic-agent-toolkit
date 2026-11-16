#!/usr/bin/env python3
"""Read-only Codex skill policy audit for ARIS issue #433.

References are conservative warnings, not proof that a child skill cannot
be invoked. No policies are modified and no runtime compatibility is assumed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

INVOKE = re.compile(r"(?<![\w/])(?:/|\$)([a-z][a-z0-9-]*)\b")
LINK = re.compile(r"\.\./([a-z][a-z0-9-]*)/SKILL\.md\b")


class PolicyLoader(yaml.SafeLoader):
    """Safe YAML with duplicate keys rejected and only true/false booleans."""

    yaml_implicit_resolvers = {
        char: [(tag, pattern) for tag, pattern in resolvers
               if tag != "tag:yaml.org,2002:bool"]
        for char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in keys:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"duplicate mapping key: {key!r}", key_node.start_mark
                    )
                keys.add(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    None, None, "unhashable mapping key", key_node.start_mark
                ) from exc
        return super().construct_mapping(node, deep=deep)

    def construct_boolean(self, node):
        value = self.construct_scalar(node)
        if value not in ("true", "True", "TRUE", "false", "False", "FALSE"):
            raise yaml.constructor.ConstructorError(
                None, None, "expected boolean true or false", node.start_mark
            )
        return value.lower() == "true"


PolicyLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)
PolicyLoader.add_constructor("tag:yaml.org,2002:bool", PolicyLoader.construct_boolean)


def policy_state(file: Path) -> tuple[str, str | None]:
    if not file.exists():
        return "implicit-default", None
    raw = file.read_text(encoding="utf-8")
    try:
        document = yaml.load(raw, Loader=PolicyLoader)
    except yaml.YAMLError as exc:
        return "invalid", f"invalid YAML: {exc}"
    if not isinstance(document, dict):
        return "invalid", "expected a YAML mapping"
    if "policy" not in document:
        return "implicit-default", None
    policy = document["policy"]
    if not isinstance(policy, dict):
        return "invalid", "expected policy to be a mapping"
    if "allow_implicit_invocation" not in policy:
        return "implicit-default", None
    value = policy["allow_implicit_invocation"]
    if type(value) is not bool:
        return "invalid", "expected boolean allow_implicit_invocation (true or false)"
    return ("implicit-allowed" if value else "explicit-only"), None


def audit(root: Path) -> dict:
    skills = {p.parent.name: p for p in sorted(root.glob("*/SKILL.md"))}
    if not skills:
        raise ValueError(f"Missing skills in {root}")
    referenced_by = {name: set() for name in skills}
    for parent, path in skills.items():
        body = path.read_text(encoding="utf-8")
        for child in (set(INVOKE.findall(body)) | set(LINK.findall(body))) & skills.keys():
            if child != parent:
                referenced_by[child].add(parent)
    rows, errors = [], []
    for name, path in skills.items():
        policy = path.parent / "agents" / "openai.yaml"
        state, error = policy_state(policy)
        if error:
            errors.append(f"{policy}: {error}")
        rows.append({"skill": name, "invocation": state, "referenced_by": sorted(referenced_by[name])})
    return {"skill_count": len(skills), "explicit_only_count": sum(x["invocation"] == "explicit-only" for x in rows), "referenced_explicit_only": [x["skill"] for x in rows if x["invocation"] == "explicit-only" and x["referenced_by"]], "invalid_policies": errors, "runtime_verified": False, "skills": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "skills" / "skills-codex")
    parser.add_argument("--fail-on-referenced-explicit", action="store_true")
    options = parser.parse_args()
    result = audit(options.root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return int(bool(result["invalid_policies"] or (options.fail_on_referenced_explicit and result["referenced_explicit_only"])))


if __name__ == "__main__":
    raise SystemExit(main())
