"""Sequential full-source preparation, GCN, GraphSAGE, GAT and frozen comparison."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time
import traceback
from research.ml.gnn_full.prepare import extract,deduplicate,compile_graphs,save,disk_guard
from research.ml.node_benchmark.audit_protocol import text_hash,file_hash


def run(source,audit,work,plan_path):
    work=work.resolve();source=source.resolve()
    if work==source or source in work.parents or work in source.parents:raise ValueError('Derived work must be separate from raw files')
    work.mkdir(parents=True,exist_ok=True);disk_guard(work)
    config=json.loads(plan_path.read_text(encoding='utf-8'))
    if config.get('cpu_workers')!=4:raise ValueError('Use the RAM-bounded four-worker extraction setting')
    required=dict(task='self_supervised_masked_node_feature_reconstruction',models=['gcn','graphsage','gat'],
        window_nanos=300000000000,epochs=5,seed=42,batch_size=256,fanouts=[10,5],
        training_mask_probability=.2,hidden_dim=64,latent_dim=32,learning_rate=.001,weight_decay=.0001,
        selection='development_masked_mse_including_epoch_zero',security_labels_used=False,
        train_end_utc='2019-05-09T00:00:00Z',development_start_utc='2019-05-09T00:05:00Z',
        development_end_utc='2019-05-10T00:00:00Z',test_start_utc='2019-05-10T00:05:00Z')
    if any(config.get(key)!=value for key,value in required.items()):
        raise ValueError('Configuration differs from the frozen implemented full-source protocol')
    actions=config['action_vocabulary']
    code={p.name:text_hash(p) for p in Path(__file__).parent.glob('*.py')}
    contract=dict(config=config,config_sha256_utf8_lf=text_hash(plan_path),code_sha256_utf8_lf=code,
        audit_sha256_utf8_lf=text_hash(audit/'reference_report.json'),python=platform.python_version(),
        versions={p:version(p) for p in ('torch','torch-geometric','duckdb','pyarrow','numpy','fastavro')})
    contract_path=work/'contract.json'
    if contract_path.exists():
        if json.loads(contract_path.read_text(encoding='utf-8'))!=contract:raise ValueError('Frozen pipeline inputs/code/runtime changed; do not silently resume')
    else:save(contract_path,contract)
    if (work/'complete.json').exists():raise ValueError('This full experiment is already complete; use its saved result')
    started=time.perf_counter()
    try:
        if not (work/'deduplication.json').exists():
            extract(source,audit,work,actions,workers=config['cpu_workers'])
            extraction=json.loads((work/'extraction.json').read_text(encoding='utf-8'))
            size=sum(f['parquet_bytes'] for f in extraction['sources'])
            disk_guard(work,2*size+12*1024**3)
            deduplicate(work)
        metadata=compile_graphs(work,actions)
        extraction=json.loads((work/'extraction.json').read_text(encoding='utf-8'))
        dedup=json.loads((work/'deduplication.json').read_text(encoding='utf-8'))
        if sum(g['native_events'] for g in metadata['graphs'])+metadata['purge_gap_events']!=dedup['unique_usable_events']:
            raise ValueError('Not every usable native Event is represented or explicitly purged')
        summary={role:dict(graphs=sum(g['role']==role for g in metadata['graphs']),
            node_windows=sum(g['nodes'] for g in metadata['graphs'] if g['role']==role),
            native_events=sum(g['native_events'] for g in metadata['graphs'] if g['role']==role)) for role in ('train','development','test')}
        save(work/'preparation_summary.json',dict(status='full_preparation_complete',sources=len(extraction['sources']),
            raw_records=sum(s['records'] for s in extraction['sources']),deduplication=dedup,partitions=summary,
            all_graph_vectors_independently_checked=True,graph_manifest_sha256=file_hash(work/'graphs.json')))
        from research.ml.gnn_full.train import train_all
        results=train_all(work,config)
        result=dict(status='all_three_full_local_gnn_experiments_complete',models=results,
            partitions=summary,local_sources=len(extraction['sources']),elapsed_this_invocation_seconds=time.perf_counter()-started,
            temporal_native_entity_overlap=metadata['native_entity_overlap'],
            all_local_sources_included=True,whole_darpa_release_claimed=False,
            task='self_supervised_masked_node_feature_reconstruction',security_threshold=None,
            attack_detection_metrics_available=False)
        save(work/'complete.json',result);save(work/'progress.json',dict(phase='complete'))
        print(json.dumps(result),flush=True)
    except BaseException as error:
        save(work/'failure.json',dict(status='incomplete_failed',error=str(error),traceback=traceback.format_exc()))
        save(work/'progress.json',dict(phase='failed',error=str(error)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','audit','work','config'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.source,args.audit,args.work,args.config)
