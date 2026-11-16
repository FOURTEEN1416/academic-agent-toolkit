"""Pre-activation readiness against a disposable copy, never the live profile."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.request import urlopen

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))


def probe_install(install: Path, profile: Path) -> dict:
    from product_runtime import runtime_executable
    python = runtime_executable(install)
    result = subprocess.run(
        [str(python), "-I", "-B", "-X", "utf8", str(install / "release" / "product_probe.py"), str(profile)],
        cwd=profile, env={**os.environ, "PATH": "", "PYTHONPATH": "", "PYTHONHOME": ""},
        capture_output=True, encoding="utf-8", timeout=60, check=False,
    )
    if result.returncode:
        raise RuntimeError("Installed runtime readiness failed: " + result.stderr[-3000:])
    return json.loads(result.stdout)


def application(install: Path, data: Path):
    from product_runtime import _enable_vendored_runtime, application_root
    _enable_vendored_runtime(install)
    app = application_root(install)
    sys.path.insert(0, str(app / "03_联合开发" / "src"))
    from paperspine_figure_integration.p2_facades import build_application
    return build_application(user_data_root=data / "tasks", core_root=install,
                             domain_database=data / "domain-events.sqlite3",
                             contracts_root=app / "03_联合开发" / "contracts")


async def mcp_ready(install: Path, data: Path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[
        "-I", "-B", "-X", "utf8", str(Path(__file__).resolve()), "--mcp", str(data)],
        env={**os.environ, "PATH": "", "PYTHONPATH": "", "PYTHONHOME": ""})
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            if "paperspine_open_task" not in names:
                raise RuntimeError("MCP OpenTask is unavailable")


def main():
    install = Path(__file__).resolve().parents[1]
    if sys.argv[1] == "--mcp":
        service, kernel = application(install, Path(sys.argv[2]))
        from paperspine_figure_integration.p2_facades import create_mcp_server
        try:
            create_mcp_server(service, principal_id="readiness-agent").run()
        finally:
            kernel.close()
        return
    profile = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="paperspine-readiness-") as temporary:
        data = Path(temporary) / "data"
        if (profile / "data").exists():
            shutil.copytree(profile / "data", data)
        else:
            data.mkdir()
        from product_runtime import migrate_profile
        migrate_profile(Path(temporary), install, "readiness-only")
        service, kernel = application(install, data)
        from paperspine_figure_integration.p2_facades import create_business_server
        server = create_business_server(service, principal_id="readiness-user", session_id="readiness")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=10) as response:
                if response.status != 200:
                    raise RuntimeError("Product Web is unavailable")
            asyncio.run(mcp_ready(install, data))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            kernel.close()
    print(json.dumps({"status": "READY", "rest": True, "mcp": True}))


if __name__ == "__main__":
    main()
