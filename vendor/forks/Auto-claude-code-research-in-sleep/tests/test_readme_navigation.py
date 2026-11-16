"""Regression coverage for numbered README navigation and legacy fragments."""

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["README.md", "README_CN.md"])
def test_numbered_subsections_match_parent_section(filename):
    section = None
    in_fence = False
    mismatches = []
    for line_number, line in enumerate(
        (REPO_ROOT / filename).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            heading = re.match(r"## (\d+)\.\s", line)
            section = heading.group(1) if heading else None
        subsection = re.match(r"### (\d+)\.\d+\s", line)
        if subsection and subsection.group(1) != section:
            mismatches.append(
                f"{filename}:{line_number}: {line} (parent section: {section})"
            )
    assert not mismatches, "\n".join(mismatches)


@pytest.mark.parametrize(
    "fragment",
    [
        "101-prerequisites",
        "102-install-skills",
        "103-update-skills",
        "104-usage",
        "105--auto-allow-for-overnight-runs-optional",
    ],
)
def test_setup_legacy_fragments_preserved(fragment):
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert f'<a id="{fragment}"></a>' in readme
