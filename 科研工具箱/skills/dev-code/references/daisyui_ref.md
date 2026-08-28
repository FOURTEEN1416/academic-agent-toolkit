# daisyUI 5 组件速查（前端审美参考）

> 生成前端界面时用 daisyUI 组件 class，别手写零散 CSS，界面会更统一专业。
> daisyUI 5 需要 Tailwind CSS 4。

## 引入（本地优先，CDN 兜底）

CSS 里：
```css
@import "tailwindcss";
@plugin "daisyui";
```
或 CDN（离线场景需自行下载到本地）：
```html
<link href="https://cdn.jsdelivr.net/npm/daisyui@5/daisyui.css" rel="stylesheet" type="text/css" />
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
```

## 主题
在 `<html data-theme="THEME">` 设置，整站统一换肤。推荐用 `light` / `corporate` / `nord` / `winter`（干净专业）。
可选主题：light, dark, cupcake, corporate, nord, winter, business, emerald, garden, lofi, pastel, wireframe 等 35 个。

## 语义色（跟随主题，别用裸 Tailwind 色）
`primary` / `secondary` / `accent` / `neutral` / `base-100/200/300` / `base-content` / `info` / `success` / `warning` / `error`，及各自 `*-content`。
铁律：**页面大部分用 `base-*`；`primary` 只用在最重要的一个元素上。** 用法 `bg-primary` `text-base-content`。

## 常用组件 class

**表单/操作**
- 按钮：`btn` + 色(`btn-primary`) + 样式(`btn-outline`/`btn-ghost`/`btn-link`) + 尺寸(`btn-sm`~`btn-xl`) + `btn-wide`/`btn-block`/`btn-circle`
- 输入：`input` / `textarea` / `select` / `file-input`（共享色和尺寸后缀）
- 勾选：`checkbox` / `radio` / `toggle` / `range`
- 表单域：`fieldset` + `fieldset-legend`，标签 `label`

**布局/容器**
- 卡片：`card` + `card-body` / `card-title` / `card-actions`；`card-side` / `image-full`
- 导航栏：`navbar` + `navbar-start/center/end`
- 页脚：`footer` + `footer-title`
- 抽屉：`drawer` + `drawer-content` / `drawer-side` / `drawer-toggle`；`lg:drawer-open`
- Hero：`hero` + `hero-content`；分割 `divider`；堆叠 `stack`；组合 `join` + `join-item`（分页/按钮组）

**导航**
- 菜单：`menu`（`menu-horizontal` / `menu-title`）
- 标签页：`tabs` + `tab`（`tabs-box`/`tabs-border`/`tabs-lift`，激活 `tab-active`）
- 面包屑 `breadcrumbs`；步骤 `steps` + `step`；下拉 `dropdown` + `dropdown-content`

**数据展示**
- 表格：`table`（`table-zebra` / `table-pin-rows`），外层包 `overflow-x-auto`
- 徽章 `badge`；统计 `stats` + `stat`；头像 `avatar`；聊天 `chat` + `chat-bubble`
- 进度 `progress` / `radial-progress`（`style="--value:70;"`）；时间线 `timeline`；列表 `list` + `list-row`

**反馈/浮层**
- 提示 `alert` + 色；吐司 `toast` + 位置
- 弹窗：`modal` + `modal-box` / `modal-action` / `modal-backdrop`（用 `<dialog>`）
- 工具提示 `tooltip`（`data-tip="..."`）；加载 `loading` + `loading-spinner/dots/ring/bars`；骨架 `skeleton`

## 用法要点
- 先加组件 class，再叠可选 修饰/部件/色/尺寸 class。
- 用 Tailwind 工具类微调（如 `btn px-10`）；尽量别用 `!important`。
- 除非用户指定，**用组件默认变体**即可。
- `flex`/`grid` 布局加响应式前缀（`sm:` `lg:`）。
- 占位图：`https://picsum.photos/200/300`。
- daisyUI 语义色会跟主题自动切换，**不用写 `dark:`**。

## 好看的基本原则
- 统一间距（用 `gap-*` `p-*` `space-y-*`），别乱。
- 容器居中限宽：`container mx-auto px-4`。
- 层次清晰：标题用 `text-xl font-bold`，正文 `text-base-content/70` 降低权重。
- 卡片化组织内容，留白充足。
- 表单用 `fieldset`/`label` 规整对齐，按钮主次分明（主操作 `btn-primary`，次要 `btn-ghost`）。
