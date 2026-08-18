#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const CORE = path.join(ROOT, 'codesucker-core', 'packages', 'core', 'src', 'index.ts');

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) throw new Error(`unexpected argument: ${token}`);
    const key = token.slice(2);
    const value = argv[i + 1];
    if (!value || value.startsWith('--')) throw new Error(`missing value for --${key}`);
    args[key] = value;
    i += 1;
  }
  if (!args.config || !args.workspace) throw new Error('--config and --workspace are required');
  return args;
}

function inside(parent, candidate) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}

function writeJson(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(stable(value), null, 2)}\n`, 'utf8');
}

async function main() {
  const args = parseArgs(process.argv);
  const configPath = path.resolve(args.config);
  const workspace = path.resolve(args.workspace);
  fs.mkdirSync(workspace, { recursive: true });
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const projectRoot = path.resolve(config.root);
  if (!fs.statSync(projectRoot).isDirectory()) throw new Error('config.root must be a directory');
  const outputDir = path.resolve(workspace, config.outputDir || 'source-materials');
  if (!inside(workspace, outputDir)) throw new Error('outputDir escapes workspace');
  const temp = `${outputDir}.tmp-${process.pid}`;
  fs.rmSync(temp, { recursive: true, force: true });
  fs.mkdirSync(temp, { recursive: true });

  const core = await import(pathToFileURL(CORE).href);
  const version = fs.readFileSync(path.join(ROOT, 'codesucker-core', 'packages', 'core', 'src', 'version.ts'), 'utf8');
  const coreFiles = [];
  for (const file of fs.readdirSync(path.join(ROOT, 'codesucker-core', 'packages', 'core', 'src'))) {
    const full = path.join(ROOT, 'codesucker-core', 'packages', 'core', 'src', file);
    if (file.endsWith('.ts')) coreFiles.push(sha256(fs.readFileSync(full)));
  }
  const normalized = {
    ...config,
    schemaVersion: config.schemaVersion ?? 1,
    root: projectRoot,
    outputDir: 'source-materials',
  };
  const defaults = {
    removeComments: true, removeBlankLines: true, maskSensitive: true,
    wrapLongLines: true, maxLineWidth: 78, tabWidth: 4,
  };
  const projectConfig = {
    root: projectRoot, title: String(config.title || ''), owner: config.owner || undefined,
    foundedDate: config.foundedDate || undefined,
    extensions: (config.extensions || []).map((x) => String(x).replace(/^\./, '')),
    excludes: config.excludes || [], sortMode: config.sortMode || 'entry',
    clean: { ...defaults, ...(config.clean || {}) }, linesPerPage: config.linesPerPage || 50,
    maxPages: config.maxPages || 60,
  };
  const discoveredByExtension = projectConfig.extensions.flatMap((extension) => (
    core.discover(projectRoot, [extension], projectConfig.excludes)
  ));
  const uniqueFiles = new Map(discoveredByExtension.map((file) => [file.relPath, file]));
  let files = [...uniqueFiles.values()];
  files = core.sortFiles(files, projectConfig.sortMode);
  const result = await core.processFilesAsync(files, projectConfig, { concurrency: config.concurrency || 4 });
  const renderOptions = {
    title: projectConfig.title, fontName: config.fontName || '宋体', fontSizePt: config.fontSizePt || 10.5,
    outDir: path.join(temp, 'rendered'), baseName: config.baseName || '源程序',
  };
  const rendered = [];
  if (result.selection.pages.length) {
    rendered.push(await core.renderDocx(result.selection.pages, renderOptions));
    rendered.push(core.renderTxt(result.selection.pages, renderOptions));
  }
  const relative = (file) => path.relative(temp, file).replaceAll('\\', '/');
  writeJson(path.join(temp, 'files.json'), {
    files: files.map(({ path: _absolute, ...file }) => file),
    sourceMode: config.sourceMode || 'real',
  });
  writeJson(path.join(temp, 'cleaned.json'), {
    cleaned: result.cleaned.map((file) => ({
      ...file,
      entry: (() => { const { path: _absolute, ...entry } = file.entry; return entry; })(),
    })),
  });
  writeJson(path.join(temp, 'selection.json'), result.selection);
  writeJson(path.join(temp, 'audit.json'), result.auditItems);
  writeJson(path.join(temp, 'stats.json'), { ...result.stats, errors: result.errors });
  const manifest = {
    schemaVersion: 1, backend: 'vendored-codesucker-core', sourceMode: config.sourceMode || 'real',
    coreVersion: '0.4.4', coreCommit: 'b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c',
    rulesVersion: (version.match(/RULES_VERSION\s*=\s*['"]([^'"]+)/) || [])[1] || 'unknown',
    config: normalized, configSha256: sha256(JSON.stringify(stable(normalized))), coreSha256: sha256(coreFiles.join('')),
    projectRoot, outputDir: 'source-materials', audit: result.auditItems, errors: result.errors,
    rendered: rendered.map((file) => `source-materials/${relative(file)}`),
  };
  writeJson(path.join(temp, 'SOURCE_MATERIALS_MANIFEST.json'), manifest);
  fs.writeFileSync(path.join(temp, 'SOURCE_MATERIALS_REPORT.md'), `# 源程序材料报告\n\n- backend: ${manifest.backend}\n- core: ${manifest.coreVersion}\n- rules: ${manifest.rulesVersion}\n- files: ${result.stats.totalFiles}\n- pages: ${result.stats.estimatedPages}\n- audit: ${result.auditItems.map((x) => x.status).join(', ')}\n`, 'utf8');
  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.renameSync(temp, outputDir);
  process.stdout.write(`${JSON.stringify({ ok: true, manifest: path.join('source-materials', 'SOURCE_MATERIALS_MANIFEST.json') })}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
