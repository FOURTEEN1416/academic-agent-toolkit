## Description: <br>
Detects AI-like patterns in Chinese text and rewrites Chinese content across general, social, stylistic, and academic AIGC-reduction workflows using local Python CLI tools. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[swaylq](https://clawhub.ai/user/swaylq) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
External users and developers use this skill to assess Chinese text for AI-like writing signals, rewrite it into more natural Chinese styles, and compare before/after detection scores. Academic users can apply its specialized workflow to revise Chinese academic prose while preserving scholarly tone. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: The skill is designed to reduce AI/AIGC detection scores, including in academic contexts, which could be misused to conceal AI authorship or bypass institutional, publisher, employer, or platform rules. <br>
Mitigation: Use only for legitimate local editing where disclosure and policy compliance are maintained, and do not use it to evade detection or misrepresent authorship. <br>
Risk: Rewriting may change meaning, citations, terminology, or factual accuracy in the source text. <br>
Mitigation: Manually review rewritten output for meaning, citation integrity, domain terminology, and accuracy before relying on or submitting it. <br>
Risk: The CLI can read from and write to local file paths selected by the user. <br>
Mitigation: Run it only on intended files, choose output paths carefully, and inspect generated files before replacing originals. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/swaylq/humanize-chinese) <br>
- [ClawHub publisher profile](https://clawhub.ai/user/swaylq) <br>


## Skill Output: <br>
**Output Type(s):** [Text, Markdown, Code, Shell commands, Configuration, Guidance] <br>
**Output Format:** [Markdown and plain text with optional JSON output from CLI commands] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Can read from stdin or files, write rewritten text to output files, and produce score-only, verbose, comparison, or JSON reports depending on command flags.] <br>

## Skill Version(s): <br>
2.4.0 (source: ClawHub release evidence) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
