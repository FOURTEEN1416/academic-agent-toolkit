---
name: dev-debug
description: "Use when the user asks to ”debug this”, ”fix this error”, ”investigate this bug”, or ”troubleshoot a failure”."
version: 0.1.0
---

# Bug Detective

A systematic debugging workflow for investigating and resolving code errors, exceptions, and failures. Provides structured debugging methods and common error pattern recognition.

## Core Philosophy

Debugging is a scientific problem-solving process that requires:
1. **Understand the problem** - Clearly define symptoms and expected behavior
2. **Gather evidence** - Collect error messages, logs, stack traces
3. **Form hypotheses** - Infer possible causes based on evidence
4. **Verify hypotheses** - Confirm or eliminate causes through experiments
5. **Resolve the issue** - Apply fixes and verify

## Debugging Workflow

### Step 1: Understand the Problem

Before starting to debug, clarify the following information:

**Required information to collect:**
- Complete error message content
- Exact location of the error (filename and line number)
- Reproduction steps (how to trigger the error)
- Expected behavior vs actual behavior
- Environment info (OS, versions, dependencies)

**Question template:**
```
1. What is the exact error message?
2. Which file and line does the error occur at?
3. How can this issue be reproduced? Provide detailed steps.
4. What was the expected result? What actually happened?
5. What recent changes might have introduced this issue?
```

### Step 2: Analyze Error Type

Choose a debugging strategy based on error type:

| Error Type | Characteristics | Debugging Method |
|-----------|----------------|-----------------|
| **Syntax Error** | Code cannot be parsed | Check syntax, bracket matching, quotes |
| **Import Error** | ModuleNotFoundError | Check module installation, path config |
| **Type Error** | TypeError | Check data types, type conversions |
| **Attribute Error** | AttributeError | Check if object attribute exists |
| **Key Error** | KeyError | Check if dictionary key exists |
| **Index Error** | IndexError | Check list/array index range |
| **Null Reference** | NoneType/NullPointerException | Check if variable is None |
| **Network Error** | ConnectionError/Timeout | Check network connection, URL, timeout settings |
| **Permission Error** | PermissionError | Check file permissions, user permissions |
| **Resource Error** | FileNotFoundError | Check if file path exists |

### Step 3: Locate the Problem Source

Use the following methods to locate the issue:

**1. Binary Search Method**
- Comment out half the code, check if the problem persists
- Progressively narrow the scope until the problematic code is found

**2. Log Tracing**
- Add print/logging statements at key locations
- Track variable value changes
- Confirm code execution path

**3. Breakpoint Debugging**
- Use debugger breakpoint functionality
- Step through code execution
- Inspect variable state

**4. Stack Trace Analysis**
- Find the call chain from the stack trace in the error message
- Determine the direct cause of the error
- Trace back to the root cause

### Step 4: Form and Verify Hypotheses

**Hypothesis framework:**
```
Hypothesis: [problem description] causes [error phenomenon]

Verification steps:
1. [verification method 1]
2. [verification method 2]

Expected results:
- If hypothesis is correct: [expected phenomenon]
- If hypothesis is wrong: [expected phenomenon]
```

### Step 5: Apply Fix

After fixing, verify:
1. The original error is resolved
2. No new errors have been introduced
3. Related functionality still works correctly
4. Tests added to prevent regression

## Python Common Error Patterns

### 1. Indentation Errors
Python 用缩进界定代码块；混用 tab/空格或复制粘贴错位会引发 `IndentationError` 或逻辑错位。统一用 4 空格，报错时先检查上一行是否有未闭合的括号/冒号。

### 2. Mutable Default Arguments
`def f(x, acc=[])` 的默认列表在多次调用间共享，上次调用的残留会带进下次。改为默认 `None` 并在函数体内 `acc = [] if acc is None else acc`。

### 3. Closure Issues in Loops
`funcs.append(lambda: i)` 捕获的是变量 `i` 本身而非当时的值，循环结束后所有 lambda 都拿到最后的 `i`。用默认参数固化：`lambda i=i: i`。

### 4. Modifying a List While Iterating
遍历中 `remove`/`append` 会跳元素甚至死循环。改为遍历副本 `for x in list(items)`，或用列表推导重建集合。

### 5. Using `is` for String Comparison
`is` 比较对象身份，值比较用 `==`。小整数/驻留字符串的 `is` 返回 True 只是 CPython 实现细节，不可依赖。

### 6. Forgetting to Call `super().__init__()`
子类 `__init__` 覆盖父类且未调 `super().__init__(...)` 时，父类属性未初始化，后续访问报 `AttributeError`。多继承按 MRO 逐层传递参数。

## JavaScript/TypeScript Common Error Patterns

### 1. `this` Binding Issues
回调与普通函数里的 `this` 不再指向实例。用箭头函数、`.bind(this)` 或类字段写法 `handleClick = () => {}` 固定 `this`。

### 2. Async Error Handling
`async` 函数内抛错会变成 rejected promise；漏 `await` 会丢失异常。`try/catch` 包住每个 `await`，并行场景用 `Promise.all`（fail-fast）或 `allSettled`（收集全部结果）。

### 3. Object Reference Comparison
`{} === {}` 为 `false`——比较的是引用。比较内容用深比较（如 `JSON.stringify` 简单场景或 lodash `isEqual`）；另注意 `NaN !== NaN`。

## Bash/Zsh Common Error Patterns

### 1. Spacing Issues

```bash
# ❌ No spaces allowed in assignment
name = "John"  # Error: tries to run 'name' command

# ✅ Correct assignment
name="John"

# ❌ Missing spaces in conditional test
if[$name -eq 1]; then  # Error

# ✅ Correct
if [ $name -eq 1 ]; then
```

### 2. Quoting Issues

```bash
# ❌ Variables not expanded inside single quotes
echo 'The value is $var'  # Output: The value is $var

# ✅ Use double quotes
echo "The value is $var"  # Output: The value is actual_value

# ❌ Using backticks for command substitution (confusing)
result=`command`

# ✅ Use $()
result=$(command)
```

### 3. Unquoted Variables

```bash
# ❌ Unquoted variable, empty value causes errors
rm -rf $dir/*  # If dir is empty, deletes all files in current directory

# ✅ Always quote variables
[ -n "$dir" ] && rm -rf "$dir"/*

# Or use set -u to prevent undefined variables
set -u  # or set -o nounset
```

### 4. Variable Scope in Loops

```bash
# ❌ Pipe creates subshell, outer variable unchanged
cat file.txt | while read line; do
    count=$((count + 1))  # Outer count won't change
done
echo "Total: $count"  # Outputs 0

# ✅ Use process substitution or redirection
while read line; do
    count=$((count + 1))
done < file.txt
echo "Total: $count"  # Correct output
```

### 5. Array Operations

```bash
# ❌ Incorrect array access
arr=(1 2 3)
echo $arr[1]  # Outputs 1[1]

# ✅ Correct array access
echo ${arr[1]}  # Outputs 2
echo ${arr[@]}  # Outputs all elements
echo ${#arr[@]} # Outputs array length
```

### 6. String Comparison

```bash
# ✅ Use `=` inside POSIX `[` tests and `==` inside Bash `[[ ]]` tests
if [ "$name" = "John" ]; then
if [[ "$name" == "John" ]]; then

# ❌ Using -eq for numeric comparison instead of =
if [ $age = 18 ]; then  # Wrong

# ✅ Use arithmetic operators for numeric comparison
if [ $age -eq 18 ]; then
if (( age == 18 )); then
```

### 7. Command Failure Continues Execution

```bash
# ❌ Execution continues after command failure
cd /nonexistent
rm file.txt  # Deletes file.txt in current directory

# ✅ Use set -e to exit on error
set -e  # or set -o errexit
cd /nonexistent  # Script exits here
rm file.txt

# Or check if command succeeded
cd /nonexistent || exit 1
```

## Common Debugging Commands

### Python pdb Debugger
```bash
python -m pdb script.py
pytest -x -vv tests/test_target.py
```

### Node.js Inspector
```bash
node --inspect-brk app.js
node --trace-warnings app.js
```

### Git Bisect
```bash
git bisect start
git bisect bad
git bisect good <known-good-commit>
```

### Bash Debugging

```bash
# Run script in debug mode
bash -x script.sh  # Print each command
bash -v script.sh  # Print command source
bash -n script.sh  # Syntax check, no execution

# Enable debugging within a script
set -x  # Enable command tracing
set -v  # Enable verbose mode
set -e  # Exit on error
set -u  # Error on undefined variables
set -o pipefail  # Fail if any command in pipe fails
```

## Preventive Debugging

### 1. Use Type Checking
用 mypy/pyright（Python）或 TypeScript strict 模式在运行前拦截类型错误，把一整类运行时异常提前到静态检查阶段。

### 2. Input Validation
在边界处（入口函数、公共 API、外部输入）校验参数类型与取值范围，fail fast 并给出明确报错，别让坏数据流入深层逻辑。

### 3. Defensive Programming
对可能失败的外部调用（文件、网络、数据库）做显式错误处理与兜底；避免裸 `except:` 吞掉异常掩盖真实问题。

### 4. Logging
结构化日志带上关键上下文（请求 ID、关键变量、耗时），级别分明（debug/info/warning/error）；关键路径预留 debug 钩子，问题复现时能直接回放现场。

## Debugging Checklist

### Before Starting
- [ ] Obtain the complete error message
- [ ] Record the stack trace of the error
- [ ] Confirm reproduction steps
- [ ] Understand expected behavior

### During Debugging
- [ ] Check recent code changes
- [ ] Use binary search to locate the issue
- [ ] Add logs to trace variables
- [ ] Verify hypotheses

### After Resolution
- [ ] Confirm the original error is fixed
- [ ] Test related functionality
- [ ] Add tests to prevent regression
- [ ] Document the problem and solution

## Additional Resources

> ⚠️ 以下参考文件与示例**未随仓集成**（缺口已登记于本技能 `ASSET-GAP.md`）。当前以正文的错误模式表、调试命令与检查清单为准执行；下列文件仅供追踪补齐进度，勿直接按路径读取。

### Reference Files

For detailed debugging techniques and patterns:
- **`references/python-errors.md`** - Python error details *(未随仓)*
- **`references/javascript-errors.md`** - JavaScript/TypeScript error details *(未随仓)*
- **`references/shell-errors.md`** - Bash/Zsh script error details *(未随仓)*
- **`references/debugging-tools.md`** - Debugging tools usage guide *(未随仓)*
- **`references/common-patterns.md`** - Common error patterns *(未随仓)*

### Example Files

Working debugging examples:
- **`examples/debugging-workflow.py`** - Complete debugging workflow example *(未随仓)*
- **`examples/error-handling-patterns.py`** - Error handling patterns *(未随仓)*
- **`examples/debugging-workflow.sh`** - Shell script debugging example *(未随仓)*
