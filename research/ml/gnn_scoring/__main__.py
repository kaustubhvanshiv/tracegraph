"""Run with python -m research.ml.gnn_scoring; no training entry point."""
import argparse
import json
from pathlib import Path
from research.ml.gnn_scoring.artifacts import export_bundle
from research.ml.gnn_scoring.inputs import export_inputs
from research.ml.gnn_scoring.score import score


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    export=commands.add_parser('export',help='Export the verified frozen checkpoint, scaler and receipts')
    export.add_argument('--work',type=Path,required=True);export.add_argument('--verification',type=Path,required=True)
    export.add_argument('--output',type=Path,required=True)
    inputs=commands.add_parser('inputs',help='Copy complete recorded graphs into a portable input package')
    inputs.add_argument('--work',type=Path,required=True)
    inputs.add_argument('--partition',choices=['train','development','test'],required=True)
    inputs.add_argument('--graph-key',action='append',help='Explicit canonical key; omit to include every graph in the partition')
    scorer=commands.add_parser('score',help='Produce per-node errors and aggregate metrics without training')
    scorer.add_argument('--input',type=Path,required=True);scorer.add_argument('--device',choices=['cpu','cuda'],required=True)
    for command in (inputs,scorer):
        command.add_argument('--bundle',type=Path,required=True)
        command.add_argument('--bundle-sha256',required=True,help='Trusted digest from the exporter or verified published receipt')
        command.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='export':result=export_bundle(args.work,args.verification,args.output)
    elif args.command=='inputs':result=export_inputs(args.work,args.bundle,args.bundle_sha256,args.partition,args.output,args.graph_key)
    else:result=score(args.bundle,args.input,args.output,args.device,args.bundle_sha256)
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
