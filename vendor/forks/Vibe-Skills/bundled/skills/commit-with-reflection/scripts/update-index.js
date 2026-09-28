#!/usr/bin/env node

/**
 * 反思报告索引更新脚本
 *
 * 功能:
 * - 扫描 docs/reflections/ 目录下的所有报告
 * - 提取报告元数据(日期、类型、错误数等)
 * - 生成分类索引(按日期、类型、错误类型、文件路径)
 * - 更新 docs/reflections/INDEX.md
 *
 * 使用方法:
 * node scripts/update-index.js
 */

const fs = require('fs');
const path = require('path');

// 配置
const REFLECTIONS_DIR = path.join(process.cwd(), 'docs', 'reflections');
const INDEX_FILE = path.join(REFLECTIONS_DIR, 'INDEX.md');

/**
 * 扫描反思报告目录
 */
function scanReports(dir) {
  const reports = [];

  if (!fs.existsSync(dir)) {
    console.log(`目录不存在: ${dir}`);
    return reports;
  }

  function scanDirectory(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        // 递归扫描子目录
        scanDirectory(fullPath);
      } else if (entry.isFile() && entry.name.endsWith('.md') && entry.name !== 'INDEX.md') {
        // 解析报告文件
        const report = parseReport(fullPath);
        if (report) {
          reports.push(report);
        }
      }
    }
  }

  scanDirectory(dir);
  return reports;
}

/**
 * 解析报告文件,提取元数据
 */
function parseReport(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const relativePath = path.relative(REFLECTIONS_DIR, filePath).replace(/\\/g, '/');

    // 从文件名提取信息
    const fileName = path.basename(filePath, '.md');
    const match = fileName.match(/^(\d+)_(\w+)_(.+)$/);

    if (!match) {
      console.warn(`文件名格式不正确: ${fileName}`);
      return null;
    }

    const [, day, type, desc] = match;

    // 从路径提取年月
    const dirName = path.basename(path.dirname(filePath));
    const yearMonthMatch = dirName.match(/^(\d{4})-(\d{2})$/);

    if (!yearMonthMatch) {
      console.warn(`目录名格式不正确: ${dirName}`);
      return null;
    }

    const [, year, month] = yearMonthMatch;
    const date = `${year}-${month}-${day}`;

    // 从内容提取元数据
    const metadata = extractMetadata(content);

    return {
      path: relativePath,
      fileName,
      date,
      year,
      month,
      day,
      type,
      description: desc.replace(/-/g, ' '),
      ...metadata
    };
  } catch (error) {
    console.error(`解析报告失败: ${filePath}`, error);
    return null;
  }
}

/**
 * 从报告内容提取元数据
 */
function extractMetadata(content) {
  const metadata = {
    totalErrors: 0,
    criticalErrors: 0,
    iterations: 0,
    duration: 0,
    filesModified: 0,
    errorTypes: [],
    tags: [],
    modifiedFiles: []
  };

  // 提取总错误数
  const totalErrorsMatch = content.match(/总错误数:\s*(\d+)/);
  if (totalErrorsMatch) {
    metadata.totalErrors = parseInt(totalErrorsMatch[1], 10);
  }

  // 提取严重错误数
  const criticalErrorsMatch = content.match(/严重错误数:\s*(\d+)/);
  if (criticalErrorsMatch) {
    metadata.criticalErrors = parseInt(criticalErrorsMatch[1], 10);
  }

  // 提取迭代次数
  const iterationsMatch = content.match(/调试迭代次数:\s*(\d+)/);
  if (iterationsMatch) {
    metadata.iterations = parseInt(iterationsMatch[1], 10);
  }

  // 提取会话时长
  const durationMatch = content.match(/会话时长:\s*(\d+)\s*分钟/);
  if (durationMatch) {
    metadata.duration = parseInt(durationMatch[1], 10);
  }

  // 提取修改文件数
  const filesMatch = content.match(/修改文件数:\s*(\d+)/);
  if (filesMatch) {
    metadata.filesModified = parseInt(filesMatch[1], 10);
  }

  // 提取错误类型
  const errorTypeMatches = content.matchAll(/###\s*错误\s*\d+:\s*(.+)/g);
  for (const match of errorTypeMatches) {
    const errorType = match[1].trim();
    if (!metadata.errorTypes.includes(errorType)) {
      metadata.errorTypes.push(errorType);
    }
  }

  // 提取修改的文件路径
  const fileMatches = content.matchAll(/^-\s*`([^`]+)`/gm);
  for (const match of fileMatches) {
    const filePath = match[1].trim();
    if (filePath && !metadata.modifiedFiles.includes(filePath)) {
      metadata.modifiedFiles.push(filePath);
    }
  }

  // 提取标签(从文件路径推断)
  metadata.tags = extractTags(metadata.modifiedFiles);

  return metadata;
}

/**
 * 从文件路径提取标签
 */
function extractTags(filePaths) {
  const tags = new Set();

  for (const filePath of filePaths) {
    // 提取技术栈标签
    if (filePath.endsWith('.tsx') || filePath.endsWith('.jsx')) {
      tags.add('React');
    }
    if (filePath.endsWith('.ts') || filePath.endsWith('.tsx')) {
      tags.add('TypeScript');
    }
    if (filePath.endsWith('.js') || filePath.endsWith('.jsx')) {
      tags.add('JavaScript');
    }
    if (filePath.includes('server/')) {
      tags.add('Backend');
    }
    if (filePath.includes('client/')) {
      tags.add('Frontend');
    }
    if (filePath.includes('test') || filePath.includes('spec')) {
      tags.add('Testing');
    }
    if (filePath.includes('api') || filePath.includes('router')) {
      tags.add('API');
    }
    if (filePath.includes('db') || filePath.includes('database')) {
      tags.add('Database');
    }

    // 提取功能模块标签
    const parts = filePath.split('/');
    for (const part of parts) {
      if (part.length > 3 && !part.includes('.')) {
        // 首字母大写
        const tag = part.charAt(0).toUpperCase() + part.slice(1);
        if (tag.length < 20) { // 避免过长的标签
          tags.add(tag);
        }
      }
    }
  }

  return Array.from(tags);
}

/**
 * 生成索引内容
 */
function generateIndex(reports) {
  const now = new Date();
  const timestamp = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });

  // 统计
  const stats = {
    total: reports.length,
    byType: {},
    totalErrors: 0,
    totalIterations: 0
  };

  for (const report of reports) {
    stats.byType[report.type] = (stats.byType[report.type] || 0) + 1;
    stats.totalErrors += report.totalErrors;
    stats.totalIterations += report.iterations;
  }

  // 按日期排序(最新的在前)
  const byDate = [...reports].sort((a, b) => b.date.localeCompare(a.date));

  // 按类型分组
  const byType = {};
  for (const report of reports) {
    if (!byType[report.type]) {
      byType[report.type] = [];
    }
    byType[report.type].push(report);
  }

  // 按错误类型分组
  const byErrorType = {};
  for (const report of reports) {
    for (const errorType of report.errorTypes) {
      if (!byErrorType[errorType]) {
        byErrorType[errorType] = [];
      }
      byErrorType[errorType].push(report);
    }
  }

  // 按文件路径分组
  const byFile = {};
  for (const report of reports) {
    for (const file of report.modifiedFiles) {
      // 提取目录路径
      const dir = path.dirname(file);
      if (!byFile[dir]) {
        byFile[dir] = [];
      }
      if (!byFile[dir].find(r => r.path === report.path)) {
        byFile[dir].push(report);
      }
    }
  }

  // 收集所有标签
  const allTags = new Set();
  for (const report of reports) {
    for (const tag of report.tags) {
      allTags.add(tag);
    }
  }

  // 生成Markdown
  let markdown = `# 反思报告索引\n\n`;
  markdown += `**最后更新**: ${timestamp}\n`;
  markdown += `**报告总数**: ${stats.total}\n\n`;

  // 统计概览
  markdown += `## 统计概览\n\n`;
  markdown += `- 功能开发 (feature): ${stats.byType.feature || 0} 个报告\n`;
  markdown += `- 错误修复 (bugfix): ${stats.byType.bugfix || 0} 个报告\n`;
  markdown += `- 重构 (refactor): ${stats.byType.refactor || 0} 个报告\n`;
  markdown += `- 文档 (docs): ${stats.byType.docs || 0} 个报告\n`;
  markdown += `- 总错误数: ${stats.totalErrors}\n`;
  markdown += `- 总迭代次数: ${stats.totalIterations}\n\n`;

  // 按日期排序
  markdown += `## 按日期排序\n\n`;
  let currentYearMonth = '';
  for (const report of byDate) {
    const yearMonth = `${report.year}年${parseInt(report.month, 10)}月`;
    if (yearMonth !== currentYearMonth) {
      markdown += `\n### ${yearMonth}\n\n`;
      currentYearMonth = yearMonth;
    }
    markdown += `- [${report.date} - ${report.description}](${report.path}) - ${getTypeLabel(report.type)}\n`;
    markdown += `  - 错误数: ${report.totalErrors} | 严重: ${report.criticalErrors} | 迭代: ${report.iterations}\n`;
    if (report.tags.length > 0) {
      markdown += `  - 标签: ${report.tags.map(t => `\`${t}\``).join(', ')}\n`;
    }
  }

  // 按类型分类
  markdown += `\n## 按类型分类\n\n`;
  for (const [type, typeReports] of Object.entries(byType)) {
    markdown += `### ${getTypeLabel(type)}\n\n`;
    for (const report of typeReports.sort((a, b) => b.date.localeCompare(a.date))) {
      markdown += `- [${report.date} - ${report.description}](${report.path})\n`;
    }
    markdown += `\n`;
  }

  // 按错误类型分类
  if (Object.keys(byErrorType).length > 0) {
    markdown += `## 按错误类型分类\n\n`;
    for (const [errorType, errorReports] of Object.entries(byErrorType)) {
      markdown += `### ${errorType}\n\n`;
      for (const report of errorReports.sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5)) {
        markdown += `- [${report.date} - ${report.description}](${report.path})\n`;
      }
      markdown += `\n`;
    }
  }

  // 按文件路径索引
  if (Object.keys(byFile).length > 0) {
    markdown += `## 按文件路径索引\n\n`;
    const sortedDirs = Object.keys(byFile).sort();
    for (const dir of sortedDirs.slice(0, 10)) { // 只显示前10个目录
      markdown += `### ${dir}/\n\n`;
      for (const report of byFile[dir].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 3)) {
        markdown += `- [${report.date} - ${report.description}](${report.path})\n`;
      }
      markdown += `\n`;
    }
  }

  // 搜索标签
  markdown += `## 搜索标签\n\n`;
  markdown += Array.from(allTags).sort().map(tag => `\`${tag}\``).join(' ') + '\n';

  return markdown;
}

/**
 * 获取类型标签
 */
function getTypeLabel(type) {
  const labels = {
    feature: '功能开发',
    bugfix: '错误修复',
    refactor: '重构',
    docs: '文档'
  };
  return labels[type] || type;
}

/**
 * 主函数
 */
function main() {
  console.log('开始扫描反思报告...');

  const reports = scanReports(REFLECTIONS_DIR);
  console.log(`找到 ${reports.length} 个报告`);

  if (reports.length === 0) {
    console.log('没有找到报告,跳过索引生成');
    return;
  }

  console.log('生成索引...');
  const indexContent = generateIndex(reports);

  // 确保目录存在
  if (!fs.existsSync(REFLECTIONS_DIR)) {
    fs.mkdirSync(REFLECTIONS_DIR, { recursive: true });
  }

  // 写入索引文件
  fs.writeFileSync(INDEX_FILE, indexContent, 'utf-8');
  console.log(`索引已更新: ${INDEX_FILE}`);
}

// 执行
if (require.main === module) {
  main();
}

module.exports = { scanReports, parseReport, generateIndex };
