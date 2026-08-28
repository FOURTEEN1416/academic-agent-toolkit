---
name: dev-code-backend
description: "一句话生成项目·后端编码。按设计实现后端(FastAPI/Flask/Express)+数据库。Use when 后端编码/写后端."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 一句话生成项目 · 后端编码

按系统设计实现**后端 + 数据库**，并与已完成的前端对接：**$ARGUMENTS**

## ⛔⛔⛔ 铁律：少读多写，绝不"读完再写"（最高优先级，先读这段）

这一步最容易犯的致命错误：**想把前端所有文件读全了再动手 → 上下文被撑爆 → 自动压缩 → 压缩后"忘了" → 又从头读 → 反复压缩、永远写不出代码（表现为"卡住不产出文件"）。**

**必须这样做：**
- ✅ **DESIGN.md 就是接口权威**（它已列全 API 路径/方法/字段），按它写即可，**不需要**为了"对齐前端"去通读前端源码。
- ✅ 确实要核对前端调用时，**只用 grep 抓关键行、绝不整文件 Read**。例如：
  ```bash
  # 抓前端所有 API 调用的路径/方法(只看这些行,不读整文件)
  grep -rn "request\.\(get\|post\|put\|delete\)\|axios\|/api/" code/frontend/src/api/ 2>/dev/null | head -60
  ```
- ✅ **拿到 DESIGN.md + schema.sql 就立刻开始写**，写一个模块就用 heredoc 落一个文件，**写完就落盘、不囤在上下文里**。
- ❌ **禁止**：`Read` 整个前端 api 目录 / 逐个整文件读 request.js、project.js、paper.js…… / "先把所有文件读完形成完整理解再写"。
- ❌ 若已读了大量文件、上下文吃紧：**立刻停止读、马上开始写文件**，别再读。

## 输入（按需读，别贪读）

1. **DESIGN.md**（必读，接口权威）— 技术架构/数据库设计/API 设计/目录结构。**这是唯一需要完整读的文件。**
2. **schema.sql** — 建表 SQL（不长，可读）。
3. **CLAUDE.md** — 技术栈（后端框架 + 数据库），读参数段即可。
4. **REQUIREMENTS.md** — 接口/功能清单，可 grep 关键小节，不必逐字。
5. **前端接口对齐** — **只 grep** `code/frontend/src/api/` 抓路径/字段（见上方铁律），**不整文件读**。以 DESIGN.md 为准，grep 仅用于核对。

## ⛔ 恢复场景

若 `code/backend/` 已有部分代码，在其基础上**续写补全，不要推倒重来**（先 `ls code/backend/` 看已有什么，不要整个重读）。

## ⛔ 先看后端框架（读 CLAUDE.md 的技术栈/目录约定段，按框架定入口和启动方式）

后端框架有三种，**入口文件名和启动方式不同，预览服务靠入口文件识别怎么起，务必按约定命名**：

| 框架 | 入口文件 | 应用写法 | 端口 | 依赖清单 | 预览启动方式 |
|------|---------|---------|------|---------|-------------|
| **FastAPI** | `code/backend/main.py` | `app = FastAPI()` | uvicorn 传入 | requirements.txt | `uvicorn main:app` |
| **Flask** | `code/backend/app.py` | `app = Flask(__name__)`，末尾 `app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))` | 读 `PORT` 环境变量 | requirements.txt | `python app.py` |
| **Node-Express** | `code/backend/index.js` + `package.json` | `express()`，`app.listen(process.env.PORT || 3000)` | 读 `process.env.PORT` | package.json（`scripts.start`=`node index.js`） | `npm start` |

⛔ **端口铁律**：Flask/Express 入口**必须读环境变量 `PORT`**（预览服务用 PORT 指定端口），没有 PORT 时用框架默认端口兜底。FastAPI 的端口由 uvicorn 命令行传，入口不用管端口。

## 任务

- 实现 `code/backend/`：**按上表选对入口文件名**、数据模型、数据库连接（按 schema.sql 建表）、覆盖 DESIGN.md 的所有 API。
- **与前端对接**：前端调的每个接口都要实现，路径/方法/字段与前端一致。
- 数据库：SQLite 免配置（推荐），按 schema.sql 初始化；MySQL 则在 README 写清连接配置。
- 配好 CORS，让前端 dev server 能跨端口调后端（Flask 用 flask-cors，Express 用 cors 中间件，FastAPI 用 CORSMiddleware）。
- **⛔ 后端必须同源托管前端静态资源（见下方铁律）** —— 否则预览时前端 `fetch("/api")` 会 404。
- 更新 `RUN.md`：补上后端启动步骤（按框架：`uvicorn main:app` / `python app.py` / `npm start`）。

## ⛔⛔⛔ 铁律：后端必须托管前端静态资源（同源，避免预览 404）

前端里所有接口调用都是**相对路径** `fetch("/api/...")`，只有"前端和 API 同一个端口(同源)"才打得中。预览服务**只起后端一个进程**，靠后端把前端页面也一起托管，实现同源。**后端入口必须挂载前端静态目录**：

- **前端目录**：全栈项目在 `code/frontend/`。若前端是 **React/Vue**(有 package.json)，托管其 **build 产物** `code/frontend/dist`(Vite) 或 `build`(CRA)；若是**纯 HTML**，直接托管 `code/frontend/`。
- **挂载路径 `/`**，且 **API 路由(`/api` 前缀)必须先于静态挂载注册**，否则会被静态兜底吃掉。
- 前端目录/产物**不存在时要容错**（`if os.path.isdir(...)` 再挂载），别让后端起不来。

**三框架示例（照抄，路径按 dist 优先、回退源码目录）：**

```python
# ── FastAPI(main.py)：API 路由全部 include 之后，再挂静态 ──
import os
from fastapi.staticfiles import StaticFiles
_here = os.path.dirname(os.path.abspath(__file__))
_fe = os.path.normpath(os.path.join(_here, "..", "frontend"))
_dist = os.path.join(_fe, "dist")
_FRONT = _dist if os.path.isdir(_dist) else _fe   # React 用 dist, 纯HTML用源码目录
if os.path.isdir(_FRONT):
    app.mount("/", StaticFiles(directory=_FRONT, html=True), name="frontend")
```

```python
# ── Flask(app.py)：static 指向前端目录, 加 SPA 回退路由 ──
import os
from flask import send_from_directory
_here = os.path.dirname(os.path.abspath(__file__))
_fe = os.path.normpath(os.path.join(_here, "..", "frontend"))
_dist = os.path.join(_fe, "dist")
_FRONT = _dist if os.path.isdir(_dist) else _fe
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def _serve_front(path):
    full = os.path.join(_FRONT, path)
    if path and os.path.isfile(full):
        return send_from_directory(_FRONT, path)
    return send_from_directory(_FRONT, "index.html")  # 首页/SPA 回退
```

```javascript
// ── Express(index.js)：API 路由之后再挂 static ──
const path = require("path");
const fs = require("fs");
const feBase = path.join(__dirname, "..", "frontend");
const dist = path.join(feBase, "dist");
const FRONT = fs.existsSync(dist) ? dist : feBase;
app.use(express.static(FRONT));
app.get(/^\/(?!api).*/, (req, res) => res.sendFile(path.join(FRONT, "index.html")));
```

## 目录约定（按框架，入口文件名不同）

```
code/backend/
  main.py / app.py / index.js   # 入口(按框架三选一, 必须)
  models.py 等                   # 数据模型(Python 系)
  database.py                    # DB 连接/建表(Python 系)
  requirements.txt / package.json # 依赖(Python→requirements.txt, Node→package.json)
```

## 完成铁律

- `code/backend/main.py` 是有效应用（FastAPI: `app=FastAPI()`）。
- `code/backend/requirements.txt` 列全依赖。
- 覆盖 REQUIREMENTS 接口清单的每个接口，用真实逻辑。
- **后端入口已同源托管前端静态资源**（有 `code/frontend/` 时，入口必须含 StaticFiles/static/express.static 挂载，见上方铁律）。
- `RUN.md` 含前后端完整启动步骤。

## ⛔⛔ 分步写入规则（防大段写入被截断，务必遵守）

**绝不一次性 Write 一个大文件。** 单次写入过大会被截断，产出残缺代码。规则：
1. **每个文件用 Bash heredoc 分段写，每段 ≤ 150 行**：先写第一段（`cat > file`），再追加后续段（`cat >> file`）。
2. **heredoc 必须用带单引号的 `'EOF'`** —— 代码含 `$` `\` `"` 反引号等特殊字符，不加引号会被 shell 转义成乱码：
   ```bash
   cat > code/backend/main.py << 'EOF'
   ...前 150 行...
   EOF
   cat >> code/backend/main.py << 'EOF'
   ...后续行...
   EOF
   ```
3. **写完每个文件用 `wc -l 文件` 确认行数符合预期**（验证没被截断）。
4. 一个模块/文件写完就落盘，再写下一个，不要囤在上下文里。

⛔ **结束前必跑产出验证**：
```bash
echo "=== 后端编码产出验证 ==="
PASS=true
BE=code/backend
# 按框架探测入口(FastAPI→main.py / Flask→app.py / Express→index.js+package.json)
if [ -f "$BE/main.py" ] && grep -qE "FastAPI\(|app *=" "$BE/main.py"; then
  echo "OK FastAPI 入口 main.py"
  { [ -f "$BE/requirements.txt" ] && echo "OK requirements.txt"; } || { echo "FAIL 缺 requirements.txt"; PASS=false; }
elif [ -f "$BE/app.py" ] && grep -qE "Flask\(|app *=" "$BE/app.py"; then
  echo "OK Flask 入口 app.py"
  grep -q "PORT" "$BE/app.py" && echo "OK app.py 读 PORT 环境变量" || echo "WARN app.py 未读 PORT, 预览可能用默认端口"
  { [ -f "$BE/requirements.txt" ] && echo "OK requirements.txt"; } || { echo "FAIL 缺 requirements.txt"; PASS=false; }
elif [ -f "$BE/package.json" ]; then
  echo "OK Node/Express 入口 package.json"
  grep -q '"start"' "$BE/package.json" && echo "OK package.json 有 start 脚本" || echo "WARN package.json 缺 start 脚本, 预览 npm start 会失败"
  { ls "$BE"/index.js "$BE"/server.js "$BE"/app.js >/dev/null 2>&1 && echo "OK 有 JS 入口文件"; } || echo "WARN 未见明确 JS 入口"
else
  echo "FAIL code/backend/ 无有效后端入口(main.py/app.py/package.json 都没有或非应用)"; PASS=false
fi
# ⛔ 全栈项目(有 code/frontend/): 后端入口必须同源托管前端静态资源, 否则预览 /api 会 404
if [ -d code/frontend ]; then
  ENTRY=""
  for e in "$BE/main.py" "$BE/app.py" "$BE/index.js" "$BE/server.js" "$BE/app.js"; do [ -f "$e" ] && ENTRY="$ENTRY $e"; done
  if [ -n "$ENTRY" ] && grep -qiE "StaticFiles|static_folder|send_from_directory|express\.static|app\.use\(express\.static|render_template" $ENTRY; then
    echo "OK 后端已同源托管前端静态资源"
  else
    echo "FAIL 有 code/frontend/ 但后端入口未托管前端静态资源(预览 /api 会 404) —— 按铁律加 StaticFiles/static/express.static 挂载"; PASS=false
  fi
fi
[ -f RUN.md ] && echo "OK RUN.md" || { echo "FAIL 缺 RUN.md"; PASS=false; }
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。
