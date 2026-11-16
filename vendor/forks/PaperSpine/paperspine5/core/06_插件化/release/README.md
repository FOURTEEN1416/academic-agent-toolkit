## 0.4.0-alpha.2 invocation update patch

The existing protocol-v1 bootstrap now supports `check` and `auto --yes`.
`check` reads channel metadata and compares the installed build/archive identity;
it does not download a suite. `auto` returns `up_to_date` or commits the verified
platform bundle. Channel `bundles` maps Windows x64, Linux glibc x86_64, macOS
arm64 and macOS x86_64; historical `bundle` remains supported. The candidate's
bootstrap, settings and Skill switch in one transaction and roll back together.
The generated Skill helper `scripts/paperspine_stable_update.py` is a byte-for-byte
projection of `stable_updater.py`, not another updater implementation.

The installed `scripts/paperspine_update.py --preflight --yes` is the normal host
invocation hook. It respects explicit opt-out and preserves old interval-based
`--auto`. Only metadata-network failure permits continuing the current install;
installation failure is reported. Old protocol-v1 apply can install the candidate;
the new preflight then refreshes an old external bootstrap using the verified
installed archive. Use a platform-specific legacy channel for an old POSIX updater.
The suite upgrade does not itself wake a stopped host or replace a running Web
process. Restart the saved profile at a safe boundary and retain its task data.

## DSH native bundle (2026-09-19 local candidate)

The existing builder now accepts `build --dsh-output <dsh.zip>`; the portable
builder accepts the same option. Both reuse the verified suite and the sole
adapter source at `../dsh/paperspine5`. To project an existing current suite:

```text
python release_cli.py build-dsh --bundle <suite.zip> --output <dsh.zip>
```

The result includes bundled Python, shared Web/core and the canonical paper-spine
Skill. Configure only the outer DSH adapter during installation; the suite stays
unchanged and verifiable. See [DSH installation](../dsh/paperspine5/INSTALL.md).
Old published suites without the current adapter are rejected instead of silently
using a developer checkout. This is a local candidate, not a published upgrade.

# PaperSpine5 deterministic suite candidate

## P5 本地产品安装与启动

当前候选沿用本目录既有 exact-bundle lifecycle；没有另建安装器。候选内包含
Windows x64 的 CPython 3.12.10 嵌入式解释器、标准库 ZIP、DLL、固定 MCP v2
与 Web 依赖，不引用系统 Python、PATH 或开发用 `.venv-p2`。
`first-start` 在 profile 的持久 `data/` 中建立或迁移产品配置、任务目录和
SQLite domain-event database；安装版本位于 `.paperspine5-lifecycle/installs/`，
升级与回滚只切换版本，不移动或清空 `data/`。

```powershell
.\paperspine.cmd install --profile-root <profile> --bundle <exact.zip> --operation-id <id>
.\paperspine.cmd first-start --profile-root <profile>
.\paperspine.cmd serve --profile-root <profile> --mode business-http --port 0
.\paperspine.cmd serve --profile-root <profile> --mode mcp-stdio
.\paperspine.cmd update --profile-root <profile> --bundle <next.zip> --operation-id <id> --confirm
.\paperspine.cmd rollback --profile-root <profile> --target-build-id <previous-build> --operation-id <id>
```

`first-start` 的成功结果必须同时报告 active build、MCP v2 runtime 和持久数据位置。
先用 Windows 解压 exact ZIP，在解压目录使用 `paperspine.cmd`。安装完成后可使用
profile 的 `.paperspine5-lifecycle/installs/<build>/paperspine.cmd`；全部路径由 launcher
自身位置和显式 profile 定位，工作目录可以在项目之外。用户无需安装 Python。
关闭运行中的 MCP/REST 后再升级或回滚。

安装和升级先对目标版本执行自带 Python 的真实 MCP initialize/list-tools 和 REST
首页就绪探针，使用临时数据副本验证配置迁移；成功后才原子替换 active state。
回滚也先检查目标可启动。`after_probe` 安全故障注入发生在指针切换前，失败保留原
active state 和用户数据。没有把探针任务或临时配置写入用户 profile。

当前 P5 runtime 明确只支持 Windows x64；其他平台会给出可理解错误，
不会回退到开发环境或清空用户数据。07 的 `0.2.1-rc` installer 是历史公开 RC，
不是当前 P5 exact-bundle 权威，也不得用来覆盖当前 profile。

`runtime_vendor/windows-py312/` 是可再生第三方字节树，不是逐文件产品能力。
解释器来源/哈希、SDK 来源 commit 和依赖版本位于 `requirements.lock.json`。
开发者可用 `prepare_runtime_vendor.py --interpreter-zip <locked.zip> --wheelhouse <wheels>
--destination <new-directory>` 离线生成字节树；它拒绝覆盖现有目录。wheelhouse 须含
锁定版本的全部 wheels，MCP/MCP-types wheels 从锁定的官方 SDK commit 构建。
生成后仍需构建 suite 并运行 `test_product_runtime`，不能把生成成功当作安装验收。

The Codex adapter allowlist includes `assets/composer-icon.png`, `assets/logo.png`,
`assets/logo-dark.png`, and `assets/paperspine-plugin-icon.svg`. Bundle verification
requires those files and checks that `.codex-plugin/plugin.json` binds them with
the approved `#203431` brand color. Candidate identity comes only from the external
build receipt; an enabled personal plugin is a separate installation state and is
never implied by source verification. Standalone Skill remains a separate surface.
Release candidates deliberately contain no `skills/*/SKILL.md` below the plugin
root: the plugin is an internal MCP dispatch backend, while
`standalone/paper-spine/SKILL.md` is the only user-facing Skill projection.

本目录实现 W7a 与可在本地验收的 W7b 生命周期核心。它构建一个精确、
自包含、可哈希验证的 PaperSpine5 candidate。`lifecycle.py` 只操作调用者显式
给出的测试 profile root；面向真实安装面的 `user_update.py` 则只对已解析的单一
personal marketplace 插件执行有 JSON 收据的 `codex plugin list/remove/add`，
不会猜测或扫描其他用户安装。

## 构建合同

`suite_release.py` 只摄取 `FILE_RULES` / `TREE_RULES` 明确列出的源。源根、
allowlist 文件或目录中出现 symlink/junction/reparse point 会被拒绝；Git、
测试、local-project 指针、开发绝对路径、重复 Skill、cache、pyc 和临时文件
不会进入包。ZIP 使用固定顺序、时间戳、mode 和压缩参数，同一源连续构建的
archive bytes 与 SHA-256 必须一致。
`01_PaperSpine4/src/skill/references/figure-reference-mapping.md` 是既有 Skill
目录 allowlist 内的原生方法资源；不再打包或要求历史跨项目对照表。
候选保留同一相对路径和源码原字节，source/build identity、
Product Kernel/Runner component hash、manifest content index 与 build receipt
都绑定它的 SHA-256。strict `verify-bundle`、提取后复验和 install 预检把该路径
视为 self-contained 必需项；缺失或相对 manifest 的任何字节/长度变化都会在
安装状态写入前 fail closed。发布层不复制另一套方法、不生成或改写方法内容。
时间边界只存在于 updater 对已安装历史前态的识别：外部
`installed-suite.json` 已绑定 build/content-index 的旧 managed suite，若其自身
不可变 manifest 从未索引该新资源，可按该历史 manifest 的完整文件集、逐文件
hash/size 与 content-index 验真并升级，但 `candidate_verified=false`。这不会让旧包
重新成为当前候选；公开 `verify-bundle`、新候选放置与升级后的 suite 仍强制包含
原生方法文件。历史 suite 的任一已索引文件缺失/变化、manifest/index 漂移、外来文件或
不受控 residue 仍照常阻断，updater 不补文件、不改 pointer/state，也不关闭字节检查。
PaperSpine 方法正文和合同可以作为组件资源进入候选包，但其源 `SKILL.md` 会被
明确排除；legacy `02_paperFig_skill` 整棵目录不再摄取。候选包因此不会把组件
真源或 legacy figure Skill 变成新的递归发现入口，FigMirror 只保留执行引擎源码。
发布 gate 会扫描所有 allowlisted 文本类型（包括 HTML/JS/CSS/TXT），
任意盘符绝对路径都会阻断构建；当前源不需要路径白名单。

唯一审计例外不是路径前缀白名单：只对候选内精确文件
`03_联合开发/src/paperspine_figure_integration/canonical_artifacts.py` 的两条完整、
独占一行的 `Path(r"C:\Program Files...WINWORD.EXE")` / x86 表达式，在执行原
absolute-path scanners 前剥离。它们是 Windows OS 安装位置的确定性 runtime
fallback，实际选择仍由 `is_file` 及 canonical Word SurfaceReceipt 中 resolved
executable path/hash/version 绑定。同字面量出现在其他文件、添加 suffix/parent
traversal、重复表达式，或任何 `C:\Users`、其他盘符/项目路径，仍会 fail closed。

包根的 `suite-manifest.json` 是唯一 suite 身份，包含 product/channel/build、
组件版本与哈希、state writer/reader、workflow/API、候选测试证据和 claim
ceiling。当前源合同声明 ProductRunner `0.2.0`、runtime `0.2.0-dev`、
HostBridge `0.4.0` 与 J0–J11 implemented slice。J4–J11 只固定通用协作元流程：
运行时研究 Agent 学习领域/小方向/venue/track，回答的
`input_artifacts` 是实际 JSON 证据载荷，不是客户自报 trusted map；已登记
同 ID 内容变化会失效下游并回到 J4。上限仍为
`internal-candidate / P0 BLOCKED`：W8 成熟度、直接交付和外部提交均未被授权。

```powershell
python .\06_插件化\release\release_cli.py build `
  --source-root . `
  --output .\06_插件化\release\out\paperspine5-candidate.zip
python .\06_插件化\release\release_cli.py verify-bundle `
  --bundle .\06_插件化\release\out\paperspine5-candidate.zip
```

## 用户更新：插件与纯 Skill 完全分开

`user_update.py` 是面向真实用户安装面的更新权威，与下文只操作测试
`profile-root` 的 lifecycle 分开。它接受本地 exact candidate ZIP，或绑定单一
`install_kind=plugin|skill` 的 `paperspine5.update-feed/1.0` JSON。远程 feed 和
artifact 只接受 HTTPS；下载后必须与 feed 中的字节数、SHA-256、build ID 和 bundle
内 manifest 完全一致。代码中不存在 `auto`：plugin 与 Skill 使用不同命令、control
root、state、receipt、history、staging、backup 和 rollback。任何一次操作最多修改
一个安装面，不能同时更新或回滚两者。

`install_kind=skill` 的唯一安装目标与候选投影均为 canonical
`paper-spine`：候选路径是 `standalone/paper-spine`，frontmatter 保持
`name: paper-spine`。updater 写入的 `references/installed-suite.json` 把它绑定到
同一候选的 verified build ID/content index；canonical Web launcher 会校验 pointer
与 managed suite manifest 后才启动。`paperspine5-workspace` 只保留不含
`SKILL.md` 的包内兼容支持文件，不能被递归发现为 Skill，也不是 Skill updater 的
目标或普通用户前门。bundle verifier 会对候选内全部 `SKILL.md` 做全树扫描，唯一
允许项是根级 canonical `standalone/paper-spine/SKILL.md`；legacy、workspace、
备份、`.test-temp`、probe 与 system 入口都会被排除或阻断。

每次真实 plugin/Skill upgrade 在替换安装面之前，还会调用候选包内的 canonical
`skill_discovery_migration.py`：只扫描用户 home 下 `.codex/skills` 与
`.agents/skills`，把同级 legacy/备份入口及 canonical 内部嵌套入口原字节迁到
`~/.paperspine5/skill-discovery-archive`。逐文件 SHA-256 receipt 链接写入 upgrade
receipt/state；升级任一步骤失败会自动恢复，用户显式执行 upgrade rollback 时会把
旧安装与 discovery 历史一起恢复。该事务不删除历史，也不修改 legacy `paperFig`。
历史版本曾把 Skill backup 写到 discovery root 内的
`.paperspine5-update-backups`；迁移器现在把该目录与顶层
`paperspine5-workspace` 一并按原字节归档。新事务的 stage、failure quarantine 和
backup 全部位于各 install-kind 的 `control_root` 内，绝不再在 Skill discovery root
中制造临时或历史 `SKILL.md`。

执行真实 profile 事务前可运行候选内同一脚本的 `preview` 子命令。它只读解析精确
`operation_id`、discovery roots 与 archive root，返回
`paperspine.skill-discovery-migration-preview/1.0`：每个拟迁移源/目标、逐文件
SHA-256、tree hash、file count 和总字节数；`mutation_performed` 恒为 `false`。

```powershell
# 发布方：同一候选也必须生成两个安装类型绑定的更新索引
python .\06_插件化\release\release_cli.py make-update-feed `
  --bundle .\06_插件化\release\candidate\paperspine5-suite-0.4.0-alpha.1-dev.zip `
  --install-kind plugin `
  --output .\06_插件化\release\candidate\paperspine5-plugin-update-feed.json
python .\06_插件化\release\release_cli.py make-update-feed `
  --bundle .\06_插件化\release\candidate\paperspine5-suite-0.4.0-alpha.1-dev.zip `
  --install-kind skill `
  --output .\06_插件化\release\candidate\paperspine5-skill-update-feed.json

# 插件：只检查、升级和回滚 personal marketplace 插件
python .\06_插件化\release\release_cli.py plugin-update-check `
  --source <candidate.zip-or-plugin-feed>
python .\06_插件化\release\release_cli.py plugin-upgrade `
  --source <candidate.zip-or-plugin-feed> --operation-id <unique-id> --confirm
python .\06_插件化\release\release_cli.py plugin-upgrade-rollback `
  --operation-id <unique-id> --confirm

# 纯 Skill：只检查、升级和回滚 standalone Skill
python .\06_插件化\release\release_cli.py skill-update-check `
  --source <candidate.zip-or-skill-feed>
python .\06_插件化\release\release_cli.py skill-upgrade `
  --source <candidate.zip-or-skill-feed> --operation-id <unique-id> --confirm
python .\06_插件化\release\release_cli.py skill-upgrade-rollback `
  --operation-id <unique-id> --confirm
```

插件目标从已登记的 personal marketplace 条目解析，更新器不手改
`marketplace.json`。权威 `.mcp.json`、PowerShell/Shell Web 前门用 Python `-B`
在解释器启动时禁止 bytecode 写入；MCP adapter、Product Web launcher、runtime、
legacy 恢复与兼容 bridge 在任何 product-core import 前再设置
`sys.dont_write_bytecode` 和继承环境 `PYTHONDONTWRITEBYTECODE=1`。Product Web 与
Agent 子进程显式保留同一环境。严格 bundle verifier 同时检查这些源码锚点；安装包
回归会实际启动 Product Web，并断言启动前后 suite 的完整路径集合、每个文件字节、
manifest/content-index 验证结果完全相同，且不存在 `__pycache__`、`.pyc` 或 `.pyo`。
插件 typed check 会把
active source、CLI source/version/enabled 状态和 enabled cache 绑定为一条 prestate：
cache 必须与 indexed source 逐字节一致；唯一可继续的差异是 cache 内普通目录下、
由当前解释器从对应 indexed `.py` 确定性编译得到的 `__pycache__/*.pyc`。pyc 的
magic/cache tag、timestamp 或 source-hash header、source size、source path 和 optimize
模式必须精确；marshal payload 必须恰好解出一个 `CodeType` 且无 trailing bytes，再与
exact source fresh compile 的递归 CodeType 语义指纹逐字段一致。指纹覆盖 bytecode、
constants/nested code、names/variables、filename/name/qualname、flags/stack/arguments、
line/exception tables 和 closure variables；float/complex 保留 bit pattern，frozenset 仅
规范无序性，未知 constant type 直接拒绝。marshal 的跨进程引用/intern 排列不作为代码
语义身份。这类 residue
明确回报 `verified-with-runtime-residue`，不会冒充 strict `verified`。cache 缺失、
indexed 文件缺失/变更、orphan/伪造 pyc、其它 extra、symlink/junction/reparse 或路径
逃逸全部 typed BLOCKED，foreign bytes 不会被移动或删除。

插件事务固定执行：只读 `plugin list --json` 核对旧 source/cache identity → 若仅有
受控 runtime pyc，则先在 plugin control root 下生成 owner/journal，把每个文件按
path/size/SHA/source-SHA 复制归档并隔离，随后重新证明 strict cache →
`plugin remove --json` 并再次 list 确认已停用 → 原子放置 candidate source →
`plugin add --json` → list 与 exact cache 的 manifest/build/content-index 三重核验。
cache reconciliation receipt 与 payload 在 commit 后保留作审计；升级失败和显式
rollback 会从该不可变归档恢复旧 activation 的原 runtime residue，且不会覆盖新生
或 foreign bytes。每个 command、source placement 和
恢复动作都立即写入 `transactions/<operation-id>.json` phase journal；只有所有激活
gate 通过后才写 update state。候选 add 失败时，更新器先确认 candidate 是否实际
存在，再恢复旧 source 并重新 add/核验旧 build，避免对“未安装”对象盲目 remove，
也避免旧 build 尚激活时直接 add 新 build。

仅对 state、CLI、build/content-index、source/cache 完整绑定的已安装历史 prestate，
事务内部可派生 `recorded-legacy-installed` 验证模式。它只允许已登记的单一
workspace discovery violation，且 cache 必须与该 source 逐字节一致，或仅叠加上述已绑定
runtime pyc。模式不可由调用方声明，必须从已记录 prestate descriptor 重开验证；
升级预检、自动补偿与显式 rollback 都使用同一 descriptor/receipt 链。恢复后会再核对
原 source tree、CLI build/source/enabled 状态、cache 及 runtime residue 原字节。该历史
prestate 始终是 `candidate_verified=false` / `candidate_eligible=false`；same-build 也不会
被当成 noop。下载、解包、放置、candidate 激活后与公开 `verify-bundle` 仍只接受严格
 canonical 候选，不会因历史兼容而放宽。

早期 `sync_local_installs.py` 生成的 standalone `paper-spine` 是没有
`installed-suite.json` 的自包含 `_paperspine5` 投影。Skill updater 只在以下条件全部
成立时把它识别为可备份、但不可冒充候选的历史前态：embedded identity 合同和固定字段
正确；排除 identity 文件后重算的逐文件 compact content index 与文件数完全匹配；外层
`agents/`、`references/`、`scripts/` 的每个字节均与 `_paperspine5` 内对应权威副本一致；
frontmatter 仍为 `name: paper-spine`；且没有 link/junction 或 foreign top-level entry。
这种前态没有 suite build ID，始终标记为
`direct-embedded-prestate-recognized`、`candidate_verified=false`、
`candidate_eligible=false`。真实升级把整树身份写进 receipt 并原字节备份，再安装严格候选；
自动补偿与显式 rollback 都按同一整树哈希恢复。任何索引、镜像或结构漂移继续返回
`CURRENT_PRESTATE_UNRECOGNIZED`，更新器不会手工补写指针或把 state 中的旧 build 强套给
当前目录。

带 `installed-suite.json` 的 standalone `paper-spine` 使用另一条公开、typed 的
`managed-suite` 前态合同。更新器从 pointer 精确绑定 build/content-index，只把 manifest
索引内的 `.py` 当作 bytecode source；额外文件必须是对应普通目录下、与当前 CPython
cache tag、header、完整 marshal `CodeType` 语义和 source bytes 精确绑定的
`__pycache__/*.pyc`。`skill-update-check` 对这种前态返回
`SKILL_MANAGED_SUITE_RUNTIME_RESIDUE` warning、`candidate_eligible=true`，并显式报告
`file_count`、`total_bytes` 和排序路径的 SHA-256 digest。orphan、foreign、tamper、未知
extra、indexed drift 和 reparse/containment 异常仍 fail closed。旧 build 若早于当前
no-bytecode markers，会如实记录 `candidate_verified=false`，但可作为已验证、可安全替换
和可精确回滚的 predecessor；公开 candidate `verify-bundle` 的 marker gate 不放宽。

Skill upgrade 在放置 candidate projection 前，将上述 residue 逐文件复制进
`skill-managed-suite-reconciliations/<operation-id>/payload`，核对 path/size/SHA/source-SHA，
移出旧 suite 并写 self-hash/receipt-hash 绑定的 reconciliation receipt。任一后续失败会先
恢复旧 projection，再从归档恢复每个原字节；显式 rollback 同样恢复 predecessor 与其
原 residue，随后重新执行 typed prestate 验证。成功的新 managed install 仍必须通过严格
bundle verifier 且 residue 为零。receipt、restore receipt 与 prestate descriptor 分别由
`skill-managed-suite-reconciliation-receipt.schema.json`、
`skill-managed-suite-reconciliation-restore-receipt.schema.json` 和
`skill-managed-suite-prestate-validation.schema.json` 约束；Plugin 原合同与目录保持不变。

外层 receipt 把请求结果和补偿结果分开：`requested_target_applied=true` 只表示请求的
candidate/previous build 最终已生效；`compensation_performed` 与
`current_installation_restored` 单独说明失败后的安全恢复。对于显式 rollback，只有
目标 build 已生效才允许 `status=committed` 和 `rollback_performed=true`；若请求失败
但已补偿回当前 build，则返回 `status=rollback_failed`、
`requested_target_applied=false`、`rollback_performed=false`，并明确是否可用新
operation ID 重试。状态消费者不需要从 phase 内部推断实际生效 build。

纯 Skill 目标按 Codex 官方 discovery 位置发现，
exact suite 放入 `~/.paperspine5/skill-updates/installs/<build-id>/`，Skill 内只写一个
受管的 `installed-suite.json` 指针。插件与 Skill 分别使用
`paperspine5.plugin-update-*` 和 `paperspine5.skill-update-*` 收据/状态合同。
升级成功后必须新建 Codex task；若 standalone Skill 没有自动出现，再重启 Codex。
更新器不改变 W8、P0、论文质量或外部动作授权。

## 显式 profile 生命周期

所有 mutation 都先验证包与 schema 兼容区间、记录 pre-snapshot、取得单 profile
事务锁，再激活唯一 discovery object。install/update 会 staging + 原子 placement；
uninstall 先把 installs/staging 原子移动到同 profile quarantine，失败恢复原字节。
如果逻辑卸载完成但 quarantine 清理失败，receipt 会返回
`committed_with_residue`，不会伪报 rollback。

```powershell
python .\06_插件化\release\release_cli.py doctor `
  --profile-root <explicit-workspace-local-profile> `
  --bundle <candidate.zip>
python .\06_插件化\release\release_cli.py install `
  --profile-root <explicit-workspace-local-profile> `
  --bundle <candidate.zip> --operation-id <unique-id>
python .\06_插件化\release\release_cli.py update `
  --profile-root <explicit-workspace-local-profile> `
  --bundle <next-candidate.zip> --operation-id <unique-id> --confirm
python .\06_插件化\release\release_cli.py reload `
  --profile-root <explicit-workspace-local-profile> --operation-id <unique-id>
python .\06_插件化\release\release_cli.py rollback `
  --profile-root <explicit-workspace-local-profile> `
  --target-build-id <build-id> --operation-id <unique-id>
python .\06_插件化\release\release_cli.py uninstall `
  --profile-root <explicit-workspace-local-profile> --operation-id <unique-id>
```

reload 当前只验证并确认 profile-local marker，receipt 明确回报
`service_drain_verified=false`；真实宿主 drain/reload 仍需在实际 Codex 安装时
单独验收。uninstall 只支持 `retain_data=true`，且不删除无关 discovery 文件。

## Doctor

doctor 是只读的，阻断 double-enabled、wrong suite object/updater target、安装
字节篡改、staging/quarantine/transaction/install residue、候选包无效和 schema
不兼容。它投影 manifest 中的 suite/components/state/workflow/readers/API 与
claim ceiling，不自己扩大成熟度或 readiness。

## 验收

```powershell
python -m unittest discover -s .\06_插件化\release -p "test_release.py" -v
```

测试在 `06_插件化/release/.release-test-<uuid>` 创建全新 profile，覆盖同源双构建、
installed bundle 离开开发树执行 health、30-tool discovery、create-task 与
ProductRunner bootstrap、install→update→reload→
rollback→uninstall、故障自动回滚、卸载字节恢复、typed residue、tamper、兼容性、
idempotency 和 JSON Schema；另以隔离的 synthetic home 验证真实 marketplace
解析、plugin 与 Skill 独立升级/独立回滚/互不改写、activation failure 原字节回滚、
跨类型 feed 拒绝、feed hash mismatch fail-closed 与三份更新 schema。测试退出后删除该目录；它不触碰
用户目录。

## 当前 recovery candidate（2026-08-29，尚未执行真实 profile）

- 文件：`90_临时工作/TimeB闭环修复/candidate/paperspine5-ps-gap-001-activation-v2.zip`
- build ID：`w7a-73c8d1373a628b30fa4c`
- archive SHA-256：`fa674eb2f320156a6b869b6bb2f8be587bfce7cccd057086ea0bee1c3451bb23`
- manifest SHA-256：`bcfdb657f05222c38951bb2d995a3751216d862acb7fdbe9266ef1ce43dba886`
- content index SHA-256：`7c1c546a21c0f261bc3df2f8428054db06f8d885cdaf67fd15ec3814117e2060`
- indexed files：429；plugin `discovered_skills=[]`

`verify-bundle` 为 PASS；release component 全量 **24/24 OK**，其中真实 `codex
plugin` 在 disposable `HOME/CODEX_HOME` 的旧 active + 空 cache
upgrade→rollback→upgrade 独立复跑 **1/1 OK**。首个真实 plugin transaction 的
旧实现仍封存为 `rollback_failed`，当前 profile 未因本候选再写入；精确残留和新
operation 计划见 `90_临时工作/TimeB闭环修复/PS-GAP-001_REAL_PROFILE_RECOVERY_PLAN_V2.md`。
该证据只解除 lifecycle blocker，不替代新任务 1/0 discovery、same-suite routing 或
真实材料论文/PDF/DOCX user journey。

## 历史 candidate（2026-08-26；以下为当时记录，已被 recovery candidate 取代）

- 文件：`candidate/paperspine5-suite-0.4.0-alpha.1-dev.zip`
- build ID：`w7a-b8009c76b921b36183b9`
- archive SHA-256：`27acb85832b14d2ead92fe9efee52c7973abee87bd7f7a8f6944b751735fde8f`
- manifest SHA-256：`63c3402fe9a3c7bf6c6777c930077d06cbdbb1e639420309a217a5ec23e1eb85`
- content index SHA-256：`582f99f310422ff4efda9a8be31dd81a4a22cad81c8de6c38d10d66b87d4cdb6`
- indexed files：290
- plugin feed：`candidate/paperspine5-plugin-update-feed.json`
- Skill feed：`candidate/paperspine5-skill-update-feed.json`

两次独立构建得到相同 archive bytes/hash；`verify-bundle`、PaperSpine 319/319、
FigMirror 75/75、V5 integration 130/130 effective PASS、runtime 14/14 与 release
lifecycle/user update 17/17 通过。该候选将 plugin/standalone Skill 更新拆为
独立命令、feed、control root、state、receipt、history、backup 和 rollback；不存在
`auto` 或同时 mutation 两个安装面的路径。standalone 使用 immutable suite pointer，
且 bridge 禁止写入 bytecode，正常 health 后 exact bundle 仍可验签。同时保留验证科学身份锁、终稿尺寸独立比较、单/双栏 placement、
`main|supplementary|omit`、claim-safe disposition，以及 broad/mixed materials
的 bounded/read-only/non-authoritative Paper Map 前置 Skill 路由。该地图路由没有
新增 typed scanner、API、schema、artifact 或 readiness authority；真实 OUP
重绘和匿名盲评也只是局部图件能力证据，不把候选扩大为成熟产品或
submission-ready。该候选还新增了 provider-neutral 的 J6/J9
Evidence-Backed Prior-Art Reviewer shadow 协议；它不依赖 WisPaper 私有服务，
不把 no-hit 当成 novelty 证明，也没有新增 prior-art receipt/tool/schema/API、
J10 authority 或 readiness claim。真实 personal plugin 已通过独立 plugin updater
升级到 `w7a-b8009c76b921b36183b9`，并完成 source/cache 品牌资产哈希核对；当前 feed
对 plugin 回报无更新。standalone Skill 保持 `w7a-4db77726e2fceb9117cc`，Skill feed
独立回报有更新可用，本次没有修改它。新 Codex task 仍是插件模型级发现与界面验收的
必要条件。这不替代 W8 前瞻性成熟度证据；P0 与外部投稿仍 BLOCKED。

前一 Ridge Seal 之前的 exact candidate `w7a-4db77726e2fceb9117cc` 已以原 ZIP、
receipt 及分安装面 feed 保存在 `candidate/history/`，archive SHA-256 为
`ad57f3fed1cdd5ea632e9e0bf889e5e8f18c1c0099503faa9bfdbe9489fe4cd1`，可作为本次
plugin 安装回退和发布审计的精确来源。

修复 immutable Skill bytecode 写入前的候选 `w7a-1b7eb6c9cebbcd6db24a`
和被否决的联合更新候选 `w7a-09fc23408f7729eec78e` 均已按原字节移入
`candidate/history/`；后者仅作时间限定历史，不再是当前更新合同。

上一精确 project candidate `w7a-32017e44b37d259d201e` 已以原字节移入
`candidate/history/`，archive SHA-256 为
`265afb0ebb4dbf9a3862861f9adf1839f6eb43374eb54ad6f5092815f324dca5`。更早的
`w7a-52df78135280178291c8` 已以原字节移入
`candidate/history/`，archive SHA-256 为
`10d56c9bc0ffe4056a148f195a2620b33d90314dbf83ec486e24d1d7d1664a0d`。更早的
`w7a-879c457de7835a95b8d4` 已以原字节移入
`candidate/history/`，archive SHA-256 为
`ec8bdd76aab0ae6f97b9c82767cc7f575819402c87e4b5d4491bb7302ae34728`。更早的
`w7a-52eecb956459fe3875eb` 也已以原字节移入
`candidate/history/`，archive SHA-256 为
`04f30f7bfe0d498ee286d79cfec8f9998bdbcbe776fa8a604c0a4f51f805bea0`。更早的
`w7a-9b6ad46bf718e7271283` 也已以原字节移入
`candidate/history/`，archive SHA-256 为
`74a281a49b28b1748c40f3eab06a133ffb84a48b0e929773adea7925aad2013f`。更早的
`w7a-7c9986d877bcf06bc51e` 也以原字节保留，archive SHA-256 为
`317e5e71b52243746b22acb8af8ec131f7fe8a3ae1edf9f5ae00c13624fa2c7e`；
`w7a-8706e853818919c78aea` 也已以原字节保留，archive SHA-256 为
`08636f228df45d25583418cde736f1ccea95a21c12dc4216b0c8ef5fc9ed3f2e`；它是
2026-08-25 的历史 personal marketplace 启用 build，当前已由独立插件更新替代。更早的
`w7a-7f0958bfc8e06ba2ae06` 也继续保留在 history，archive SHA-256 为
`c3778e86364d2c9e040e49534e093dc5312ecdb485fa1b1c76dffbff515d8631`。
旧 `w7a-80e2a92918d5da2623cd` 因 HTML 中含有开发机材料路径已废弃，不得安装。

## P8 安装 Skill 入口修复（2026-09-05）

P7 ZIP 的用户帮助已使用 v1 MCP，但唯一 standalone Skill 仍指向旧阶段工具；
P8 黑盒因此停止，不能把两个任务协议混用。唯一方法源
`01_PaperSpine4/src/skill/SKILL.md` 现直接使用 v1 产品工具，按
`references/product-v1-workflow.md` 监督当前 Agent 的真实研究、用户 Web 选择、
成果导入、独立审核和下载。沿用既有源目录 allowlist，不引入第二个 Skill 真源。
`test_p8_installed_skill.py` 安装候选后比对实际 MCP tools/list 与 Skill 工具集合，
并拒绝用户入口和其直接路由文档中的旧阶段/工具指令。此检查不是论文旅程通过；
P8 仍须用新隔离任务完成真实 CARBON 下载。当前未发布、未请求 Atlas 接纳。
### Stable updater

`release/stable_updater.py` is the compatibility entrypoint for direct V1--V4
to-current upgrades. It detects the old Skill, verifies a hash-bound bundle,
keeps a transaction archive, switches only after a real launcher probe, and
retains user data. `release/stable-update.cmd` is the Windows wrapper. Future
releases keep protocol `paperspine-updater/1` and provide a version-owned
adapter, so users do not need to install intermediate versions.
