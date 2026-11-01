"""Apply a separately fingerprinted execution adapter to the frozen GNN pipeline.

The original orchestration, contracts, settings and completed reports stay intact.
Only its epoch implementation is explicitly dispatched to the reviewed prefetch loop.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch
from research.ml.gnn_full import train as original_train
from research.ml.gnn_full import run as original_run
from research.ml.gnn_full.prepare import save
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash
from research.ml.gnn_accel.prefetch import epoch


def execution_code():
    return {p.name:text_hash(p) for p in Path(__file__).parent.glob('*.py')}


def validate_profile(work):
    path=work/'execution_profile_prefetch.json'
    profile=json.loads(path.read_text(encoding='utf-8'))
    if profile['status']!='reviewed_bounded_cpu_prefetch_revision':raise ValueError('Unreviewed execution profile')
    if profile['execution_code_sha256_utf8_lf']!=execution_code():raise ValueError('Execution adapter code changed')
    if profile['original_contract_sha256']!=file_hash(work/'contract.json'):raise ValueError('Original contract changed')
    for name,digest in profile['preserved_completed_reports'].items():
        if file_hash(work/'runs'/name/'run.json')!=digest:raise ValueError('Preserved completed report changed')
    for name,digest in profile.get('preserved_completed_checkpoints',{}).items():
        if file_hash(work/'runs'/name/'best.pt')!=digest:raise ValueError('Preserved completed checkpoint changed')
    for name,digest in profile.get('prepared_artifacts',{}).items():
        if file_hash(work/name)!=digest:raise ValueError('Prepared artifact changed')
    return profile,file_hash(path)


def run(source,audit,work,config):
    profile,profile_sha=validate_profile(work)
    if (work/'complete.json').exists():raise ValueError('Experiment is already complete')
    for family in ('gcn','graphsage','gat'):
        save(work/'runs'/family/'execution.json',dict(
            training_execution='original_serial_cuda' if family!='gat' else 'bounded_cpu_prefetch_cuda',
            final_test_execution='bounded_cpu_prefetch_cuda',execution_profile_sha256=profile_sha,
            model_protocol_unchanged=True))
    # Explicit process-local dispatch: the original trainer still validates its
    # original code receipts, then the supplementary profile binds this epoch.
    with patch.object(original_train,'epoch',epoch):
        original_run.run(source,audit,work,config)
    result=json.loads((work/'complete.json').read_text(encoding='utf-8'))
    result['execution_profile_sha256']=profile_sha
    result['execution_adapter']='bounded_cpu_prefetch_cuda'
    save(work/'complete.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','audit','work','config'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.source,args.audit,args.work,args.config)
