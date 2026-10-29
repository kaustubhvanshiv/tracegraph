"""Recompute prepared label-free vectors with independent SQL aggregates."""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from research.ml.label_free.prepare import ROLES, validate_plan
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash


def verify(directory, plan_path, output):
    if output.exists():
        raise ValueError('Use a fresh verification report path')
    report = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    windows = validate_plan(plan)
    if (report['status'] != 'complete_label_free_preparation_not_trained'
            or report['plan_sha256_utf8_lf'] != text_hash(plan_path)
            or report['windows'] != windows or report['models_selected_or_trained'] is not False):
        raise ValueError('Prepared snapshot does not match the frozen label-free plan')
    scaler = json.loads((directory/'scaler.json').read_text())
    names = json.loads((directory/'feature_schema.json').read_text())['names']
    actions = plan['action_vocabulary']
    expected_names = ['event_count']+['count_'+a for a in actions]+['count_unknown_action',
        'predicate_reference_count','second_predicate_event_count','no_predicate_event_count','active_span_seconds']
    if names != expected_names or len(names) != report['feature_count']:
        raise ValueError('Numeric schema changed')
    if len(scaler['means']) != len(names) or len(scaler['standard_deviations']) != len(names):
        raise ValueError('Scaler width differs from the fixed numeric schema')
    if file_hash(directory/'scaler.json') != report['scaler_sha256']:
        raise ValueError('Scaler fingerprint changed')
    if file_hash(directory/'feature_schema.json') != report['feature_schema_sha256']:
        raise ValueError('Feature schema fingerprint changed')
    with closing(sqlite3.connect((directory/'events.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Deduplication index failed integrity check')
        aggregates = {tuple(row[:3]):row[3:] for row in db.execute(
            'SELECT window_idx,host,actor,COUNT(*),MIN(ts),MAX(ts),'
            'SUM((obj1 IS NOT NULL)+(obj2 IS NOT NULL)),SUM(obj2 IS NOT NULL),SUM(obj1 IS NULL AND obj2 IS NULL) '
            'FROM events WHERE conflict=0 AND window_idx>=0 AND actor IS NOT NULL GROUP BY window_idx,host,actor')}
        action_counts = defaultdict(dict)
        for window,host,actor,action,count in db.execute('SELECT window_idx,host,actor,action,COUNT(*) FROM events '
                'WHERE conflict=0 AND window_idx>=0 AND actor IS NOT NULL GROUP BY window_idx,host,actor,action'):
            action_counts[(window,host,actor)][action] = count
        ownership, expected = {}, {role:set() for role in ROLES}
        for key in sorted(aggregates):
            role = windows[key[0]]['role']
            if ownership.setdefault(key[1:],role) == role:
                expected[role].add(key)
        rows, actors, sample_ids = {}, {}, set()
        for role in ROLES:
            if file_hash(directory/(role+'.jsonl')) != report['partition_file_sha256'][role]:
                raise ValueError('Partition fingerprint changed')
            rows[role] = [json.loads(line) for line in (directory/(role+'.jsonl')).read_text().splitlines()]
            seen,actors[role] = set(),set()
            for row in rows[role]:
                trace = row['trace']
                indices = [w['index'] for w in windows if w['start_nanos'] == trace['window_start_nanos']
                           and w['end_nanos'] == trace['window_end_nanos'] and w['role'] == role]
                if len(indices) != 1 or row['security_label'] is not None:
                    raise ValueError('Wrong partition window or fabricated security label')
                key = (indices[0],trace['host_uuid'],trace['subject_uuid'])
                if key not in expected[role] or key in seen:
                    raise ValueError('Duplicate, missing or wrongly assigned actor window')
                seen.add(key);actors[role].add(key[1:])
                event_count,first,last,references,second,missing = aggregates[key]
                counts = action_counts[key]
                vector = [event_count]+[counts.get(a,0) for a in actions]+[
                    sum(c for a,c in counts.items() if a not in actions),references,second,missing,(last-first)/1e9]
                if row['raw_features'] != vector or len(row['features']) != len(vector):
                    raise ValueError('Feature vector differs from independent native-Event aggregates')
                window = windows[key[0]]
                if not window['start_nanos'] <= first <= last < window['end_nanos']:
                    raise ValueError('Future or out-of-window Event entered a feature vector')
                if trace['anchor_nanos'] != window['end_nanos']-1 or (trace['first_event_nanos'],trace['last_event_nanos']) != (first,last):
                    raise ValueError('Trace timestamps changed')
                fingerprint = hashlib.sha256(json.dumps([key[1],key[2],window['start_nanos'],window['end_nanos']],
                    sort_keys=True,separators=(',',':')).encode()).hexdigest()
                if row['sample_id'] != fingerprint or fingerprint in sample_ids:
                    raise ValueError('Sample identity changed or duplicated')
                sample_ids.add(fingerprint)
                witness = db.execute('SELECT actor,window_idx,ts,source_file,record_idx,conflict FROM events WHERE host=? AND uuid=?',
                    (key[1],trace['witness_event_uuid'])).fetchone()
                if witness != (key[2],key[0],first,trace['witness_source_file'],trace['witness_record_index_1based'],0):
                    raise ValueError('Native source witness changed')
            if seen != expected[role] or len(seen) != report['partition_sample_counts'][role]:
                raise ValueError('Prepared sample universe was silently changed')
        contexts = {r:set() for r in ROLES}
        key_roles = {key:role for role,keys in expected.items() for key in keys}
        for window,host,actor,obj1,obj2 in db.execute('SELECT window_idx,host,actor,obj1,obj2 FROM events '
                'WHERE conflict=0 AND window_idx>=0 AND actor IS NOT NULL'):
            role = key_roles.get((window,host,actor))
            if role:
                for obj in (obj1,obj2):
                    if obj is not None:
                        contexts[role].add((host,obj))
        context_pairs = [('train','development'),('train','holdout'),('development','holdout')]
        context_counts = {a+'/'+b:len(contexts[a]&contexts[b]) for a,b in context_pairs}
        if context_counts != report['shared_object_context_counts']:
            raise ValueError('Shared native object context was incorrectly reported')
    training = [[math.log1p(v) for v in row['raw_features']] for row in rows['train']]
    if len(training) != scaler['training_samples'] or scaler['fitted_on'] != 'train_only':
        raise ValueError('Scaler fit scope changed')
    expected_means = [math.fsum(row[i] for row in training)/len(training) for i in range(len(names))]
    expected_vars = [math.fsum((row[i]-expected_means[i])**2 for row in training)/len(training) for i in range(len(names))]
    expected_stds = [math.sqrt(v) if v>1e-24 else 1.0 for v in expected_vars]
    close = lambda a,b: math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
    if (any(not close(a,b) for a,b in zip(expected_means,scaler['means']))
            or any(not close(a,b) for a,b in zip(expected_stds,scaler['standard_deviations']))):
        raise ValueError('Scaler statistics were not fit on exactly the training rows')
    for role in ROLES:
        for row in rows[role]:
            wanted = [(math.log1p(v)-m)/s for v,m,s in zip(row['raw_features'],expected_means,expected_stds)]
            if any(not math.isfinite(a) or not close(a,b) for a,b in zip(row['features'],wanted)):
                raise ValueError('Normalized vector changed')
    pairs = [('train','development'),('train','holdout'),('development','holdout')]
    overlaps = {a+'/'+b:len(actors[a]&actors[b]) for a,b in pairs}
    if any(overlaps.values()):
        raise ValueError('Native actor identity overlaps partitions')
    result = dict(status='verified_label_free_preparation', verifier_sha256_utf8_lf=text_hash(Path(__file__)),
        plan_sha256_utf8_lf=text_hash(plan_path), manifest_sha256_utf8_lf=text_hash(directory/'manifest.json'),
        independently_recomputed_vectors=sum(map(len,rows.values())),feature_count=len(names),
        partition_sample_counts={r:len(rows[r]) for r in ROLES},sample_actor_overlap=overlaps,
        independent_sql_feature_reaggregation=True,training_only_scaler_recomputed=True,
        all_security_labels_unknown=True,temporal_windows_and_witnesses_verified=True,
        source_validation_scope='Saved disk-backed native Event index; raw archives not reread by this verifier',
        shared_object_context_counts=report['shared_object_context_counts'],
        incident_independence_established=False,models_trained=False,attack_detection_metrics_available=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('directory','plan','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory,args.plan,args.output)),flush=True)


if __name__=='__main__':
    main()
