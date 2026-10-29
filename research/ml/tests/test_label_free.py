"""Label-free preparation must preserve unknown intent and honest holdouts."""
import copy
import gzip
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastavro import writer

from research.ml.data_prep.inspect_fivedirections import utc_nanos
from research.ml.node_benchmark.build_graphs import text_hash
from research.ml.label_free.prepare import (
    aggregate, feature_names, fit_scaler, prepare, split_actors, transform, validate_plan,
)
from research.ml.label_free.verify import verify
from research.ml.node_benchmark.audit_protocol import file_hash
from research.ml.tests.test_recover_metadata import SCHEMA, HOST, OTHER_HOST, TARGET, ACTOR, OTHER

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/'data/ml/datasets/darpa/label_free/preparation_plan_20261029.json'


class LabelFreeTests(unittest.TestCase):
    def plan(self):
        plan = json.loads(PLAN.read_text())
        plan.update(host_uuid=HOST,window_nanos=10,purge_gap_nanos=10,
            minimum_samples_per_partition=1,action_vocabulary=['EVENT_READ','EVENT_WRITE'])
        plan['partitions'] = {role:dict(start_utc=utc_nanos(start),end_utc=utc_nanos(end))
            for role,start,end in [('train',10,30),('development',40,50),('holdout',60,70)]}
        return plan

    def test_label_objective_purge_and_whole_history_rules_are_enforced(self):
        plan = self.plan()
        windows = validate_plan(plan)
        self.assertEqual([(w['start_nanos'],w['end_nanos']) for w in windows],[(10,20),(20,30),(40,50),(60,70)])
        for key,value in [('security_label',0),('training_period_certified_normal',True),
                          ('annotations_used_for_selection_or_features',True),('purge_gap_nanos',9)]:
            changed = copy.deepcopy(plan); changed[key] = value
            with self.subTest(rule=key), self.assertRaises(ValueError): validate_plan(changed)
        plan['partitions']['development']['start_utc'] = utc_nanos(35)
        with self.assertRaises(ValueError): validate_plan(plan)

    def test_scaler_uses_training_only_and_handles_constant_columns(self):
        train = [[0,2,0],[2,2,3]]
        scaler = fit_scaler(train,3)
        self.assertEqual(scaler['constant_columns'],[1])
        self.assertEqual(scaler['standard_deviations'][1],1)
        self.assertAlmostEqual(scaler['means'][0],math.log(3)/2)
        saved = copy.deepcopy(scaler)
        transformed = transform([1000000,999,1000000],scaler)
        self.assertEqual(scaler,saved)
        self.assertTrue(all(math.isfinite(v) for v in transformed))
        self.assertGreater(transformed[0],1)
        with self.assertRaises(ValueError): fit_scaler([[-1,0,0]],3)
        with self.assertRaises(ValueError): transform([0],scaler)

    def test_actor_ownership_drops_only_later_partition_windows(self):
        windows = validate_plan(self.plan())
        groups = {(3,HOST,ACTOR):{'values':[1]},(1,HOST,ACTOR):{'values':[1]},
            (0,HOST,ACTOR):{'values':[1]},(2,HOST,OTHER):{'values':[1]},(3,HOST,TARGET):{'values':[1]}}
        kept,dropped = split_actors(groups,windows)
        self.assertEqual({r:len(v) for r,v in kept.items()},{'train':2,'development':1,'holdout':1})
        self.assertEqual(dropped,{'holdout':1})

    def fixture(self, base):
        source, ref = base/'source',base/'ref'
        source.mkdir();ref.mkdir()
        schema = copy.deepcopy(SCHEMA)
        schema['fields'][0]['type'][2]['fields'].extend([
            dict(name='timestampNanos',type='long'),dict(name='type',type='string')])
        def event(uid,ts,actor=ACTOR,action='EVENT_READ',host=HOST,target=TARGET):
            return dict(type='RECORD_EVENT',hostId=bytes.fromhex(host),datum=('Event',dict(
                uuid=bytes.fromhex(f'{uid:032x}'),subject=bytes.fromhex(actor),
                predicateObject=bytes.fromhex(target),timestampNanos=ts,type=action)))
        records = [event(101,11),event(102,21,action='EVENT_WRITE'),event(103,41,OTHER),
            event(104,61,TARGET,action='EVENT_UNSEEN'),event(105,42),event(106,62),
            event(101,11),event(107,12),event(107,35,action='EVENT_WRITE'),
            event(108,50,OTHER),event(109,43,host=OTHER_HOST),event(110,70,TARGET)]
        # Backward timestamps and a conflict in the purge gap must not escape.
        path = source/'ta1-fivedirections-1-e5-official-1.bin.gz'
        with gzip.open(path,'wb') as stream: writer(stream,schema,records)
        (ref/'references.sqlite').write_bytes(b'not read: no metadata used')
        item = dict(filename=path.name,records=len(records),complete_scan=True,
            compressed_bytes=path.stat().st_size,modified_time_ns=path.stat().st_mtime_ns,
            record_type_counts={'RECORD_EVENT':len(records)},min_event_utc=utc_nanos(11),max_event_utc=utc_nanos(70))
        (ref/'reference_report.json').write_text(json.dumps(dict(all_files_fully_scanned=True,files=[item])),encoding='utf-8')
        plan = self.plan();plan['source_reference_report_sha256_utf8_lf'] = text_hash(ref/'reference_report.json')
        plan_path = base/'plan.json';plan_path.write_text(json.dumps(plan),encoding='utf-8')
        return source,plan_path,ref

    def test_complete_native_run_deduplicates_quarantines_and_reproduces_features(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); args=self.fixture(base)
            first=prepare(*args,base/'first');second=prepare(*args,base/'second')
            self.assertEqual(first['status'],'complete_label_free_preparation_not_trained')
            self.assertEqual(first['partition_sample_counts'],{'train':2,'development':1,'holdout':1})
            self.assertEqual(first['conflicting_event_uuids'],1)
            self.assertEqual(first['identical_duplicate_occurrences'],1)
            self.assertEqual(first['unique_nonconflicting_selected_events'],6)
            self.assertEqual(first['dropped_later_partition_actor_windows'],{'development':1,'holdout':1})
            self.assertEqual(first['sample_actor_overlap'],{'train/development':0,'train/holdout':0,'development/holdout':0})
            self.assertEqual(first['partition_file_sha256'],second['partition_file_sha256'])
            self.assertEqual(first['scaler_sha256'],second['scaler_sha256'])
            self.assertFalse(first['models_selected_or_trained'])
            self.assertFalse(first['training_period_certified_normal'])
            self.assertGreater(first['shared_object_context_counts']['train/development'],0)
            holdout=json.loads((base/'first/holdout.jsonl').read_text())
            self.assertIsNone(holdout['security_label'])
            names=feature_names(['EVENT_READ','EVENT_WRITE'])
            self.assertEqual(holdout['raw_features'][names.index('count_unknown_action')],1)
            self.assertEqual(holdout['trace']['window_end_nanos'],70)
            self.assertTrue(all(math.isfinite(v) for v in holdout['features']))
            with self.assertRaisesRegex(ValueError,'fresh'): prepare(*args,base/'first')

    def test_insufficient_disjoint_rows_never_silently_relax_the_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); args=self.fixture(base)
            plan=json.loads(args[1].read_text());plan['minimum_samples_per_partition']=2
            args[1].write_text(json.dumps(plan),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Insufficient actor-disjoint'):
                prepare(*args,base/'incomplete')
            report=json.loads((base/'incomplete/manifest.json').read_text())
            self.assertEqual(report['status'],'incomplete_failed')
            self.assertFalse((base/'incomplete/train.jsonl').exists())

    def test_complete_source_counts_and_memory_bounds_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); args=self.fixture(base)
            reference=json.loads((args[2]/'reference_report.json').read_text())
            reference['files'][0]['records']+=1
            (args[2]/'reference_report.json').write_text(json.dumps(reference),encoding='utf-8')
            plan=json.loads(args[1].read_text())
            plan['source_reference_report_sha256_utf8_lf']=text_hash(args[2]/'reference_report.json')
            args[1].write_text(json.dumps(plan),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'record/type counts'):
                prepare(*args,base/'incomplete')
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.execute('CREATE TABLE events(window_idx,host,actor,ts,uuid,action,obj1,obj2,source_file,record_idx,conflict)')
        db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,0)',
            [(0,HOST,ACTOR,11,'a','EVENT_READ',TARGET,None,'x',1),(0,HOST,OTHER,12,'b','EVENT_READ',TARGET,None,'x',2)])
        with self.assertRaisesRegex(ValueError,'memory bound'):
            aggregate(db,['EVENT_READ'],1)

    def test_sql_verifier_rejects_relabeled_or_changed_vectors_with_updated_digests(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);args=self.fixture(base);directory=base/'prepared'
            report=prepare(*args,directory)
            verified=verify(directory,args[1],base/'verified.json')
            self.assertEqual(verified['independently_recomputed_vectors'],4)
            self.assertTrue(verified['all_security_labels_unknown'])
            path=directory/'holdout.jsonl';original=json.loads(path.read_text())
            for change in ('label','features'):
                row=copy.deepcopy(original)
                if change=='label':row['security_label']=0
                else:row['raw_features'][0]+=1
                path.write_text(json.dumps(row)+'\n',encoding='utf-8')
                report['partition_file_sha256']['holdout']=file_hash(path)
                (directory/'manifest.json').write_text(json.dumps(report),encoding='utf-8')
                with self.subTest(change=change),self.assertRaises(ValueError):
                    verify(directory,args[1],base/('bad-'+change+'.json'))

    def test_sql_verifier_recomputes_scaler_and_shared_context(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);args=self.fixture(base);directory=base/'prepared'
            report=prepare(*args,directory)
            scaler_path=directory/'scaler.json';original=scaler_path.read_bytes()
            scaler=json.loads(original);scaler['means'][0]+=100
            scaler_path.write_text(json.dumps(scaler),encoding='utf-8')
            report['scaler_sha256']=file_hash(scaler_path)
            (directory/'manifest.json').write_text(json.dumps(report),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'statistics were not fit'):
                verify(directory,args[1],base/'bad-scaler.json')
            scaler_path.write_bytes(original)
            report['scaler_sha256']=file_hash(scaler_path)
            report['shared_object_context_counts']['train/development']=0
            (directory/'manifest.json').write_text(json.dumps(report),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'object context'):
                verify(directory,args[1],base/'bad-context.json')


if __name__=='__main__':
    unittest.main()
