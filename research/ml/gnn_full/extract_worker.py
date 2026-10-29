"""One CPU-only archive reader; avoids loading GPU libraries in reader processes."""
import argparse
import json
from pathlib import Path
import pyarrow as pa
from research.ml.gnn_full.prepare import extract_serial

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','audit','work'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--index',type=int,required=True)
    args=parser.parse_args();pa.set_cpu_count(2)
    actions=json.loads((args.work/'actions.json').read_text(encoding='utf-8'))
    extract_serial(args.source,args.audit,args.work,actions,only_index=args.index)
