# PaperSpine5 shared host runtime

`paperspine5_runtime.py` is the only host execution bridge. It imports the canonical coordinator from
`03_联合开发/src`, exposes it through MCP stdio, and also accepts the frozen HostBridge JSON envelope.

The runtime never contains a second copy of the paper or figure engines. Installed local adapters use
`PAPERSPINE5_PROJECT_ROOT` or `config/local-project.json` to find this repository.

Quick checks:

```powershell
python 06_插件化/runtime/paperspine5_runtime.py health
python 06_插件化/runtime/paperspine5_runtime.py bridge < request.json
```
