"""真实命令与依赖计划执行；不组装提交证据、不决定步骤验收。"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from engine.execution_protocol import normalize_command_record
from engine.workflow_store import StepStatus
from .context import digest, snapshot

# 影响解释器行为的环境键：受控环境必须携带并进入缓存指纹。
_CACHE_ENV_KEYS = ("PYTHONPATH", "PYTHONHOME", "PYTHONUTF8", "PYTHONIOENCODING",
                   "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED", "PYTHONWARNINGS",
                   "LANG", "LC_ALL", "LC_CTYPE")
# 系统运行必需键白名单：受控环境据此构造，存在的才传入；未列出的变量对
# 可缓存子进程不可见。混列 Windows/Linux 键，按当前环境过滤即跨平台安全。
_BASE_ENV_KEYS = ("PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR",
                  "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES",
                  "COMMONPROGRAMFILES", "HOMEDRIVE", "HOMEPATH", "USERPROFILE",
                  "USERDOMAIN", "USERNAME", "ALLUSERSPROFILE", "OS",
                  "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "HOME")
# 网络与包管理命令存在仓外隐藏依赖，即使声明 pure 也不可缓存。
_NETWORK_TOOLS = {"curl", "wget", "ping", "ssh", "scp", "sftp", "ftp", "telnet",
                  "pip", "pip3", "npm", "yarn", "pnpm", "gem", "cargo",
                  "git", "svn", "gh", "rsync", "bower"}

class CommandExecutor:
    def __init__(self, context):
        self.context = context
        self.store = context.store
        self.action = context.action
        self.workspace = context.workspace

    def execute(self, spec: dict, *, force: bool = False) -> dict:
        """运行执行者已选择的命令；只有显式完整依赖+纯计算的命令才允许复用。

        产出归属唯一依据是"执行窗口+字节"：命令窗口内输出字节发生变化即归因
        于本命令（子进程真实写入或窗口内发生的变更），mtime/ctime 不参与归属
        ——Windows 上两者都可复原或天然不动，不作内容真值。窗口内字节未变的
        输出不是本命令产出，保留既有有效来源，无来源则拒绝认领。
        """
        self.context.require_active()
        argv = spec.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv):
            raise ValueError("argv 必须是非空字符串数组；不使用shell拼接")
        if any(re.search(r"(?i)(api[-_]?key|password|authorization|access[-_]?token|secret)\s*[=:]|^--(?:api[-_]?key|password|token|secret)$|\bsk-[A-Za-z0-9]{12,}|\bbearer\s+\S+|\bgh[pousr]_[A-Za-z0-9_]{12,}", a) for a in argv):
            raise ValueError("凭据不得出现在命令参数或持久证据中，请使用执行环境")
        executable = shutil.which(argv[0])
        if not executable:
            raise ValueError(f"执行程序不可用: {argv[0]}")
        argv = [str(Path(executable).resolve()), *argv[1:]]
        cwd_rel = self.context.relative(str(spec.get("cwd", ".")))
        cwd = self.workspace / cwd_rel
        outputs = [self.context.relative(v) for v in spec.get("outputs", [])]
        inputs = [self.context.relative(v) for v in spec.get("inputs", [])]
        # 路径型脚本/配置参数也进入依赖，避免只追数据、不追代码。
        for arg in argv[1:]:
            try:
                candidate = (cwd / arg).resolve()
                is_file = candidate.is_file()
            except (OSError, ValueError):
                continue
            if is_file and candidate.is_relative_to(self.workspace):
                rel = candidate.relative_to(self.workspace).as_posix()
                if rel not in inputs and rel not in outputs:
                    inputs.append(self.context.relative(rel))
        if self.action.skill_name == "comp-final-audit" and "AUDIT_REPORT.json" in outputs:
            raise ValueError("审计报告由finish生成；终审检查命令应输出其真实检查结果而非改写报告")
        mode = spec.get("mode", "produce")
        if mode not in {"produce", "check"}:
            raise ValueError("命令mode必须是produce或check")
        if not outputs and mode != "check":
            raise ValueError("产出命令需声明outputs；无产物的核查命令应明确mode=check")
        if mode == "check" and (outputs or not inputs or not spec.get("id")):
            raise ValueError("核查命令需具名id、明确inputs且outputs为空")
        if "." in inputs or "." in outputs:
            raise ValueError("不能把整个工作区含引擎状态作为输入或产物；声明具体任务路径")
        mutations = {self.context.relative(v) for v in spec.get("mutates", [])}
        if not mutations <= (set(inputs) & set(outputs)):
            raise ValueError("mutates必须同时出现在inputs与outputs中")
        overlaps = {(i, o) for i in inputs for o in outputs
                    if i == o or i.startswith(o.rstrip("/") + "/") or o.startswith(i.rstrip("/") + "/")}
        if any(i != o or i not in mutations for i, o in overlaps):
            raise ValueError("输入输出重叠须用mutates明确同路径修订；目录与子路径重叠须拆分")
        node = str(spec.get("id") or digest(sorted(outputs)))
        before = snapshot(self.workspace, inputs)
        output_versions = snapshot(self.workspace, [p for p in outputs if (self.workspace / p).exists()])
        inherited = self.context.trace_lineage({m: before[m] for m in mutations}) if mutations else {}
        stable_inputs = [i for i in inputs if i not in mutations]
        cacheable = (spec.get("pure") is True and spec.get("complete_inputs") is True
                     and bool(inputs) and not mutations and mode == "produce")
        # Windows 下可执行文件带 .exe/.cmd/.bat 等扩展名，先规范化再识别工具。
        executable_stem = Path(argv[0]).stem.lower()
        # 先确定最终复用资格：网络/包管理命令、独立评审/终审步骤、未声明受控
        # 环境键，任一不满足即不复用（评审/终审禁缓存规则保留）；资格定后再
        # 构造受控环境并选择执行环境，使 environment_mode、cacheable、cache_key
        # 与子进程实际参数一致：可复用→受控环境及其同源指纹；
        # 不复用→继承环境真实运行。
        if cacheable and (executable_stem in _NETWORK_TOOLS
                          or executable_stem.startswith(("pip", "npm", "yarn", "pnpm"))
                          or any("://" in a for a in argv[1:])):
            cacheable = False  # 网络/包管理命令有仓外隐藏依赖，成功不可缓存
        if cacheable and (self.action.requires_subagent or "review" in self.action.skill_name
                          or self.action.skill_name == "comp-final-audit"):
            cacheable = False
        declared_env_keys = [str(k) for k in spec.get("env_keys", [])]
        # 受控白名单环境本身就是完整的环境真值：子进程可见变量全部来自
        # controlled_env 并以 digest 入缓存键（指纹同源），因此未声明 env_keys
        # 的纯计算命令同样可复用；声明键只是向白名单追加任务所需变量。
        controlled_env = None
        if cacheable:
            controlled_keys = sorted(set(_BASE_ENV_KEYS) | set(_CACHE_ENV_KEYS) | set(declared_env_keys))
            controlled_env = {k: os.environ[k] for k in controlled_keys if k in os.environ}
        external_files = {}
        for arg in argv[1:]:
            try:
                candidate = (cwd / arg).resolve()
                if candidate.is_file() and not candidate.is_relative_to(self.workspace):
                    external_files[str(candidate)] = hashlib.sha256(candidate.read_bytes()).hexdigest()
            except (OSError, ValueError):
                continue
        from importlib.metadata import distributions
        packages = sorted((d.metadata.get("Name", ""), d.version) for d in distributions())
        # 安装环境清单用于复现，不等于本命令实际依赖；缓存键只含解析后的声明依赖。
        dependencies = {}
        installed = {name.lower().replace("_", "-"): version for name, version in packages}
        for name in spec.get("dependencies", {}):
            actual = installed.get(name.lower().replace("_", "-"))
            if actual is None:
                raise ValueError(f"声明依赖未安装，不能伪填版本: {name}")
            dependencies[name] = actual
        if Path(argv[0]).name.lower().startswith("python"):
            import sys
            dependencies["python"] = sys.version.split()[0]
        key_payload = {"workspace": str(self.workspace), "argv": argv, "cwd": cwd_rel,
                       "inputs": before, "outputs": outputs,
                       "contract": self.context.execution_relevant_contract(),
                       "executable_sha256": hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest(),
                       "environment": digest(controlled_env) if controlled_env is not None else "",
                       "dependencies": dependencies, "external_tools": external_files}
        cache_key = digest(key_payload) if cacheable else ""
        payload = {"node": node, "argv": argv, "cwd": cwd_rel, "inputs_snapshot": before,
                   "dependencies": dependencies, "environment_packages": dict(packages),
                   "backend": "recorded-command",
                   "environment_mode": ("program-controlled allowlist" if cacheable
                                        else "inherited; not reusable"),
                   # execution_config 仅是溯源元数据：不传给子进程、不影响命令行为、不入缓存键。
                   "execution_config": spec.get("config", {}),
                   "declared_outputs": outputs, "contract": self.context.contract(), "mode": mode,
                   "mutates": sorted(mutations), "cacheable": cacheable,
                   "outputs_before": output_versions, **inherited,
                   "dependency_boundary": "caller-declared; not an OS sandbox"}
        node_key = "check:" + node if mode == "check" else "command:" + digest(sorted(outputs))
        op = self.context.begin("command", node_key, payload, cache_key)
        start = time.perf_counter()
        producer_path = self.workspace / "STEP_MANIFEST.json"
        producer_before = producer_path.read_bytes() if producer_path.is_file() else None
        try:
            if cacheable and not force:
                for old in self.store.reusable_operations(cache_key):
                    prior = old["payload"]
                    produced_at = self.store.get_step(old["step_id"])
                    # 未接受步骤只能在同一个仍活跃attempt内复用；完成步骤可在同库内复用真实产物。
                    if not (produced_at.status == StepStatus.COMPLETED or
                            (old["step_id"] == self.action.step_id and old["attempt_id"] == self.action.attempt_id)):
                        continue
                    try:
                        if snapshot(self.workspace, outputs) != prior["outputs_snapshot"]:
                            continue
                    except (OSError, ValueError):
                        continue
                    # 传递依赖也要对账：上游已变化时，下游产物即使字节未动也是陈旧结果。
                    prior_lineage = {**prior.get("lineage_inputs", {}), **prior.get("inputs_snapshot", {})}
                    prior_mutations = set(prior.get("mutates", []))
                    stable_prior = {p: h for p, h in prior_lineage.items() if p not in prior_mutations}
                    try:
                        if snapshot(self.workspace, list(stable_prior)) != stable_prior:
                            continue
                    except (OSError, ValueError):
                        continue
                    if snapshot(self.workspace, inputs) != before:
                        raise ValueError("复用期间输入变化")
                    payload.update(command_record={**prior["command_record"], "reused_from": old["id"]},
                                   outputs_snapshot=prior["outputs_snapshot"], reused_from=old["id"],
                                   lineage_inputs=dict(prior.get("lineage_inputs", {})),
                                   retained_from=prior.get("retained_from"),
                                   producer_manifest=prior.get("producer_manifest"),
                                   duration_seconds=time.perf_counter() - start)
                    return self.context.finish(op, "reused", payload)
            completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=float(spec.get("timeout", 600)),
                check=False, env=controlled_env)
            record = normalize_command_record({"command": argv, "returncode": completed.returncode,
                                               "cwd": cwd_rel}, self.workspace)
            payload.update(command_record=record, duration_seconds=time.perf_counter() - start,
                           stdout_sha256=hashlib.sha256(completed.stdout.encode()).hexdigest(),
                           stderr_sha256=hashlib.sha256(completed.stderr.encode()).hexdigest())
            if completed.returncode != 0:
                failed = self.context.finish(op, "failed", {**payload, "error": "command_failed"})
                failed.update(stdout=completed.stdout[-12000:], stderr=completed.stderr[-4000:])
                return failed
            if snapshot(self.workspace, stable_inputs) != {p: h for p, h in before.items() if p not in mutations}:
                return self.context.finish(op, "failed", {**payload, "error": "inputs_changed_during_execution"})
            payload["outputs_snapshot"] = snapshot(self.workspace, outputs)
            # 窗口内字节未变的输出不是本命令产出：保留既有有效来源；无来源则拒绝。
            # 字节变化的输出归因于本命令（执行窗口+字节），stat 是否变化不影响归属。
            untouched = [p for p in outputs if output_versions.get(p) == payload["outputs_snapshot"].get(p)]
            if untouched:
                retained = self.context.trace_lineage({p: payload["outputs_snapshot"][p] for p in untouched})
                if set(retained["source_operations"]) != set(untouched):
                    raise ValueError("命令未产生声明输出，且没有可追溯的既有生产者；不能用成功空命令接收旧文件")
                payload["retained_from"] = retained["source_operations"]
                payload["lineage_inputs"] = {**payload.get("lineage_inputs", {}), **retained["lineage_inputs"]}
            producer_after = producer_path.read_bytes() if producer_path.is_file() else None
            if producer_after is not None and producer_after != producer_before:
                import json
                from engine.step_manifest import atomic_write_json, validate_manifest
                producer = json.loads(producer_after)
                verdict = validate_manifest(self.workspace, manifest_data=producer)
                if not verdict["ok"]:
                    raise ValueError("工具生成的原始执行清单无效: " + "; ".join(verdict["errors"]))
                saved = self.workspace / ".engine/producer-manifests" / f"{op}.json"
                atomic_write_json(saved, producer)
                payload["producer_manifest"] = saved.relative_to(self.workspace).as_posix()
            result = self.context.finish(op, "succeeded", payload)
            # 控制台结果供解题使用；不把输出正文写入日志/数据库。
            result["stdout"] = completed.stdout[-12000:]
            result["stderr"] = completed.stderr[-4000:]
            return result
        except Exception as exc:
            self.context.finish(op, "failed", {**payload, "error": type(exc).__name__,
                                       "duration_seconds": time.perf_counter() - start})
            raise


    def run_plan(self, plan: dict, *, force: bool = False) -> dict:
        nodes = plan.get("nodes", [])
        if not nodes or any(not isinstance(n, dict) or not n.get("id") for n in nodes):
            raise ValueError("plan.nodes必须包含具名的实际命令")
        pending = {str(n["id"]): n for n in nodes}
        if len(pending) != len(nodes):
            raise ValueError("重复节点标识")
        producers = {}
        for node in nodes:
            for output in node.get("outputs", []):
                relative = self.context.relative(output)
                if any(relative == p or relative.startswith(p.rstrip("/") + "/")
                       or p.startswith(relative.rstrip("/") + "/") for p in producers):
                    raise ValueError(f"产物多重写入者: {relative}")
                producers[relative] = str(node["id"])
        dependencies = {name: set(node.get("depends_on", [])) | {
            owner for output, owner in producers.items() for inp in node.get("inputs", [])
            if (self.context.relative(inp) == output or self.context.relative(inp).startswith(output + "/")
                or output.startswith(self.context.relative(inp).rstrip("/") + "/")) and owner != name}
            for name, node in pending.items()}
        if any(not deps <= set(pending) for deps in dependencies.values()):
            raise ValueError("依赖引用未知节点")
        ordered, done = [], set()
        while len(ordered) < len(nodes):
            ready = [name for name in pending if name not in done and dependencies[name] <= done]
            if not ready:
                raise ValueError("执行计划包含循环依赖")
            ordered.extend(ready)
            done.update(ready)
        results = []
        for name in ordered:
            spec = dict(pending[name])
            # 显式依赖同样进入内容键，不只是排序提示，避免未列出父产物导致假命中。
            spec["inputs"] = list(dict.fromkeys([*spec.get("inputs", []),
                *(output for dependency in dependencies[name] for output in pending[dependency].get("outputs", []))]))
            result = self.execute(spec, force=force)
            results.append(result)
            if result["status"] == "failed":
                return {"status": "needs_work", "operations": results, "failed_node": name}
        return {"status": "executed", "operations": results,
                "executed": sum(r["status"] == "succeeded" for r in results),
                "reused": sum(r["status"] == "reused" for r in results)}
