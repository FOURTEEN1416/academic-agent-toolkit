---
name: paper-spine
description: Research, write, review and deliver evidence-bound papers in one task, with user choices, real files, editable outputs and same-task revision.
# Suite Update Authority; Blocks unsupported readiness claims.
---

# PaperSpine Orchestrator

Before paper production or resume, read [paper-spine-production-protocol.md](references/paper-spine-production-protocol.md). It is the operational 17-step handoff for the methods below.

The current host Agent performs research, citation checking, interpretation,
writing, figures and revision, and arranges independent review. Web, local files
and small scripts support interaction, persistence, rendering and delivery.

When configuration is missing, launch the intake UI automatically before inspecting
materials; do not hand-write configuration or silently choose a paper root.
For a visible launcher action, use `require_escalated` as required by the host.
After the update preflight below, launch is the first paper-production action when configuration is missing.

**Product outcome:** an evidence-bound, coherent paper with informative figures,
applicable venue format and editable sources. Learn from strong same-field and
venue papers. Let users configure, choose contribution/figures, preview,
download and revise the same task.

Tool success, hashes and task status do not establish scientific, editorial,
visual or submission readiness; assess the actual paper.

## Authority and boundaries

1. The host Agent owns scholarly judgment and the current paper files.
2. The user's materials/results are authoritative for claims about this study.
   Never invent data, metrics, p-values, citations, figures, methods, authors,
   ethics, funding, permissions or review conclusions.
3. Use one task ID, one material/workspace binding and one continuous revision
   history. Never create a second task because a launcher, profile or transport
   failed. Never silently switch to another directory, profile, task or paper.
4. Web is the supported path for configuration, user choices, previews, downloads
   and feedback. It supports the configuration and choice boundaries below; existing confirmed
   scope permits independent local corrections during a Web outage.
5. Task status never authorizes uploads, publication, submission, payment,
   licensing, telemetry or external contact; obtain explicit authorization.
6. Private materials stay local unless explicitly authorized for sharing. Apply
   the saved research mode as described below; public literature reading is normal.

## Update once on invocation, then continue the paper

Before starting or resuming paper production, run the installed Skill's
`scripts/paperspine_update.py --preflight --yes` with its verified Python.
This checks the official channel on every invocation: if current, continue;
if newer, transactionally update the Skill, Web/runtime and updater together.
Honor an explicit auto-update opt-out. An offline check may continue with the
existing installation and a clear notice; a failed install must retain the old
installation and report the actual error. Never repeatedly reinstall to repair
paper state. After a successful update, reread this installed SKILL and the
current public tool schemas, preserving the same task, profile and user files.
See [product-v1-workflow.md](references/product-v1-workflow.md) for entry details.

## Start, configure and continue the current paper

A read-only explanation, audit or plan ends with the requested result. Launch
and configuration below apply to paper production, not Skill inspection or plans.

Read [product-v1-workflow.md](references/product-v1-workflow.md) for the actual
public tool shapes and [intent-configuration.md](references/intent-configuration.md)
for first-message prefilling. The current Agent is the scientific host; launching
Web does not launch another writer. Follow this sequence:

1. Resolve the user's named material folder. “This/current folder” explicitly
   selects the conversation working directory. Without such an instruction, do
   not assume an unrelated shell directory is the paper. Initially list names
   and identify candidate inputs; defer substantive analysis until configuration
   and the material choice are saved. Preserve original materials.
2. Start the installed launcher with `launch --no-open`; it returns a service URL,
   not a paper or running AI. Open only the bound task URL once. In Codex prefer
   its available in-app browser unless the user chose another; never also open
   the external browser. Reuse that tab and the same profile for later choices.
3. Read public schemas with `host tools`. Resume the explicitly linked task only
   after checking its material roots against this paper. A remembered profile is
   a shared server preference, not the current paper ID. A recent/open browser
   tab is not task-selection authority. Two different papers have separate task
   IDs even in one profile. If this paper has no task, the current Agent calls
   `paperspine_open_task`; it must not wait for another host to create one.
4. For a new task supply a concise `title` and one-sentence `description` in the
   open-task payload, derived from the user's actual topic, inputs and requested
   output. Include the target venue when known; do not invent findings or expose
   absolute private paths. Preserve identity on resume. The task's workspace is
   for generated files; authorized material roots may correctly be elsewhere.
5. Prefill settings supported by the user's request as an AI proposal, including
   workflow, target, language, research mode, reading depth and delivery formats.
   Default to 3+3 papers or 6+6 for deeper literature learning; explicit counts
   prevail. Public-paper retrieval needs no permission toggle; private inputs
   stay local. Open the returned `skill_bridge.web_path` on the launched origin;
   verify the task title/ID and configuration/material cards. A homepage, stale
   task, blank page or printed URL is not a configuration handoff.
6. Await Web input with `host wait` (`product-v1-workflow.md`).
   Use same profile/task/version; follow its running exec session.
   Configuration needs `source=web_user`, `user_confirmed=true`,
   `readiness.ready=true`; choices need saved selections and comments.
   Prefills, old receipts and unrelated events are not answers. If pending,
   wait from `task_version`; stay responsive. Continue when valid;
   stop on cancellation/interruption. Web cannot wake a finished host turn.
7. Later motivation and figure choices follow the same request → Web save →
   read-back route. Respect existing explicit delegated-choice authorization;
   never label an Agent choice as a user click. On interruption, read the same
   task's snapshot and current pending input before continuing.

If startup fails, repair that concrete runtime/browser problem and retry the
same binding. Do not create a replacement task or infer missing configuration.
For an existing configured task, independent local corrections within its saved
scope can continue while Web is unavailable. New research/writing that depends
on pending configuration, material selection or figure decisions must wait.
If the user explicitly requests restarting from scratch, create fresh task state
for the same original inputs; do not silently resurrect deleted task IDs.

Use the chosen browser for paper decisions and results; keep internal grants,
receipts and Runner stages out of user chores.

## Work continuously within the confirmed scope

Use applicable protocol steps, not 17 forms or backend gates. Check artifacts
and downstream use; repair the source at the defect location and compare
outputs. After two unchanged attempts, change tactic, not notes/status/hash.
Reuse valid saved work.

**Mandatory before the next work segment or stage:** verify that the previous
segment's real results have reached the same task's workbench. Read the current
snapshot; publish any completed deliverable that the user should see; call
`paperspine_commit_milestone` with a factual summary, the appropriate existing
stage and actual artifact IDs. Then read back the same task/profile and current
version: confirm its stage, milestone summary, visible files and pending choices
match what actually happened. Only then begin the next dependent segment.
Several protocol steps may share one existing stage; do not create 17 backend
stages or write a milestone for every sentence/tool call. Reuse an already
matching checkpoint rather than duplicating it. On resume apply this check first.
Writing or publishing files alone does not advance the workbench. If read-back
fails, fix the concrete binding/sync error before claiming progression; keep
local results and continue only independent work within saved scope. Never fake
review/delivery completion to move a progress indicator. Follow the exact calls
in [product-v1-workflow.md](references/product-v1-workflow.md).

Read the saved `configuration.workflow` and `research_mode` before choosing work.
Use `build_from_materials` to develop the paper; `rewrite_existing` to improve the
existing argument and prose while retaining valid results; `audit` and `review`
to deliver findings on the supplied files; `revise` to address actual feedback;
and `transfer` to adapt the existing science to the new venue. Read the matching
playbook. Reuse valid configuration, choices and results: a workflow label does
not require another intake, new analyses, or an entirely new manuscript.

Choose tools, intermediate files, work order and repair tactics with scholarly
judgment. The route below describes the work the paper needs; it is not a rigid
sequence of approvals. Combine related work and run independent retrieval,
analysis or rendering in parallel when useful. Draft, figures and evidence can
inform each other while pending user choices remain unassumed.

Pause dependent work only for an actual missing user decision, indispensable
fact, or unavailable capability. Bundle related questions, reuse saved answers
and explicit delegated-choice authority, and continue unaffected work. Ordinary
search, template adaptation, wording, chart construction and local repairs within
the saved scope do not need another confirmation. Never silently skip the initial
Web configuration/material save or choose on the user's behalf in guided work.

Keep compact notes and valid outputs, not every example form or receipt. Read
applicable methods fully on first use. On resume, recover saved choices and the
next action; reopen needed original passages if their content was lost, even when
files are unchanged. A read marker is not retained knowledge.
When available and authorized, delegate bounded work with real inputs and disjoint
writes; inspect returned artifacts and manuscript use yourself. A worker's self-check
is not independent review. No fixed team is required.

Distinguish dependencies from permissions; retry with a concrete correction.
Recheck affected outputs and stop optional polish without useful improvement.

## Scientific work and expected results

Use [current-method-routing.md](references/current-method-routing.md) to select applicable original methods. Read their full text on first use; routing is not application or quality proof. If the helper is unavailable, read the local originals and continue the same task.

### 1. Anchor, intake and inventory

Read [intake.md](references/intake.md), [intent-configuration.md](references/intent-configuration.md) and [resume.md](references/resume.md) as applicable. Preserve originals. Inventory results, draft, figures, references, scripts, provenance, permissions and limits; identify only necessary missing decisions. Do not create placeholders.

Select actual research files deliberately: pass exact root-relative files in
`grants[].include_paths` to `paperspine_authorize_materials`. A project folder may
contain locked logs, caches and generated drafts; do not treat all of them as
scientific inputs. Keep generated outputs in the task workspace. Read the returned
inventory and `scan_issues`, then actually open the files needed for each claim.
A listed filename or successful registration does not prove reading. Individual
`materials.read_failed` warnings do not cancel saved configuration or the entire
paper: use readable inputs and continue unaffected research/writing. State which
file failed and why, retry only that concrete problem, and pause only claims that
need indispensable unavailable evidence. Never invent its contents. When the user
replaces the material folder, use `replace: true`; otherwise retain the same roots
and explicit selection. See the material call example in the workflow reference.

### 2. Research, target learning and citations

Read [research.md](references/research.md), [local-reference-ingestion.md](references/local-reference-ingestion.md), [citation.md](references/citation.md), [journal-learning.md](references/journal-learning.md), [target-journal-research.md](references/target-journal-research.md) and the applicable venue playbook. Read public literature unless explicitly limited. Use the saved learning-set sizes; inspect actual target-venue PDFs, current official instructions and any applicable official template. Abstracts can support bounded claims but cannot prove full-text, figure or page-design learning. Verify citation identity and use; build useful references without padding.

Resolve target identity before claiming target-format learning. An Agent-selected comparator is not the saved target. If unknown, save a delegated choice, ask once, or keep the draft venue-neutral. Format learning counts only when the source uses a verified template/style or stated fallback and representative pages match actual exemplars.

Apply the saved analysis scope to actual tool work:

- `required`: carry out justified research or analysis on authorized materials.
  Preserve reusable code, derived data, Methods, Results and uncertainty. A
  literature dossier or analysis plan alone does not complete research.
- `agent_decide`: assess what evidence the scientific question needs and what
  the inputs support, state the rationale briefly, and perform the justified
  work. This mode does not silently mean `materials_only`.
- `materials_only`: use the supplied analyses, tables, images and reported
  results without new EDA, tests, modelling, experiments or reruns. Literature
  study, faithful extraction, plotting supplied results and consistency checks
  remain available. Missing raw arrays alone do not invalidate user results.

Learning depth (3+3/6+6) does not authorize analysis. Pursue the strongest
supported question within scope; missing endpoint facts do not require an
inventory-only paper. Never invent facts, change accepted direction silently,
or analyze outside the selected mode.

### 3. Contribution, motivation and evidence contract

Read [contribution.md](references/contribution.md), [semantic-confirmation.md](references/semantic-confirmation.md), [scientific-evidence-ledger.md](references/scientific-evidence-ledger.md), and [results-validation.md](references/results-validation.md) for evidence-bearing work. Form a small set of evidence-backed options; have the user choose when choice matters. Use the accepted contribution, motivation, claim boundaries, terminology and uncertainty to guide drafting. Refine the argument as actual findings develop; request another choice only for a substantive change to the user-selected direction.

### 4. Outline, writing and figures

For `build_from_materials`, read [build.md](references/build.md); for rewriting, read [rewrite.md](references/rewrite.md). Apply [editorial-completeness.md](references/editorial-completeness.md) and [assertive-scientific-writing.md](references/assertive-scientific-writing.md). Write a complete evidence-bound argument, not a summary or template shell.

Before figures, read [scientific-figure-workflow.md](references/scientific-figure-workflow.md), [figure-story.md](references/figure-story.md) and [figure-reference-mapping.md](references/figure-reference-mapping.md). Map actual results to questions and assign each useful job—cohort, primary finding, comparison, uncertainty/validation, robustness/subgroup and explanation—to a figure, table, prose, supplement or justified omission. No quota: merge duplicates, but do not let the current folder or one omnibus plot define the story. View matched references before design.

For `mechanism_figure: auto` or `prefer`, make an explicit decision. If explanation is central and sourced, create a complete mechanism/conceptual/architecture candidate in addition to necessary data figures, distinguishing observations, established knowledge and hypotheses. Under `auto`, omit only for a concrete reason. A flowchart, ROC panel or statistical summary is not a mechanism figure.

Expose current, reference and candidate files for each selectable figure and read every saved choice/comment before assembly. Preserve data truth, editable sources, panel identity, caption/body alignment, units, claim boundaries and prior figure bytes; keep references/comparisons separate from final candidates.

### 5. Render, assemble and inspect

Read [latex.md](references/latex.md), [manuscript-format.md](references/manuscript-format.md), [visual-readiness-gate.md](references/visual-readiness-gate.md), and [publication-surface.md](references/publication-surface.md). Produce the requested editable source, a submission-oriented file when the venue defines one, a clean reading PDF, and DOCX unless the user explicitly opts out. Submission and reading surfaces must share one semantic source, numbers, citations, captions and selected figures; layout may differ only for a documented venue purpose. Inspect every PDF page and the actual DOCX/faithful Word rendering. Check title, headings, citations/links, figures, captions, references, units, clipping, page breaks, fonts, declarations, page occupancy and reader flow. Any blank or nearly blank page/column, avoidable large void, stranded heading, excessive float gap, orphaned caption, or late source/Word/PDF mismatch is a failure requiring source-level repair. Visible TeX, inert literal citations, missing images and unreadable pages are failures.

### 6. Independent review and repair

Read [review-policy.md](references/review-policy.md), [audit.md](references/audit.md), [reviewer-audit.md](references/reviewer-audit.md), [evidence-grounded-review.md](references/evidence-grounded-review.md) and [publication-surface.md](references/publication-surface.md) as applicable. An independent-context reviewer must inspect the actual current manuscript, figures and renders. `balanced` means compact editorial review; `strict` adds requested depth/specialists. Never substitute the writer's self-check or fabricate a reviewer, objection, score or PASS. If unavailable, disclose pending independent review and continue safe local repair.

Trace headline claims to sources, controls and uncertainty; compare final figures and evidence coverage with venue exemplars. Independently check three demonstrated failure points: whether the saved target was actually applied to source and rendered pages, whether distinct result families received an appropriate visual/table/text role, and whether an `auto`/`prefer` explanatory figure was completed or honestly omitted for a stated reason. Separate scientific, editorial, technical and submission findings: a format check or figure choice cannot approve the whole paper. Repair the producing source/method, regenerate affected outputs and re-review, rather than editing receipts.

### 7. Delivery and same-task revision

Read [submission.md](references/submission.md), [publication-cycle.md](references/publication-cycle.md), [publication-cycle-interface.md](references/publication-cycle-interface.md), and [submission-metadata.md](references/submission-metadata.md) only when the requested delivery/venue operation needs them. Use [open-release.md](references/open-release.md) only for explicit release work. Publish the real files, keep shareable and local-workspace packages separate, exclude private raw materials by default, and verify the actual browser download when claiming it. On feedback, reread the saved feedback and affected artifacts, preserve the previous revision, change only affected work, regenerate and re-review in this same task.

## Quality rules that always remain active

- Every substantive claim has source/result support and a bounded uncertainty.
- Citation identity and citation context are both checked; no fabricated or inert
  references. Author, ethics, permissions and external actions are confirmed,
  never inferred.
- User results are not silently reanalyzed, embellished or generalized.
- Figure story, pixels, caption, body reference and editable source agree.
- Use evidence-bound `author_voice_check.py`; `humanize_check.py` and detector
  scores are diagnostics, not paper-quality verdicts. Keep internal workflow
  chatter out of the paper, but preserve real study methods, software/model
  names, citations, ethics and factual venue-required or user-requested
  disclosures. Do not invent notices or remove truthful required disclosures.
  Keep detailed execution provenance in the private work package.
- Do not require historical Runner receipts, VERA acceptance, medical replay or
  a completed historical case suite as a general product prerequisite. The saved
  literature-learning counts remain active requirements for this paper.
- Unknown venue/author/ethics facts may limit submission readiness but do not
  block safe local drafting or correction.
- Report local delivery, scientific limitations, submission readiness and
  external authorization separately.

## Completion contract

Deliver the requested scope, not a publication guarantee:

- Same task/material root; saved choices and limitations preserved.
- Arrange independent manuscript review. Correct scientific contradictions or
  narrow claims. If review is unavailable, deliver a usable draft with review
  pending, not a reviewed final. Optional style preferences need not block it.
- Requested figures, citations, PDF/DOCX and editable dependencies present;
  actual renders inspected, not merely hashed or built.
- Package contents and sharing scope explicit. Local draft delivery is not
  submission readiness; missing author/ethics/venue facts remain disclosed.
- External submission/publication requires separate authorization.

For resume/update/respond/translate/transfer/audit requests, read the specific
playbook first and keep the same task. Updates concern installation only and must
preserve task/data roots. Historical worker skill names and old Runner protocols
are not user entry points.

Use the user's language for progress and delivery. Keep reports concise and
truthful. The manuscript is the product; the task state is only its support.
