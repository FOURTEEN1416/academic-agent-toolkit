"""Multi-model debate engine (Stage 8 / 14 / 18).

Upgrades the project's shallow "multi-perspective one-shot" pattern into a real
debate:

  1. multiple *models* each play a distinct role (round-robin over the panel),
  2. an optional rebuttal round where every role sees the others' prior turn and
     pushes back, and
  3. an independent judge that scores and ranks the perspectives; the final text
     is then synthesized either by that judge (legacy) or, when a distinct
     ``synthesizer`` is given, by the stronger model anchored to the ranking.

Opt-in: callers only route here when ``build_panel_llms(config)`` returns a
non-empty panel (i.e. ``llm.debate_enabled`` is set). When the panel has a single
model this degrades to single-model multi-role, matching the legacy behaviour
plus a judging step.

The engine is provider-agnostic and offline-testable: it only calls
``client.chat(messages, *, system=...)`` on whatever clients it is handed.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _model_name(client: Any) -> str:
    return getattr(getattr(client, "config", None), "primary_model", "") or "unknown"


def _chat_with_retry(
    client: Any,
    user: str,
    system: str,
    max_tokens: int,
    *,
    label: str,
    attempts: int = 2,
) -> str:
    """One debate turn with a one-shot retry; returns content or "" (never raises).

    A panel role's transient failure (an exception, or an empty body — e.g. a
    reasoning model occasionally starving the answer) would otherwise drop that
    whole perspective from the debate. Retrying once recovers the common
    transient case before the caller falls back to dropping the role.
    """
    for k in range(attempts):
        try:
            resp = client.chat(
                [{"role": "user", "content": user}],
                system=system,
                max_tokens=max_tokens,
            )
            text = resp.content or ""
            if text.strip():
                return text
            logger.warning("Debate %s: empty output (attempt %d/%d)", label, k + 1, attempts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Debate %s: chat failed (attempt %d/%d): %s", label, k + 1, attempts, exc)
    return ""


def _resolve_rounds(config_rounds: int) -> int:
    """Effective rebuttal rounds, honoring the ARC_DEBATE_ROUNDS override."""
    env = os.environ.get("ARC_DEBATE_ROUNDS", "").strip()
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return max(0, int(config_rounds))


def run_debate(
    panel: list,
    judge: Any,
    roles: dict[str, dict[str, str]],
    variables: dict[str, str],
    *,
    rounds: int,
    synth_prompt: str,
    out_dir: Path,
    prompts: Any,
    author_model: str = "",
    gen_max_tokens: int = 8192,
    synthesizer: Any = None,
) -> tuple[str, dict]:
    """Run a multi-model, multi-round debate and judge it into a final text.

    Args:
        panel: list of LLM clients (each exposes ``.chat`` and ``.config``).
            Empty list is not allowed — callers must pass at least one client.
        judge: independent judge client (scores/ranks the perspectives). Falls
            back to ``panel[0]`` if None.
        synthesizer: client that writes the final synthesis. When None (or the
            same object as the judge) the judge does scoring AND synthesis in one
            call (legacy). When a distinct client is given, scoring and synthesis
            are split: the independent ``judge`` scores/ranks (anti
            self-preference) and the (stronger) ``synthesizer`` writes the final
            text, anchored to that ranking — keeps the judge independent while
            letting the strong model produce concrete, falsifiable output.
        roles: ``{role_name: {"system": ..., "user": ...}}`` (domain bank).
        variables: template variables for ``_render``.
        rounds: number of rebuttal rounds after the opening statements.
        synth_prompt: name of the judge/synthesis sub-prompt (e.g.
            ``"hypothesis_synthesize"``).
        out_dir: directory for per-role / per-round transcripts + record.
        prompts: PromptManager (for ``sub_prompt`` rendering).
        author_model: generator model name, for provenance.

    Returns:
        ``(final_text, record_dict)``. ``final_text`` is the synthesis produced
        by the ``synthesizer`` (or the judge, in the legacy single-call path);
        ``record_dict`` is also written to ``out_dir/debate_record.json``.
    """
    from researchclaw.prompts import _render  # local import: avoid cycles

    if not panel:
        raise ValueError("run_debate requires a non-empty panel")

    rounds = _resolve_rounds(rounds)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ablation hook (shared with the legacy path): collapse to a single role.
    if os.environ.get("ARC_ABL_DISABLE_DEBATE", "").strip() == "1" and roles:
        first = next(iter(roles))
        roles = {first: roles[first]}
        logger.info("ARC_ABL_DISABLE_DEBATE=1 — debate collapsed to role %s", first)

    role_names = list(roles.keys())
    # Bind each role to a panel model round-robin so distinct models argue.
    role_model: dict[str, Any] = {
        name: panel[i % len(panel)] for i, name in enumerate(role_names)
    }

    # --- Opening statements (round 0) ---
    current: dict[str, str] = {}
    for name in role_names:
        rp = roles[name]
        system = _render(rp["system"], variables)
        user = _render(rp["user"], variables)
        text = _chat_with_retry(
            role_model[name], user, system, gen_max_tokens, label=f"r0 role={name}",
        )
        if not text.strip():
            # Empty/failed after retry — drop this role rather than feed a blank
            # opening statement into the rebuttal/synthesis.
            logger.warning(
                "Debate r0 role=%s model=%s empty after retries — dropped",
                name, _model_name(role_model[name]),
            )
            continue
        current[name] = text
        (out_dir / f"{name}.r0.md").write_text(text, encoding="utf-8")
        logger.info(
            "Debate r0 role=%s model=%s (%d chars)",
            name, _model_name(role_model[name]), len(text),
        )

    # --- Rebuttal rounds (each role sees the others' latest turn) ---
    for r in range(1, rounds + 1):
        prev = dict(current)
        if len(prev) < 2:
            break  # nothing to push back against
        for name in role_names:
            if name not in prev:
                continue
            others = "\n\n---\n\n".join(
                f"### {other}\n{prev[other]}" for other in prev if other != name
            )
            sp = prompts.sub_prompt(
                "debate_rebuttal",
                role=name,
                own_position=prev.get(name, ""),
                others=others,
            )
            text = _chat_with_retry(
                role_model[name], sp.user, sp.system, gen_max_tokens,
                label=f"r{r} role={name}",
            )
            if not text.strip():
                # Keep the prior round's non-empty position rather than
                # overwriting it with a blank rebuttal.
                logger.warning(
                    "Debate r%d role=%s empty after retries — keeping prior turn",
                    r, name,
                )
                continue
            current[name] = text
            (out_dir / f"{name}.r{r}.md").write_text(text, encoding="utf-8")

    if not current:
        raise RuntimeError("debate produced no perspectives")

    # --- Judge + synthesize ---
    judge_client = judge or panel[0]
    judge_model = _model_name(judge_client)
    synth_client = synthesizer or judge_client
    synth_model = _model_name(synth_client)
    split = synth_client is not judge_client
    parts = [f"### Perspective: {name}\n{text}" for name, text in current.items()]
    combined = "\n\n---\n\n".join(parts)
    sp = prompts.sub_prompt(synth_prompt, perspectives=combined)
    synth_max = sp.max_tokens or gen_max_tokens
    final_text = ""

    if not split:
        # Legacy single call: the judge scores, ranks, and synthesizes at once.
        judge_system = (
            "You are an INDEPENDENT judge, distinct from the debating models. "
            "First score each perspective 1-10 for rigor and evidence, rank them, "
            "then synthesize — take the strongest elements and preserve genuine "
            "disagreements.\n\n"
        ) + sp.system
        try:
            resp = judge_client.chat(
                [{"role": "user", "content": sp.user}],
                system=judge_system,
                max_tokens=synth_max,
            )
            final_text = resp.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("Debate judge failed: %s — falling back to concatenation", exc)
            final_text = combined
    else:
        # Split: independent judge scores/ranks (anti self-preference), then the
        # stronger synthesizer writes the final text anchored to that ranking.
        # The judge no longer synthesizes, so a weak judge can't flatten the
        # output into vague consensus; the strong model owns concreteness.
        ranking = ""
        try:
            score_resp = judge_client.chat(
                [{"role": "user", "content": (
                    f"Perspectives under debate:\n\n{combined}\n\n"
                    "Score each perspective 1-10 for rigor, evidence, and "
                    "falsifiability, then rank them best-first with a one-line "
                    "reason each. Be concise."
                )}],
                system=(
                    "You are an INDEPENDENT judge, distinct from the debating "
                    "models. Evaluate only — do not rewrite or merge them."
                ),
                max_tokens=gen_max_tokens,
            )
            ranking = score_resp.content or ""
            (out_dir / "debate_scores.md").write_text(ranking, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Debate scoring failed: %s — synthesizing without ranking", exc)

        synth_input = (
            f"## Independent reviewer assessment (scores + ranking)\n{ranking}\n\n"
            f"---\n\n{combined}"
        ) if ranking.strip() else combined
        sp2 = prompts.sub_prompt(synth_prompt, perspectives=synth_input)
        synth_system = (
            "Synthesize this debate into the strongest possible final position. "
            "Take the strongest elements, preserve genuine disagreements, and make "
            "every claim concrete and falsifiable with measurable predictions and "
            "explicit thresholds.\n\n"
        ) + sp2.system
        try:
            resp = synth_client.chat(
                [{"role": "user", "content": sp2.user}],
                system=synth_system,
                max_tokens=sp2.max_tokens or gen_max_tokens,
            )
            final_text = resp.content or combined
        except Exception as exc:  # noqa: BLE001
            logger.warning("Debate synthesis failed: %s — falling back to concatenation", exc)
            final_text = combined

    record = {
        "panel_models": [_model_name(c) for c in panel],
        "roles": {name: _model_name(role_model[name]) for name in role_names},
        "rounds": rounds,
        "author_model": author_model,
        "judge_model": judge_model,
        "synthesizer_model": synth_model,
        "split_judge_synthesis": split,
        "independent_judge": bool(judge_model and judge_model != author_model),
        "perspectives_succeeded": sorted(current.keys()),
    }
    (out_dir / "debate_record.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return final_text, record
