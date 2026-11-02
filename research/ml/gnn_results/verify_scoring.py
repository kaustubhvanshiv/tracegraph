"""Verify real offline replay coverage and CPU parity; publish aggregate evidence."""
import argparse
import csv
from pathlib import Path
import numpy as np
from research.ml.gnn_scoring.artifacts import load_bundle,read,write,require,fresh_output
from research.ml.gnn_scoring.inputs import input_manifest,load_graph
from research.ml.node_benchmark.audit_protocol import file_hash


RTOL=1e-5
ATOL=1e-7
METRICS=('mse','mae','mean_reference_mse')
ROW_METRICS=('reconstruction_mse','reconstruction_mae','training_mean_reference_mse')


def checked_summary(directory,input_path,bundle,bundle_sha,device):
    summary=read(directory/'summary.json')
    require(not (directory/'failure.json').exists() and not list(directory.glob('*.partial')),'Scoring failure or partial output remains')
    require(summary['status']=='standalone_graphsage_reconstruction_complete' and summary['device']==device and
            summary['bundle_sha256']==bundle_sha and summary['input_manifest_sha256']==file_hash(input_path),
            'Scoring receipt binding differs')
    for key,name in [('checkpoint_sha256','best.pt'),('scaler_sha256','scaler.json'),('feature_schema_sha256','feature_schema.json')]:
        require(summary[key]==bundle['files_sha256'][name],'Scoring artifact binding differs')
    require(summary['checkpoint_state_sha256']==bundle['checkpoint_state_sha256'] and
            summary['scoring_code_sha256_utf8_lf']==bundle['scoring_code_sha256_utf8_lf'],'Scored model/code state differs')
    require(summary['weights_updated'] is False and summary['scaler_refit'] is False and summary['security_labels_used'] is False and
            summary['security_threshold'] is None and summary['attack_detection_metrics_available'] is False and
            summary['backend_integration'] is False,'Unsupported inference/security claim')
    for name in ('scores.csv','graphs.csv'):
        require(file_hash(directory/name)==summary['files_sha256'][name],'Scoring CSV fingerprint differs')
    return summary


def row_values(row):
    require(set(row)=={'graph_id','node_index','node_uuid',*ROW_METRICS,'security_label','security_threshold'} and
            row['security_label']==row['security_threshold']=='','Invalid row score/security fields')
    values=np.array([float(row[k]) for k in ROW_METRICS])
    require(np.isfinite(values).all() and (values>=0).all(),'Invalid row reconstruction values')
    return values


def verify(work,bundle_path,bundle_sha,full_input,full_score,cpu_input,cpu_score,output):
    output=fresh_output(output,work,bundle_path,full_input.parent,full_score,cpu_input.parent,cpu_score)
    bundle,_,schema,_=load_bundle(bundle_path,'cpu',bundle_sha)
    original=read(work/'graphs.json');test=read(work/'runs/graphsage/test.json')
    require(file_hash(work/'graphs.json')==schema['source_graph_manifest_sha256'] and
            file_hash(work/'runs/graphsage/best.pt')==bundle['files_sha256']['best.pt'] and
            file_hash(work/'runs/graphsage/test.json')==bundle['files_sha256']['source_test.json'] and
            file_hash(work/'scaler.json')==bundle['files_sha256']['scaler.json'],'Original frozen artifacts changed')
    full=input_manifest(full_input,bundle['files_sha256']['feature_schema.json'])
    cpu=input_manifest(cpu_input,bundle['files_sha256']['feature_schema.json'])
    recorded=[g for g in original['graphs'] if g['role']=='test']
    expected=[dict(file=g['file'],graph_id=f"{g['host']}_{g['window_start_nanos']}",sampling_key=g['file'],host_uuid=g['host'],
        window_start_nanos=g['window_start_nanos'],nodes=g['nodes'],adjacency_edges=g['adjacency_edges'],
        native_events=g['native_events'],role='test',sha256=g['sha256']) for g in recorded]
    require(full['graphs']==expected and full['selection']['all_partition_graphs_included'] is True,
            'Replay is not the complete recorded test partition in its original order')
    full_map={g['graph_id']:g for g in full['graphs']}
    require(all(g==full_map.get(g['graph_id']) for g in cpu['graphs']),'CPU parity input differs from full replay input')
    cuda_summary=checked_summary(full_score,full_input,bundle,bundle_sha,'cuda')
    cpu_summary=checked_summary(cpu_score,cpu_input,bundle,bundle_sha,'cpu')
    parity={};cpu_count=0
    with (cpu_score/'scores.csv').open(newline='',encoding='utf-8') as stream:
        rows=csv.DictReader(stream)
        for entry in cpu['graphs']:
            nodes,*_=load_graph(cpu_input.parent/entry['file'],entry)
            for i,uid in enumerate(nodes):
                row=next(rows);require((row['graph_id'],int(row['node_index']),row['node_uuid'])==
                    (entry['graph_id'],i,bytes(uid).hex()),'CPU node coverage differs')
                parity[(entry['graph_id'],i)]=row_values(row);cpu_count+=1
        require(next(rows,None) is None,'Extra CPU rows')
    require(cpu_count==cpu_summary['metrics']['target_node_count']==cpu_summary['metrics']['seed_nodes_visited'] and
            cpu_summary['graph_count']==len(cpu['graphs']),'CPU aggregate coverage differs')
    require(cpu_count>256 and any(g['nodes']>256 for g in cpu['graphs']),'CPU parity must exercise multiple batches')
    with (full_score/'graphs.csv').open(newline='',encoding='utf-8') as stream:graph_rows=list(csv.DictReader(stream))
    require(len(graph_rows)==len(recorded),'Graph CSV coverage differs')
    sums=np.zeros(3);parity_sums=np.zeros(3);max_abs=np.zeros(3);visited=0;parity_count=0
    with (full_score/'scores.csv').open(newline='',encoding='utf-8') as stream:
        rows=csv.DictReader(stream)
        for entry,graph_row in zip(full['graphs'],graph_rows):
            nodes,*_=load_graph(full_input.parent/entry['file'],entry);values=np.empty((len(nodes),3))
            require(graph_row['graph_id']==entry['graph_id'] and graph_row['host_uuid']==entry['host_uuid'] and
                    int(graph_row['window_start_nanos'])==entry['window_start_nanos'] and graph_row['role']=='test' and
                    int(graph_row['node_windows'])==entry['nodes'] and int(graph_row['native_events'])==entry['native_events'] and
                    int(graph_row['adjacency_edges'])==entry['adjacency_edges'],'Graph CSV metadata differs')
            for i,uid in enumerate(nodes):
                row=next(rows);require((row['graph_id'],int(row['node_index']),row['node_uuid'])==
                    (entry['graph_id'],i,bytes(uid).hex()),'CUDA row identity/coverage differs')
                values[i]=row_values(row);key=(entry['graph_id'],i)
                if key in parity:
                    reference=parity.pop(key);difference=np.abs(values[i]-reference);max_abs=np.maximum(max_abs,difference)
                    require(np.allclose(values[i],reference,rtol=RTOL,atol=ATOL),'CPU/CUDA row parity failed')
                    parity_sums+=reference;parity_count+=1
            require(np.allclose(values.mean(0),[float(graph_row[k]) for k in METRICS],rtol=RTOL,atol=ATOL),
                    'Per-graph metrics do not reconcile with rows')
            sums+=values.sum(0);visited+=len(nodes)
        require(next(rows,None) is None,'Extra CUDA score rows')
    require(not parity and parity_count==cpu_count,'Incomplete CPU/CUDA comparison')
    require(visited==cuda_summary['metrics']['seed_nodes_visited']==cuda_summary['metrics']['target_node_count']==
            test['metrics']['target_node_count'] and cuda_summary['graph_count']==len(recorded),'Full replay coverage differs')
    require(np.allclose(parity_sums/cpu_count,[cpu_summary['metrics'][k] for k in METRICS],rtol=RTOL,atol=ATOL),
            'CPU metrics do not reconcile with rows')
    measured={k:cuda_summary['metrics'][k] for k in METRICS};saved={k:test['metrics'][k] for k in METRICS}
    require(np.allclose(list(measured.values()),list(saved.values()),rtol=RTOL,atol=ATOL),'Frozen test replay differs')
    require(np.allclose(sums/visited,list(measured.values()),rtol=RTOL,atol=ATOL),'Full row scores do not reconcile with aggregate metrics')
    receipt=dict(status='standalone_graphsage_scoring_verified',date='2026-11-02',model='graphsage',selected_epoch=bundle['selected_epoch'],
        parameter_count=bundle['parameter_count'],bundle_sha256=bundle_sha,bundle_bytes=sum(p.stat().st_size for p in bundle_path.iterdir()),
        checkpoint_sha256=bundle['files_sha256']['best.pt'],checkpoint_state_sha256=bundle['checkpoint_state_sha256'],
        scaler_sha256=bundle['files_sha256']['scaler.json'],source_graph_manifest_sha256=file_hash(work/'graphs.json'),
        full_replay=dict(graphs=len(recorded),node_windows=visited,native_events=sum(g['native_events'] for g in recorded),
            measured_metrics=measured,frozen_metrics=saved,absolute_metric_differences={k:abs(measured[k]-saved[k]) for k in METRICS},
            seconds=cuda_summary['seconds'],device=cuda_summary['device'],gpu=cuda_summary['gpu'],
            input_manifest_sha256=file_hash(full_input),summary_sha256=file_hash(full_score/'summary.json'),
            row_csv_sha256=cuda_summary['files_sha256']['scores.csv'],graph_csv_sha256=cuda_summary['files_sha256']['graphs.csv'],
            all_recorded_test_graphs_included=True,all_native_row_ids_checked=True,all_row_metrics_finite=True,
            rows_reconcile_with_graph_and_global_metrics=True),
        cpu_cuda_parity=dict(graphs=len(cpu['graphs']),node_windows=cpu_count,all_selected_rows_compared=True,
            maximum_absolute_row_differences=dict(zip(ROW_METRICS,map(float,max_abs))),
            cpu_metrics={k:cpu_summary['metrics'][k] for k in METRICS},cpu_seconds=cpu_summary['seconds'],
            input_manifest_sha256=file_hash(cpu_input),cpu_summary_sha256=file_hash(cpu_score/'summary.json'),
            independent_cpu_only_wheel_installation_tested=False),
        tolerance=dict(rtol=RTOL,atol=ATOL),runtime=cuda_summary['runtime'],scoring_code_sha256_utf8_lf=bundle['scoring_code_sha256_utf8_lf'],
        verification_code_sha256=file_hash(Path(__file__)),weights_updated=False,scaler_refit=False,security_labels_used=False,
        security_threshold=None,attack_detection_metrics_available=False,backend_integration=False,
        fresh_security_evaluation=False,raw_avro_required_for_scoring=False,external_event_semantics_independently_verified=False,
        independent_clean_machine_reproduction=False)
    output.parent.mkdir(parents=True,exist_ok=True);write(output,receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','bundle','full-input','full-score','cpu-input','cpu-score','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--bundle-sha256',required=True)
    a=parser.parse_args()
    result=verify(a.work,a.bundle,a.bundle_sha256,a.full_input,a.full_score,a.cpu_input,a.cpu_score,a.output)
    print(result['status'],result['full_replay']['node_windows'],'rows checked')


if __name__=='__main__':main()
