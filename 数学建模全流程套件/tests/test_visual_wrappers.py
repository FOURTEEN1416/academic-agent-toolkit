import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_visual_wrappers_run_under_current_python(tmp_path):
    missing_image = tmp_path / "missing.png"
    for tool_name in ("drawio_vision_check.py", "data_fig_vision_check.py"):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / tool_name), str(missing_image)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 2
        assert "File not found" in completed.stdout
