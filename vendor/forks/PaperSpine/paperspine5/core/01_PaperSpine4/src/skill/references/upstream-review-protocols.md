# Upstream Review Protocol Provenance

PaperSpine uses a clean-room, provider-neutral reimplementation of general
review protocols learned from the projects below. No runtime dependency or
copied source code is introduced. The inspected commits and licenses make the
design provenance auditable.

| Upstream | Inspected commit | License | Protocol absorbed | Boundary retained |
|---|---|---|---|---|
| Agentic Paper Review | `c117aba2dbb26fece9ab2de12b84c1874fa63e6f` | MIT | Specialist/editor separation, optional librarian/fact-checker/critic, conflict Judge, criterion evidence | Humans retain accept/reject authority; weighted scores do not override PaperSpine truth gates |
| Open ScholarPeer | `c93d344cd40017b7c406d9e410c04805e6c2c644` | MIT | Problem/method/time retrieval rounds, historian and baseline-scout lanes, auditable artifacts | Provider support is not assumed; PaperSpine records actual provider status and keeps closed-corpus runs closed |
| DeepReviewer 2.0 | `1c19a232c0620b0f24e56d5965258dde00a702ae` | MIT | Proactive PDF locate/annotate/search tool loop, event receipts, usage accounting | Fixed call-count quotas are not copied; PaperSpine uses risk-based budget ceilings and evidence goals |
| AI Paper Review | `f2f72a912b3a1a23b92165382cbedf332a7b92a6` | MIT | Replaceable personas, duplicate clustering, AI-human hit/miss/false-alarm calibration, cross-paper recommendations | Lexical alignment is labeled heuristic; calibration cannot silently rewrite the registry |

Repository sources inspected on 2026-08-26:

- <https://github.com/ngstcf/agentic-paper-review>
- <https://github.com/amirkiarafiei/open-scholar-peer>
- <https://github.com/ResearAI/DeepReviewer-v2>
- <https://github.com/UnaryLab/ai-paper-review>

The controlling PaperSpine contract is `evidence-grounded-review.md`, not any
upstream README or implementation detail.
