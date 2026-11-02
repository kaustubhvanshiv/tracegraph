"""Evidence gates must stay separate from unknown data and completed reconstruction."""
import copy
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
import zipfile
from research.ml.data_prep.readiness_audit import assess_samples,support_inventory


class ReadinessTests(unittest.TestCase):
    def row(self,uid,label,group,seconds,eligible=True):
        nanos=seconds*1_000_000_000
        annotation=dict(event_uuid=uid,host_uuid='host',subject_uuid='subject',timestamp_nanos=nanos,
            cdm_event_type='EVENT_OPEN',source_file='source.gz',record_index_1based=1,label=label,
            review_status='candidate' if label is None else 'verified',group_id=group,evidence={'source':'software fixture only'})
        if label==1:annotation['incident_id']='incident-'+group
        if not eligible:annotation.update(split_eligible=False,split_exclusion_reason='Uncalibrated clock')
        raw=dict(hostId='host',datum=dict(uuid=uid,subject='subject',timestampNanos=nanos,type='EVENT_OPEN'))
        sample=copy.deepcopy(annotation)
        sample['security_event']=dict(event_id=uid,source_type='darpa_cdm',event_type='file',action='access',
            timestamp=datetime.fromtimestamp(seconds,tz=timezone.utc).isoformat(),raw_data={'cdm':raw})
        return annotation,sample

    def test_excluded_benign_and_unknown_rows_do_not_unlock_supervised_gate(self):
        rows=[self.row('p1',1,'a',100),self.row('p2',1,'b',200),self.row('p3',1,'b',201),
              self.row('u1',None,'c',300),self.row('u2',None,'c',301),self.row('b0',0,'d',400,False)]
        result=assess_samples([a for a,_ in rows],[r for _,r in rows])
        self.assertEqual(result['reviewed_label_counts'],{'0':1,'1':3,'None':2})
        self.assertEqual(result['eligible_label_counts'],{'0':0,'1':3})
        self.assertEqual(result['named_attack_group_count'],2)
        self.assertFalse(result['supervised_gate_passes'])

    def test_annotation_and_cached_native_event_disagreement_is_rejected(self):
        annotation,row=self.row('u',None,'g',100)
        changed=copy.deepcopy(row);changed['security_event']['raw_data']['cdm']['datum']['type']='EVENT_WRITE'
        with self.assertRaisesRegex(ValueError,'identity/time/action mismatch'):assess_samples([annotation],[changed])
        changed=copy.deepcopy(row);changed['label']=0
        with self.assertRaisesRegex(ValueError,'disagrees'):assess_samples([annotation],[changed])

    def test_duplicate_missing_or_changed_canonical_time_is_rejected(self):
        annotation,row=self.row('u',None,'g',100)
        with self.assertRaisesRegex(ValueError,'Duplicate prepared'):assess_samples([annotation],[row,row])
        with self.assertRaisesRegex(ValueError,'exactly cover'):assess_samples([annotation],[])
        changed=copy.deepcopy(row);changed['security_event']['timestamp']='1970-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'timestamp differs'):assess_samples([annotation],[changed])

    def test_group_isolation_and_both_classes_remain_required(self):
        rows=[self.row(f'{g}-{label}',label,str(g),g*100+label) for g in range(3) for label in (0,1)]
        result=assess_samples([a for a,_ in rows],[r for _,r in rows])
        self.assertTrue(result['supervised_gate_passes'])
        # Passing structural fixtures does not claim real-world independence.
        self.assertFalse(result['independent_group_validation_claimed'])
        for a,r in rows:
            if a['label']==1:a['incident_id']=r['incident_id']='same-incident'
        result=assess_samples([a for a,_ in rows],[r for _,r in rows])
        self.assertFalse(result['supervised_gate_passes'])

    def test_support_inventory_lists_candidates_without_accepting_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);support=root/'support';support.mkdir();cache=root/'cache';cache.mkdir()
            (cache/'report.pdf').write_bytes(b'fixture report')
            with zipfile.ZipFile(support/'support.zip','w') as archive:
                archive.writestr('report.pdf',b'fixture report');archive.writestr('labels.csv','event,label\n')
            (support/'incoming.jsonl').write_text('{}')
            result=support_inventory(support,cache)
            self.assertTrue(result['archives'][0]['members'][0]['matches_cached_copy'])
            self.assertEqual(result['archived_annotation_candidates'],['support.zip::labels.csv'])
            self.assertEqual(result['standalone_annotation_candidates'],['incoming.jsonl'])
            self.assertNotIn('accepted_labels',result)


if __name__=='__main__':unittest.main()
