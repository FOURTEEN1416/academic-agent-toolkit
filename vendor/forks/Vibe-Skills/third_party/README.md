# Third-Party Boundary

`third_party/` 在 canonical repo 中承担的是 **合规与许可证边界**，不是工作区级 upstream mirror 集合。

## What Lives Here

- `licenses/`：第三方许可证文本；
- `../THIRD_PARTY_LICENSES.md`：聚合清单；
- `../NOTICE`：notice / attribution 入口。

## What Does Not Belong Here

- 活跃开发中的 upstream clone；
- operator-local scratch / backups；
- workspace 级 research mirror 或临时 vendor 快照。
- repo-local retained upstream assets that need `ORIGIN.md` and tiered distribution governance。

## Rule

- canonical repo 的 `third_party/` 只保存 **compliance artifacts**。
- 如果外层工作区还维护 upstream mirror，应在工作区级治理里单独管理，不要把它们塞进这个 canonical repo。
- 若未来需要 repo-local retention，请改走 `vendor/**`，并补 `ORIGIN.md`、`THIRD_PARTY_LICENSES.md` / `NOTICE`、以及对应 provenance/distribution gates。
