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
from .._paths import ENGINE_DIR, MODEX_CORE, TOOLBOX_ROOT

_ENGINE_DIR = ENGINE_DIR
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
if str(_ENGINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR.parent))

try:
    from ..storage.artifact_manifest import ArtifactManifest
    from ..storage.step_manifest import validate_manifest as _validate_step_manifest
except ImportError:
    try:
        from storage.artifact_manifest import ArtifactManifest
        from storage.step_manifest import validate_manifest as _validate_step_manifest
    except ImportError:
        from engine.storage.artifact_manifest import ArtifactManifest
        from engine.storage.step_manifest import validate_manifest as _validate_step_manifest

PROJECT_ROOT = TOOLBOX_ROOT
TOOLS_DIR = PROJECT_ROOT / "tools"
RULES_FILE = MODEX_CORE / "comp_rules.json"
GATES_FILE = MODEX_CORE / "quality_gates.json"

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
    from ..host.env_loader import apply_env, get as env_get
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
        from ..host.runtime_adapter import RuntimePaths
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


_PAPER_SOURCE_SCOPE = None


def _paper_source_scope_module():
    """加载技能侧唯一 active-sections 解析器（与编译/检查脚本同一份实现）。

    不复制一份 TeX 解析规则到引擎：分章范围口径必须与 skills/_utils 的
    paper_source_scope 一致，避免引擎与检查器各认一套装配面。
    """
    global _PAPER_SOURCE_SCOPE
    if _PAPER_SOURCE_SCOPE is None:
        import importlib.util
        path = PROJECT_ROOT / "skills" / "_utils" / "paper_source_scope.py"
        if not path.is_file():
            raise ImportError(f"active sections 解析器缺席: {path}")
        spec = importlib.util.spec_from_file_location("acat_paper_source_scope", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PAPER_SOURCE_SCOPE = module
    return _PAPER_SOURCE_SCOPE


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
    from ..contracts import contest_profile
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
    "ai_flavor": "check_ai_flavor",
    "figure_narrative": "check_figure_narrative",
}


# =====================================================
# P2a 检查分级（裁决 6.3-A）
# -----------------------------------------------------
# 两个正交维度：
#   severity —— 跑成了但不过，要不要挡（blocking/fixable/advisory）
#   status   —— 检查有没有跑成（pass/fail/unknown）
# unknown（工具缺失/检查器异常）绝不等同于「产物不合格」，也绝不冒充 pass：
# ok 恒等于 (status == "pass")，故 unknown 按 fail-closed 处理，但 reason/action
# 指向修复工具而不是返修产物。
# =====================================================

SEVERITY_BLOCKING = "blocking"
SEVERITY_FIXABLE = "fixable"
SEVERITY_ADVISORY = "advisory"
CHECK_SEVERITIES = (SEVERITY_BLOCKING, SEVERITY_FIXABLE, SEVERITY_ADVISORY)
CHECK_STATUSES = ("pass", "fail", "unknown")
# 合同档位（P4-6）：legacy = 改造前行为（默认）；legacy/explore 保留 rglob 兜底，
# delivery 收紧主产物判据：禁用「随便一个大 md」兜底，并按声明产物扩展名挂载
# 可解析性检查。档位语义与 execution_contract.tier 对齐。
CONTRACT_TIERS = ("legacy", "explore", "delivery")
DELIVERY_TIER = "delivery"
PRIMARY_PARSEABLE_SUFFIXES = (".json", ".pdf", ".tex")

# 裁决 6.3-A：这十项永不降级（硬编码，守护断言拒绝任何 advisory/fixable 改动）。
NEVER_DOWNGRADE_CHECKS = frozenset({
    "protocol",
    "binding",
    "review",
    "final_audit",
    "step_manifest",
    "assets_usage",
    "independent_review",
    "citation_integrity",
    "figure_provenance",
    "compilation_log",
})

# 47 模板 sub_steps.required_checks 实测并集 = 15 个唯一检查名（2026-10-25 拆解复算）。
TEMPLATE_CHECK_NAMES = frozenset({
    "ai_flavor", "citation_integrity", "compilation_log", "consistency",
    "experiment_reproduc", "figure_narrative", "figure_provenance", "final_audit",
    "literature", "literature_search", "modeling_contract", "paper_consistency",
    "review", "source_materials", "step_manifest",
})

# 注册表：15 个模板检查名 + runner/run_all 自产检查名。
# 未登记名默认 blocking（见 resolve_check_severity），由 unregistered_check_names 列名。
# 分档理由：
#   blocking —— 证据/防伪造/契约下限（缺了就是「没做完」或「不可信」）；
#   fixable  —— 内容质量可当场返修，按裁决留给 P2b 的接收者判定消费；
#   advisory —— 风格/叙述类提示，留痕不阻断。
CHECK_SEVERITY_REGISTRY: dict[str, str] = {
    # —— 15 个模板检查名 ——
    "literature": SEVERITY_BLOCKING,
    "literature_search": SEVERITY_BLOCKING,
    "review": SEVERITY_BLOCKING,
    "consistency": SEVERITY_FIXABLE,
    "final_audit": SEVERITY_BLOCKING,
    "source_materials": SEVERITY_BLOCKING,
    "step_manifest": SEVERITY_BLOCKING,
    "paper_consistency": SEVERITY_FIXABLE,
    "citation_integrity": SEVERITY_BLOCKING,
    "experiment_reproduc": SEVERITY_FIXABLE,
    "figure_provenance": SEVERITY_BLOCKING,
    "compilation_log": SEVERITY_BLOCKING,
    "modeling_contract": SEVERITY_FIXABLE,
    "ai_flavor": SEVERITY_ADVISORY,
    "figure_narrative": SEVERITY_ADVISORY,
    # —— runner / run_all 自产检查名（其中十项永不降级见 NEVER_DOWNGRADE_CHECKS）——
    "review_rounds": SEVERITY_BLOCKING,    "protocol": SEVERITY_BLOCKING,
    "binding": SEVERITY_BLOCKING,
    "assets_usage": SEVERITY_BLOCKING,
    "independent_review": SEVERITY_BLOCKING,
    "final_audit_binding": SEVERITY_BLOCKING,
    "final_audit_live_state": SEVERITY_BLOCKING,
    "contest_identity": SEVERITY_BLOCKING,
    "candidate_roots": SEVERITY_BLOCKING,
    "declared_outputs": SEVERITY_BLOCKING,
    "additional_skills": SEVERITY_BLOCKING,
    "business_outputs": SEVERITY_BLOCKING,
    "companion": SEVERITY_BLOCKING,
    "validation": SEVERITY_BLOCKING,
    "artifacts": SEVERITY_BLOCKING,
    "min_size": SEVERITY_BLOCKING,
    "companions": SEVERITY_BLOCKING,
    "primary_parseable": SEVERITY_BLOCKING,
    "figures": SEVERITY_BLOCKING,
    "paper_pages": SEVERITY_BLOCKING,
    "early_quality": SEVERITY_BLOCKING,
    "checker_registry": SEVERITY_BLOCKING,
    # —— P3 闸门下沉：技能正文闸门的引擎等价检查器（registration 见 checkers/registry.json）——
    # 交付档 blocking（承接被替换的技能硬门禁，不得降为 advisory）；探索档由
    # runner 的 quality: 前缀族统一降为留痕（execution_contract 分层，不是判据放水）。
    "paper_final_gate": SEVERITY_BLOCKING,
    "result_sanity_check": SEVERITY_BLOCKING,
    "figure_plan_reconciliation": SEVERITY_BLOCKING,
    "modeling_machine_contract": SEVERITY_BLOCKING,
    "paper_write_gate": SEVERITY_BLOCKING,
    "paper_scoring_contract": SEVERITY_BLOCKING,
}


def _assert_severity_registry() -> None:
    """启动守护：注册表不完整/被降级/含非法档位即拒绝加载。

    用 RuntimeError 而不是 assert：`python -O` 会剥掉 assert，守护不能随之失效。
    """
    missing = sorted(TEMPLATE_CHECK_NAMES - set(CHECK_SEVERITY_REGISTRY))
    if missing:
        raise RuntimeError(f"severity 注册表缺少模板检查名: {missing}")
    invalid = {name: value for name, value in CHECK_SEVERITY_REGISTRY.items()
               if value not in CHECK_SEVERITIES}
    if invalid:
        raise RuntimeError(f"severity 注册表含非法档位: {invalid}")
    downgraded = sorted(name for name in NEVER_DOWNGRADE_CHECKS
                        if CHECK_SEVERITY_REGISTRY.get(name) != SEVERITY_BLOCKING)
    if downgraded:
        raise RuntimeError(f"永不降级检查被改档: {downgraded}")


_assert_severity_registry()


def resolve_check_severity(name: str) -> str:
    """解析检查名 → severity；精确名 → 前缀族（output_spec:/quality:）→ 默认 blocking。

    前缀族必须走解析而不是枚举：output_spec:<产物名> 是动态名（模板里自由声明），
    枚举不完；把动态名当未登记 blocking 虽然结果相同，但会让「未登记即放行」的
    误读有机会成立——这里显式声明族规则。
    """
    key = str(name)
    if key in CHECK_SEVERITY_REGISTRY:
        return CHECK_SEVERITY_REGISTRY[key]
    if key.startswith("output_spec:"):
        # D7 产物规格下限是契约，不是建议项。
        return SEVERITY_BLOCKING
    if key.startswith("quality:"):
        inner = key.split(":", 1)[1]
        if inner in CHECK_SEVERITY_REGISTRY:
            return CHECK_SEVERITY_REGISTRY[inner]
        return SEVERITY_BLOCKING
    return SEVERITY_BLOCKING


def is_registered_check(name: str) -> bool:
    """精确名或已知前缀族算已登记；未登记名由 unregistered_check_names 列出。"""
    key = str(name)
    if key in CHECK_SEVERITY_REGISTRY:
        return True
    if key.startswith("output_spec:"):
        return True
    if key.startswith("quality:"):
        return key.split(":", 1)[1] in CHECK_SEVERITY_REGISTRY
    return False


def unregistered_check_names(names) -> list[str]:
    """返回未登记检查名（默认 blocking，但必须能被诊断列出来，不许静默兜底）。"""
    return sorted({str(name) for name in names if not is_registered_check(str(name))})


def annotate_check_result(name: str, result) -> dict:
    """给单个检查结果补 severity 与独立 status，并令 ok 恒等于 (status == "pass")。

    - 已显式标注合法 status 的检查（工具缺失/异常路径）保留其标注；
    - 其余由 ok 推导 pass/fail；
    - ok 缺失或非布尔、或已带非规范 status（历史字段，如评审轮次里的工作流状态）
      → unknown（fail-closed），原值改存 status_detail，不冒充通过。
    """
    data = dict(result) if isinstance(result, dict) else {
        "ok": False, "reason": f"检查器返回非字典结果: {type(result).__name__}"}
    existing = data.get("status")
    if existing in CHECK_STATUSES:
        status = existing
    elif existing is not None:
        data.setdefault("status_detail", existing)
        status = "unknown"
    elif data.get("ok") is True:
        status = "pass"
    elif data.get("ok") is False:
        status = "fail"
    else:
        status = "unknown"
    data["status"] = status
    data["severity"] = resolve_check_severity(name)
    data["ok"] = status == "pass"
    if status == "unknown":
        data.setdefault("action", "fix_tool")
    return data


# =====================================================
# P3 闸门下沉：引擎检查器注册表（承接 P2a 的 severity）
# -----------------------------------------------------
# 与 NAMED_CHECKS_REGISTRY 的分工：
#   NAMED_CHECKS_REGISTRY —— 模板 required_checks 可按名挂载的检查（模板可引用）；
#   checkers/registry.json —— 引擎按 (template, step) 自动挂载的检查器。
# 后者不写进 templates.json（不改模板哈希），但每次 step 验收都会按对键执行。
# 阶段：active = 交付档按登记 severity 执行（当前六项均为 blocking，承接技能
# 正文原有的硬门禁）；shadow = 仅 advisory 留痕，等待 A/B。探索档的降级由
# workflow_runner 按 execution_contract 统一处理，而不是把判据本身改软。
# =====================================================

CHECKER_REGISTRY_PATH = MODEX_CORE / "checkers" / "registry.json"


def load_checker_registry(path: Path | None = None) -> dict:
    """读取引擎检查器注册表；文件缺失视为空表，结构非法直接报错（不静默）。"""
    target = Path(path) if path is not None else CHECKER_REGISTRY_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema_version": 1, "checkers": []}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"检查器注册表不是有效 JSON: {target}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("checkers"), list):
        raise RuntimeError(f"检查器注册表结构非法（需 checkers 列表）: {target}")
    return data


def validate_checker_registry(registry: dict, *, implementations=None) -> list[str]:
    """校验注册表：命名/实现存在/档位一致/阶段与阻断口径匹配/挂载键完整/fix_hint 在位。

    阶段口径：shadow 只能 advisory（未完成 A/B 不得阻断）；active 必须 blocking
    （声明已承接硬门禁却仍留 advisory 属于静默降级）。用返回值而不是 assert：
    调用方可决定是拒绝加载还是只告警，`python -O` 也剥不掉这条守护。
    """
    problems: list[str] = []
    seen: set[str] = set()
    stage_default = str(registry.get("stage") or "shadow")
    for index, entry in enumerate(registry.get("checkers") or []):
        if not isinstance(entry, dict):
            problems.append(f"checkers[{index}] 不是对象")
            continue
        name = str(entry.get("name") or "")
        impl = str(entry.get("implementation") or "")
        if not name or not impl:
            problems.append(f"checkers[{index}] 缺 name/implementation")
            continue
        if name in seen:
            problems.append(f"检查器重名: {name}")
        seen.add(name)
        if implementations is not None and impl not in implementations:
            problems.append(f"检查器 {name} 的实现 {impl} 不存在")
        severity = entry.get("severity")
        if severity not in CHECK_SEVERITIES:
            problems.append(f"检查器 {name} severity 非法: {severity!r}")
        elif resolve_check_severity(name) != severity:
            problems.append(
                f"检查器 {name} severity={severity} 与 severity 注册表 "
                f"{resolve_check_severity(name)} 不一致")
        stage = str(entry.get("stage") or stage_default)
        if stage == "shadow" and severity != SEVERITY_ADVISORY:
            problems.append(f"shadow 阶段检查器 {name} 必须是 advisory（未完成 A/B 不得阻断）")
        if stage == "active" and severity != SEVERITY_BLOCKING:
            problems.append(f"active 阶段检查器 {name} 必须登记为 blocking（不得静默降级）")
        applies = entry.get("applies_to")
        if not isinstance(applies, list) or not applies:
            problems.append(f"检查器 {name} 缺 applies_to")
        else:
            for rule in applies:
                if not isinstance(rule, dict) or not rule.get("template") or not rule.get("step"):
                    problems.append(f"检查器 {name} 的 applies_to 必须是 (template, step) 键: {rule!r}")
        if not str(entry.get("fix_hint") or "").strip():
            problems.append(f"检查器 {name} 缺 fix_hint")
        if not str(entry.get("single_run") or "").strip():
            problems.append(f"检查器 {name} 缺单跑命令 single_run")
        if not entry.get("manual_items"):
            problems.append(f"检查器 {name} 未登记无法程序化的遗留人工项")
    return problems


def auto_checks_for(template_name: str, step_name: str, registry: dict | None = None) -> list[dict]:
    """按 (template, step) 解析应自动挂载的检查器条目；template="*" 表示与模板无关。"""
    data = registry if registry is not None else load_checker_registry()
    matches: list[dict] = []
    for entry in data.get("checkers") or []:
        if not isinstance(entry, dict):
            continue
        for rule in entry.get("applies_to") or []:
            if not isinstance(rule, dict) or rule.get("step") != step_name:
                continue
            pattern = str(rule.get("template") or "")
            if pattern == "*" or pattern == template_name:
                matches.append(entry)
                break
    return matches


def find_checker(name: str, registry: dict | None = None) -> dict | None:
    """按检查名或实现方法名查注册表条目（CLI 单跑用）。"""
    data = registry if registry is not None else load_checker_registry()
    for entry in data.get("checkers") or []:
        if isinstance(entry, dict) and name in {entry.get("name"), entry.get("implementation")}:
            return entry
    return None


def annotate_auto_check(entry: dict, result: dict) -> dict:
    """把注册表中的修复指针写进检查结果（diagnostics 里可直接看到去哪儿修）。"""
    data = dict(result)
    data.setdefault("checker", entry.get("name", ""))
    data.setdefault("fix_hint", entry.get("fix_hint", ""))
    data.setdefault("single_run", entry.get("single_run", ""))
    data.setdefault("source_ref", entry.get("source_ref", ""))
    data.setdefault("stage", entry.get("stage") or "shadow")
    data.setdefault("manual_items", list(entry.get("manual_items") or []))
    return data


# -----------------------------------------------------
# 技能闸门判据的公用抽取器
# -----------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _paper_files(workspace: Path) -> list[Path]:
    paper = Path(workspace) / "paper"
    files: list[Path] = []
    if (paper / "main.tex").is_file():
        files.append(paper / "main.tex")
    sections = paper / "sections"
    if sections.is_dir():
        files.extend(sorted(sections.glob("*.tex")))
    return files


def _paper_text(workspace: Path) -> str:
    return "\n".join(_read_text(p) for p in _paper_files(workspace))


def _flatten_numbers(payload, prefix: str = "") -> dict[str, float]:
    flat: dict[str, float] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            flat.update(_flatten_numbers(value, f"{prefix}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            flat.update(_flatten_numbers(value, f"{prefix}[{index}]"))
    elif isinstance(payload, (int, float)) and not isinstance(payload, bool):
        if 0.001 < abs(payload) < 1e10:
            flat[prefix] = float(payload)
    return flat


def _all_float_values(payload, prefix: str = "") -> list[tuple[str, float]]:
    """扁平化所有 float（不过滤区间）：NaN/Inf 检测必须看原始值。"""
    values: list[tuple[str, float]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            values.extend(_all_float_values(value, f"{prefix}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            values.extend(_all_float_values(value, f"{prefix}[{index}]"))
    elif isinstance(payload, float):
        values.append((prefix, payload))
    return values


NUMERIC_KEY_HINTS = (
    "accuracy", "acc", "rmse", "mae", "r2", "f1", "auc", "loss", "precision",
    "recall", "bleu", "rouge", "perplexity", "ppl", "speed", "latency",
    "throughput", "map", "ndcg",
)


def _numeric_consistency(figures_json: Path, paper_text: str) -> dict:
    """paper-compile「数值一致性」判据：JSON 关键指标须在正文出现（1% 容差）。"""
    try:
        payload = json.loads(Path(figures_json).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"readable": False, "reason": str(exc), "total": 0, "missing": []}
    flat = _flatten_numbers(payload)
    key_values = {k: v for k, v in flat.items()
                  if any(word in k.lower() for word in NUMERIC_KEY_HINTS)}
    paper_numbers = [float(m) for m in
                     re.findall(r"(?<![A-Za-z])(\d+\.?\d+)(?![A-Za-z_{}])", paper_text)]
    missing = [k for k, v in key_values.items()
               if not any(abs(p - v) < abs(v) * 0.01 + 0.001 for p in paper_numbers)]
    return {"readable": True, "total": len(key_values), "missing": missing}


def _unrealistic_values(figures_json: Path) -> list[str]:
    """paper-compile/paper-analysis「太完美」判据（只提示，不阻断）。"""
    try:
        payload = json.loads(Path(figures_json).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    suspicious: list[str] = []
    for name, value in _flatten_numbers(payload).items():
        key = name.lower()
        if any(w in key for w in ("r2", "r_squared", "accuracy", "acc", "precision",
                                  "recall", "f1", "auc")) and value > 0.999:
            suspicious.append(f"{name}={value:.4f} 过完美（>0.999），疑似过拟合/泄漏")
        if any(w in key for w in ("rmse", "mae", "mse", "loss")) and value == 0:
            suspicious.append(f"{name}=0 零误差，几乎不可能")
        if ("p_value" in key or "pvalue" in key) and value == 0:
            suspicious.append(f"{name}=0 完美显著")
        if any(w in key for w in ("improvement", "speedup", "gain")) and value > 10:
            suspicious.append(f"{name}={value} 提升幅度不合理")
    return suspicious


def _claims_coverage(plan_text: str, paper_text: str) -> dict:
    """paper-compile「claims 覆盖」判据：PAPER_PLAN 的 claims-evidence 矩阵逐条查关键词。"""
    rows = re.findall(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", plan_text or "")
    claims = [c.strip() for c, _e in rows
              if c.strip() not in ("Claim", "---") and "---" not in c and len(c.strip()) > 8]
    if not claims:
        return {"applicable": False, "claims": 0, "missing": []}
    missing: list[str] = []
    for claim in claims[:15]:
        keywords = [w for w in re.findall(r"[a-zA-Z_]{4,}|[\u4e00-\u9fff]{2,}", claim)
                    if len(w) > 3][:3]
        if keywords and not any(w.lower() in (paper_text or "").lower() for w in keywords):
            missing.append(claim[:50])
    return {"applicable": True, "claims": len(claims), "missing": missing}


def _count_figure_stacking(text: str) -> int:
    """复刻 paper-compile 的 awk 判据：图/表结束块后不足 3 行正文又起新块 = 堆叠。"""
    count = 0
    armed = False
    text_lines = 0
    for line in (text or "").splitlines():
        if re.search(r"\\end\{(?:figure|table)\}", line):
            armed, text_lines = True, 0
            continue
        if armed and re.search(r"\\begin\{(?:figure|table)\}", line):
            if text_lines < 3:
                count += 1
            armed = False
            continue
        if armed and re.search(r"[A-Za-z\u4e00-\u9fff]{3,}", line):
            text_lines += 1
        if armed and text_lines >= 3:
            armed = False
    return count


def _parse_figure_manifest(text: str) -> list[dict]:
    """解析 FIGURE_MANIFEST 注释块：返回 [{name, kind}]，kind=data/diagram/unknown。"""
    match = re.search(r"<!-- BEGIN FIGURE_MANIFEST -->(.*?)<!-- END FIGURE_MANIFEST -->",
                      text or "", re.S)
    if not match:
        return []
    entries: list[dict] = []
    kind = "unknown"
    for line in match.group(1).splitlines():
        if line.strip().startswith("**"):
            if re.search("数据图|matplotlib|gen_fig", line, re.I):
                kind = "data"
            elif re.search("drawio|html|tikz|流程|架构", line, re.I):
                kind = "diagram"
            else:
                kind = "unknown"
        name = re.match(r"\s*-\s+((?:fig|tikz)_[A-Za-z0-9_]+)", line)
        if name:
            entries.append({"name": name.group(1), "kind": kind})
    return entries


def _parse_drawio_plan(text: str) -> list[dict]:
    """paper-figure-drawio Step 6 的 `DrawIO-N` 规划行 → 图名（无 manifest 时的兼容口径）。"""
    names: list[str] = []
    for line in (text or "").splitlines():
        if not re.search(r"DrawIO-\d+", line, re.I):
            continue
        for name in re.findall(r"\b((?:fig|tikz)_[A-Za-z0-9_]+)\b", line):
            if name not in names:
                names.append(name)
    return [{"name": name, "kind": "diagram"} for name in names]


def _read_max_pages(workspace: Path) -> int | None:
    env = _read_text(Path(workspace) / ".env_skill")
    match = re.search(r"^\s*(?:export\s+)?MAX_PAGES\s*=\s*(\d+)", env, re.M)
    return int(match.group(1)) if match else None


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

    def __init__(self, workspace: Path, audit_report_path: Path | None = None):
        self.workspace = Path(workspace)
        # G2：所有工作流优先读 workflow-scoped 预审报告，避免复用工作区时
        # 误读上一轮 ready 的根 AUDIT_REPORT.json。缺省保持旧单测的根路径行为。
        self._audit_report_path = Path(audit_report_path) if audit_report_path else None

    def check_min_size(self, skill_name: str, primary_output: str,
                       contract_tier: str = "legacy") -> dict:
        """检查产出文件是否达到最小大小。

        ``contract_tier="delivery"``（P4-6）：未声明 primary_output 时禁用
        ``workspace.rglob("*.md")`` 兜底——交付档的主产物必须由模板显式声明，
        不能让工作区里任意一个够大的 markdown 冒充主产物。legacy/explore 保留
        既有兜底行为（默认参数不改既有调用方语义）。
        """
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
        if contract_tier == DELIVERY_TIER:
            return {"ok": False, "min": min_size,
                    "reason": (f"交付档未声明 primary_output：已禁用 rglob 兜底，"
                               f"不接受工作区内任意 ≥{min_size}B 的 markdown 冒充主产物")}
        # Legacy calls without a declared primary output retain best-effort discovery.
        for f in self.workspace.rglob("*.md"):
            if f.stat().st_size >= min_size:
                return {"ok": True, "size": f.stat().st_size, "min": min_size,
                        "reason": f"找到产出 {f.name} = {f.stat().st_size}B ✅"}
        return {"ok": False, "reason": f"未找到 ≥{min_size}B 的产出文件"}

    def check_primary_parseable(self, primary_output: str) -> dict:
        """交付档主产物可解析性（P4-6）：按声明产物扩展名选择判据。

        - ``.json`` → ``json.loads`` 必须成功（存在但不可解析 = 不合格）；
        - ``.pdf``  → 文件头必须是 ``%PDF-``，且页数可解析且 > 0；
        - ``.tex``  → 「main 非空 OR 装配面非空」。只判装配面会误杀单文件论文
          （``assembly_faces`` 对无 ``\\input`` 的 main.tex 返回空列表——V10 口径）；
        - 其他扩展名/目录主产物 → 显式 skip（无对应解析判据，不冒充核验）。
        """
        name = str(primary_output or "").strip()
        if not name:
            return {"ok": False, "reason": "未声明 primary_output，无法核验主产物可解析性"}
        path = self.workspace / name
        if not path.is_file():
            return {"ok": False, "reason": f"未找到主产物 {name}，无法核验其可解析性"}
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return {"ok": False, "kind": "json",
                        "reason": f"主产物 {name} 不是合法 JSON: {exc}"}
            return {"ok": True, "kind": "json", "reason": f"主产物 {name} JSON 可解析"}
        if suffix == ".pdf":
            try:
                header = path.open("rb").read(8)
            except OSError as exc:
                return {"ok": False, "status": "unknown", "action": "fix_tool",
                        "reason": f"主产物 {name} 无法读取文件头: {exc}"}
            if not header.startswith(b"%PDF-"):
                return {"ok": False, "kind": "pdf",
                        "reason": f"主产物 {name} 缺少 PDF 文件头（前 8 字节 {header!r}）"}
            pages = None
            try:
                document = _fitz.open(str(path))
                pages = int(document.page_count)
                document.close()
            except Exception:  # noqa: BLE001 — 解析器异常 = 页数未核验
                pages = None
            if pages is None:
                return {"ok": False, "status": "unknown", "action": "fix_tool",
                        "reason": f"主产物 {name} 文件头合法，但页数无法解析（未核验）"}
            ok = pages > 0
            return {"ok": ok, "kind": "pdf", "pages": pages,
                    "reason": f"主产物 {name} PDF 文件头合法，{pages} 页"
                              f"{'✅' if ok else '❌ 零页 PDF'}"}
        if suffix == ".tex":
            try:
                main_text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                return {"ok": False, "status": "unknown", "action": "fix_tool",
                        "reason": f"主产物 {name} 无法读取: {exc}"}
            faces = assembly_faces(path)
            main_nonempty = bool(main_text.strip())
            faces_nonempty = any(
                p.read_text(encoding="utf-8", errors="ignore").strip()
                for p in faces
                if p.is_file()
            )
            ok = main_nonempty or faces_nonempty
            return {"ok": ok, "kind": "tex", "main_nonempty": main_nonempty,
                    "assembly_faces": len(faces),
                    "reason": (f"主产物 {name} TeX {'可装配' if ok else '为空'}："
                               f"main {'非空' if main_nonempty else '空'}，"
                               f"装配面 {len(faces)} 个文件"
                               f"{'（至少一处非空）✅' if ok else '（main 与装配面均为空）❌'}")}
        return {"ok": True, "skipped": True, "kind": suffix or "none",
                "reason": f"主产物 {name} 的扩展名无解析判据，跳过可解析性检查"}

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
            return {"ok": False, "status": "unknown", "action": "fix_tool",
                    "reason": "无法解析 PDF 页数（pdfinfo 和 PyMuPDF 均不可用）——页数未核验，"
                              "不判产物不合格"}
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
            return {"ok": False, "status": "unknown", "action": "fix_tool",
                    "reason": "fitz (PyMuPDF) 不可用，无法统计正文页数（未核验，不判产物不合格）"}
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
        """Require a manifest-backed delivery decision, not a presence-only JSON file.

        预审报告固定优先读 workflow-scoped 的 ``reports/<workflow_id>/AUDIT_REPORT.json``；
        仅当该文件不存在时才回落根 AUDIT_REPORT.json（兼容旧工作区/旧测试）。
        """
        path = self._audit_report_path or (self.workspace / "AUDIT_REPORT.json")
        delivery = self.workspace / "DELIVERY_REPORT.json"
        if not path.is_file():
            path = self.workspace / "AUDIT_REPORT.json"
        # 非最终审计步骤验收（工作流已进入 ready 派生视图阶段）继续读根
        # DELIVERY_REPORT.json；最终审计步骤验收时 active_final_step_id 非空，
        # 必须读 workflow-scoped 预审源，不能误读上一轮 ready 根。
        if not getattr(self, "_active_final_step_id", "") and delivery.is_file():
            path = delivery
        if not path.is_file():
            expected = self._audit_report_path or (self.workspace / "AUDIT_REPORT.json")
            return {"ok": False, "reason": f"缺少最终审计报告: {expected}"}
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "reason": "最终审计报告不是有效 JSON"}
        required = {"workflow_id", "artifacts", "gate_outcomes", "waivers", "delivery_decision"}
        missing = sorted(required - report.keys()) if isinstance(report, dict) else sorted(required)
        if missing:
            return {"ok": False, "missing": missing, "reason": f"最终审计报告字段不完整: {', '.join(missing)}"}
        if report.get("contract_tier") == "explore" or report["delivery_decision"] == "explore_only":
            return {"ok": False, "failed_gates": ["contract_tier"],
                    "reason": ("explore 档报告（delivery_decision=explore_only）不能作为交付验收："
                               "探索只需 EXPLORE_REPORT.json，正式交付必须 promote 为候选后走 delivery 档")}
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
        # P2b-1：终审 gate_outcomes 已消费 severity（additive）。advisory 只留痕，
        # 不阻断交付；fixable_open 仅在 open_items 中已人工签署时才视为清除；
        # fail/unknown 一律阻断（无接收者的 fixable 在 audit_store 已记 fail）。
        signed_checks = {
            str(item.get("check") or "")
            for item in (report.get("open_items") or [])
            if isinstance(item, dict) and item.get("signed") is True
        }
        failed_gates = [
            name for name, outcome in report["gate_outcomes"].items()
            if not (outcome in {"pass", "advisory"}
                    or (outcome == "fixable_open" and name in signed_checks))
        ]
        if failed_gates:
            candidate_gates = [name for name in failed_gates if name.startswith("candidate_")]
            if candidate_gates:
                detail = (report.get("candidate") or {}).get("gates") or {}
                reasons = {
                    name: str((detail.get(name) or {}).get("reason") or "")
                    for name in candidate_gates if isinstance(detail.get(name), dict)
                }
                degraded = any("L1" in reason or "degraded" in reason.lower()
                               for reason in reasons.values())
                return {"ok": False, "failed_gates": failed_gates,
                        "candidate_gates": reasons,
                        "degraded_host_attestation": degraded,
                        "reason": ("候选交付就绪门未通过: " + ", ".join(
                            f"{name}({reasons.get(name, '')})" if reasons.get(name) else name
                            for name in candidate_gates))}
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

        W5：正文范围从"只看 paper/main.tex 装配壳"改为全部 active sections
        （main.tex 的 \\input/\\include 递归展开，\\includeonly 生效）——分章正文
        里的数字漂移才能在写作步被抓到，而不是等编译后人工发现。通过条件不变：
        至少命中一个结果关键数字；不设每问/每节阈值。
        """
        paper_dir = self.workspace / "paper"
        tex = paper_dir / "main.tex"
        md = paper_dir / "main.md"
        contents: dict[str, str] = {}
        scope_note = ""
        scope = None
        if tex.is_file():
            sources: list[Path] = []
            try:
                scope = _paper_source_scope_module()
                sources = scope.active_sources(paper_dir)
            except (OSError, ValueError, ImportError, AttributeError) as exc:
                scope_note = f"active sections 解析失败，退回 main.tex：{exc}"
            if not sources:
                sources = [tex]
            for path in sources:
                try:
                    label = (scope.source_label(path, paper_dir).as_posix()
                             if scope is not None else Path(path).name)
                except (ValueError, OSError):
                    label = Path(path).name
                try:
                    contents[label] = Path(path).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
        elif md.is_file():
            contents["main.md"] = md.read_text(encoding="utf-8", errors="ignore")
        if not contents:
            return {"ok": False, "reason": "未找到 paper/main.tex 或 paper/main.md"}
        paper_text = "\n".join(contents.values())

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
        section_hits: dict[str, int] = {}
        for value in result_numbers:
            candidates = _number_candidates(value)
            matched_sections = [label for label, text in contents.items()
                                if any(candidate in text for candidate in candidates)]
            if matched_sections:
                hits += 1
                for label in matched_sections:
                    section_hits[label] = section_hits.get(label, 0) + 1
        detail = {"checked_numbers": len(result_numbers), "hits": hits,
                  "sections": list(contents), "section_hits": section_hits}
        if scope_note:
            detail["scope_note"] = scope_note
        if hits == 0:
            return {"ok": False, "paper_numbers": len(paper_numbers), **detail,
                    "reason": "论文正文未引用任何结果关键数字（可 `\\ref` 或直接写数值）"}
        return {"ok": True, **detail,
                "reason": f"论文引用 {hits}/{len(result_numbers)} 个结果关键数字"
                          f"（active sections: {len(contents)} 个文件）"}

    def check_ai_flavor(self) -> dict:
        """AI 痕迹闸：正文工程/质检语汇与内部标记密度不得高于获奖论文水平。

        2026-10-02 历遍复核实锤：写作质量闸（ai_tell_check/writing_check 等）在
        真实工作流 10 份执行证据中零执行——质量闸全靠 LLM 自觉，真实终版残留
        12 处 AI 痕迹，而获奖论文抽样 8 篇 0-2 处/篇（密度差约 10 倍）。本闸把
        "AI 痕迹检查真的跑过且不超阈值" 变成引擎强制项，与证据格式闸对位：
        强制的闸要管质量，管质量的闸必须强制。
        阈值定标：获奖论文抽样分布 0-2 处/篇 → 容许上限 3（获奖水平上界）；
        零容忍会连获奖水平论文一起拦（8 篇抽样 5 篇过不了零容忍）。
        """
        tool = PROJECT_ROOT / "skills" / "_utils" / "ai_tell_check.py"
        # ⛔ resolve：workspace 可能以相对路径传入；subprocess 的 cwd 与 argv 各自
        # 相对子进程 cwd 解析，相对路径拼接会指向不存在的位置（实测踩坑）
        workspace = Path(self.workspace).resolve()
        tex = workspace / "paper" / "main.tex"
        md = workspace / "paper" / "main.md"
        if not tex.is_file() and not md.is_file():
            return {"ok": False, "reason": "未找到 paper/main.tex 或 paper/main.md（正文未成文）"}
        if not tool.is_file():
            return {"ok": False, "status": "unknown", "action": "fix_tool",
                    "reason": f"闸工具缺席：{tool.relative_to(PROJECT_ROOT)}（未核验，不冒充通过、也不判正文不合格）"}
        try:
            proc = subprocess.run(
                [sys.executable, str(tool), "--strict", "--max-errors", "3", str(workspace / "paper")],
                capture_output=True, text=True, timeout=120, cwd=str(workspace),
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "ai_tell_check 超时（>120s）——检查正文规模是否异常"}
        tail = [l for l in (proc.stdout or "").splitlines() if l.strip()][-6:]
        if proc.returncode == 0:
            return {"ok": True, "reason": "；".join(tail[-1:]) or "AI 痕迹密度在获奖论文水平内"}
        if proc.returncode == 2:
            return {"ok": False, "reason": "ai_tell_check 未找到正文（SKIP 语义不冒充通过）: " + "；".join(tail[-2:])}
        return {"ok": False, "reason": "AI 痕迹超获奖论文水平阈值（>3 处）——按输出行号逐条改写："
                                       + " | ".join(tail[-3:])}

    def check_figure_narrative(self) -> dict:
        """图表叙述闸：正文中的图/表必须有正文说明或 \ref 引用（零容忍）。

        2026-10-02 历遍复核定标：真实终版 20+ 张图中 11+ 张是"孤儿图"
        （贴进正文却从未被引用、无解读段）——图海堆砌正是图表侧 AI 味的
        主要形态；获奖论文图表惯例（figure_table_conventions）每图承载叙述。
        figure_narrative_check 的判据是"零叙述且零引用"，无宽容空间：
        修复动作明确（补引用句/补解读段/删图），故不设阈值。
        """
        tool = PROJECT_ROOT / "skills" / "_utils" / "figure_narrative_check.py"
        workspace = Path(self.workspace).resolve()
        tex = workspace / "paper" / "main.tex"
        md = workspace / "paper" / "main.md"
        if not tex.is_file() and not md.is_file():
            return {"ok": False, "reason": "未找到 paper/main.tex 或 paper/main.md（正文未成文）"}
        if not tool.is_file():
            return {"ok": False, "status": "unknown", "action": "fix_tool",
                    "reason": f"闸工具缺席：{tool.relative_to(PROJECT_ROOT)}（未核验，不冒充通过、也不判正文不合格）"}
        try:
            proc = subprocess.run(
                [sys.executable, str(tool), str(workspace / "paper")],
                capture_output=True, text=True, timeout=120, cwd=str(workspace),
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "figure_narrative_check 超时（>120s）"}
        lines = [l for l in (proc.stdout or "").splitlines() if l.strip()]
        fails = [l.strip() for l in lines if "FAIL" in l]
        if proc.returncode == 0:
            return {"ok": True, "reason": "全部图表有正文说明或引用"}
        if proc.returncode == 2:
            return {"ok": False, "reason": "figure_narrative_check 未找到正文（SKIP 语义不冒充通过）"}
        return {"ok": False, "reason": "%d 个图表缺正文说明或引用（孤儿图）——补 \\ref 引用句/解读段或删图: "
                                       % len(fails) + " | ".join(fails[:3])}

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
            # 工具缺失 = 未核验，不是「PNG 不合格」：status=unknown、ok=False（fail-closed），
            # action 指向补装 Pillow 而不是返修产物。
            return {"ok": False, "status": "unknown", "action": "fix_tool", "invalid": [],
                    "fig_count": len(figures),
                    "reason": "Pillow 不可用：PNG 可解码性未核验（装运行期依赖后重跑，"
                              "不得据此判定图表不合格）"}
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

    # -------------------------------------------------
    # P3 闸门下沉：六个重灾区技能的命名闸门 → 引擎检查器
    # 只收「可程序化判定」的判项；语义判断登记在 registry.json 的 manual_items。
    # -------------------------------------------------

    def check_paper_final_gate(self) -> dict:
        """paper-compile Step 7 FINAL QUALITY GATE 的引擎等价物。

        逐项承接 SKILL.md 的可判项：PDF 体量、数学错误、bib/cite、未嵌入图、
        占位符、overfull、itemize、未定义引用、图堆叠、TOC、模板前言、TikZ 嵌入、
        计划图数、数值对账、claims 覆盖、合理性审查章节、meta 泄漏。
        mtime 类（复制/恢复工作区必误报）只作 advisory；语义判断进 manual_items。
        """
        ws = self.workspace
        paper = ws / "paper"
        main_tex, main_log, main_pdf = paper / "main.tex", paper / "main.log", paper / "main.pdf"
        sections = sorted((paper / "sections").glob("*.tex")) if (paper / "sections").is_dir() else []
        body = _paper_text(ws)
        violations: list[str] = []
        advisories: list[str] = []
        unverified: list[str] = []
        counts: dict[str, int] = {}

        # 1) PDF 体量
        if not main_pdf.is_file():
            violations.append("❌ PDF missing")
        else:
            counts["pdf_bytes"] = main_pdf.stat().st_size
            if counts["pdf_bytes"] <= 50000:
                violations.append(f"❌ PDF 体量 {counts['pdf_bytes']}B ≤ 50000B")
        # 2) 编译日志相关判据（日志缺失 = 未核验，不冒充通过）
        if not main_log.is_file():
            unverified.append("paper/main.log 缺失：数学错误/overfull/未定义引用未核验")
        else:
            log_text = _read_text(main_log)
            counts["math_errors"] = len(re.findall(
                r"Bad math.*delimiter|Missing \$ inserted", log_text))
            counts["overfull_vbox"] = len(re.findall(r"Overfull.*vbox", log_text))
            counts["overfull_hbox"] = len(re.findall(r"Overfull.*hbox", log_text))
            counts["undefined_refs"] = len(re.findall(
                r"LaTeX Warning.*Reference.*undefined", log_text))
            if counts["math_errors"]:
                violations.append(f"❌ {counts['math_errors']} math errors")
            if counts["overfull_vbox"]:
                violations.append(f"❌ {counts['overfull_vbox']} overfull vbox")
            if counts["overfull_hbox"] >= 5:
                violations.append(f"❌ {counts['overfull_hbox']} overfull hbox")
            if counts["undefined_refs"]:
                violations.append(f"❌ {counts['undefined_refs']} undefined refs")
        # 3) 书目与引用
        bbl = paper / "main.bbl"
        counts["bibitems"] = len(re.findall(r"\\bibitem", _read_text(bbl))) if bbl.is_file() else 0
        if counts["bibitems"] <= 0:
            violations.append("❌ Bib empty（paper/main.bbl 无 \\bibitem）")
        counts["citations"] = len(re.findall(r"\\cite\{", body))
        if counts["citations"] <= 0:
            violations.append("❌ No citations")
        # 4) 未嵌入图
        figures_dir = ws / "figures"
        unembedded = []
        if figures_dir.is_dir():
            for pdf in sorted(figures_dir.glob("*.pdf")):
                if pdf.name not in body:
                    unembedded.append(pdf.name)
        counts["unembedded_figures"] = len(unembedded)
        if unembedded:
            violations.append(f"❌ {len(unembedded)} unembedded figures: {', '.join(unembedded[:5])}")
        # 5) 占位符
        placeholders = [p.name for p in sections if re.search(r"PLACEHOLDER|TODO", _read_text(p))]
        counts["placeholders"] = len(placeholders)
        if placeholders:
            violations.append(f"❌ {len(placeholders)} placeholders: {', '.join(placeholders[:5])}")
        # 6) itemize（AI 痕迹）
        counts["itemize"] = sum(len(re.findall(r"\\begin\{itemize\}", _read_text(p))) for p in sections)
        if counts["itemize"]:
            violations.append(f"❌ {counts['itemize']} itemize — convert to prose")
        # 7) 图/表堆叠
        counts["figure_stacking"] = sum(_count_figure_stacking(_read_text(p)) for p in sections)
        if counts["figure_stacking"]:
            violations.append(f"❌ {counts['figure_stacking']} figure stacking")
        # 8) TOC
        if "tableofcontents" in _read_text(main_tex):
            toc = paper / "main.toc"
            if not (toc.is_file() and toc.stat().st_size > 0):
                violations.append("❌ TOC empty")
        # 9) 模板前言完整性（工作区无模板副本时跳过）
        template_pre = None
        for name in ("bachelor_main.tex", "master_main.tex", "journal_main.tex",
                     "stats_main.tex", "cumcm_main.tex", "mcm_main.tex"):
            candidate = ws / "_templates" / name
            if candidate.is_file():
                template_pre = candidate
                break
        if template_pre is not None and main_tex.is_file():
            pattern = r"\\(?:usepackage|documentclass|pagestyle|bibliography)"

            def preamble(path):
                text = _read_text(path)
                return sorted(line.strip() for line in text.splitlines()
                              if re.search(pattern, line))
            missing = [line for line in preamble(template_pre)
                       if line not in set(preamble(main_tex))]
            if missing:
                violations.append(f"❌ Template preamble modified: {missing[:3]}")
        # 10) TikZ PDF 嵌入
        tikz_unembedded = []
        if figures_dir.is_dir():
            for pdf in sorted(figures_dir.glob("tikz_*.pdf")):
                if pdf.name not in body:
                    tikz_unembedded.append(pdf.name)
        counts["tikz_unembedded"] = len(tikz_unembedded)
        if tikz_unembedded:
            violations.append(f"❌ {len(tikz_unembedded)} TikZ PDF(s) not embedded")
        # 11) 计划图数
        plan = ws / "PAPER_PLAN.md"
        if plan.is_file():
            planned = len([line for line in _read_text(plan).splitlines()
                           if re.search(r"fig_|figure.*:", line, re.I)])
            actual = len(list(figures_dir.glob("*.pdf"))) if figures_dir.is_dir() else 0
            counts["planned_figures"], counts["actual_figures"] = planned, actual
            if planned > 0 and actual < planned:
                violations.append(f"❌ Only {actual} figures (plan: ~{planned})")
        # 12) 数值一致性
        all_results = figures_dir / "all_results.json"
        if all_results.is_file():
            numeric = _numeric_consistency(all_results, body)
            if not numeric.get("readable"):
                unverified.append("figures/all_results.json 不可读：数值一致性未核验")
            else:
                counts["numeric_total"] = int(numeric["total"])
                counts["numeric_missing"] = len(numeric["missing"])
                if len(numeric["missing"]) > 3:
                    violations.append(
                        f"❌ {len(numeric['missing'])}/{numeric['total']} key values not found in paper")
            advisories.extend(_unrealistic_values(all_results))
        # 13) RESULTS.md 合理性审查章节
        results_md = ws / "RESULTS.md"
        if results_md.is_file():
            if not re.search(r"reasonableness.*review|sanity.*check|合理性审查|plausibility",
                             _read_text(results_md), re.I):
                violations.append("❌ RESULTS.md missing reasonableness review")
        else:
            unverified.append("RESULTS.md 缺失：合理性审查章节未核验")
        # 14) 数据新鲜度（mtime 判据降 advisory：复制/恢复工作区必误报）
        if all_results.is_file() and figures_dir.is_dir():
            json_time = all_results.stat().st_mtime
            stale = [p.name for p in figures_dir.glob("*.pdf")
                     if p.stat().st_mtime < json_time - 60]
            if stale:
                advisories.append(f"{len(stale)} figures older than all_results.json（可能数据陈旧）")
        # 15) meta 泄漏
        leak_re = (r"RESULTS\.md|AGENTS\.md|MODELING_REPORT|PROBLEM_ANALYSIS|"
                   r"PAPER_PLAN|latex_includes|all_results\.json")
        meta = sum(len(re.findall(leak_re, _read_text(p))) for p in sections)
        counts["meta_leaks"] = meta
        if meta:
            violations.append(f"❌ {meta} meta content leaks")
        # 16) overclaiming（原文仅 ⚠，不阻断）
        overclaim_words = ("首次提出", "首次发现", "完美", "无可比拟", "前所未有", "开创性",
                           "revolutionary", "unprecedented", "groundbreaking")
        overclaim = sum(sum(len(re.findall(re.escape(w), _read_text(p), re.I))
                            for w in overclaim_words) for p in sections)
        counts["overclaiming"] = overclaim
        if overclaim:
            advisories.append(f"⚠ {overclaim} overclaiming instances")
        # 17) claims 覆盖
        if plan.is_file():
            coverage = _claims_coverage(_read_text(plan), body)
            if coverage["applicable"] and coverage["missing"]:
                violations.append(
                    f"❌ {len(coverage['missing'])}/{coverage['claims']} planned claims not covered")
        status = "fail" if violations else ("unknown" if unverified else "pass")
        reason = "FINAL QUALITY GATE: " + (
            "; ".join(violations) if violations else
            ("未核验项: " + "; ".join(unverified) if unverified else "全部通过"))
        return {"ok": status == "pass", "status": status, "violations": violations,
                "advisories": advisories, "unverified": unverified, "counts": counts,
                "reason": reason}

    def check_result_sanity_check(self) -> dict:
        """paper-analysis Step 6 sanity_check + 结果约束审计 + comp-paper-zh 数据可追溯性。

        机器可判部分：结果 JSON 的 NaN/Inf/负误差/R² 过低/p 值越界、AUDIT_OK 凭证、
        历史版本 JSON 残留。9 问合理性审查等语义判断登记为 manual_items。
        """
        ws = self.workspace
        result_files: list[Path] = []
        for name in ("figures/all_results.json", "results.json"):
            path = ws / name
            if path.is_file():
                result_files.append(path)
        figures_dir = ws / "figures"
        if figures_dir.is_dir():
            result_files.extend(sorted(figures_dir.glob("*_results.json")))
        seen: set[Path] = set()
        errors: list[str] = []
        suspicious: list[str] = []
        unverified: list[str] = []
        checked = 0
        for path in result_files:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                unverified.append(f"{path.relative_to(ws).as_posix()} 不可读（未核验）")
                continue
            checked += 1
            flat = _flatten_numbers(payload)
            # NaN/Inf 会被 _flatten_numbers 的区间过滤丢掉，单独扫一遍原始数值
            for name, value in _all_float_values(payload):
                if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                    errors.append(f"❌ {path.name}: {name} 为 NaN/Inf")
            for name, value in flat.items():
                key = name.lower()
                if any(w in key for w in ("r2", "r_squared", "accuracy", "acc",
                                          "precision", "recall", "f1", "auc")):
                    if value > 0.99:
                        suspicious.append(f"🚩 {name} = {value:.4f}（>0.99），确认是否过拟合")
                    elif value < 0:
                        errors.append(f"❌ {name} = {value} 负值（模型不如均值）")
                    elif value < 0.5 and any(w in key for w in ("r2", "r_squared")):
                        errors.append(f"❌ {name} = {value:.4f}（R² < 0.5，解释力极弱）")
                if any(w in key for w in ("rmse", "mae", "mse", "loss")):
                    if value == 0:
                        suspicious.append(f"🚩 {name} = 0 完美误差，确认训练/测试是否分开")
                    elif value < 0:
                        errors.append(f"❌ {name} = {value} 误差不应为负")
                if any(w in key for w in ("improvement", "speedup", "gain", "提升", "改进")) and value > 1:
                    suspicious.append(f"🚩 {name} = {value:.2f}（提升 {value * 100:.0f}%），请结合背景确认")
                if "p_value" in key or "pvalue" in key or "p值" in key:
                    if value == 0:
                        suspicious.append(f"🚩 {name} = 0 完美显著（应 > 1e-16）")
                    elif value > 1:
                        errors.append(f"❌ {name} = {value} p 值 > 1 不可能")
        # 结果约束审计凭证（paper-analysis / comp-paper-zh 同一条铁律）
        results_md = ws / "RESULTS.md"
        if results_md.is_file():
            text = _read_text(results_md)
            if not re.search(r"<!--\s*AUDIT_OK\b[^>]*\bsource=[^>]*\brechecked_at=", text):
                errors.append("❌ RESULTS.md 缺 AUDIT_OK 凭证（<!-- AUDIT_OK source=... rechecked_at=... -->）")
        else:
            unverified.append("RESULTS.md 缺失：审计凭证未核验")
        # 历史版本 JSON 残留（版本漂移源；原文只提示，人工确认后删除）
        stale: list[str] = []
        for pattern in ("results_v*.json", "results_old.json", "*_backup.json"):
            stale.extend(p.name for p in sorted(ws.glob(pattern)) if p.is_file())
        if stale:
            suspicious.append(f"⚠ 历史版本 JSON 残留: {', '.join(stale[:5])}")
        if not checked and not results_md.is_file():
            unverified.append("未找到任何结果 JSON 或 RESULTS.md")
        status = "fail" if errors else ("unknown" if unverified else "pass")
        reason = "结果 sanity check: " + (
            "; ".join(errors) if errors else
            (f"{checked} 个结果文件通过；" + ("; ".join(suspicious) if suspicious else "无疑似项")
             if checked else "; ".join(unverified) or "通过"))
        return {"ok": status == "pass", "status": status, "errors": errors,
                "suspicious": suspicious, "unverified": unverified,
                "checked_files": checked, "stale_files": stale, "reason": reason}

    def check_figure_plan_reconciliation(self) -> dict:
        """paper-figure-drawio Step 6 / paper-write-zh FIGURE_MANIFEST 对账。

        规划清单里每张图都必须：产物文件存在 → 图类型有可编辑源（图表 .drawio/.tex）
        → 正文引用。无 FIGURE_MANIFEST 时跳过（无规划合同，不硬造判据）。
        """
        ws = self.workspace
        plan_path = None
        for name in ("PROBLEM_ANALYSIS.md", "PAPER_PLAN.md", "MODELING_REPORT.md", "TOPIC_PLAN.md"):
            candidate = ws / name
            if candidate.is_file() and "<!-- BEGIN FIGURE_MANIFEST -->" in _read_text(candidate):
                plan_path = candidate
                break
        if plan_path is None:
            # 无 FIGURE_MANIFEST 时兼容 DrawIO-N 规划行（paper-figure-drawio Step 6 原口径）
            drawio_plan = ws / "PROBLEM_ANALYSIS.md"
            entries = _parse_drawio_plan(_read_text(drawio_plan)) if drawio_plan.is_file() else []
            if not entries:
                return {"ok": True, "status": "pass", "skipped": True,
                        "reason": "未找到 FIGURE_MANIFEST / DrawIO-N 规划（跳过对账）"}
            plan_path = drawio_plan
        else:
            entries = _parse_figure_manifest(_read_text(plan_path))
        if not entries:
            return {"ok": False, "status": "fail", "missing_files": [],
                    "reason": f"{plan_path.name}: FIGURE_MANIFEST 为空（规划了 0 张图）"}
        paper_text = _paper_text(ws)
        # 嵌入判定只在本步已有正文时执行：paper-figure-drawio 早于写作步骤，
        # 此时无正文是正常时序，不能据此误报"未嵌入"。
        can_check_embedding = bool(paper_text.strip())
        figures_dir = ws / "figures"
        missing_files: list[str] = []
        missing_sources: list[str] = []
        unembedded: list[str] = []
        for entry in entries:
            name, kind = entry["name"], entry["kind"]
            artifacts = [p for ext in ("pdf", "png", "svg")
                         if (p := figures_dir / f"{name}.{ext}").is_file() and p.stat().st_size]
            if not artifacts:
                missing_files.append(name)
                continue
            if kind == "diagram":
                source_ok = any((figures_dir / f"{name}.{ext}").is_file()
                                for ext in ("drawio", "tex"))
                if not source_ok:
                    missing_sources.append(name)
            if can_check_embedding and not re.search(
                    re.escape(name) + r"\.(?:pdf|png|svg)", paper_text):
                unembedded.append(name)
        violations = []
        if missing_files:
            violations.append(f"❌ 规划产物未生成: {', '.join(missing_files[:5])}")
        if missing_sources:
            violations.append(f"❌ 图示缺可编辑源(.drawio/.tex): {', '.join(missing_sources[:5])}")
        if unembedded:
            violations.append(f"❌ 已生成但未嵌入正文: {', '.join(unembedded[:5])}")
        status = "fail" if violations else "pass"
        return {"ok": status == "pass", "status": status, "planned": len(entries),
                "missing_files": missing_files, "missing_sources": missing_sources,
                "unembedded": unembedded,
                "reason": "FIGURE_MANIFEST 对账: " + ("; ".join(violations) if violations else "全部齐全")}

    def check_modeling_machine_contract(self) -> dict:
        """comp-modeling Step 5.5 的机器可核合同：METHOD_CLAIMS_MACHINE + LOGIC_CONTRACT_MACHINE
        + CAPABILITY_CHECKLIST 能力项认领。

        判的是「合同块存在且可被下游脚本消费」，不判方法是否真实现（那是 comp-code 的
        claim_code_check 与语义审查，登记为 manual_items）。
        """
        ws = self.workspace
        report = ws / "MODELING_REPORT.md"
        if not report.is_file():
            return {"ok": False, "status": "fail", "violations": ["缺少 MODELING_REPORT.md"],
                    "reason": "缺少 MODELING_REPORT.md"}
        text = _read_text(report)
        violations: list[str] = []
        unverified: list[str] = []
        claims_block = re.search(r"<!--\s*METHOD_CLAIMS_MACHINE(.*?)-->", text, re.S)
        claims_lines: list[str] = []
        if not claims_block:
            violations.append("缺少 METHOD_CLAIMS_MACHINE 注释块")
        else:
            claims_lines = [line.strip() for line in claims_block.group(1).splitlines()
                            if line.strip()]
            if not claims_lines:
                violations.append("METHOD_CLAIMS_MACHINE 块为空")
            for line in claims_lines:
                if not re.search(r"\bmust\s*:?\s*\S", line):
                    violations.append(f"METHOD_CLAIMS_MACHINE 行缺 must 铁证: {line[:40]}")
        logic_ok = False
        for block in re.findall(r"```json\s*(.*?)```", text, re.S):
            if "LOGIC_CONTRACT_MACHINE" not in block:
                continue
            try:
                payload = json.loads(block)
            except (json.JSONDecodeError, ValueError):
                violations.append("LOGIC_CONTRACT_MACHINE 不是有效 JSON")
                logic_ok = True
                break
            contract = payload.get("LOGIC_CONTRACT_MACHINE") if isinstance(payload, dict) else None
            if not isinstance(contract, dict) or not contract:
                violations.append("LOGIC_CONTRACT_MACHINE 为空或不是对象")
            logic_ok = True
            break
        if not logic_ok:
            violations.append("缺少 LOGIC_CONTRACT_MACHINE JSON 块")
        capability_missing: list[str] = []
        checklist = ws / "CAPABILITY_CHECKLIST.json"
        if checklist.is_file():
            try:
                data = json.loads(checklist.read_text(encoding="utf-8"))
                caps = [c for c in (data.get("capabilities") or [])
                        if isinstance(c, dict) and c.get("id")]
            except (OSError, json.JSONDecodeError, ValueError):
                unverified.append("CAPABILITY_CHECKLIST.json 不可读：能力认领未核验")
                caps = []
            for cap in caps:
                cid = str(cap["id"])
                if not re.search(r"(?<![\w-])" + re.escape(cid) + r"(?![\w-])", text):
                    capability_missing.append(cid)
            if capability_missing:
                violations.append(
                    f"❌ {len(capability_missing)} 条能力项在建模报告中无着落: "
                    f"{', '.join(capability_missing[:5])}")
        status = "fail" if violations else ("unknown" if unverified else "pass")
        return {"ok": status == "pass", "status": status, "violations": violations,
                "capability_missing": capability_missing, "unverified": unverified,
                "claims_lines": len(claims_lines),
                "reason": "建模机器合同: " + ("; ".join(violations) if violations else "合同块齐全")}

    def check_paper_write_gate(self) -> dict:
        """paper-write-zh 完成铁律 + 页数预检 + 摘要数字溯源的可判部分。

        - PDF 模式：paper/main.tex ≥5KB，sections/*.tex 每章 ≥500 字符；
        - docx 模式：paper/main.md ≥5KB（单文件）；
        - 摘要里的每个小数必须在正文（不含摘要自身）或 RESULTS.md 出现；
        - sections 不应含代码块（⚠ 级）、配置 MAX_PAGES 时估算页数不得低于 80%。
        写作风格/摘要语感等登记为 manual_items。
        """
        ws = self.workspace
        paper = ws / "paper"
        main_tex, main_md = paper / "main.tex", paper / "main.md"
        sections = sorted((paper / "sections").glob("*.tex")) if (paper / "sections").is_dir() else []
        violations: list[str] = []
        advisories: list[str] = []
        counts: dict[str, int] = {}
        if main_md.is_file() and not main_tex.is_file():
            counts["main_md_bytes"] = main_md.stat().st_size
            if counts["main_md_bytes"] < 5000:
                violations.append(f"❌ paper/main.md {counts['main_md_bytes']}B < 5000B")
            status = "fail" if violations else "pass"
            return {"ok": status == "pass", "status": status, "mode": "docx",
                    "violations": violations, "advisories": advisories, "counts": counts,
                    "reason": "paper-write 完成铁律(docx): " + ("; ".join(violations) if violations else "通过")}
        if not main_tex.is_file():
            return {"ok": False, "status": "unknown", "unverified": ["paper/main.tex 与 paper/main.md 均缺失"],
                    "reason": "paper-write 完成铁律: 主产物缺失（未核验）"}
        counts["main_tex_bytes"] = main_tex.stat().st_size
        if counts["main_tex_bytes"] < 5000:
            violations.append(f"❌ paper/main.tex {counts['main_tex_bytes']}B < 5000B")
        if not (paper / "references.bib").is_file():
            violations.append("❌ 缺少 paper/references.bib")
        if not sections:
            violations.append("❌ 缺少 paper/sections/*.tex")
        thin = [p.name for p in sections if len(_read_text(p)) < 500]
        counts["thin_sections"] = len(thin)
        if thin:
            violations.append(f"❌ 章节正文 <500 字符: {', '.join(thin[:5])}")
        # 摘要数字必须在正文其他章节或 RESULTS.md 出现
        abstract_files = [p for p in sections
                          if "abstract" in p.name.lower() or "摘要" in p.name]
        other_text = "\n".join(_read_text(p) for p in sections if p not in abstract_files)
        results_md = ws / "RESULTS.md"
        if results_md.is_file():
            other_text += "\n" + _read_text(results_md)
        fabricated: list[str] = []
        for path in abstract_files:
            for number in sorted(set(re.findall(r"\d+\.\d+", _read_text(path)))):
                if number not in other_text:
                    fabricated.append(f"{number}@{path.name}")
        counts["abstract_numbers_unverified"] = len(fabricated)
        if fabricated:
            violations.append(f"⛔ 摘要数字未在正文出现（疑似编造）: {', '.join(fabricated[:5])}")
        # sections 不应含代码块
        for path in sections:
            if re.search(r"\\begin\{(?:lstlisting|verbatim|minted|python|matlab)\}", _read_text(path)):
                advisories.append(f"⚠️ {path.name} 含代码块 — 代码应放 paper/appendix/")
        # 页数预检（仅当显式配置 MAX_PAGES）
        max_pages = _read_max_pages(ws)
        if max_pages:
            total = sum(p.stat().st_size for p in sections)
            estimated = total // 900
            counts["estimated_pages"] = estimated
            if estimated < max_pages * 80 // 100:
                violations.append(
                    f"⛔ 正文估算页数 {estimated} 低于目标 {max_pages} 的 80%")
        status = "fail" if violations else "pass"
        return {"ok": status == "pass", "status": status, "mode": "pdf",
                "violations": violations, "advisories": advisories, "counts": counts,
                "reason": "paper-write 完成铁律: " + ("; ".join(violations) if violations else "通过")}

    def check_paper_scoring_contract(self) -> dict:
        """模板显式 ``paper_scoring: true`` 的链：评分件必须是可解析的评分合同。

        只声明 ``output_files`` 只能证明文件存在；空 JSON ``{}`` 或非法 JSON 同样
        能过 declared_outputs 并被候选冻结。本检查器解析 ``scores`` /
        ``weighted_total`` / ``fatal_dimensions`` 三个下游消费者字段，缺一即 fail。
        """
        path = self.workspace / "PAPER_SCORING.json"
        if not path.is_file():
            return {"ok": False, "status": "fail",
                    "reason": "PAPER_SCORING.json 缺失（模板声明 paper_scoring: true）"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {"ok": False, "status": "fail",
                    "reason": f"PAPER_SCORING.json 不可解析: {exc}"}
        if not isinstance(payload, dict):
            return {"ok": False, "status": "fail",
                    "reason": "PAPER_SCORING.json 顶层必须是对象"}
        missing = [key for key in ("scores", "weighted_total", "fatal_dimensions")
                   if key not in payload]
        violations: list[str] = []
        if missing:
            violations.append(f"❌ 缺评分合同字段: {missing}")
        scores = payload.get("scores")
        if not isinstance(scores, dict) or not scores:
            violations.append("❌ scores 必须是非空对象（每维含分数与正文/图/表位置）")
        if "weighted_total" in payload and not isinstance(
                payload["weighted_total"], (int, float)):
            violations.append("❌ weighted_total 必须是数值")
        if "fatal_dimensions" in payload and not isinstance(payload["fatal_dimensions"], list):
            violations.append("❌ fatal_dimensions 必须是数组")
        status = "fail" if violations else "pass"
        return {"ok": status == "pass", "status": status,
                "dimension_count": len(scores) if isinstance(scores, dict) else 0,
                "violations": violations,
                "reason": "评分合同: " + ("; ".join(violations) if violations
                                          else f"{len(scores)} 维评分合同可解析")}

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
            from ..contracts import contest_profile as cp_mod
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
        workflow_status = str(state.get("status", ""))
        detail = f"声称 {claimed} 轮，实际可核对 {verified_rounds} 轮"
        if problems:
            return {"ok": False, "claimed_rounds": claimed, "verified_rounds": verified_rounds,
                    "problems": problems, "workflow_status": workflow_status,
                    "reason": detail + "；" + "; ".join(problems)}
        early_stop = "；提前结束合法（MAX_ROUNDS 是上限不是必须做满）" if workflow_status == "completed" else ""
        return {"ok": True, "claimed_rounds": claimed, "verified_rounds": verified_rounds,
                "workflow_status": workflow_status, "reason": detail + early_stop}

    @staticmethod
    def _run_check(name: str, fn) -> dict:
        """检查器边界：单个检查抛异常 → 该检查 unknown（≠ 产物不合格），不牵连其他检查。

        unknown 仍是 fail-closed（ok=False）；reason/action 指向修复工具/检查器，
        由分级层决定它是否阻断（blocking 会挡，advisory 只留痕）。
        """
        try:
            return annotate_check_result(name, fn())
        except Exception as exc:  # noqa: BLE001 — 检查器是不可信边界，异常=未核验
            return {"ok": False, "status": "unknown", "severity": resolve_check_severity(name),
                    "action": "fix_tool",
                    "reason": f"检查器执行异常（unknown ≠ 产物不合格）: {type(exc).__name__}: {exc}"}

    def run_all(self, skill_name: str, declared_outputs=None, comp_name: str = "", requires_figures: bool = False,
                required_checks: list[str] | None = None, primary_output=None,
                fingerprint_session=None, manifest_data=None, active_final_step_id: str = "",
                quick_gates: bool = False, quick_gates_max_pages: int | None = None,
                compliance_profile: str = "", page_contract: dict | None = None,
                compliance_block: dict | None = None,
                audit_report_path: Path | None = None,
                template_name: str = "", contract_tier: str = "legacy") -> dict:
        """运行所有门禁检查

        ``contract_tier``（P4-6）：默认 ``legacy`` 保持改造前行为；``delivery``
        收紧主产物判据（min_size 禁用 rglob 兜底 + 按扩展名挂载可解析性检查）。
        """
        if contract_tier not in CONTRACT_TIERS:
            raise ValueError(f"未知合同档位 contract_tier={contract_tier!r}，"
                             f"允许: {', '.join(CONTRACT_TIERS)}")
        # Keep the existing positional ``run_all(skill, comp_name)`` call valid.
        if isinstance(declared_outputs, str) and not comp_name:
            comp_name = declared_outputs
            declared_outputs = None
        self._declared_outputs = declared_outputs
        self._fingerprint_session = fingerprint_session
        self._manifest_data = manifest_data
        self._active_final_step_id = active_final_step_id
        if audit_report_path is not None:
            self._audit_report_path = Path(audit_report_path)
        results = {}
        if declared_outputs is not None:
            artifact_result = ArtifactManifest.validate(self.workspace, declared_outputs, session=fingerprint_session)
            results["artifacts"] = self._run_check("artifacts", lambda: {
                "ok": artifact_result["ok"],
                "missing": artifact_result["missing"],
                "invalid": artifact_result["invalid"],
                "reason": "声明产出齐全且哈希匹配" if artifact_result["ok"] else "声明产出校验失败",
            })
            primary = primary_output
            if primary is None:
                primary = declared_outputs[0] if declared_outputs else None
            if isinstance(primary, dict):
                primary = primary.get("path")
            results["min_size"] = self._run_check(
                "min_size", lambda: self.check_min_size(skill_name, primary, contract_tier))
            # P4-6：交付档按声明产物扩展名自动挂载可解析性检查；legacy/explore
            # 不新增判据（默认参数保持旧行为，避免打断既有调用方）。
            if contract_tier == DELIVERY_TIER and primary and \
                    Path(str(primary)).suffix.lower() in PRIMARY_PARSEABLE_SUFFIXES:
                results["primary_parseable"] = self._run_check(
                    "primary_parseable", lambda: self.check_primary_parseable(primary))
            results["companions"] = self._run_check("companions", lambda: self.check_companions(skill_name))
        else:
            results["min_size"] = self._run_check(
                "min_size", lambda: self.check_min_size(skill_name, None, contract_tier))
            results["companions"] = self._run_check("companions", lambda: self.check_companions(skill_name))
        results["figures"] = self._run_check("figures", lambda: self.check_figure_health() if requires_figures else {
            "ok": True, "skipped": True, "reason": "未声明需要图表检查"
        })
        # 页数门禁只在「本步确实应携带论文」的步骤执行（comp_name 非空 = 模板声明
        # revalidate_paper_pages，或本步为 comp-compile-zh/en）；page_contract 仅作为
        # 口径来源透传（B-02 快照单一事实），**不得**据此把页检扩散到所有步骤——
        # bound 赛事的 page_contract 对每一步都非 None，扩散会让尚无 paper/ 的早期步骤
        # （如 comp-problem-analysis）被"未找到 paper/main.tex"判 FAIL 而无法完成。
        if comp_name:
            results["paper_pages"] = self._run_check(
                "paper_pages", lambda: self.check_paper_pages(comp_name, page_contract=page_contract))
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
                results[f"required_{name}"] = self._run_check(
                    f"required_{name}", lambda name=name: {"ok": False, "reason": f"未知质量门禁: {name}"})
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
                    results[name] = self._run_check(
                        name, lambda: self.check_review_evidence(mode=review_mode, strict_model_match=strict))
                else:
                    results[name] = self._run_check(name, named_checks[name])
        # P3：按 (template, step) 自动挂载引擎检查器（checkers/registry.json）。
        # 注册表缺失 = 安装损坏：默认路径缺席时 P3 检查器会整体静默消失，故按
        # unknown 阻断（fix_tool），不允许「空表 = 全部通过」。显式传路径的
        # load_checker_registry(path) 仍保留空表语义供单测/工具使用。
        if template_name and not CHECKER_REGISTRY_PATH.is_file():
            results["checker_registry"] = self._run_check("checker_registry", lambda: {
                "ok": False, "status": "unknown", "action": "fix_tool",
                "reason": f"检查器注册表缺失: {CHECKER_REGISTRY_PATH}（P3 自动检查器未执行）"})
        # 模板显式 required_checks 同名时以模板为准（不重复执行）。
        for entry in auto_checks_for(template_name, skill_name):
            name = str(entry.get("name") or "")
            method_name = str(entry.get("implementation") or "")
            if not name or not method_name or name in results:
                continue
            method = getattr(self, method_name, None)
            if not callable(method):
                results[name] = {"ok": False, "status": "unknown", "action": "fix_tool",
                                 "reason": f"注册检查器 {name} 的实现 {method_name} 不存在"}
                continue
            results[name] = annotate_auto_check(entry, self._run_check(name, method))
        # D3 门禁前移程序化（B窗 2026-09-26 接入）：模板声明 metadata.quick_gates=true 的
        # 步骤由引擎在验收时直接执行早检，不再依赖模型先跑脚本再回报。参数取真实合同：
        # max_pages 优先步骤声明（quick_gates_max_pages），缺省回落 compliance 口径；
        # ERROR（解析失败/编排异常）按失败计入，不得冒充 PASS；SKIP（产物未齐）不阻断。
        if quick_gates:
            results["early_quality"] = self._run_check("early_quality", lambda: self.check_early_quality(
                max_pages=quick_gates_max_pages, compliance_profile=compliance_profile,
                page_contract=page_contract, compliance_block=compliance_block))
        # 统一补 severity/status（检查器自身已标注 unknown 的原样保留）：
        # ok 恒等于 (status == "pass")，任何检查都不得缺 status。
        results = {name: annotate_check_result(name, result) for name, result in results.items()}
        all_ok = all(r["ok"] for r in results.values())
        return {"ok": all_ok, "checks": results}


# P3 注册表启动守护：实现缺失/档位不一致/shadow 阻断/挂载键不全 → 拒绝加载。
def _assert_checker_registry_ready() -> None:
    problems = validate_checker_registry(
        load_checker_registry(), implementations=set(dir(QualityGate)))
    if problems:
        raise RuntimeError("检查器注册表校验失败: " + "; ".join(problems))


_assert_checker_registry_ready()


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
    gate.add_argument("--template", default="", help="模板名（applies_to 匹配用）")
    gate.add_argument("--check", default="",
                      help="单跑注册检查器（名字或实现方法名）；退出码 0=pass 1=fail 3=unknown/未注册")

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
        if args.check:
            entry = find_checker(args.check)
            if entry is None:
                print(json.dumps({"ok": False, "status": "unknown",
                                  "reason": f"未注册的检查器: {args.check}"},
                                 ensure_ascii=False, indent=2))
                return 3
            method = getattr(g, str(entry.get("implementation") or ""), None)
            if not callable(method):
                print(json.dumps({"ok": False, "status": "unknown",
                                  "reason": f"检查器实现不存在: {entry.get('implementation')}"},
                                 ensure_ascii=False, indent=2))
                return 3
            result = annotate_auto_check(entry, annotate_check_result(entry["name"], method()))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return {"pass": 0, "fail": 1}.get(str(result.get("status")), 3)
        result = g.run_all(args.skill, args.comp, template_name=args.template)
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
