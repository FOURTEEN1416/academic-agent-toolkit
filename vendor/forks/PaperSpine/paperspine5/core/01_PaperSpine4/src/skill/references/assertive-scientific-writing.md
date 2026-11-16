# Assertive Scientific Writing

Internal verification can be strict without making the paper timid. Write the
reader-facing manuscript as a confident scholarly argument.

## Direct by Default

- State observed results directly: “CARBON improved Pearson correlation across
  the evaluated tasks,” not “The supplied evidence appears to suggest that
  CARBON may potentially improve…”.
- Use active, specific verbs: improves, reduces, identifies, captures, supports,
  outperforms, reveals. Choose the verb whose strength matches the evidence.
- State the contribution and why it matters without self-deprecating workflow
  language.
- Write the user's study as a research paper, with its scientific question,
  methods, findings and significance. Do not make the assistant's material
  inventory, file checks or lack of a new replication the subject of the paper.
  Preserve scientifically important design and measurement information; put
  engineering execution details in task notes or the local work package, not
  in the article's scientific supplementary material. Research reproducibility
  information and required disclosures remain part of the scholarly record.

## Hedge Only Where the Inference Changes

Use qualification for causal claims from observational evidence, extrapolation
beyond evaluated data, uncertain provenance, incomplete statistics, or genuine
alternative explanations. Put one clear boundary at the relevant paragraph,
section, caption, or limitations passage; do not repeat it sentence by sentence.

Avoid stacked hedges such as “may potentially suggest,” repetitive “within the
supplied materials,” and audit phrases such as “user-authoritative evidence.”
The evidence ledger holds provenance; the manuscript communicates the science.
Apply [publication-surface.md](publication-surface.md) to mixed scientific and
production-status paragraphs. Figure choices govern which image is used; they
are not a finding to announce. Prefer one consequential limitation over repeated
workflow disclaimers, without removing uncertainties that change interpretation.

## Limitations

Limitations should identify the few constraints that change interpretation or
generalizability. Do not add ritual disclaimers for every ordinary design choice.
A concise, specific limitation is stronger than pervasive defensive prose.

## Organize the argument around the earned result

Use the closest actually read work to state what the study adds under the
tested conditions. After analysis or a substantive revision, check the title,
abstract, introduction's contribution and conclusion against the same result.
A useful negative or uncertain result may change the question the paper can
answer; it need not be hidden or converted into a positive claim.

Distinguish improvement of a complete method from evidence that one component
caused it. A component-removal comparison whose uncertainty includes no change
does not establish that component's independent benefit, and does not prove it
has no effect. Consider other changed controls, evaluation windows and resource
budgets before attributing the result. Resolve this through a narrower claim or
an authorized targeted experiment, not stronger adjectives or significance seeking.

For Results, connect the decisive quantitative comparison and its uncertainty
to the scientific question. For Discussion, explain the contrast with prior
work, plausible alternatives and the remaining discriminating question. Group
repeated limitations where they change interpretation; keep locally necessary
qualifications and required disclosures. Reader-facing labels such as "supplied"
or "confirmation" are appropriate only when they identify a meaningful study
design, not merely how the assistant received or checked a file. This is
contextual editing, not a word blacklist or automatic deletion rule.

## Apply the saved author-expression preference

Read `configuration.author_voice_restoration` from the same task. `off` uses
ordinary scientific editing. `standard` preserves the author's characteristic
terminology, emphasis and useful phrasing while improving concrete weaknesses.
`strict` makes the minimum necessary changes to the author's expression and
argument structure; explain any substantial restructuring in the revision notes.
Neither option permits changing results, claim strength or scientific meaning.

Use the supplied draft and the author's own or explicitly authorized writing
as the voice reference. Do not treat a target-journal exemplar as that author's
personal voice. If no author text exists, retain the user's explicit expression
preferences and state that a personal voice could not be learned; continue useful
writing without inventing one or requiring a new writing corpus.

Preserve the prior draft. For each affected passage, identify its scientific
function, retain the evidence and terminology, and fix only the actual reader
problem. Clear text may remain unchanged. Compare the revised passage with the
original for numbers, negation, qualifications, attribution and conclusion strength.
Give the independent reviewer both versions and the actual saved preference.
Do not use a detector score, word blacklist or sentence-rhythm quota as authorship
evidence. Historical author-voice receipts, hash-bound confirmation and fixed
approval sequences are not prerequisites for this current host method.
