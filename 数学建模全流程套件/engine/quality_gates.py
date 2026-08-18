#!/usr/bin/env python3
"""P4+P5+P6+P7 统一能力封装
quality_gates.py — 质量门禁系统 + 多角色 Agent + 视觉能力 + 编辑器 AI
"""
from __future__ import annotations
import os, sys, json, re, subprocess, hashlib
import fitz as _fitz
from pathlib import Path

# 确保 engine 目录在 sys.path（CLI 直接运行时）
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
if str(_ENGINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR.parent))

try:
    from .artifact_manifest import ArtifactManifest
except ImportError:
    try:
        from artifact_manifest import ArtifactManifest
    except ImportError:
        from engine.artifact_manifest import ArtifactManifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
RULES_FILE = PROJECT_ROOT / "engine" / "modex-core" / "comp_rules.json"
GATES_FILE = PROJECT_ROOT / "engine" / "modex-core" / "quality_gates.json"

# =====================================================
# 审稿角色 → agent 配置文件映射（软校验用）
# 与共享根 .opencode/agents/*.md 的模型配置保持一致；
# 本系统模型策略与整个 OpenCode 桌面端 agent 配置同源。
# =====================================================
ROLE_AGENT_FILES = {
    "reviewer": "数模审稿人.md",
    "visual_reviewer": "数模视觉审查.md",
    "editor": "数模编辑.md",
    "final_reviewer": "数模专家.md",
}

# OpenCode 配置目录（共享根 .opencode/agents/），可被环境变量覆盖（测试用）
OPENCODE_AGENTS_DIR = os.environ.get(
    "OPENCODE_AGENTS_DIR",
    str(PROJECT_ROOT.parent / ".opencode" / "agents"),
)


def _parse_agent_model(agent_file: Path) -> str | None:
    """从 agent markdown frontmatter 解析 model 字段（provider/model 或 model）。"""
    try:
        text = agent_file.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^model:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def load_configured_role_models() -> dict[str, str]:
    """读取 .opencode/agents/ 中四个审稿角色的当前配置模型。

    返回 {角色: 配置的 model}；agent 文件缺失或无法解析时该角色为空字符串。
    """
    agents_dir = Path(os.environ.get("OPENCODE_AGENTS_DIR", OPENCODE_AGENTS_DIR))
    result: dict[str, str] = {}
    for role, filename in ROLE_AGENT_FILES.items():
        model = _parse_agent_model(agents_dir / filename)
        result[role] = model or ""
    return result


_REVIEW_EVIDENCE_ROLES = {"reviewer", "visual_reviewer", "editor", "final_reviewer"}


def build_review_execution_evidence(workspace: Path | str, roles: dict, completed_at: str) -> dict:
    """Build machine-verifiable review provenance from primary-agent role records."""
    if set(roles) != _REVIEW_EVIDENCE_ROLES:
        raise ValueError("角色集合不完整")
    root = Path(workspace).resolve()
    evidence_roles = {}
    for role_name, record in roles.items():
        if not isinstance(record, dict):
            raise ValueError(f"{role_name} 执行证据字段不完整")
        session_id = str(record.get("session_id", "")).strip()
        model = str(record.get("model", "")).strip()
        output_file = str(record.get("output_file", "")).strip()
        if not session_id or not model or not output_file or not completed_at:
            raise ValueError(f"{role_name} 执行证据字段不完整")
        output_path = (root / output_file).resolve()
        try:
            output_path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{role_name} output_file 超出工作区: {output_file}") from exc
        if not output_path.is_file():
            raise ValueError(f"{role_name} output_file 不存在: {output_file}")
        evidence_roles[role_name] = {
            "session_id": session_id,
            "model": model,
            "output_file": output_path.relative_to(root).as_posix(),
            "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
            "completed_at": completed_at,
        }
    return {"roles": evidence_roles}

# 加载 .env 配置
try:
    from env_loader import apply_env, get as env_get
    apply_env()
except ImportError:
    env_get = lambda k, d="": os.environ.get(k, d)

# =====================================================
# 质量门禁常量（从原版导出）
# =====================================================

# 默认门禁（若 quality_gates.json 缺失）
DEFAULT_MIN_SIZE = {
    "comp-prob-analysis": 1500, "comp-modeling": 2000, "comp-code": 1000,
    "comp-review": 40, "comp-stats-topic": 1000, "comp-paper-zh": 10000,
    "comp-paper-en": 10000, "paper-write": 15000, "paper-write-zh": 15000,
    "paper-plan": 3000, "literature-review": 5000, "idea-discovery": 3000,
}

DEFAULT_REQUIRED_COMPANIONS = {
    "comp-code": ["code/main.py", "figures/all_results.json"],
    "paper-analysis": ["RESULTS.md", "figures/all_results.json", "code/main.py"],
}

# 竞赛页数要求
COMP_PAGES = {
    "comp_cumcm": 30, "comp_mcm": 25, "comp_huawei": 50,
    "comp_mathorcup": 30, "comp_apmcm": 25, "comp_teddy": 40,
    "comp_certcup": 35, "comp_stats": 30,
}


# =====================================================
# 环境能力检测（LaTeX / 绘图 / API 可用性）
# =====================================================

def detect_capabilities() -> dict:
    """检测当前环境的可用能力，供 Agent 决定采用哪条出图路径"""
    caps = {
        "latex": False,
        "matplotlib": False,
        "seaborn": False,
        "pillow": False,
        "drawio": False,
        "gpt_image_api": False,
        "vision_api": False,
        "xelatex_path": None,
        "runtime_source": None,
        "runtime_commands": {},
    }
    # 1. Discover optional suite runtimes or commands on the system PATH.
    try:
        from engine.runtime_adapter import RuntimePaths
        rt = RuntimePaths.discover(PROJECT_ROOT)
        caps["runtime_source"] = rt.source
        caps["runtime_commands"] = {name: bool(p) for name, p in rt.commands.items()}
        caps["runtime_guidance"] = rt.capabilities()["guidance"]
        try:
            if rt.command("xelatex"):
                caps["latex"] = True
                caps["xelatex_path"] = str(rt.command("xelatex"))
        except FileNotFoundError:
            pass
        try:
            if rt.command("drawio"):
                caps["drawio"] = True
        except FileNotFoundError:
            pass
    except Exception:
        # 不依赖 runtime_adapter 的导入失败场景
        pass
    # 2. Retain common MiKTeX locations as a platform-specific capability check.
    if not caps["latex"]:
        for c in [
            os.environ.get("LOCALAPPDATA", "") + r"\Programs\MiKTeX\miktex\bin\x64\xelatex.exe",
            r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
        ]:
            if os.path.exists(c):
                caps["latex"] = True
                caps["xelatex_path"] = c
                break
    # 3. Python 绘图库
    try:
        import matplotlib
        caps["matplotlib"] = True
    except ImportError:
        pass
    try:
        import seaborn
        caps["seaborn"] = True
    except ImportError:
        pass
    try:
        from PIL import Image
        caps["pillow"] = True
    except ImportError:
        pass
    # 4. API Key
    if env_get("GPT_IMAGE_API_KEY"):
        caps["gpt_image_api"] = True
    if env_get("EDITOR_AI_API_KEY") or env_get("OPENAI_API_KEY") or env_get("SENSENOVA_API_KEY"):
        caps["vision_api"] = True
    return caps


def _load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _body_citation_markers(text: str) -> list[str]:
    """从论文全文提取「正文区」的 [n] 引用标记。

    排除两类干扰：
    1. 参考文献列表区（"参考文献"/"References" 标题之后到附录/正文结束）；
    2. 附录区（"附录"/"Appendix" 标题之后，其中可能含源代码中的数组下标 [i]）。
    只统计摘要+正文区内的 [n]，避免把参考文献自身的编号当成正文引用。
    """
    markers = []
    # 找到参考文献区与附录区的起始位置
    ref_starts = []
    for pat in ("参考文献", "References", "REFERENCES", "Reference"):
        idx = text.find(pat)
        if idx >= 0:
            ref_starts.append(idx)
    appendix_starts = []
    for pat in ("附录", "Appendix", "APPENDIX"):
        idx = text.find(pat)
        if idx >= 0:
            appendix_starts.append(idx)
    cut_start = min(ref_starts) if ref_starts else None
    cut_end = min(appendix_starts) if appendix_starts else None

    # 正文区 = 全文截断到参考文献之前；若参考文献区缺失则只截掉附录
    if cut_start is not None:
        body = text[:cut_start]
    elif cut_end is not None:
        body = text[:cut_end]
    else:
        body = text

    # 提取 [n] 或 [n,m] 标记；过滤掉明显的非引用（如源码数组下标出现在大段代码中，
    # 但正文区一般没有代码——保守起见仅匹配 [1..99] 数字）
    for match in re.finditer(r"\[(\d+(?:\s*[,，]\s*\d+)*)\]", body):
        token = match.group(0)
        markers.append(token)
    return markers


def get_min_size(skill_name: str) -> int:
    """获取技能的最小产出大小"""
    gates = _load_json(GATES_FILE, {}) or {}
    step_min = gates.get("_STEP_MIN_SIZE", DEFAULT_MIN_SIZE)
    return step_min.get(skill_name, DEFAULT_MIN_SIZE.get(skill_name, 0))


def get_required_companions(skill_name: str) -> list:
    """获取技能的必需伴随文件"""
    gates = _load_json(GATES_FILE, {}) or {}
    companions = gates.get("_STEP_REQUIRED_COMPANIONS", DEFAULT_REQUIRED_COMPANIONS)
    return companions.get(skill_name, DEFAULT_REQUIRED_COMPANIONS.get(skill_name, []))


def get_comp_rules(comp_name: str) -> dict:
    """获取竞赛规则"""
    rules = _load_json(RULES_FILE, {}) or {}
    return rules.get(comp_name, {})


# =====================================================
# P4: 质量门禁检查
# =====================================================

class QualityGate:
    """质量门禁系统 — 检查每个步骤产出"""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)

    def check_min_size(self, skill_name: str, primary_output: str) -> dict:
        """检查产出文件是否达到最小大小"""
        min_size = get_min_size(skill_name)
        if min_size <= 0:
            return {"ok": True, "reason": f"技能 {skill_name} 无最小大小要求"}
        # 找产出文件
        output_path = self.workspace / primary_output if primary_output else None
        if output_path and output_path.exists():
            if output_path.is_dir():
                size = sum(path.stat().st_size for path in output_path.rglob("*") if path.is_file())
            else:
                size = output_path.stat().st_size
            ok = size >= min_size
            return {"ok": ok, "size": size, "min": min_size,
                    "reason": f"产出 {primary_output} = {size}B {'✅' if ok else f'❌ 需≥{min_size}B'}"}
        if primary_output:
            return {"ok": False, "reason": f"未找到指定产出 {primary_output} 或其大小不足 {min_size}B"}
        # Legacy calls without a declared primary output retain best-effort discovery.
        for f in self.workspace.rglob("*.md"):
            if f.stat().st_size >= min_size:
                return {"ok": True, "size": f.stat().st_size, "min": min_size,
                        "reason": f"找到产出 {f.name} = {f.stat().st_size}B ✅"}
        return {"ok": False, "reason": f"未找到 ≥{min_size}B 的产出文件"}

    def check_companions(self, skill_name: str) -> dict:
        """检查必需伴随文件是否存在"""
        companions = get_required_companions(skill_name)
        if not companions:
            return {"ok": True, "reason": f"技能 {skill_name} 无伴随文件要求"}
        missing = []
        for comp in companions:
            if not (self.workspace / comp).exists():
                missing.append(comp)
        ok = len(missing) == 0
        return {"ok": ok, "missing": missing,
                "reason": "✅ 伴随文件齐全" if ok else f"❌ 缺少: {missing}"}

    def check_paper_pages(self, comp_name: str, paper_dir: str = "paper") -> dict:
        """Enforce a competition page upper bound, with body-only semantics for CUMCM."""
        rules = get_comp_rules(comp_name)
        max_pages = rules.get("max_pages") or COMP_PAGES.get(comp_name)
        if not max_pages:
            return {"ok": True, "reason": f"竞赛 {comp_name} 无页数要求"}
        pdf = self.workspace / paper_dir / "main.pdf"
        tex = self.workspace / paper_dir / "main.tex"
        if pdf.exists():
            if rules.get("page_scope") == "body":
                return self._check_body_pages(pdf, max_pages)
            return self._check_total_pdf_pages(pdf, max_pages)
        if tex.exists():
            # M4 FIX: tex 回退按内容量估算页数（与 max_pages 语义一致），
            # 不再用 "section >= 3" 这种与页数无关的判定。
            # 估算规则：正文中文字符数（剔除 LaTeX 命令/注释/空行）≈ 每页 3500 字符。
            content = tex.read_text(encoding="utf-8", errors="ignore")
            # 剔除注释行与 LaTeX 命令，保留正文文本
            lines = [ln for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("%")]
            body_text = "\n".join(lines)
            body_text = re.sub(r"\\(?:begin|end)\{[^}]+\}", "", body_text)
            body_text = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", body_text)
            # 中文字符 + 普通字符计数（中文字符按 1 字计）
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", body_text))
            other_chars = len(re.sub(r"[\u4e00-\u9fff\s]", "", body_text))
            estimated_chars = chinese_chars + other_chars * 0.5  # 半角字符约半宽
            estimated_pages = max(1, int(estimated_chars / 3500) + 1)
            ok = estimated_pages <= max_pages
            return {"ok": ok, "estimated_pages": estimated_pages, "max_pages": max_pages,
                    "reason": f"LaTeX 估算约 {estimated_pages} 页（上限 {max_pages} 页，PDF 未生成）"
                              f"{'✅' if ok else '❌ 请先编译 PDF 确认页数'}"}
        return {"ok": False, "reason": "未找到 paper/main.tex 或 paper/main.pdf"}

    def _check_total_pdf_pages(self, pdf: Path, max_pages: int) -> dict:
        pages = None
        try:
            completed = subprocess.run(
                ["pdfinfo", str(pdf)], capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30, check=False
            )
            if completed.stdout:
                match = re.search(r"^Pages:\s*(\d+)\s*$", completed.stdout, re.MULTILINE)
                if completed.returncode == 0 and match:
                    pages = int(match.group(1))
        except (FileNotFoundError, subprocess.TimeoutExpired, UnicodeDecodeError):
            pass
        if pages is None:
            try:
                doc = _fitz.open(str(pdf))
                pages = doc.page_count
                doc.close()
            except Exception:
                pass
        if pages is None:
            return {"ok": False, "reason": "无法解析 PDF 页数（pdfinfo 和 PyMuPDF 均不可用）"}
        ok = pages <= max_pages
        return {"ok": ok, "pages": pages, "max": max_pages,
                "reason": f"PDF {pages} 页（上限 {max_pages} 页）{'✅' if ok else '❌'}"}

    @staticmethod
    def _check_body_pages(pdf: Path, max_body: int) -> dict:
        """Count body pages in a PDF by text keyword detection.

        First page = summary (摘要). Body = pages between summary and 附录.
        Appendix (附录 and later) is unlimited.
        """
        try:
            doc = _fitz.open(str(pdf))
        except ImportError:
            return {"ok": False, "reason": "fitz (PyMuPDF) 不可用，无法统计正文页数"}
        try:
            pages = doc.page_count
            body_start = False
            body_count = 0
            for i in range(pages):
                text = doc[i].get_text().strip()
                if not body_start:
                    if "摘要" in text:
                        body_start = True
                    continue
                if "附录" in text:
                    break
                body_count += 1
        finally:
            doc.close()
        ok = body_count <= max_body
        return {"ok": ok, "body_pages": body_count, "total_pages": pages, "max_body": max_body,
                "reason": f"正文 {body_count} 页（上限 {max_body} 页）{'✅' if ok else '❌'}"}

    def check_literature_evidence(self, require_citations: bool = True) -> dict:
        """Require reproducible research records, and optionally paper citation closure."""
        required = [self.workspace / "LITERATURE.md", self.workspace / "literature" / "search_evidence.json"]
        missing = [str(path.relative_to(self.workspace)).replace("\\", "/") for path in required if not path.is_file()]
        if missing:
            return {"ok": False, "missing": missing, "reason": f"缺少文献证据: {', '.join(missing)}"}
        try:
            records = json.loads(required[1].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "reason": "文献检索证据不是有效 JSON"}
        if not isinstance(records, list) or not records:
            return {"ok": False, "reason": "文献检索证据为空"}
        if not require_citations:
            return {"ok": True, "records": len(records), "reason": "文献检索记录与参考文献完整"}
        search_dois = set()
        search_keys = set()
        for record in records:
            candidates = record.get("records", []) if isinstance(record, dict) else []
            if isinstance(record, dict) and record.get("doi"):
                candidates = [record, *candidates]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("doi"):
                    search_dois.add(str(candidate["doi"]).lower().strip())
                if candidate.get("key"):
                    search_keys.add(str(candidate["key"]).lower().strip())
        bib_path = self.workspace / "paper" / "references.bib"
        if not bib_path.is_file():
            return {"ok": False, "reason": "缺少 paper/references.bib"}
        bib_content = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_dois = {value.lower().strip() for value in re.findall(r"doi\s*=\s*[\{\"]([^}\"]+)", bib_content, re.I)}
        bib_keys = {value.lower().strip() for value in re.findall(r"@\w+\s*\{\s*([^,\s]+)", bib_content)}
        provenance_overlap = (search_dois & bib_dois) or (search_keys & bib_keys)
        if (search_dois or search_keys) and not provenance_overlap:
            return {"ok": False, "reason": "文献检索证据与 references.bib 无 DOI/citation-key 交集"}
        # 检查引用：优先 main.tex，降级 main.pdf（PyMuPDF），再降级 main.docx
        citations = []
        tex = self.workspace / "paper" / "main.tex"
        pdf = self.workspace / "paper" / "main.pdf"
        docx = self.workspace / "paper" / "main.docx"
        if tex.exists():
            content = tex.read_text(encoding="utf-8", errors="ignore")
            citations = re.findall(r"\\(?:cite|citep|citet)\{[^}]+\}", content)
        elif pdf.exists():
            try:
                doc = _fitz.open(str(pdf))
                text = "".join(doc[i].get_text() for i in range(doc.page_count))
                doc.close()
                citations = _body_citation_markers(text)
            except Exception:
                pass
        elif docx.exists():
            # docx 路径：检查 [n] 标注是否存在（粗粒度）
            try:
                from docx import Document
                d = Document(str(docx))
                text = "\n".join(p.text for p in d.paragraphs)
                citations = _body_citation_markers(text)
            except Exception:
                pass
        if not citations:
            return {"ok": False, "reason": "正文没有 citation 引用（checked .tex/.pdf/.docx）"}
        return {"ok": True, "records": len(records), "citations": len(citations),
                "reason": "文献检索与引用闭环完整"}

    def check_review_evidence(self, mode: str = "auto") -> dict:
        """Require reviewer, visual reviewer, editor, and fatal-free final verdicts.

        mode:
          "full"  — require all 7 files (multi-role review)
          "solo"  — require COMP_REVIEW.md + COMP_REVIEW_VERDICT.json only (single-person)
          "auto"  — if all 7 exist, check full; if only solo files exist, check solo; else FAIL
        """
        all_reports = ["COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"]
        all_verdicts = ["COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW_VERDICT.json", "FINAL_REVIEW_VERDICT.json"]
        provenance_name = "REVIEW_EXECUTION_EVIDENCE.json"
        solo_reports = ["COMP_REVIEW.md"]
        solo_verdicts = ["COMP_REVIEW_VERDICT.json"]

        if mode == "auto":
            all_exist = all((self.workspace / f).is_file() for f in all_reports + all_verdicts)
            if all_exist:
                mode = "full"
            else:
                # 有任何多角色文件存在（部分完成的多角色审稿）时不允许静默降级，
                # 否则会掩盖"审稿只做了一半"的缺失。
                # ⛔ FIX: 只检查真正的多角色文件（visual/editor/final/execution_evidence），
                # 不能把 solo 文件（COMP_REVIEW.md / COMP_REVIEW_VERDICT.json）误判为多角色证据——
                # 否则 solo 模式永远切 full、永远缺文件。
                multi_role_files = [
                    "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md",
                    "VISUAL_REVIEW_VERDICT.json", "FINAL_REVIEW_VERDICT.json",
                    "REVIEW_EXECUTION_EVIDENCE.json",
                ]
                any_multi_role = any((self.workspace / f).is_file() for f in multi_role_files)
                if any_multi_role:
                    mode = "full"
                else:
                    mode = "solo"

        if mode == "full":
            reports, verdicts = all_reports, all_verdicts
        else:
            reports, verdicts = solo_reports, solo_verdicts

        required_files = reports + verdicts + ([provenance_name] if mode == "full" else [])
        missing = [name for name in required_files if not (self.workspace / name).is_file()]
        if missing:
            fatal_count = 0
            for name in verdicts:
                path = self.workspace / name
                if not path.is_file():
                    continue
                try:
                    verdict = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(verdict.get("fatal_count"), int):
                        fatal_count += verdict["fatal_count"]
                except json.JSONDecodeError:
                    pass
            return {"ok": False, "missing": missing, "fatal_count": fatal_count, "mode": mode,
                    "reason": f"缺少审稿证据 ({mode} 模式): {', '.join(missing)}"}
        fatal_count = 0
        for name in verdicts:
            try:
                verdict = json.loads((self.workspace / name).read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"ok": False, "reason": f"审稿裁定不是有效 JSON: {name}"}
            has_findings = isinstance(verdict.get("findings"), list) or isinstance(verdict.get("findings_fixed"), list)
            if not has_findings or not isinstance(verdict.get("fatal_count"), int):
                return {"ok": False, "reason": f"审稿裁定字段不完整: {name}"}
            fatal_count += verdict["fatal_count"]
            # 视觉审查裁定必须携带 status（pass|fail|unavailable）：
            # 视觉 API 不可用而伪装成 pass 是典型造假路径，这里硬性拦截。
            if name == "VISUAL_REVIEW_VERDICT.json":
                status = verdict.get("status")
                if status not in ("pass", "fail", "unavailable"):
                    return {"ok": False,
                            "reason": f"视觉审查裁定缺少有效 status 字段（需 pass|fail|unavailable）: {name}"}
                if status != "pass":
                    return {"ok": False,
                            "reason": f"视觉审查未通过（status={status}），终审不得放行: {name}"}
        provenance_ok = True
        provenance_reason = ""
        provenance_warnings: list[str] = []
        if mode == "full" and not missing:
            try:
                provenance = json.loads((self.workspace / provenance_name).read_text(encoding="utf-8"))
                roles = provenance.get("roles", {})
                required_roles = {"reviewer", "visual_reviewer", "editor", "final_reviewer"}
                if set(roles) != required_roles:
                    raise ValueError("角色集合不完整")
                sessions = []
                # 软校验：证据声明的模型 vs .opencode/agents 当前配置（整个 OpenCode 桌面端同源）
                configured_models = load_configured_role_models()
                for role_name, role in roles.items():
                    if not all(role.get(field) for field in ("session_id", "model", "output_sha256", "completed_at", "output_file")):
                        raise ValueError(f"{role_name} 执行证据字段不完整")
                    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(role["output_sha256"])):
                        raise ValueError(f"{role_name} output_sha256 无效")
                    output_path = self.workspace / role["output_file"]
                    if not output_path.is_file():
                        raise ValueError(f"{role_name} output_file 不存在: {role['output_file']}")
                    actual = hashlib.sha256(output_path.read_bytes()).hexdigest()
                    if actual.lower() != str(role["output_sha256"]).lower():
                        raise ValueError(f"{role_name} output_sha256 与 {role['output_file']} 实际哈希不一致")
                    sessions.append(role["session_id"])
                    # ⚠️ 软校验（不阻断）：证据模型与 agent 配置不一致时警告
                    claimed = str(role.get("model", "")).strip()
                    configured = configured_models.get(role_name, "")
                    if configured and claimed and claimed != configured:
                        provenance_warnings.append(
                            f"{role_name}: 证据模型 {claimed!r} ≠ 配置模型 {configured!r}"
                        )
                if len(set(sessions)) != len(sessions):
                    raise ValueError("审稿角色 session_id 不独立")
            except (json.JSONDecodeError, ValueError) as exc:
                provenance_ok = False
                provenance_reason = str(exc)
        ok = fatal_count == 0 and provenance_ok
        if provenance_warnings:
            reason = (f"审稿闭环无 fatal ({mode} 模式)，但存在模型配置不一致警告: "
                      + "; ".join(provenance_warnings))
        else:
            reason = f"审稿闭环无 fatal ({mode} 模式)" if ok else (
                f"审稿执行证据无效: {provenance_reason}" if not provenance_ok else f"审稿闭环有 {fatal_count} 个 fatal ({mode} 模式)"
            )
        return {"ok": ok, "fatal_count": fatal_count, "mode": mode,
                "reason": reason, "warnings": provenance_warnings}

    def check_consistency_evidence(self) -> dict:
        """Require a canonical result ledger and a passing code-paper consistency report."""
        required = [self.workspace / "RESULTS.md", self.workspace / "figures" / "all_results.json",
                    self.workspace / "CONSISTENCY_REPORT.json"]
        missing = [str(path.relative_to(self.workspace)).replace("\\", "/") for path in required if not path.is_file()]
        if missing:
            return {"ok": False, "missing": missing, "reason": f"缺少一致性证据: {', '.join(missing)}"}
        try:
            report = json.loads(required[-1].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "reason": "一致性报告不是有效 JSON"}
        if report.get("ok") is not True or not isinstance(report.get("claims"), list):
            return {"ok": False, "reason": "代码-论文一致性报告未通过"}
        return {"ok": True, "claims": len(report["claims"]), "reason": "代码-论文一致性报告通过"}

    def check_final_audit_report(self) -> dict:
        """Require a manifest-backed delivery decision, not a presence-only JSON file."""
        path = self.workspace / "AUDIT_REPORT.json"
        if not path.is_file():
            return {"ok": False, "reason": "缺少 AUDIT_REPORT.json"}
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "reason": "最终审计报告不是有效 JSON"}
        required = {"workflow_id", "artifacts", "gate_outcomes", "waivers", "delivery_decision"}
        missing = sorted(required - report.keys()) if isinstance(report, dict) else sorted(required)
        if missing:
            return {"ok": False, "missing": missing, "reason": f"最终审计报告字段不完整: {', '.join(missing)}"}
        if not isinstance(report["artifacts"], list) or not report["artifacts"]:
            return {"ok": False, "reason": "最终审计报告 artifacts 为空"}
        for artifact in report["artifacts"]:
            if not isinstance(artifact, dict) or not artifact.get("path") or not re.fullmatch(
                r"[0-9a-fA-F]{64}", str(artifact.get("sha256", ""))
            ):
                return {"ok": False, "reason": "最终审计报告 artifact 字段或 SHA-256 无效"}
        if not isinstance(report["gate_outcomes"], dict) or not isinstance(report["waivers"], list):
            return {"ok": False, "reason": "最终审计报告 gate_outcomes/waivers 类型无效"}
        failed_gates = [name for name, outcome in report["gate_outcomes"].items() if outcome != "pass"]
        if failed_gates:
            return {"ok": False, "failed_gates": failed_gates,
                    "reason": f"最终审计存在未通过门禁: {', '.join(failed_gates)}"}
        if report["delivery_decision"] != "ready":
            return {"ok": False, "reason": "最终交付决定不是 ready"}
        return {"ok": True, "artifact_count": len(report["artifacts"]), "reason": "最终审计报告可交付"}

    def check_source_materials(self) -> dict:
        """Validate the manifest-backed CodeSucker source-materials contract."""
        base = self.workspace / "source-materials"
        required = ["SOURCE_MATERIALS_MANIFEST.json", "files.json", "selection.json", "audit.json", "stats.json"]
        missing = [name for name in required if not (base / name).is_file()]
        if missing:
            return {"ok": False, "failures": missing, "warnings": [], "reason": f"缺少源码材料产物: {', '.join(missing)}"}
        try:
            manifest = json.loads((base / "SOURCE_MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
            files = json.loads((base / "files.json").read_text(encoding="utf-8")).get("files", [])
            selection = json.loads((base / "selection.json").read_text(encoding="utf-8"))
            audit_items = json.loads((base / "audit.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "failures": [str(exc)], "warnings": [], "reason": "源码材料 JSON 无效"}
        failures, warnings = [], []
        if manifest.get("backend") != "vendored-codesucker-core":
            failures.append("backend 不是 vendored-codesucker-core")
        for field in ("coreVersion", "coreCommit", "rulesVersion", "configSha256", "coreSha256"):
            if not manifest.get(field):
                failures.append(f"manifest 缺少 {field}")
        if not isinstance(manifest.get("outputSha256"), dict) or not manifest.get("outputSha256"):
            failures.append("manifest 缺少 outputSha256")
        if not files or not selection.get("pages"):
            failures.append("没有有效源码或分页结果")
        pages = selection.get("pages", [])
        line_limit = int(manifest.get("config", {}).get("linesPerPage", 50))
        if any(len(page.get("lines", [])) < line_limit for page in pages[:-1]):
            failures.append("存在非末页行数不足")
        if any(item.get("status") == "fail" for item in audit_items):
            failures.append("源码审计包含 fail")
        warnings.extend(item.get("detail", item.get("name", "")) for item in audit_items if item.get("status") == "warn")
        rendered = manifest.get("rendered", [])
        if not rendered or not any((self.workspace / path).is_file() and (self.workspace / path).stat().st_size > 0 for path in rendered):
            failures.append("没有非空渲染 DOCX/TXT")
        return {
            "ok": not failures, "backend": manifest.get("backend"), "failures": failures,
            "warnings": warnings, "artifact_count": len(required) + len(rendered),
            "reason": "源码材料门禁通过" if not failures else "; ".join(failures),
        }

    def check_figure_health(self) -> dict:
        """Check declared PNG figures are non-empty and decodable when Pillow is available."""
        figures_dir = self.workspace / "figures"
        figures = sorted(figures_dir.glob("*.png")) if figures_dir.is_dir() else []
        if not figures:
            return {"ok": False, "invalid": [], "reason": "未找到 PNG 图表"}
        invalid = []
        try:
            from PIL import Image
        except ImportError:
            Image = None
        for path in figures:
            if path.stat().st_size == 0:
                invalid.append(path.relative_to(self.workspace).as_posix())
                continue
            if Image is not None:
                try:
                    with Image.open(path) as image:
                        image.verify()
                except Exception:
                    invalid.append(path.relative_to(self.workspace).as_posix())
        return {"ok": not invalid, "invalid": invalid, "fig_count": len(figures),
                "reason": "PNG 图表可读" if not invalid else f"PNG 图表无效: {', '.join(invalid)}"}

    def check_figures(self) -> dict:
        """检查图表是否生成"""
        figures = list((self.workspace / "figures").glob("*.png")) if (self.workspace / "figures").exists() else []
        fig_count = len(figures)
        ok = fig_count >= 1
        return {"ok": ok, "fig_count": fig_count,
                "reason": f"生成了 {fig_count} 张图 {'✅' if ok else '❌ 至少 1 张'}"}

    def run_all(self, skill_name: str, declared_outputs=None, comp_name: str = "", requires_figures: bool = False,
                required_checks: list[str] | None = None, primary_output=None) -> dict:
        """运行所有门禁检查"""
        # Keep the existing positional ``run_all(skill, comp_name)`` call valid.
        if isinstance(declared_outputs, str) and not comp_name:
            comp_name = declared_outputs
            declared_outputs = None
        results = {}
        if declared_outputs is not None:
            artifact_result = ArtifactManifest.validate(self.workspace, declared_outputs)
            results["artifacts"] = {
                "ok": artifact_result["ok"],
                "missing": artifact_result["missing"],
                "invalid": artifact_result["invalid"],
                "reason": "声明产出齐全且哈希匹配" if artifact_result["ok"] else "声明产出校验失败",
            }
            primary = primary_output
            if primary is None:
                primary = declared_outputs[0] if declared_outputs else None
            if isinstance(primary, dict):
                primary = primary.get("path")
            results["min_size"] = self.check_min_size(skill_name, primary)
            results["companions"] = self.check_companions(skill_name)
        else:
            results["min_size"] = self.check_min_size(skill_name, None)
            results["companions"] = self.check_companions(skill_name)
        results["figures"] = self.check_figure_health() if requires_figures else {
            "ok": True, "skipped": True, "reason": "未声明需要图表检查"
        }
        if comp_name:
            results["paper_pages"] = self.check_paper_pages(comp_name)
        named_checks = {
            "literature": self.check_literature_evidence,
            "literature_search": lambda: self.check_literature_evidence(require_citations=False),
            "review": self.check_review_evidence,
            "consistency": self.check_consistency_evidence,
            "final_audit": self.check_final_audit_report,
            "source_materials": self.check_source_materials,
        }
        # M1 FIX: 审核类技能即使模板未声明 required_checks，也必须自动跑 review gate——
        # 否则 comp_mcm 等 21 个无 required_checks 模板的审稿步骤门禁从不执行，
        # 审稿证据缺失/伪造不会被发现。
        review_skills = {"comp-review", "comp-visual-review", "comp-final-review"}
        effective_checks = list(required_checks or [])
        if skill_name in review_skills and "review" not in effective_checks:
            effective_checks.append("review")
        for name in effective_checks:
            if name not in named_checks:
                results[f"required_{name}"] = {"ok": False, "reason": f"未知质量门禁: {name}"}
            else:
                results[name] = named_checks[name]()
        all_ok = all(r["ok"] for r in results.values())
        return {"ok": all_ok, "checks": results}


# =====================================================
# P5: 多角色 Agent
# =====================================================

class RoleAgent:
    """多角色 Agent — 执行者/审稿人/编辑器"""

    # 角色配置
    ROLES = {
        "executor": {
            "desc": "执行者：完成主要工作",
            "system": "你是科研执行者，负责完成建模、写作、代码等主要工作。产出必须完整、准确、可复现。",
        },
        "reviewer": {
            "desc": "审稿人：审查产出质量",
            "system": "你是资深审稿人，负责从方法、逻辑、格式、完整性多维度审查论文/产出。找出具体问题并给出修改建议。",
        },
        "editor": {
            "desc": "编辑器：润色修改",
            "system": "你是学术编辑，负责根据审稿意见润色修改论文。保留原意，提升表达质量，确保引用和数据准确。",
        },
    }

    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or env_get("OPENAI_API_KEY") or env_get("SENSENOVA_API_KEY")
        self.base_url = base_url or env_get("OPENAI_BASE_URL") or env_get("SENSENOVA_BASE_URL")
        self.model = model or env_get("REVIEWER_MODEL_ID") or env_get("SENSENOVA_MODEL") or "deepseek-v4-flash"

    def call(self, role: str, prompt: str, system: str = "") -> str:
        """调用 LLM 执行角色任务"""
        if role not in self.ROLES:
            raise ValueError(f"未知角色: {role}")
        sys_prompt = system or self.ROLES[role]["system"]
        return self._call_llm(sys_prompt, prompt)

    def _call_llm(self, system: str, prompt: str) -> str:
        """调用 OpenAI 兼容 API（支持推理模型）。

        韧性设计（解决"全局配额只够一次审核、复核失败"）：
        1. 429/5xx 指数退避重试（3 次）
        2. 主 provider 失败后按 .env 配置顺序 fallback 到备用 provider
        """
        if not self.api_key:
            # 回退：用 reviewer_client.py（其 call_api 自带重试）
            return self._call_reviewer_client(prompt, system)
        import http.client, json as _json
        import time as _time
        from urllib.parse import urlparse as _urlparse

        # provider 候选：当前配置优先，随后尝试 SENSENOVA / AGNES 备用
        candidates = []
        if self.base_url and self.api_key:
            candidates.append((self.base_url, self.api_key, self.model))
        for key, base, model in (
            ("OPENAI_BASE_URL", "OPENAI_API_KEY", "REVIEWER_MODEL_ID"),
            ("SENSENOVA_BASE_URL", "SENSENOVA_API_KEY", "SENSENOVA_MODEL"),
            ("AGNES_BASE_URL", "AGNES_API_KEY", "AGNES_MODEL"),
        ):
            b, k, m = env_get(key), env_get(base), env_get(model)
            if b and k:
                candidates.append((b, k, m or self.model))

        last_error = None
        for base_url, api_key, model in candidates:
            try:
                parsed = _urlparse(base_url)
                host = parsed.hostname
                path = (parsed.path or "").rstrip("/")
                if not path.endswith("/chat/completions"):
                    path = path + "/chat/completions"
                scheme = parsed.scheme or "https"
                conn_method = getattr(http.client, "HTTPSConnection" if scheme == "https" else "HTTPConnection")
                payload = _json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "max_tokens": 4000,
                })
                # 429/5xx 指数退避重试（最多 3 次）
                for attempt in range(3):
                    conn = conn_method(host)
                    try:
                        conn.request("POST", path, payload, {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        })
                        resp = conn.getresponse()
                        data = resp.read()
                        if resp.status == 429 or resp.status >= 500:
                            last_error = RuntimeError(f"HTTP {resp.status} from {base_url}")
                            if attempt < 2:
                                _time.sleep(2.0 * (2 ** attempt))
                                continue
                            raise last_error
                        result = _json.loads(data.decode("utf-8"))
                        break
                    finally:
                        conn.close()
                # 支持 reasoning 模型（content 为空时读 reasoning 字段）
                if "choices" in result and result["choices"]:
                    msg = result["choices"][0].get("message", {})
                    content = msg.get("content") or ""
                    if not content.strip():
                        content = msg.get("reasoning") or msg.get("reasoning_content") or ""
                    return content
                return str(result)[:500]
            except Exception as exc:
                last_error = exc
                continue
        raise last_error if last_error else RuntimeError("所有 LLM provider 均调用失败")

    def _call_reviewer_client(self, prompt: str, system: str) -> str:
        """回退到 reviewer_client.py"""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "reviewer_client.py"),
             "--prompt", prompt, "--system", system],
            capture_output=True, text=True, timeout=600)
        return result.stdout.strip() or result.stderr


# =====================================================
# P6: 视觉能力
# =====================================================

class VisionAgent:
    """视觉能力 — 用 Vision LLM 分析图片"""

    def __init__(self, api_key="", base_url="", model="gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        self.model = model

    def describe_image(self, image_path: str, context: str = "") -> str:
        """用 Vision 描述图片内容"""
        import base64, http.client, json as _json
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        mime = "image/png" if image_path.endswith(".png") else "image/jpeg"
        parsed = self.base_url.replace("https://", "").replace("http://", "").rstrip("/")
        scheme = "https" if "https://" in self.base_url else "http"
        conn_method = getattr(http.client, f"HTTPSConnection" if scheme == "https" else "HTTPConnection")
        conn = conn_method(parsed)
        payload = _json.dumps({
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"描述这张科研图表的内容。{context}"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
        })
        conn.request("POST", "/v1/chat/completions", payload, {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        data = _json.loads(resp.read().decode("utf-8"))
        conn.close()
        return data["choices"][0]["message"]["content"]

    def check_figure_quality(self, image_path: str) -> dict:
        """检查图表质量（重叠/截断/美观）"""
        # 优先用本地 tikz_vision_check.py
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "tikz_vision_check.py"), image_path],
            capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return {"ok": True, "verdict": result.stdout.strip()}
        # 回退到 Vision LLM
        desc = self.describe_image(image_path, "检查是否有文字截断、重叠、空白过多等问题。若正常回 PASS，有问题逐条列出。")
        return {"ok": "PASS" in desc.upper(), "verdict": desc}


# =====================================================
# P7: 编辑器 AI
# =====================================================

class EditorAgent:
    """编辑器 AI — 自动润色修改"""

    def __init__(self, api_key="", base_url="", model="gpt-4o"):
        self.role = RoleAgent(api_key, base_url, model)

    def polish(self, content: str, style: str = "学术") -> str:
        """润色内容"""
        prompt = f"请按照{style}风格润色以下内容，保留原意，提升表达质量：\n\n{content}"
        return self.role.call("editor", prompt)

    def apply_review_fixes(self, content: str, review: str) -> str:
        """根据审查意见修改内容"""
        prompt = f"根据以下审查意见修改内容。逐条处理，保留原文合理的部分：\n\n=== 审查意见 ===\n{review}\n\n=== 原文 ===\n{content}"
        return self.role.call("editor", prompt)


# =====================================================
# CLI 入口
# =====================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="科研系统能力封装（门禁/多角色/视觉/编辑）")
    sub = parser.add_subparsers(dest="cmd")

    # 能力检测
    sub.add_parser("caps", help="检测环境可用能力")

    # P4: 门禁
    gate = sub.add_parser("gate", help="质量门禁检查")
    gate.add_argument("workspace", help="工作区路径")
    gate.add_argument("--skill", default="", help="技能名")
    gate.add_argument("--comp", default="", help="竞赛名")

    # P5: 多角色
    role = sub.add_parser("role", help="多角色调用")
    role.add_argument("role", choices=["executor", "reviewer", "editor"])
    role.add_argument("prompt", help="提示词")
    role.add_argument("--system", default="", help="系统提示")

    # P6: 视觉
    vision = sub.add_parser("vision", help="图片分析")
    vision.add_argument("image", help="图片路径")
    vision.add_argument("--context", default="", help="上下文")

    args = parser.parse_args()

    if args.cmd == "caps":
        caps = detect_capabilities()
        print(json.dumps(caps, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "gate":
        g = QualityGate(args.workspace)
        result = g.run_all(args.skill, args.comp)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    if args.cmd == "role":
        agent = RoleAgent()
        result = agent.call(args.role, args.prompt, args.system)
        print(result)
        return 0

    if args.cmd == "vision":
        v = VisionAgent()
        result = v.describe_image(args.image, args.context)
        print(result)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
