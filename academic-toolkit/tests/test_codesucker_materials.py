import json
import hashlib

from tools.codesucker_bridge import run_source_materials
from tools.codesucker_materials import write_code_pages


def test_code_pages_are_derived_from_selection(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 55, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)
    output = workspace / "草稿" / "代码-全部.md"
    pages = write_code_pages(workspace, output, "测试软件 V1.0")
    assert pages == 2
    text = output.read_text(encoding="utf-8")
    assert "## 第1页" in text
    assert "source: main.py" in text


def test_manifest_has_output_hashes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n" * 50, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_source_materials({"root": str(project), "title": "测试软件 V1.0", "extensions": ["py"]}, workspace)
    manifest = json.loads((workspace / "source-materials" / "SOURCE_MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["outputSha256"]
    assert "source-materials/audit.json" in manifest["outputSha256"]
    audit = workspace / "source-materials" / "audit.json"
    assert manifest["outputSha256"]["source-materials/audit.json"] == hashlib.sha256(audit.read_bytes()).hexdigest()
    assert "source-materials/SOURCE_MATERIALS_MANIFEST.json" not in manifest["outputSha256"]


def test_directory_publication_retries_only_transient_windows_locks(tmp_path):
    """发布仅重试 Windows 短暂占用，不重做生成、不吞永久失败或覆盖冲突。"""
    import subprocess
    from tools.codesucker_bridge import CLI

    script = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
const { publishDirectory } = await import(process.argv[1]);
const base = process.argv[2];
const rename = fs.renameSync;
const platform = Object.getOwnPropertyDescriptor(process, 'platform');
const cases = [
  { name: 'normal', platform: 'win32', code: '', fail: 0, calls: 1, ok: true },
  { name: 'transient', platform: 'win32', code: 'EPERM', fail: 2, calls: 3, ok: true },
  { name: 'busy', platform: 'win32', code: 'EBUSY', fail: 1, calls: 2, ok: true },
  { name: 'access', platform: 'win32', code: 'EACCES', fail: 1, calls: 2, ok: true },
  { name: 'permanent', platform: 'win32', code: 'EPERM', fail: 99, calls: 6, ok: false },
  { name: 'other_error', platform: 'win32', code: 'EINVAL', fail: 99, calls: 1, ok: false },
  { name: 'non_windows', platform: 'linux', code: 'EPERM', fail: 99, calls: 1, ok: false },
  { name: 'conflict', platform: 'win32', code: 'EPERM', fail: 99, calls: 1, ok: false, conflict: true },
];
try {
  for (const test of cases) {
    Object.defineProperty(process, 'platform', { value: test.platform, configurable: true });
    const source = path.join(base, `${test.name}.tmp`);
    const target = path.join(base, test.name);
    fs.mkdirSync(source);
    fs.writeFileSync(path.join(source, 'payload.txt'), 'verified content');
    let calls = 0;
    const injected = Object.assign(new Error(test.name), { code: test.code });
    fs.renameSync = (from, to) => {
      calls += 1;
      if (calls <= test.fail) {
        if (test.conflict) {
          fs.mkdirSync(target);
          fs.writeFileSync(path.join(target, 'other.txt'), 'other writer');
        }
        throw injected;
      }
      return rename(from, to);
    };
    if (test.ok) {
      await publishDirectory(source, target);
      assert.equal(fs.readFileSync(path.join(target, 'payload.txt'), 'utf8'), 'verified content');
      assert.equal(fs.existsSync(source), false);
    } else {
      await assert.rejects(() => publishDirectory(source, target), (error) => error === injected);
      assert.equal(fs.readFileSync(path.join(source, 'payload.txt'), 'utf8'), 'verified content');
      if (test.conflict) {
        assert.equal(fs.readFileSync(path.join(target, 'other.txt'), 'utf8'), 'other writer');
      } else {
        assert.equal(fs.existsSync(target), false);
      }
    }
    assert.equal(calls, test.calls, test.name);
    fs.renameSync = rename;
  }
} finally {
  fs.renameSync = rename;
  Object.defineProperty(process, 'platform', platform);
}
console.log(JSON.stringify({ ok: true, cases: cases.length }));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, CLI.as_uri(), str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "cases": 8}
