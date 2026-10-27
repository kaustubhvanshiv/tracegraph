"""Compare pinned public attack nodes with reviewed DARPA Events, without importing labels.

This audit reproduces the May-2019 comparison documented in
ml02_public_case_review_20261027.md. It checks four pinned CSV hashes, validates
existing source/reference caches, and rereads two bounded source prefixes.
Node-touch counts are diagnostics; reviewed labels and raw timestamps do not
change. No model framework or downloaded third-party code is executed.
"""
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from fastavro import reader

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.ml.data_prep.resolve_references import clean, resolve_chain, reusable_files, validate_cached_index
from research.ml.data_prep.inspect_fivedirections import uuid_text, utc_nanos

def audit(source, annotation_dir, reference_audit, prepared_events, output, annotations_path, public_audit_path):
    CACHE = Path(annotation_dir).resolve()
    OUT = Path(output).resolve()
    SOURCE = Path(source).resolve()
    REFERENCE = Path(reference_audit).resolve()
    PREPARED = Path(prepared_events).resolve()
    digest = lambda p: hashlib.sha256(p.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
    raw_hash = lambda r: hashlib.sha256(json.dumps(r, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    annotation_file = Path(annotations_path).resolve()
    audit_file = Path(public_audit_path).resolve()
    if SOURCE == OUT or SOURCE in OUT.parents:
        raise ValueError('Audit output must be outside the raw source directory')
    OUT.mkdir(parents=True, exist_ok=True)
    audit = json.loads(audit_file.read_text(encoding='utf-8'))
    if not (digest(annotation_file) == audit['current_gate']['annotation_sha256_utf8_lf']):
        raise ValueError('Reviewed annotations changed since the public-node audit; refresh provenance first.')
    annotations = json.loads(annotation_file.read_text(encoding='utf-8'))['events']
    prepared_rows = list(map(json.loads, PREPARED.read_text(encoding='utf-8').splitlines()))
    prepared = {r['event_uuid']: r for r in prepared_rows}
    if not (len(prepared) == len(prepared_rows)):
        raise ValueError('Duplicate Event UUIDs in prepared review rows.')
    if not (set(prepared) == {a['event_uuid'] for a in annotations}):
        raise ValueError('Prepared review rows do not cover exactly the selected annotations.')
    for a in annotations:
        if not (all(prepared[a['event_uuid']].get(k) == v for k, v in a.items())):
            raise ValueError('A prepared row disagrees with its current reviewed annotation.')

    nodes, cases = defaultdict(list), {}
    # Explicit fixed offset applies to these four May-2019 benchmark windows only.
    # It does not reinterpret any raw Event timestamp or the MARPLE alarm clock.
    if not (audit['upstream_configuration']['timezone'] == 'US/Eastern'):
        raise ValueError('This fixed-offset audit requires the reviewed US/Eastern case configuration.')
    if not (all(str(t).startswith('2019-05-') for spec in audit['upstream_configuration']['attack_to_time_window'] for t in spec[1:])):
        raise ValueError("This audit's UTC-04:00 comparison applies only to the reviewed May 2019 cases.")
    edt = timezone(timedelta(hours=-4))
    for item in audit['files']:
        path = CACHE / item['name']
        if not (hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']):
            raise ValueError('Published CSV bytes differ from their pinned SHA-256 hash.')
        case_nodes = {}
        for line, row in enumerate(csv.reader(path.open(encoding='utf-8', newline='')), 1):
            uid = uuid.UUID(row[0]).hex
            fields = ast.literal_eval(row[1])
            if not (len(row) == 3 and len(fields) == 1 and uid not in case_nodes):
                raise ValueError('CSV shape or UUID uniqueness disagrees with the reviewed source format.')
            kind = next(iter(fields))
            if not (kind in {'subject', 'file', 'netflow'}):
                raise ValueError('Unsupported public annotation node kind.')
            entry = {'case_file': item['name'], 'line_1based': line, 'node_kind': kind}
            nodes[uid].append(entry)
            case_nodes[uid] = kind
        spec = next(x for x in audit['upstream_configuration']['attack_to_time_window'] if x[0].endswith(item['name']))
        bounds = [int(datetime.fromisoformat(t).replace(tzinfo=edt).timestamp()) * 1_000_000_000 for t in spec[1:]]
        cases[item['name']] = {'source_url': item['source_url'], 'sha256': item['sha256'], 'nodes': case_nodes, 'utc_window_nanos': bounds,
                              'utc_window': [utc_nanos(t) for t in bounds], 'direct_node_touch_raw_event_records_in_scanned_prefixes': 0}

    if digest(REFERENCE / 'reference_report.json') != audit['current_gate']['reference_report_sha256_utf8_lf']:
        raise ValueError('Reference report differs from the pinned public-node audit.')
    ref = sqlite3.connect((REFERENCE / 'references.sqlite').as_uri() + '?mode=ro', uri=True)
    files = reusable_files(list(SOURCE.glob('*.gz')), REFERENCE)
    validate_cached_index(ref, files)
    report = {'review_date': '2026-10-27', 'public_annotation_audit_sha256_utf8_lf': digest(audit_file),
              'annotation_sha256_utf8_lf': digest(annotation_file), 'published_source_commit': audit['annotation_source']['commit'],
              'reference_report_sha256_utf8_lf': digest(REFERENCE / 'reference_report.json'),
              'reference_files_validated': len(files), 'csv_files_sha256_verified': len(cases),
              'timestamp_policy': 'Raw UTC nanoseconds preserved; only the four upstream May-2019 case windows are interpreted with EDT UTC-04:00 for a compatibility comparison.',
              'raw_record_hash_format': 'SHA-256 of UTF-8 json.dumps(clean(raw), sort_keys=True, separators=(comma,colon))',
              'case_summaries': [], 'scans': [], 'node_definitions': [], 'event_comparisons': []}

    # Reread only the prefixes containing our five current attack/candidate Events.
    # The excluded benign Event is compared from its unchanged prepared raw record.
    selected = {a['event_uuid']: a for a in annotations if a['label'] != 0}
    by_file = defaultdict(list)
    for a in selected.values():
        by_file[a['source_file']].append(a)
    actual = {}
    for filename, targets in by_file.items():
        path = SOURCE / filename
        limit = ((max(a['record_index_1based'] for a in targets) + 99999) // 100000) * 100000
        types = Counter()
        index = 0
        with gzip.open(path, 'rb') as stream:
            for index, raw in enumerate(itertools.islice(reader(stream), limit), 1):
                kind = raw['type']
                types[kind] += 1
                datum = raw['datum']; host = uuid_text(raw['hostId']); uid = uuid_text(datum.get('uuid'))
                if kind != 'RECORD_EVENT' and uid in nodes:
                    safe = clean(raw)
                    report['node_definitions'].append({'uuid': uid, 'host_uuid': host, 'kind': kind,
                        'source_file': filename, 'record_index_1based': index, 'raw_record_sha256': raw_hash(safe),
                        'cdm_object_type': datum.get('type'), 'upstream_memberships': nodes[uid]})
                if kind == 'RECORD_EVENT':
                    if uid in selected:
                        if not (uid not in actual):
                            raise ValueError('Duplicate selected Event UUID found in source prefixes.')
                        safe = clean(raw)
                        if not (safe == prepared[uid]['security_event']['raw_data']['cdm']):
                            raise ValueError('Fresh source Event differs from its prepared raw CDM record.')
                        if not (index == selected[uid]['record_index_1based'] and filename == selected[uid]['source_file']):
                            raise ValueError('Selected Event was found at an unexpected source position.')
                        actual[uid] = safe
                    timestamp = datum['timestampNanos']
                    refs = {uuid_text(datum.get(k)) for k in ['subject', 'predicateObject', 'predicateObject2']}
                    for case in cases.values():
                        lo, hi = case['utc_window_nanos']
                        if lo <= timestamp <= hi and refs.intersection(case['nodes']):
                            case['direct_node_touch_raw_event_records_in_scanned_prefixes'] += 1
                if index % 500000 == 0:
                    print(filename, index, flush=True)
        if not (index == limit):
            raise ValueError('Source ended before the configured review prefix.')
        report['scans'].append({'source_file': filename, 'records_read': index, 'complete_scan': False,
                               'record_type_counts': dict(types), 'compressed_bytes': path.stat().st_size,
                               'modified_time_ns': path.stat().st_mtime_ns,
                               'selected_event_uuids_reread': [a['event_uuid'] for a in targets]})
    if not (set(actual) == set(selected)):
        raise ValueError('A selected attack/candidate Event was absent from its source prefix.')

    for a in annotations:
        uid = a['event_uuid']; raw = actual.get(uid, prepared[uid]['security_event']['raw_data']['cdm'])
        datum = raw['datum']; host = raw['hostId']; timestamp = datum['timestampNanos']
        if not ((uid, host, timestamp, datum['type']) == (a['event_uuid'], a['host_uuid'], a['timestamp_nanos'], a['cdm_event_type'])):
            raise ValueError('Raw Event identity, host, timestamp or action disagrees with its annotation.')
        chain = resolve_chain(ref, datum['subject'], timestamp, host)
        process = next((s for s in chain if s.get('type') == 'SUBJECT_PROCESS'), None)
        process_valid = bool(process) and all(s['status'] == 'resolved' and s.get('started_at_or_before_event') is True for s in chain)
        roles = {k: datum.get(k) for k in ['subject', 'predicateObject', 'predicateObject2']}
        if process_valid:
            roles['resolved_actor_process'] = process['uuid']
        matches = []
        for role, identity in roles.items():
            for node in nodes.get(identity, []):
                case = cases[node['case_file']]
                lo, hi = case['utc_window_nanos']
                matches.append({'role': role, 'uuid': identity, **node, 'within_upstream_window': lo <= timestamp <= hi})
        row = {'event_uuid': uid, 'host_uuid': host, 'timestamp_nanos': timestamp, 'timestamp_utc': utc_nanos(timestamp),
               'cdm_event_type': datum['type'], 'subject_uuid': datum['subject'], 'predicate_object_uuid': datum.get('predicateObject'),
               'predicate_object_path': datum.get('predicateObjectPath'), 'source_file': a['source_file'],
               'record_index_1based': a['record_index_1based'], 'raw_source_reread_this_review': uid in actual,
               'raw_record_sha256': raw_hash(raw), 'upstream_matches': matches,
               'subject_chain': [{'uuid': s.get('uuid'), 'status': s['status'], 'type': s.get('type'), 'cid': s.get('cid'),
                                  'started_at_or_before_event': s.get('started_at_or_before_event')} for s in chain],
               'process_chain_resolved_and_time_valid': process_valid,
               'current_label': a['label'], 'decision_label': a['label'], 'group_id': a['group_id'],
               'split_eligible': a.get('split_eligible', True)}
        if a['label'] is None:
            if not (not process_valid):
                raise ValueError('A formerly unknown actor now resolves; perform a new action review before continuing.')
            row['decision'] = 'Retain unknown: direct thread and generated object match published Drakon nodes, but required actor parent remains missing; no node-touch label import.'
        elif a['label'] == 0:
            row['decision'] = 'Retain reviewed benign label and clock exclusion; no published-node match or clock repair.'
        else:
            row['decision'] = 'Retain existing action-specific report-reviewed positive; published matches are corroborating case evidence only.'
        report['event_comparisons'].append(row)

    for name, case in cases.items():
        summary = {k: v for k, v in case.items() if k != 'nodes'}
        summary['case_file'] = name
        summary['unique_nodes'] = len(case['nodes'])
        summary['direct_subject_matches_in_six_review_events'] = sum(any(m['case_file'] == name and m['role'] == 'subject' for m in e['upstream_matches']) for e in report['event_comparisons'])
        summary['direct_object_matches_in_six_review_events'] = sum(any(m['case_file'] == name and m['role'].startswith('predicateObject') for m in e['upstream_matches']) for e in report['event_comparisons'])
        summary['resolved_process_matches_in_six_review_events'] = sum(any(m['case_file'] == name and m['role'] == 'resolved_actor_process' for m in e['upstream_matches']) for e in report['event_comparisons'])
        report['case_summaries'].append(summary)

    report['records_reread_this_review'] = sum(f['records_read'] for f in report['scans'])
    report['new_labels_assigned'] = 0
    report['models_trained'] = False
    report['splits_created'] = False
    report['current_gate'] = audit['current_gate']
    report['scope_limits'] = ['Two bounded source prefixes, not a full 37-archive scan.',
        'Direct node-touch counts are candidate diagnostics, not verified attack labels or new training samples.',
        'No-hit cases do not establish absence from the full dataset.', 'No raw timestamp or PID was corrected.',
        'No independence is inferred from the count of CSV files or node UUIDs.']
    if not (digest(annotation_file) == report['annotation_sha256_utf8_lf']):
        raise ValueError('Reviewed annotation file changed during this audit.')
    (OUT / 'case_comparison.json').write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
    ref.close()
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--annotation-dir', required=True, type=Path)
    parser.add_argument('--reference-audit', required=True, type=Path)
    parser.add_argument('--prepared-events', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--annotations-path', type=Path, default=ROOT / 'data/ml/datasets/darpa/review_annotations.json')
    parser.add_argument('--public-audit-path', type=Path, default=ROOT / 'data/ml/datasets/darpa/public_node_annotation_audit_20261027.json')
    args = parser.parse_args()
    result = audit(**vars(args))
    print(json.dumps({'records_reread': result['records_reread_this_review'],
                      'review_events': len(result['event_comparisons']),
                      'new_labels_assigned': result['new_labels_assigned'],
                      'case_candidate_record_counts': {c['case_file']: c['direct_node_touch_raw_event_records_in_scanned_prefixes'] for c in result['case_summaries']},
                      'output': str(args.output / 'case_comparison.json')}, indent=2))


if __name__ == '__main__':
    main()
