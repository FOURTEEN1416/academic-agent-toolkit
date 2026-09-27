"""声明式业务产出检查。只返回结构化问题，不由模型复制shell自检片段。"""
from __future__ import annotations
import re
from pathlib import Path


def check_output_contract(workspace: Path, contract: dict, *, primary_output: str = "",
                          params: dict | None = None) -> dict:
    root = Path(workspace).resolve()
    errors = []
    checks = 0
    params = params or {}

    def safe(name):
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("output contract path escapes workspace")
        return path

    def require_file(name, minimum=1, contains=()):
        nonlocal checks
        name = primary_output if name == "$primary" else name
        checks += 1
        path = safe(name)
        if not name or not path.is_file() or path.stat().st_size < minimum:
            errors.append(f"{name}: 缺文件或低于实际合同下限{minimum}B")
            return
        if contains:
            text = path.read_text(encoding="utf-8", errors="replace")
            missing = [word for word in contains if word not in text]
            if missing:
                errors.append(f"{name}: 缺内容结构 {missing}")

    for item in contract.get("files", []):
        require_file(item["path"], int(item.get("min_bytes", 1)), item.get("contains", []))
    for item in contract.get("any_glob", []):
        checks += 1
        files = {p.resolve() for pattern in item["patterns"] for p in root.glob(pattern)
                 if p.is_file() and p.resolve().is_relative_to(root) and p.stat().st_size > 0}
        if len(files) < int(item.get("min_count", 1)):
            errors.append(f"缺少产物集合: {item['patterns']}")
    figure = contract.get("figure_manifest")
    if figure:
        checks += 1
        path = safe(figure)
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        match = re.search(r"<!-- BEGIN FIGURE_MANIFEST -->(.*?)<!-- END FIGURE_MANIFEST -->", text, re.S)
        if not match:
            errors.append(f"{figure}: 缺完整FIGURE_MANIFEST")
        else:
            names = re.findall(r"^\s*-\s+([^\s]+)", match[1], re.M)
            invalid = [name for name in names if not re.match(r"(?:fig|tikz)_[A-Za-z0-9_]+", name)]
            if invalid:
                errors.append(f"{figure}: 图名不符合下游识别规则 {invalid}")
            total = re.search(r"ALL\s*=\s*(\d+)", match[1])
            if total and int(total[1]) != len(names):
                errors.append(f"{figure}: 清单ALL与实际条目数不同")
            # 数据图硬底线（B窗 2026-09-26 承接原技能 shell 验证）：规划的数据图少于
            # 合同下限即违约。仅当合同显式声明 min_data_figures 时启用（非竞赛类写作
            # 不声明则不受影响）；口径与 figure_outputs 相同——按粗体章节标题判定
            # 数据图归属（数据图/matplotlib/gen_fig），流程图章节不计入。
            floor = contract.get("min_data_figures")
            if floor:
                data_names, capture = [], False
                for line in match[1].splitlines():
                    if line.strip().startswith("**"):
                        capture = bool(re.search("数据图|matplotlib|gen_fig", line, re.I))
                    entry = re.match(r"\s*-\s+((?:fig|tikz)_[A-Za-z0-9_]+)", line)
                    if capture and entry:
                        data_names.append(entry[1])
                if len(data_names) < int(floor):
                    errors.append(f"{figure}: 规划数据图 {len(data_names)} 张低于合同硬底线 {floor} 张（工作不完整）")
    if contract.get("figure_outputs"):
        checks += 1
        plan = next((safe(name) for name in ("PROBLEM_ANALYSIS.md", "PAPER_PLAN.md", "MODELING_REPORT.md", "TOPIC_PLAN.md")
                     if safe(name).is_file() and "<!-- BEGIN FIGURE_MANIFEST -->" in safe(name).read_text(encoding="utf-8", errors="replace")), None)
        expected = []
        if plan is not None:
            text = plan.read_text(encoding="utf-8", errors="replace")
            block = re.search(r"<!-- BEGIN FIGURE_MANIFEST -->(.*?)<!-- END FIGURE_MANIFEST -->", text, re.S)
            capture = False
            if block:
                for line in block[1].splitlines():
                    if line.strip().startswith("**"):
                        data = bool(re.search("数据图|matplotlib|gen_fig", line, re.I))
                        diagram = bool(re.search("drawio|html|tikz|流程|架构", line, re.I))
                        capture = data if contract["figure_outputs"] == "data" else diagram
                    match = re.match(r"\s*-\s+((?:fig|tikz)_[A-Za-z0-9_]+)", line)
                    if capture and match:
                        expected.append(match[1])
            for name in expected:
                if not any(safe(f"figures/{name}.{ext}").is_file() and safe(f"figures/{name}.{ext}").stat().st_size
                           for ext in ("pdf", "png", "svg")):
                    errors.append(f"规划产物未生成: {name}")
        elif contract["figure_outputs"] == "data" and not any(root.glob("figures/fig_*.png")) and not any(root.glob("figures/fig_*.pdf")):
            errors.append("未找到规划清单或实际数据图产物")
    project_type = params.get("project_type", "fullstack")
    kind = contract.get("project_contract")
    if kind == "design":
        if project_type in {"fullstack", "frontend"}:
            require_file("DESIGN.md", contains=["## 数据库设计", "## API 设计"])
        if project_type == "fullstack":
            require_file("schema.sql", contains=["CREATE TABLE"])
    if kind == "code":
        require_file("RUN.md")
        require_file("code/README.md")
        if project_type == "fullstack":
            require_file("code/backend/main.py")
            if not any(safe(p).is_file() for p in ("code/backend/requirements.txt", "code/backend/package.json")):
                errors.append("缺后端依赖声明")
            if not safe("code/frontend").is_dir():
                errors.append("缺前端实现目录")
        elif not any(p.suffix in {".py", ".js", ".ts", ".jsx", ".tsx", ".html"} for p in safe("code").rglob("*") if p.is_file()):
            errors.append("code缺实际主源码")
        if project_type == "frontend" and list(safe("code").rglob("*.html")):
            if not safe("code/index.html").is_file() and not safe("code/package.json").is_file():
                errors.append("静态前端缺index.html入口")
    if contract.get("subproblem_outputs"):
        path = safe("MODELING_REPORT.md")
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        names = set(re.findall(r"^#{1,4}\s+.*?((?:问题[一二三四五六七八九十\d]+)|(?:(?:Problem|Question)\s*\d+))", text, re.M | re.I))
        for pattern in ("code/problem*.py", "figures/problem_*_results.json"):
            if len(list(root.glob(pattern))) < len(names):
                errors.append(f"{pattern}: 实际子问题产出不足{len(names)}项")
    md_deliverable = contract.get("markdown_deliverable")
    if md_deliverable:
        # docx 模式产出合同（B窗 2026-09-27 承接原技能正文验证脚本，阈值原样保留）：
        # ① 交付文件存在且不低于现行字节下限；② Markdown/LaTeX 模式边界——只判
        # 文档结构类 LaTeX 命令残留（\section{/\cite{/\input{…}），数学环境命令
        # （\begin{cases}/\end{aligned}/\text{} 等 docx 公式引擎语法）不判违规，
        # 正文正常提及 ".tex" 字样也不判违规（残留看命令形态，不看字符串）；
        # ③ docx 模式禁产的 .tex 产物文件（paper/、paper/sections/ 下）存在即违规；
        # figures/latex_includes.tex 等参考资料不在禁产清单内，天然豁免。
        name = str(md_deliverable.get("path", ""))
        name = primary_output if name == "$primary" else name
        minimum = int(md_deliverable.get("min_bytes", 1))
        checks += 1
        path = safe(name) if name else None
        if path is None or not name or not path.is_file() or path.stat().st_size < minimum:
            errors.append(f"{name}: 缺Markdown交付文件或低于现行下限{minimum}B")
        else:
            if md_deliverable.get("latex_residue"):
                text = path.read_text(encoding="utf-8", errors="replace")
                residue = re.findall(
                    r"\\(?:input|include|includegraphics|section|subsection|chapter|"
                    r"bibliography|bibliographystyle|bibitem|usepackage|documentclass|cite|ref|label)\s*\{",
                    text)
                if residue:
                    errors.append(f"{name}: 残留文档结构类LaTeX命令 {sorted(set(residue))[:6]}"
                                  "（数学环境公式语法不属残留；正文提及 .tex 字样不判违规）")
            for pattern in md_deliverable.get("no_tex_artifacts", []):
                artifacts = [p for p in root.glob(pattern) if p.is_file()]
                if artifacts:
                    errors.append(f"docx模式禁产.tex产物: {[p.relative_to(root).as_posix() for p in artifacts[:4]]}"
                                  "（figures/latex_includes.tex 等作图参考资料除外）")
    return {"ok": not errors, "checks": checks, "errors": errors,
            "reason": "; ".join(errors) if errors else "业务产出结构与当前合同一致"}
