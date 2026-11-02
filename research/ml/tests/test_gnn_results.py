"""Reject inconsistent completion evidence and unsupported reconstruction reports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from research.ml.gnn_results.verify import metrics_valid,history_valid,test_valid
from research.ml.gnn_results.analyze import distribution
from research.ml.gnn_results.report import build,digest


class ResultTests(unittest.TestCase):
    def metric(self,value=.2,rows=10):
        return dict(mse=value,mae=.1,mean_reference_mse=.5,seed_nodes_visited=rows,target_node_count=rows,seconds=1.)

    def test_metrics_reject_nan_and_incomplete_test_coverage(self):
        metrics_valid(self.metric(),10)
        for modified in (dict(self.metric(),mse=float('nan')),dict(self.metric(),target_node_count=9)):
            with self.assertRaises(ValueError):metrics_valid(modified,10)

    def test_checkpoint_selection_requires_full_history_and_development_minimum(self):
        history=[dict(epoch=i,training=None if i==0 else self.metric(rows=20),development=self.metric(.5-i*.05)) for i in range(6)]
        report=dict(best_epoch=5,development=history[-1]['development'])
        history_valid(history,report,20,10)
        with self.assertRaisesRegex(ValueError,'Incomplete epoch'):history_valid(history[:-1],report,20,10)
        with self.assertRaisesRegex(ValueError,'selected by development'):history_valid(history,dict(report,best_epoch=4),20,10)

    def test_final_test_must_match_frozen_checkpoint_and_aggregate(self):
        report=dict(checkpoint_sha256='abc');metrics=self.metric()
        test=dict(status='frozen_gnn_feature_reconstruction_test_complete',checkpoint_sha256='abc',metrics=metrics,
            security_threshold=None,attack_detection_metrics_available=False)
        aggregate=dict(report,final_reconstruction_test=metrics)
        test_valid(test,report,aggregate,10)
        with self.assertRaisesRegex(ValueError,'checkpoint mismatch'):test_valid(dict(test,checkpoint_sha256='different'),report,aggregate,10)
        with self.assertRaisesRegex(ValueError,'Aggregate test mismatch'):test_valid(test,report,dict(aggregate,final_reconstruction_test=self.metric(.4)),10)

    def test_security_claims_are_rejected(self):
        report=dict(checkpoint_sha256='abc');metrics=self.metric()
        test=dict(status='frozen_gnn_feature_reconstruction_test_complete',checkpoint_sha256='abc',metrics=metrics,
            security_threshold=.3,attack_detection_metrics_available=True)
        with self.assertRaisesRegex(ValueError,'security claim'):test_valid(test,report,dict(report,final_reconstruction_test=metrics),10)

    def test_residual_distribution_retains_outlier_concentration_and_zero_case(self):
        errors=np.array([0.]*99+[100.]);result=distribution(errors)
        self.assertEqual(result['median'],0);self.assertEqual(result['maximum'],100)
        self.assertEqual(result['top_1_percent_squared_error_share'],1.)
        self.assertEqual(distribution(np.zeros(20))['top_10_squared_error_share'],0.)
        with self.assertRaises(ValueError):distribution([0.,float('inf')])

    def test_report_reproduces_values_and_rejects_changed_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);work=root/'work';work.mkdir();output=root/'report'
            models={};verified_models={}
            for family in ('gcn','graphsage','gat'):
                directory=work/'runs'/family;directory.mkdir(parents=True)
                history=[dict(epoch=i,training=None,development=self.metric()) for i in range(6)]
                for name,value in [('history',history),('run',{}),('test',{})]:
                    (directory/(name+'.json')).write_text(json.dumps(value))
                verified_models[family]={name+'_sha256':digest(directory/(name+'.json')) for name in ('run','test','history')}
                models[family]=dict(development=self.metric(),final_reconstruction_test=self.metric(.25),
                    parameter_count=100,best_epoch=5,epochs_completed=5,elapsed_seconds=60,
                    checkpoint_sha256='abc',checkpoint_state_sha256='def',gpu='fixture',torch_version='fixture',pyg_version='fixture')
            complete=dict(models=models,partitions={},temporal_native_entity_overlap={},task='self_supervised_masked_node_feature_reconstruction')
            (work/'complete.json').write_text(json.dumps(complete))
            verification=root/'verification.json'
            verification.write_text(json.dumps(dict(status='completed_full_local_gnn_artifacts_verified',models=verified_models,
                complete_sha256=digest(work/'complete.json'),graph_manifest_sha256='g',scaler_sha256='s',execution_profile_sha256='p')))
            analysis=root/'analysis.json'
            analysis.write_text(json.dumps(dict(status='frozen_full_test_error_analysis_complete',complete_sha256=digest(work/'complete.json'),
                verification_sha256=digest(verification),models={f:dict(row_errors=distribution(np.arange(10.))) for f in models})))
            summary=build(work,verification,analysis,output)
            self.assertEqual(summary['models']['gcn']['test_mse_reduction_percent'],50.)
            self.assertFalse(summary['attack_detection_metrics_available'])
            self.assertIn('| 0.500000000 | 0.500000000 | Unrecorded |', (output/'RESULTS_20261102.md').read_text())
            (work/'runs/gcn/test.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'Frozen evidence changed'):build(work,verification,analysis,output)


if __name__=='__main__':unittest.main()
