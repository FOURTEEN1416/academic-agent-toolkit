#!/usr/bin/env python3
"""P4+P5+P6+P7 统一能力封装
quality_gates.py — 质量门禁系统 + 多角色 Agent + 视觉能力 + 编辑器 AI
"""
from __future__ import annotations
import os, sys, json, re, subprocess, hashlib
from datetime import datetime, timezone
import pymupdf as _fitz  # 不用 `import fitz`：兼容 shim 会向 stdout 打 deprecation 警告，污染 CLI 纯 JSON 契约（CI run 35708105058 实测）
from pathlib import Path

# 确保 engine 目录在 sys.path（CLI 直接运行时）
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
if str(_ENGINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR.parent))

try:
    from .artifact_manifest import ArtifactManifest
    from .step_manifest import validate_manifest as _validate_step_manifest
except ImportError:
    try:
        from artifact_manifest import ArtifactManifest
        from step_manifest import validate_manifest as _validate_step_manifest
    except ImportError:
        from engine.artifact_manifest import ArtifactManifest
        from engine.step_manifest import validate_manifest as _validate_step_manifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
RULES_FILE = PROJECT_ROOT / "engine" / "modex-core" / "comp_rules.json"
GATES_FILE = PROJECT_ROOT / "engine" / "modex-core" / "quality_gates.json"

# =====================================================
# 审稿角色 → 配置模型 解析（软校验用）
# 宿主中立（2026-09-09 用户裁定：不预设任何视觉/LLM 模型，比赛时再配置；
# 2026-09-20 泛化改造：可选宿主适配器不再是硬回退）：
#   1. ACAT_CONTEST_MODELS 环境变量指向的 JSON（最高，测试/临时注入用）
#   2. engine/modex-core/contest_models.json（仓库内竞赛配置槽，比赛时填写）
#   3. agents/adapters/*/models.json（任意宿主/通道可声明角色模型）
#   4. 可选宿主 agent 目录中的 *.md model: 行（.opencode/.claude/agents/roles 等）
# 皆空 → 该角色无配置模型，strict 比对降级为跳过（warn 不阻断）。
# =====================================================
ROLE_AGENT_FILES = {
    "reviewer": "数模审稿人.md",
    "visual_reviewer": "数模视觉审查.md",
    "editor": "数模编辑.md",
    "final_reviewer": "数模专家.md",
}

CONTEST_MODELS_FILE = RULES_FILE.parent / "contest_models.json"

# 可选宿主适配器的 agent 定义目录（均非驱动前提）。
# OPENCODE_AGENTS_DIR 保留兼容旧测试/部署；ACAT_ADAPTER_AGENTS_DIRS 可追加自定义目录（os.pathsep 分隔）。
OPENCODE_AGENTS_DIR = os.environ.get(
    "OPENCODE_AGENTS_DIR",
    str(PROJECT_ROOT.parent / ".opencode" / "agents"),
)


def _optional_adapter_agents_dirs() -> list[Path]:
    """收集可选适配器的 agent 定义目录。

    - 显式设置 `ACAT_ADAPTER_AGENTS_DIRS` 或 `OPENCODE_AGENTS_DIR` 时：只用显式列表
      （测试/部署可完全屏蔽仓库内可选宿主目录，避免“配置了却仍读到默认宿主”的污染）。
    - 未显式设置时：自动发现常见可选宿主目录（仍非驱动前提）。
    """
    dirs: list[Path] = []
    env_extra = os.environ.get("ACAT_ADAPTER_AGENTS_DIRS", "").strip()
    explicit_opencode = os.environ.get("OPENCODE_AGENTS_DIR", "").strip()

    if env_extra:
        for part in env_extra.split(os.pathsep):
            part = part.strip()
            if part:
                dirs.append(Path(part))

    if explicit_opencode:
        dirs.append(Path(explicit_opencode))
        return _unique_paths(dirs)

    dirs.append(Path(OPENCODE_AGENTS_DIR))
    repo = PROJECT_ROOT.parent
    for candidate in (
        repo / ".opencode" / "agents",
        repo / ".claude" / "agents",
        repo / "agents" / "roles",
    ):
        dirs.append(candidate)
    return _unique_paths(dirs)


def _unique_paths(dirs: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def _adapter_models_json() -> dict[str, str]:
    """读取 agents/adapters/*/models.json 中的 roles 字段。"""
    adapters_dir = PROJECT_ROOT.parent / "agents" / "adapters"
    merged: dict[str, str] = {}
    if not adapters_dir.is_dir():
        return merged
    for path in sorted(adapters_dir.glob("*/models.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        roles = data.get("roles") if isinstance(data, dict) else {}
        if not isinstance(roles, dict):
            continue
        for role in ROLE_AGENT_FILES:
            value = str(roles.get(role, "") or "").strip()
            if value and not merged.get(role):
                merged[role] = value
    return merged


def _parse_agent_model(agent_file: Path) -> str | None:
    """从 agent markdown frontmatter 解析 model 字段（provider/model 或 model）。"""
    try:
        text = agent_file.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^model:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _load_contest_models() -> dict[str, str]:
    """读取竞赛配置槽（仓库中立，宿主无关）。ACAT_CONTEST_MODELS 可指向替代文件。"""
    path = Path(os.environ.get("ACAT_CONTEST_MODELS", str(CONTEST_MODELS_FILE)))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    roles = data.get("roles", {}) if isinstance(data, dict) else {}
    return {r: str(roles.get(r, "") or "").strip() for r in ROLE_AGENT_FILES}


def load_configured_role_models() -> dict[str, str]:
    """四审稿角色的当前配置模型——宿主中立多级解析（见 ROLE_AGENT_FILES 上方注释）。

    竞赛配置槽优先；其后 adapters/*/models.json；最后可选宿主 agent 目录。
    返回 {角色: 模型}，无配置为空串。
    """
    contest = _load_contest_models()
    adapters = _adapter_models_json()
    result: dict[str, str] = {}
    for role in ROLE_AGENT_FILES:
        model = contest.get(role, "") or adapters.get(role, "")
        if not model:
            for agents_dir in _optional_adapter_agents_dirs():
                parsed = _parse_agent_model(agents_dir / ROLE_AGENT_FILES[role])
                if parsed:
                    model = parsed
                    break
        result[role] = model
    return result


def model_config_provenance() -> dict[str, str]:
    """报告每个角色配置模型的来源（contest/adapters/host_adapter/none），供审计与体检输出。"""
    contest = _load_contest_models()
    adapters = _adapter_models_json()
    out: dict[str, str] = {}
    for role, filename in ROLE_AGENT_FILES.items():
        if contest.get(role):
            out[role] = "contest_models"
            continue
        if adapters.get(role):
            out[role] = "adapters"
            continue
        source = "none"
        for agents_dir in _optional_adapter_agents_dirs():
            if _parse_agent_model(agents_dir / filename):
                source = "host_adapter"
                break
        out[role] = source
    return out


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


# =====================================================
# 审稿角色实际调用通道留痕（A6-F4 修复）
# RoleAgent 每次成功调用 LLM 后，把"角色→实际使用的 base_url/model"写进工作区
# sidecar（.engine/role_calls_actual.json）；check_review_evidence 的执行证据校验
# 据此交叉核对——fallback 备用通道产生的审稿输出，无法再伪装成主通道模型申报。
# =====================================================
ROLE_CALLS_SIDECAR = ".engine/role_calls_actual.json"


def record_role_call_actual(workspace: Path | str, role: str, base_url: str, model: str) -> None:
    """记录角色实际使用的调用通道（写工作区 sidecar；IO 失败不阻断主流程）。"""
    try:
        root = Path(workspace).resolve()
        sidecar = root / ROLE_CALLS_SIDECAR
        data: dict = {}
        if sidecar.is_file():
            try:
                loaded = json.loads(sidecar.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except json.JSONDecodeError:
                data = {}
        roles = data.get("roles") if isinstance(data.get("roles"), dict) else {}
        roles[role] = {
            "base_url": str(base_url),
            "model": str(model),
            "called_at": datetime.now(timezone.utc).isoformat(),
        }
        data["roles"] = roles
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# =====================================================
# 视觉人工复核记录校验（A7-M5 修复：宿主开不出独立视觉窗口时的受控降级路径）
# =====================================================
VISUAL_MANUAL_CHECK_FILE = "VISUAL_REVIEW_MANUAL_CHECK.md"
_MANUAL_CHECK_MIN_ITEMS = 5

# A7R-F1 防伪造红线：approved_by 必须是人类操作者署名。
# 命中下列任一 agent 自指词即判定"agent 伪造用户签名"，硬拦。
# 英文词：ASCII 字母边界匹配（避免子串误伤，如 said/rain 不因含 "ai" 被拦，
# ragent/Baier 不因含 "agent"/"ai" 被拦；CJK 相邻不算边界内字母，"AI审稿"照样命中）；
# 中文词：子串匹配（中文无词边界概念）。名单与 SKILL.md 降级预案小节保持一致。
_MANUAL_CHECK_AGENT_WORDS_EN = (
    # agent/AI 自指词
    "agent", "ai", "bot", "llm", "auto",
    # 常见模型/厂商名（含国内外主流模型族；命中任一即视为模型自署）
    "glm", "agnes", "gpt", "chatgpt", "openai", "anthropic", "claude",
    "gemini", "deepseek", "sensenova", "sense", "qwen", "kimi", "doubao",
    "ernie", "hunyuan", "llama", "mistral", "copilot", "zhipu",
    "opencode", "zcode",
)
_MANUAL_CHECK_AGENT_WORDS_CJK = ("机器人", "智能体", "自动")
# 2026-09-22 G3 实跑补漏：边界匹配让 "subagent"（agent 前紧邻字母 b）逃逸，
# 而它恰是子代理署名高频词——按无边界子串单列（ragent/Baier 不受影响）。
_MANUAL_CHECK_AGENT_WORDS_EN_SUBSTR = ("subagent", "multi-agent", "multiagent")


def _agent_self_reference_hit(approved_by: str) -> str:
    """approved_by 命中 agent 自指词时返回命中的词，未命中返回空串。"""
    lowered = approved_by.lower()
    for word in _MANUAL_CHECK_AGENT_WORDS_EN_SUBSTR:
        if word in lowered:
            return word
    for word in _MANUAL_CHECK_AGENT_WORDS_EN:
        # ASCII 字母边界：两侧不得紧邻英文字母（数字相邻视为独立 token，可命中
        # "gpt4"/"qwen2.5" 这类无连字符模型写法）
        pattern = r"(?<![a-z])" + re.escape(word) + r"(?![a-z])"
        if re.search(pattern, lowered):
            return word
    for word in _MANUAL_CHECK_AGENT_WORDS_CJK:
        if word in approved_by:
            return word
    return ""


def validate_visual_manual_check(path: Path) -> dict:
    """校验人工复核记录（VISUAL_REVIEW_VERDICT.status=manual_review 的放行条件）。

    合法条件（全部满足才放行）：
      1. 文件存在；
      2. 含非空 `approved_by:` 行，且**不含 agent 自指词**（agent/ai/bot/llm/auto/
         机器人/智能体/自动 及模型名 glm/agnes/gpt/deepseek/sense/claude 等——
         英文词按 ASCII 字母边界匹配、中文词按子串匹配）。命中即硬拦：
         人工复核必须由人类操作者本人署名，agent/AI/机器人/模型名署名视同伪造审核证据；
      3. 含 ≥5 条 `- [x]` 逐项检查记录（对应视觉检查单逐项人工目检后勾选）。
    """
    if not path.is_file():
        return {"ok": False,
                "reason": (f"status=manual_review 需要 {VISUAL_MANUAL_CHECK_FILE} 人工复核记录。"
                           "正确格式（Markdown）:\n"
                           "  approved_by: 用户姓名\n"
                           "  ## 逐项检查\n"
                           "  - [x] 坐标轴名称与单位可读\n"
                           "  - [x] 图例完整且不遮挡曲线\n"
                           "  （……逐项检查记录至少 5 条，对应 SKILL 视觉检查单）")}
    text = path.read_text(encoding="utf-8", errors="ignore")
    approved = re.search(r"(?im)^[ \t]*approved_by[ \t]*:[ \t]*(\S.+)$", text)
    if not approved or not approved.group(1).strip():
        return {"ok": False,
                "reason": (f"{VISUAL_MANUAL_CHECK_FILE} 缺少非空 approved_by 行"
                           "（批准人必须为用户本人，禁止填 agent）。正确格式: approved_by: 用户姓名")}
    approved_by = approved.group(1).strip()
    hit = _agent_self_reference_hit(approved_by)
    if hit:
        return {"ok": False,
                "reason": (f"{VISUAL_MANUAL_CHECK_FILE} 的 approved_by 命中 agent 自指词「{hit}」"
                           "——人工复核必须由人类操作者本人署名，agent/AI/机器人/模型名署名一律硬拦"
                           "（视同伪造审核证据）。正确写法: approved_by: 操作者真实姓名（如 默默），"
                           "不要带 agent/AI/bot/llm/auto/机器人/模型名等字样")}
    items = re.findall(r"(?m)^\s*[-*]\s*\[[xX]\]", text)
    if len(items) < _MANUAL_CHECK_MIN_ITEMS:
        return {"ok": False,
                "reason": (f"{VISUAL_MANUAL_CHECK_FILE} 逐项检查记录不足: 仅 {len(items)} 条 `- [x]`，"
                           f"需 ≥{_MANUAL_CHECK_MIN_ITEMS} 条（按视觉检查单逐项人工目检后勾选）")}
    return {"ok": True, "approved_by": approved_by, "items": len(items)}


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
    "comp-problem-analysis": 1500, "comp-modeling": 2000, "comp-code": 1000,
    "comp-review": 40, "comp-statistics-topic": 1000, "comp-paper-zh": 10000,
    "comp-paper-en": 10000, "paper-write": 15000, "paper-write-zh": 15000,
    "paper-plan": 3000, "literature-review": 5000, "idea-discovery": 3000,
}

DEFAULT_REQUIRED_COMPANIONS = {
    "comp-code": ["code/main.py", "figures/all_results.json"],
    "paper-analysis": ["RESULTS.md", "figures/all_results.json", "code/main.py"],
}

# 竞赛页数第二真源 COMP_PAGES 已删除（B窗 B-02，2026-09-27；承接 IR-E-B1）：
# 页数口径唯一来自 comp_rules.json（经 engine/contest_profile）+ 工作流快照
# operative 口径；条目缺口径时按"无页数合同"SKIP，不静默吐旧值、不默认国赛。


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
        import matplotlib  # noqa: F401 — 可用性探测，非使用
        caps["matplotlib"] = True
    except ImportError:
        pass
    try:
        import seaborn  # noqa: F401 — 可用性探测，非使用
        caps["seaborn"] = True
    except ImportError:
        pass
    try:
        from PIL import Image  # noqa: F401 — 可用性探测，非使用
        caps["pillow"] = True
    except ImportError:
        pass
    # 4. API Key（仅出图类；视觉审核已换驱动：宿主独立窗口执行，不做 key 探测）
    if env_get("GPT_IMAGE_API_KEY"):
        caps["gpt_image_api"] = True
    return caps


def _load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _moderate_number(value: float) -> bool:
    """过滤明显不是"结果数字"的值：日期/脚注/页码等小整数与天文数字。"""
    return abs(value) >= 0.001 and abs(value) < 1e12


def _collect_numbers(payload) -> list[float]:
    """递归收集 JSON 中的 int/float 数值（忽略 NaN/Inf）。"""
    numbers: list[float] = []
    if isinstance(payload, dict):
        for value in payload.values():
            numbers.extend(_collect_numbers(value))
    elif isinstance(payload, list):
        for value in payload:
            numbers.extend(_collect_numbers(value))
    elif isinstance(payload, (int, float)) and not isinstance(payload, bool):
        try:
            numbers.append(float(payload))
        except (TypeError, ValueError):
            pass
    return numbers


def _number_candidates(value: float) -> list[str]:
    """生成论文正文里可能出现的关键数字书写形式（原值/整数值/4位/2位小数）。"""
    if value != value or value in (float("inf"), float("-inf")):  # NaN/Inf
        return []
    candidates = [str(value)]
    if float(value).is_integer():
        candidates.append(str(int(value)))
    for digits in (4, 2):
        rounded = round(value, digits)
        if rounded != value:
            candidates.append(str(rounded))
    return candidates


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
    """获取竞赛规则（B窗 2026-09-27：代理唯一解析器 engine.contest_profile，
    本文件不再直接读档案文件）。未知名称返回 {}（非赛事步骤不启用赛事检查；
    显式错误路径由 contest_profile.resolve_profile 承担）。"""
    from . import contest_profile
    try:
        return contest_profile.load_entry(comp_name)
    except contest_profile.ContestProfileError:
        return {}


# =====================================================
# P4: 质量门禁检查
# =====================================================

# 命名门禁注册表（单一真相源）：
# 迁移脚本 / 模板校验读取这个集合，防止引用不存在的门禁。
# 值 = QualityGate 的实例方法名（run_all 内解析绑定方法）。
NAMED_CHECKS_REGISTRY: dict[str, str] = {
    "literature": "check_literature_evidence",
    "literature_search": "_check_literature_search",
    "review": "check_review_evidence",
    "consistency": "check_consistency_evidence",
    "final_audit": "check_final_audit_report",
    "source_materials": "check_source_materials",
    "step_manifest": "check_step_manifest",
    "paper_consistency": "check_paper_consistency",
    "citation_integrity": "check_citation_integrity",
    "experiment_reproduc": "check_experiment_reproduc",
    "figure_provenance": "check_figure_provenance",
    "compilation_log": "check_compilation_log",
    "modeling_contract": "check_modeling_contract",
    "review_rounds": "check_review_rounds",
}


TEX_TARGET_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def assembly_faces(main_tex: Path) -> list[Path]:
    r"""主 tex 之外真正被装配进去的分章文件（体量与引用两道判据共用的同一个计量面）。

    原实现只认 `sections/` 目录约定；扁平布局（`\input{01_xxx}` 与 main.tex 同目录）
    会让判据只看到装配壳，把合格论文误判为过薄、把有引用的正文误判为无引用。
    这里按 main.tex 的 \input/\include 实测取文件，阈值不变，只修正计量面。
    取数限制在主 tex 所在目录子树内：装配面不得被用来读工作区其他位置的文件。
    """
    root = Path(main_tex).parent
    faces: dict[Path, None] = {}
    try:
        text = Path(main_tex).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    targets = [t.strip().replace("\\", "/") for t in TEX_TARGET_RE.findall(text)]
    targets += [p.name for p in sorted((root / "sections").glob("*.tex"))]
    for name in targets:
        if not name or ".." in Path(name).parts:
            continue
        cand = root / (name if name.endswith(".tex") else name + ".tex")
        try:
            resolved = cand.resolve()
            if resolved.is_file():
                resolved.relative_to(root.resolve())
            else:
                continue
        except (OSError, ValueError):
            continue
        faces.setdefault(resolved, None)
    return list(faces)


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
                # 模块化论文（main.tex + sections/*.tex）：正文体量在分章文件里，
                # 仅计主文件会把合格论文误判为过薄（阈值不变，只修正计量面）。
                if output_path.suffix == ".tex":
                    # 装配面 = main.tex 实测 \input 进来的分章 + sections/*.tex（两条约定并集，去重）
                    size += sum(p.stat().st_size for p in assembly_faces(output_path))
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

    def check_paper_pages(self, comp_name: str, paper_dir: str = "paper",
                          page_contract: dict | None = None) -> dict:
        """Enforce a competition page upper bound, with body-only semantics for CUMCM.

        B-02：口径优先来自工作流快照的 operative 合同（cap/scope/status 单一事实）；
        无合同时回落档案条目（不启用任何兜底字典）。scope 决定判总页数还是正文页数；
        性质（verified/unverified/task_override）随结果携带，供终审区分结论与未知。
        """
        rules = {}
        if page_contract is not None:
            cap = page_contract.get("cap")
            status = page_contract.get("status") or "unverified"
            if not cap:
                return {"ok": True, "skipped": True, "page_cap_status": status,
                        "reason": page_contract.get("reason") or "该赛事无页数合同（不默认任何口径）"}
        else:
            rules = get_comp_rules(comp_name)
            cap = rules.get("max_pages")
            status = "unverified"
            if not cap:
                return {"ok": True, "skipped": True, "page_cap_status": "none",
                        "reason": f"竞赛 {comp_name} 无页数合同（不默认任何口径）"}
        scope = str(page_contract.get("scope")) if page_contract else (rules.get("page_scope") or None)
        pdf = self.workspace / paper_dir / "main.pdf"
        tex = self.workspace / paper_dir / "main.tex"
        result_scope_tag = {"page_cap_status": status, "page_cap_scope": scope}
        if pdf.exists():
            if scope == "body":
                out = self._check_body_pages(pdf, cap)
            else:
                out = self._check_total_pdf_pages(pdf, cap)
            return {**out, **result_scope_tag}
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
            ok = estimated_pages <= cap
            return {**{"ok": ok, "estimated_pages": estimated_pages, "max_pages": cap,
                       "reason": f"LaTeX 估算约 {estimated_pages} 页（上限 {cap} 页，PDF 未生成）"
                                 f"{'✅' if ok else '❌ 请先编译 PDF 确认页数'}"}, **result_scope_tag}
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

        First page = summary (摘要 / Abstract / 引言). Body = pages between the
        body-start marker and 附录/Appendix. Appendix (and later) is unlimited.

        Fail-closed (FIX academic-agent-toolkit HIGH): when no body-start
        keyword is found, body_count stays 0 and the old implementation
        silently returned ok=True — a missing-摘要 English paper would bypass
        the body page cap. Now:
          - no start keyword → ok=False, reason=body_pages_unknown_no_abstract
          - start keyword found but body_count==0 → ok=False (unverified body
            extent; do not claim a page-cap pass)
          - alternative start markers (Abstract/ABSTRACT/引言/Introduction)
            are accepted so bilingual/English papers still get a real count
        """
        # Alternative body-start markers (English / 引言) — allowed only as a
        # real page-count path, never as a silent zero-count pass.
        start_keywords = ("摘要", "Abstract", "ABSTRACT", "引言", "Introduction")
        # 2026-09-25 TOOLFIX-C9（终止侧）：裸「附录」子串匹配会命中正文行文
        # （实证：摘要页「按附录无线传输模型」、正文「按附录3判定」），导致
        # body_count==0 的 fail-closed 误拦。终止判定改为页首锚定（归一化后
        # 页面文本以「附录」开头 = 附录标题页）+「附录A/B」式编号标题兜底。
        end_prefixes = ("附录", "Appendix", "APPENDIX")
        end_re = re.compile(r"附录[A-ZＡ-Ｚ]|Appendix|APPENDIX")
        try:
            doc = _fitz.open(str(pdf))
        except ImportError:
            return {"ok": False, "reason": "fitz (PyMuPDF) 不可用，无法统计正文页数"}
        try:
            pages = doc.page_count
            body_start = False
            body_count = 0
            start_marker = None
            for i in range(pages):
                # 2026-09-25 TOOLFIX-C9：gmcmthesis 等模板把「摘要」排成「摘　要：」
                # （\qquad 撑开字距），抽取文本中关键词不连续，naive 匹配永远失配 →
                # fail-closed 误拦（body_pages_unknown_no_abstract）。
                # 修复：关键词匹配前做空白归一化；fail-closed 语义不变。
                text = re.sub(r"\s+", "", doc[i].get_text()).strip()
                if not body_start:
                    for kw in start_keywords:
                        if kw in text:
                            body_start = True
                            start_marker = kw
                            break
                    continue
                if text.startswith(end_prefixes) or end_re.search(text):
                    break
                body_count += 1
        finally:
            doc.close()

        if not body_start:
            return {
                "ok": False,
                "body_pages": 0,
                "total_pages": pages,
                "max_body": max_body,
                "reason": "body_pages_unknown_no_abstract",
                "detail": (
                    "PDF 全文未检出「摘要/Abstract/引言」正文起始关键词，"
                    "正文页范围不可界定；门禁 fail-closed（勿静默放行）。"
                    "请提供含英文 Abstract 的版本，或人工复核正文页数后"
                    "在 execution_evidence 中标注。"
                ),
            }
        if body_count == 0:
            return {
                "ok": False,
                "body_pages": 0,
                "total_pages": pages,
                "max_body": max_body,
                "start_marker": start_marker,
                "reason": "body_pages_unknown_no_abstract",
                "detail": (
                    f"检出正文起始关键词「{start_marker}」但其后未统计到正文页"
                    f"（total_pages={pages}）；正文页数未核验，门禁 fail-closed。"
                    "请人工复核或提供可解析的正文结构（摘要→附录）。"
                ),
            }
        ok = body_count <= max_body
        return {
            "ok": ok,
            "body_pages": body_count,
            "total_pages": pages,
            "max_body": max_body,
            "start_marker": start_marker,
            "reason": f"正文 {body_count} 页（上限 {max_body} 页）{'✅' if ok else '❌'}",
        }

    def _check_literature_search(self) -> dict:
        """文献检索证据门禁（不要求论文已写完成的引用闭环）。"""
        return self.check_literature_evidence(require_citations=False)

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
            # 模块化论文：引用命令写在被装配进去的分章文件里，拼接后统一识别。
            # 与体量判据共用 assembly_faces，避免两处尺子读到不同的面。
            for sec in assembly_faces(tex):
                content += "\n" + sec.read_text(encoding="utf-8", errors="ignore")
            # \upcite 为 cumcmthesis 等模板的上标引用包装（展开为 \cite），计入合法引用
            citations = re.findall(r"\\(?:cite|citep|citet|upcite)\{[^}]+\}", content)
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

    def check_review_evidence(self, mode: str = "auto", strict_model_match: bool = False) -> dict:
        """Require reviewer, visual reviewer, editor, and fatal-free final verdicts.

        mode:
          "full"  — require all 7 files + REVIEW_EXECUTION_EVIDENCE.json (multi-role closed)
          "solo"  — require COMP_REVIEW.md + COMP_REVIEW_VERDICT.json only (single-person)
          "visual" — require the visual pair (VISUAL_REVIEW.md/VERDICT)；COMP 对存在任一成员时
                     也必须完整并校验。不要求 editor/final 产物（属第 12/13 步，尚未发生）。
                     供 comp-visual-review 步骤（第 11 步）使用。
          "auto"  — 按工作区时序解析（A7-F1 死锁修复）:
                     * 全部 7 件齐 → full
                     * 任一 full 专属产物（EDITOR_CHANGELOG.md / FINAL_REVIEW.md /
                       FINAL_REVIEW_VERDICT.json / REVIEW_EXECUTION_EVIDENCE.json）存在 → full
                       （多角色审稿已启动，不允许静默降级）
                     * 视觉对完整 → visual（第 11 步完成时序：后续步骤产物尚未生成是正常的）
                     * 视觉对残缺 → full（"审稿只做了一半"不得降级，保持 M1 防线）
                     * 否则 → solo

        strict_model_match:
          False — evidence model != configured model is a warning only (default)
          True  — evidence model != configured model blocks the gate (for final delivery)
        """
        all_reports = ["COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"]
        all_verdicts = ["COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW_VERDICT.json", "FINAL_REVIEW_VERDICT.json"]
        provenance_name = "REVIEW_EXECUTION_EVIDENCE.json"
        solo_reports = ["COMP_REVIEW.md"]
        solo_verdicts = ["COMP_REVIEW_VERDICT.json"]
        visual_report, visual_verdict = "VISUAL_REVIEW.md", "VISUAL_REVIEW_VERDICT.json"
        # full 模式专属产物：只有第 12/13 步（编辑/终审）才会生成。它们的存在才能证明
        # 多角色审稿已真正启动——AUTO→FULL 的升级只由这些文件触发（A7-F1 根因修复：
        # 旧逻辑把 VISUAL_REVIEW.md 也当多角色证据，导致第 11 步永远缺第 12/13 步产物）。
        full_exclusive_files = [
            "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md", "FINAL_REVIEW_VERDICT.json",
            provenance_name,
        ]

        if mode == "auto":
            ws = self.workspace
            all_exist = all((ws / f).is_file() for f in all_reports + all_verdicts)
            visual_pair_complete = (ws / visual_report).is_file() and (ws / visual_verdict).is_file()
            visual_pair_partial = (ws / visual_report).is_file() or (ws / visual_verdict).is_file()
            if all_exist:
                mode = "full"
            elif any((ws / f).is_file() for f in full_exclusive_files):
                # full 专属产物已出现：多角色审稿已启动，缺件就是缺件，按 full 硬校验。
                mode = "full"
            elif visual_pair_complete:
                mode = "visual"
            elif visual_pair_partial:
                # 有任何多角色文件存在（部分完成的多角色审稿）时不允许静默降级，
                # 否则会掩盖"审稿只做了一半"的缺失。
                mode = "full"
            else:
                mode = "solo"

        if mode == "full":
            reports, verdicts = all_reports, all_verdicts
        elif mode == "visual":
            if any((self.workspace / f).is_file() for f in full_exclusive_files):
                # 视觉步骤完成时 editor/final 产物不应存在；出现即视为时序异常，
                # 按 full 硬校验（缺件会带完整缺失清单返回，不静默放过）。
                reports, verdicts = all_reports, all_verdicts
            else:
                reports, verdicts = [visual_report], [visual_verdict]
                # COMP 对已启动（任一成员存在）时必须完整并一并校验，防"前序审稿做一半"被跳过。
                comp_any = (self.workspace / "COMP_REVIEW.md").is_file() or (self.workspace / "COMP_REVIEW_VERDICT.json").is_file()
                if comp_any:
                    reports = solo_reports + reports
                    verdicts = solo_verdicts + verdicts
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
        sidecar_roles: dict = {}
        manual_review_notes: list[str] = []
        for name in verdicts:
            try:
                verdict = json.loads((self.workspace / name).read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"ok": False, "reason": f"审稿裁定不是有效 JSON: {name}"}
            has_findings = isinstance(verdict.get("findings"), list) or isinstance(verdict.get("findings_fixed"), list)
            if not has_findings or not isinstance(verdict.get("fatal_count"), int):
                return {"ok": False, "reason": f"审稿裁定字段不完整: {name}"}
            fatal_count += verdict["fatal_count"]
            # 视觉审查裁定必须携带 status（pass|fail|manual_review|unavailable）：
            # 视觉审核通道不可用而伪装成 pass 是典型造假路径，这里硬性拦截。
            if name == visual_verdict:
                status = verdict.get("status")
                if status not in ("pass", "fail", "unavailable", "manual_review"):
                    return {"ok": False, "fatal_count": fatal_count, "mode": mode,
                            "reason": (f"视觉审查裁定缺少有效 status 字段"
                                       f"（需 pass|fail|manual_review|unavailable）: {name}。"
                                       "正确示例: {\"findings\": [], \"fatal_count\": 0, \"status\": \"pass\"}")}
                if status == "manual_review":
                    # A7-M5 受控降级：宿主开不出独立视觉窗口 → 人工按检查单逐项目检，
                    # 记录 VISUAL_REVIEW_MANUAL_CHECK.md（approved_by 非空 + ≥5 条逐项记录）才放行。
                    manual_result = validate_visual_manual_check(self.workspace / VISUAL_MANUAL_CHECK_FILE)
                    if not manual_result["ok"]:
                        return {"ok": False, "fatal_count": fatal_count, "mode": mode,
                                "reason": f"视觉人工复核记录无效: {manual_result['reason']}"}
                    manual_review_notes.append(
                        f"视觉为 manual_review（人工复核放行，approved_by={manual_result['approved_by']}，"
                        f"{manual_result['items']} 条逐项记录）")
                elif status != "pass":
                    return {"ok": False, "fatal_count": fatal_count, "mode": mode,
                            "reason": f"视觉审查未通过（status={status}），终审不得放行: {name}。"
                                      "宿主开不出独立视觉窗口时的合法降级路径见 comp-visual-review SKILL.md"
                                      "（人工复核 → manual_review + VISUAL_REVIEW_MANUAL_CHECK.md）"}
        provenance_ok = True
        provenance_reason = ""
        provenance_warnings: list[str] = []
        if mode == "full" and not missing:
            # A6-F4：引擎侧实际调用通道留痕（RoleAgent 写入，存在时交叉核对）
            sidecar_roles: dict = {}
            sidecar_path = self.workspace / ROLE_CALLS_SIDECAR
            if sidecar_path.is_file():
                try:
                    loaded = json.loads(sidecar_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict) and isinstance(loaded.get("roles"), dict):
                        sidecar_roles = loaded["roles"]
                except (OSError, json.JSONDecodeError):
                    sidecar_roles = {}
            try:
                provenance = json.loads((self.workspace / provenance_name).read_text(encoding="utf-8"))
                roles = provenance.get("roles", {})
                required_roles = {"reviewer", "visual_reviewer", "editor", "final_reviewer"}
                if set(roles) != required_roles:
                    raise ValueError("角色集合不完整")
                sessions = []
                # 软校验：证据声明的模型 vs 配置模型（竞赛配置槽优先，宿主 agents 回退）
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
                    # 证据模型与 agent 配置比对
                    claimed = str(role.get("model", "")).strip()
                    configured = configured_models.get(role_name, "")
                    if configured and claimed and claimed != configured:
                        msg = f"{role_name}: 证据模型 {claimed!r} ≠ 配置模型 {configured!r}"
                        if strict_model_match:
                            raise ValueError(msg)
                        provenance_warnings.append(msg)
                    elif not configured and claimed:
                        # 仓库不预设模型（2026-09-09 裁定）：未配置时 strict 无从比对，
                        # 显式 warn 留痕——比赛时填 contest_models.json 后此闸自动恢复硬拦截。
                        provenance_warnings.append(
                            f"{role_name}: 无配置模型（contest_models.json 未填写且宿主无 agent 配置），"
                            f"模型比对跳过，证据声明为 {claimed!r}")
                    # A6-F4 硬校验：引擎记录的实际调用模型 vs 证据声明模型。
                    # fallback 备用通道产生的输出若被申报成主通道模型，在这里被拦
                    # （与配置串无关——记录值就是事实，不符即证据失实，一律硬拦）。
                    actual_record = sidecar_roles.get(role_name) if isinstance(sidecar_roles, dict) else None
                    if isinstance(actual_record, dict) and str(actual_record.get("model", "")).strip():
                        actual_model = str(actual_record["model"]).strip()
                        if claimed and actual_model != claimed:
                            raise ValueError(
                                f"{role_name}: 引擎记录的实际调用模型 {actual_model!r} ≠ 证据声明模型 {claimed!r}"
                                f"（来源 {ROLE_CALLS_SIDECAR}）——审稿输出疑似由未申报通道产生，证据不可信；"
                                f"请让证据 model 字段如实填写实际通道，或以实际通道重跑审稿")
                if len(set(sessions)) != len(sessions):
                    raise ValueError("审稿角色 session_id 不独立")
            except (json.JSONDecodeError, ValueError) as exc:
                provenance_ok = False
                provenance_reason = str(exc)
        ok = fatal_count == 0 and provenance_ok
        # 2026-09-09 独立审计修复：旧逻辑 warnings 非空时先占用 reason，
        # provenance 失败的真正原因（provenance_reason）被遮蔽 → ok=false 却显示"警告"文案，误导修复。
        if not ok:
            if not provenance_ok:
                reason = f"审稿执行证据无效: {provenance_reason}"
            else:
                reason = f"审稿闭环有 {fatal_count} 个 fatal ({mode} 模式)"
            if provenance_warnings:
                reason += f"（另有 {len(provenance_warnings)} 条模型配置警告）"
        elif provenance_warnings:
            reason = (f"审稿闭环无 fatal ({mode} 模式)，但存在模型配置不一致警告: "
                      + "; ".join(provenance_warnings))
        else:
            reason = f"审稿闭环无 fatal ({mode} 模式)"
        if ok and manual_review_notes:
            reason += "；" + "; ".join(manual_review_notes)
        # B窗 2026-09-27 收口4：实际调用事实采集状态独立披露。当前只有引擎内置
        # RoleAgent 通道自动采集；宿主独立评审通道尚无采集源——缺席时交叉核对
        # 无从执行，model/session 字段停留在申报值。显式记为 absent，不模拟通过。
        return {"ok": ok, "fatal_count": fatal_count, "mode": mode,
                "reason": reason, "warnings": provenance_warnings,
                "actual_call_capture": "captured" if sidecar_roles else
                    ("absent" if mode == "full" and not missing else "not_applicable")}

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
        delivery = self.workspace / "DELIVERY_REPORT.json"
        if not getattr(self, "_active_final_step_id", "") and delivery.is_file():
            path = delivery
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
        if not report["gate_outcomes"]:
            return {"ok": False,
                    "reason": ("最终审计报告 gate_outcomes 为空——最终审计未实际运行任何门禁。"
                               "请用 engine.audit_store.build_final_audit_report 生成报告，禁止手写")}
        # A2 补丁1：状态-事件一致性 named check（编排状态必须能被事件链解释）
        if report["gate_outcomes"].get("state_event_consistency") == "fail":
            return {"ok": False, "failed_gates": ["state_event_consistency"],
                    "reason": ("状态-事件一致性核查未通过：存在无 step_completed 事件的 completed 步骤，"
                               "或无 checkpoint_approved 事件的检查点步骤完成"
                               "（疑似绕过引擎直改 workflow.sqlite），"
                               "详见 AUDIT_REPORT.json 的 state_event_consistency_detail")}
        # A2 补丁2：防绕过检测 named check（检测结果已接入交付判定）
        if report["gate_outcomes"].get("operation_audit") == "fail":
            return {"ok": False, "failed_gates": ["operation_audit"],
                    "reason": ("防绕过检测未通过：存在工作区归属的未申报操作（bash/编辑）且已接入交付判定。"
                               "请在对应步骤 evidence 中申报真实命令与产物，或消除绕过操作；"
                               "详见 AUDIT_REPORT.json 的 operation_audit_detail")}
        # A2R 修复：waiver 不放行——skip_review 等 skip_ 豁免只留痕，交付一律 blocked。
        if report["gate_outcomes"].get("waiver_review") == "fail":
            return {"ok": False, "failed_gates": ["waiver_review"],
                    "reason": ("最终审计存在 skip_ 豁免参数（waivers 非空，详见 AUDIT_REPORT.json 的 "
                               "waiver_detail.hit_params）。豁免只留痕不放行：skip_review=true 会在启动时"
                               "静默删除审核步骤，审核防线从未运行过，交付一律 blocked。"
                               "解除方式：以不含 skip_ 参数的方式重新执行完整工作流"
                               "（审核类步骤必须真实完成，不可豁免）。")}
        failed_gates = [name for name, outcome in report["gate_outcomes"].items() if outcome != "pass"]
        if failed_gates:
            return {"ok": False, "failed_gates": failed_gates,
                    "reason": f"最终审计存在未通过门禁: {', '.join(failed_gates)}"}
        if report["delivery_decision"] != "ready":
            active = getattr(self, "_active_final_step_id", "")
            if not (report["delivery_decision"] == "eligible" and active
                    and report.get("pre_audit_step_id") == active):
                return {"ok": False, "reason": "最终交付决定不是 ready（eligible 仅可用于当前最终审计步骤验收）"}
        directories = report.get("directory_coverage", [])
        if not isinstance(directories, list):
            return {"ok": False, "reason": "最终审计目录覆盖字段无效"}
        verified = ArtifactManifest.validate_coverage(self.workspace, report["artifacts"], directories,
                                                      session=getattr(self, "_fingerprint_session", None))
        if not verified["ok"]:
            return {"ok": False, "reason": "最终审计产物已变化、缺失或越界", "missing": verified["missing"],
                    "invalid": verified["invalid"]}
        return {"ok": True, "artifact_count": len(report["artifacts"]), "reason": "最终审计报告产物与验收结论一致"}

    def check_source_materials(self) -> dict:
        """Validate the manifest-backed CodeSucker source-materials contract."""
        base = self.workspace / "source-materials"
        required = [
            "SOURCE_MATERIALS_MANIFEST.json",
            "files.json",
            "cleaned.json",
            "selection.json",
            "audit.json",
            "stats.json",
            "SOURCE_MATERIALS_REPORT.md",
        ]
        missing = [name for name in required if not (base / name).is_file()]
        if missing:
            return {"ok": False, "failures": missing, "warnings": [], "reason": f"缺少源码材料产物: {', '.join(missing)}"}
        try:
            manifest = json.loads((base / "SOURCE_MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
            files = json.loads((base / "files.json").read_text(encoding="utf-8")).get("files", [])
            cleaned = json.loads((base / "cleaned.json").read_text(encoding="utf-8")).get("cleaned", [])
            selection = json.loads((base / "selection.json").read_text(encoding="utf-8"))
            audit_items = json.loads((base / "audit.json").read_text(encoding="utf-8"))
            stats = json.loads((base / "stats.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "failures": [str(exc)], "warnings": [], "reason": "源码材料 JSON 无效"}
        failures, warnings = [], []
        if manifest.get("backend") != "vendored-codesucker-core":
            failures.append("backend 不是 vendored-codesucker-core")
        if manifest.get("schemaVersion") != 1:
            failures.append("manifest schemaVersion 不是 1")
        for field in ("coreVersion", "coreCommit", "rulesVersion", "configSha256", "coreSha256"):
            if not manifest.get(field):
                failures.append(f"manifest 缺少 {field}")
        if not isinstance(manifest.get("outputSha256"), dict) or not manifest.get("outputSha256"):
            failures.append("manifest 缺少 outputSha256")
        output_hashes = manifest.get("outputSha256", {}) if isinstance(manifest.get("outputSha256"), dict) else {}
        for relative, expected_hash in output_hashes.items():
            path = self.workspace / relative
            if not path.is_file():
                failures.append(f"outputSha256 指向缺失文件: {relative}")
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash.lower() != str(expected_hash).lower():
                failures.append(f"outputSha256 哈希不一致: {relative}")
        for name in required:
            relative = f"source-materials/{name}"
            if name != "SOURCE_MATERIALS_MANIFEST.json" and relative not in output_hashes:
                failures.append(f"outputSha256 缺少 {relative}")
        if not files or not cleaned or not selection.get("pages"):
            failures.append("没有有效源码或分页结果")
        pages = selection.get("pages", [])
        line_limit = int(manifest.get("config", {}).get("linesPerPage", 50))
        max_pages = int(manifest.get("config", {}).get("maxPages", 60))
        if len(pages) > max_pages:
            failures.append(f"页数超过 maxPages: {len(pages)} > {max_pages}")
        if any(len(page.get("lines", [])) < line_limit for page in pages[:-1]):
            failures.append("存在非末页行数不足")
        estimated_pages = stats.get("estimatedPages") if isinstance(stats, dict) else None
        if isinstance(estimated_pages, int) and estimated_pages > max_pages:
            failures.append(f"stats.estimatedPages 超过 maxPages: {estimated_pages} > {max_pages}")
        if any(item.get("status") == "fail" for item in audit_items):
            failures.append("源码审计包含 fail")
        warnings.extend(item.get("detail", item.get("name", "")) for item in audit_items if item.get("status") == "warn")
        rendered = manifest.get("rendered", [])
        if not rendered or not any((self.workspace / path).is_file() and (self.workspace / path).stat().st_size > 0 for path in rendered):
            failures.append("没有非空渲染 DOCX/TXT")
        for rendered_path in rendered or []:
            if rendered_path not in output_hashes:
                failures.append(f"outputSha256 缺少 rendered 产物: {rendered_path}")
        return {
            "ok": not failures, "backend": manifest.get("backend"), "failures": failures,
            "warnings": warnings, "artifact_count": len(required) + len(rendered),
            "reason": "源码材料门禁通过" if not failures else "; ".join(failures),
        }

    def check_paper_consistency(self) -> dict:
        """轻量前置一致性：论文必须引用代码/结果中的关键数字。

        这是 comp-paper-zh/en 在写作阶段的门禁，避免写完才发现数字与结果脱节。
        完整的一致性合同（CONSISTENCY_REPORT.json）仍由 comp-consistency 步骤负责（check_consistency_evidence）。
        """
        tex = self.workspace / "paper" / "main.tex"
        md = self.workspace / "paper" / "main.md"
        paper = tex if tex.is_file() else (md if md.is_file() else None)
        if paper is None:
            return {"ok": False, "reason": "未找到 paper/main.tex 或 paper/main.md"}
        paper_text = paper.read_text(encoding="utf-8", errors="ignore")

        result_numbers: list[float] = []
        results_json = self.workspace / "figures" / "all_results.json"
        if results_json.is_file():
            try:
                raw = json.loads(results_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"ok": False, "reason": "figures/all_results.json 不是有效 JSON"}
            result_numbers = _collect_numbers(raw)
        results_md = self.workspace / "RESULTS.md"
        if not result_numbers and results_md.is_file():
            md_text = results_md.read_text(encoding="utf-8", errors="ignore")
            result_numbers = [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", md_text) if _moderate_number(float(m))]
        if not result_numbers:
            return {"ok": False, "reason": "无结果数字来源（figures/all_results.json 或 RESULTS.md 为空/缺失）"}

        paper_numbers = {float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", paper_text) if _moderate_number(float(m))}
        hits = 0
        for value in result_numbers:
            for candidate in _number_candidates(value):
                if candidate in paper_text:
                    hits += 1
                    break
        if hits == 0:
            return {"ok": False, "paper_numbers": len(paper_numbers),
                    "reason": "论文正文未引用任何结果关键数字（可 `\\ref` 或直接写数值）"}
        return {"ok": True, "checked_numbers": len(result_numbers), "hits": hits,
                "reason": f"论文引用 {hits}/{len(result_numbers)} 个结果关键数字"}

    def check_citation_integrity(self) -> dict:
        """引用完整性：references.bib 条目存在、字段完整、DOI 格式合法。

        离线可跑：只做格式与结构校验，不做联网解析。
        """
        bib = self.workspace / "paper" / "references.bib"
        if not bib.is_file():
            return {"ok": False, "reason": "缺少 paper/references.bib"}
        content = bib.read_text(encoding="utf-8", errors="ignore")
        entries = re.findall(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", content)
        if not entries:
            return {"ok": False, "reason": "references.bib 无 BibTeX 条目"}
        warnings: list[str] = []
        invalid_dois: list[str] = []
        missing_doi_warned = 0
        for etype, key in entries:
            block_start = max(0, content.find("{" + key, 0))
            block = content[block_start:block_start + 4000]
            has_title = "title" in block
            has_author = "author" in block
            doi_match = re.search(r"doi\s*=\s*[\{\"]\s*([^}\"]+?)\s*[\}\"]", block, re.I)
            if not has_title or not has_author:
                warnings.append(f"条目 {key}: 缺 title 或 author")
            if doi_match:
                doi = doi_match.group(1).strip()
                if not re.fullmatch(r"10\.\d{4,9}/[^\s{}]+", doi):
                    invalid_dois.append(f"{key}: {doi}")
            elif etype.lower() not in ("misc", "techreport") and missing_doi_warned < 5:
                warnings.append(f"条目 {key}: 期刊/会议条目缺 DOI")
                missing_doi_warned += 1
        ok = not invalid_dois
        reason = f"引用完整性 {'✅' if ok else '❌'}: {len(entries)} 条目"
        if invalid_dois:
            reason += f"，非法 DOI: {', '.join(invalid_dois[:3])}"
        if warnings:
            reason += f"，警告 {len(warnings)} 项"
        return {"ok": ok, "entries": len(entries), "warnings": warnings, "invalid_dois": invalid_dois, "reason": reason}

    def check_experiment_reproduc(self) -> dict:
        """实验可复现性：STEP_MANIFEST.json 必须声明依赖与命令，且存在实验结果。

        用于 experiment-bridge 等实验类步骤：环境可复现是闭环前提。
        """
        manifest_path = self.workspace / "STEP_MANIFEST.json"
        manifest_result = _validate_step_manifest(self.workspace,
            session=getattr(self, "_fingerprint_session", None), manifest_data=getattr(self, "_manifest_data", None))
        failures: list[str] = []
        warnings: list[str] = []
        if not manifest_result["ok"]:
            failures.append("STEP_MANIFEST.json 缺失或无效")
        else:
            manifest = manifest_result["manifest"]
            deps = manifest.get("dependencies", {})
            commands = manifest.get("commands", [])
            if not deps:
                failures.append("manifest 未声明依赖（dependencies 为空）")
            if not commands:
                failures.append("manifest 未声明命令（commands 为空）")
        declared = getattr(self, "_declared_outputs", None) or []
        result_candidates = [str(p.get("path", "") if isinstance(p, dict) else p) for p in declared]
        if not result_candidates:
            result_candidates = ["RESULTS.md", "EXPERIMENT_REPORT.md", "results.json", "experiment_results.md", "figures/experiment_data.json"]
        result_files = [f for f in result_candidates if Path(f).suffix.lower() in {".md", ".json", ".csv"}
                        and (self.workspace / f).is_file()]
        if not result_files:
            failures.append("缺少当前实验合同声明的结果文件")
        seed_mentioned = False
        if manifest_path.is_file() and manifest_result.get("manifest"):
            cfg = manifest_result["manifest"].get("config", {})
            seed_mentioned = any("seed" in str(k).lower() for k in cfg) if isinstance(cfg, dict) else False
        if not seed_mentioned:
            warnings.append("manifest 未记录随机种子（若实验含随机性请补充）")
        ok = not failures
        return {"ok": ok, "failures": failures, "warnings": warnings, "result_files": result_files,
                "reason": "实验可复现门禁通过" if ok else "; ".join(failures)}

    def check_figure_provenance(self) -> dict:
        """图表溯源：每张图要有来源证据（脚本/元数据/数据源）。

        不允许"无来源图片"直接通过：figures/ 下的 png 必须有同目录脚本、
        FIGURE_PROVENANCE.json 记录，或数据源 all_results.json 存在。
        
        兼容非 PNG 输出（如 latex_includes.tex）的情况。
        """
        figures_dir = self.workspace / "figures"
        if not figures_dir.is_dir():
            return {"ok": False, "issuelist": [], "reason": "缺少 figures/ 目录"}
        
        # 检查 PNG 图表
        pngs = sorted(figures_dir.glob("*.png"))
        tex_includes = sorted(figures_dir.glob("*.tex"))
        
        # 如果没有 PNG，但有 LaTeX include 文件，视为有效输出
        has_pngs = len(pngs) > 0
        has_tex = len(tex_includes) > 0
        
        if not has_pngs and not has_tex:
            return {"ok": False, "issuelist": [], "reason": "figures/ 无图表文件（PNG 或 TEX）"}
        
        provenance_file = figures_dir / "FIGURE_PROVENANCE.json"
        scripts_exist = bool(list(figures_dir.glob("*.py"))) or bool(list(self.workspace.glob("code/*.py")))
        data_source = (self.workspace / "figures" / "all_results.json").is_file() or (self.workspace / "RESULTS.md").is_file()
        
        # 对于 PNG 图表，需要溯源证据；对于纯 TEX 输出，放宽要求
        if has_pngs and not (provenance_file.is_file() or scripts_exist or data_source):
            return {"ok": False, "png_count": len(pngs),
                    "reason": "图表无溯源证据（无 FIGURE_PROVENANCE.json 且无脚本/数据源）"}
        
        warnings = []
        if provenance_file.is_file():
            try:
                records = json.loads(provenance_file.read_text(encoding="utf-8"))
                if not isinstance(records, (list, dict)) or not records:
                    warnings.append("FIGURE_PROVENANCE.json 为空")
            except json.JSONDecodeError:
                warnings.append("FIGURE_PROVENANCE.json 不是有效 JSON")
        
        return {"ok": True, "png_count": len(pngs), "tex_count": len(tex_includes), "warnings": warnings,
                "reason": f"图表溯源证据齐备（{len(pngs)} 张 PNG, {len(tex_includes)} 个 TEX）"}

    def check_compilation_log(self) -> dict:
        """编译日志门禁：LaTeX 编译日志必须存在且无 fatal 错误。

        强制 agent 用编译入口（latex_bridge / 编译脚本）保留日志，禁止只交 PDF 不交日志。
        """
        candidates = [
            self.workspace / "paper" / "main.log",
            self.workspace / "latex_bridge.log",
            self.workspace / "compile.log",
        ]
        log_path = next((p for p in candidates if p.is_file()), None)
        if log_path is None:
            return {"ok": False, "reason": "缺少编译日志（paper/main.log 或 latex_bridge.log）"}
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        fatal_patterns = [
            r"! LaTeX Error",
            r"! Undefined control sequence",
            r"! Emergency stop",
            r"Fatal error",
            r"! Package [^\s]+ Error",
        ]
        fatals = [m for pat in fatal_patterns for m in re.findall(pat, text)]
        warnings = []
        warning_count = len(re.findall(r"Warning", text))
        if warning_count:
            warnings.append(f"日志含 {warning_count} 条 Warning")
        ok = not fatals
        return {"ok": ok, "log": log_path.name, "fatals": len(fatals), "warnings": warnings,
                "reason": f"编译日志 {'无 fatal' if ok else '含 fatal'}: {log_path.name}"}

    def check_modeling_contract(self) -> dict:
        """建模合同门禁：MODELING_REPORT.md 必须包含 METHOD_CLAIMS_MACHINE 注释块。

        这是防"名不副实"的关键防线：强制 agent 在建模报告中显式声明方法假设与适用范围，
        而不是只写公式不写约束条件。
        """
        report = self.workspace / "MODELING_REPORT.md"
        if not report.is_file():
            return {"ok": False, "reason": "缺少 MODELING_REPORT.md"}
        text = report.read_text(encoding="utf-8", errors="ignore")
        if "METHOD_CLAIMS_MACHINE" not in text:
            return {"ok": False, "reason": "MODELING_REPORT.md 缺少 METHOD_CLAIMS_MACHINE 声明块"}
        # 检查块内容是否完整（至少有 assumptions 和 scope 字段）
        if "assumptions" not in text.lower() or "scope" not in text.lower():
            return {"ok": False, "reason": "METHOD_CLAIMS_MACHINE 块缺少 assumptions 或 scope 字段"}
        return {"ok": True, "reason": "建模合同完整（含 METHOD_CLAIMS_MACHINE 声明）"}

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


    def check_early_quality(self, *, max_pages=None, compliance_profile="",
                            page_contract: dict | None = None,
                            compliance_block: dict | None = None) -> dict:
        """复用现有轻检实现，由程序执行；不再让模型手抄同一检查命令。

        B-02：页数口径与合规块优先来自工作流快照（page_contract/compliance_block，
        单一事实）；旧参数路径回落 comp_rules 条目。任何路径都没有缺省页数——
        无口径时页检 SKIP 并明示原因，不默认任何赛事（默认国赛30已删除）。
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location("acat_early_quality", PROJECT_ROOT / "skills/_utils/quick_gates.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if compliance_block is not None:
            profile = dict(compliance_block)
            contract = dict(page_contract) if page_contract is not None else None
        elif compliance_profile:
            from . import contest_profile as cp_mod
            try:
                entry = cp_mod.load_entry(compliance_profile)
            except cp_mod.ContestProfileError as exc:
                return {"ok": False, "checks": [{"name": "compliance", "status": "ERROR", "detail": str(exc)}],
                        "max_pages_effective": None, "reason": f"合规口径不可解析: {exc}"}
            profile = cp_mod.compliance_profile(entry)
            contract = dict(page_contract) if page_contract is not None else \
                cp_mod.resolve_operative_cap(cp_mod.page_cap_contract(entry), max_pages)
        else:
            profile = None
            contract = dict(page_contract) if page_contract is not None else \
                ({"cap": max_pages, "scope": "body", "status": "explicit_argument", "reason": ""}
                 if max_pages else
                 {"cap": None, "scope": "total", "status": "unconfigured",
                  "reason": "未配置页数合规口径（--max-pages/--compliance-profile 均未提供；不默认任何赛事）"})
        if contract is None:
            contract = {"cap": None, "scope": "total", "status": "unconfigured", "reason": "无页数口径合同"}
        pdf = self.workspace / "paper/main.pdf"
        jobs = [("page_count", lambda: module._page_check(self.workspace, pdf, contract)),
                ("figure_font", lambda: module._figure_check(self.workspace)),
                ("leakage", lambda: module._leakage_check(self.workspace))]
        if compliance_profile:
            if profile is not None:
                jobs.append(("compliance", lambda: module._pledge_check(self.workspace, pdf, profile)))
            else:
                # schema v2（E-MERGE-01）：合规口径在 profiles 维度，contest 层条目无顶层
                # compliance 块；未绑定档案快照的路径无从选择口径——如实 SKIP 不计失败
                # （不冒充通过、不误报"配置缺失"）。绑定工作流的口径由快照 compliance
                # 块下发；unknown≠PASS 的交付结论仍由终审 contest_compliance 把关。
                jobs.append(("compliance", lambda: ("SKIP",
                    "档案条目无顶层合规口径（schema v2 口径在 profiles 维度，"
                    "未绑定快照路径未选择届次/提交形态）——合规机检不执行，"
                    "绑定后由快照口径驱动，人工确认承接")))
        checks = []
        for name, check in jobs:
            try:
                status, detail = check()
            except Exception as exc:
                status, detail = "ERROR", str(exc)
            checks.append({"name": name, "status": status, "detail": detail})
        failures = [c for c in checks if c["status"] in {"FAIL", "ERROR"}]
        return {"ok": not failures, "checks": checks, "max_pages_effective": contract.get("cap"),
                "page_contract": contract,
                "reason": "; ".join(c["detail"] for c in failures) if failures else "本步早期检查完成；缺席产物按SKIP记录"}

    def check_step_manifest(self) -> dict:
        """验证 STEP_MANIFEST.json 的存在性、schema 版本、必填字段完整性。"""
        result = _validate_step_manifest(self.workspace, session=getattr(self, "_fingerprint_session", None),
                                         manifest_data=getattr(self, "_manifest_data", None))
        if result["ok"]:
            return {"ok": True, "stepName": result["stepName"], "backend": result["backend"],
                    "outputCount": result["outputCount"], "reason": "STEP_MANIFEST.json 验证通过"}
        return {"ok": False, "errors": result["errors"],
                "reason": "STEP_MANIFEST.json 验证失败: " + "; ".join(result["errors"])}

    def check_review_rounds(self) -> dict:
        """评审轮次对账（B窗 2026-09-27 承接 auto-review-loop 轮次纪律）。

        只读既有产物，不要求模型另填证明：REVIEW_STATE.json 声称完成 N 轮，
        磁盘就必须有第 1..N 轮的真实任务卡（round_<i>.task.md）与评审原文
        （round_<i>.verdict.md，非空且含裁定信号）——没有真实评审不能声称完成多轮。
        MAX_ROUNDS 是上限不是必须做满：status=completed 且轮数未达上限属合法
        提前结束，不误拒（positive 判定是 loop 自身 stop-condition，不在此重复）。
        REVIEW_STATE.json 缺席 = 该用法无轮次声称，不启用对账（不误拒）。
        """
        state_path = self.workspace / "REVIEW_STATE.json"
        if not state_path.is_file():
            return {"ok": True, "skipped": True, "reason": "无 REVIEW_STATE.json（无轮次声称，不对账）"}
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return {"ok": False, "reason": f"REVIEW_STATE.json 不是有效JSON: {exc}"}
        if not isinstance(state, dict) or "round" not in state:
            return {"ok": False, "reason": "REVIEW_STATE.json 缺 round 字段（轮次声称不可核对）"}
        claimed = state.get("round")
        if not isinstance(claimed, int) or claimed < 1:
            return {"ok": False, "reason": f"REVIEW_STATE.json round 非法: {claimed!r}"}
        max_rounds = state.get("max_rounds")
        if isinstance(max_rounds, int) and max_rounds >= 1 and claimed > max_rounds:
            return {"ok": False, "reason": f"声称轮数 {claimed} 超过上限 max_rounds={max_rounds}"}
        task_dir = self.workspace / "review_tasks"
        problems = []
        verified_rounds = 0
        verdict_signals = ("ready", "accept", "not ready", "almost")
        for i in range(1, claimed + 1):
            task = task_dir / f"round_{i}.task.md"
            verdict = task_dir / f"round_{i}.verdict.md"
            if not task.is_file() or task.stat().st_size == 0:
                problems.append(f"第{i}轮缺任务卡 review_tasks/round_{i}.task.md")
                continue
            if not verdict.is_file() or verdict.stat().st_size == 0:
                problems.append(f"第{i}轮缺评审原文 review_tasks/round_{i}.verdict.md（无真实返回不能计入该轮）")
                continue
            try:
                verdict_text = verdict.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                problems.append(f"第{i}轮评审原文不可读")
                continue
            if not any(signal in verdict_text for signal in verdict_signals):
                problems.append(f"第{i}轮评审原文缺少裁定标记（ready/accept/not ready/almost 任一），疑似占位")
                continue
            verified_rounds += 1
        status = str(state.get("status", ""))
        detail = f"声称 {claimed} 轮，实际可核对 {verified_rounds} 轮"
        if problems:
            return {"ok": False, "claimed_rounds": claimed, "verified_rounds": verified_rounds,
                    "problems": problems, "status": status,
                    "reason": detail + "；" + "; ".join(problems)}
        early_stop = "；提前结束合法（MAX_ROUNDS 是上限不是必须做满）" if status == "completed" else ""
        return {"ok": True, "claimed_rounds": claimed, "verified_rounds": verified_rounds,
                "status": status, "reason": detail + early_stop}

    def run_all(self, skill_name: str, declared_outputs=None, comp_name: str = "", requires_figures: bool = False,
                required_checks: list[str] | None = None, primary_output=None,
                fingerprint_session=None, manifest_data=None, active_final_step_id: str = "",
                quick_gates: bool = False, quick_gates_max_pages: int | None = None,
                compliance_profile: str = "", page_contract: dict | None = None,
                compliance_block: dict | None = None) -> dict:
        """运行所有门禁检查"""
        # Keep the existing positional ``run_all(skill, comp_name)`` call valid.
        if isinstance(declared_outputs, str) and not comp_name:
            comp_name = declared_outputs
            declared_outputs = None
        self._declared_outputs = declared_outputs
        self._fingerprint_session = fingerprint_session
        self._manifest_data = manifest_data
        self._active_final_step_id = active_final_step_id
        results = {}
        if declared_outputs is not None:
            artifact_result = ArtifactManifest.validate(self.workspace, declared_outputs, session=fingerprint_session)
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
        # 页数门禁只在「本步确实应携带论文」的步骤执行（comp_name 非空 = 模板声明
        # revalidate_paper_pages，或本步为 comp-compile-zh/en）；page_contract 仅作为
        # 口径来源透传（B-02 快照单一事实），**不得**据此把页检扩散到所有步骤——
        # bound 赛事的 page_contract 对每一步都非 None，扩散会让尚无 paper/ 的早期步骤
        # （如 comp-problem-analysis）被"未找到 paper/main.tex"判 FAIL 而无法完成。
        if comp_name:
            results["paper_pages"] = self.check_paper_pages(comp_name, page_contract=page_contract)
        named_checks = {name: getattr(self, method_name) for name, method_name in NAMED_CHECKS_REGISTRY.items()}
        # M1 FIX: 审核类技能即使模板未声明 required_checks，也必须自动跑 review gate——
        # 否则 comp_mcm 等 21 个无 required_checks 模板的审稿步骤门禁从不执行，
        # 审稿证据缺失/伪造不会被发现。
        review_skills = {"comp-review", "comp-visual-review", "comp-final-review"}
        effective_checks = list(required_checks or [])
        if skill_name in review_skills and "review" not in effective_checks:
            effective_checks.append("review")
        # M1 同款先例（B窗 2026-09-27）：auto-review-loop 的轮次对账不依赖模板声明，
        # 循环类审核步骤一律对账——"声称N轮必须有N轮真实记录"是程序责任，非模板配置。
        if skill_name == "auto-review-loop" and "review_rounds" not in effective_checks:
            effective_checks.append("review_rounds")
        for name in effective_checks:
            if name not in named_checks:
                results[f"required_{name}"] = {"ok": False, "reason": f"未知质量门禁: {name}"}
            else:
                if name == "review":
                    # comp-final-review 启用严格模型比对（软约定→硬阻断）
                    strict = skill_name == "comp-final-review"
                    # A7-F1 死锁修复：按步骤语义选择模式——
                    #   comp-visual-review（第 11 步）只校验视觉对，不能强制 full
                    #   （EDITOR/FINAL 产物属第 12/13 步，顺序上尚不存在）；
                    #   comp-final-review 必须 full（本步就是补齐终审产物的一步）；
                    #   其余（comp-review / 模板显式声明）保持 auto 时序解析。
                    review_mode = {"comp-visual-review": "visual", "comp-final-review": "full"}.get(skill_name, "auto")
                    results[name] = self.check_review_evidence(mode=review_mode, strict_model_match=strict)
                else:
                    results[name] = named_checks[name]()
        # D3 门禁前移程序化（B窗 2026-09-26 接入）：模板声明 metadata.quick_gates=true 的
        # 步骤由引擎在验收时直接执行早检，不再依赖模型先跑脚本再回报。参数取真实合同：
        # max_pages 优先步骤声明（quick_gates_max_pages），缺省回落 compliance 口径；
        # ERROR（解析失败/编排异常）按失败计入，不得冒充 PASS；SKIP（产物未齐）不阻断。
        if quick_gates:
            results["early_quality"] = self.check_early_quality(
                max_pages=quick_gates_max_pages, compliance_profile=compliance_profile,
                page_contract=page_contract, compliance_block=compliance_block)
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

    def __init__(self, api_key: str = "", base_url: str = "", model: str = "",
                 workspace: Path | str = ""):
        self.api_key = api_key or env_get("OPENAI_API_KEY") or env_get("SENSENOVA_API_KEY")
        self.base_url = base_url or env_get("OPENAI_BASE_URL") or env_get("SENSENOVA_BASE_URL")
        self.model = model or env_get("REVIEWER_MODEL_ID") or env_get("SENSENOVA_MODEL") or "deepseek-v4-flash"
        # A6-F4：传入 workspace（或设 ACAT_WORKSPACE 环境变量）后，每次调用会把
        # "角色→实际使用的 base_url/model"写进工作区 sidecar，供 strict 闸交叉核对。
        resolved_ws = str(workspace or "").strip() or str(env_get("ACAT_WORKSPACE", "") or "").strip()
        self._workspace = Path(resolved_ws).resolve() if resolved_ws else None

    def call(self, role: str, prompt: str, system: str = "") -> str:
        """调用 LLM 执行角色任务"""
        if role not in self.ROLES:
            raise ValueError(f"未知角色: {role}")
        sys_prompt = system or self.ROLES[role]["system"]
        return self._call_llm(sys_prompt, prompt, role=role)

    def _call_llm(self, system: str, prompt: str, role: str = "") -> str:
        """调用 OpenAI 兼容 API（支持推理模型）。

        韧性设计（解决"全局配额只够一次审核、复核失败"）：
        1. 429/5xx 指数退避重试（3 次）
        2. 主 provider 失败后按 .env 配置顺序 fallback 到备用 provider
        3. 成功后把实际使用的 base_url/model 写入工作区 sidecar（A6-F4，
           需构造时传入 workspace 或设 ACAT_WORKSPACE；未配置工作区则不落盘）
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
                    if role and self._workspace is not None:
                        record_role_call_actual(self._workspace, role, base_url, model)
                    return content
                if role and self._workspace is not None:
                    record_role_call_actual(self._workspace, role, base_url, model)
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
# P6: 视觉能力（2026-09-23 换驱动：宿主独立窗口视觉审核）
# =====================================================

class VisionAgent:
    """视觉能力 — 宿主独立窗口视觉审核（不再调用外部 Vision LLM API）。

    2026-09-23 第三次用户裁定：视觉审核驱动从「填 APIKey 调外部视觉 API」
    整体置换为「项目驱动宿主自身视觉能力 LLM 在独立窗口读图审核」。
    本类不再持有 api_key/base_url，不再发起任何网络请求；职责收敛为
    任务卡生成（派发独立窗口）与证据收集（解析 verdict）。
    """

    def __init__(self):
        self.tools_dir = TOOLS_DIR

    def describe_image(self, image_path: str, context: str = "") -> str:
        """生成独立窗口审核任务卡并返回派发指引（不再调用外部 Vision API）。"""
        card = self.check_figure_quality(image_path)
        lines = [
            "宿主独立窗口视觉审核任务已就绪（本引擎不调用外部视觉 API）：",
            f"- 待审图件: {image_path}",
            f"- 上下文: {context}" if context else "- 上下文: （无）",
        ]
        if card.get("task_card"):
            lines.append(f"- 任务卡: {card['task_card']}")
        lines.append(f"- 判定: {card.get('verdict', '')}")
        return "\n".join(lines)

    def check_figure_quality(self, image_path: str) -> dict:
        """检查图表质量（重叠/截断/美观）— 经 tikz_vision_check.py 宿主窗口驱动。"""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "tikz_vision_check.py"), image_path],
            capture_output=True, text=True, timeout=120)
        stdout = result.stdout.strip()
        task_card = ""
        for line in stdout.splitlines():
            if line.startswith("任务卡已生成: "):
                task_card = line[len("任务卡已生成: "):]
        # exit 0=PASS/STOP 定稿放行；1=ISSUE；2=独立窗口证据未就绪（任务卡已派发）
        return {
            "ok": result.returncode == 0,
            "verdict": stdout or result.stderr.strip(),
            "task_card": task_card,
            "pending_host_window": result.returncode == 2,
        }


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
    role.add_argument("--workspace", default="",
                      help="工作区路径（提供后把实际调用 base_url/model 写入 "
                           ".engine/role_calls_actual.json，供 final-review strict 闸交叉核对）")

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
        agent = RoleAgent(workspace=getattr(args, "workspace", ""))
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
