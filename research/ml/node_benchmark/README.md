# DARPA E5 FiveDirections node-benchmark preparation

**Source review and input history, 2026-10-29:** all 500 frozen candidates now
have recorded evidence-sufficiency decisions; all remain unknown. A fixed
five-minute past-only, one-hop native-reference input definition clears the
history gap. Three dataset blockers remain: an accepted background cohort,
binary ground truth and enough independent groups. All 46 relevant software
tests pass. See the [pretraining review and remaining evidence](PRETRAINING_REVIEW.md).
ML-02.4 and supervised training remain incomplete.

**Native evidence packets, 2026-10-29:** the next preparation step attaches
source-linked native Events, entity definitions, actor lineage and pilot overlap
to all 500 candidates in the existing frozen review draw. Seven actor chains
have future-start flags; all 40 relevant software tests pass. See the
[measured result](../../../data/ml/datasets/darpa/node_benchmark/native_evidence_review_20261029.md)
and use the [review guide](EVIDENCE_REVIEW.md)
to reproduce the packets and inspect the local reader. Security labels remain
unknown; a human action-intent review and the four preparation gaps still stand.

**Active route, 2026-10-28: background/group review completed.** There are
500 seeded unknown-label review candidates from 7,034 observed host-1 nodes;
60 candidate identities recur in the attack pilot. No verified benign labels
were added. The current cases are assigned to one conservative evaluation group,
without claiming a common campaign or independent partitions. All 34 relevant
software checks pass. See the [review guide](BACKGROUND_REVIEW.md),
[measured result](../../../data/ml/datasets/darpa/node_benchmark/background_group_review_20261028.md)
and [v2 readiness audit](../../../data/ml/datasets/darpa/node_benchmark/background_group_protocol_audit_20261028.json).
Four preparation gaps remain; the review pool is not training data.

**Uniform metadata pass, 2026-10-28:** the original frozen
295,442-node universe received a uniform search, resolving 45,806 additional
native types (45,782 unlisted and 24 listed nodes). There are 267,164 resolved
and 28,278 unresolved types; reference labels stay 45 supported / 295,397 unknown.
All 27 relevant software checks pass. The
[measured result](../../../data/ml/datasets/darpa/node_benchmark/uniform_metadata_20261028.md)
and [uniform-recovery guide](UNIFORM_METADATA.md) document the local graph and
[updated readiness audit](../../../data/ml/datasets/darpa/node_benchmark/uniform_protocol_audit_20261028.json).
The metadata-selection blocker is cleared; five other preparation gaps remain.

**Initial preparation protocol review, 2026-10-28:** the
[metadata/background/split contract](PREPARATION_PROTOCOL.md) and its
[machine-readable audit](../../../data/ml/datasets/darpa/node_benchmark/preparation_protocol_audit_20261028.json)
are ready. All 21 relevant software checks pass, including seven new protocol
checks. At that initial review, preparation lacked a uniform metadata pass, an independently
selected background cohort, binary node ground truth, enough reviewed whole
groups and a frozen history horizon. The audit creates only diagnostics.

**Native metadata follow-up, 2026-10-28:** exact native
definitions resolved 24 of 26 untyped references, increasing accepted typed
reference matches from 21 to 45. Two Subject UUIDs remain unknown. The original
graph is preserved; a separate enriched SQLite graph remains local. Events,
relationships and Event annotations are unchanged. See the
[measured recovery report](../../../data/ml/datasets/darpa/node_benchmark/metadata_recovery_20261028.md)
and [recovery command/evidence rules](METADATA_RECOVERY.md). This annotation-directed
review does not establish a uniform metadata/sampling or training protocol.

**Initial compact raw-CDM pilot, 2026-10-28:** the existing
archives produced a 1.52 GB SQLite database with 3,425,979 unique Events,
295,442 entities and 3,540,766 native Event relations. There are 21 typed
published-reference matches; unlisted/unresolved labels remain unknown.
See the [measured pilot report](../../../data/ml/datasets/darpa/node_benchmark/compact_graph_pilot_20261028.md)
and [builder command/schema](GRAPH_FORMAT.md). No processed dump or model is
needed for this completed preparation step.

The sections below retain the optional processed-database route and its storage
limits. They are not prerequisites for the compact pilot.

**Status, 2026-10-28: preparation selected; full dump download on hold pending a storage plan.**
This is a separate benchmark track within the same DARPA E5 dataset. The
existing Event-level labels, ML-02.4 gate and raw CDM files remain unchanged.
No model has been selected, installed or trained.

The rationale is practical: the current raw subset cannot populate the
published validation date, and exact benign Event evidence remains missing.
The authors' processed source provides a concrete alternative to inspect.
It does not automatically solve label quality or evaluation design.
See the [readiness audit](../../../data/ml/datasets/darpa/ml02_benign_split_readiness_20261028.md).

## 1. Source identified; check storage before downloading

The candidate source is
[the authors' fivedirections_e5.dump](https://drive.google.com/file/d/1EkxlbReJgMHW4TwAypPggQBA-RTRVxs4/view?usp=drivesdk).
Its intended local path, if intake proceeds, is:

```text
D:\Deep Learning\fivedirections_e5.dump
```

Expected metadata size: **38,603,947,024 bytes**, about **38.6 GB**. It is the
processed FiveDirections E5 source identified in the pinned PIDSMaker download
script, not another TC engagement or the original raw-data ZIP folder.
Keep the `.dump` file intact; no extraction is requested at this step.
Do not delete or modify the existing gzip telemetry or support files.

Only file metadata has been read through the connected Drive plugin. Its
contents and download access are not yet verified. No large-file download or
browser-permission workaround was attempted.

The [authors' storage table](https://ubc-provenance.github.io/PIDSMaker/ten-minute-install/)
estimates **280 GB after loading FiveDirections E5 into PostgreSQL**, in addition
to retaining the roughly 38.6 GB source file and any working space. This is a
published estimate, not a measured restore here. The checked free space is about
159.2 GB on D: and 31.3 GB on C:, so a full restore does not fit either volume.

**Hold the large download for now.** First establish a bounded streaming/subset
intake approach or a separately approved storage plan. The metadata-size check
alone does not establish that the dataset can be used locally. Do not remove
existing data to make room. No database service or restore has been started.

## 2. Run the lightweight local check

From the repository root, use the existing ML Python environment:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.check_input `
  --manifest "data/ml/datasets/darpa/node_benchmark/source_manifest_20261028.json" `
  --input "D:/Deep Learning/fivedirections_e5.dump" `
  --output ".cache/ml-runs/node-benchmark-input-20261028/preflight.json"
```

This uses only the standard library. It checks existence, exact size and header,
then records a local report. Exit code 2 with `awaiting_download` is expected
until the file is present. Size or unknown-format failures also stop intake.
A recognized header still requires archive and dataset-scope review; it is
never marked safe to train.

Add `--sha256` after the download if a local file fingerprint is wanted. That
reads the entire 38.6 GB file. No publisher SHA-256 was supplied by the metadata
response, so a calculated local hash is recorded as a fingerprint, not described
as publisher-verified authenticity.

## 3. Inspect before restoring or training

The next phase will establish the actual archive format and inspect its table
list read-only. PostgreSQL client commands were not found on PATH during this
preparation; no packages or database service were installed.

Before accepting the source, verify:

- Table schemas, node/Event counts, timestamp units/timezone and date coverage.
- Which publishing hosts were retained and whether native CDM UUID/provenance
  can still be recovered. The inspected example table schema has no explicit
  publishing-host column; the actual dump remains uninspected.
- Coverage of the four published case lists, including missing/duplicate IDs,
  node types and the shared file UUID. Never use CSV row indices as raw offsets.
- ACT-documented activity absent from those four lists, especially May 10 host 3,
  plus persistence that can cross calendar boundaries.

Source metadata, exact size and pinned CSV hashes are in the
[input manifest](../../../data/ml/datasets/darpa/node_benchmark/source_manifest_20261028.json).
No downloaded third-party script is executed by the intake checker.

## 4. Label and evaluation protocol to review

The proposed unit is a graph node, with **published-reference membership** kept
separate from verified attack intent. The four files contain 158 rows and 157
distinct UUIDs. A listed UUID is a published attack-node reference; an unlisted
UUID is simply unlisted, not independently verified benign.

Any binary reference-membership benchmark must disclose that its zero class
means absence from the selected published list. Those zeros must not be copied
to the original Event-level annotation file or described as expert-verified
normal security activity. Missing nodes, unsupported kinds and uncertain
provenance require explicit handling before an evaluation denominator exists.

The upstream dates are reference material, not approved TraceGraph partitions.
May 10 needs host/action review; its release-level attack activity prevents a
blanket benign assumption. The upstream latest training day is after its
validation day and first test day. The primary project evaluation should retain
a justified chronological holdout; an upstream reproduction, if pursued, must
report its different assumptions separately.

Actual splits, incident/context isolation, training-only feature transforms,
normal-period assumptions and threshold selection remain undecided pending the
pilot coverage/metadata review (or dump inspection if that route is resumed).
Publication reference labels must not appear in model
features. Small numbers of attack cases limit generalization claims even when
the raw graph is large.

This preparation does not complete ML-02.4 or reactivate the original deferred
GNN/LLM experiments. A model choice comes after the data/label/split review.

## Current result

The source file was not found under `D:\Deep Learning` during this check. The
recorded [input preflight](../../../data/ml/datasets/darpa/node_benchmark/input_preflight_20261028.json)
therefore reports `awaiting_download`, with no partitions, training or dataset
content validation. That status describes file presence, not a recommendation
to download it now. The full dump intake is on hold pending the storage plan.
