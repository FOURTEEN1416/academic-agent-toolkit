import { expect, test } from "bun:test"
import path from "path"

const templatePath = path.resolve(import.meta.dir, "../../skills/biology/scanpy/assets/analysis_template.py")

test("scanpy template gates regress_out with a memory-sized worker count", async () => {
  const source = await Bun.file(templatePath).text()
  expect(source).toContain("def memory_safe_n_jobs(adata, fraction=0.5):")
  expect(source).toContain("if _n_jobs >= 1 and _dense_gb <= MAX_DENSE_GB:")
  expect(source).toContain("n_jobs=_n_jobs")
  expect(source).toContain("zero_center=_scale_zero_center")
  expect(source).not.toContain("n_jobs=-1")
})

test("scanpy memory guard is valid Python and returns zero when no worker copy fits", async () => {
  const python = Bun.which("python3") ?? Bun.which("python")
  if (!python) return

  const harness = String.raw`
import ast
import os
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text()
tree = ast.parse(source)
functions = [
    node for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name in {"_available_ram_bytes", "memory_safe_n_jobs"}
]
namespace = {"_os": os}
exec(compile(ast.Module(body=functions, type_ignores=[]), sys.argv[1], "exec"), namespace)

class Data:
    n_obs = 10_000
    n_vars = 1_000

namespace["_available_ram_bytes"] = lambda: 100 * 1024 ** 2
assert namespace["memory_safe_n_jobs"](Data()) == 0

namespace["_available_ram_bytes"] = lambda: 16 * 1024 ** 3
workers = namespace["memory_safe_n_jobs"](Data())
assert 1 <= workers <= (os.cpu_count() or 1)

regress_calls = [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "regress_out"
]
assert len(regress_calls) == 1
assert any(keyword.arg == "n_jobs" for keyword in regress_calls[0].keywords)

scale_calls = [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "scale"
]
assert len(scale_calls) == 1
assert any(keyword.arg == "zero_center" for keyword in scale_calls[0].keywords)
`
  const proc = Bun.spawnSync([python, "-c", harness, templatePath], {
    stdout: "pipe",
    stderr: "pipe",
  })

  expect(proc.exitCode, proc.stderr.toString()).toBe(0)
})
