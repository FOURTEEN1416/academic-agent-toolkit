import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from engine.quality_gates import QualityGate

workspace = Path(tempfile.mkdtemp(prefix='fig-debug2-'))
workspace.mkdir(parents=True, exist_ok=True)

# 创建 figures 目录和 latex_includes.tex
(workspace / 'figures').mkdir(parents=True, exist_ok=True)
(workspace / 'figures' / 'latex_includes.tex').write_text('\\usepackage{amsfonts}\n' * 50, encoding='utf-8')

# 运行门禁
gate = QualityGate(workspace)
checks = gate.run_all('paper-figure', declared_outputs=['figures/latex_includes.tex'], required_checks=['figure_provenance'])
print(json.dumps(checks, ensure_ascii=False, indent=2, default=str))
