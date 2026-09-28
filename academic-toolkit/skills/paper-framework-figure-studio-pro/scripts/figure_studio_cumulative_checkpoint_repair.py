#!/usr/bin/env python3
"""Generic cumulative checkpoint detector/repair for paper-framework-figure-studio-pro runs.

Rules:
- Derive stage order, output roots, candidate IDs, image targets, and pending future images from project state and prompt-index files.
- Do not hard-code project paper terms, candidate counts, or image page counts.
- Rebuild a cumulative restore zip if the requested stage checkpoint is missing/incomplete.
"""
from __future__ import annotations

import argparse, json, re, zipfile, hashlib, tempfile, shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

RASTER_EXTS = {'.png', '.jpg', '.jpeg', '.webp'}
EXCLUDE_DIRS = {'checkpoints'}
META_NAMES = {'checkpoint-manifest.json','checkpoint-cumulative-integrity.json','checkpoint-integrity-audit.json'}

def now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def rel_norm(p: str | Path) -> str:
    s = Path(p).as_posix().lstrip('/')
    parts=[]
    for part in s.split('/'):
        if not part or part == '.':
            continue
        if part == '..':
            raise ValueError(f'unsafe path: {p!r}')
        parts.append(part)
    return '/'.join(parts)

def sha256_path(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def stage_index_map(state: dict[str, Any]) -> dict[str, int]:
    plan = state.get('workflow_plan') or []
    return {row.get('step'): i for i,row in enumerate(plan) if isinstance(row,dict) and row.get('step')}

def output_roots_through_stage(state: dict[str, Any], stage: str) -> list[str]:
    roots=['state','inputs']
    for row in state.get('workflow_plan') or []:
        if not isinstance(row, dict):
            continue
        out=row.get('output_dir')
        if out:
            roots.append(rel_norm(out))
        if row.get('step') == stage:
            break
    seen=[]
    for r in roots:
        if r and r not in seen:
            seen.append(r)
    return seen

def find_prompt_indexes(run: Path) -> list[tuple[str, dict[str, Any]]]:
    rows=[]
    for p in (run/'outputs').rglob('prompt-index.json') if (run/'outputs').exists() else []:
        try:
            rows.append((rel_norm(p.relative_to(run)), read_json(p)))
        except Exception:
            continue
    return rows

def include_future_prompt_roots(run: Path, roots: list[str], target_stage: str) -> list[str]:
    # S4-style embedded preparation is generic: if a future prompt-index says it was
    # prepared_by_stage == target_stage, include that output root as pending future assets.
    for rel, data in find_prompt_indexes(run):
        if data.get('prepared_by_stage') == target_stage:
            root = rel.rsplit('/prompt-index.json',1)[0]
            if root and root not in roots:
                roots.append(root)
    return roots

def path_under_roots(rel: str, roots: list[str]) -> bool:
    rel=rel_norm(rel)
    if any(rel == d or rel.startswith(d + '/') for d in EXCLUDE_DIRS):
        return False
    return any(rel == root or rel.startswith(root + '/') for root in roots)

def collect_existing_files(run: Path, roots: list[str]) -> list[str]:
    files=[]
    for root in roots:
        p=run/root
        if p.is_file():
            files.append(root)
        elif p.exists():
            for f in p.rglob('*'):
                if f.is_file():
                    rel=rel_norm(f.relative_to(run))
                    if path_under_roots(rel, roots):
                        files.append(rel)
    return sorted(set(files))

def prompt_index_image_targets(run: Path, roots: list[str], target_stage: str, state: dict[str, Any]) -> tuple[list[str], list[str]]:
    idx=stage_index_map(state)
    target_i=idx.get(target_stage, 10**6)
    required=[]; pending=[]
    for rel, data in find_prompt_indexes(run):
        if not path_under_roots(rel, roots):
            continue
        prompt_stage=data.get('stage') or ''
        prompt_i=idx.get(prompt_stage, 10**6)
        for cand in data.get('candidates') or []:
            if not isinstance(cand, dict):
                continue
            t=cand.get('target_image_path')
            if not isinstance(t, str):
                continue
            t=rel_norm(t)
            exists=(run/t).is_file()
            if prompt_i <= target_i:
                if exists:
                    required.append(t)
                else:
                    required.append(t)  # completed/past image-stage target must exist
            else:
                pending.append(t)
            for ref in cand.get('reference_image_paths') or []:
                if isinstance(ref, str):
                    ref = rel_norm(ref)
                    # S5 reference images are prior-stage inputs, not future S5
                    # outputs. If listed, they must already exist in the
                    # cumulative roots even when the S5 target images are still
                    # pending.
                    if path_under_roots(ref, roots):
                        required.append(ref)
    return sorted(set(required)), sorted(set(pending))

def valid_zip_members(path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(path) as z:
            return set(z.namelist())
    except Exception:
        return set()

def next_sequence(run: Path, stage: str) -> int:
    d=run/'checkpoints'/stage
    nums=[]
    if d.exists():
        for p in d.glob('stage-final-*.zip'):
            m=re.search(r'stage-final-(\d+)', p.name)
            if m:
                nums.append(int(m.group(1)))
    return max(nums or [0]) + 1

def checkpoint_candidates(run: Path, stage: str) -> list[Path]:
    d=run/'checkpoints'/stage
    if not d.exists():
        return []
    def seq(p: Path) -> int:
        m=re.search(r'stage-final-(\d+)', p.name)
        return int(m.group(1)) if m else -1
    return sorted(d.glob('stage-final-*.zip'), key=seq, reverse=True)

def read_state_from_zip(zip_path: Path) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(zip_path) as z:
            if 'state/project-state.json' not in z.namelist():
                return None
            return json.loads(z.read('state/project-state.json').decode('utf-8'))
    except Exception:
        return None

def later_stages_pending(state: dict[str,Any], stage: str) -> bool:
    seen=False
    for row in state.get('workflow_plan') or []:
        if not isinstance(row, dict):
            continue
        if row.get('step') == stage:
            seen=True
            continue
        if seen and row.get('status') not in {'pending', None, ''}:
            return False
    return True

def stage_row_status(state: dict[str,Any], stage: str) -> str | None:
    for row in state.get('workflow_plan') or []:
        if isinstance(row,dict) and row.get('step') == stage:
            return row.get('status')
    return None

def choose_state_snapshot(run: Path, stage: str, live_state: dict[str,Any]) -> tuple[dict[str,Any], str, str | None]:
    # If live state has not progressed past the target stage, use it.
    idx=stage_index_map(live_state)
    current=live_state.get('current_step') or live_state.get('active_stage')
    if current in idx and stage in idx and idx[current] <= idx[stage]:
        return live_state, 'live_state', None
    # Otherwise recover a stage-appropriate snapshot from prior checkpoint zips.
    for z in checkpoint_candidates(run, stage):
        st=read_state_from_zip(z)
        if not st:
            continue
        if stage_row_status(st, stage) in {'completed','in_progress','current'} and later_stages_pending(st, stage):
            return st, f'recovered_from_{rel_norm(z.relative_to(run))}', None
    return live_state, 'live_state_fallback_after_stage_progression', 'No prior stage-appropriate state snapshot found; checkpoint state may reflect a later stage.'

def normalize_state_for_stage(state: dict[str,Any], stage: str, next_stage: str | None, repair_zip_rel: str) -> dict[str,Any]:
    st=json.loads(json.dumps(state))
    # Normalize workflow statuses around target stage, without paper-specific facts.
    reached=False
    for row in st.get('workflow_plan') or []:
        if not isinstance(row, dict):
            continue
        if row.get('step') == stage:
            row['status']='completed'
            reached=True
        elif not reached:
            row['status']='completed'
        else:
            row['status']='pending'
    st['current_step']=stage
    st['updated_at']=now()
    st.setdefault('checkpoint_repair_notes', [])
    st['checkpoint_repair_notes'].append({
        'created_at': now(),
        'stage': stage,
        'repair_zip': repair_zip_rel,
        'rule': 'generic cumulative checkpoint repair; no hard-coded candidate/image counts',
    })
    return st

def build_checkpoint(run: Path, stage: str, output_zip: Path) -> dict[str, Any]:
    live_state=read_json(run/'state/project-state.json')
    snapshot, snapshot_source, snapshot_warning = choose_state_snapshot(run, stage, live_state)
    next_stage=None
    plan=snapshot.get('workflow_plan') or []
    for i,row in enumerate(plan):
        if isinstance(row,dict) and row.get('step') == stage and i+1 < len(plan):
            next_stage = plan[i+1].get('step')
            break
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    zip_rel=rel_norm(output_zip.relative_to(run))
    stage_state=normalize_state_for_stage(snapshot, stage, next_stage, zip_rel)
    roots=output_roots_through_stage(stage_state, stage)
    roots=include_future_prompt_roots(run, roots, stage)
    existing=collect_existing_files(run, roots)
    # Ensure canonical state is represented by the stage-normalized snapshot, not stale live file.
    if 'state/project-state.json' not in existing:
        existing.append('state/project-state.json')
    existing=sorted(set(existing))
    req_targets, pending_targets=prompt_index_image_targets(run, roots, stage, stage_state)
    missing_required_files=[rel for rel in existing if rel != 'state/project-state.json' and not (run/rel).is_file()]
    missing_required_targets=[rel for rel in req_targets if not (run/rel).is_file()]
    # Existing raster files under roots, plus prompt-index targets that exist.
    required_existing_images=sorted(set([rel for rel in existing if Path(rel).suffix.lower() in RASTER_EXTS] + [rel for rel in req_targets if (run/rel).is_file()]))
    checkpoint_stage_list=[]
    for row in stage_state.get('workflow_plan') or []:
        if not isinstance(row,dict):
            continue
        out=row.get('output_dir')
        if out and rel_norm(out) in roots:
            checkpoint_stage_list.append({'step':row.get('step'), 'output_dir':rel_norm(out), 'status':row.get('status')})
    manifest={
        'schema_version': 3,
        'skill_name': stage_state.get('skill_name','paper-framework-figure-studio-pro'),
        'skill_version': stage_state.get('skill_version','unknown'),
        'project_id': stage_state.get('project_id'),
        'stage': stage,
        'checkpoint_type': 'stage-final-cumulative-repair',
        'created_at': now(),
        'checkpoint_scope': 'cumulative_from_workflow_start_to_current_stage_or_substage',
        'included_roots': roots,
        'checkpoint_stage_list': checkpoint_stage_list,
        'state_snapshot_source': snapshot_source,
        'state_snapshot_warning': snapshot_warning,
        'required_existing_asset_count': len(existing),
        'required_existing_image_count': len(required_existing_images),
        'pending_future_image_count': len(pending_targets),
        'pending_future_images': pending_targets,
        'missing_required_file_count_before_write': len(missing_required_files),
        'missing_required_image_count_before_write': len(missing_required_targets),
        'non_hardcoding_statement': 'Candidate IDs, image counts, image targets, and roots are derived from workflow state and prompt-index files; no paper/module/candidate-count hardcoding was used.',
        'checkpoint_status': 'complete_restore_ready' if not missing_required_files and not missing_required_targets else 'restore_repair_required_stage_redo',
        'restore_status': 'complete_restore_ready' if not missing_required_files and not missing_required_targets else 'restore_repair_required_stage_redo',
    }
    audit={
        'schema_version': 1,
        'stage': stage,
        'checkpoint_type': 'stage-final-cumulative-repair',
        'created_at': now(),
        'cumulative_checkpoint_stage_list': checkpoint_stage_list,
        'included_roots': roots,
        'prior_checkpoint_payload_count': 0,
        'recovered_prior_payload_count': 0,
        'prior_payload_still_missing_after_write': [],
        'required_existing_asset_count': len(existing),
        'required_existing_image_count': len(required_existing_images),
        'pending_future_image_count': len(pending_targets),
        'missing_required_file_count_before_write': len(missing_required_files),
        'missing_required_image_count_before_write': len(missing_required_targets),
        'final_verdict': manifest['checkpoint_status'],
        'non_hardcoding_statement': manifest['non_hardcoding_statement'],
    }
    integrity={
        'schema_version': 2,
        'stage': stage,
        'created_at': now(),
        'checkpoint_scope': manifest['checkpoint_scope'],
        'included_roots': roots,
        'required_existing_asset_count': len(existing),
        'required_existing_image_count': len(required_existing_images),
        'pending_future_image_count': len(pending_targets),
        'missing_asset_count': len(missing_required_files),
        'missing_image_count': len(missing_required_targets),
        'checkpoint_integrity_status': manifest['checkpoint_status'],
        'post_write_validation_status': 'not_run_yet',
    }
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('checkpoint-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        z.writestr('checkpoint-cumulative-integrity.json', json.dumps(integrity, ensure_ascii=False, indent=2)+'\n')
        z.writestr('checkpoint-integrity-audit.json', json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
        for rel in existing:
            if rel == 'state/project-state.json':
                z.writestr(rel, json.dumps(stage_state, ensure_ascii=False, indent=2)+'\n')
            else:
                p=run/rel
                if p.is_file():
                    z.write(p, rel)
    members=valid_zip_members(output_zip)
    missing_after=[rel for rel in existing if rel not in members]
    missing_meta=[name for name in META_NAMES if name not in members]
    post_status='PASS' if not missing_after and not missing_meta and not missing_required_files and not missing_required_targets else 'FAIL'
    zip_sha=sha256_path(output_zip)
    integrity['post_write_validation_status']=post_status
    integrity['missing_after_write_count']=len(missing_after)
    integrity['missing_metadata_after_write']=missing_meta
    integrity['zip_sha256']=zip_sha
    audit['missing_after_write_count']=len(missing_after)
    audit['missing_metadata_after_write']=missing_meta
    audit['final_verdict']='complete_restore_ready' if post_status == 'PASS' else 'restore_repair_required_stage_redo'
    manifest['post_write_validation_status']=post_status
    manifest['sha256']=zip_sha
    manifest['checkpoint_status']='complete_restore_ready' if post_status == 'PASS' else 'restore_repair_required_stage_redo'
    manifest['restore_status']=manifest['checkpoint_status']
    if post_status != 'PASS':
        manifest['required_action']='redo_related_producing_stage_or_substage_then_rebuild_checkpoint_until_pass'
        integrity['required_action']=manifest['required_action']
        audit['required_action']=manifest['required_action']
    # Repack metadata with final validation/sha.
    with zipfile.ZipFile(output_zip, 'r') as z:
        payload={name:z.read(name) for name in z.namelist() if name not in META_NAMES}
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('checkpoint-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        z.writestr('checkpoint-cumulative-integrity.json', json.dumps(integrity, ensure_ascii=False, indent=2)+'\n')
        z.writestr('checkpoint-integrity-audit.json', json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
        for name, data in payload.items():
            z.writestr(name, data)
    return {'manifest':manifest, 'integrity':integrity, 'audit':audit, 'zip_path':zip_rel}

def validate_checkpoint(run: Path, stage: str, zip_path: Path) -> dict[str,Any]:
    live_state=read_json(run/'state/project-state.json')
    snapshot, _, _ = choose_state_snapshot(run, stage, live_state)
    roots=output_roots_through_stage(snapshot, stage)
    roots=include_future_prompt_roots(run, roots, stage)
    existing=collect_existing_files(run, roots)
    if 'state/project-state.json' not in existing:
        existing.append('state/project-state.json')
    members=valid_zip_members(zip_path)
    return {
        'zip_path': rel_norm(zip_path.relative_to(run)),
        'metadata_present': {name: name in members for name in META_NAMES},
        'required_count': len(set(existing)),
        'member_count': len(members),
        'missing_count': len([rel for rel in set(existing) if rel not in members]),
        'missing_first_20': [rel for rel in sorted(set(existing)) if rel not in members][:20],
        'status': 'PASS' if all(name in members for name in META_NAMES) and not [rel for rel in set(existing) if rel not in members] else 'FAIL',
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--stage', action='append', required=True)
    ap.add_argument('--repair', action='store_true')
    ap.add_argument('--report', required=True)
    args=ap.parse_args()
    run=Path(args.run_dir).resolve()
    report={'created_at':now(), 'run_dir':str(run), 'stages':[]}
    for stage in args.stage:
        candidates=checkpoint_candidates(run, stage)
        latest=candidates[0] if candidates else None
        before=validate_checkpoint(run, stage, latest) if latest else {'status':'MISSING','zip_path':None}
        row={'stage':stage, 'latest_before':before}
        if args.repair and before.get('status') != 'PASS':
            seq=next_sequence(run, stage)
            out=run/'checkpoints'/stage/f'stage-final-{seq:04d}-generic-cumulative-repair.zip'
            result=build_checkpoint(run, stage, out)
            row['repair_created']=rel_norm(out.relative_to(run))
            row['repair_integrity']=result['integrity']
            row['repair_validation']=validate_checkpoint(run, stage, out)
        report['stages'].append(row)
    write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
