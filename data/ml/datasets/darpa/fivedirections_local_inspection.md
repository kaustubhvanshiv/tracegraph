# FiveDirections — local Windows inspection

Inspection date: 2026-10-11. This supplements the historical `analysis.md`;
its Linux paths and older download inventory do not describe this download.

## Source and method

```text
D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections
```

Six gzip files contain Avro object containers (`Obj\x01`) with an embedded
`com.bbn.tc.schema.avro.cdm20.TCCDMDatum` writer schema. Their internal Avro
codec is `null`; the external compression is gzip. Direct streaming works;
an external schema is not required to decode these containers.

The inspection reads the first **20,000 records per file** in natural segment
order. This is a bounded diagnostic, not a representative statistical sample.
The tool reads one extra record to distinguish a complete file from a prefix,
but does not count it. It does not export raw telemetry. Prefix scans do not
validate the remainder of a file or its final gzip checksum.

Machine-readable results: [fivedirections_profile.json](fivedirections_profile.json).
The report includes schema field descriptions, schema hashes, source paths,
compressed sizes, counts, missing-field indicators, and timestamp ranges.

## Observations

Total compressed size: **1,891,510,041 bytes** (~1.89 GB / 1.76 GiB).
Decoded records: **120,000**; events: **112,498**; file decode failures: **0**.
The six schema hashes match. All six scans are partial.

| Segment | Events in 20,000 records | Earliest sampled event (UTC) | Latest sampled event (UTC) | Timestamp regressions |
|---|---:|---|---|---:|
| 15 | 19,894 | 2019-05-08 22:59:58.045 | 2019-05-08 23:09:38.909 | 258 |
| 17 | 19,973 | 2019-05-09 10:02:34.773 | 2019-05-09 10:02:37.585 | 121 |
| 20 | 17,824 | 2019-05-09 16:32:30.535 | 2019-05-09 16:35:57.880 | 420 |
| 23 | 19,591 | 2019-05-09 21:10:02.221 | 2019-05-09 21:11:41.105 | 418 |
| 27 | 19,090 | 2019-05-10 06:17:29.869 | 2019-05-10 06:18:39.879 | 231 |
| 121 | 16,126 | 2019-05-17 19:54:35.342 | 2019-05-17 19:54:49.483 | 182 |

These ranges cover only prefixes. They do not establish full segment coverage,
attack coverage, or gaps between entire segments.

| Record type | Sample count |
|---|---:|
| Event | 112,498 |
| MemoryObject | 5,620 |
| Subject | 1,774 |
| IpcObject | 53 |
| NetFlowObject | 48 |
| TimeMarker | 4 |
| RegistryKeyObject | 3 |

No Host, Principal, or FileObject definitions occur in these prefixes. That
does not prove their absence from the complete files. Resolving UUID references
requires broader scanning and potentially additional segments.

The nonzero host UUID observed is `2ab88dcdcbe641dfac699f6d6058e398`.
The all-zero host UUID also occurs; treat it as unspecified, not a second host.

There are **27 event types** in the sample. Examples include 23,105 reads,
3,161 writes, 11,371 opens, 38 connects, 13 executes, and 3 logins.
`EVENT_OTHER` is not automatically meaningless: the additional `names` field
includes `EVENT_FREE_OBJECT` and `EVENT_PRINCIPAL_PRIVILEGE_ASSIGNMENT`.
Keep both the primary type and names during preparation.

Observed properties include process IDs, image names, command lines, usernames,
SIDs, file names, IP addresses, and ports. These fields are event-dependent;
presence of a key somewhere does not imply it is populated on all events.

## Label and preparation status

No candidate attack-label keys were found by the inspector's limited key-name
check. This is not proof of their absence across every field or unsampled
record. The source folder has no other files, and the user confirmed they did
not download ground truth. Current labels are **unknown**; class balance cannot
be measured.

Before creating training data:

1. Obtain the [download checklist](../../download_checklist.md) files.
2. Match documented incidents to this stream's hosts, timestamps, and UUIDs.
3. Audit reference resolution across the available segments; quantify missing
   parents, users, objects, and hosts instead of inventing those attributes.
4. Normalize only actions whose semantics are supported. Do not map arbitrary
   memory/registry access to a file relationship.
5. Deduplicate and sort using event timestamps, then group incidents and apply
   the split policy in [ground_truth.md](../../ground_truth.md).

## Reproduce

Run these PowerShell commands from the repository root:

```powershell
python -m venv research/ml/.venv
& .\research\ml\.venv\Scripts\python.exe -m pip install -r research/ml/requirements.txt
& .\research\ml\.venv\Scripts\python.exe -m research.ml.data_prep.inspect_fivedirections --source 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049' --output data/ml/datasets/darpa/fivedirections_profile.json --records-per-file 20000
& .\research\ml\.venv\Scripts\python.exe -m unittest discover -s research/ml/tests -v
```

Use `--records-per-file 0` for a full streaming scan when complete counts and
whole-file integrity checking are needed. Model training has not begun.
