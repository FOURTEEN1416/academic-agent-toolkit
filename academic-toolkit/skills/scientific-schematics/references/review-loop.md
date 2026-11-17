<!-- 改写收编自 K-Dense Inc. 的 scientific-schematics 技能（MIT，github.com/K-Dense-AI/scientific-agent-skills）。生成–评审–精炼回路的机制、评分合同与示例；本仓以 generate_image 原生路由为主，scripts/ 为回退实现。 -->

# Smart Iterative Refinement Workflow

How the generate–review–refine loop works: the initial generation, the quality
review, the decision to continue or stop, subsequent iterations, and the review
log. Then the advanced generation options (Python API, command-line options,
prompt engineering) and four worked examples.

Model names below (image model, review model) are illustrative examples — the
actual backends are whatever Step 0 of the SKILL detected and the environment
configured.

## How smart iteration works

The loop is **smart iteration**: it only regenerates when quality is below the
threshold for your document type.

```
┌─────────────────────────────────────────────────────┐
│  1. Generate image (image model)                    │
│                    ↓                                │
│  2. Review quality (vision-capable review model)    │
│                    ↓                                │
│  3. Score >= threshold?                             │
│       YES → DONE! (early stop)                      │
│       NO  → Improve prompt, go to step 1            │
│                    ↓                                │
│  4. Repeat until quality met OR max iterations      │
└─────────────────────────────────────────────────────┘
```

### Iteration 1: initial generation

**Prompt construction:**

```
Scientific diagram guidelines + User request
```

**Output:** `diagram_v1.png`

### Quality review

The review pass evaluates the diagram on five criteria, 0–2 points each (the
same rubric as SKILL.md Step 4):

1. **Scientific Accuracy** (0–2) — correct concepts, notation, relationships
2. **Clarity and Readability** (0–2) — easy to understand, clear hierarchy
3. **Label Quality** (0–2) — complete, readable, consistent labels
4. **Layout and Composition** (0–2) — logical flow, balanced, no overlaps
5. **Professional Appearance** (0–2) — publication-ready quality

**Example review output:**

```
SCORE: 8.0

STRENGTHS:
- Clear flow from top to bottom
- All phases properly labeled
- Professional typography

ISSUES:
- Participant counts slightly small
- Minor overlap on exclusion box

VERDICT: ACCEPTABLE (for poster, threshold 7.0)
```

### Decision point: continue or stop?

| If score... | Action |
|-------------|--------|
| >= threshold | **STOP** — quality is good enough for this document type |
| < threshold | Continue to the next iteration with an improved prompt |

**Example:**

- For a **poster** (threshold 7.0): score of 7.5 → **done after 1 iteration**
- For a **journal** (threshold 8.5): score of 7.5 → continue improving

Thresholds by document type: **journal 8.5**; **conference / thesis / grant
8.0**; **preprint / report 7.5**; **poster 7.0**; **slides / presentation 6.5**.

### Subsequent iterations (only if needed)

If quality is below threshold, the loop:

1. Extracts the specific issues from the review
2. Enhances the prompt with improvement instructions
3. Regenerates the image
4. Reviews again
5. Repeats until the threshold is met or the maximum (2) iterations are reached

### Review log

All iterations are saved with a JSON review log that includes early-stop
information:

```json
{
  "user_prompt": "CONSORT participant flow diagram...",
  "doc_type": "poster",
  "quality_threshold": 7.0,
  "iterations": [
    {
      "iteration": 1,
      "image_path": "figures/consort_v1.png",
      "score": 7.5,
      "reviewed": true,
      "review_error": null,
      "needs_improvement": false,
      "critique": "SCORE: 7.5\nSTRENGTHS:..."
    }
  ],
  "final_score": 7.5,
  "final_reviewed": true,
  "early_stop": true,
  "early_stop_reason": "Quality score 7.5 meets threshold 7.0 for poster"
}
```

**Note:** with smart iteration you may see only 1 iteration instead of the full
2 when quality is achieved early.

### When the review does not run

The reviewer is a second model call, and it can fail on its own — a rate limit,
a content filter, an answer in a shape the parser cannot read. The image is
generated first and is kept regardless; what is missing in that case is the
*measurement*, so the log says so rather than substituting a number:

```json
{
  "iterations": [
    {
      "iteration": 1,
      "image_path": "figures/consort_v1.png",
      "score": null,
      "reviewed": false,
      "review_error": "the review model returned no choices",
      "needs_improvement": false,
      "critique": "Review unavailable: the review model returned no choices."
    }
  ],
  "final_score": null,
  "final_reviewed": false
}
```

The run exits 0 — the diagram is real — and prints
`Review unavailable — image kept, quality not verified`. It does **not**
regenerate: a reviewer that did not answer says nothing about the diagram, so
another generation would be guesswork. Look at the image yourself and re-run if
you want a score; these failures are usually transient.

`final_reviewed` is the field to check in automation. `final_score` alone cannot
distinguish "scored 7.5" from "never scored".

## Advanced generation usage

### Python API

```python
from scripts.generate_schematic_ai import ScientificSchematicGenerator

# Initialize generator
generator = ScientificSchematicGenerator(
    api_key="your_openrouter_key",
    verbose=True
)

# Generate with iterative refinement (max 2 iterations)
results = generator.generate_iterative(
    user_prompt="Transformer architecture diagram",
    output_path="figures/transformer.png",
    iterations=2
)

# Access results
print(f"Final score: {results['final_score']}/10")
print(f"Final image: {results['final_image']}")

# Review individual iterations
for iteration in results['iterations']:
    print(f"Iteration {iteration['iteration']}: {iteration['score']}/10")
    print(f"Critique: {iteration['critique']}")
```

### Command-line options

```bash
# Basic usage (default threshold 7.5/10)
python scripts/generate_schematic.py "diagram description" -o output.png

# Specify document type for the appropriate quality threshold
python scripts/generate_schematic.py "diagram" -o out.png --doc-type journal      # 8.5/10
python scripts/generate_schematic.py "diagram" -o out.png --doc-type conference   # 8.0/10
python scripts/generate_schematic.py "diagram" -o out.png --doc-type poster       # 7.0/10
python scripts/generate_schematic.py "diagram" -o out.png --doc-type presentation # 6.5/10

# Custom max iterations (1-2)
python scripts/generate_schematic.py "complex diagram" -o diagram.png --iterations 2

# Verbose output (see all API calls and reviews)
python scripts/generate_schematic.py "flowchart" -o flow.png -v

# Combine options
python scripts/generate_schematic.py "neural network" -o nn.png --doc-type journal --iterations 2 -v
```

### Setup and cost

```bash
# The key comes from the environment (Step 0 of the SKILL); for the script
# fallback, provide it via env var or a .env file at the project root:
export OPENROUTER_API_KEY='sk-or-v1-your_key_here'
```

Each iteration costs **two API calls**: one image generation and one vision
review. A diagram that passes on the first try therefore costs two calls, and
the maximum for any single run is four. The image model dominates the bill.
Check current per-model pricing on the provider console — it changes, and any
figure written here would go stale.

Cost discipline: external API calls require high-risk confirmation and count
toward the C5 cost metric (see SKILL.md Step 0).

### Prompt engineering tips

**1. Be specific about layout:**

```
✓ "Flowchart with vertical flow, top to bottom"
✓ "Architecture diagram with encoder on left, decoder on right"
✓ "Circular pathway diagram with clockwise flow"
```

**2. Include quantitative details:**

```
✓ "Neural network with input layer (784 nodes), hidden layer (128 nodes), output (10 nodes)"
✓ "Flowchart showing n=500 screened, n=150 excluded, n=350 randomized"
✓ "Circuit with 1kΩ resistor, 10µF capacitor, 5V source"
```

**3. Specify visual style:**

```
✓ "Minimalist block diagram with clean lines"
✓ "Detailed biological pathway with protein structures"
✓ "Technical schematic with engineering notation"
```

**4. Request specific labels:**

```
✓ "Label all arrows with activation/inhibition"
✓ "Include layer dimensions in each box"
✓ "Show time progression with timestamps"
```

**5. Mention colour requirements:**

```
✓ "Use colorblind-friendly colors"
✓ "Grayscale-compatible design"
✓ "Color-code by function: blue for input, green for processing, red for output"
```

## Worked examples

### Example 1: CONSORT flowchart

```bash
python scripts/generate_schematic.py \
  "CONSORT participant flow diagram for randomized controlled trial. \
   Start with 'Assessed for eligibility (n=500)' at top. \
   Show 'Excluded (n=150)' with reasons: age<18 (n=80), declined (n=50), other (n=20). \
   Then 'Randomized (n=350)' splits into two arms: \
   'Treatment group (n=175)' and 'Control group (n=175)'. \
   Each arm shows 'Lost to follow-up' (n=15 and n=10). \
   End with 'Analyzed' (n=160 and n=165). \
   Use blue boxes for process steps, orange for exclusion, green for final analysis." \
  -o figures/consort.png
```

### Example 2: neural network architecture

```bash
python scripts/generate_schematic.py \
  "Transformer encoder-decoder architecture diagram. \
   Left side: Encoder stack with input embedding, positional encoding, \
   multi-head self-attention, add & norm, feed-forward, add & norm. \
   Right side: Decoder stack with output embedding, positional encoding, \
   masked self-attention, add & norm, cross-attention (receiving from encoder), \
   add & norm, feed-forward, add & norm, linear & softmax. \
   Show cross-attention connection from encoder to decoder with dashed line. \
   Use light blue for encoder, light red for decoder. \
   Label all components clearly." \
  -o figures/transformer.png --iterations 2
```

### Example 3: biological pathway

```bash
python scripts/generate_schematic.py \
  "MAPK signaling pathway diagram. \
   Start with EGFR receptor at cell membrane (top). \
   Arrow down to RAS (with GTP label). \
   Arrow to RAF kinase. \
   Arrow to MEK kinase. \
   Arrow to ERK kinase. \
   Final arrow to nucleus showing gene transcription. \
   Label each arrow with 'phosphorylation' or 'activation'. \
   Use rounded rectangles for proteins, different colors for each. \
   Include membrane boundary line at top." \
  -o figures/mapk_pathway.png
```

### Example 4: system architecture

```bash
python scripts/generate_schematic.py \
  "IoT system architecture block diagram. \
   Bottom layer: Sensors (temperature, humidity, motion) in green boxes. \
   Middle layer: Microcontroller (ESP32) in blue box. \
   Connections to WiFi module (orange box) and Display (purple box). \
   Top layer: Cloud server (gray box) connected to mobile app (light blue box). \
   Show data flow arrows between all components. \
   Label connections with protocols: I2C, UART, WiFi, HTTPS." \
  -o figures/iot_architecture.png
```
