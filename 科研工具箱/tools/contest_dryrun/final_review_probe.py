"""终审真实模型调用探针（链路验证级；step12 comp-final-review 的辅助产物生成器）。

2026-09-09 审计教训：终审证据必须由**真实配置的模型**执行——模型名与 contest_models.json
配置不一致会被 strict 门禁拒绝（不可伪造）。本探针不预设模型：端点与模型全部来自环境
（仓库不预设任何厂商，比赛时配置哪个模型就用哪个）。

端点解析（三级，取第一个齐备的）：
  1. ACAT_FINAL_BASE_URL + ACAT_FINAL_API_KEY + ACAT_FINAL_MODEL
  2. SENSENOVA_BASE_URL + SENSENOVA_API_KEY + SENSENOVA_MODEL
  3. EDITOR_AI_BASE_URL(或 OPENAI_BASE_URL) + EDITOR_AI_API_KEY(或 OPENAI_API_KEY)
     + EDITOR_AI_MODEL_ID(或 REVIEWER_MODEL_ID)
三者皆不全 → 明确报错退出（fail-closed，不产伪证据）。

用法：python tools/contest_dryrun/final_review_probe.py --ws <chain_dryrun工作区>
产出：FINAL_REVIEW.md / FINAL_REVIEW_VERDICT.json / final_review_session.json
（API 响应 id 留痕，供 REVIEW_EXECUTION_EVIDENCE 的 session_id/model 字段引用。）
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SUITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SUITE))
from engine.env_loader import apply_env  # noqa: E402

apply_env()
_argv = sys.argv[1:]
WS = Path(_argv[_argv.index("--ws") + 1]) if "--ws" in _argv else Path.cwd()


def resolve_endpoint():
    env = os.environ
    for base_k, key_k, model_ks in (
        ("ACAT_FINAL_BASE_URL", "ACAT_FINAL_API_KEY", ("ACAT_FINAL_MODEL",)),
        ("SENSENOVA_BASE_URL", "SENSENOVA_API_KEY", ("SENSENOVA_MODEL",)),
        ("EDITOR_AI_BASE_URL", "EDITOR_AI_API_KEY", ("EDITOR_AI_MODEL_ID", "REVIEWER_MODEL_ID")),
        ("OPENAI_BASE_URL", "OPENAI_API_KEY", ("EDITOR_AI_MODEL_ID", "REVIEWER_MODEL_ID")),
    ):
        base, key = env.get(base_k, ""), env.get(key_k, "")
        if not (base and key):
            continue
        for mk in model_ks:
            model = env.get(mk, "")
            if model:
                return base.rstrip("/"), key, model
    print("FATAL: 未配置终审模型端点——仓库不预设模型，比赛时配置 env"
          "（ACAT_FINAL_* 或 SENSENOVA_* 或 EDITOR_AI_*/OPENAI_* 三元组齐备其一）", file=sys.stderr)
    sys.exit(2)


def main():
    base, key, model = resolve_endpoint()
    res_file = WS / "figures" / "all_results.json"
    res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.is_file() else {}

    prompt = (
        "你是数模竞赛终审评委。对工作区产物做最终审查。这是一次【链路验证级】样例"
        "（非真实参赛论文），正文占位句式/重复段落不计致命；只判四类致命："
        "结果编造（正文数字与 figures/all_results.json 不符）、文献 DOI 编造、"
        "声称与实现脱钩（code/main.py 须真实求解）、PDF 缺失。"
        f"当前 all_results.json = {json.dumps(res, ensure_ascii=False)}。"
        "请给出简短终审意见（≤120字），然后严格按此格式结尾两行：\n"
        "FATAL_COUNT: <整数>\nVERDICT: <pass 或 fail>"
    )
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.3}).encode("utf-8")
    req = urllib.request.Request(f"{base}/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode("utf-8"))

    text = resp["choices"][0]["message"]["content"].strip()
    api_id = resp.get("id", "no-id")
    m_fatal = re.search(r"FATAL_COUNT:\s*(\d+)", text)
    m_verd = re.search(r"VERDICT:\s*(pass|fail)", text, re.I)
    fatal = int(m_fatal.group(1)) if m_fatal else 9
    verdict = m_verd.group(1).lower() if m_verd else "fail"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    (WS / "FINAL_REVIEW.md").write_text(
        "# 终审报告（由配置的模型真实执行）\n\n"
        f"- 执行模型: {model}（端点 env 配置，仓库不预设）\n"
        f"- API 会话: {api_id}\n- 时间: {now}\n- 判定: {verdict}\n\n## 模型原文\n\n{text}\n",
        encoding="utf-8")
    (WS / "FINAL_REVIEW_VERDICT.json").write_text(json.dumps({
        "findings": [f"终审由 {model} 真实执行（session {api_id}），判定见 FINAL_REVIEW.md 模型原文"],
        "fatal_count": fatal}, ensure_ascii=False), encoding="utf-8")
    (WS / "final_review_session.json").write_text(json.dumps({
        "session_id": api_id, "model": model, "at": now}, ensure_ascii=False), encoding="utf-8")
    print("FATAL:", fatal, "VERDICT:", verdict, "SESSION:", api_id, "MODEL:", model)


if __name__ == "__main__":
    main()
