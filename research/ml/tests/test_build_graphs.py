"""Software invariants for graph extraction; fixtures are not training data."""
import csv
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastavro import writer

from research.ml.node_benchmark.build_graphs import GraphStore, build, select_sources, iso_nanos
from research.ml.data_prep.inspect_fivedirections import utc_nanos


class CompactGraphTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.graph = GraphStore(self.db)
        self.case = {"case_id":"case-a","host_uuid":"host-a","start_nanos":10,"end_nanos":20}
        self.db.execute("INSERT INTO cases VALUES ('case-a','host-a',10,20)")

    def event(self, uid="e", timestamp=12, subject="s", target="f"):
        return {"hostId":"host-a","type":"RECORD_EVENT","datum":{
            "uuid":uid,"timestampNanos":timestamp,"type":"EVENT_OPEN",
            "subject":subject,"predicateObject":target,"predicateObjectPath":"C:/observed.txt"}}

    def test_scope_uses_native_host_and_half_open_time_not_arrival_order(self):
        self.assertFalse(self.graph.event(self.case,self.event("after",20),1,1))
        self.assertTrue(self.graph.event(self.case,self.event("inside",11),1,2))
        wrong=self.event("wrong-host");wrong["hostId"]="host-b"
        self.assertFalse(self.graph.event(self.case,wrong,1,3))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],1)

    def test_equal_uuid_on_other_host_cannot_supply_metadata(self):
        a=self.graph.node("host-a","same");b=self.graph.node("host-b","same")
        self.assertNotEqual(a,b)
        self.graph.apply_metadata(b,"RECORD_FILE_OBJECT",{"type":"FILE_OBJECT_FILE"},"other")
        self.assertEqual(self.db.execute("SELECT metadata_status FROM nodes WHERE id=?",(a,)).fetchone()[0],"unresolved")

    def test_duplicate_event_keeps_source_occurrences_conflict_is_withheld(self):
        raw=self.event()
        self.graph.event(self.case,raw,1,1);self.graph.event(self.case,raw,2,1)
        changed=self.event(timestamp=13)
        self.graph.event(self.case,changed,2,2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM event_sources").fetchone()[0],3)
        self.assertEqual(self.db.execute("SELECT conflict FROM events").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM usable_event_relations").fetchone()[0],0)

    def test_reference_labels_are_separate_and_unlisted_nodes_remain_null(self):
        self.graph.event(self.case,self.event(),1,1)
        subject=self.graph.node("host-a","s")
        self.graph.apply_metadata(subject,"RECORD_SUBJECT",{"type":"SUBJECT_PROCESS","startTimestampNanos":1},"native")
        self.db.execute("INSERT INTO published_nodes VALUES ('case-a','s','RECORD_SUBJECT','reference.csv',1)")
        self.graph.match_references()
        labels=dict(self.db.execute("SELECT node_id,published_reference_label FROM node_reference_labels"))
        self.assertEqual(labels[subject],1)
        self.assertIsNone(labels[self.graph.node("host-a","f")])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM node_reference_labels WHERE published_reference_label=0").fetchone()[0],0)

    def test_future_process_or_missing_parent_does_not_become_usable_context(self):
        self.graph.event(self.case,self.event(),1,1)
        subject=self.graph.node("host-a","s");target=self.graph.node("host-a","f")
        self.graph.apply_metadata(subject,"RECORD_SUBJECT",{"type":"SUBJECT_PROCESS","startTimestampNanos":15},"native")
        self.graph.apply_metadata(target,"RECORD_FILE_OBJECT",{"type":"FILE_OBJECT_FILE"},"native")
        self.graph.finish_context()
        self.assertEqual(self.db.execute("SELECT process_context_status FROM events").fetchone()[0],"future_start")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM usable_event_relations").fetchone()[0],0)
        self.db.execute("UPDATE nodes SET subtype='SUBJECT_THREAD',start_ns=1,parent_uuid='absent' WHERE id=?",(subject,))
        self.assertEqual(self.graph.context(subject)[0],"missing_parent")

    def test_future_destination_subject_is_not_usable_even_with_valid_actor(self):
        self.graph.event(self.case,self.event(),1,1)
        subject=self.graph.node('host-a','s');target=self.graph.node('host-a','f')
        self.graph.apply_metadata(subject,'RECORD_SUBJECT',{'type':'SUBJECT_PROCESS','startTimestampNanos':1},'native')
        self.graph.apply_metadata(target,'RECORD_SUBJECT',{'type':'SUBJECT_PROCESS','startTimestampNanos':18},'native')
        self.graph.finish_context()
        self.assertEqual(self.db.execute('SELECT process_context_status FROM events').fetchone()[0],'time_valid')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM usable_event_relations').fetchone()[0],0)

    def test_nanosecond_bounds_are_not_rounded_and_all_intersecting_files_selected(self):
        edge="2019-05-09T17:25:00.000000001Z"
        self.assertEqual(iso_nanos(edge)-iso_nanos("2019-05-09T17:25:00Z"),1)
        cases=[{"case_id":"a","file_prefix":"stream-","start_nanos":iso_nanos(edge),"end_nanos":iso_nanos("2019-05-09T17:26:00Z")}]
        files=[{"filename":"stream-later.gz","min_event_utc":"2019-05-08T00:00:00Z","max_event_utc":edge},
               {"filename":"stream-outside.gz","min_event_utc":"2019-05-10T00:00:00Z","max_event_utc":"2019-05-11T00:00:00Z"}]
        self.assertEqual(select_sources(files,cases),{"stream-later.gz":["a"]})

    def test_end_to_end_archive_build_keeps_sources_and_unknown_reference_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'raw';source.mkdir();ref=base/'reference';ref.mkdir()
            annotations=base/'csv';annotations.mkdir()
            host,subject,target,event=[f'{x:032x}' for x in range(1,5)]
            schema={'type':'record','name':'CDMTest','fields':[
                {'name':'hostId','type':'string'},{'name':'type','type':'string'},
                {'name':'datum','type':{'type':'record','name':'DatumTest','fields':[
                    {'name':'uuid','type':'string'},{'name':'type','type':'string'},
                    {'name':'timestampNanos','type':'long','default':0},
                    {'name':'startTimestampNanos','type':['null','long'],'default':None},
                    {'name':'subject','type':['null','string'],'default':None},
                    {'name':'predicateObject','type':['null','string'],'default':None}]}}]}
            process={'uuid':subject,'type':'SUBJECT_PROCESS','startTimestampNanos':1}
            records=[{'hostId':host,'type':'RECORD_SUBJECT','datum':process},
                     {'hostId':host,'type':'RECORD_FILE_OBJECT','datum':{'uuid':target,'type':'FILE_OBJECT_FILE'}},
                     {'hostId':host,'type':'RECORD_EVENT','datum':{'uuid':event,'type':'EVENT_OPEN',
                        'timestampNanos':12,'subject':subject,'predicateObject':target}}]
            path=source/'sample.gz'
            with gzip.open(path,'wb') as stream:
                writer(stream,schema,records)
            db=sqlite3.connect(ref/'references.sqlite')
            db.execute('CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)')
            db.execute('INSERT INTO entities VALUES (?,?,?,?,?,?)',(subject,'RECORD_SUBJECT',json.dumps(process),'sample.gz',1,host))
            db.commit();db.close()
            source_info={'filename':'sample.gz','records':3,'complete_scan':True,'compressed_bytes':path.stat().st_size,
                'modified_time_ns':path.stat().st_mtime_ns,'record_type_counts':{'RECORD_SUBJECT':1,'RECORD_FILE_OBJECT':1,'RECORD_EVENT':1},
                'min_event_utc':utc_nanos(12),'max_event_utc':utc_nanos(12)}
            ref_report=ref/'reference_report.json'
            ref_report.write_text(json.dumps({'all_files_fully_scanned':True,'files':[source_info]}),encoding='utf-8')
            listed=annotations/'nodes.csv'
            with listed.open('w',encoding='utf-8',newline='') as stream:
                csv.writer(stream).writerow([subject,"{'subject':'fixture'}",999])
            public=base/'public.json';public.write_text(json.dumps({'current_gate':{
                'reference_report_sha256_utf8_lf':hashlib.sha256(ref_report.read_text(encoding='utf-8').encode()).hexdigest()},
                'files':[{'name':'nodes.csv','sha256':hashlib.sha256(listed.read_bytes()).hexdigest()}]}),encoding='utf-8')
            config=base/'cases.json';config.write_text(json.dumps({'cases':[{'case_id':'a','host_uuid':host,
                'file_prefix':'sample','start_nanos':10,'end_nanos':20,'reference_file':'nodes.csv'}]}),encoding='utf-8')
            report=build(source,config,public,annotations,ref,base/'output',max_gib=0.02)
            self.assertEqual(report['raw_records_scanned'],3)
            self.assertEqual(report['unique_events'],1)
            self.assertEqual(report['native_event_relations'],1)
            self.assertEqual(report['usable_relation_count'],1)
            self.assertFalse(report['ready_for_training'])
            with closing(sqlite3.connect(base/'output/graph.sqlite')) as graph:
                self.assertEqual(graph.execute('SELECT COUNT(*) FROM event_sources').fetchone()[0],1)
                self.assertEqual(graph.execute('SELECT COUNT(*) FROM node_reference_labels WHERE published_reference_label IS NULL').fetchone()[0],1)


if __name__ == "__main__":
    unittest.main()
