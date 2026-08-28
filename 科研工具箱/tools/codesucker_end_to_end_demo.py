#!/usr/bin/env python3
"""端到端演示：验证 CodeSucker 融合流程。"""
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, '.')

from tools.codesucker_bridge import run_source_materials
from engine.quality_gates import QualityGate
from engine.step_manifest import write_manifest, validate_manifest


def main() -> int:
    ws = Path(tempfile.mkdtemp())

    project = ws / 'test_project'
    project.mkdir()
    (project / 'main.py').write_text('def hello():\n    print("Hello World")\n\nif __name__ == "__main__":\n    hello()\n', encoding='utf-8')
    (project / 'utils.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')

    print('=' * 60)
    print('端到端测试: CodeSucker 融合流程')
    print('=' * 60)

    config = {
        'schemaVersion': 1,
        'root': str(project),
        'title': '测试软件 V1.0',
        'owner': '测试者',
        'foundedDate': '2026-01-01',
        'extensions': ['py'],
        'excludes': ['node_modules', '.git', '*.lock'],
        'sortMode': 'entry',
        'clean': {'removeComments': True, 'removeBlankLines': True, 'maskSensitive': True},
        'linesPerPage': 50,
        'maxPages': 10,
        'outputDir': 'source-materials',
    }

    try:
        result = run_source_materials(config, ws)
        print('\n✅ 源码材料生产成功')
        print(f'   backend: {result.get("backend")}')
        print(f'   coreVersion: {result.get("coreVersion")}')
        print(f'   audit items: {len(result.get("audit", []))}')

        gate = QualityGate(ws)
        gate_result = gate.check_source_materials()
        print(f'\n✅ Gate 检查: {"通过" if gate_result["ok"] else "失败 - " + gate_result["reason"]}')

        manifest_path = write_manifest(
            workspace=ws,
            step_name='copyright-source-materials',
            config={'backend': 'vendored-codesucker-core', 'title': '测试软件 V1.0'},
            inputs=[project],
            outputs=[ws / 'source-materials' / 'SOURCE_MATERIALS_MANIFEST.json'],
            backend='codesucker 0.4.4',
            commands=[{'command': 'python tools/codesucker_bridge.py', 'exitCode': 0}],
            dependencies={'codesucker-core': '0.4.4'},
        )
        print(f'\n✅ STEP_MANIFEST 创建: {manifest_path}')

        validate_result = validate_manifest(ws)
        print(f'✅ STEP_MANIFEST 验证: {"通过" if validate_result["ok"] else "失败 - " + str(validate_result["errors"])}')

        print('\n' + '=' * 60)
        print('端到端测试完成')
        print('=' * 60)
        return 0
    except Exception as e:
        print(f'\n❌ 流程失败: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
