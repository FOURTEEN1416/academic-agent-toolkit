"""唯一赛事档案解析器（B窗 2026-09-27 赛事规则隔离；B-02 端到端隔离重构）。

数据真源：engine/modex-core/comp_rules.json（E独占写，本模块只读）。

身份与偏好分离（B-02）：
  - 赛事身份只有两类显式来源：① 模板名（templates.json 的 comp_* 键与 comp_rules
    顶层键 1:1，模板名即锁定身份）；② 通用模板经 params["contest"]["id"] 显式选择。
  - 固定赛事模板 + 显式赛事ID冲突 → ContestProfileError（拒绝，不静默改写身份）。
  - edition/submission_form 是**选择维度**不是覆盖标签：档案提供 profiles 维度时
    按其选出真正对应的规则（无匹配即显式失败，不回退）；档案无此维度时显式记
    missing_fields，绝不把请求值当规则用。
  - 任务偏好（page_target 目标 / page_cap 任务门禁口径）只随当前工作流生效：
    page_target 只进写作上下文；page_cap 不得放宽已核验官方硬上限。

页数语义分名（B-02）：总页数与正文页限是两个语义，禁止共用一个名字——
  - max_body_pages：正文口径上限（compliance.max_body_pages，或 page_scope=body
    的顶层 max_pages）；
  - max_total_pages：全 PDF 计上限（page_scope 缺席/total 的顶层 max_pages，
    与引擎 check_paper_pages 的既有判定语义一致）；
  - 上限性质（status）来自档案数据自带的 verification/classification；档案无
    性质与来源记载时一律 unverified，**不自动升级为官方硬限制**。

快照纪律（B-02）：工作流启动时把有效档案冻结进 workflow metadata
（contest_profile_snapshot）；此后所有消费者（context/写作/页数/早检/打包/终审）
读同一份快照，全局配置变化不静默改变旧任务；无快照的既有任务显式标
pending_binding，不拿现盘规则冒充历史快照。

⛔ 禁止项在此程序化：字符串包含/前缀匹配、中文赛事名映射、未知回退默认国赛、
缺省页数兜底——一律不实现；显式声明错误必须显式失败。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

RULES_FILE = Path(__file__).resolve().parent / "modex-core" / "comp_rules.json"

# 约束/上限性质（封闭集合；档案数据未记载性质 → unverified，不猜测升级）
STATUS_VERIFIED = "official_verified"
STATUS_TASK_OVERRIDE = "task_override"
STATUS_UNVERIFIED = "unverified"


class ContestProfileError(ValueError):
    """显式赛事声明无法解析（未知ID/身份冲突/届次形态无匹配）。不提供默认回退。"""


@dataclass(frozen=True)
class ContestProfile:
    contest_id: str
    profile_id: str                     # contest_id 或档案 profiles 维度的显式 profile_id
    name: str
    language: str
    edition: str | None                 # 选中的届次（档案数据或选择结果；不是自由标签）
    submission_form: str | None
    rules_revision: str                 # 版本标识：档案显式字段优先，回落档案文件sha256
    max_total_pages: int | None         # 全 PDF 计上限（page_scope 缺席/total 的语义）
    max_body_pages: int | None          # 正文口径上限（compliance.max_body_pages / body scope）
    page_cap_status: str                # operative 门禁口径的性质（verified/task_override/unverified）
    page_scope: str | None
    appendix_unlimited: bool | None
    template_cls: str | None
    compliance: dict[str, Any] = field(default_factory=dict)
    operative: dict[str, Any] = field(default_factory=dict)        # 本任务 operative 页数口径
    constraints: tuple[dict[str, Any], ...] = ()   # 逐项 {name,status,value,scope,source_ids}
    guidance: tuple[dict[str, Any], ...] = ()      # 经验建议带，独立于 constraints
    non_inherited_overrides: tuple[dict[str, Any], ...] = ()  # 档案中的历史任务裁决，本任务不继承
    missing_fields: tuple[str, ...] = ()
    override: dict[str, Any] = field(default_factory=dict)          # 身份/选择显式声明留痕
    task_preferences: dict[str, Any] = field(default_factory=dict)  # 页数目标等，只影响当前任务
    source: dict[str, Any] = field(default_factory=dict)

    @property
    def gate_page_cap(self) -> int | None:
        """本任务 operative 门禁页数口径。"""
        return self.operative.get("cap")

    @property
    def gate_page_scope(self) -> str:
        return str(self.operative.get("scope") or "total")

    def context_view(self) -> dict[str, Any]:
        """下发执行上下文的紧凑视图：只含当前适用规则，不含其他赛事正文。"""
        return {
            "status": "bound",
            "profile_id": self.profile_id,
            "contest_id": self.contest_id,
            "name": self.name,
            "language": self.language,
            "edition": self.edition,
            "submission_form": self.submission_form,
            "rules_revision": self.rules_revision,
            "max_total_pages": self.max_total_pages,
            "max_body_pages": self.max_body_pages,
            "page_cap_status": self.page_cap_status,
            "page_scope": self.page_scope,
            "gate_page_cap": self.gate_page_cap,
            "gate_page_scope": self.gate_page_scope,
            "operative": dict(self.operative),
            "appendix_unlimited": self.appendix_unlimited,
            "compliance": self.compliance,
            "constraints": [dict(c) for c in self.constraints],
            "guidance": [dict(g) for g in self.guidance],
            "non_inherited_overrides": [dict(o) for o in self.non_inherited_overrides],
            "missing_fields": list(self.missing_fields),
            "override": self.override,
            "task_preferences": self.task_preferences,
            "page_semantics": {
                "max_total_pages": "全PDF计上限（Summary/目录/正文/参考文献均计入）",
                "max_body_pages": "正文口径上限（附录另计的赛事）",
                "page_target": "任务页数目标（只影响当前任务，不是上限，不放宽官方硬限制）",
                "page_cap": "任务门禁口径（只影响当前任务；不得放宽已核验官方硬上限）",
            },
            "source": self.source,
        }

    def to_snapshot(self) -> dict[str, Any]:
        """冻结进 workflow metadata 的有效档案快照（context/页数/早检/打包/终审消费同一份）。"""
        snap = self.context_view()
        snap["resolved_at"] = datetime.now().isoformat(timespec="seconds")
        snap["identity_source"] = self.source.get("declared_sources", [""])[0]
        return snap


_RULES_CACHE: dict[str, Any] = {}


def _load_rules(rules_file: Path | None = None) -> dict[str, Any]:
    path = Path(rules_file) if rules_file else RULES_FILE
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    cached = _RULES_CACHE.get(str(path))
    if cached and cached[0] == digest:
        return cached[1]
    if not path.is_file():
        raise ContestProfileError(f"赛事档案缺失: {path}")
    rules = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rules, dict):
        raise ContestProfileError(f"赛事档案不是对象: {path}")
    # schema v2（E-MERGE-01 合并版）：赛事表包裹在顶层 contests 键下（sources 为
    # 平级来源登记表）；v1 扁平形态无该键，原样使用。unwrap 后下游
    # （known_contest_ids/_entry_for/is_known_contest）对两形态同构。
    contests = rules.get("contests")
    if isinstance(contests, dict) and contests:
        rules = contests
    _RULES_CACHE[str(path)] = (digest, rules)
    return rules


def rules_digest(rules_file: Path | None = None) -> str:
    path = Path(rules_file) if rules_file else RULES_FILE
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def known_contest_ids(rules_file: Path | None = None) -> list[str]:
    return sorted(_load_rules(rules_file).keys())


def _entry_for(contest_id: str, rules_file: Path | None) -> dict[str, Any]:
    """精确键命中；任何模糊形态（子串/前缀/中文名/大小写变体）都不是匹配。"""
    rules = _load_rules(rules_file)
    if contest_id not in rules:
        raise ContestProfileError(
            f"未知赛事ID {contest_id!r}（comp_rules.json 顶层键须精确命中；"
            f"可用: {', '.join(sorted(rules.keys()))}）。不做名称推断，不默认任何赛事")
    entry = rules[contest_id]
    if not isinstance(entry, dict):
        raise ContestProfileError(f"赛事条目非法: {contest_id}")
    return entry


def is_known_contest(name: str, rules_file: Path | None = None) -> bool:
    """模板名是否为已配置赛事（精确键）；用于区分"非赛事模板"与"待绑定赛事任务"。"""
    return name in _load_rules(rules_file)


# ── 上限性质判定：只认档案数据自带记载，绝不自动升级 ─────────────────────────

def _classification(entry: dict[str, Any]) -> dict[str, Any]:
    bands = entry.get("classification")
    return bands if isinstance(bands, dict) else {}


def _verification_status(entry: dict[str, Any]) -> str:
    ver = entry.get("verification")
    return str(ver["status"]) if isinstance(ver, dict) and ver.get("status") else ""


def _task_override_on(entry: dict[str, Any], key_frag: str) -> dict[str, Any] | None:
    for item in _classification(entry).get("task_override") or []:
        if isinstance(item, dict) and key_frag in str(item.get("key", "")):
            return item
    return None


def _official_claim_covering(entry: dict[str, Any], *fragments: str) -> dict[str, Any] | None:
    claims = _classification(entry).get("official_verified") or []
    for item in claims:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", ""))
        if any(frag in claim for frag in fragments):
            return item
    return None


def _status_for(entry: dict[str, Any], *, claim_fragments: tuple[str, ...],
                cap_field: str | None) -> str:
    """性质三源：task_override 带（显式裁决）> official_verified 带（官方主张）
    > verification.status == verified_official > unverified（档案无记载，不升级）。"""
    if cap_field and _task_override_on(entry, cap_field) is not None:
        return STATUS_TASK_OVERRIDE
    if _official_claim_covering(entry, *claim_fragments) is not None:
        return STATUS_VERIFIED
    if _verification_status(entry) == "verified_official":
        return STATUS_VERIFIED
    return STATUS_UNVERIFIED


def _migration_task_override(entry: dict[str, Any]) -> dict[str, Any] | None:
    """schema v2：赛事级 migration_evidence 中带 ruling+数值页数的任务裁决条目。

    E-MERGE-01 把历史任务口径（如华为 80）移出全局有效规则、只留痕于此；
    带 ruling（显式裁决）且 value 为正整数才认定为任务口径，legacy 记录不认。"""
    ev = entry.get("migration_evidence")
    if not isinstance(ev, list):
        return None
    for item in ev:
        if (isinstance(item, dict) and item.get("ruling")
                and isinstance(item.get("value"), int) and item["value"] > 0):
            return item
    return None


def _page_cap_from_constraints(entry: dict[str, Any]) -> dict[str, Any] | None:
    """schema v2（constraints 带）页数口径：kind=page_limit 约束是口径唯一承载。

    status=verified → value.basis(body/total)/value.limit 分名取值；unknown/
    not_applicable（E 契约钉死 value=null）→ 无口径，不猜不兜底。
    任务裁决（migration_evidence）优先级与 v1 同：置 TASK_OVERRIDE，由
    resolve_operative_cap 走非继承。非 constraint 带形态返回 None（走 v1 路径）。
    """
    cons = entry.get("constraints")
    if not (isinstance(cons, list) and cons):
        return None
    limits = [c for c in cons if isinstance(c, dict) and c.get("kind") == "page_limit"]
    if len(limits) > 1:
        raise ContestProfileError(
            f"档案 constraints 带含 {len(limits)} 条 page_limit 约束，页数口径歧义不猜"
            f"（{[c.get('id') for c in limits]}）")
    body_cap = total_cap = None
    scope = None
    cap_field = ""
    band_status = STATUS_UNVERIFIED
    if limits:
        c = limits[0]
        if str(c.get("status")) == "verified":
            value = c.get("value")
            if not isinstance(value, dict) or not isinstance(value.get("limit"), int):
                raise ContestProfileError(
                    f"约束 {c.get('id')!r} status=verified 但 value.limit 非整数页数: {value!r}")
            basis = str(value.get("basis") or "total")
            cap_field = f"constraints:{c.get('id')}"
            band_status = STATUS_VERIFIED
            if basis == "body":
                body_cap, scope = int(value["limit"]), "body"
            else:
                total_cap, scope = int(value["limit"]), "total"
    override = _migration_task_override(entry)
    if override is not None:
        return {"max_total_pages": total_cap, "max_body_pages": body_cap,
                "page_scope": scope, "status": STATUS_TASK_OVERRIDE,
                "cap_field": cap_field,
                "task_override": {"key": "max_pages", "ruling": str(override.get("ruling", "")),
                                  "scope": str(override.get("scope", "")),
                                  "value": override.get("value")}}
    return {"max_total_pages": total_cap, "max_body_pages": body_cap,
            "page_scope": scope, "status": band_status,
            "cap_field": cap_field, "task_override": None}


def page_cap_contract(entry: dict[str, Any]) -> dict[str, Any]:
    """档案页数口径契约：上限值 + 口径范围（body/total）+ 性质 + 来源字段。

    唯一实现，engine/quality_gates 与 skills 脚本（quick_gates/pack_submission）
    共同调用，杜绝各自副本。总页数与正文页限在这里就分开命名，禁止混用。
    """
    band = _page_cap_from_constraints(entry)
    if band is not None:
        return band
    compliance = entry.get("compliance") if isinstance(entry.get("compliance"), dict) else {}
    scope = str(entry["page_scope"]) if entry.get("page_scope") else None
    body = compliance.get("max_body_pages")
    top = entry.get("max_pages")
    body_cap = body if isinstance(body, int) and body > 0 else (
        top if isinstance(top, int) and top > 0 and scope == "body" else None)
    total_cap = top if isinstance(top, int) and top > 0 and scope != "body" else None
    if body_cap is not None:
        cap_field = "compliance.max_body_pages" if isinstance(body, int) and body > 0 else "max_pages(page_scope=body)"
        status = _status_for(entry, claim_fragments=("页", "max_pages"), cap_field="max_pages")
    elif total_cap is not None:
        cap_field = "max_pages(page_scope=total)"
        status = _status_for(entry, claim_fragments=("页", "max_pages"), cap_field="max_pages")
    else:
        cap_field, status = "", _status_for(entry, claim_fragments=("页数上限",), cap_field="max_pages")
    override = _task_override_on(entry, "max_pages") if status == STATUS_TASK_OVERRIDE else None
    return {
        "max_total_pages": total_cap,
        "max_body_pages": body_cap,
        "page_scope": scope,
        "status": status,
        "cap_field": cap_field,
        "task_override": dict(override) if override else None,
    }


def resolve_operative_cap(contract: dict[str, Any], explicit_task_cap: int | None = None) -> dict[str, Any]:
    """本任务 operative 门禁口径（唯一裁决点，早检/编译页检共用同一份）。

    1. 任务显式声明（step metadata / params.contest.page_cap）→ explicit_task，
       只影响当前任务；
    2. 档案口径性质为 task_override（历史任务裁决）→ **不自动继承**（cap=None，
       新任务如需口径必须显式声明——"新任务不继承单次80页"程序化在此）；
    3. official_verified → 档案口径作为已核验官方硬上限执行；
    4. unverified（档案无性质/来源记载）→ **不产生任何默认硬页限**：cap 仅在
       档案显式记载口径值时提供（无记载即 cap=None，页检 SKIP），阈值按档案
       显式值判定并随结果携带 page_cap_status=unverified——不当作已证官方规则、
       不自动升级，对应合规结论按 unknown 阻塞（既不放行也不编出限制）。

    与技能正文（comp-paper/comp-compile 系）共用同一三分性话语：
    official_verified / 显式任务授权才按硬上限执行；禁止"未知照值当硬限制"
    的表述与实现，禁止把未知官方规则包装成任务覆盖。
    """
    if explicit_task_cap is not None:
        return {"cap": int(explicit_task_cap), "scope": "body", "status": "explicit_task",
                "reason": "任务显式声明口径（只影响当前任务）"}
    if contract.get("status") == STATUS_TASK_OVERRIDE:
        ov = contract.get("task_override") or {}
        return {"cap": None, "scope": contract.get("page_scope") or "total",
                "status": STATUS_TASK_OVERRIDE,
                "reason": f"档案页数口径为历史任务裁决，不自动继承（ruling: {ov.get('ruling', '')}；"
                          f"scope: {ov.get('scope', '')}）；本任务如需页数口径请显式声明"}
    cap = contract.get("max_body_pages")
    scope = "body"
    if cap is None:
        cap = contract.get("max_total_pages")
        scope = "total"
    return {"cap": cap, "scope": scope, "status": contract.get("status") or STATUS_UNVERIFIED,
            "reason": "" if cap is not None else "档案无页数口径（该赛事无页数合同）"}


# ── profiles 维度选择（总调度批准 v2 方向：按届次/形态选真正对应的规则） ──────

def _select_dimension_profile(contest_id: str, entry: dict[str, Any],
                              edition: str | None, submission: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """档案带 profiles 维度时按 edition/submission_form 选出唯一匹配。

    显式请求无匹配 → ContestProfileError（不回退、不静默取第一条）；
    匹配不唯一 → 要求更精确（region/phase/profile_id），不猜。
    """
    profiles = entry.get("profiles")
    if not (isinstance(profiles, list) and profiles and all(isinstance(p, dict) for p in profiles)):
        return entry, {}
    selection_note: dict[str, Any] = {"selection_dimension": "profiles"}

    def matches(p: dict[str, Any]) -> bool:
        if edition and str(p.get("edition", "")) != edition:
            return False
        if submission and str(p.get("submission_form", "")).lower() != submission.lower():
            return False
        return True

    cands = [p for p in profiles if matches(p)]
    if not cands:
        have = [(p.get("edition"), p.get("submission_form")) for p in profiles]
        raise ContestProfileError(
            f"{contest_id} 无匹配 edition={edition!r} submission_form={submission!r} 的 profile"
            f"（现有: {have}）。届次/提交形式必须选择真实对应规则，不回退默认")
    if len(cands) > 1:
        raise ContestProfileError(
            f"{contest_id} 匹配到 {len(cands)} 个 profile，须以 region/phase/profile_id 精确化，不猜测")
    chosen = cands[0]
    selection_note["profile_id"] = chosen.get("profile_id") or ""
    merged = {k: v for k, v in entry.items() if k != "profiles"}
    merged.update(chosen)
    return merged, selection_note


def resolve_profile(template_name: str, params: dict[str, Any] | None = None,
                    rules_file: Path | None = None) -> ContestProfile | None:
    """解析当前工作流的有效赛事档案（B-02：身份/偏好分离 + 选择维度 + 性质留痕）。

    - 非赛事模板且无显式选择 → None（不默认任何赛事）；
    - 固定赛事模板 + params.contest.id 冲突 → ContestProfileError（拒绝改写身份）；
    - 通用模板 + params.contest.id 显式选择 → 该赛事；未知ID → ContestProfileError；
    - edition/submission_form 是选择维度（档案有 profiles 即选择；无该维度显式记缺席）；
    - page_target/page_cap 是任务偏好：只影响当前工作流；page_cap 不得放宽已核验官方上限。
    """
    params = params or {}
    declared = params.get("contest") if isinstance(params.get("contest"), dict) else {}
    declared_id = str(declared.get("id") or "").strip() or None
    template_is_contest = is_known_contest(template_name or "", rules_file)

    if template_is_contest and declared_id and declared_id != template_name:
        raise ContestProfileError(
            f"赛事身份冲突：模板 {template_name!r} 已锁定赛事 {template_name}，"
            f"params.contest.id 又声明 {declared_id!r}——固定赛事模板与显式赛事ID冲突必须拒绝，"
            f"不以覆盖名义改写身份（任务偏好请用 page_target/page_cap）")
    contest_id = template_name if template_is_contest else declared_id
    if not contest_id:
        return None

    entry = _entry_for(contest_id, rules_file)  # 显式选择的未知ID在此显式失败

    edition_req = str(declared.get("edition") or "").strip() or None
    submission_req = str(declared.get("submission_form") or "").strip().lower() or None
    entry, selection_note = _select_dimension_profile(contest_id, entry, edition_req, submission_req)

    # edition/submission_form 只取数据支撑值（档案字段或 profiles 选择结果）；
    # 请求值无维度可选时记入 override + missing，不冒充数据
    edition = str(entry["edition"]).strip() if entry.get("edition") else None
    submission = str(entry["submission_form"]).strip().lower() if entry.get("submission_form") else None

    missing: list[str] = []
    for f in ("edition", "submission_form"):
        if not entry.get(f):
            missing.append(f)
    if selection_note.get("selection_dimension") != "profiles":
        if edition_req and not entry.get("edition"):
            missing.append("edition_selection_unavailable")
        if submission_req and not entry.get("submission_form"):
            missing.append("submission_form_selection_unavailable")

    contract = page_cap_contract(entry)
    compliance = entry.get("compliance") if isinstance(entry.get("compliance"), dict) else {}
    if not compliance and isinstance(entry.get("constraints"), list) and entry["constraints"]:
        compliance = _v2_compliance_view(entry["constraints"])

    # 任务偏好：目标只进上下文；page_cap 是任务门禁口径，不得放宽已核验官方上限
    preferences: dict[str, Any] = {}
    if declared.get("page_target") is not None:
        preferences["page_target"] = declared["page_target"]
    if declared.get("page_cap") is not None:
        cap_req = declared["page_cap"]
        if not (isinstance(cap_req, int) and cap_req > 0):
            raise ContestProfileError(f"params.contest.page_cap 非法: {cap_req!r}（须正整数页数）")
        official_cap = contract["max_body_pages"] if contract["max_body_pages"] is not None else contract["max_total_pages"]
        if (contract["status"] == STATUS_VERIFIED and official_cap is not None
                and cap_req > official_cap):
            raise ContestProfileError(
                f"任务页数口径 {cap_req} 不得放宽已核验官方硬上限 {official_cap}（{contest_id}）——"
                f"任务偏好只影响当前任务，不能放宽官方硬限制")
        preferences["page_cap"] = cap_req
        preferences["page_cap_scope"] = "body"  # 任务口径按正文口径执行（与早检正文语义一致）

    operative = resolve_operative_cap(contract, preferences.get("page_cap"))
    constraints, non_inherited = _build_constraints(entry, contract, compliance, operative)

    raw_guidance = entry.get("guidance")
    if isinstance(raw_guidance, list) and raw_guidance:
        # schema v2：guidance 带在 profile 上（{topic,text,basis,nature}）
        guidance = tuple(
            {"text": str(i.get("text", "")),
             "source": str(i.get("basis") or i.get("source") or ""),
             "nature": str(i.get("nature", "experience"))}
            for i in raw_guidance if isinstance(i, dict))
    else:
        guidance = tuple(
            {"text": str(i.get("text", "")), "source": str(i.get("source", "")), "nature": str(i.get("nature", "experience"))}
            for i in (_classification(entry).get("experience") or []) if isinstance(i, dict))

    digest = rules_digest(rules_file)
    revision = str(entry.get("rules_revision") or digest)
    profile_id = str(selection_note.get("profile_id") or contest_id)

    override_record = {k: declared[k] for k in ("id", "edition", "submission_form") if k in declared}
    source = {
        "rules_file": str(rules_file or RULES_FILE),
        "rules_sha256": digest,
        "rules_revision": revision,
        "entry_key": contest_id,
        "profile_id": profile_id,
        "declared_sources": (["template_name"] if template_is_contest else [])
                            + (["params.contest"] if declared_id else []),
        "selection": selection_note,
        "verification_status": _verification_status(entry) or "unrecorded",
    }
    return ContestProfile(
        contest_id=contest_id,
        profile_id=profile_id,
        name=str(entry.get("name", contest_id)),
        language=str(entry.get("language", "")),
        edition=edition,
        submission_form=submission,
        rules_revision=revision,
        max_total_pages=contract["max_total_pages"],
        max_body_pages=contract["max_body_pages"],
        page_cap_status=contract["status"],
        page_scope=contract["page_scope"],
        appendix_unlimited=bool(entry["appendix_unlimited"]) if "appendix_unlimited" in entry else None,
        template_cls=str(entry["template_cls"]) if entry.get("template_cls") else None,
        compliance=dict(compliance),
        operative=operative,
        constraints=constraints,
        guidance=guidance,
        non_inherited_overrides=non_inherited,
        missing_fields=tuple(missing),
        override=override_record,
        task_preferences=preferences,
        source=source,
    )


def _v2_compliance_view(cons: list) -> dict[str, Any]:
    """schema v2：约束带 → 脚本消费者（pledge 方向判定）所需的等效 compliance 视图。

    只映射带内核验/记载的承诺书状态；unknown（value=null）不构造——下游如实
    SKIP/unknown，不冒充任何方向。"""
    view: dict[str, Any] = {}
    for c in cons:
        if not isinstance(c, dict) or c.get("kind") != "pledge_page":
            continue
        value = c.get("value") if isinstance(c.get("value"), dict) else {}
        presence = str(value.get("presence") or "")
        if presence == "forbidden":
            view["pledge_page"] = "forbidden_in_electronic"
        elif presence == "required":
            view["pledge_page"] = "required"
        elif presence == "absent":
            view["pledge_page"] = "absent_in_official_template"
    return view


def _build_constraints(entry: dict[str, Any], contract: dict[str, Any],
                       compliance: dict[str, Any],
                       operative: dict[str, Any]) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """逐项约束 {name,status,value,scope,source_ids}；性质只来自档案记载，缺席即 unverified。

    返回 (本任务适用的约束, 不继承的历史裁决)。官方"无页数上限条款"也是已核验
    结论（value=None + official_verified），与"未核验"严格区分——未知不冒充任何一侧。
    """
    cons = entry.get("constraints")
    if isinstance(cons, list) and cons:
        return _build_constraints_from_band(cons, contract, operative)
    items: list[dict[str, Any]] = []
    non_inherited: list[dict[str, Any]] = []

    if contract["status"] == STATUS_TASK_OVERRIDE:
        # 档案口径是历史任务裁决：不进本任务约束（新任务不继承），留痕披露
        ov = contract["task_override"] or {}
        non_inherited.append({"key": str(ov.get("key", "max_pages")), "value": ov.get("value"),
                              "ruling": str(ov.get("ruling", "")), "scope": str(ov.get("scope", "")),
                              "reason": "历史任务裁决不自动继承；本任务如需口径须显式声明"})
        official_no_cap = _official_claim_covering(entry, "无页数上限")
        items.append({"name": "official_page_cap", "value": None, "scope": "official",
                      "status": STATUS_VERIFIED if official_no_cap else STATUS_UNVERIFIED,
                      "source_ids": [str(official_no_cap.get("evidence", ""))] if official_no_cap else [],
                      "note": "官方无页数上限条款（已核验负面结论）" if official_no_cap
                              else "官方口径未记载（官方上限有无均未核验）"})
    elif operative.get("cap") is not None:
        items.append({"name": "page_cap", "value": operative["cap"], "scope": operative["scope"],
                      "status": operative["status"],
                      "source_ids": [f"comp_rules.{contract['cap_field']}"] if contract["cap_field"] else []})

    if operative.get("status") == "explicit_task":
        items.append({"name": "page_cap_task_override", "value": operative["cap"],
                      "scope": "task:当前任务显式声明", "status": STATUS_TASK_OVERRIDE,
                      "source_ids": ["params.contest.page_cap / step metadata"],
                      "note": "任务显式口径只影响当前任务，不写回全局档案"})
    pledge = compliance.get("pledge_page")
    if pledge:
        pledge_claim = _official_claim_covering(entry, "承诺书")
        items.append({"name": "pledge_page", "value": pledge, "scope": "electronic_preface",
                      "status": STATUS_VERIFIED if (pledge_claim or _verification_status(entry) == "verified_official") else STATUS_UNVERIFIED,
                      "source_ids": [str(pledge_claim.get("evidence", ""))] if pledge_claim else []})
    return tuple(items), tuple(non_inherited)


def _build_constraints_from_band(
        cons: list, contract: dict[str, Any], operative: dict[str, Any],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """schema v2：档案约束带即本任务约束，逐项透传（三态封闭 verified/unknown/
    not_applicable，unknown value=null 由 E 窗契约保证）。

    任务裁决不进本任务约束（非继承），仅留痕 non_inherited；显式任务口径照旧
    追加 page_cap_task_override。页数口径已由带内 page_limit 约束承载，不再
    二次合成 page_cap 项。"""
    items = [
        {k: v for k, v in {
            "name": str(c.get("id", "")),
            "kind": str(c.get("kind", "")),
            "status": str(c.get("status", "")),
            "value": c.get("value"),
            "scope": str(c.get("scope", "")),
            "source_ids": list(c.get("source_ids") or []),
            "note": str(c["note"]) if c.get("note") else None,
            "locator": str(c["locator"]) if c.get("locator") else None,
        }.items() if v is not None}
        for c in cons if isinstance(c, dict)]
    non_inherited: list[dict[str, Any]] = []
    if contract.get("status") == STATUS_TASK_OVERRIDE:
        ov = contract.get("task_override") or {}
        non_inherited.append({"key": str(ov.get("key", "max_pages")), "value": ov.get("value"),
                              "ruling": str(ov.get("ruling", "")), "scope": str(ov.get("scope", "")),
                              "reason": "历史任务裁决不自动继承；本任务如需口径须显式声明"})
    if operative.get("status") == "explicit_task":
        items.append({"name": "page_cap_task_override", "value": operative["cap"],
                      "scope": "task:当前任务显式声明", "status": STATUS_TASK_OVERRIDE,
                      "source_ids": ["params.contest.page_cap / step metadata"],
                      "note": "任务显式口径只影响当前任务，不写回全局档案"})
    return tuple(items), tuple(non_inherited)


# ── 快照消费侧（runner/session/audit 共用；B-02 端到端同一份） ────────────────

def pending_binding_snapshot(template_name: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """既有工作流无快照时的显式标记：待绑定/确认，不拿现盘规则冒充历史快照。"""
    declared = (params or {}).get("contest") if isinstance((params or {}).get("contest"), dict) else {}
    return {
        "status": "pending_binding",
        "contest_hint": str(declared.get("id") or template_name or ""),
        "declared": dict(declared),
        "reason": "工作流创建于快照机制启用前，无有效档案快照；现盘规则可能是任务启动后变更的，"
                  "不冒充历史快照。合规/页数口径在显式绑定前不下发、不执行。",
    }


def compliance_conclusion(snapshot: dict[str, Any] | None, *, contest_intent: bool) -> dict[str, Any]:
    """终审合规结论：unknown ≠ PASS。

    - 无赛事语义 → not_applicable（无关建模不受合规缺证影响）；
    - 有赛事语义但无 bound 快照（待绑定）→ unknown（阻塞正式 ready，不伪放行）；
    - bound 快照中任一约束 unverified → unknown 并列明；全部已核验/任务裁决 → pass。
    """
    if not isinstance(snapshot, dict) or snapshot.get("status") != "bound":
        if contest_intent:
            return {"verdict": "unknown",
                    "reason": "赛事工作流无 bound 档案快照（pending_binding）——"
                              "不冒用现盘规则，正式 ready 不把 unknown 当 PASS"}
        return {"verdict": "not_applicable", "reason": "非赛事工作流，无赛事合规结论"}
    constraints = snapshot.get("constraints") or []
    unknown = [c for c in constraints if c.get("status") in {"unverified", "unknown"}]
    if unknown:
        names = ", ".join(str(c.get("name")) for c in unknown)
        return {"verdict": "unknown",
                "reason": f"以下约束缺性质/来源核验，不构成合规结论: {names}（E窗补核验数据后自动解除）",
                "unknown_constraints": unknown}
    return {"verdict": "pass", "reason": "快照内全部约束已核验或为显式任务裁决"}


def load_entry(contest_id: str, rules_file: Path | None = None) -> dict[str, Any]:
    """脚本消费者（quick_gates/pack_submission 等）的收敛入口：替代各自副本加载器。"""
    return dict(_entry_for(contest_id, rules_file))


def compliance_profile(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """兼容旧消费者语义：返回条目的 compliance 块（无则 None，不构造）。"""
    if not isinstance(entry, dict):
        return None
    block = entry.get("compliance")
    return dict(block) if isinstance(block, dict) else None
