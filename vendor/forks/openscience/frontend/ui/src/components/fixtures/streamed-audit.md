**Harness Issues**

1. **Infrastructure failures consumed autoresearch ideas permanently.**

One XGBoost idea failed before model execution with:

```text
Modal input changed after approval
```

The study contract allows exactly one run per idea and does not distinguish scientific failure from dispatch failure.

2. **A concluded study cannot be resumed or have its budget extended.**

A better API would support:

- study extend_budget
- study reopen

3. **Modal's 100 MiB staging limit conflicts with foundation models.**

The TabICLv2 checkpoint was approximately 110 MB and was rejected:

```text
Modal staging input exceeds the 100 MiB approval limit
```

4. **compute_job wait once aborted while the job continued successfully.**

A wait call returned only:

```text
Tool execution aborted
```

The underlying final-model job kept running and later succeeded.

All scripts should expose explicit names such as:

```text
oof_accuracy
oof_average_precision
mean_fold_accuracy
mean_fold_average_precision
```

**Status**

Phase 2 should remain paused.
