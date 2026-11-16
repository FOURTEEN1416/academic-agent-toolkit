# Codex skill invocation audit (#433)

Install the audit dependency in your Python environment, then run:

```bash
python -m pip install -r tools/requirements-codex-policy-audit.txt
python tools/audit_codex_invocation.py --root skills/skills-codex > codex-policy-report.json
```

The report inventories the Codex mirror, detects malformed/duplicate opt-in invocation policies and lists skills referenced by other skills. A reference is a **conservative warning**, not evidence of a successful runtime sub-skill invocation.

YAML is parsed with PyYAML's safe loader, including block and flow mappings. Duplicate keys, malformed YAML, non-mapping policies, and non-boolean invocation flags are errors. An omitted policy or flag retains Codex's implicit-invocation default. The report always records `runtime_verified: false`; static references cannot establish runtime compatibility.

The audit is read-only. It never sets `allow_implicit_invocation: false`, because a maintainer raised a risk that explicit-only configuration may disable parent-to-child skill calls. Before changing policies, verify actual `$child-skill` invocation with the installed Codex CLI and record its version. Run `python tools/audit_codex_invocation.py --fail-on-referenced-explicit` to fail closed for any potentially blocked references.

## Runtime diagnostic with real Codex CLI

Run `python tools/probe_codex_invocation.py` with an installed `codex` executable. The script initializes a disposable Git project and `CODEX_HOME`, creates two control skills, and calls `codex debug prompt-input` once with a neutral prompt that names neither skill. No model requests or credentials are needed; the installed skills and user configuration are untouched.

Observed on GitHub-hosted Ubuntu in the original probe and reproduced locally on macOS with the neutral prompt using **codex-cli 0.163.0**:

- Default skill: present in model-visible `<skills_instructions>` metadata.
- Skill with `policy.allow_implicit_invocation: false`: absent from the implicit catalog.
- This verifies discovery/context filtering **only**. It does not test explicit invocation or establish that a parent ARIS Skill can invoke an explicit-only child.

Original CI evidence: https://github.com/SiyuanChenToDo/Auto-claude-code-research-in-sleep/actions/runs/39044605650

The dedicated workflow runs on relevant pull requests, pushes to `main`, and manual dispatch. It publishes the static report and pins the catalog probe to Codex **0.163.0** so CLI changes are reviewed explicitly. Unit tests run in the normal Linux/macOS test suite. A missing control or unusable debug output is inconclusive (exit 2); a visible explicit-only control is a filtering failure (exit 3).

Before any shipping policy changes, exercise a real parent-to-child workflow through Codex CLI in the relevant execution mode, and ensure the child Skill body and artifacts are actually produced. Upstream issue [openai/codex#40600](https://github.com/openai/codex/issues/40600) reports explicit `$skill` expansion problems on Codex 0.149.0; this probe does not reproduce or resolve that issue on 0.163.0. Keep current defaults until the parent-to-child compatibility gate is satisfied. This diagnostic does not close ARIS #433.
