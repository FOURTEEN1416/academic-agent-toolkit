---
name: dev-selfcheck
description: "毕业设计(软件开发)自测验证。装依赖、构建前端、起后端探活、验证核心功能。Use when user says 自测/测试/毕设验证."
argument-hint: [project-idea]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 毕业设计 · 自测验证

对已实现的项目做自测：**$ARGUMENTS**

## 输入（靠跑命令验证，不要通读代码）

1. **RUN.md** — 启动步骤（读它就知道怎么跑）。
2. **CLAUDE.md** — 读 `project_type` 决定验证方式（见下）。
3. **REQUIREMENTS.md** — 核对核心功能，可 grep 功能清单。
4. **code/** — ⛔ **不要 Read 整个目录**（文件多会撑爆上下文）。自测是**跑命令**（装依赖/构建/起服务探活），不是读代码；需要看时用 `ls`/`grep`/`head` 按需，别整读。

## ⛔ 按项目类型验证（先读 project_type）

- **fullstack**：装前后端依赖 → 前端（有 package.json 则 `npm run build`；纯 HTML 则见下方"前端入口校验"）→ 后端"起服务探活立即杀"（见下方铁律）。
- **frontend**：有 package.json 则装依赖 + `npm run build` 通过；纯 HTML 则见下方"前端入口校验"。**不起后端服务。**

### ⛔ 前端入口校验（纯 HTML 前端必查，否则预览起不来）
预览服务靠 `index.html` 或 `package.json` 启动。若前端是纯 HTML（无 package.json），**必须确认有 `index.html` 入口**：
```bash
FE=code/frontend; [ -d "$FE" ] || FE=code
if [ ! -f "$FE/package.json" ] && [ ! -f "$FE/index.html" ] && find "$FE" -name "*.html" | grep -q .; then
  echo "缺 index.html 入口, 预览会打开成文件列表 —— 补一个 index.html(首页/导航链到各页)"
  # 有散页无首页: 生成一个导航页(daisyUI 卡片链到各 .html)
fi
```
发现缺 index.html 就**补一个**（daisyUI 导航页链到各页面），并记录到修复记录。
- **cli**：跑 `--help` + 一两条核心命令验证。**不起常驻服务。**
- **script**：直接跑主脚本，确认能执行、无报错。**不起常驻服务。**

## ⛔ 恢复场景

若已有 `TEST_REPORT.md`，在其基础上补全，不要推倒重写。

## ⛔⛔⛔ 起服务铁律（最重要，违反会导致整步卡死失败）

**绝对不能前台阻塞式起服务。** `uvicorn main:app`、`npm run dev` 这类前台常驻进程会占住终端不返回，触发系统的"40 分钟无输出超时"，导致整步失败。

**必须用"启动 → 后台 → 探活 → 立即杀"的自限时模式**，每个命令都带 `timeout`：

```bash
# ✅ 装依赖(按后端框架: Python→pip, Node→npm)
# ⛔ 成功不打日志(几百行 added/deprecated 会撑爆上下文触发 compact), 失败才 tail -30 看错因
if [ -f code/backend/requirements.txt ]; then
  timeout 300 bash -c 'cd code/backend && pip install -r requirements.txt' >/tmp/be_install.log 2>&1 && echo "OK 后端依赖已装" || { echo "FAIL 后端依赖(见下)"; tail -30 /tmp/be_install.log; }
elif [ -f code/backend/package.json ]; then
  timeout 300 bash -c 'cd code/backend && npm install' >/tmp/be_install.log 2>&1 && echo "OK 后端依赖已装" || { echo "FAIL 后端依赖(见下)"; tail -30 /tmp/be_install.log; }
fi
# 前端依赖 + 构建(React/Vue 有 package.json; 纯 HTML 无, 跳过)
if [ -f code/frontend/package.json ]; then
  timeout 300 bash -c 'cd code/frontend && npm install' >/tmp/fe_install.log 2>&1 && echo "OK 前端依赖已装" || { echo "FAIL 前端依赖(见下)"; tail -30 /tmp/fe_install.log; }
  timeout 180 bash -c 'cd code/frontend && npm run build' >/tmp/fe_build.log 2>&1 && echo "OK 前端构建通过" || { echo "FAIL 前端构建(见下)"; tail -30 /tmp/fe_build.log; }
else
  echo "前端无 package.json(纯 HTML), 跳过 npm build; 确认有 index.html 入口即可"
  [ -f code/frontend/index.html ] || echo "⚠ 纯 HTML 前端缺 index.html 入口(预览会显示文件列表)"
fi

# ✅ 起后端服务探活(按框架三选一): 后台起 → 睡几秒 → curl 探活 → 立即杀。高位端口 8731
cd code/backend
PORT=8731
if [ -f main.py ]; then          # FastAPI
  (timeout 30 python -m uvicorn main:app --host 127.0.0.1 --port $PORT >/tmp/belog 2>&1 &)
  KILLPAT="uvicorn main:app --host 127.0.0.1 --port $PORT"
elif [ -f app.py ]; then         # Flask(入口读 PORT 环境变量)
  (PORT=$PORT timeout 30 python app.py >/tmp/belog 2>&1 &)
  KILLPAT="python app.py"
elif [ -f package.json ]; then   # Express/Node(npm start, 读 process.env.PORT)
  (PORT=$PORT timeout 30 npm start >/tmp/belog 2>&1 &)
  KILLPAT="node"
fi
sleep 8
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:$PORT/ 2>&1 || echo "后端未响应(看 /tmp/belog)"
# FastAPI 额外探 /docs; 其它框架探根路径即可
[ -f main.py ] && curl -s http://127.0.0.1:$PORT/docs -o /dev/null -w "docs: %{http_code}\n" 2>&1
# 杀掉刚起的后端进程, 绝不留驻
pkill -f "$KILLPAT" 2>/dev/null || true
cd ../..
```

⛔ 要点：
- 后端起服务用**高位随机端口**（如 8731），绝不用 18088/18089（主后端占用）。Flask/Express 通过 `PORT` 环境变量传端口。
- 起完探活后**立即 pkill 杀掉**，不留后台进程。
- 前端有 package.json（React/Vue）**只验证 `npm run build` 通过**；纯 HTML 确认有 index.html 入口即可，不起 dev server 交互。
- 每个命令加 `timeout`，装依赖 5 分钟上限、构建 3 分钟上限、起服务 30 秒上限。
- 装依赖/构建失败：尝试修明显问题（缺依赖、语法错）后重试一次；仍失败则如实记录到报告，不要卡死。

## ⛔ 界面截图（前端有界面就截真图存 figures/，供报告复用）

联调时前端已能跑，**顺手给界面截真图**存 `figures/shot_*.png`，后面 dev-report 直接引用（截过就不用报告阶段重起前端）。
- **截图能力可能不可用**（非桌面环境、开发机没配 Electron）：`--check` 探测失败就**整段跳过**，不阻塞自测，报告相应处退占位符。
- 纯 HTML：直接 `file://` 逐页截。框架项目：用前面 `npm run build` 出的 `dist/`(或 `build/`) 静态产物，`http.server` 秒起截首页（**不起 `npm run dev`**，避免现编译卡死）。
- ⛔ 严守起服务铁律：后台起 + 记 PID + 截完**立即 kill** + 看门狗兜底，绝不留后台进程。

```bash
echo "=== 界面截图(可选, 失败不阻塞自测) ==="
# 1) 探测截图能力(Electron capturePage), 不可用整段跳过
if ! python _utils/screenshot_capture.py --check >/dev/null 2>&1; then
  echo "⚠ 截图能力不可用(非桌面环境?), 跳过界面截图, 报告相应处用占位符"
else
  mkdir -p figures
  FE=code/frontend; [ -d "$FE" ] || FE=code
  SHOT_N=0
  # A) 纯 HTML: 逐个主要 .html 直接 file:// 截(最多 6 张; index→shot_home)
  if [ -f "$FE/index.html" ] || { [ ! -f "$FE/package.json" ] && ls "$FE"/*.html >/dev/null 2>&1; }; then
    for html in "$FE"/index.html "$FE"/*.html; do
      [ -f "$html" ] || continue
      bn=$(basename "$html" .html)
      out=$([ "$bn" = index ] && echo figures/shot_home.png || echo "figures/shot_${bn}.png")
      [ -f "$out" ] && continue   # 去重(index.html 会被通配再匹配一次)
      timeout 60 python _utils/screenshot_capture.py --file "$html" --out "$out" --width 1280 --height 800 >/dev/null 2>&1
      [ -f "$out" ] && { echo "✅ $out"; SHOT_N=$((SHOT_N+1)); }
      [ "$SHOT_N" -ge 6 ] && break
    done
  fi
  # B) 框架项目(有 package.json): 用 build 产物起静态服务截首页
  #    ⛔ 用 dist/(Vite) 或 build/(CRA) 静态文件, 不起 npm run dev(现编译慢/易卡)
  if [ -f "$FE/package.json" ] && [ ! -f figures/shot_home.png ]; then
    DIST=""
    for d in "$FE/dist" "$FE/build"; do [ -f "$d/index.html" ] && DIST="$d" && break; done
    if [ -z "$DIST" ]; then
      echo "⚠ 框架项目无 dist/build 产物(build 未成功?), 跳过截图, 报告用占位符"
    else
      SPORT=8752
      # 后台起静态服务(不套 timeout/子shell, 才能拿到真实 PID 可靠 kill)
      python -m http.server $SPORT --directory "$DIST" >/tmp/shot_http.log 2>&1 &
      SRV_PID=$!
      # 看门狗: 45s 后兜底杀(防主逻辑异常没走到 kill 而留进程)
      ( sleep 45; kill "$SRV_PID" 2>/dev/null ) &
      WD_PID=$!
      sleep 2
      CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:$SPORT/" 2>/dev/null)
      if [ "$CODE" = "200" ]; then
        timeout 60 python _utils/screenshot_capture.py --url "http://127.0.0.1:$SPORT/" --out figures/shot_home.png --width 1280 --height 800 --wait-ms 1500 >/dev/null 2>&1
        [ -f figures/shot_home.png ] && { echo "✅ figures/shot_home.png"; SHOT_N=$((SHOT_N+1)); }
      else
        echo "⚠ 静态服务探活失败(HTTP=$CODE), 跳过截图"
      fi
      # ⛔ 立即杀静态服务 + 关看门狗, 不留后台进程
      kill "$SRV_PID" 2>/dev/null
      sleep 1
      kill -0 "$SRV_PID" 2>/dev/null && taskkill //PID "$SRV_PID" //F //T >/dev/null 2>&1
      kill "$WD_PID" 2>/dev/null
    fi
  fi
  echo "界面截图完成: 共 $SHOT_N 张(存 figures/shot_*.png)"
fi
```

## 任务

按上面套路跑一遍，把结果如实写进 `TEST_REPORT.md`。核对 REQUIREMENTS 的必做功能是否都实现了。

## 产出（TEST_REPORT.md，固定小节）

```markdown
# 自测报告

## 依赖安装
（后端 pip / 前端 npm install 结果：成功/失败+原因）

## 服务启动
（后端 uvicorn 探活结果：HTTP 状态码；前端 build 结果）

## 功能验证
（逐条核对 REQUIREMENTS 必做功能：已实现/未实现/部分）

## 修复记录
（自测中发现并修复了什么）

## 已知问题
（还存在的问题，供用户知晓）
```

## 完成铁律

- `TEST_REPORT.md` ≥ 500 字节，五个小节齐全，如实记录（不许编造"全部通过"）。
- ⛔ 结束前确认**没有遗留的后台服务进程**（该 pkill 的都杀了）。

⛔ **结束前必跑产出验证**：
```bash
echo "=== 自测报告产出验证 ==="
PASS=true
[ -f TEST_REPORT.md ] && SZ=$(wc -c < TEST_REPORT.md) || SZ=0
if [ "$SZ" -ge 500 ]; then echo "OK TEST_REPORT.md ($SZ bytes)"; else echo "FAIL TEST_REPORT.md 过小 ($SZ)"; PASS=false; fi
for sec in "## 依赖安装" "## 服务启动" "## 功能验证" "## 修复记录" "## 已知问题"; do
  grep -qF "$sec" TEST_REPORT.md 2>/dev/null && echo "OK 小节: $sec" || { echo "FAIL 缺小节: $sec"; PASS=false; }
done
# 确认没有遗留后台服务(三框架 + 截图静态服务都查: uvicorn/flask app.py/node/http.server)
if pgrep -f "uvicorn main:app --host 127.0.0.1 --port 87" >/dev/null 2>&1 \
   || pgrep -f "python app.py" >/dev/null 2>&1 \
   || pgrep -f "http.server 875" >/dev/null 2>&1; then
  echo "WARN 有遗留后台服务(uvicorn/flask/截图静态服务), 请 pkill"
else
  echo "OK 无遗留服务进程"
fi
# 截图产物提示(有界面的项目应有 shot_*.png; 无则报告退占位符, 不算 FAIL)
if ls figures/shot_*.png >/dev/null 2>&1; then
  echo "OK 界面截图: $(ls figures/shot_*.png | wc -l) 张(dev-report 可复用)"
else
  echo "INFO 无界面截图(cli/script 或截图不可用), 报告将用占位符"
fi
[ "$PASS" != true ] && echo "产出验证失败 — 必须补全后重跑, 不要结束本步骤"
```
验证失败就继续补全，不要 end_turn。
