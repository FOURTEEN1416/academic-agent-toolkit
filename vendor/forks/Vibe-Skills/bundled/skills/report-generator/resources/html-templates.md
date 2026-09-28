# HTML 报告模板资源

本文件包含用于生成交互式 HTML 报告的完整模板和样式。

## 📋 模板索引

1. [基础 HTML 结构](#1-基础-html-结构)
2. [CSS 样式库](#2-css-样式库)
3. [交互式组件](#3-交互式组件)
4. [完整报告模板](#4-完整报告模板)
5. [导出功能脚本](#5-导出功能脚本)

---

## 1. 基础 HTML 结构

### HTML5 模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{报告描述}">
    <title>{报告标题} - {域名}</title>

    <!-- 样式表 -->
    <link rel="stylesheet" href="styles.css">

    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <!-- 导航栏 -->
    <nav class="navbar">
        <div class="nav-brand">
            <h1>🤖 GEO 报告系统</h1>
        </div>
        <div class="nav-links">
            <a href="#summary">执行摘要</a>
            <a href="#engines">引擎表现</a>
            <a href="#competitors">竞争对手</a>
            <a href="#recommendations">优化建议</a>
        </div>
    </nav>

    <!-- 主容器 -->
    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <h1>{报告标题}</h1>
            <p class="meta">
                域名：<span class="domain">{域名}</span> |
                报告周期：<span class="period">{开始日期} 至 {结束日期}</span> |
                生成时间：<span class="timestamp">{时间戳}</span>
            </p>
        </header>

        <!-- 主内容 -->
        <main>
            {内容章节}
        </main>

        <!-- 页脚 -->
        <footer class="footer">
            <p>由 Claude Code SEO Assistant 生成 | <a href="#">查看在线版本</a></p>
        </footer>
    </div>

    <!-- 脚本 -->
    <script src="scripts.js"></script>
</body>
</html>
```

---

## 2. CSS 样式库

### 完整样式表（styles.css）

```css
/* ========================================
   基础重置和变量
   ======================================== */
:root {
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --success-color: #4CAF50;
    --warning-color: #FF9800;
    --danger-color: #F44336;
    --info-color: #2196F3;
    --text-color: #333;
    --text-light: #666;
    --bg-light: #f5f5f5;
    --bg-white: #ffffff;
    --border-color: #ddd;
    --shadow-sm: 0 2px 4px rgba(0,0,0,0.1);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
    --shadow-lg: 0 10px 20px rgba(0,0,0,0.1);
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
    color: var(--text-color);
    background: var(--bg-light);
}

/* ========================================
   导航栏
   ======================================== */
.navbar {
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    color: white;
    padding: 1rem 2rem;
    box-shadow: var(--shadow-md);
    position: sticky;
    top: 0;
    z-index: 1000;
}

.nav-brand h1 {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
}

.nav-links {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
}

.nav-links a {
    color: white;
    text-decoration: none;
    padding: 0.5rem 1rem;
    border-radius: var(--radius-sm);
    transition: background 0.3s;
}

.nav-links a:hover {
    background: rgba(255, 255, 255, 0.1);
}

/* ========================================
   容器
   ======================================== */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

/* ========================================
   头部
   ======================================== */
.header {
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    color: white;
    padding: 3rem 2rem;
    border-radius: var(--radius-lg);
    margin-bottom: 2rem;
    box-shadow: var(--shadow-lg);
}

.header h1 {
    font-size: 2.5rem;
    margin-bottom: 1rem;
}

.header .meta {
    font-size: 1rem;
    opacity: 0.9;
}

.header .meta span {
    font-weight: bold;
}

/* ========================================
   指标卡片网格
   ======================================== */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.metric-card {
    background: var(--bg-white);
    border-radius: var(--radius-md);
    padding: 1.5rem;
    box-shadow: var(--shadow-sm);
    text-align: center;
    transition: transform 0.3s, box-shadow 0.3s;
}

.metric-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--shadow-md);
}

.metric-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.metric-card h3 {
    font-size: 1rem;
    color: var(--text-light);
    margin-bottom: 0.5rem;
}

.metric-value {
    font-size: 2.5rem;
    font-weight: bold;
    color: var(--primary-color);
    margin-bottom: 0.5rem;
}

.metric-trend {
    font-size: 1rem;
    font-weight: bold;
}

.metric-trend.up {
    color: var(--success-color);
}

.metric-trend.down {
    color: var(--danger-color);
}

.metric-trend.stable {
    color: var(--info-color);
}

/* ========================================
   章节样式
   ======================================== */
.section {
    background: var(--bg-white);
    border-radius: var(--radius-md);
    padding: 2rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow-sm);
}

.section h2 {
    font-size: 2rem;
    margin-bottom: 1.5rem;
    color: var(--primary-color);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 0.5rem;
}

.section h3 {
    font-size: 1.5rem;
    margin: 1.5rem 0 1rem;
    color: var(--text-color);
}

/* ========================================
   图表容器
   ======================================== */
.charts-section {
    margin: 2rem 0;
}

.chart-container {
    background: var(--bg-white);
    padding: 2rem;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    margin: 1rem 0;
}

.chart-container h3 {
    margin-bottom: 1rem;
    color: var(--text-color);
}

/* ========================================
   数据表格
   ======================================== */
.data-table {
    overflow-x: auto;
}

.data-table table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
}

.data-table th,
.data-table td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.data-table th {
    background: var(--bg-light);
    font-weight: bold;
    color: var(--text-color);
}

.data-table tr:hover {
    background: var(--bg-light);
}

.trend-up {
    color: var(--success-color);
    font-weight: bold;
}

.trend-down {
    color: var(--danger-color);
    font-weight: bold;
}

/* ========================================
   可展开章节
   ======================================== */
.collapsible-section {
    margin: 1rem 0;
}

.collapsible {
    background: var(--bg-light);
    border: none;
    padding: 1rem 1.5rem;
    font-size: 1.1rem;
    font-weight: bold;
    cursor: pointer;
    width: 100%;
    text-align: left;
    border-radius: var(--radius-sm);
    transition: background 0.3s;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.collapsible:hover {
    background: #e0e0e0;
}

.collapsible.active {
    background: var(--primary-color);
    color: white;
}

.collapsible-content {
    display: none;
    padding: 1.5rem;
    background: var(--bg-white);
    border: 1px solid var(--border-color);
    border-top: none;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm);
}

.collapsible-content.show {
    display: block;
}

/* ========================================
   状态标签
   ======================================== */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: bold;
}

.status-badge.success {
    background: #e8f5e9;
    color: #2e7d32;
}

.status-badge.warning {
    background: #fff3e0;
    color: #ef6c00;
}

.status-badge.danger {
    background: #ffebee;
    color: #c62828;
}

.status-badge.info {
    background: #e3f2fd;
    color: #1565c0;
}

/* ========================================
   进度条
   ======================================== */
.progress-bar {
    width: 100%;
    height: 20px;
    background: var(--bg-light);
    border-radius: 10px;
    overflow: hidden;
    margin: 0.5rem 0;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
    transition: width 0.5s ease;
}

/* ========================================
   按钮样式
   ======================================== */
.button {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 1rem;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.button-primary {
    background: var(--primary-color);
    color: white;
}

.button-primary:hover {
    background: #5568d3;
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.button-secondary {
    background: var(--info-color);
    color: white;
}

.button-secondary:hover {
    background: #1976d2;
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.button-success {
    background: var(--success-color);
    color: white;
}

.button-success:hover {
    background: #388e3c;
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

/* ========================================
   导出按钮组
   ======================================== */
.export-buttons {
    display: flex;
    gap: 1rem;
    justify-content: center;
    margin: 2rem 0;
    flex-wrap: wrap;
}

/* ========================================
   页脚
   ======================================== */
.footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-light);
    border-top: 1px solid var(--border-color);
    margin-top: 3rem;
}

.footer a {
    color: var(--primary-color);
    text-decoration: none;
}

.footer a:hover {
    text-decoration: underline;
}

/* ========================================
   响应式设计
   ======================================== */
@media (max-width: 768px) {
    .navbar {
        padding: 1rem;
    }

    .nav-links {
        gap: 1rem;
    }

    .header {
        padding: 2rem 1rem;
    }

    .header h1 {
        font-size: 1.8rem;
    }

    .metrics-grid {
        grid-template-columns: 1fr;
    }

    .container {
        padding: 1rem;
    }

    .section {
        padding: 1.5rem;
    }

    .export-buttons {
        flex-direction: column;
    }

    .button {
        width: 100%;
        justify-content: center;
    }
}

/* ========================================
   打印样式
   ======================================== */
@media print {
    .navbar,
    .export-buttons,
    .footer {
        display: none;
    }

    .container {
        max-width: 100%;
    }

    .section {
        page-break-inside: avoid;
    }

    .collapsible-content {
        display: block !important;
    }
}
```

---

## 3. 交互式组件

### 可展开章节

```html
<section class="collapsible-section">
    <button class="collapsible" onclick="toggleSection(this)">
        <span>▼</span> ChatGPT 详细分析
    </button>
    <div class="collapsible-content">
        <h3>可见性评分：68/100</h3>
        <p>ChatGPT 在过去 30 天中引用了您的内容 234 次，增长了 18%。</p>
        <!-- 更多内容 -->
    </div>
</section>

<script>
function toggleSection(button) {
    button.classList.toggle('active');
    const content = button.nextElementSibling;
    const icon = button.querySelector('span');

    if (content.classList.contains('show')) {
        content.classList.remove('show');
        icon.textContent = '▼';
    } else {
        content.classList.add('show');
        icon.textContent = '▲';
    }
}
</script>
```

### 数据筛选器

```html
<div class="filter-section">
    <h3>数据筛选</h3>
    <div class="filter-group">
        <label for="engine-filter">AI 引擎：</label>
        <select id="engine-filter" onchange="filterData()">
            <option value="all">全部引擎</option>
            <option value="chatgpt">ChatGPT</option>
            <option value="claude">Claude</option>
            <option value="perplexity">Perplexity</option>
            <option value="google-sge">Google SGE</option>
        </select>
    </div>
    <div class="filter-group">
        <label for="period-filter">时间周期：</label>
        <select id="period-filter" onchange="filterData()">
            <option value="30">30 天</option>
            <option value="60">60 天</option>
            <option value="90">90 天</option>
        </select>
    </div>
</div>

<script>
function filterData() {
    const engine = document.getElementById('engine-filter').value;
    const period = document.getElementById('period-filter').value;

    // 过滤数据并更新图表
    updateCharts(engine, period);
}
</script>
```

### 数据钻取

```html
<div class="data-drilldown">
    <table id="main-table">
        <thead>
            <tr>
                <th>引擎</th>
                <th>可见性</th>
                <th>引用次数</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>ChatGPT</td>
                <td>68/100</td>
                <td>234</td>
                <td><button class="button button-secondary" onclick="showDetails('chatgpt')">查看详情</button></td>
            </tr>
            <!-- 更多行 -->
        </tbody>
    </table>
</div>

<!-- 详情模态框 -->
<div id="details-modal" class="modal">
    <div class="modal-content">
        <span class="close" onclick="closeModal()">&times;</span>
        <h2 id="modal-title">详细信息</h2>
        <div id="modal-body"></div>
    </div>
</div>

<script>
function showDetails(engine) {
    const modal = document.getElementById('details-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    title.textContent = engine.toUpperCase() + ' 详细分析';
    body.innerHTML = `
        <h3>引用趋势</h3>
        <!-- 详细数据 -->
    `;

    modal.style.display = 'block';
}

function closeModal() {
    document.getElementById('details-modal').style.display = 'none';
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('details-modal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}
</script>

<style>
.modal {
    display: none;
    position: fixed;
    z-index: 2000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
}

.modal-content {
    background-color: #fefefe;
    margin: 5% auto;
    padding: 20px;
    border: 1px solid #888;
    width: 80%;
    max-width: 800px;
    border-radius: 8px;
}

.close {
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
}

.close:hover {
    color: #000;
}
</style>
```

---

## 4. 完整报告模板

### GEO 综合报告模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GEO 综合报告 - yoursite.com</title>
    <link rel="stylesheet" href="styles.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <!-- 导航栏 -->
    <nav class="navbar">
        <div class="nav-brand">
            <h1>🤖 GEO 报告系统</h1>
        </div>
        <div class="nav-links">
            <a href="#summary">执行摘要</a>
            <a href="#engines">引擎表现</a>
            <a href="#competitors">竞争对手</a>
            <a href="#recommendations">优化建议</a>
        </div>
    </nav>

    <!-- 主容器 -->
    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <h1>🤖 GEO 综合报告</h1>
            <p class="meta">
                域名：<span class="domain">yoursite.com</span> |
                报告周期：<span class="period">2024-01-15 至 2024-02-15（30 天）</span> |
                生成时间：<span class="timestamp">2024-02-15 10:30</span>
            </p>
        </header>

        <!-- 执行摘要 -->
        <section id="summary" class="section">
            <h2>📊 执行摘要</h2>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-icon">📈</div>
                    <h3>整体 GEO 评分</h3>
                    <div class="metric-value">72/100</div>
                    <div class="metric-trend up">⬆️ +12</div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon">🤖</div>
                    <h3>AI 引用次数</h3>
                    <div class="metric-value">677</div>
                    <div class="metric-trend up">⬆️ +45%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon">🏆</div>
                    <h3>行业排名</h3>
                    <div class="metric-value">Top 10%</div>
                    <div class="metric-trend up">⬆️ +15%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon">📊</div>
                    <h3>月度增长</h3>
                    <div class="metric-value">+45%</div>
                    <div class="metric-trend up">✅ 达标</div>
                </div>
            </div>
        </section>

        <!-- 可视化图表 -->
        <section class="charts-section">
            <h2>📈 引用趋势分析</h2>
            <div class="chart-container">
                <canvas id="trendChart"></canvas>
            </div>
        </section>

        <!-- 引擎表现 -->
        <section id="engines" class="section">
            <h2>🤖 各引擎表现</h2>

            <!-- ChatGPT -->
            <div class="collapsible-section">
                <button class="collapsible" onclick="toggleSection(this)">
                    <span>▼</span> ChatGPT 表现详情
                </button>
                <div class="collapsible-content">
                    <h3>可见性评分：68/100 ⬆️ +18%</h3>
                    <p>ChatGPT 在过去 30 天中引用了您的内容 234 次，平均排名 Top 5。</p>
                    <!-- 详细数据 -->
                </div>
            </div>

            <!-- Claude -->
            <div class="collapsible-section">
                <button class="collapsible" onclick="toggleSection(this)">
                    <span>▼</span> Claude 表现详情
                </button>
                <div class="collapsible-content">
                    <h3>可见性评分：75/100 ⬆️ +22%</h3>
                    <p>Claude 在过去 30 天中引用了您的内容 189 次，平均排名 Top 3。</p>
                    <!-- 详细数据 -->
                </div>
            </div>
        </section>

        <!-- 导出按钮 -->
        <div class="export-buttons">
            <button class="button button-primary" onclick="exportPDF()">
                📄 导出 PDF
            </button>
            <button class="button button-secondary" onclick="exportExcel()">
                📊 导出 Excel
            </button>
            <button class="button button-success" onclick="printReport()">
                🖨️ 打印报告
            </button>
        </div>
    </div>

    <script>
        // 初始化趋势图表
        const trendChart = new Chart(document.getElementById('trendChart'), {
            type: 'line',
            data: {
                labels: ['Day 1', 'Day 5', 'Day 10', 'Day 15', 'Day 20', 'Day 25', 'Day 30'],
                datasets: [{
                    label: 'ChatGPT',
                    data: [156, 168, 175, 182, 195, 210, 234],
                    borderColor: '#00FF00',
                    backgroundColor: 'rgba(0, 255, 0, 0.1)',
                    tension: 0.4,
                    fill: true
                }, {
                    label: 'Claude',
                    data: [120, 135, 148, 155, 168, 178, 189],
                    borderColor: '#FF6B6B',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: '引用次数'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: '时间'
                        }
                    }
                }
            }
        });

        // 可展开章节交互
        function toggleSection(button) {
            button.classList.toggle('active');
            const content = button.nextElementSibling;
            const icon = button.querySelector('span');

            if (content.classList.contains('show')) {
                content.classList.remove('show');
                icon.textContent = '▼';
            } else {
                content.classList.add('show');
                icon.textContent = '▲';
            }
        }

        // 导出功能
        function exportPDF() {
            window.print();
        }

        function exportExcel() {
            alert('Excel 导出功能开发中');
        }

        function printReport() {
            window.print();
        }
    </script>
</body>
</html>
```

---

## 5. 导出功能脚本

### 完整导出脚本（export.js）

```javascript
// 导出为 PDF
function exportPDF() {
    // 使用浏览器原生打印功能
    window.print();

    // 或使用 jsPDF 库
    // const { jsPDF } = window.jspdf;
    // const doc = new jsPDF();
    // doc.html(document.body, {
    //     callback: function(doc) {
    //         doc.save('report.pdf');
    //     }
    // });
}

// 导出为 Excel
function exportExcel() {
    // 需要 SheetJS 库
    // https://cdn.sheetjs.com/xlsx-latest/package/dist/xlsx.full.min.js

    const data = [
        ['引擎', '可见性', '引用次数', '趋势'],
        ['ChatGPT', 68, 234, '+18%'],
        ['Claude', 75, 189, '+22%'],
        ['Perplexity', 70, 156, '+15%'],
        ['Google SGE', 55, 98, '稳定']
    ];

    const ws = XLSX.utils.aoa_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'GEO Report');
    XLSX.writeFile(wb, 'geo-report.xlsx');
}

// 导出为 JSON
function exportJSON() {
    const reportData = {
        reportId: 'geo-comprehensive-20240215',
        timestamp: '2024-02-15T10:30:00Z',
        domain: 'yoursite.com',
        scores: {
            overall: 72,
            chatgpt: 68,
            claude: 75,
            perplexity: 70,
            google_sge: 55
        },
        citations: {
            chatgpt: 234,
            claude: 189,
            perplexity: 156,
            google_sge: 98
        }
    };

    const dataStr = JSON.stringify(reportData, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'geo-report.json';
    link.click();
}

// 打印报告
function printReport() {
    window.print();
}

// 复制到剪贴板
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    const text = element.innerText;

    navigator.clipboard.writeText(text).then(() => {
        alert('已复制到剪贴板！');
    }).catch(err => {
        console.error('复制失败:', err);
    });
}

// 分享报告
function shareReport() {
    if (navigator.share) {
        navigator.share({
            title: 'GEO 综合报告',
            text: '查看您的 GEO 优化报告',
            url: window.location.href
        }).then(() => {
            console.log('分享成功');
        }).catch(err => {
            console.log('分享取消:', err);
        });
    } else {
        alert('您的浏览器不支持分享功能');
    }
}

// 生成报告链接
function generateReportLink() {
    const url = window.location.href;
    const link = `<a href="${url}">查看 GEO 报告</a>`;

    navigator.clipboard.writeText(link).then(() => {
        alert('报告链接已复制到剪贴板！');
    });
}

// 发送邮件
function emailReport() {
    const subject = encodeURIComponent('GEO 综合报告 - yoursite.com');
    const body = encodeURIComponent('请查看附件中的 GEO 综合报告。\n\n报告链接：' + window.location.href);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
}
```

---

**资源版本：** 1.0.0
**最后更新：** 2024-01-15
**维护者：** report-generator skill

**使用说明：**
1. 复制所需的模板代码
2. 根据需要自定义样式和内容
3. 在 HTML 报告中引用
4. 确保所有依赖库（Chart.js）已加载
