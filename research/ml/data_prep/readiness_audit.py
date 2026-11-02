"""Read-only evidence and task-readiness audit after self-supervised training.

Reuses exact cached review rows and the complete source-reference audit.
Does not assign labels, export splits, train models or change raw sources.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile
from research.ml.data_prep.prepare_dataset import reviewed_label,make_splits,SecurityEvent
from research.ml.data_prep.resolve_references import reusable_files,validate_cached_index,resolve_chain
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash


def require(condition,message):
    if not condition:raise ValueError(message)


def assess_samples(annotations,prepared):
    by_id={row['event_uuid']:row for row in prepared}
    require(len(by_id)==len(prepared),'Duplicate prepared review identities')
    require(len({a['event_uuid'] for a in annotations})==len(annotations),'Duplicate annotation identities')
    require(set(by_id)=={a['event_uuid'] for a in annotations},'Prepared rows must exactly cover current annotations')
    for annotation in annotations:
        row=by_id[annotation['event_uuid']]
        require(all(row.get(k)==v for k,v in annotation.items()),'Cached review row disagrees with current annotation')
        event=SecurityEvent.model_validate(row['security_event'])
        raw=row['security_event']['raw_data']['cdm']
        require(reviewed_label(annotation,raw)==row['label'],'Reviewed label mismatch')
        require(row['security_event']['event_id']==row['event_uuid'],'Canonical event identity mismatch')
        require(raw['datum'].get('subject')==annotation['subject_uuid'],'Native subject mismatch')
        require(event.timestamp.tzinfo is not None,'Canonical timestamp requires timezone')
        delta=event.timestamp.astimezone(timezone.utc)-datetime(1970,1,1,tzinfo=timezone.utc)
        canonical_us=(delta.days*86400+delta.seconds)*1_000_000+delta.microseconds
        require(canonical_us==annotation['timestamp_nanos']//1000,'Canonical timestamp differs from native time')
    splits,reasons=make_splits(prepared,context_nanos=0)
    eligible=[row for row in prepared if row['label'] is not None and row.get('split_eligible',True)]
    return dict(reviewed_label_counts={str(k):sum(row['label']==k for row in prepared) for k in (0,1,None)},
        eligible_label_counts={str(k):sum(row['label']==k for row in eligible) for k in (0,1)},
        named_attack_group_count=len({r['group_id'] for r in eligible if r['label']==1}),
        named_benign_group_count=len({r['group_id'] for r in eligible if r['label']==0}),
        positive_incident_count=len({r['incident_id'] for r in eligible if r['label']==1}),
        independent_group_validation_claimed=False,
        excluded=[dict(event_uuid=r['event_uuid'],label=r['label'],reason=r['split_exclusion_reason'])
                  for r in prepared if r.get('split_eligible') is False],
        supervised_gate_passes=splits is not None,blocking_reasons=reasons,
        structural_context_check_nanos=0,history_horizon_selected=False,
        note='The existing preparation split function is checked at zero context. Failure already prevents splits; no supervised input horizon is selected.')


def support_inventory(support,cache):
    archives=[]
    for path in sorted(support.glob('*.zip')):
        members=[]
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                if item.is_dir():continue
                h=hashlib.sha256()
                with archive.open(item) as stream:
                    while block:=stream.read(1024*1024):h.update(block)
                copied=cache/item.filename
                members.append(dict(name=item.filename,bytes=item.file_size,sha256=h.hexdigest(),
                    matches_cached_copy=copied.is_file() and file_hash(copied)==h.hexdigest()))
        archives.append(dict(name=path.name,sha256=file_hash(path),members=members))
    files=[dict(name=p.name,sha256=file_hash(p)) for p in sorted(support.iterdir()) if p.is_file() and p.suffix.lower()!='.zip']
    possible=[]
    for path in support.rglob('*'):
        if path.is_file() and path.suffix.lower() in ('.csv','.tsv','.jsonl','.json','.ndjson'):
            possible.append(str(path.relative_to(support)))
    archived_candidates=[a['name']+'::'+m['name'] for a in archives for m in a['members']
        if Path(m['name']).suffix.lower() in ('.csv','.tsv','.jsonl','.json','.ndjson')]
    return dict(archives=archives,standalone_files=files,standalone_annotation_candidates=possible,
        archived_annotation_candidates=archived_candidates,
        scope='Current local support folder only; no fresh website/Drive check or new document interpretation.')


def audit(source,support,reference,prepared_path,annotations_path,gnn_work,output):
    root=Path(__file__).resolve().parents[3]
    require(not output.resolve().is_relative_to(source.resolve()) and not output.resolve().is_relative_to(support.resolve()),
            'Audit output must be outside raw/support sources')
    annotations=json.loads(annotations_path.read_text(encoding='utf-8'))['events']
    prepared=[json.loads(line) for line in prepared_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    assessment=assess_samples(annotations,prepared)
    manifest=json.loads(prepared_path.with_name('manifest.json').read_text(encoding='utf-8'))
    require(manifest['annotations_sha256']==text_hash(annotations_path),'Preparation annotation provenance changed')
    paths=list(source.rglob('*.gz'));require(len({p.name for p in paths})==len(paths),'Duplicate raw source basenames')
    files=reusable_files(paths,reference);cached={f['filename'] for f in files}
    extra=sorted(p.name for p in paths if p.name not in cached)
    if extra:assessment['blocking_reasons'].append('New raw archives need their own complete source/label audit')
    process_checks=[]
    with closing(sqlite3.connect((reference.resolve()/'references.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        validate_cached_index(db,files)
        require(db.execute('PRAGMA quick_check').fetchone()[0]=='ok','Cached reference database integrity failed')
        definitions=db.execute('SELECT count(*) FROM entities').fetchone()[0]
        for annotation in annotations:
            chain=resolve_chain(db,annotation['subject_uuid'],annotation['timestamp_nanos'],annotation['host_uuid'])
            resolved=bool(chain) and chain[-1].get('type')=='SUBJECT_PROCESS' and all(
                step['status']=='resolved' and step.get('started_at_or_before_event') is True for step in chain)
            previous=next(r for r in prepared if r['event_uuid']==annotation['event_uuid'])['subject_resolution']['process_resolved']
            process_checks.append(dict(event_uuid=annotation['event_uuid'],chain_length=len(chain),
                process_resolved=resolved,previous_process_resolved=previous,resolution_changed=resolved!=previous,
                missing_reference=chain[-1]['uuid'] if chain and chain[-1]['status']=='missing' else None,
                future_or_unknown_start=any(s['status']=='resolved' and s.get('started_at_or_before_event') is not True for s in chain)))
    require(not any(c['resolution_changed'] for c in process_checks),'Identity resolution changed; fresh source review required')
    inventory=support_inventory(support,root/'.cache/ml-support')
    old_gate=json.loads((root/'data/ml/datasets/darpa/alignment_gate_report_20261027.json').read_text())
    require(old_gate['annotation_sha256']==text_hash(annotations_path),'Historical annotation binding differs')
    require(old_gate['reference_report_sha256']==text_hash(reference/'reference_report.json'),'Reference binding differs')
    for archive in inventory['archives']:
        for member in archive['members']:
            if member['name'].endswith('TA51_Final_report_E5.pdf'):
                require(member['sha256']=='95785dd6e32e1585e3a3b49f7f69aac785ca9d2db05593ad919b1b627897f0a1','ACT report bytes changed')
    log=support/'Engagement-5-Event-Log.md'
    require(text_hash(log)=='70b111fff7bc4662d4c22664be19c4c08702a36676f31f160d4b3a856ee5c3c9','Operational log changed')
    verification=json.loads((root/'data/ml/datasets/darpa/gnn_full/verification_20261102.json').read_text())
    complete=gnn_work/'complete.json'
    require(file_hash(complete)==verification['complete_sha256'],'Completed GNN aggregate changed')
    completed={}
    for family in ('gcn','graphsage','gat'):
        expected=verification['models'][family]
        for name,key in (('best.pt','checkpoint_sha256'),('run.json','run_sha256'),('test.json','test_sha256')):
            require(file_hash(gnn_work/'runs'/family/name)==expected[key],'Frozen GNN artifact changed')
        completed[family]=dict(epochs=5,selected_epoch=expected['selected_epoch'],checkpoint_sha256=expected['checkpoint_sha256'])
    scenarios={p.name:[str(f.relative_to(p)) for f in p.rglob('*') if f.is_file() and f.name!='.gitkeep']
        for p in (root/'data/scenarios').iterdir() if p.is_dir()}
    node_report_path=root/'data/ml/datasets/darpa/node_benchmark/source_evidence_review_report_20261029.json'
    node_report=json.loads(node_report_path.read_text())
    node_decisions=root/'.cache/ml-runs/pretraining-review-20261029/review_decisions.jsonl'
    require(file_hash(node_decisions)==node_report['decision_file_sha256'],'Node-pilot decisions changed')
    node_rows=[json.loads(line) for line in node_decisions.read_text().splitlines() if line.strip()]
    require(len(node_rows)==node_report['candidate_count']==500,'Node review count changed')
    require(all(r['label'] is None and r['supervised_eligible'] is False for r in node_rows),'Node-pilot labels require a fresh review')
    result=dict(status='readiness_audit_complete_supervised_not_ready' if not assessment['supervised_gate_passes'] else 'readiness_requires_independent_review',
        date='2026-11-02',event_target='A native CDM Event is a documented ACT attack action',event_track=assessment,
        source_inventory=dict(current_archives=len(paths),audited_archives=len(files),unreviewed_archives=extra,
            raw_records=sum(f['records'] for f in files),eligible_label_volume_inferred_from_raw_count=False,
            metadata_revalidated=True,raw_bytes_rescanned=False),
        support_inventory=inventory,reference_index=dict(definitions=definitions,quick_check='ok',read_only=True,
            sha256=file_hash(reference/'references.sqlite'),reference_report_sha256_utf8_lf=text_hash(reference/'reference_report.json')),
        annotation_sha256_utf8_lf=text_hash(annotations_path),prepared_rows_sha256=file_hash(prepared_path),
        process_resolution_checks=process_checks,controlled_scenario_nonplaceholder_files=scenarios,
        frozen_gnn_work=dict(status='complete_verified_reconstruction_only',models=completed,
            completion_sha256=file_hash(complete),new_graph_hash_scan_performed=False,new_training_performed=False),
        separate_node_pilot=dict(status='existing_unknown_decisions_revalidated',candidates=len(node_rows),verified_binary_labels=0,
            decision_file_sha256=file_hash(node_decisions),source_report_sha256=file_hash(node_report_path)),
        new_labels_assigned=0,supervised_splits_exported=False,security_metrics_computed=False,
        raw_sources_modified=False,annotations_modified=False,models_modified=False,
        limitations=['Exact cached review rows reused; no fresh Avro normalization or raw-byte scan',
            'Local support inventory is not a current Drive availability check',
            'Annotation count/group checks are necessary gates, not statistical sample-size validation',
            'Self-supervised reconstruction and original Event-level security classification have different targets'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes((json.dumps(result,indent=2,allow_nan=False)+'\n').encode())
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','support','reference','prepared','annotations','gnn-work','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.source,args.support,args.reference,args.prepared,args.annotations,args.gnn_work,args.output)
    print(json.dumps(dict(status=result['status'],event_track=result['event_track'],raw_archives=result['source_inventory']['current_archives'])))
