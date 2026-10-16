# matplotlib 坑清单（实测，泛化）

> 每条都是真实返工踩出来的，按"症状 → 根因 → 解法"记。新增坑请续表。

## 渲染 / 字形

| 症状 | 根因 / 解法 |
|------|-------------|
| 图例 `set_path` 报错 | 基类 `Patch` 抽象 → 手柄用零尺寸 `Rectangle((x,y),0,0)` |
| violin 轮廓复制成黑块 | 复制 body 用 `PathCollection([pc.get_paths()[0]])`，**不是** PolyCollection |
| boxplot box 取不到 xy | box 是 PathPatch（无 `get_xy`）：`PathPatch(p.get_path(), transform=p.get_transform())` |
| 中文渲染成方框 | `font.family='serif'+serif链` 回退失效，必须 `font.family=[列表]`；含中文串禁 `$...$` mathtext，单位用 Unicode 上标（`veh·h⁻¹`） |
| 个别符号变 U+FFFF 空框 | 缺字形集 `∈ ⊮ ∃ ∀ ∗ ‖` 渲染 `\uffff`；λ τ θ µ Ω 正常 → 换词或换字体 |
| PDF 里 notdef 空白 | fitz 扫 `\uffff`；fitz 的 warning 污染 stdout，机检前隔离 stderr |

## 脚本 / 工程

| 症状 | 根因 / 解法 |
|------|-------------|
| 反斜杠代码跑出来缺字符 | Bash heredoc 会折叠 `\\` → 含反斜杠的代码一律 Write/Edit 落盘再执行 |
| 重构后图例消失 | `gradient_bar` 替换原 `bar` 时 Rectangle 手柄易丢 → 替换后回查图例 |
| 图例把数据点挡了 | 图例放图外或 `loc` 换空角；多面板共享图例用 `consolidate_shared_legends`（plot_utils） |
| 上页字号腰斩、线发虚 | 原生画布相对"插入显示宽"过大 → 画布宽≈显示宽（缩放比 0.9–1.1），`figure_check.sh` 按长宽比分档机检 |
| 出图非确定性、验收复跑对不上 | 忘设 `rng=default_rng(42)` → 每个数据生成脚本固定种子 |
| Windows 管道 UnicodeEncodeError | python 往管道输出默认 GBK，遇 `⚠ · —` 崩 → `PYTHONIOENCODING=utf-8` |
| 路径失效（旧仓库布局） | 门禁脚本真源在 `academic-toolkit/skills/…`，旧 `科研工具箱/` 路径已废；本包已内联到 `_utils/`，直接 `import figstyle` |

## 配色 / 质感

| 症状 | 根因 / 解法 |
|------|-------------|
| "AI 感 / 脏" | 藏蓝深蓝作主色 → 蓝色系禁深色，向亮青绿 #00B4AD 族靠拢 |
| 小字看不清 | #00B4AD 太亮不能当小字 → 文字/图例墨色单设 AQUA_INK #0F7E78（白底对比度≈6.5） |
| "纯色平涂被打回" | 大面积填充未走质感三件套 → 见 `plotting-playbook.md` |
| 浅底卡片文字过不了 4.5:1 对比度闸 | `ink_of(fill)` 只登记 v6 色板 hex，不认 PASTEL 浅底（`#DCF5F1` 等）→ 传 fill 会原样返回浅色。卡片文字墨色取**同族描边色**加深：`deepen(PASTEL[key][1], 0.45)` |
| 灰度打印浅色头偏弱 | 浅色渐变在灰度下对比不足 → 靠描边 + 数值标注缓解，并如实声明 |
| 多系列灰度不可分 | 只靠颜色 → 必须"颜色+线型/标记"双编码（`PC` × `LS_SEQ`） |
