<!-- Source: alirezarezvani/claude-skills@4680893d91f2aee6f77ca1519fd1b86b7a104c87 engineering-team/skills/code-reviewer/languages/c.md · MIT License · 2026-11-17 原样收编（仅加本溯源注释） -->
---
language: c
extensions: [".c", ".h"]
---

# C — Language-Specific Review Notes

Load this file alongside `rules/universal.md`. Universal rules are not repeated here — only C-specific rules and idioms.

---

## PR Analyzer — C Risk Signals

- `printf` / debug `fprintf(stderr, ...)` statements left in production code
- `// TODO` / `// FIXME` comments near memory management code — high risk
- Disabled compiler warnings (`#pragma GCC diagnostic ignore`, `-w` flags in Makefile)
- Hardcoded credentials or keys in source
- Use of banned functions: `gets`, `strcpy`, `strcat`, `sprintf`, `scanf` without width limits

---

## Code Quality — C Checks

- Functions longer than 50 lines — C functions tend to grow organically and become hard to reason about
- Missing `NULL` check after `malloc` / `calloc` / `realloc`
- Return value of functions ignored without explicit `(void)` cast
- Global mutable state used across translation units without clear ownership
- Magic numbers without `#define` or `const` — especially sizes and offsets
- Mixed `malloc`/`free` ownership — unclear which caller is responsible for freeing

---

## Security

- Flag `gets()` — no bounds checking, always a buffer overflow; replace with `fgets()`
- Flag `strcpy()` / `strcat()` — use `strncpy()` / `strncat()` with explicit size, or `strlcpy()` / `strlcat()`
- Flag `sprintf()` — use `snprintf()` with explicit buffer size
- Flag `scanf("%s", buf)` without a width specifier — unbounded read
- Flag `strlen()` result used as a signed integer — potential truncation on 64-bit
- Flag user-controlled data used as a format string (`printf(user_input)`) — format string attack
- Flag integer arithmetic used as array index without bounds check
- Flag signed integer overflow — undefined behavior in C

---

## Async / Concurrency

- Flag shared global or `static` variables accessed from multiple threads without a mutex or `_Atomic`
- Flag `pthread_mutex_t` / `sem_t` not initialized before use
- Flag signal handlers that call non-async-signal-safe functions (`malloc`, `printf`, etc.)
- Flag `volatile` used as a substitute for proper synchronization — it is not sufficient
- Flag lock acquisition order inconsistency across call sites — deadlock risk

---

## Resource Management

- Flag every `malloc` / `calloc` / `realloc` path — verify a matching `free` exists on all exit paths
- Flag `fopen` without a matching `fclose` on all paths including error paths
- Flag `dup` / `socket` / `open` file descriptors not closed on all paths
- Flag stack-allocated VLAs (variable-length arrays) of unbounded size — stack overflow risk
- Flag `realloc` return value assigned directly to the source pointer — leaks on failure

---

## Exception Handling

- Flag ignored return values from `malloc`, `fopen`, `read`, `write`, `close` — all can fail
- Flag `errno` checked after a function that doesn't set it, or not checked immediately after one that does
- Flag `perror` / `strerror` as the sole error handling in library code — propagate errors to callers
- Flag functions that return `-1` on error without documenting which `errno` values are possible
- Flag `assert()` used for runtime error handling — disabled by `NDEBUG` in production builds

---

## Performance

- Flag `strlen()` called repeatedly on the same string in a loop — cache the result
- Flag unnecessary copies of large structs passed by value — pass by pointer
- Flag `memcpy` / `memset` on overlapping regions — use `memmove` for overlapping
- Flag repeated heap allocations in a tight loop — consider a pool or stack allocation
- Flag `volatile` on variables not accessed by hardware or signal handlers — prevents optimization

---

## Idioms and Best Practices

### Memory Safety
- Every pointer must have a clear owner responsible for freeing it — document ownership in comments
- Set pointers to `NULL` immediately after `free` to catch use-after-free early
- Prefer `calloc` over `malloc` + `memset` for zero-initialized allocations
- Use `const` on pointer parameters that the function does not modify

### Defensive Coding
- Always check `NULL` returns from allocation functions
- Use `size_t` for sizes and counts — never `int`
- Prefer `snprintf` and `fgets` over any unbounded string function
- Compile with `-Wall -Wextra -Werror` and treat warnings as errors

### Portability
- Do not assume pointer size equals `int` size — use `intptr_t` / `uintptr_t`
- Do not rely on undefined behavior for performance — use compiler intrinsics instead
- Use `stdint.h` types (`uint32_t`, `int64_t`) for fixed-width requirements
