# TraceGraph deep learning research

Follow this guide to reproduce the DARPA FiveDirections inspection and evidence
alignment. Run commands from the repository root. Branch: **`deeplearning/shlok`**.

**2026-10-17 download refresh:** the local inventory now contains 28 archives
across three FiveDirections streams. All 28 match `bins.md5sum`. See the
[refresh procedure and results](../../data/ml/datasets/darpa/download_refresh_20261017.md)
before interpreting the historical six-file measurements below. This work
continues DARPA data preparation; it does not start a new model experiment.

## Active plan and next gate

On 2026-10-16, the **ML-R1–ML-R5 revised research plan** from `Shl-Dev` commit
`341b321` was restored in [tasks.md](../../.kiro/specs/tracegraph/tasks.md).
The original supervised GNN track remains deferred. Existing inspections,
preparation tools and the synthetic XNOR exercise are retained as recorded
work; they do not establish that a DARPA model can be trained or evaluated.

[ML-R1.1 dataset outcome](report/dataset_outcome.md) is complete. None of the
four proposed learning/reconstruction tasks has sufficient current benchmark
evidence for a credible experiment. **The ML-R1 stop condition applies: do not
proceed to ML-R2, select a GNN, or run an LLM comparison.** ML-R1.2's LANL
secondary-benchmark assessment remains pending. New datasets/models or changed
scope require the user's approval.

## Current progress

| Stage | Status |
|---|---|
| ML-01 dataset selection | Complete: DARPA TC Engagement 5 |
| Six-file prefix inspection | 120,000 records; 112,498 Events |
| Support ZIP/PDF review | Complete: E5 report, CDM 2.0 schema, operational log |
| Complete segment-121 scan | 10,000,000 records; 9,650,235 Events |
| Ground-truth alignment | Three file-open matches: one report-reviewed positive, two unknowns |
| Reviewed-event preparation | 2,000,000 records scanned; three candidates retained; one parent process resolved |
| Full reference audit | Six files; 60,000,000 records; missing actor/Host/Principal definitions confirmed |
| ML-02.1 / ML-02.2 / ML-02.3 | Target/graph definition, split policy and scenario-use plan complete |
| ML-02.4 actual dataset preparation | Partial: scripts tested; real supervised splits blocked by label coverage |
| Labels, splits, training | Contract and split checks implemented; verified evidence and independent groups missing |
| ML-03.1 baseline assessment | Complete: current labeled subset cannot support supervised baseline evaluation |
| Historical ML-04 neural-network exercise | Completed on synthetic XNOR; retained educational artifact within deferred original track |
| ML-R1.1 dataset feasibility | Complete: stop finding for current audited evidence; ML-R1.2 remains pending |

All six segments were fully decoded in the reference audit; the original
inspection profile remains prefix-only. No trained DARPA GNN or security
classification results exist. Research is separate from production correlation.

## 1. Get the code

Install Git and Python **3.11 or newer**. These steps do not require Docker,
PostgreSQL, Neo4j, CUDA, or a GPU.

```powershell
git clone --branch deeplearning/shlok https://github.com/kaustubhvanshiv/tracegraph.git
cd tracegraph
```

For an existing clone, save your work before switching branches:

```powershell
git fetch origin
git switch deeplearning/shlok
git pull --ff-only origin deeplearning/shlok
```

## 2. Download data outside Git

Use the [official E5 Drive folder](https://drive.google.com/drive/folders/1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf)
linked by [DARPA](https://github.com/darpa-i2o/Transparent-Computing).
For the same subset, download these files from `data/fivedirections/`:

```text
ta1-fivedirections-1-e5-official-1.bin.15.gz
ta1-fivedirections-1-e5-official-1.bin.17.gz
ta1-fivedirections-1-e5-official-1.bin.20.gz
ta1-fivedirections-1-e5-official-1.bin.23.gz
ta1-fivedirections-1-e5-official-1.bin.27.gz
ta1-fivedirections-1-e5-official-1.bin.121.gz
```

Together they are about **1.89 GB compressed**. If Drive wraps telemetry in a
ZIP, unpack the outer ZIP to obtain these gzip files. Keep the `.gz` compression;
our reader streams it directly.

Also download the ground-truth and schema folders as ZIPs, plus the operational
log. The support reader handles those ZIPs directly. Actual received contents:

- `Ground_Truth/TA51_Final_report_E5.pdf` (Revision 1.0, June 28, 2019).
- `Schema/TCCDMDatum.avsc`, `Schema/CDM20.avdl`, `Schema/cdm.pdf`.
- `Engagement-5-Event-Log.md`.

The official manifest uses `tc_ground_truth_report_e5_update.pdf` and
`operational_event_log.md`; actual downloaded names can differ. Check your
support manifest rather than assuming different report versions share page
numbers or hashes. Keep all original downloads outside this repository.

## 3. Create the Python environment

```powershell
python -m venv research/ml/.venv
& .\research\ml\.venv\Scripts\python.exe -m pip install -r research/ml/requirements-support.txt
```

This installs `fastavro==1.12.2` and `pypdf==6.10.0`. Only `requirements.txt` is
needed for telemetry inspection, but PDF tests then skip. No Codex runtime is
required. Replace these download paths with yours:

```powershell
$MlPython = '.\research\ml\.venv\Scripts\python.exe'
$DataSource = 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049'
$SupportSource = 'D:\Deep Learning\darpa-tc-e5-support'
```

## 4. Run the fast inspection

```powershell
& $MlPython -m research.ml.data_prep.inspect_fivedirections --source "$DataSource" --output '.cache/ml-runs/fivedirections_profile.json' --records-per-file 20000
```

For the same files, expect **120,000 records**, **112,498 Events**, and no decode
errors. These are file prefixes, not representative samples or complete counts.
Timestamps can move backwards. Different files can produce different counts.

## 5. Read the support ZIPs

```powershell
& $MlPython -m research.ml.data_prep.read_support --source "$SupportSource" --output '.cache/ml-support'
```

Expected inspection outputs include:

```text
.cache/ml-support/manifest.json
.cache/ml-support/Ground_Truth/TA51_Final_report_E5.pdf
.cache/ml-support/Ground_Truth/TA51_Final_report_E5.pages.txt
.cache/ml-support/Schema/TCCDMDatum.avsc
```

Our report has 158 pages and `cdm.pdf` has six. The manifest records source/member
hashes and page counts. Recovery warnings may appear for the report PDF; view
relevant original pages when interpreting extracted text.

## 6. Optionally scan the complete attack segment

This reads **10 million records** and can take several minutes. Existing findings
are committed, so a repeat scan is optional.

```powershell
& $MlPython -m research.ml.data_prep.audit_attack_coverage --source "$DataSource" --filename 'ta1-fivedirections-1-e5-official-1.bin.121.gz' --candidates 'data/ml/datasets/darpa/fivedirections_attack_candidates.json' --schema '.cache/ml-support/Schema/TCCDMDatum.avsc' --output '.cache/ml-runs/fivedirections_attack_coverage.json'
```

Omit `--filename` to scan every discovered segment. Completion refers to the
selected files; the report records selected and discovered counts. Progress
prints every 250,000 records and completed-file checkpoints are saved.
Add `--resume` to the same command to reuse completed files. Source paths,
configuration, size, and modification time must match. An interrupted file is
restarted from its beginning.

In segment 121, expect matching schemas and one `EVENT_OPEN` occurrence each
for `PD2GziBJ2wpDwP`, `7B4qoq3yWIKPQh`, and `DXu0yAtkCpuUTo`.
These are review candidates; the tool assigns **zero labels**. A single-file
scan does not establish indicator frequency across the release.

## 7. Run tests

```powershell
& $MlPython -m unittest discover -s research/ml/tests -v
```

With support dependencies installed, all **32 tests** should pass. They cover
corrupt input, sampling limits, timestamp precision/timezones, indicator-label
separation, safe ZIP paths, preservation of archives, strict label validation,
streaming preparation, deduplication, chronological group/context checks,
reference conflicts, cyclic parents, process start-time checks, and local versus
remote IP evidence, positive incidents assigned to multiple groups, and ID-only
split export to the requested directory without overwriting existing splits.
Additional adapter tests cover typed file/memory/registry mappings, host-scoped
joins, temporal process validity, incoming/outgoing network fields, distinct
login/logout/thread/execute semantics, and ambiguous command lines.

## 8. Prepare the reviewed events

Install the updated requirements in your ML environment first. Preparation
uses the backend's Pydantic models but does not start the backend or database.

```powershell
& $MlPython -m pip install -r research/ml/requirements-support.txt
& $MlPython -m research.ml.data_prep.prepare_dataset `
  --source $DataSource `
  --annotations data/ml/datasets/darpa/review_annotations.json `
  --output .cache/ml-runs/my-prepared-review `
  --records-per-file 2000000
```

Use a fresh output directory for each run. Exit code **2** means the preparation
finished but evidence is insufficient for supervised splits. Inspect
`manifest.json` and `review_events.jsonl` in that directory; the SQLite subject
index stays local. These are only three selected review events, not a sampled
training dataset. `--records-per-file 0` scans selected source files fully.
Only filenames listed in annotations are scanned; other downloaded segments
are not implicitly covered.

When all checks pass, the CLI exports only event IDs in `train.json`,
`validation.json` and `test.json` under `data/ml/splits/`. To keep multiple
validated runs, supply `--split-output data/ml/splits/<run-name>` with a fresh
destination. Existing directories are not overwritten. Blocked runs do not
create a split destination; unknown events are excluded from binary splits.
Synthetic split-export tests are code validation, not real DARPA split results.

The current run found all three events, with one report-reviewed positive,
two unknown labels and one resolved parent process. Two events share an
unresolved parent. No split files were
written. The adapter preserves CDM actions and nanosecond timestamps in raw
metadata. The 2026-10-13 rerun resolves all three selected objects as files
and emits canonical `file/access` events. One has a time-valid Firefox process
image; missing users/hostnames remain null. No labels changed and no splits
exist. See [SEMANTICS.md](data_prep/SEMANTICS.md) for mappings and limitations.
Canonical event fields and reference metadata are not ML feature vectors or
trained graph inputs.

To unblock training: obtain event-level annotations or independently review
host identity and actor/object evidence for positives; identify explicitly
verified benign events; obtain at least three independent groups with both
classes in each chronological partition. Keep related attack phases together.
Then review annotation `label`, `review_status`, `group_id`, and `evidence`
against the [label contract](../../data/ml/ground_truth.md), rerun preparation
with the intended `--context-nanos`, and check the achieved split counts.
Do not change null labels to zero to make the checks pass.

## 9. Audit references across all downloaded segments

```powershell
& $MlPython -m research.ml.data_prep.resolve_references `
  --source $DataSource `
  --annotations data/ml/datasets/darpa/review_annotations.json `
  --output .cache/ml-runs/my-reference-audit `
  --records-per-file 0
```

This full scan can take several minutes. It builds a local SQLite index of
subject, principal and host definitions, then joins the three review events.
`scan_progress.json` records completed files; interrupted runs cannot be resumed.
Use a fresh output directory. `--file-pattern` selects a stream, and
`--reuse-audit` reuses a completed local full audit after checking the selected
files' sizes/modification times and the cached index's definition counts.
Verify archive checksums separately. A positive limit scans prefixes only and
cannot establish that a definition is absent from an entire segment.

To incorporate newly downloaded files for the original host, run:

```powershell
& $MlPython -m research.ml.data_prep.resolve_references `
  --source $DataSource `
  --annotations data/ml/datasets/darpa/review_annotations.json `
  --file-pattern 'ta1-fivedirections-1-*.gz' `
  --output .cache/ml-runs/my-expanded-host1-audit `
  --records-per-file 0

& $MlPython -m research.ml.data_prep.prepare_dataset `
  --source $DataSource `
  --annotations data/ml/datasets/darpa/review_annotations.json `
  --reference-audit .cache/ml-runs/my-expanded-host1-audit `
  --output .cache/ml-runs/my-expanded-preparation `
  --records-per-file 2000000
```

The first command scans all matching files on a fresh clone. If a completed
local reference audit and its SQLite index already exist, optionally add
`--reuse-audit .cache/ml-runs/my-earlier-full-audit` to avoid decoding unchanged
files again. A checked-in JSON report alone cannot supply that local index.
Preparation imports only audited host/principal/subject definitions, still
checks host identity and subject start times, and preserves annotation labels.
Exit code **2** means preparation completed but training gates remain blocked;
read `manifest.json` rather than interpreting it as a successful split export.

`reference_report.json` reports unresolved and conflicting UUIDs, distinguishes
thread IDs from process IDs, and checks process start time against event time.
Full command lines and principal names stay in the local SQLite index. The
aggregate report exposes only a Firefox command-line flag for these candidates.
Entity joins alone do not establish attack or benign labels.

The completed run decoded all **60,000,000 records**, including **58,037,343
Events**, and indexed 257,164 Subjects. No Host/Principal definitions or the
missing parent are present in these six files. Host/IP evidence instead comes
from 268 local netflow observations of `128.55.12.55` in a two-million-record
segment-121 prefix. Reproduce that bounded check with:

```powershell
$Segment121 = Join-Path $DataSource 'fivedirections/ta1-fivedirections-1-e5-official-1.bin.121.gz'
& $MlPython -m research.ml.data_prep.audit_network_host `
  --source-file $Segment121 `
  --output .cache/ml-runs/my-network-host-review.json `
  --records 2000000
```

Adjust `$Segment121` if your download has a different directory layout.
The [reference review](../../data/ml/datasets/darpa/reference_review.md)
documents the one positive's provenance and limitations. The documented benign
driver setup falls outside these files' event ranges. Additional telemetry or
reviewed annotations are needed for benign examples and independent incidents.

## Linux and macOS

Use the same module arguments and your own source paths:

```bash
python3 -m venv research/ml/.venv
research/ml/.venv/bin/python -m pip install -r research/ml/requirements-support.txt
research/ml/.venv/bin/python -m unittest discover -s research/ml/tests -v
```

Replace `& $MlPython` in the Windows examples with
`research/ml/.venv/bin/python` and use normal quoted paths.

## Findings and next work

The [classical baseline assessment](baseline/README.md) is complete. With one
reviewed positive, no verified negatives and no valid partitions, optional
baseline feature engineering/training is deferred.

[Historical ML-04 neural-network fundamentals](nn_fundamentals/README.md) was completed.
It uses separate CPU dependencies in `requirements-nn.txt` and synthetic data.
The guide includes commands, tensor/gradient explanations, measured training
dynamics, plots, and checkpoint inference. Model checkpoints stay local in
`.cache/`; code, concise summaries and plots are committed. No synthetic result
is a DARPA detection metric. The revised ML-R1–ML-R5 plan now controls sequencing;
ML-05 is deferred, not the next active task. The
[dataset outcome report](report/dataset_outcome.md) records current feasibility
and stop conditions. ML-02 actual preparation still requires label/incident evidence.

- [Dataset selection](../../data/ml/comparison/primary_dataset_selection.md).
- [Local prefix inspection](../../data/ml/datasets/darpa/fivedirections_local_inspection.md).
- [Support review and exact matches](../../data/ml/datasets/darpa/support_review.md).
- [Ground-truth/split plan](../../data/ml/ground_truth.md).
- [Task checklist](../../.kiro/specs/tracegraph/tasks.md).

The May 17 log explicitly uses EDT: **16:11 EDT = 20:11 UTC**. The May 16
persistence and May 17 escalation belong to one attack group, so cannot serve
as independent training and test incidents. Unmatched events remain unknown,
not automatically benign. Thread subjects must resolve to parent processes
before constructing process features.

Implemented: reviewed-event preparation and split validation. Remaining:
verified labels, benign evidence, complete reference/host coverage and
independent incident groups. Model experiments follow after those gates pass.

## Collaboration and Git

Commit code, instructions, small aggregate reports, and annotation metadata.
Keep raw downloads, extracted support files, environments, models, and large
prepared datasets outside Git. `.cache/` and `.venv/` are ignored. Local reruns
above write to `.cache/` to preserve the committed findings from Shlok's run.

After completing and testing a change:

```powershell
git status --short
git add research/ml/README.md
# Add the specific code/report files you changed, then review the staged diff.
git diff --cached --stat
git diff --cached --check
git commit -m "Describe the completed ML change"
git push origin deeplearning/shlok
```

Maintain this README whenever commands, dependencies, findings, or prerequisites
change. Record what ran and its results in each milestone's notes.
