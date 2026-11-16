# Harness handoff boundaries

The server owns execution and durable records. Clients render those records;
they do not reconstruct executable inputs from presentation summaries. This
keeps the same behavior available to the desktop, CLI, SDK and future plugins.

This follows the useful boundaries in OpenCode's implementation, inspected at
`d6855b6b47a8433462ac6aeeba882ccf734cb7f1`: preserve tool inputs while pruning
outputs, keep a durable child identity, and resolve tools at the model boundary.
OpenScience retains its stricter project, child-session and filesystem checks.

## Arguments and outputs

`MessageV2.compactToolInput` retains authoritative arguments byte for byte.
Compaction summarizes old outputs separately. Write, Edit, ApplyPatch and Task
reject copies of an identifiable legacy shortened argument before mutation or
child dispatch. The check reconstructs a known preview from retained history;
it does not guess that every literal ellipsis is damaged data. Existing literal
examples in files remain editable. An intentional new quotation of an exact
known shortened argument is conservatively rejected; recover its full source.

## Worker completion and evidence

The latest assistant message's text after its last tool call is the handoff.
Earlier progress is not a substitute for missing final findings. Step limits,
provider errors, partial operations and missing handoffs keep explicit outcomes.
The durable Task attempt stores the result; restart recovery compares its
canonical fingerprint before returning it, without rerunning completed work.

Task evidence comes from recorded operations and ArtifactStore versions, not
from parsing the worker's claims. The parent receives artifact/version IDs,
hashes, sizes and references to shell receipts. Exit zero refers to the outer
process; scientific validity and nested test success need separate evidence.
This is an evidence handoff, not a mandatory model-generated report schema or
a new verifier loop.

Workers explicitly save important outputs with `artifact.save_file`. The lead
uses `artifact.read_file` with exact IDs to read immutable versions within the
same project. This does not grant access to the child's scratch directory or
copy an entire workspace. Text windows preserve UTF-8 byte boundaries. Reads
verify the stored blob hash; files over the 8 MiB inline limit return clearly
labeled metadata and use the existing Files/API retrieval path. No automatic
publication or artifact-store capacity bypass is added.

## Environment and tool identity

Local compute chooses its Python runtime once for both execution and receipt
generation. Shell receipts distinguish a selected default from a measured
version. An explicit interpreter in a command can override that default.
On Windows, `python` selects this default; an independently installed `python3`
or an absolute executable path can select another interpreter.
Remote source capture is labeled as submitter metadata; unmeasured remote
environment details remain unknown. Exact scientific capability runtimes keep
their separate attestation and admission path.

The LLM boundary records the actual advertised tool definitions using the
existing harness trace. A change in tool names produces a compact added/removed
notice in the next request. The initial request does not duplicate the tool
catalog in prose. Permission checks still run at execution time; a notice
cannot grant authority.
