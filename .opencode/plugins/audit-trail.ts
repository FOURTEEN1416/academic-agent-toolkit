// .opencode/plugins/audit-trail.ts
// 数模全流程套件 — 操作审计插件（拦截式，无法绕过）
//
// 设计来源：复用 OpenCode 官方生态成熟方案
//   - opencode-logger（radekBednarik/opencode-logger，MIT）：互斥锁串行写 + 日志轮转 + scope 过滤
//   - opencode-primer/audit-log.js（wesammustafa）：tool.execute.after 记录工具调用
// 本插件在其基础上增强"参数级审计"（bash 命令全文/编辑路径/skill 名/task 描述），
// 与 opencode-logger 的"全事件流"互补。两者共同写入 <共享根>/.engine/audit/。
//
// 审计文件：
//   - operations.jsonl         本插件（参数级：tool_call/tool_result/file_edit/session/permission）
//   - log.jsonl                官方 opencode-logger（全事件流，含轮转）
//
// 这是"拦截式审计"：无论 agent 是否调用 runner.complete_step，只要发生工具调用
// 就会被记录。引擎层 evidence 是"申报式"，本插件补足"实际执行"侧。
//
// 读取与报告：python -m engine.workflow_cli audit --workspace <ws>
//             或 from engine.audit_store import generate_audit_report

import {
  appendFileSync, mkdirSync, renameSync, statSync, readdirSync, unlinkSync,
} from "node:fs";
import { join, basename, extname, isAbsolute, resolve } from "node:path";

// ---------- 配置（与 opencode-logger 兼容的环境变量） ----------
const ENV = process.env;
const DEFAULT_LOG_DIR = ".engine/audit";           // 相对共享根
const DEFAULT_FILENAME = "operations.jsonl";
const DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024;   // 100MB 轮转
const DEFAULT_MAX_FILES = 5;                        // 保留 5 份轮转

export const AuditTrail = async ({ directory }) => {
  // 审计根目录：共享项目根（directory 即 opencode.json 所在目录）
  const projectRoot = directory;
  const logDirRaw = ENV.OPENCODE_AUDIT_DIR || DEFAULT_LOG_DIR;
  const logDir = isAbsolute(logDirRaw) ? logDirRaw : resolve(projectRoot, logDirRaw);
  const logPath = join(logDir, ENV.OPENCODE_AUDIT_FILENAME || DEFAULT_FILENAME);
  const maxFileSize = parseInt(ENV.OPENCODE_AUDIT_MAX_FILE_SIZE || "", 10) || DEFAULT_MAX_FILE_SIZE;
  const maxFiles = parseInt(ENV.OPENCODE_AUDIT_MAX_FILES || "", 10) || DEFAULT_MAX_FILES;

  // 互斥锁：所有写操作串行化（复用 opencode-logger 已验证的 mutex 模式）
  let lock = Promise.resolve();

  const rotate = () => {
    try {
      const ext = extname(logPath);
      const base = basename(logPath, ext);
      const ts = new Date().toISOString().replace(/:/g, "-").replace(/\..+$/, "");
      const shortId = Math.random().toString(16).slice(2, 10);
      renameSync(logPath, join(logDir, `${base}.${ts}-${shortId}${ext}`));
      if (maxFiles > 0) {
        const pattern = new RegExp(`^${base.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\..+${ext.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
        const rotated = readdirSync(logDir).filter((n) => pattern.test(n)).sort();
        const excess = rotated.length - maxFiles;
        if (excess > 0) rotated.slice(0, excess).forEach((n) => { try { unlinkSync(join(logDir, n)); } catch { /* best effort */ } });
      }
    } catch { /* 轮转失败不阻断 */ }
  };

  const record = (entry) => {
    // 写入操作串行化，避免并发交错
    lock = lock.then(() => {
      try {
        mkdirSync(logDir, { recursive: true });
        if (maxFileSize > 0) {
          try { if (statSync(logPath).size >= maxFileSize) rotate(); } catch { /* 文件不存在则直接写 */ }
        }
        const line = JSON.stringify({ ts: new Date().toISOString(), ...entry });
        appendFileSync(logPath, line + "\n", "utf8");
      } catch (e) {
        /* 审计失败绝不阻断工具执行 */
      }
    }).catch(() => {});
    return lock;
  };

  // 截断过长参数，避免日志膨胀
  const clip = (v, n = 500) => {
    if (v === undefined || v === null) return "";
    const s = typeof v === "string" ? v : JSON.stringify(v);
    return s.length > n ? s.slice(0, n) + "...[TRUNC]" : s;
  };

  // 从工具参数中提取可审计要点（不记录敏感值全文）
  const extract = (tool, args = {}) => {
    switch (tool) {
      case "bash":
        return { command: clip(args.command) };
      case "edit":
        return {
          filePath: args.filePath,
          oldLen: (args.oldString || "").length,
          newLen: (args.newString || "").length,
        };
      case "write":
        return { filePath: args.filePath, contentLen: (args.content || "").length };
      case "read":
        return { filePath: args.filePath, offset: args.offset, limit: args.limit };
      case "glob":
        return { pattern: args.pattern };
      case "grep":
        return { pattern: clip(args.pattern), path: args.path, include: args.include };
      case "skill":
        return { skillName: args.name };
      case "task":
        return { subagentType: args.subagent_type, description: clip(args.description, 300) };
      case "webfetch":
        return { url: args.url, format: args.format };
      case "todowrite":
        return { todos: clip(args.todos, 400) };
      case "firecrawl_firecrawl_search":
      case "firecrawl_firecrawl_scrape":
        return { query: clip(args.query || args.url, 300) };
      default:
        try {
          return { argKeys: Object.keys(args).slice(0, 20), argLen: JSON.stringify(args).length };
        } catch (e) {
          return {};
        }
    }
  };

  return {
    // 工具调用前（可拿到 tool 名与参数）— 记录调用参数
    "tool.execute.before": async (input, output) => {
      const tool = input?.tool || output?.tool || "unknown";
      const sessionID = input?.sessionID || output?.sessionID || "";
      const args = output?.args || input?.input || {};
      await record({ type: "tool_call", event: "before", tool, sessionID, detail: extract(tool, args) });
    },

    // 工具调用后（可拿到结果/错误）— 记录执行结果
    "tool.execute.after": async (input) => {
      const tool = input?.tool || "unknown";
      const sessionID = input?.sessionID || "";
      const ok = !input?.error;
      let resultSummary = "";
      try {
        if (input?.output !== undefined && input?.output !== null) {
          resultSummary = clip(typeof input.output === "string" ? input.output : JSON.stringify(input.output), 300);
        }
      } catch (e) { /* ignore */ }
      await record({
        type: "tool_result", event: "after", tool, sessionID,
        ok, error: clip(input?.error?.message || input?.error || "", 200),
        resultSummary,
      });
    },

    // 平台事件（文件编辑/会话/权限请求）
    event: async ({ event }) => {
      if (!event) return;
      if (event.type === "file.edited" || event.type === "file.watcher.updated") {
        await record({ type: "file_edit", event: event.type, detail: clip(event, 400) });
      } else if (event.type === "session.created") {
        await record({ type: "session", event: event.type, sessionID: event.sessionID || "" });
      } else if (event.type === "session.idle") {
        await record({ type: "session", event: event.type, sessionID: event.sessionID || "" });
      } else if (event.type === "permission.asked") {
        await record({ type: "permission", event: event.type, detail: clip(event, 300) });
      }
    },
  };
}

export default AuditTrail
