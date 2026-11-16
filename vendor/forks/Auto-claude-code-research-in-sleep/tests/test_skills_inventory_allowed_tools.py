"""Regression coverage for frontmatter-only tool-grant inspection."""

import pytest

from tools.check_skills_inventory import allowed_tools


@pytest.mark.parametrize(
    ("skill", "expected"),
    [
        (
            "---\nname: example\nallowed-tools: Read, Agent, Bash(*)\n"
            "---\n# Skill\n",
            ["Read", "Agent", "Bash(*)"],
        ),
        (
            "---\nname: example\nallowed-tools: Read\n---\n"
            "Documentation:\nallowed-tools: Agent\n",
            ["Read"],
        ),
        (
            "---\nname: example\n---\n"
            "Example:\nallowed-tools: Agent\n",
            [],
        ),
        ("# No frontmatter\nallowed-tools: Agent\n", []),
        (
            "---\nname: example\nallowed-tools:\nAgent\n---\n",
            [],
        ),
        (
            "---\r\nname: example\r\nallowed-tools: Read, Agent\r\n---\r\n",
            ["Read", "Agent"],
        ),
        (
            "---\r\nname: example\r\nallowed-tools: Read, Agent\r\n"
            "description: example\r\n---\r\n",
            ["Read", "Agent"],
        ),
        (
            "\ufeff---\nname: example\nallowed-tools: Read\n---\n",
            ["Read"],
        ),
        (
            "---\nname: example\ndescription: |\n"
            "  allowed-tools: Agent\nallowed-tools: Read\n---\n",
            ["Read"],
        ),
    ],
)
def test_allowed_tools_ignores_markdown_body_and_non_grants(skill, expected):
    assert allowed_tools(skill) == expected
