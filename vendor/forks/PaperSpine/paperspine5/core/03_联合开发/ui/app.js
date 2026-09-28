const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

let snapshot = null;
let currentView = "configuration";
let hasChosenView = false;

const STAGE_LABELS = {
  initialized: "任务已初始化",
  awaiting_candidates: "正在生成图件",
  awaiting_review: "等待整图确认",
  figures_confirmed: "图件已确认",
  awaiting_paper_integration: "等待正文与像素回证",
  canonical_paper_ready: "规范主稿已完成",
  target_profile_ready: "目标配置已核验",
  rebuttal_validated: "返修轮次已核验",
  rebuttal_materials_ready: "返修材料已就绪",
  destination_rebuild_ready: "转投重建计划已就绪",
  awaiting_external_authorization: "目标投稿包已就绪 · 等待授权",
  complete: "旧版完成状态",
  blocked: "工作流已阻塞"
};

const VIEW_META = {
  configuration: { name: "工作配置", kicker: "STAGE 01", title: "配置说明" },
  anchoring: { name: "论文定锚", kicker: "STAGE 02", title: "确认依据" },
  figures: { name: "科研图件", kicker: "STAGE 03", title: "图件审阅" },
  deliverables: { name: "规范主稿", kicker: "STAGE 04", title: "主稿证据" },
  publication: { name: "投稿循环", kicker: "STAGE 05", title: "本地投稿操作" }
};

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = text;
  return element;
}

function stageLabel(stage) {
  return STAGE_LABELS[stage] || stage || "未知阶段";
}

function setView(view, { user = false } = {}) {
  if (!VIEW_META[view]) return;
  currentView = view;
  if (user) hasChosenView = true;
  $(".app-shell").dataset.view = view;
  $$(".workspace-view").forEach((panel) => {
    const active = panel.dataset.view === view;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });
  $$(".inspector-view").forEach((panel) => {
    const active = panel.dataset.inspector === view;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });
  $$(".workflow-step").forEach((step) => {
    step.classList.toggle("active", step.dataset.viewTarget === view);
  });
  const meta = VIEW_META[view];
  $("#view-name").textContent = meta.name;
  $("#inspector-kicker").textContent = meta.kicker;
  $("#inspector-title").textContent = meta.title;
  $("#rich-review").classList.toggle("hidden", view !== "figures" || !snapshot?.review?.figures?.length);
}

function phaseForSnapshot(data) {
  const stage = data?.state?.stage;
  if (["canonical_paper_ready", "target_profile_ready", "rebuttal_validated", "rebuttal_materials_ready", "destination_rebuild_ready", "awaiting_external_authorization"].includes(stage)) return "publication";
  if (["awaiting_paper_integration", "complete"].includes(stage)) return "deliverables";
  if (["awaiting_candidates", "awaiting_review", "figures_confirmed"].includes(stage)) return "figures";
  if (data?.paper?.contribution || data?.paper?.motivation || data?.configuration?.exists) return "anchoring";
  return "configuration";
}

function renderWorkflow(data) {
  const stage = data?.state?.stage || "unknown";
  const done = {
    configuration: Boolean(data?.configuration?.exists),
    anchoring: Boolean(data?.paper?.contribution && data?.paper?.motivation),
    figures: ["figures_confirmed", "awaiting_paper_integration", "canonical_paper_ready", "target_profile_ready", "rebuttal_validated", "rebuttal_materials_ready", "destination_rebuild_ready", "awaiting_external_authorization", "complete"].includes(stage),
    deliverables: Boolean(data?.deliverables?.canonical_ready),
    publication: Boolean(data?.publication_cycle?.latest?.result?.ok)
  };
  $$(".workflow-step").forEach((step) => {
    const key = step.dataset.viewTarget;
    step.classList.toggle("done", done[key]);
    step.classList.toggle("blocked", stage === "blocked" && key === phaseForSnapshot(data));
  });
}

function splitLines(value) {
  return String(value || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function setFormValue(name, value) {
  const field = $(`[name="${name}"]`, $("#config-form"));
  if (!field || value === undefined || value === null) return;
  field.value = Array.isArray(value) ? value.join("\n") : String(value);
}

function configurationFromForm() {
  const form = $("#config-form");
  const data = new FormData(form);
  return {
    workflow: data.get("workflow"),
    scene: data.get("scene"),
    tier: data.get("tier"),
    output_language: data.get("output_language"),
    target_name: String(data.get("target_name") || "").trim(),
    materials_dir: String(data.get("materials_dir") || "").trim(),
    draft_path: String(data.get("draft_path") || "").trim(),
    user_motivation: String(data.get("user_motivation") || "").trim(),
    official_urls: splitLines(data.get("official_urls")),
    reference_mode: data.get("reference_mode"),
    reference_paths: splitLines(data.get("reference_paths")),
    citation_target_count: Number(data.get("citation_target_count") || 20),
    special_requirements: splitLines(data.get("special_requirements")),
    word_output: data.get("word_output"),
    translation_package: data.get("translation_package"),
    humanize_tier: data.get("humanize_tier"),
    detection_platform: data.get("detection_platform"),
    ui_language: data.get("ui_language") || "zh"
  };
}

function renderConfiguration(data) {
  const configuration = data.configuration || {};
  const values = configuration.values || {};
  Object.entries(values).forEach(([name, value]) => setFormValue(name, value));
  $("#config-status").textContent = configuration.exists ? "配置已保存" : "尚未保存";
  $("#config-path").textContent = configuration.config_file || "等待任务服务连接后显示保存位置。";
  $("#entry-command").textContent = configuration.entry_command || "/paperspine";
  $("#save-config").disabled = !data.state || data.state.stage !== "initialized";
}

function renderAnchoring(data) {
  const contribution = data.paper?.contribution;
  const motivation = data.paper?.motivation;
  $("#contribution").textContent = contribution || "尚未确认核心贡献。";
  $("#motivation").textContent = motivation || "尚未确认研究动机。";
  $("#contribution-main").textContent = contribution || "等待 PaperSpine 生成贡献候选。";
  $("#motivation-main").textContent = motivation || "等待 PaperSpine 生成与贡献对齐的动机候选。";
  $("#contribution-main").classList.toggle("muted", !contribution);
  $("#motivation-main").classList.toggle("muted", !motivation);
  $("#contribution-state").textContent = contribution ? "已确认" : "待确认";
  $("#motivation-state").textContent = motivation ? "已确认" : "待确认";
  $("#contribution-main").closest(".anchor-document").classList.toggle("confirmed", Boolean(contribution));
  $("#motivation-main").closest(".anchor-document").classList.toggle("confirmed", Boolean(motivation));
  $("#anchor-status").textContent = contribution && motivation ? "双锚点已确认" : "等待定锚";
  $("#host-next").textContent = JSON.stringify(data.host_next || {}, null, 2);
}

function assetUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return new URL("/figmirror/review/" + path, window.location.origin).href;
}

function candidatePreview(candidate) {
  return candidate.full_preview
    || candidate.vector_preview
    || (candidate.review_views && candidate.review_views[0] && candidate.review_views[0].path)
    || (candidate.panels && candidate.panels[0] && candidate.panels[0].preview)
    || "";
}

function candidateTitle(id, candidate) {
  return "方案 " + id + " · " + (candidate.title || candidate.layout || "完整候选图");
}

function candidateFacts(candidate) {
  const facts = [];
  if (candidate.panel_count !== undefined && candidate.panel_count !== null) facts.push(String(candidate.panel_count) + " 个面板");
  if (candidate.layout) facts.push(String(candidate.layout));
  if (candidate.reference_similarity !== undefined && candidate.reference_similarity !== null) facts.push("参考相似度 " + String(candidate.reference_similarity));
  const scientificStatus = candidate.verification && candidate.verification.scientific_status;
  if (scientificStatus) facts.push("科学门禁 " + String(scientificStatus));
  return facts.join(" · ") || "完整候选";
}

function setImageSource(image, source, alt) {
  image.classList.remove("asset-error");
  image.alt = alt;
  image.src = source;
  image.onerror = () => {
    image.classList.add("asset-error");
    image.alt = alt + "（预览暂不可用，请打开 FigMirror 深度审阅）";
  };
}

function buildCandidateOption(figure, id, candidate) {
  const label = createElement("label", "candidate-option");
  const input = createElement("input");
  input.type = "radio";
  input.name = figure.figure_id;
  input.value = id;
  input.dataset.preview = assetUrl(candidatePreview(candidate));
  input.dataset.title = candidateTitle(id, candidate);
  input.dataset.facts = candidateFacts(candidate);
  input.dataset.note = candidate.note || "";
  input.dataset.figureLabel = figure.figure_id;
  const key = createElement("span", "candidate-key", id);
  const copy = createElement("span", "candidate-copy");
  copy.append(
    createElement("strong", "", candidate.title || candidate.layout || "完整候选图"),
    createElement("span", "", candidateFacts(candidate))
  );
  label.append(input, key, copy);
  return label;
}

function buildFigure(figure, index) {
  const block = createElement("section", "figure-block");
  block.dataset.figureId = figure.figure_id;
  const heading = createElement("header", "figure-heading");
  const number = createElement("span", "figure-number", String(index + 1).padStart(2, "0"));
  const headingCopy = createElement("div");
  headingCopy.append(
    createElement("h2", "", figure.figure_id || "未命名图件"),
    createElement("p", "", "选择一个完整候选；局部面板不会跨方案混用。")
  );
  const kind = createElement("span", "figure-kind", figure.figure_kind || figure.kind || "科研图");
  heading.append(number, headingCopy, kind);
  const claim = createElement("p", "figure-claim", figure.claim || "该图件的论证主张尚未提供。");
  const entries = Object.entries(figure.candidates || {});
  block.append(heading, claim);
  if (!entries.length) {
    const empty = createElement("div", "empty-state");
    empty.append(createElement("strong", "", "候选图尚未全部定稿"), createElement("p", "", "请按 generation_plan.json 完成 Agent 原生绘图，再推进工作流。"));
    block.append(empty);
    return block;
  }
  const [firstId, firstCandidate] = entries[0];
  const frame = createElement("div", "preview-frame");
  const stage = createElement("div", "preview-stage");
  const image = createElement("img", "figure-preview");
  setImageSource(image, assetUrl(candidatePreview(firstCandidate)), figure.figure_id + " 方案 " + firstId);
  stage.append(image);
  const caption = createElement("div", "preview-caption");
  caption.append(
    createElement("strong", "preview-title", "预览 · " + candidateTitle(firstId, firstCandidate)),
    createElement("span", "preview-facts", candidateFacts(firstCandidate))
  );
  frame.append(stage, caption);
  const options = createElement("div", "candidate-options");
  entries.forEach(([id, candidate]) => options.append(buildCandidateOption(figure, id, candidate)));
  block.append(frame, options);
  return block;
}

function selectedInputFor(figureId) {
  return $$("#figures input[type='radio']").find((input) => input.name === figureId && input.checked);
}

function renderSelectionSummary() {
  const figures = snapshot?.review?.figures || [];
  const summary = $("#selection-summary");
  summary.replaceChildren();
  let selectedCount = 0;
  if (!figures.length) {
    summary.append(createElement("p", "muted", "候选图载入后可逐张选择。"));
    $("#selection-progress").textContent = "0 / 0";
    $("#confirm").disabled = true;
    $("#confirm").textContent = "先完成全部整图选择";
    return;
  }
  figures.forEach((figure) => {
    const selected = selectedInputFor(figure.figure_id);
    if (selected) selectedCount += 1;
    const row = createElement("div", "selection-row" + (selected ? " selected" : ""));
    row.append(createElement("strong", "", figure.figure_id), createElement("span", "", selected ? "方案 " + selected.value : "未选择"));
    summary.append(row);
  });
  $("#selection-progress").textContent = selectedCount + " / " + figures.length;
  const ready = selectedCount === figures.length;
  $("#confirm").disabled = !ready;
  $("#confirm").textContent = ready ? "确认 " + selectedCount + " 张整图并装配" : "还需选择 " + (figures.length - selectedCount) + " 张整图";
}

function showCandidateDetail(input) {
  const detail = $("#candidate-detail");
  detail.classList.remove("muted");
  detail.replaceChildren(
    createElement("strong", "", input.dataset.figureLabel + " · " + input.dataset.title),
    createElement("span", "", input.dataset.facts),
    createElement("span", "", input.dataset.note || "完整候选已载入，可进入 FigMirror 查看更深审阅证据。")
  );
}

function updatePreview(input) {
  const block = input.closest(".figure-block");
  if (!block) return;
  const image = $(".figure-preview", block);
  const title = $(".preview-title", block);
  const facts = $(".preview-facts", block);
  if (image && input.dataset.preview) setImageSource(image, input.dataset.preview, input.dataset.figureLabel + " 方案 " + input.value);
  if (title) title.textContent = input.dataset.title;
  if (facts) facts.textContent = input.dataset.facts;
  showCandidateDetail(input);
  renderSelectionSummary();
  $("#message").textContent = "";
}

function renderFigures(data) {
  const state = data.state || {};
  const figures = data.review?.figures || [];
  $("#next").textContent = state.next_action || "等待工作流给出下一步操作。";
  $("#review-eyebrow").textContent = "03 · FIGURE WORKSPACE · " + String(figures.length).padStart(2, "0");
  $("#review-mode").textContent = figures.length ? "完整候选 · 每图单选" : "等待候选";
  $("#candidate-detail").className = "candidate-detail muted";
  $("#candidate-detail").textContent = "选择候选后显示布局与面板信息。";
  const root = $("#figures");
  root.replaceChildren();
  if (!figures.length) {
    const empty = createElement("div", "empty-state");
    empty.append(
      createElement("strong", "", state.stage === "initialized" ? "先完成论文定锚" : "候选图尚未进入人工审阅"),
      createElement("p", "", state.stage === "initialized" ? "配置、核心贡献与研究动机确认后，PaperSpine 才会发出图件请求。" : "完成 generation_plan.json 中的候选定稿并推进工作流后，这里会显示完整 A/B/C 方案。")
    );
    root.append(empty);
  } else {
    figures.forEach((figure, index) => root.append(buildFigure(figure, index)));
    $("#rich-review").href = "/figmirror/review/index.html";
  }
  renderSelectionSummary();
}

function formatBytes(size) {
  if (size < 1024) return size + " B";
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + " KB";
  return (size / 1024 / 1024).toFixed(1) + " MB";
}

function renderDeliverables(data) {
  const deliverables = data.deliverables || {};
  const files = deliverables.files || [];
  const canonicalReady = Boolean(deliverables.canonical_ready);
  const bundleReady = Boolean(deliverables.bundle_ready);
  const assetsReady = ["awaiting_paper_integration", "canonical_paper_ready", "target_profile_ready", "rebuttal_validated", "rebuttal_materials_ready", "destination_rebuild_ready", "awaiting_external_authorization", "complete"].includes(data.state?.stage);
  $("#deliverable-status").textContent = bundleReady ? "目标投稿包已就绪" : (canonicalReady ? "规范主稿已完成" : (assetsReady ? "等待正文与最终像素审计" : "尚未完成"));
  $("#package-hero").classList.toggle("pending", !canonicalReady);
  $("#package-path").textContent = deliverables.directory || "等待装配完成后显示交付目录。";
  $("#deliverable-path").textContent = deliverables.directory || "尚未生成。";
  $("#file-count").textContent = files.length + " 个文件";
  const root = $("#deliverable-files");
  root.replaceChildren();
  if (!files.length) {
    root.append(createElement("p", "muted", "工作流完成后自动读取，不展示虚构文件。"));
  } else {
    files.forEach((file) => {
      const row = createElement("div", "file-row");
      row.append(createElement("strong", "", file.path), createElement("span", "", formatBytes(file.size)));
      root.append(row);
    });
  }
  const evidence = [];
  if (deliverables.manifest) evidence.push("装配清单：" + deliverables.manifest);
  if (deliverables.report) evidence.push("装配报告：" + deliverables.report);
  if (!canonicalReady && deliverables.paper_next_stage) evidence.push("PaperSpine 下一关：" + deliverables.paper_next_stage);
  if (!canonicalReady && deliverables.paper_next_action) evidence.push("下一步：" + deliverables.paper_next_action);
  $("#assembly-evidence").textContent = evidence.join("\n") || "工作流完成后显示装配清单与报告。";
  $("#assembly-evidence").classList.toggle("muted", !evidence.length);
}

const PUBLICATION_INPUTS = {
  profile_check: ["profile"],
  assemble: ["profile", "plan"],
  rebuttal_check: ["review_round"],
  rebuttal_render: ["review_round"],
  transfer_plan: ["origin_profile", "destination_profile", "transfer_request"]
};

function publicationRequest(operation) {
  const form = $("#publication-form");
  const formData = new FormData(form);
  const inputs = {};
  (PUBLICATION_INPUTS[operation] || []).forEach((name) => {
    const value = String(formData.get(name) || "").trim();
    if (value) inputs[name] = value;
  });
  const outputDirectory = String(formData.get("output_directory") || "").trim();
  return {
    operation,
    inputs,
    outputs: outputDirectory ? { directory: outputDirectory } : {},
    options: { write_report: true }
  };
}

function renderPublication(data) {
  const publication = data.publication_cycle || {};
  const latest = publication.latest;
  const result = latest?.result;
  const allowed = new Set(publication.allowed_operations || []);
  $("#publication-status").textContent = result?.signals?.submission_bundle_ready
    ? "本地投稿包已就绪"
    : result?.ok
      ? stageLabel(data.state?.stage)
      : publication.canonical_paper_ready
        ? "可执行本地操作"
        : "等待规范主稿";
  $("#publication-stage").textContent = data.state?.stage || "unknown";
  $("#publication-latest").textContent = latest
    ? (latest.operation + " · " + (result?.outcome || "UNKNOWN"))
    : "尚未执行";
  $("#publication-result").textContent = result
    ? JSON.stringify(result, null, 2)
    : "规范主稿完成后可运行五个本地操作。";
  const signals = result?.signals;
  $("#publication-signals").textContent = signals
    ? JSON.stringify(signals, null, 2)
    : "尚无 Publication Cycle 回执。";
  $("#publication-signals").classList.toggle("muted", !signals);
  $("#publication-authority").textContent = publication.authority_note || "external_action_authorized = false";
  $$('[data-publication-operation]').forEach((button) => {
    button.disabled = !allowed.has(button.dataset.publicationOperation);
  });
}

function renderAdvance(data) {
  const stage = data.state?.stage;
  const button = $("#advance");
  const settings = {
    initialized: ["校验定锚并进入图像", false],
    awaiting_candidates: ["检查候选定稿", false],
    awaiting_review: ["等待用户确认整图", true],
    figures_confirmed: ["装配交付成果", false],
    awaiting_paper_integration: ["检查正文与最终审计", false],
    canonical_paper_ready: ["请使用投稿循环操作", true],
    target_profile_ready: ["请继续准备或装配目标包", true],
    rebuttal_validated: ["请生成返修材料", true],
    rebuttal_materials_ready: ["返修材料已就绪", true],
    destination_rebuild_ready: ["请按转投计划重建主稿", true],
    awaiting_external_authorization: ["本地投稿包已就绪", true],
    complete: ["旧版状态待迁移", true],
    blocked: ["修复后恢复工作流", false]
  }[stage] || ["推进工作流", true];
  button.textContent = settings[0];
  button.disabled = settings[1];
}

function render(data, { autoNavigate = false } = {}) {
  snapshot = data;
  const state = data.state || {};
  const configValues = data.configuration?.values || {};
  const requests = data.paper?.requests || {};
  const paperId = requests.paper_id || configValues.target_name || data.job?.job_id || "当前论文";
  $(".app-shell").dataset.stage = state.stage || "unknown";
  $("#stage").textContent = data.deliverables?.bundle_ready ? "目标投稿包已就绪 · 等待授权" : stageLabel(state.stage);
  $("#stage-code").textContent = "stage: " + (state.stage || "unknown");
  $("#paper-id").textContent = paperId;
  $("#project-name").textContent = paperId;
  renderConfiguration(data);
  renderAnchoring(data);
  renderFigures(data);
  renderDeliverables(data);
  renderPublication(data);
  renderWorkflow(data);
  renderAdvance(data);
  if (!hasChosenView || autoNavigate) setView(phaseForSnapshot(data));
  else setView(currentView);
}

async function readJsonResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) throw new Error(fallbackMessage);
  const data = await response.json();
  if (!response.ok || data.status === "FAIL") throw new Error(data.error || fallbackMessage);
  return data;
}

async function request(path, body = {}) {
  $("#message").textContent = "正在处理…";
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  await readJsonResponse(response, "工作流请求失败。");
  await load({ autoNavigate: true });
  $("#message").textContent = "已更新。";
}

async function load(options = {}) {
  const response = await fetch("/api/snapshot", { cache: "no-store" });
  const data = await readJsonResponse(response, "当前地址未连接任务后端。");
  render(data, options);
}

function renderConnectionError() {
  snapshot = null;
  $(".app-shell").dataset.stage = "disconnected";
  $("#stage").textContent = "未连接任务";
  $("#stage-code").textContent = "stage: disconnected";
  $("#paper-id").textContent = "新论文任务";
  $("#project-name").textContent = "尚未命名的任务";
  $("#advance").textContent = "等待任务连接";
  $("#advance").disabled = true;
  $("#save-config").disabled = true;
  $("#confirm").disabled = true;
  $$('[data-publication-operation]').forEach((button) => { button.disabled = true; });
  $("#host-next").textContent = "等待任务服务连接后显示 AI 下一步。";
  $("#config-path").textContent = "通过 paperspine_figure.py serve 启动任务后，可把配置保存到 PaperSpine 输出目录。";
  $("#review-mode").textContent = "等待任务";
  $("#figures").replaceChildren(
    (() => {
      const state = createElement("div", "connection-state");
      state.append(
        createElement("strong", "", "科研图件工作区尚未连接"),
        createElement("p", "", "配置与论文定锚完成后，真实候选整图会在这里载入。")
      );
      return state;
    })()
  );
  renderSelectionSummary();
  $("#message").textContent = "当前为静态前端预览；未执行任何配置或论文写入。";
  $$(".workflow-step").forEach((step) => step.classList.remove("done", "blocked"));
  setView("configuration");
}

$$(".workflow-step").forEach((step) => {
  step.addEventListener("click", () => setView(step.dataset.viewTarget, { user: true }));
});

$("#config-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!event.currentTarget.reportValidity()) return;
  request("/api/configuration", { configuration: configurationFromForm() }).catch((error) => {
    $("#message").textContent = error.message;
  });
});

$("#copy-command").addEventListener("click", async () => {
  const command = $("#entry-command").textContent;
  try {
    await navigator.clipboard.writeText(command);
    $("#message").textContent = "已复制 PaperSpine 入口命令。";
  } catch {
    $("#message").textContent = "复制权限不可用，请手动复制：" + command;
  }
});

$("#advance").addEventListener("click", () => {
  request("/api/advance").catch((error) => {
    $("#message").textContent = error.message;
  });
});

$("#figures").addEventListener("change", (event) => {
  if (event.target.matches("input[type='radio']")) updatePreview(event.target);
});

$("#confirm").addEventListener("click", () => {
  if (!snapshot?.review) return;
  const selections = {};
  (snapshot.review.figures || []).forEach((figure) => {
    const selected = selectedInputFor(figure.figure_id);
    selections[figure.figure_id] = selected && selected.value;
  });
  request("/api/decision", { selections }).catch((error) => {
    $("#message").textContent = error.message;
  });
});

$$('[data-publication-operation]').forEach((button) => {
  button.addEventListener("click", () => {
    const operation = button.dataset.publicationOperation;
    request("/api/publication-cycle", publicationRequest(operation)).catch((error) => {
      $("#message").textContent = error.message;
    });
  });
});

load().catch(() => renderConnectionError());
