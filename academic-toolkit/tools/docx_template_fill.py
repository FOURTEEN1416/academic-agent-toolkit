# -*- coding: utf-8 -*-
"""docx_template_fill.py — 把 Markdown 内容填充到用户上传的 .docx 模板。

实现策略：
1. 调用 Node 引擎（md_to_docx.js）把 markdown 渲染成「内容 docx」
   - 复用所有现有渲染能力：OMML 公式 / 三线表 / 上标 / 代码块 / 浅灰底色 / 图片嵌入
2. 打开内容 docx，按章节切元素列表（标题 / 摘要 / 关键词 / 正文 / 参考文献 / 附录）
3. 打开用户模板，启发式找占位段，跨文档深拷贝元素插入到对应位置
4. 跨文档转移图片：复制 word/media/ 下的图片文件 + 注册新 relationship + 重写 rId
5. 保留模板原有的封面表格、页眉页脚、页边距、字体设置

用法：
    python docx_template_fill.py \\
        --template path/to/template.docx \\
        --source paper/main.md \\
        --output paper/main.docx \\
        --workspace .
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

log = logging.getLogger('docx_template_fill')

# 本文件是 academic-toolkit/tools/docx_template_fill.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = Path(sys.argv[0]).stem + '.pyc'

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
PIC_NS = 'http://schemas.openxmlformats.org/drawingml/2006/picture'


def _convert_dotx_to_docx(dotx_path: Path) -> Path:
    """把 .dotx (Word 模板，content-type=template.main+xml) 重写为 .docx
    (content-type=document.main+xml)，其他结构原样保留。

    返回：转换后的 .docx 路径（在系统临时目录，进程退出时自动清理）。
    """
    import zipfile as _zip

    if not dotx_path.exists():
        raise FileNotFoundError(dotx_path)

    tmp_root = Path(tempfile.gettempdir()) / 'docx_template_fill_dotx_cache'
    tmp_root.mkdir(parents=True, exist_ok=True)
    out_path = tmp_root / f'{dotx_path.stem}.converted.docx'

    try:
        if out_path.exists() and out_path.stat().st_mtime >= dotx_path.stat().st_mtime:
            return out_path
    except Exception:
        pass

    TEMPLATE_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml'
    DOC_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'

    with _zip.ZipFile(dotx_path, 'r') as zin:
        with _zip.ZipFile(out_path, 'w', _zip.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == '[Content_Types].xml':
                    text = data.decode('utf-8')
                    text = text.replace(TEMPLATE_CT, DOC_CT)
                    data = text.encode('utf-8')
                zout.writestr(item, data)

    return out_path


def _transfer_images(rendered_doc, target_doc, elements_to_transfer: list) -> dict:
    """把 rendered_doc 中被引用的图片复制到 target_doc，并返回 rId 映射 {old_rId: new_rId}。

    流程：
      1. 扫描 elements_to_transfer 中所有 <a:blip r:embed="rIdN">，收集旧 rId 集合
      2. 在 rendered_doc 的关系（part.rels）找到对应 image part
      3. 把这些 image part 的二进制注册到 target_doc 的 part 集合中
      4. target_doc.part.relate_to(image_part, IMAGE_TYPE) 得到新 rId
      5. 返回 old_rId → new_rId 映射
    """

    rendered_part = rendered_doc.part
    target_part = target_doc.part

    rid_map = {}
    embed_attr = f'{{{R_NS}}}embed'
    link_attr = f'{{{R_NS}}}link'

    referenced_rids = set()
    for el in elements_to_transfer:
        for blip in el.iter(f'{{{A_NS}}}blip'):
            r = blip.get(embed_attr)
            if r:
                referenced_rids.add(r)
            r2 = blip.get(link_attr)
            if r2:
                referenced_rids.add(r2)

    if not referenced_rids:
        return rid_map

    log.info('Transferring %d image relationship(s) cross-document', len(referenced_rids))

    for old_rid in referenced_rids:
        src_rels = rendered_part.rels
        if old_rid not in src_rels:
            log.warning('Image rId %s not found in rendered doc rels', old_rid)
            continue
        src_rel = src_rels[old_rid]
        if src_rel.is_external:
            new_rid = target_part.relate_to(src_rel.target_ref, src_rel.reltype, is_external=True)
            rid_map[old_rid] = new_rid
            continue
        src_image_part = src_rel.target_part
        try:
            new_rid = target_part.relate_to(src_image_part, src_rel.reltype)
            rid_map[old_rid] = new_rid
        except Exception as e:
            log.warning('Failed to relate image part %s: %s', getattr(src_image_part, 'partname', '?'), e)
            continue

    return rid_map


def _rewrite_image_rids(elements: list, rid_map: dict):
    """把元素中的旧 rId 改为新 rId（in-place）。"""
    if not rid_map:
        return
    embed_attr = f'{{{R_NS}}}embed'
    link_attr = f'{{{R_NS}}}link'
    for el in elements:
        for blip in el.iter(f'{{{A_NS}}}blip'):
            for attr in (embed_attr, link_attr):
                old = blip.get(attr)
                if old and old in rid_map:
                    blip.set(attr, rid_map[old])


_TITLE_PLACEHOLDER_RE = re.compile('(标题|论文.*?标题|题目).*?[(（](此处|这里|本处)?.*?(填|换成?|为|输入)?.*?[)）]')
_INSTRUCTION_RE = re.compile('^\\s*[(（]?\\s*(注[:：]|说明[:：]|示例[:：]|例如|例[:：])')
_ABSTRACT_RE = re.compile('^\\s*(摘\\s*要|Abstract)\\s*$', re.IGNORECASE)
_KEYWORDS_RE = re.compile('^\\s*\\*{0,2}(关键词|关键字|Key\\s*words?)\\*{0,2}\\s*[：:]', re.IGNORECASE)
_BODY_PLACEHOLDER_RE = re.compile('^\\s*正文\\s*(内容\\s*[(（].*?[)）]?|大纲|.*?(另起|开始).*?|（.*?）|\\(.*?\\))?\\s*$')
_REFERENCES_RE = re.compile('^\\s*(参考文献|References)(\\s|（|\\(|$)', re.IGNORECASE)
_APPENDIX_RE = re.compile('^\\s*(附\\s*录|Appendix)(\\s|（|\\(|$)', re.IGNORECASE)
_ACK_RE = re.compile('^\\s*(致\\s*谢|Acknowledg)', re.IGNORECASE)


def _is_title_placeholder(text: str) -> bool:
    norm = (text or '').strip()
    if not norm:
        return False
    if '标题' in norm and ('此处' in norm or '这里' in norm or '换成' in norm or '填' in norm):
        return True
    return False


def _is_instruction_paragraph(text: str) -> bool:
    norm = (text or '').strip()
    if not norm:
        return False
    if _INSTRUCTION_RE.search(norm):
        return True
    if '(说明' in norm or '（说明' in norm:
        return True
    if '请删除' in norm or '看完后删除' in norm or '删除该' in norm:
        return True
    if '示例段落' in norm or '本段为示例' in norm:
        return True
    if '[编号]' in norm and ('作者' in norm or '文献' in norm):
        return True
    if '参考文献的编号' in norm or '参考文献按' in norm:
        return True
    if '参考文献中' in norm and ('表述方式' in norm or '格式' in norm):
        return True
    if norm.startswith('书籍') and '表述方式' in norm:
        return True
    return False


def _delete_paragraph(p):
    """删除 paragraph 对象。"""
    el = p._element
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _para_text(para_elem) -> str:
    """提取 <w:p> 元素的纯文本（含所有 <w:t>）。"""
    if para_elem is None:
        return ''
    parts = []
    for t in para_elem.iter(f'{{{W_NS}}}t'):
        if t.text:
            parts.append(t.text)
    return ''.join(parts).strip()


def _para_heading_level(para_elem) -> int:
    """从 pStyle 推断 Heading level。1-6 对应 Heading1-Heading6，否则 0。"""
    if para_elem is None:
        return 0
    pStyle = para_elem.find(f'.//{{{W_NS}}}pPr/{{{W_NS}}}pStyle')
    if pStyle is None:
        return 0
    val = pStyle.get(f'{{{W_NS}}}val', '')
    m = re.match('Heading(\\d+)', val)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    if val == 'Title':
        return 1
    return 0


def _render_md_via_node(source_md: Path, output_path: Path, workspace: Optional[Path],
                        style_profile: Optional[Path]) -> Path:
    """调 docx-cn-engine 渲染 markdown 为完整 docx（含 OMML / 三线表 / 上标）。"""
    import importlib.util
    import importlib.machinery

    _tools_dir = Path(__file__).resolve().parent
    _internal_name = '_mh_tools_docx_export_fill_view'

    if _internal_name in sys.modules:
        _mod = sys.modules[_internal_name]
    else:
        _src = _tools_dir / 'docx_export.py'
        if _src.exists():
            _loader = importlib.machinery.SourceFileLoader(_internal_name, str(_src))
        else:
            _src = _tools_dir / 'docx_export.pyc'
            if not _src.exists():
                raise FileNotFoundError(
                    f'docx_export 工具未找到（{_tools_dir}/docx_export.py 和 .pyc 都不存在）')
            _loader = importlib.machinery.SourcelessFileLoader(_internal_name, str(_src))
        _spec = importlib.util.spec_from_loader(_internal_name, _loader, origin=str(_src))
        _mod = importlib.util.module_from_spec(_spec)
        _mod.__file__ = str(_src)
        _mod.__loader__ = _loader
        _mod.__spec__ = _spec
        _tools_str = str(_tools_dir)
        if _tools_str not in sys.path:
            sys.path.insert(0, _tools_str)
        sys.modules[_internal_name] = _mod
        try:
            _spec.loader.exec_module(_mod)
        except Exception:
            sys.modules.pop(_internal_name, None)
            raise

    _convert_with_node = _mod._convert_with_node
    _is_node_engine_available = _mod._is_node_engine_available
    if not _is_node_engine_available():
        raise RuntimeError(
            'Node 引擎不可用：fill 模式需要 docx-cn-engine 才能渲染公式 / 三线表 / 上标。'
            '请检查 tools/docx-cn-engine/node_modules 和 node 可执行文件。')
    return _convert_with_node(source_md, output_path, workspace, style_profile)


def _slice_rendered_doc(rendered: Document) -> dict:
    """按章节切渲染好的 docx，返回 lxml 元素列表（深拷贝过的）。

    sections = {
        'title_text': str,         # 论文标题文本
        'abstract': [<w:p>],       # 摘要段落（不含关键词）
        'keywords': <w:p> or None, # 关键词段落
        'body': [<elem>],          # 正文章节元素（含 H1/H2 标题、段落、表格）
        'references': [<w:p>],
        'appendix': [<elem>],
    }
    """
    body = rendered.element.body
    children = []
    for el in body.iterchildren():
        if el.tag.endswith('}sectPr'):
            continue
        children.append(el)

    sections = {'title_text': '', 'abstract': [], 'keywords': None,
                'body': [], 'references': [], 'appendix': []}
    cur = None
    title_seen = False

    for el in children:
        is_para = el.tag == f'{{{W_NS}}}p'
        text = _para_text(el) if is_para else ''
        level = _para_heading_level(el) if is_para else 0
        norm = text.replace(' ', '').lower() if text else ''

        if is_para and text:
            norm_title = re.sub('^[\\s\\d一二三四五六七八九十\\.、]+', '', norm)
            if norm_title in ('摘要', 'abstract'):
                cur = 'abstract'
                continue
            if norm_title in ('参考文献', 'references', 'reference'):
                cur = 'references'
                continue
            if norm_title in ('附录', 'appendix') or re.match('^附录[a-z\\d一二三四五六]{1,4}$', norm_title) or norm_title.startswith('appendix'):
                cur = 'appendix'
                continue
            if norm_title in ('致谢',) or norm_title.startswith('acknowledg'):
                cur = 'ack'
                sections['body'].append(el)
                continue

        if is_para and text and not title_seen:
            sections['title_text'] = text
            title_seen = True
            continue

        if is_para and text and level >= 1:
            cur = 'body'
            sections['body'].append(el)
            continue

        if cur == 'abstract' and is_para and _KEYWORDS_RE.match(text):
            sections['keywords'] = el
            continue

        if cur == 'abstract':
            if is_para and not text:
                continue
            sections['abstract'].append(el)
            continue

        if cur == 'body':
            sections['body'].append(el)
            continue

        if cur == 'references':
            if is_para:
                if text.strip():
                    sections['references'].append(el)
                continue
            sections['references'].append(el)
            continue

        if cur == 'appendix':
            sections['appendix'].append(el)
            continue

        if cur == 'ack':
            if is_para and not text:
                sections['body'].append(el)
            continue

        if is_para and text.strip():
            sections['body'].append(el)

    return sections


def _clean_style_refs(elem):
    """清理元素中可能引用的不存在的样式 ID（避免 Word 警告）。

    Heading1-6 / Title 这些通用样式名一般在所有 Word 文档中都存在，
    自定义样式 ID 可能冲突，统一保留 Heading 系列，去掉非通用 pStyle。
    """
    KEEP_STYLES = {'Heading1', 'Heading2', 'Heading3', 'Heading4', 'Heading5', 'Heading6', 'Title'}
    for pStyle in list(elem.iter(f'{{{W_NS}}}pStyle')):
        val = pStyle.get(f'{{{W_NS}}}val', '')
        if val not in KEEP_STYLES:
            parent = pStyle.getparent()
            if parent is not None:
                parent.remove(pStyle)
    return elem


def _prepare_for_insert(src_el, rid_map: dict):
    """深拷贝源元素 + 清理样式 + 重写图片 rId，得到可安全插入到目标 doc 的元素。"""
    new_el = copy.deepcopy(src_el)
    _clean_style_refs(new_el)
    if rid_map:
        _rewrite_image_rids([new_el], rid_map)
    return new_el


def _insert_after(anchor_elem, new_elem):
    """在 anchor_elem 之后插入 new_elem，返回 new_elem。"""
    anchor_elem.addnext(new_elem)
    return new_elem


def _replace_placeholder_with_text(p, new_text: str, fonts: dict, size_pt: float,
                                   bold: bool, alignment: str):
    """把段落 p 的内容替换为 new_text（清空原 runs，添加新 run）。"""
    for run_el in list(p._element.iter(f'{{{W_NS}}}r')):
        parent = run_el.getparent()
        if parent is not None:
            parent.remove(run_el)

    align_map = {
        'center': WD_ALIGN_PARAGRAPH.CENTER,
        'left': WD_ALIGN_PARAGRAPH.LEFT,
        'right': WD_ALIGN_PARAGRAPH.RIGHT,
    }
    p.alignment = align_map.get(alignment, WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.first_line_indent = Pt(0)

    run = p.add_run(new_text)
    run.bold = bold
    run.font.size = Pt(size_pt)

    cn_font = fonts.get('chinese_heading', 'SimHei') if bold else fonts.get('chinese_body', 'SimSun')
    en_font = fonts.get('latin', 'Times New Roman')

    rPr = run._element.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), en_font)
    rFonts.set(qn('w:hAnsi'), en_font)
    rFonts.set(qn('w:eastAsia'), cn_font)
    rPr.append(rFonts)


def fill_template(template_path: Path, source_md: Path, output_path: Path,
                  workspace: Optional[Path] = None, fonts: Optional[dict] = None,
                  style_profile: Optional[Path] = None, template_map: Optional[dict] = None) -> Path:
    """把 markdown 内容填到用户模板的占位位置。

    template_map: 可选，由 docx-template-map SKILL 输出的占位映射，结构见 SKILL.md。
        如果提供，优先按 idx 精确定位；不提供时退回正则启发式。
    """
    if not template_path.exists():
        raise FileNotFoundError(f'模板文件不存在: {template_path}')
    if not source_md.exists():
        raise FileNotFoundError(f'源 Markdown 不存在: {source_md}')

    suffix = template_path.suffix.lower()
    if suffix == '.dotx':
        template_path = _convert_dotx_to_docx(template_path)
        log.info('Converted .dotx to .docx: %s', template_path)
    elif suffix in ('.doc', '.rtf', '.odt'):
        raise ValueError(f'不支持的模板格式 {suffix}：请用 Word 打开后另存为 .docx 再上传')

    if fonts is None:
        fonts = {'chinese_body': 'SimSun', 'chinese_heading': 'SimHei',
                 'latin': 'Times New Roman', 'monospace': 'Consolas'}

    if not workspace:
        workspace = source_md.parent

    if template_map is None:
        _map_path = workspace / '_template_map.json'
        if _map_path.exists():
            try:
                template_map = json.loads(_map_path.read_text(encoding='utf-8'))
                log.info('Loaded template_map from %s (%d keys)', _map_path, len(template_map))
            except Exception as e:
                log.warning('_template_map.json 解析失败，退回正则模式: %s', e)
                template_map = None

    with tempfile.TemporaryDirectory(prefix='docx_fill_') as tmp:
        tmp_path = Path(tmp) / 'rendered.docx'
        _render_md_via_node(source_md, tmp_path, workspace, style_profile=style_profile)
        log.info('Node engine rendered markdown to temporary docx (%d bytes)', tmp_path.stat().st_size)

        rendered = Document(str(tmp_path))
        sections = _slice_rendered_doc(rendered)
        log.info('Sliced sections: title=%r abstract=%d body=%d refs=%d appendix=%d',
                 sections['title_text'][:30], len(sections['abstract']), len(sections['body']),
                 len(sections['references']), len(sections['appendix']))

        doc = Document(str(template_path))

        all_transfer_elements = (sections['abstract'] +
                                 ([sections['keywords']] if sections['keywords'] is not None else []) +
                                 sections['body'] + sections['references'] + sections['appendix'])
        rid_map = _transfer_images(rendered, doc, all_transfer_elements)
        if rid_map:
            log.info('Image rId mapping: %s', rid_map)

        all_paras = list(doc.paragraphs)
        tmap = template_map or {}

        anchor_keys = ['title_anchor_para_idx', 'abstract_anchor_para_idx', 'body_anchor_para_idx',
                       'references_anchor_para_idx', 'appendix_anchor_para_idx']
        anchor_refs = {}
        for key in anchor_keys:
            idx = tmap.get(key)
            if idx is None:
                anchor_refs[key] = None
                continue
            if 0 <= idx < len(all_paras):
                anchor_refs[key] = all_paras[idx]
            else:
                log.warning('template_map[%s]=%s 超出段落范围 (total=%d)', key, idx, len(all_paras))
                anchor_refs[key] = None

        def _para_by_idx(key: str):
            return anchor_refs.get(key)

        if tmap and isinstance(tmap.get('delete_paragraph_indices'), list):
            del_indices = tmap['delete_paragraph_indices']
            del_count = 0
            for di in sorted(del_indices, reverse=True):
                if not (0 <= di < len(all_paras)):
                    continue
                pp = all_paras[di]
                if pp._element.getparent() is None:
                    continue
                if any(ref is not None and ref._element is pp._element for ref in anchor_refs.values()):
                    log.warning('delete_paragraph_indices[%d] 与某个 anchor 重合，跳过', di)
                    continue
                _delete_paragraph(pp)
                del_count += 1
            log.info('Deleted %d instructional paragraph(s) by template_map', del_count)

        title_p = _para_by_idx('title_anchor_para_idx')
        title_replaced = False

        abstract_placed = False
        references_placed = False
        appendix_placed = False
        body_placed = False
        body_end_cursor = None

        abstract_fallback_anchor = None

        if title_p is not None and title_p._element.getparent() is not None:
            _replace_placeholder_with_text(title_p, sections['title_text'] or '未命名论文',
                                           fonts, 22, True, 'center')
            title_replaced = True
            log.info('Title replaced via template_map: %r', sections['title_text'][:40])
        else:
            for p in list(doc.paragraphs):
                if _is_title_placeholder(p.text):
                    _replace_placeholder_with_text(p, sections['title_text'] or '未命名论文',
                                                   fonts, 22, True, 'center')
                    title_replaced = True
                    log.info('Title replaced (regex): %r', sections['title_text'][:40])
                    break

        abstract_p = _para_by_idx('abstract_anchor_para_idx')
        if abstract_p is None or abstract_p._element.getparent() is None:
            for p in list(doc.paragraphs):
                if _ABSTRACT_RE.match(p.text or ''):
                    abstract_p = p
                    break
        if abstract_p is not None and abstract_p._element.getparent() is not None:
            anchor = abstract_p
            stop_elements = set()
            for next_key in ('body_anchor_para_idx', 'references_anchor_para_idx', 'appendix_anchor_para_idx'):
                next_p = _para_by_idx(next_key)
                if next_p is not None and next_p._element.getparent() is not None:
                    stop_elements.add(next_p._element)
            to_delete = []
            cur_el = anchor._element.getnext()
            while cur_el is not None:
                if cur_el in stop_elements:
                    break
                if cur_el.tag == f'{{{W_NS}}}p':
                    next_text = _para_text(cur_el)
                    if (cur_el in stop_elements or _BODY_PLACEHOLDER_RE.match(next_text)
                            or _REFERENCES_RE.match(next_text) or _APPENDIX_RE.match(next_text)
                            or _ACK_RE.match(next_text)):
                        break
                    to_delete.append(cur_el)
                cur_el = cur_el.getnext()
            for el in to_delete:
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)
            cursor = anchor._element
            for src_el in sections['abstract']:
                new_el = _prepare_for_insert(src_el, rid_map)
                cursor = _insert_after(cursor, new_el)
            if sections['keywords'] is not None:
                new_kw = _prepare_for_insert(sections['keywords'], rid_map)
                cursor = _insert_after(cursor, new_kw)
            abstract_placed = True
            log.info('Abstract (%d paras) + keywords inserted', len(sections['abstract']))

        body_p = _para_by_idx('body_anchor_para_idx')
        if body_p is None or body_p._element.getparent() is None:
            for p in list(doc.paragraphs):
                if _BODY_PLACEHOLDER_RE.match(p.text or ''):
                    body_p = p
                    break
        if body_p is not None and body_p._element.getparent() is not None:
            anchor_el = body_p._element
            cursor = anchor_el

            if not title_replaced and (sections.get('title_text') or '').strip():
                _title_p = doc.add_paragraph()
                _replace_placeholder_with_text(_title_p, sections['title_text'], fonts, 22, True, 'center')
                _title_el = _title_p._element
                _tp_parent = _title_el.getparent()
                if _tp_parent is not None:
                    _tp_parent.remove(_title_el)
                cursor = _insert_after(cursor, _title_el)
                title_replaced = True
                log.info('Title inserted at body anchor (fallback): %r',
                         (sections['title_text'] or '')[:40])

            abstract_fallback_anchor = cursor

            for src_el in sections['body']:
                new_el = _prepare_for_insert(src_el, rid_map)
                cursor = _insert_after(cursor, new_el)
            body_end_cursor = cursor
            body_placed = True

            mode = (tmap or {}).get('body_anchor_mode', 'delete')
            if mode == 'delete':
                parent = anchor_el.getparent()
                if parent is not None:
                    parent.remove(anchor_el)
            log.info('Body (%d elements) inserted (anchor_mode=%s)', len(sections['body']), mode)

        refs_p = _para_by_idx('references_anchor_para_idx')
        if refs_p is None or refs_p._element.getparent() is None:
            for p in list(doc.paragraphs):
                if _REFERENCES_RE.match(p.text or ''):
                    refs_p = p
                    break
        if refs_p is not None and refs_p._element.getparent() is not None:
            anchor = refs_p
            stop_elements = set()
            for next_key in ('appendix_anchor_para_idx',):
                next_p = _para_by_idx(next_key)
                if next_p is not None and next_p._element.getparent() is not None:
                    stop_elements.add(next_p._element)
            to_delete = []
            cur_el = anchor._element.getnext()
            while cur_el is not None:
                if cur_el in stop_elements:
                    break
                if cur_el.tag == f'{{{W_NS}}}p':
                    next_text = _para_text(cur_el)
                    if (cur_el in stop_elements or _APPENDIX_RE.match(next_text) or _ACK_RE.match(next_text)):
                        break
                    to_delete.append(cur_el)
                cur_el = cur_el.getnext()
            for el in to_delete:
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)
            cursor = anchor._element
            for src_el in sections['references']:
                new_el = _prepare_for_insert(src_el, rid_map)
                cursor = _insert_after(cursor, new_el)
            references_placed = True
            log.info('References (%d items) inserted', len(sections['references']))

        if sections['appendix']:
            app_p = _para_by_idx('appendix_anchor_para_idx')
            if app_p is None or app_p._element.getparent() is None:
                for p in list(doc.paragraphs):
                    if _APPENDIX_RE.match(p.text or ''):
                        app_p = p
                        break
            if app_p is not None and app_p._element.getparent() is not None:
                anchor = app_p
                to_delete = []
                cur_el = anchor._element.getnext()
                while cur_el is not None:
                    if cur_el.tag == f'{{{W_NS}}}p':
                        next_text = _para_text(cur_el).strip()
                        if next_text and not _is_instruction_paragraph(next_text):
                            break
                    to_delete.append(cur_el)
                    cur_el = cur_el.getnext()
                for el in to_delete:
                    parent = el.getparent()
                    if parent is not None:
                        parent.remove(el)
                cursor = anchor._element
                for src_el in sections['appendix']:
                    new_el = _prepare_for_insert(src_el, rid_map)
                    cursor = _insert_after(cursor, new_el)
                appendix_placed = True
                log.info('Appendix (%d elements) inserted', len(sections['appendix']))

        def _append_section(elems: list, name: str = None, heading: str = None):
            nonlocal body_end_cursor
            if not elems:
                return
            if body_end_cursor is None or body_end_cursor.getparent() is None:
                body_children = list(doc.element.body)
                anchor_el = None
                for _c in reversed(body_children):
                    if _c.tag != f'{{{W_NS}}}sectPr':
                        anchor_el = _c
                        break
                if anchor_el is None:
                    return
                body_end_cursor = anchor_el
            cur = body_end_cursor
            if heading:
                _h = doc.add_paragraph()
                _replace_placeholder_with_text(_h, heading, fonts, 14, True, 'left')
                _h_el = _h._element
                _hp = _h_el.getparent()
                if _hp is not None:
                    _hp.remove(_h_el)
                cur = _insert_after(cur, _h_el)
            for src_el in elems:
                new_el = _prepare_for_insert(src_el, rid_map)
                cur = _insert_after(cur, new_el)
            body_end_cursor = cur
            log.warning('Safety-net: appended %s (%d elems) at body tail (template had no anchor/placeholder)',
                        name, len(elems))

        if not body_placed and sections.get('body'):
            _append_section(sections['body'], 'body')

        if not abstract_placed and sections.get('abstract'):
            _kw = [sections['keywords']] if sections.get('keywords') is not None else []
            _ab_elems = list(sections['abstract']) + _kw
            if abstract_fallback_anchor is not None and abstract_fallback_anchor.getparent() is not None:
                cur = abstract_fallback_anchor
                _h = doc.add_paragraph()
                _replace_placeholder_with_text(_h, '摘要', fonts, 14, True, 'left')
                _h_el = _h._element
                if _h_el.getparent() is not None:
                    _h_el.getparent().remove(_h_el)
                cur = _insert_after(cur, _h_el)
                for src_el in _ab_elems:
                    new_el = _prepare_for_insert(src_el, rid_map)
                    cur = _insert_after(cur, new_el)
                abstract_placed = True
                log.warning('Safety-net: abstract inserted at body START (%d elems) '
                            '(template had no abstract anchor/placeholder)', len(_ab_elems))
            else:
                _append_section(_ab_elems, 'abstract', heading='摘要')

        if not references_placed and sections.get('references'):
            _appendix_anchor_el = None
            for _p in doc.paragraphs:
                if _APPENDIX_RE.match((_p.text or '').strip()):
                    _appendix_anchor_el = _p._element
                    break
            if _appendix_anchor_el is not None and _appendix_anchor_el.getparent() is not None:
                _h = doc.add_paragraph()
                _replace_placeholder_with_text(_h, '参考文献', fonts, 14, True, 'left')
                _h_el = _h._element
                if _h_el.getparent() is not None:
                    _h_el.getparent().remove(_h_el)
                _appendix_anchor_el.addprevious(_h_el)
                _cur = _h_el
                for src_el in sections['references']:
                    new_el = _prepare_for_insert(src_el, rid_map)
                    _cur.addnext(new_el)
                    _cur = new_el
                references_placed = True
                log.warning('Safety-net: references inserted BEFORE appendix (%d items)',
                            len(sections['references']))
            else:
                _append_section(sections['references'], 'references', heading='参考文献')

        if not appendix_placed and sections.get('appendix'):
            _append_section(sections['appendix'], 'appendix', heading='附录')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        log.info('Filled docx saved: %s (%d bytes)', output_path, output_path.stat().st_size)
        return output_path


def main():
    parser = argparse.ArgumentParser(prog=PROG, description='将 Markdown 内容填充到 .docx 模板')
    parser.add_argument('--template', '-t', type=Path, required=True)
    parser.add_argument('--source', '-s', type=Path, required=True)
    parser.add_argument('--output', '-o', type=Path, required=True)
    parser.add_argument('--workspace', '-w', type=Path, default=None)
    parser.add_argument('--profile', '-p', type=Path, default=None,
                        help='样式 profile JSON（可选，传给 Node 引擎）')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    fill_template(args.template, args.source, args.output, args.workspace,
                  style_profile=args.profile)
    print(f'OK: filled {args.output}')


if __name__ == '__main__':
    main()
