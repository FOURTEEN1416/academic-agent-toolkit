# Architecture and multi-panel design

## Architecture diagrams

Read the actual model code, configuration, or methods specification before
drawing. Record:

- input channels and shapes;
- stem/tokenization operations;
- parallel branches and kernel/scale definitions;
- fusion/gating/attention;
- backbone blocks and repeat counts;
- normalization and residual paths;
- output heads and reconstruction/decision rules;
- losses or training objectives when central to the method.

### Transformer minimum

When the real model uses a Transformer, expose:

- token or patch construction;
- positional/context encoding;
- LayerNorm location;
- query/key/value or multi-head attention;
- residual Add/Norm paths;
- feed-forward network;
- repetition count or multiple visible encoders;
- output pooling/heads;
- tensor shapes when verified.

A row of generic rounded boxes labeled Input, Attention, Context, Output is not
a publication-quality Transformer architecture.

### Non-Transformer models

Do not force Transformer conventions. For CNN/RNN/graph/multimodal models,
show the actual computational modules and data flow. Enlarge the true novelty,
not a fashionable substitute.

## Evidence-backed architecture figure

Architecture panels are strongest when linked to real evidence. Candidate
supporting panels:

- source input tensor or feature channel;
- scale/attention utilization;
- component ablation;
- reconstruction or prediction track;
- objective decomposition;
- efficiency/parameter frontier;
- failure or robustness example.

Use connectors only when the supporting panel directly corresponds to a model
component.

## Multi-panel narrative patterns

### Benchmark

1. paired scatter for task-level comparison;
2. distribution summary across methods;
3. ranked margin across all tasks;
4. subgroup or metric consistency;
5. efficiency when relevant.

### Ablation

1. mean effect and uncertainty;
2. per-metric effect map;
3. full task-level distributions;
4. consistency/win-rate;
5. contribution-versus-cost view.

### Generalization/transfer

1. within-versus-cross retention;
2. candidate mechanism correlation;
3. stratified dose response;
4. directional symmetry;
5. ranked entity landscape;
6. degradation distribution.

### Interpretation/mechanism

1. population-level recovery or association;
2. representative aligned local examples;
3. perturbation/attribution evidence;
4. specificity or negative control;
5. cross-task consistency.

## Layout rules

- Make the hero panel 1.5-3 times the area of supporting panels.
- Use shared axes where comparisons depend on scale.
- Consolidate repeated legends.
- Keep panel letters inside safe page margins.
- Leave enough white space to separate evidence groups.
- Align baselines, titles, and axes across rows.
- Use stable category order across pages.
- Avoid polar/circular charts unless topology or periodicity is meaningful.

