# DARPA TC E5 — additional downloads

**Alignment audit, 2026-10-27:** no defensible clock/PID conversion was found.
The next input is authoritative alarm-to-CDM mapping or independently verified
benign annotations, rather than another broad archive batch. A conditional
07:38 UTC gap exists if the quoted time means EDT, but that interpretation is
not established. See the [resolution audit and clarification questions](datasets/darpa/ml02_alignment_resolution_20261027.md).

**Latest SCP follow-up, 2026-10-27:** parts 18-20 are received and verified;
all 37 local archives are fully audited (345,099,571 raw records). Filename
matches did not establish the report's specific benign WRITE/PID/time case.
No further broad download batch is requested: clarify the source annotation
and time mapping before selecting additional telemetry. The label/split gate
remains blocked. See the [SCP review](datasets/darpa/ml02_scp_followup_20261027.md).

**Earlier 2026-10-27 update:** host-2 parts 15 and 17 are present, checksum-verified
and fully decoded. All 34 local archives are now audited. Two reviewed May 9
attack actions were added, but the downloaded host-2 data still lack the
May 10 benign SCP example. The next manual coverage probes are parts 18, 19
and 20 (about 966 MB total), with unverified dates. See the exact source links
and checksums in [the new queue](datasets/darpa/host2_download_queue_20261027.json)
and [the continuation report](datasets/darpa/ml02_label_review_20261027.md).
More evidence and independent groups are still required; these downloads do
not guarantee valid splits. The schema, operational log and existing report
are already available locally.

**2026-10-17 ML-02.4 finding:** all 28 locally downloaded archives are fully scanned.
The corresponding host-2/3 streams end on May 8, before the additional
documented attack and benign SCP cases. Host 1's documented May 16 benign
setup interval is also absent. See the
[verified activity coverage and required evidence](datasets/darpa/ml02_label_review_20261017.md).
The review found one benign administrative execution, but its uncalibrated
clock excludes it from supervised splits. More raw records alone do not supply
reviewed labels or independent train/validation/test groups. Archive numbers
for the missing windows have not been verified; do not infer them from adjacent
filenames or redownload support materials already present.

**2026-10-17 inventory update:** 28 local archives across FiveDirections-1/2/3
now match the downloaded `bins.md5sum`: 10, 8 and 10 files respectively, totaling
8,849,857,844 compressed bytes. The manifest lists 337 files; 309 are absent
locally. Missing files are not all required downloads. The user reports that
the shared `starc` folder opens empty; no STARC files were acquired or verified.
The starting file supplies Host/Principal metadata absent from the original
six-file audit. See the [download refresh](datasets/darpa/download_refresh_20261017.md)
for scope, measurements and reproducible next steps. Older priorities below
describe the original acquisition stage, not a request to redownload support
materials already present.

**Received 2026-10-11:** The user downloaded ground-truth and schema ZIPs plus
the operational log to `D:\Deep Learning\darpa-tc-e5-support`. The ground-truth
archive actually contains `TA51_Final_report_E5.pdf` (Revision 1.0), not the
updated-report filename in the manifest below. It covers E5 and has been read.
See [support review](datasets/darpa/support_review.md) for verified contents,
event matches, and the remaining labeling requirements. No manual unzip is
needed for the current pipeline.

Use the [official Engagement 5 Google Drive folder](https://drive.google.com/drive/folders/1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf)
linked by [DARPA's release README](https://github.com/darpa-i2o/Transparent-Computing).
Use **Engagement 5 / CDM 2.0**, matching the existing `e5` files; do not mix
Engagement 3 labels or schema into this experiment.

The file paths below are from DARPA's manifest. The Drive's live file listing
was not available through the web reader; folder capitalization may differ.

| Priority | Download | Why |
|---|---|---|
| Required before supervised training | `ground truth/tc_ground_truth_report_e5_update.pdf` | Describes ACT attack actions, timing, hosts, and indicators. Needed to establish which incidents overlap the six segments and to define defensible positive/negative examples. A narrative still needs careful event alignment. |
| Strongly recommended; obtain if present | STARC / TA3 attack annotations for FiveDirections E5 | DARPA says STARC supplied attack annotations for each stream. These may provide more precise event mappings than the narrative. Exact filenames/location/format are not verified; look for `starc`, `annotation`, or `ground truth` materials and preserve their provenance. |
| Recommended before semantic conversion | `schema/CDM20.avdl` | Human-readable schema with semantic notes. Helps interpret UUID references, action directions, units, and optional fields. |
| Recommended before semantic conversion | `schema/cdm.pdf` | Explains CDM concepts, needed to distinguish process/file/network/memory/registry activity correctly. |
| Recommended for coverage checks | `operational_event_log.md` | Lists activity and operational issues in the exercise. Helps assess collection gaps and label uncertainty. It is not itself an event-level attack-label file. |
| Optional for the current parser | `schema/TCCDMDatum.avsc` | Standalone machine-readable schema. Useful for reference and other tools; all six current files already embed a readable schema. |
| Later, after inspecting incident coverage | More `data/fivedirections/` segments | Needed if attacks are outside current time coverage or referenced entities occur in other segments. Select segments based on verified coverage; adjacent filenames alone do not guarantee complete references. |

The Java consumer under `tools/ta5-java-consumer.tar.gz` is optional: the current
Python reader already decodes these files. No need to download other performers
or the entire release for the first FiveDirections experiment.

Rechecked 2026-10-13: the [official release manifest](https://github.com/darpa-i2o/Transparent-Computing)
confirms STARC attack annotations, but does not name their archive/files. No
new annotation file was retrieved or imported. The local support folder still
contains the original report/schema ZIPs and event log. To unblock ML-02.4,
obtain event-level annotation evidence plus telemetry covering verified benign
host-1 actions and independent campaigns. More raw events alone are not labels.

Suggested local organization outside Git (create these while downloading):

```text
D:\Deep Learning\darpa-tc-e5-support\
    ground_truth\
    annotations\
    schema\
    operational_event_log.md
```

After downloading, provide the actual folder path. Next we will inspect the
ground truth, establish host/UTC/UUID mappings, check incident coverage, resolve
entity references, and prepare labeled data. Events with insufficient evidence
remain unknown. Do not assume every unannotated event is benign.
