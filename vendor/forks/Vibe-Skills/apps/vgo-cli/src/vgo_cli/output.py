from __future__ import annotations

import json
import subprocess

from .errors import CliError
from .process import print_process_output


def parse_json_output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        print_process_output(result)
        raise CliError('core command failed')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print_process_output(result)
        raise CliError(f'Invalid JSON output from core command: {exc}') from exc


def print_json_payload(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
