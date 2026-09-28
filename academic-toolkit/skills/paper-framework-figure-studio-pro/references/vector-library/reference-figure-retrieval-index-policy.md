# Reference Figure Retrieval Index Policy

## Purpose

Build a retrieval index that lets Skill B ask:

> Which existing reference figures are relevant to this target paper's story, model architecture, and desired reviewer effect?

Retrieval must not be style-only. The most useful reference for a target paper may have a different color palette but a similar architecture/story structure.

## Retrieval Dimensions

### Story Similarity

- reader question;
- problem-to-method narrative;
- central insight type;
- contribution type;
- mechanism explanation type;
- evidence role;
- target misconception to prevent.

### Architecture Similarity

- modality: text, vision, audio, graph, multimodal, code, tabular, RL/environment;
- topology: pipeline, encoder-core-decoder, stack, loop, graph network, retrieval-augmented flow, agent workflow, system/data-flow, train-infer split;
- module roles: encoder, retriever, memory, planner, verifier, generator, loss, reward, tool, database, environment;
- edge roles: data flow, control flow, feedback, memory update, loss signal, evidence link;
- stage outputs: embeddings, retrieved evidence, latent state, plan, action, prediction, metric.

### Figure Design Similarity

- subtype;
- layout grammar;
- visual rhetoric: overview, mechanism, walkthrough, evidence, comparison, failure;
- reader path;
- density;
- symbol/formula level;
- evidence placement;
- icon style;
- dimensionality;
- vector-buildability.

### Preference Compatibility

- user palette preference;
- shape language;
- icon style;
- arrow style;
- professional vs teaching tone;
- vector/PPT safety.

## Scoring Recommendation

Use a weighted score such as:

```text
score =
  0.30 * story_similarity
+ 0.30 * architecture_similarity
+ 0.15 * figure_subtype_layout_match
+ 0.10 * reviewer_first_score
+ 0.10 * vector_buildability
+ 0.05 * preference_compatibility
```

Visual style should not dominate retrieval unless the user explicitly requests a style reference search.

## Required Retrieval Output

`retrieved_reference_case_set.json` should group references as:

- `direct_story_architecture_match`
- `architecture_match_style_different`
- `story_match_architecture_different`
- `visual_style_match_only`
- `evidence_treatment_reference`
- `do_not_use_due_to_mismatch`

Each reference must include:

- why it matches;
- what to borrow;
- what not to borrow;
- risks;
- adaptation notes for the target paper;
- whether it can guide Round 1, Round 2, or final vector construction.
