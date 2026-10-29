"""Prepare native actor-window vectors for label-free activity reconstruction.

Only native Events supply predictors. Unknown security intent is never benign.
No graph, model, attack score, security threshold or detection metric is made.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3

from fastavro import reader

from research.ml.data_prep.inspect_fivedirections import natural_key, uuid_text
from research.ml.data_prep.resolve_references import clean, reusable_files
from research.ml.node_benchmark.background_review import canonical
from research.ml.node_benchmark.build_graphs import iso_nanos, select_sources, text_hash
from research.ml.node_benchmark.audit_protocol import file_hash

ROLES = ('train', 'development', 'holdout')
NS = 1_000_000_000


def validate_plan(plan):
    if (plan['version'] != 1 or plan['objective'] != 'unlabeled_activity_reconstruction_preparation'
            or plan['security_label'] is not None or plan['training_period_certified_normal'] is not False
            or plan['actor_assignment'] != 'first_selected_partition_later_rows_excluded'
            or plan['annotations_used_for_selection_or_features'] is not False):
        raise ValueError('Require the separate label-free objective and unknown security labels')
    horizon = plan['window_nanos']
    if type(horizon) is not int or horizon <= 0 or plan['purge_gap_nanos'] < horizon:
        raise ValueError('Require a positive history and a purge gap at least as long')
    actions = plan['action_vocabulary']
    if not actions or len(actions) != len(set(actions)) or any(not a.startswith('EVENT_') for a in actions):
        raise ValueError('Action vocabulary must be fixed, unique native action names')
    windows, previous_end = [], None
    for role in ROLES:
        interval = plan['partitions'][role]
        start, end = iso_nanos(interval['start_utc']), iso_nanos(interval['end_utc'])
        if end <= start or (end-start) % horizon:
            raise ValueError('Partitions must contain whole nonempty history windows')
        if previous_end is not None and start-previous_end < plan['purge_gap_nanos']:
            raise ValueError('Partitions need chronological purge gaps')
        while start < end:
            windows.append(dict(index=len(windows), role=role, start_nanos=start,
                                end_nanos=start+horizon, anchor_nanos=start+horizon-1))
            start += horizon
        previous_end = end
    if plan['minimum_samples_per_partition'] < 1 or plan['maximum_actor_windows'] < 1:
        raise ValueError('Use positive sample-count and memory bounds')
    return windows


def feature_names(actions):
    return ['event_count'] + ['count_'+a for a in actions] + ['count_unknown_action',
        'predicate_reference_count', 'second_predicate_event_count',
        'no_predicate_event_count', 'active_span_seconds']


def new_state(width, ts, uid, source, index):
    return dict(values=[0]*width, first_ns=ts, last_ns=ts,
                witness=(ts, uid, source, index))


def aggregate(db, actions, maximum):
    positions = {a:i+1 for i,a in enumerate(actions)}
    width = len(feature_names(actions))
    groups = {}
    for window, host, actor, ts, uid, action, first, second, source, index in db.execute(
            'SELECT window_idx,host,actor,ts,uuid,action,obj1,obj2,source_file,record_idx FROM events '
            'WHERE conflict=0 AND window_idx>=0 AND actor IS NOT NULL'):
        key = (window, host, actor)
        state = groups.get(key)
        if state is None:
            if len(groups) >= maximum:
                raise ValueError('Actor-window memory bound exceeded; no silent subsampling')
            state = groups[key] = new_state(width, ts, uid, source, index)
        values = state['values']
        values[0] += 1
        values[positions.get(action, len(actions)+1)] += 1
        values[-4] += int(first is not None)+int(second is not None)
        values[-3] += int(second is not None)
        values[-2] += int(first is None and second is None)
        state['first_ns'] = min(state['first_ns'], ts)
        state['last_ns'] = max(state['last_ns'], ts)
        state['witness'] = min(state['witness'], (ts, uid, source, index))
    for state in groups.values():
        state['values'][-1] = (state['last_ns']-state['first_ns'])/NS
    return groups


def split_actors(groups, windows):
    owners, kept, dropped = {}, {role:[] for role in ROLES}, Counter()
    for key, state in sorted(groups.items()):
        window, host, actor = key
        role = windows[window]['role']
        owner = owners.setdefault((host, actor), role)
        if owner != role:
            dropped[role] += 1
            continue
        kept[role].append((key, state))
    return kept, dict(dropped)


def fit_scaler(rows, width):
    if not rows:
        raise ValueError('Cannot fit preprocessing without training samples')
    if any(len(row) != width or any(not math.isfinite(v) or v < 0 for v in row) for row in rows):
        raise ValueError('Feature vectors must be finite nonnegative values with the fixed width')
    transformed = [[math.log1p(v) for v in row] for row in rows]
    means = [math.fsum(row[i] for row in transformed)/len(rows) for i in range(width)]
    variances = [math.fsum((row[i]-means[i])**2 for row in transformed)/len(rows) for i in range(width)]
    stds = [math.sqrt(v) if v > 1e-24 else 1.0 for v in variances]
    return dict(transform='log1p_then_training_population_zscore', fitted_on='train_only',
        training_samples=len(rows), means=means, standard_deviations=stds,
        constant_columns=[i for i,v in enumerate(variances) if v <= 1e-24],
        constant_column_scale=1.0)


def transform(values, scaler):
    if len(values) != len(scaler['means']) or len(values) != len(scaler['standard_deviations']):
        raise ValueError('Scaler and feature vector widths differ')
    result = [(math.log1p(v)-m)/s for v,m,s in zip(values, scaler['means'], scaler['standard_deviations'])]
    if len(result) != len(values) or any(not math.isfinite(v) for v in result):
        raise ValueError('Invalid transformed feature vector')
    return result


def context_overlap(db, kept):
    db.execute('CREATE TABLE kept_pairs(window_idx INTEGER,host TEXT,actor TEXT,role TEXT,PRIMARY KEY(window_idx,host,actor)) WITHOUT ROWID')
    db.executemany('INSERT INTO kept_pairs VALUES (?,?,?,?)',
                  [(k[0],k[1],k[2],role) for role,rows in kept.items() for k,_ in rows])
    db.execute('CREATE TABLE context_ids(role TEXT,host TEXT,uuid TEXT,PRIMARY KEY(role,host,uuid)) WITHOUT ROWID')
    for field in ('obj1','obj2'):
        db.execute('INSERT OR IGNORE INTO context_ids SELECT k.role,e.host,e.'+field+
            ' FROM events e JOIN kept_pairs k ON k.window_idx=e.window_idx AND k.host=e.host AND k.actor=e.actor '
            'WHERE e.conflict=0 AND e.'+field+' IS NOT NULL')
    result = {}
    for left,right in (('train','development'),('train','holdout'),('development','holdout')):
        result[left+'/'+right] = db.execute('SELECT COUNT(*) FROM context_ids a JOIN context_ids b '
            'ON a.host=b.host AND a.uuid=b.uuid WHERE a.role=? AND b.role=?',(left,right)).fetchone()[0]
    db.commit()
    return result


def prepare(source, plan_path, reference_audit, output):
    source, output = source.resolve(), output.resolve()
    if output.exists() or source == output or source in output.parents:
        raise ValueError('Use a fresh output directory outside raw data')
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    windows = validate_plan(plan)
    if text_hash(reference_audit/'reference_report.json') != plan['source_reference_report_sha256_utf8_lf']:
        raise ValueError('Source audit snapshot changed')
    paths = list(source.rglob('*.gz'))
    files = reusable_files(paths, reference_audit)
    if len({p.name for p in paths}) != len(paths) or {p.name for p in paths} != {f['filename'] for f in files}:
        raise ValueError('Raw inventory differs from the audited subset')
    envelope = dict(case_id='label-free-envelope', host_uuid=plan['host_uuid'], file_prefix=plan['file_prefix'],
                    start_nanos=windows[0]['start_nanos'], end_nanos=windows[-1]['end_nanos'])
    names = select_sources(files, [envelope])
    if not names:
        raise ValueError('No local source overlaps the requested interval')
    # Fail before extraction if a declared partition has no available source bounds.
    for window in windows:
        if not select_sources(files, [dict(window,case_id=str(window['index']),file_prefix=plan['file_prefix'])]):
            raise ValueError('A declared window has no source-bound overlap')
    if shutil.disk_usage(next(p for p in output.parents if p.exists())).free < 3*1024**3:
        raise ValueError('At least 3 GiB free working space is required for the bounded dedup index')
    by_name, expected = {p.name:p for p in paths}, {f['filename']:f for f in files}
    output.mkdir(parents=True)
    report = dict(status='preparing_label_free_features', plan_sha256_utf8_lf=text_hash(plan_path),
        producer_sha256_utf8_lf=text_hash(Path(__file__)),
        source_reference_report_sha256_utf8_lf=text_hash(reference_audit/'reference_report.json'),
        source_inventory_files=len(files), windows=windows, scans=[],
        representation='native_actor_five_minute_numeric_activity_vector',
        security_labels='unknown_for_every_sample', training_period_certified_normal=False,
        annotation_content_read=False, metadata_predictors_used=False, native_uuid_values_are_predictors=False,
        clock_corrections_applied=False, models_selected_or_trained=False,
        supervised_task_completed=False, attack_detection_accuracy_established=False)
    save = lambda: (output/'manifest.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    save()
    try:
        with closing(sqlite3.connect(output/'events.sqlite')) as db:
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('PRAGMA max_page_count=524288')  # 2 GiB at the required 4096-byte page size.
            if db.execute('PRAGMA page_size').fetchone()[0] != 4096:
                raise ValueError('Unexpected SQLite page size for the bounded index')
            db.execute('CREATE TABLE events(host TEXT,uuid TEXT,window_idx INTEGER,ts INTEGER,actor TEXT,action TEXT,'
                'obj1 TEXT,obj2 TEXT,fingerprint BLOB,source_file TEXT,record_idx INTEGER,conflict INTEGER DEFAULT 0,'
                'occurrences INTEGER DEFAULT 1,PRIMARY KEY(host,uuid)) WITHOUT ROWID')
            insert = ('INSERT INTO events(host,uuid,window_idx,ts,actor,action,obj1,obj2,fingerprint,source_file,record_idx) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(host,uuid) DO UPDATE SET occurrences=occurrences+1,'
                'conflict=CASE WHEN fingerprint<>excluded.fingerprint THEN 1 ELSE conflict END')
            raw_window_counts, raw_envelope, batch = Counter(), 0, []
            for name in sorted(names,key=lambda n:natural_key(Path(n))):
                kinds, index = Counter(), 0
                with gzip.open(by_name[name],'rb') as stream:
                    for index,raw in enumerate(reader(stream),1):
                        kinds[raw['type']] += 1
                        if index % 2_000_000 == 0:
                            print(json.dumps(dict(filename=name,records=index,raw_envelope_events=raw_envelope)),flush=True)
                        if raw['type'] != 'RECORD_EVENT' or uuid_text(raw.get('hostId')) != plan['host_uuid']:
                            continue
                        datum = raw['datum']; ts = datum.get('timestampNanos')
                        if type(ts) is not int or not envelope['start_nanos'] <= ts < envelope['end_nanos']:
                            continue
                        uid = uuid_text(datum.get('uuid'))
                        if not uid:
                            raise ValueError('Selected native Event has no UUID')
                        raw_envelope += 1
                        window_idx = next((w['index'] for w in windows if w['start_nanos'] <= ts < w['end_nanos']),-1)
                        raw_window_counts[window_idx] += 1
                        batch.append((plan['host_uuid'],uid,window_idx,ts,uuid_text(datum.get('subject')),datum.get('type'),
                            uuid_text(datum.get('predicateObject')),uuid_text(datum.get('predicateObject2')),
                            hashlib.sha256(canonical(clean(raw))).digest(),name,index))
                        if len(batch) >= 5000:
                            db.executemany(insert,batch); db.commit(); batch.clear()
                    if stream.read(1):
                        raise ValueError('Unexpected trailing Avro bytes')
                if batch:
                    db.executemany(insert,batch); db.commit(); batch.clear()
                if index != expected[name]['records'] or dict(kinds) != expected[name]['record_type_counts']:
                    raise ValueError('Complete source record/type counts changed')
                report['scans'].append(dict(filename=name,records=index,record_type_counts=dict(kinds),
                    complete_scan=True,gzip_exhaustion_verified=True,compressed_bytes=expected[name]['compressed_bytes']))
                save()
            reusable_files(paths,reference_audit)
            groups = aggregate(db,plan['action_vocabulary'],plan['maximum_actor_windows'])
            kept,dropped = split_actors(groups,windows)
            counts = {r:len(kept[r]) for r in ROLES}
            report.update(raw_events_in_envelope=raw_envelope,raw_event_records_per_window=dict(raw_window_counts),
                unique_envelope_events=db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                conflicting_event_uuids=db.execute('SELECT COUNT(*) FROM events WHERE conflict=1').fetchone()[0],
                identical_duplicate_occurrences=db.execute('SELECT COALESCE(SUM(occurrences-1),0) FROM events WHERE conflict=0').fetchone()[0],
                dedup_conflict_scope='Available selected streams, same-host full time envelope including purge gaps only',
                unique_nonconflicting_selected_events=db.execute('SELECT COUNT(*) FROM events WHERE conflict=0 AND window_idx>=0').fetchone()[0],
                selected_events_without_native_actor=db.execute('SELECT COUNT(*) FROM events WHERE conflict=0 AND window_idx>=0 AND actor IS NULL').fetchone()[0],
                actor_windows_before_ownership_purge=len(groups), dropped_later_partition_actor_windows=dropped,
                partition_sample_counts=counts)
            if any(c < plan['minimum_samples_per_partition'] for c in counts.values()):
                raise ValueError('Insufficient actor-disjoint samples; do not silently weaken the split rule')
            schema = feature_names(plan['action_vocabulary'])
            scaler = fit_scaler([s['values'] for _,s in kept['train']],len(schema))
            (output/'scaler.json').write_bytes((json.dumps(scaler,indent=2)+'\n').encode())
            (output/'feature_schema.json').write_bytes((json.dumps(dict(names=schema,width=len(schema),
                source='Native Event fields only; fixed action vocabulary, never fitted on held-out data',
                units='Counts except active_span_seconds',security_label_is_predictor=False),indent=2)+'\n').encode())
            hashes, profiles, actors, exported_events = {}, {}, {}, {}
            for role in ROLES:
                profiles[role],actors[role],exported_events[role] = set(),set(),0
                with (output/(role+'.jsonl')).open('wb') as stream:
                    for (window_idx,host,actor),state in kept[role]:
                        window = windows[window_idx]
                        sample_id = hashlib.sha256(canonical([host,actor,window['start_nanos'],window['end_nanos']])).hexdigest()
                        witness = state['witness']
                        trace = dict(host_uuid=host,subject_uuid=actor,window_start_nanos=window['start_nanos'],
                            window_end_nanos=window['end_nanos'],anchor_nanos=window['anchor_nanos'],
                            first_event_nanos=state['first_ns'],last_event_nanos=state['last_ns'],
                            witness_event_uuid=witness[1],witness_source_file=witness[2],witness_record_index_1based=witness[3])
                        stream.write(canonical(dict(sample_id=sample_id,trace=trace,raw_features=state['values'],
                            features=transform(state['values'],scaler),security_label=None))+'\n'.encode())
                        profiles[role].add(hashlib.sha256(canonical(state['values'])).hexdigest())
                        actors[role].add((host,actor)); exported_events[role] += state['values'][0]
                hashes[role] = file_hash(output/(role+'.jsonl'))
            pairs = [('train','development'),('train','holdout'),('development','holdout')]
            actor_overlaps = {a+'/'+b:len(actors[a]&actors[b]) for a,b in pairs}
            if any(actor_overlaps.values()):
                raise ValueError('Actor identities leaked across partitions')
            context = context_overlap(db,kept)
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Deduplication index integrity check failed')
            report.update(feature_count=len(schema), feature_names=schema, scaler_fit_on='train_only',
                constant_training_feature_count=len(scaler['constant_columns']),
                sample_actor_overlap=actor_overlaps,shared_object_context_counts=context,
                common_raw_feature_profile_counts={a+'/'+b:len(profiles[a]&profiles[b]) for a,b in pairs},
                exported_native_event_counts=exported_events,partition_file_sha256=hashes,
                scaler_sha256=file_hash(output/'scaler.json'),feature_schema_sha256=file_hash(output/'feature_schema.json'),
                security_label_counts=dict(unknown=sum(counts.values()),attack=0,benign=0),
                temporal_purge_gap_nanos=plan['purge_gap_nanos'],
                context_identity_isolation_proven=False,incident_independence_established=False,
                scope='Same-host same-day actor-disjoint label-free preparation, not an independent attack benchmark')
        report.update(status='complete_label_free_preparation_not_trained',
            dedup_index_bytes=(output/'events.sqlite').stat().st_size,
            limitations=['Unlabeled training data may contain attacks; no certified normal-data claim',
                'First-selected-partition ownership biases later data toward newly observed actors, which may be threads',
                'Common object context and identical feature profiles remain; no independent incident or host-generalization claim',
                'No metadata availability or process-lineage inference is used by these aggregate vectors',
                'Feature artifacts are model inputs, not anomaly scores, attack predictions or detection metrics'])
        save(); return report
    except BaseException as error:
        report.update(status='incomplete_failed',error=str(error)); save(); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','plan','reference-audit','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    result = prepare(args.source,args.plan,args.reference_audit,args.output)
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
