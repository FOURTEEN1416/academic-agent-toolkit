# 软著 mock 界面 UI 设计规范

> 生成"操作手册界面截图"用的 mock HTML 的唯一准绳。目标：**每个软件项目的界面配色/布局由确定性种子推导** → 不同软件千人千面、同一软件所有页面视觉统一、断线重跑可复现；同时始终**高端、克制、像真实在用的商业软件**，而不是灰蓝方角的默认草稿。
>
> ⛔ 本规范对标数模 `skills/paper-figure-html/SKILL.md` 的《AI 自主生成 HTML 流程图设计规范》，把"流程图节点"换成"软件界面组件"。核心手法一致：**确定性种子 + 低饱和配色 + 组件级样式 + 对齐硬纪律**。

## 0 硬约束（⛔ 违反即返工，无例外）

1. **单文件自包含**：每个 mock 页面是一个独立 `.html`，CSS 内联在 `<style>`；⛔ 不引 CDN、不引网络字体、不引外部图片（离线环境截图会失败）。
2. **画布真实感**：`body{margin:0}`，页面根容器铺满视口宽度（如 `1280px` 或 `1440px`），模拟真实软件窗口；不是 `fit-content` 小块（这点与流程图相反——界面就是要占满窗口）。
3. **无 emoji、无装饰性图标字体**：图标用 CSS 画（几何形状/边框）或纯文字符号（如 `≡ ⌕ ⚙ ▸`），不用 emoji、不引 FontAwesome。
4. **字体走高端系统栈**（离线安全，全是 Win/Mac 自带）：
   ```css
   *{font-family:"Segoe UI","Helvetica Neue",Helvetica,Arial,"Microsoft YaHei","Noto Sans SC",sans-serif;
     font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased;}
   ```
   西文优先 → 英文/数字用 Segoe UI（精致），中文自动 fallback 雅黑。数字用 tabular-nums 让表格/统计对齐。
5. **示例数据要真实**：表格/表单/卡片里填**该软件所属行业的真实感字段名 + 像样的值**（如"订单编号 SO-20250718-0032 / 客户 华东仓储 / 状态 已发货"），⛔ 禁止"数据1/数据2""字段A"这类占位。
6. **一页一文件、模块间不雷同**：每个 `manual_modules` 模块生成独立 HTML，标题/导航高亮/主体控件/示例数据按该模块 `purpose`/`visible_elements` 差异化。⛔ 绝不多个模块共用一图。

## 1 确定性风格种子（⛔ 每个软著项目开头先算一次，全项目所有 mock 页共用）

```bash
# 种子 = 工作区目录名的确定性哈希（同一软著项目=同一工作区=所有界面共用同一套视觉）
WFID=$(basename "$PWD")
if command -v cksum >/dev/null 2>&1; then
    UISEED=$(printf '%s' "$WFID" | cksum | cut -d' ' -f1)
else
    UISEED=$(python -c "import sys,zlib;print(zlib.crc32(sys.argv[1].encode()))" "$WFID")
fi
HUE=$(( UISEED % 360 ))
# 回避刺眼黄绿[50,70) 与 高纯红[350,360)∪[0,12) → 品牌色更沉稳
# ⛔ 用 while 反复修正(步长质数37与360互质,不死循环)：单次 +偏移 可能把低值红区推进黄绿区(如 11→56)，必须循环到彻底脱离所有回避区
while { [ $HUE -ge 50 ] && [ $HUE -lt 70 ]; } || [ $HUE -ge 350 ] || [ $HUE -lt 12 ]; do HUE=$(( (HUE + 37) % 360 )); done
SCHEME=$(( (UISEED / 7) % 3 ))   # 配色方案(界面最抢眼的差异): 0=亮白后台 1=浅灰底卡片 2=深色侧栏+亮内容区
NAV=$(( (UISEED / 11) % 3 ))     # 导航布局(界面骨架最大差异): 0=左侧竖导航 1=顶部横导航 2=左侧窄图标导航
RAD=$(( (UISEED / 13) % 3 ))     # 圆角档: 0=硬朗(3px) 1=现代(7px) 2=柔和(12px)
DENS=$(( (UISEED / 17) % 3 ))    # 密度档: 0=紧凑(专业工具) 1=舒适(主流SaaS) 2=宽松(轻量应用)
echo "🎨 UI种子 UISEED=$UISEED HUE=$HUE° SCHEME=$SCHEME NAV=$NAV RAD=$RAD DENS=$DENS（全项目所有mock页共用）"
```

⛔ 记下 `HUE/SCHEME/NAV/RAD/DENS`，**所有 mock 页面用同一组值**——禁逐页换、禁随机数/时间戳。组合空间 ~11(HUE色带)×3(SCHEME)×3(NAV)×3(RAD)×3(DENS) ≈ 上千种明显不同的界面风格，跨项目撞脸概率极低；但同项目内所有页视觉统一（像同一个软件的不同页面）。

## 2 配色配方（⛔ 从种子 HUE 用 HSL 推导，示例数值不得照抄）

界面配色的**高端秘诀**（和数模一致）：**主体是白/浅灰/中性灰阶，品牌色 HUE 只用于点睛处**——logo、激活态导航项、主按钮、关键链接、图表主色、状态高亮。品牌色目测占比 **≤15%**，其余全中性。⛔ 绝不整屏铺满高饱和色（那就是廉价 admin 模板的元凶）。

按下表用 HSL 从 `HUE` 推导整套 `:root` 变量（每页 `<style>` 开头写一次）：

| 角色 | 变量 | 推导规则（H=HUE） | 用途 |
|---|---|---|---|
| 品牌主色 | `--brand` | `hsl(H,42%,46%)` | logo、主按钮底、激活导航、图表主色 |
| 品牌深色 | `--brand-d` | `hsl(H,44%,38%)` | 按钮 hover、强调文字 |
| 品牌浅底 | `--brand-bg` | `hsl(H,40%,96%)` | 激活项浅底、选中行、标签底 |
| 正文字 | `--text` | `#1f2329`（近黑无色相） | 主文字 |
| 次要字 | `--muted` | `#6b7280` | 副标题、表头、提示 |
| 分割线 | `--line` | `#e5e7eb` | 边框、表格线、分隔 |
| 页面底 | `--bg` | SCHEME 定（见下）| 最外层背景 |
| 卡片底 | `--card` | `#ffffff` | 卡片/表格/表单容器 |
| 成功/警告/危险 | `--ok/--warn/--err` | `hsl(150,45%,42%)` / `hsl(38,80%,50%)` / `hsl(4,65%,52%)` | 状态标签（语义色，固定，不随 HUE 变） |

⛔ **配色铁律**：①主体中性灰阶，品牌色 ≤15% 只点睛；②`--brand` 饱和 ≤45%（低饱和才高端）；③状态色（成功绿/警告橙/危险红）是**语义固定色**，不跟品牌色走，但也用低饱和版本；④对比度：正文对卡片底 ≥ 7:1（近黑配白自然达标）；⑤⛔ 不用纯黑 `#000`、不用高饱和原色、不用彩虹渐变。

## 3 配色方案 SCHEME + 导航布局 NAV（界面骨架的最大差异来源）

**SCHEME（配色方案）——决定 `--bg` 和整体明暗气质：**

| 值 | 方案 | `--bg` | 气质 | 适合 |
|---|---|---|---|---|
| 0 | 亮白后台 | `#ffffff` | 干净通透，卡片靠 `--line` 描边区分 | Notion/Linear 风，最百搭 |
| 1 | 浅灰底卡片 | `#f5f6f8` | 内容区浅灰、卡片纯白浮起（细阴影），层次分明 | 主流 SaaS 后台 |
| 2 | 深色侧栏+亮内容 | 内容区 `#f7f8fa`、侧栏 `hsl(H,20%,16%)` 深底白字 | 专业、稳重、有科技感 | 数据/监控/管理类 |

**NAV（导航布局）——决定页面骨架，界面第一眼差异：**

| 值 | 布局 | 结构 |
|---|---|---|
| 0 | 左侧竖导航 | 左 220px 竖栏（logo + ≥4 导航项，激活项 `--brand-bg` 底 + `--brand` 左竖条）+ 右内容区（顶部面包屑/操作条 + 主体） |
| 1 | 顶部横导航 | 顶 56px 横栏（logo + 横向 ≥4 菜单 + 右侧用户区）+ 下方内容区（可选二级左栏或直接主体） |
| 2 | 左侧窄图标导航 | 左 64px 窄栏（纯 CSS 图标 + 激活高亮）+ 右内容区；窄栏省空间、显精致 |

⛔ SCHEME 与 NAV 由种子定，**全项目所有页统一用同一组**（同一个软件不可能这页左导航那页顶导航）。SCHEME=2 深色侧栏必须配 NAV=0 或 2（有侧栏才能深色）；若种子恰好 SCHEME=2 且 NAV=1（顶导航无侧栏），则深色只落到顶栏。

## 4 组件样式库（⛔ 界面"不丑"的核心——按此给每类组件样式，别放任默认）

RAD 定圆角 `--r`（0→3px / 1→7px / 2→12px）；DENS 定间距节奏 `--pad`/`--gap`（0紧凑→8/10px、1舒适→12/16px、2宽松→16/22px）。以下骨架照搭，把示例内容换成本软件真实字段。

**① 顶栏 / logo**：高 52–56px，白底或品牌深底（SCHEME2 顶栏可深色），左侧 logo（`--brand` 色块 + 软件名 `font-weight:700`），右侧用户头像圆 + 名字。底部 `1px solid --line` 分隔。
```css
.topbar{height:54px;display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;background:var(--card);border-bottom:1px solid var(--line)}
.logo{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--text);font-size:15px}
.logo .mark{width:26px;height:26px;border-radius:var(--r);background:var(--brand)}
```

**② 侧导航（NAV0/2）**：宽 220px（图标档 64px）；导航项 `padding:10px 14px`、图标 + 文字；**激活项** = `--brand-bg` 浅底 + 左 `3px solid --brand` 竖条 + `--brand-d` 文字 + `font-weight:600`；其余项 `--muted` 文字、hover 浅灰底。⛔ 激活项**不用**实心品牌色满底白字（那是廉价感来源），用浅底+竖条。
```css
.side{width:220px;background:var(--card);border-right:1px solid var(--line);padding:12px 10px;display:flex;flex-direction:column;gap:2px}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:var(--r);
  color:var(--muted);font-size:14px;cursor:default}
.nav-item.active{background:var(--brand-bg);color:var(--brand-d);font-weight:600;
  box-shadow:inset 3px 0 0 var(--brand)}
.nav-item .ico{width:16px;height:16px;border:1.6px solid currentColor;border-radius:4px;flex:none}
```

**③ 内容区顶部操作条**：面包屑（`当前模块 / 子页`，`--muted`）+ 页标题（18–20px `font-weight:700`）+ 右侧主按钮/筛选。与主体留 `--gap`。

**④ 主按钮 / 次按钮**：主按钮 = `--brand` 底 + 白字 + `--r` 圆角 + `padding:8px 16px`（**按钮是允许用品牌色满底的少数例外**，因面积小占比低）；次按钮 = 白底 + `--line` 边 + `--text` 字；危险按钮 = `--err` 边/字。⛔ 一个页面最多一个主按钮，其余用次按钮（唯一主操作原则）。
```css
.btn{padding:8px 16px;border-radius:var(--r);font-size:13px;font-weight:600;border:1px solid transparent;cursor:default}
.btn.primary{background:var(--brand);color:#fff}
.btn.ghost{background:var(--card);border-color:var(--line);color:var(--text)}
```

**⑤ 表格（列表页核心）**：卡片容器包裹；表头 `--muted` 底浅灰 `font-weight:600` 小字；行高 44–48px、行间 `1px solid --line`、hover 行 `--brand-bg` 浅底；数字列右对齐（tabular-nums 已全局）；操作列放小号次按钮/链接。⛔ 表头别用品牌色满底，用浅灰 `#f9fafb`。
```css
.table{width:100%;border-collapse:collapse;background:var(--card);border-radius:var(--r);overflow:hidden;border:1px solid var(--line)}
.table th{background:#f9fafb;color:var(--muted);font-weight:600;font-size:12px;text-align:left;padding:11px 14px;border-bottom:1px solid var(--line)}
.table td{padding:12px 14px;font-size:13px;color:var(--text);border-bottom:1px solid var(--line)}
.table tr:last-child td{border-bottom:none}
```

**⑥ 统计卡片（仪表盘页）**：3–4 个等宽卡片（`display:grid;grid-template-columns:repeat(4,1fr);gap:--gap` 强制等宽等高）；每卡 = 小标题 `--muted` + 大数字 `28px font-weight:700 --text` + 变化量（`--ok`/`--err` 小字带 ↑↓）；卡片白底 `--line` 细边或细阴影。
```css
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap)}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px;display:flex;flex-direction:column;gap:6px}
.stat .k{font-size:12px;color:var(--muted)} .stat .v{font-size:28px;font-weight:700;color:var(--text)}
.stat .d{font-size:12px;font-weight:600}
```

**⑦ 图表占位（仪表盘）**：不引图表库，用 CSS 画**像样的**柱/折线示意——柱状用等宽 `--brand` 半透明矩形高低错落 + 底部 X 轴标签 + 左侧 Y 轴刻度线；折线用 `border` 或 `clip-path`。⛔ 别放空白灰框写"图表区域"，那是空壳。至少画出坐标轴 + 3–6 根柱/一条折线 + 图例。

**⑧ 表单（表单页）**：字段纵向排列或两列 grid；每字段 = label（`--muted` 13px）+ 输入框（白底 `--line` 边 `--r` 圆角 `padding:9px 12px`，focus 态 `--brand` 边）；下拉/开关/单选按真实控件画；底部主按钮 + 取消次按钮。至少 5–8 个带标签字段。

**⑨ 状态标签 / 徽章**：小圆角胶囊，语义色浅底 + 深字（成功=`--ok` 系浅底深字、进行中=`--brand-bg`+`--brand-d`、警告/失败同理）。⛔ 不用高饱和满底白字。
```css
.tag{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600}
.tag.ok{background:hsl(150,45%,95%);color:hsl(150,45%,32%)}
.tag.run{background:var(--brand-bg);color:var(--brand-d)}
.tag.err{background:hsl(4,65%,96%);color:hsl(4,55%,44%)}
```

**⑩ 分页 / 详情页**：分页 = 右下角页码按钮组（当前页 `--brand` 高亮）；详情页 = 字段分组卡片（label-value 两列）+ 顶部状态标签 + 操作按钮。

## 5 高端审美细节（⛔ 这些决定"像商业软件"还是"像半成品 demo"）

对标数模 D.1 七条，界面版：

1. **层次靠深浅灰+字重，不靠多色**：主/次信息用 `--text`/`--muted` 和 `font-weight` 700/600/500/400 拉层次，别每类加个颜色。品牌色只留给点睛处。
2. **克制阴影**：SCHEME1 卡片最多 `0 1px 3px rgba(0,0,0,.06)`；SCHEME0 尽量只用 `--line` 描边不用阴影。⛔ 无大面积渐变、无粗黑边、无外发光。
3. **留白呼吸**：内容区四周 `padding` ≥ 20px；卡片内 `padding` 按 DENS；组件间 `gap` 统一。宁可空，不要挤。
4. **⛔⛔ 对齐硬纪律（"不对齐/参差"是最直接的丑，一票否决）**：
   - 并列的统计卡片/表单字段用 `grid` + `1fr` 强制**等宽等高**，禁手写不同 width；
   - 表格列、卡片、按钮的边缘对齐成线；导航项左边距一致；
   - 全页统一一个 `--r` 圆角、统一 `gap` 节奏、统一字号档；
   - 一句话：**看上去像用尺子摆过**——横平竖直、等大等距、边缘成线。
5. **唯一主操作**：一个页面只有一个 `--brand` 主按钮（最重要动作），其余次按钮，避免满屏彩色按钮。
6. **真实信息密度**：表格 6–10 行真实数据、表单 5–8 字段、仪表盘 3–4 卡片 + 图表——填满但不堆砌，像真在用的软件。
7. **文字规范**：数字 tabular-nums 对齐；中文用词专业（该行业真实术语）；⛔ 界面文案不写"数据1"、不写 lorem、不写"功能模块"这类占位。

> 一句话：**中性灰阶主体 + 品牌色≤15%点睛 + 组件级规范样式 + 对齐硬纪律 + 唯一主操作**——这几条齐了，mock 界面就有商业软件的高级感。

## 6 生成 + 自检清单（每张 mock 页出图前后各过一遍）

**生成前：**
1. 种子 `HUE/SCHEME/NAV/RAD/DENS` 算好了吗？本页用的是不是和其它页**同一组**？
2. 本页对应哪个 `manual_modules` 模块？标题/导航高亮/主体控件是否按该模块 `purpose`/`visible_elements` 定制（不是照抄别的模块）？
3. 页面类型对不对：列表页→表格、仪表盘→卡片+图表、表单页→表单、详情页→字段分组？

**出图后：**
1. 品牌色占比 ≤15% 吗？主体是不是中性灰阶（没有整屏铺高饱和色）？
2. 眯眼看：并列卡片/字段等宽等高吗？边缘对齐成线吗？圆角/间距全页统一吗？——参差就用 grid+1fr 改。
3. 有真实感数据吗（真字段名+像样值，非占位）？表格 ≥6 行、表单 ≥5 字段、仪表盘 ≥3 卡片？
4. 只有一个主按钮吗？状态标签用浅底深字（非高饱和满底）吗？
5. 和本项目其它 mock 页比：配色/圆角/布局统一（像同一软件），但**主体内容因模块不同而不同**？
6. 像一个"真实在用的商业软件界面"，而不是"灰蓝方角的默认后台草稿"吗？认不出就回去按本规范重做。

⛔ **与数模流程图的关键区别**：流程图要 `fit-content` 小图、`transparent` 无底；界面要**铺满窗口宽度**（1280/1440px）、**有页面背景色**（`--bg`），因为它模拟的是真实软件窗口截图。除此之外，配色克制/组件规范/对齐纪律的高端手法完全一致。
