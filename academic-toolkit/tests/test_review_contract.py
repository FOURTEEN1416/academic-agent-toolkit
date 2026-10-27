import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cumcm_final_review_declares_review_execution_evidence():
    templates = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    steps = templates["comp_cumcm"]["sub_steps"]
    final_review = next(step for step in steps if step["skill_name"] == "comp-final-review")

    assert "REVIEW_EXECUTION_EVIDENCE.json" in final_review["output_files"]
