# Persistent State Contract v3.1.9

State files store only project-run-relative paths. They must not contain local absolute paths, secrets, or target-paper facts in the reusable skill package.

State validation rejects:

- path traversal and host-specific absolute paths;
- forbidden target-image substitutes for S2/S5 raster outputs;
- unknown workflow steps;
- invalid candidate statuses or substage modes;
- After S5, human decisions are outside this assistant workflow.

No state records are created after S5 in v3.2.13.
