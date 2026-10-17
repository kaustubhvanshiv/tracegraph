# DARPA download refresh — 2026-10-17

This continues the user's requested DARPA preparation work with new local
downloads. It does not select an architecture, change labels automatically,
reactivate the deferred GNN track, or run a training experiment.

## Download integrity and scope

Raw source (read only):

```text
D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections
```

All **28** gzip archives match the downloaded `bins.md5sum`, totaling
**8,849,857,844 compressed bytes**. There are 22 more archives than in the
original six-file inspection. The manifest contains 337 unique filenames;
309 are absent locally. These are inventory counts, not a requirement to
download the remaining release. MD5 comparison checks consistency with this
downloaded manifest; it is not a digital signature or independent proof of
origin.

| Stream | Local archives | Manifest archives | Missing |
|---|---|---:|---:|
| FiveDirections-1 | Base file; segments 1, 2, 3, 15, 17, 20, 23, 27, 121 | 123 | 113 |
| FiveDirections-2 | Base file; segments 1–7 | 102 | 94 |
| FiveDirections-3 | Base file; segments 1–9 | 112 | 102 |

"Base file" means `ta1-fivedirections-N-e5-official-1.bin.gz`, without a
number between `.bin` and `.gz`. Checksums, file sizes, source modification
times and all missing filenames are in
[the inventory](download_inventory_20261017.json).

No telemetry was extracted into the repository: the reader streams gzip/Avro
directly. Support ZIPs remain usable by the existing support reader. The user
reports that the shared `starc` folder opens empty. No STARC annotation file
was downloaded or inspected; its availability elsewhere is not established.

## Prefix coverage across all three streams

The existing inspector decoded **100,000 records per archive**: 2,800,000
records and 2,640,206 Events, with zero decoding errors. All 28 inspections
are bounded prefixes; none is represented as a full-file scan. See
[the aggregate prefix profile](download_prefix_summary_20261017.json).

The three base-file prefixes each contain one Host definition and respectively
three, two and one Principal records. Other inspected prefixes contain neither
type. These are observed prefix counts, not whole-release totals. The original
host UUID `2ab88dcdcbe641dfac699f6d6058e398` is directly associated with
hostname `ta1-fivedirections-1` in its Host definition. Its base file also
contains Principal UUID `042ef90b178e43d490106b36c128af1b`, referenced by the
reviewed Firefox process. Full command lines and principal usernames remain
in local indexes/prepared events, not in these aggregate reports.

Hosts 2 and 3 have different publishing UUIDs. Their events and identities
are not assigned the host-1 attack labels. Prefix samples do not establish
complete incident coverage or absence of an entity later in an archive.

## Reproduce the preparation workflow

Follow [the ML README](../../../../research/ml/README.md) to create the Python
environment with `fastavro`, `pydantic` and the support-reader dependencies.
Run from the repository root, using fresh output directories:

```powershell
$MlPython = '.\research\ml\.venv\Scripts\python.exe'
$DataSource = 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections'

& $MlPython -m research.ml.data_prep.inspect_fivedirections `
  --source $DataSource `
  --output .cache/ml-runs/my-download-prefixes.json `
  --records-per-file 100000

& $MlPython -m research.ml.data_prep.resolve_references `
  --source $DataSource `
  --annotations data/ml/datasets/darpa/review_annotations.json `
  --file-pattern 'ta1-fivedirections-1-*.gz' `
  --output .cache/ml-runs/my-host1-reference-audit `
  --records-per-file 0

& $MlPython -m research.ml.data_prep.prepare_dataset `
  --source $DataSource `
  --annotations data/ml/datasets/darpa/review_annotations.json `
  --reference-audit .cache/ml-runs/my-host1-reference-audit `
  --output .cache/ml-runs/my-host1-preparation `
  --records-per-file 2000000
```

If an earlier **completed** local full audit and its `references.sqlite`
already exist, append `--reuse-audit <that-local-directory>` to the reference
command. Reuse requires matching source file sizes/modification times and
matching per-file definition counts. Interrupted or prefix-only audits are
not reusable. A fresh clone must build its own index; the committed JSON is
an aggregate report, not an entity database.

Preparation uses reference metadata from audited files, then reads only the
annotation-listed event-source files. It preserves unknown labels, rejects
conflicting identities, scopes joins to a publishing host, and requires every
visited subject to have started by the event time. This offline identity join
does not establish online availability of every definition or construct model
features. Exit code **2** means the preparation completed with training gates
blocked; inspect `manifest.json`. Do not change unknown labels to zero.

To recheck downloaded checksums:

```powershell
$Expected = @{}
Get-Content -LiteralPath (Join-Path $DataSource 'bins.md5sum') | ForEach-Object {
  if ($_ -match '^([0-9a-fA-F]{32})\s+\*?(\S+)$') {
    $Expected[$Matches[2]] = $Matches[1]
  } else { throw 'Invalid checksum-manifest entry' }
}
Get-ChildItem -LiteralPath $DataSource -File -Filter '*.gz' | ForEach-Object {
  $Actual = (Get-FileHash -LiteralPath $_.FullName -Algorithm MD5).Hash
  [pscustomobject]@{ File = $_.Name; Matches = ($Actual -eq $Expected[$_.Name]) }
}
```

All rows must show `Matches = True` before processing. Keep the raw archives,
local SQLite indexes and prepared JSONL outside Git. Commit only code,
instructions and bounded aggregate reports.

## Validation

The research suite passes **38 tests**. New coverage exercises incremental
versus fresh audit equivalence, source-change rejection, cache inconsistency,
stream selection, host/type scoping and real preparation with external
metadata. Integration fixtures verify that future-starting processes and
other-host definitions cannot populate actor/user fields, and metadata alone
cannot supply labels or produce supervised splits. Fixtures are synthetic
software tests, not DARPA training examples.

## Completed host-1 reference audit

The completed audit covers **all 10 locally downloaded host-1 files**:
100,000,000 records, including **96,402,473 Events**, 449,557 Subject records,
six Principal records and one Host record. These are record counts, not unique
entities or labeled samples. The four new files contributed 40,000,000 decoded
records; 60,000,000 records were reused from the validated six-file cache.
The other 18 files remain prefix-inspected only. Do not describe this as a
complete scan of all 28 archives or of the whole DARPA release.

See [the completed reference report](expanded_reference_report_20261017.json).
All three review events now resolve their Host definition directly. The
Firefox process's Principal also resolves. The parent process
`1fca97f4e4134d05869b31eb09df8770` is still absent from these 10 complete
host-1 files, so the two affected candidates retain an incomplete actor chain.
The new host-1 files' event ranges are confined to May 7; they do not supply
the documented May 16 benign driver-setup interval.

This reference audit assigns **zero new labels**. Its `label: null` fields
mean it performs identity auditing, not that it withdraws the existing
report-reviewed positive in `review_annotations.json`.

## Completed preparation rerun and remaining gate

Preparation imported 449,564 Host/Principal/Subject definition records from
the completed host-1 audit, then streamed the same 2,000,000-record prefix of
segment 121 (1,901,311 Events) used in the earlier semantic run. All three
annotation-listed events are present without conflicting event payloads.
See [the new preparation manifest](preparation_refresh_manifest_20261017.json).

| Field in the three selected normalized events | Before | After |
|---|---:|---:|
| File path | 3 | 3 |
| Time-valid process image | 1 | 1 |
| Hostname | 0 | 3 |
| Linked Principal username | 0 | 1 |

These rates describe three indicator-selected events, not all DARPA events.
The annotation file and its SHA-256 digest are unchanged. The rerun retains
**one report-reviewed positive, two unknowns, zero verified negatives and one
related campaign**. No train/validation/test splits or trained model were
created. The preparation status is `blocked_for_training`, as required by
the existing class/group checks.

This closes the missing Host/Principal issue for the relevant resolved actor,
but not the missing parent chain for the other two events. ML-02.4 remains
incomplete. The next evidence work is independently reviewed benign examples
and additional independent attack/benign groups, with matching telemetry and
complete required actor context. More raw files alone are not labels. No
architecture, new dataset or labeling-policy change is selected here.
