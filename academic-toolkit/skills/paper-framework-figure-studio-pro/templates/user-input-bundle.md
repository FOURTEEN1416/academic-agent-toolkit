# User Input Bundle Template v3.2.15f

## Workflow

S0-PAPER-FOUNDATION -> S1-FIGURE-STRATEGY -> S2-SKETCH-EXPLORE -> S3-DIRECTION-SELECT -> S4-CANDIDATE-BRIEF -> S5-CANDIDATE-IMAGE -> END

## Required user-visible inputs by stage

- S0: paper/source files, task scope, runtime, canvas preferences, risk tolerance.
- S1: S0 foundation/risk register and any user constraints; S1 also plans eight complementary style-combination proposals, selects four, and prepares the C01-C04 S2 prompt-index.
- S2: S1-prepared C01-C04 S2 prompt-index; image generation only.
- S3: registered S2 images and prompt-index; S3 reviews/aggregates S2 and chooses direction.
- S4: S3 direction decision and S2 issue transfer; S4 also prepares the F01-F02 S5 prompt-index with row-level S2 reference image paths.
- S5: S4-prepared F01-F02 S5 prompt-index plus row-level S2 reference images when supported; image generation only and terminal.

## Cleanup / rerun

If rerunning a prior stage, clean that stage and downstream run outputs according to the step-rewind policy. S2/S5 candidate-level rerun is removed; use explicit rerun rather than rerun.

## Terminal boundary

After S5, assistant workflow ends. Remaining selection, manual editing, captioning, and paper-layout decisions are human decisions.
