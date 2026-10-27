# DARPA E5 Drive downloads — 2026-10-18

**Later update, 2026-10-27:** parts 15 and 17 are now received and fully audited.
See the [current ML-02.4 review](ml02_label_review_20261027.md) and
[next queue](host2_download_queue_20261027.json). The snapshots below retain
their original scope; they are not a request to download part 15/17 again.

This refresh uses only the user's linked [E5 Data folder](https://drive.google.com/drive/folders/1GVlHQwjJte3yz0n1a1y4H4TfSe8cu6WJ).
The relevant FiveDirections folder contains 337 gzip archives and `bins.md5sum`;
all 337 archive names agree with the existing local checksum manifest. STARC
returns an empty child listing. No timestamp index or ground-truth report is
listed inside FiveDirections. Other performers were not downloaded.

## Downloaded and verified

Local dataset: `D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections`.

| Archive | Bytes | Fully decoded records | Event timestamp bounds, UTC |
|---|---:|---:|---|
| `ta1-fivedirections-1-e5-official-1.bin.122.gz` | 11,670,416 | 358,733 | May 16 20:13:05.352 – May 17 21:38:50.256 |
| `ta1-fivedirections-2-e5-official-1.bin.101.gz` | 124,386,417 | 3,890,348 | May 15 17:12:45.421 – May 17 21:39:06.370 |
| `ta1-fivedirections-3-e5-official-1.bin.111.gz` | 28,531,125 | 850,490 | May 15 18:03:55.035 – May 17 21:39:37.094 |

These are the final numbered segments of the three streams. They were selected
as a small batch to measure later-date coverage, not because their filenames
establish a particular attack window. Bounds do not imply continuous coverage.

All three match the publisher's local `bins.md5sum`; downloaded byte sizes
match Drive metadata. All records identify CDM version 20. SHA-256 hashes,
exact source links, per-file profiles and the failed large-file request are in
[the download report](drive_download_report_20261018.json). The 5,099,571 new
records include 4,981,252 Event records. The local inventory now has **31 archives,
9,014,445,802 compressed bytes**. Raw archives and SQLite caches stay local.

[The Drive inventory](drive_inventory_20261018.json) records the 338 listed
FiveDirections items and their original links without temporary download tokens.

## Evidence search and task status

The existing seven-activity search was run across all three new files, retaining
7,442 Host/Principal/Subject definition records in a local SQLite index.
[The evidence audit](drive_evidence_audit_20261018.json) reports:

- Host 2, May 15 BITS/MicroAPT window: **207 Events**, zero configured Subject
  command-line, Event path or previously seen matching-subject hits.
- Host 2, May 9 attack and May 10 benign SCP windows: **zero Events**.
- Host 3, May 10 SSH/SCP and May 17 Drakon windows: **zero Events**.
- Host 1, May 16 benign driver setup window: **zero Events**.

The search inspects Subject command lines and Event paths, not all fields.
For example, an indicator appearing only in a NetFlow record would not be found.
Missing matches do not prove absence, and neither a timestamp window nor an
unannotated record establishes a benign label. No labels were added.

**ML-02.4 remains partial.** The existing reviewed annotation set still has one
eligible attack example, no eligible benign example, and no valid supervised
train/validation/test splits. The clock-uncertain benign execution remains
excluded. These new files have not been merged into the previous combined
reference index or used to rerun reviewed-event preparation; the October 17
reports remain historical snapshots.

## Connector limit and remaining downloads

The Google Drive connector rejects stored files larger than **268,435,456 bytes
(256 MiB)**. A request for host-2 part 16, size 326,601,232 bytes, returned
HTTP 413 before downloading. Its dates remain unknown: it was a coverage probe,
not a verified May 9/10 segment. All host-2 archives except its final part 101
exceed this connector limit.

Larger segments therefore need a download route that supports their size,
such as the user's normal Drive browser download. Select and inspect additional
FiveDirections E5 segments to locate the missing documented benign and attack
activities. There is no verified date-to-part index in this folder, so this
report does not prescribe all remaining archives or infer dates from part numbers.
An empty STARC folder supplies no annotation download. The linked Data folder
does not itself provide the separately discussed updated ground-truth PDF.

## Reproduce on a friend's computer

Use the Python environment in [the ML guide](../../../../research/ml/README.md).
The downloaded files can be obtained through their original links in the report.
Run from the repository root, adjust the dataset path and use fresh cache names:

~~~powershell
$ErrorActionPreference = 'Stop'
$DatasetFolder = 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections'
$DownloadReport = Get-Content data/ml/datasets/darpa/drive_download_report_20261018.json -Raw | ConvertFrom-Json
$NewBatch = '.cache/ml-downloads/my-e5-final-segments'
New-Item -ItemType Directory -Path $NewBatch | Out-Null

foreach ($File in $DownloadReport.files) {
    $Name = Split-Path $File.path -Leaf
    $Archive = Join-Path $DatasetFolder $Name
    $Hash = (Get-FileHash -LiteralPath $Archive -Algorithm MD5).Hash.ToLowerInvariant()
    if ($Hash -ne $File.md5) { throw "Checksum mismatch: $Name" }
    if ((Get-Item -LiteralPath $Archive).Length -ne $File.compressed_bytes) {
        throw "Size mismatch: $Name"
    }
    Copy-Item -LiteralPath $Archive -Destination $NewBatch
}

$MlPython = '.\research\ml\.venv\Scripts\python.exe'
& $MlPython -m research.ml.data_prep.inspect_fivedirections --source $NewBatch --output .cache/ml-runs/my-e5-final-profile.json --records-per-file 0
& $MlPython -m research.ml.data_prep.audit_label_evidence --source $NewBatch --activities data/ml/datasets/darpa/label_review_activities_20261017.json --output .cache/ml-runs/my-e5-final-evidence
~~~

This isolates the new batch and avoids rescanning all 31 local archives.
The first command profiles all records; the second retains identity metadata
and searches the existing evidence specification. Neither command trains a model
or creates supervised labels.

## Follow-up: user-supplied host-2 part 16

The user downloaded `ta1-fivedirections-2-e5-official-1.bin.16.gz` into the same
dataset folder. Its 326,601,232 bytes and MD5
`71de2541c5d141ad5539326efc7f96ed` match the publisher's checksum manifest.
At verification the local dataset contained **32 archives**; the 31-archive
figures above describe the earlier three-file refresh.

[The complete part-16 audit](host2_part16_evidence_audit_20261018.json) decoded
**10,000,000 records**, including **9,630,752 Event records**, and retained
45,857 Subject definitions locally. Event timestamp bounds are
**2019-05-08 12:33:25.398 to 2019-05-09 20:02:12.246 UTC**; bounds do not establish
continuous coverage. The first 20,000 records separately sampled May 9 around
17:46–17:49 UTC, illustrating why a prefix alone is insufficient.

The configured May 9 host-2 attack window contains 5,544,605 raw Events and
817 path matches, with 30 candidates retained for review. There are no matching
Subject command lines in that window. Generic indicator/path hits do not prove
malice: **no new labels were assigned**. The configured May 10 benign SCP window
contains zero Events in this file. Reviewed-event preparation and supervised
splits were not rerun.

### Next manual download batch

Download these two files from the same FiveDirections folder and place them
beside part 16, keeping the original filenames and gzip compression:

| File | Size | Original Drive link |
|---|---:|---|
| `ta1-fivedirections-2-e5-official-1.bin.15.gz` | 325,830,490 bytes | [Download part 15](https://drive.google.com/file/d/1k3QQv4fEnl2rhYuUqL_oKL_jZGdWU9Pz/view) |
| `ta1-fivedirections-2-e5-official-1.bin.17.gz` | 323,153,443 bytes | [Download part 17](https://drive.google.com/file/d/1Xce-QcFz5FU8YBDJfrsT6j0idZEPxuHW/view) |

Combined size: **648,983,933 bytes (about 649 MB)**. These are adjacent-file
coverage probes, not verified date-specific downloads or a guaranteed complete
set. Part 15 may recover earlier attack/process context, while part 17 extends
the search toward May 10. Their actual dates must be inspected. Source metadata
and expected MD5 hashes are in [the download queue](host2_download_queue_20261018.json).
The user has already supplied part 16; it is not requested again.

Browser automation was rejected by the saved permission or managed policy for
`drive.google.com`; these two files also exceed the connector's 256 MiB limit.
The user can download them through their normal browser. A changed file suffix
such as `.crdownload` or an HTML confirmation page is not a complete archive.

To reproduce only the part-16 evidence scan, use a fresh output directory:

~~~powershell
& '.\research\ml\.venv\Scripts\python.exe' -m research.ml.data_prep.audit_label_evidence --source 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections' --activities data/ml/datasets/darpa/label_review_activities_20261017.json --file-pattern 'ta1-fivedirections-2-e5-official-1.bin.16.gz' --output .cache/ml-runs/my-host2-part16-evidence
~~~
