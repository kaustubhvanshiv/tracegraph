"""Count local CDM flow addresses; remote IP matches cannot prove local identity."""
import argparse
from collections import Counter
import gzip
import itertools
import json
from pathlib import Path

from fastavro import reader
from research.ml.data_prep.inspect_fivedirections import uuid_text


def summarize(records, expected_address):
    counts, references, count = Counter(), [], 0
    for count, raw in enumerate(records, 1):
        if raw.get("type") != "RECORD_NET_FLOW_OBJECT":
            continue
        datum = raw.get("datum") or {}
        host, address = uuid_text(raw.get("hostId")), datum.get("localAddress")
        counts[(host, address)] += 1
        if address == expected_address and len(references) < 5:
            references.append({"host_uuid": host, "netflow_uuid": uuid_text(datum.get("uuid")),
                "local_address": address, "record_index_1based": count})
    return {"records_inspected": count,
        "local_address_counts": [{"host_uuid": h, "local_address": a, "count": c} for (h, a), c in counts.items()],
        "matching_local_address_references": references, "labels_assigned": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--expected-address", default="128.55.12.55")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--records", type=int, default=2_000_000)
    args = parser.parse_args()
    if args.records <= 0:
        raise ValueError("Provide a positive prefix limit")
    source, output = args.source_file.resolve(), args.output.resolve()
    if output == source or source.parent == output.parent or source.parent in output.parents:
        raise ValueError("Output must be outside raw source folder")
    if output.exists():
        raise ValueError("Output already exists")
    with gzip.open(source, "rb") as stream:
        report = summarize(itertools.islice(reader(stream), args.records), args.expected_address)
    report.update(source_file=source.name, complete_scan=False, expected_local_address=args.expected_address)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
