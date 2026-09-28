# Framework Figure Pattern Library

Use these layout patterns after the reader effect and primary subtype are known.

## Layout Patterns

| Pattern | Use When | Strength | Risk |
|---|---|---|---|
| Left-to-right pipeline | The method is stepd and sequential | Fast 10-second comprehension | Can hide feedback loops |
| Layered architecture stack | Components have abstraction levels | Clear module boundaries | Can feel generic |
| Hub-and-spoke model center | One core module coordinates inputs/tools/memory | Highlights novelty | Can over-center one block |
| Swimlane system diagram | Data/user/tool/model roles must be separated | Good for agent/system papers | Needs strong label discipline |
| Loop / agent workflow | Planning, tool use, verification, or memory updates repeat | Shows dynamics | Arrows can become cluttered |
| Modular tile board | Many modules or evidence cards need comparison | Scannable, modern | Weak sequence unless arrows are clear |
| Mechanism snapshot | One mechanism explains why the method works | Strong for intro/method bridge | May omit operational details |
| Case walkthrough strip | A concrete example travels through the method | Intuitive for qualitative papers | Not enough for full method spec |
| Baseline-vs-ours split | Novelty is comparative | Reweb-display-friendly contrast | Can become adversarial or oversimplified |

## Framework-Specific Prompt Rules

- Give every module a short, exact label.
- Make novelty visually salient without turning every box into a highlight.
- Use arrows with semantics: data flow, control flow, feedback, supervision, or evidence link.
- Keep secondary details in caption/body text unless they are needed for the 10-second reader effect.
- When multiple layout patterns are plausible, use the S1 style-combination planning pool and the selected S2 first-round candidate set to preserve structural diversity. S1-FIGURE-STRATEGY prepares exactly eight style-combination planning proposals and selects only the top four for C01-C04 prompt packages. S2-SKETCH-EXPLORE generates exactly four formal publication-style first-round candidates. S4 prepares exactly two F01-F02 formal prompt packages, and S5-CANDIDATE-IMAGE generates exactly two terminal formal candidates. Uploaded style references only inform S1-FIGURE-STRATEGY type advice and must not automatically add preference-informed extras.

## Anti-Patterns

- Generic boxes with no novelty hierarchy.
- Too many equal-weight arrows.
- Text paragraphs inside the figure.
- Fake plots or invented numeric results.
- Decorative icons that do not carry method meaning.
- Photorealistic clutter for reweb-display-sensitive method figures.

