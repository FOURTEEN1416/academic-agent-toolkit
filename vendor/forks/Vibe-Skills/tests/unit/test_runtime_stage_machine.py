from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = ROOT / 'packages' / 'contracts' / 'src'
RUNTIME_SRC = ROOT / 'packages' / 'runtime-core' / 'src'
for src in (CONTRACTS_SRC, RUNTIME_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

import vgo_runtime.governance as governance_module
import vgo_runtime.stage_machine as stage_machine_module
from vgo_runtime.kernel.planner import (
    RuntimeGovernanceProfile,
    RuntimeStageMachine as KernelRuntimeStageMachine,
    normalize_runtime_mode as kernel_normalize_runtime_mode,
)
from vgo_runtime.governance import normalize_runtime_mode
from vgo_runtime.stage_machine import RuntimeStageMachine


EXPECTED_STAGES = [
    'skeleton_check',
    'deep_interview',
    'requirement_doc',
    'xl_plan',
    'plan_execute',
    'phase_cleanup',
]


def test_stage_machine_and_governance_modules_delegate_to_kernel() -> None:
    assert stage_machine_module.RuntimeStageMachine is KernelRuntimeStageMachine
    assert governance_module.RuntimeGovernanceProfile is RuntimeGovernanceProfile
    assert governance_module.normalize_runtime_mode is kernel_normalize_runtime_mode


def test_runtime_stage_machine_order_is_fixed() -> None:
    machine = RuntimeStageMachine()
    assert list(machine.stages) == EXPECTED_STAGES


def test_runtime_stage_machine_rejects_unknown_stage() -> None:
    machine = RuntimeStageMachine()
    try:
        machine.index_of('unknown')
    except ValueError:
        assert True
    else:
        raise AssertionError('expected stage validation failure')


def test_runtime_stage_machine_none_stop_runs_to_terminal_stage() -> None:
    machine = RuntimeStageMachine()
    assert machine.iter_between('requirement_doc', None) == (
        'requirement_doc',
        'xl_plan',
        'plan_execute',
        'phase_cleanup',
    )


def test_runtime_stage_machine_rejects_empty_stop_stage() -> None:
    machine = RuntimeStageMachine()
    try:
        machine.iter_between('skeleton_check', '')
    except ValueError:
        assert True
    else:
        raise AssertionError('expected empty stop stage validation failure')


def test_governance_mode_accepts_only_interactive_governed() -> None:
    assert normalize_runtime_mode('interactive_governed') == 'interactive_governed'


def test_stage_machine_module_is_compatibility_surface_only() -> None:
    text = Path("packages/runtime-core/src/vgo_runtime/stage_machine.py").read_text(encoding="utf-8")
    assert "unknown governed runtime stage" not in text
