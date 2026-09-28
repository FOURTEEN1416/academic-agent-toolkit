# Script Core Architecture v3.2.13

The script core models the workflow as S0-S5 only. S2 and S5 support `IMAGE_GENERATE` substages only. S1/S3/S4 carry the active text duties adjacent to image-only stages.

No script command may create or validate an assistant stage after S5. Commands for post-S5 assistant flow must stay absent.
