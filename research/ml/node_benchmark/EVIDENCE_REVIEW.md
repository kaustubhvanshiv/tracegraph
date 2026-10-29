# Review native DARPA evidence before assigning labels

Follow-up: the [source-sufficiency review](PRETRAINING_REVIEW.md) records an
unknown decision for every frozen candidate and fixes a bounded input history.
No candidate was promoted to verified binary ground truth.

The 2026-10-29 follow-up attaches native evidence to the existing 500-ID
unknown-label draw. It keeps the selected identities and ordering fixed.
This supports ML-02 evidence preparation; it does not finish ML-02.4, create
training data or activate the deferred GNN tasks.

## Reproduce

Use the existing ML environment from the repository root. Prerequisites are the
completed background pool, the pinned plan, the 37-file reference index, the
uniform pilot graph and its conservative grouping manifest. No new dataset,
dependency, GPU or processed database dump is required.

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.review_packets `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --pool ".cache/ml-runs/background-review-pool-20261028" `
  --plan "data/ml/datasets/darpa/node_benchmark/background_review_plan_20261028.json" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --pilot-graph ".cache/ml-runs/uniform-metadata-20261028/graph.sqlite" `
  --group-review "data/ml/datasets/darpa/node_benchmark/group_review_20261028.json" `
  --annotations "data/ml/datasets/darpa/review_annotations.json" `
  --output ".cache/ml-runs/native-review-packets-20261029-new"
```

Use a fresh output directory. The producer independently recomputes the frozen
draw, verifies each selected witness and reads the original review-window
archive completely. It checks raw record/type counts and gzip exhaustion, then
checks the unchanged source inventory and input database/annotation hashes.
The source archives and databases are opened read-only.

The completed local run is in:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\native-review-packets-20261029
```

## Files for teammates

Open `review.html` locally in a browser and expand a candidate to inspect:

- The original frozen candidate and its NULL label.
- The exact native Event payload, publishing host, UTC time, native role,
  source archive, 1-based record position and complete raw-record fingerprint.
- Native entity definitions with exact source positions and full payloads.
  Repeated identical definitions are counted; different full payloads are
  preserved as conflicting variants rather than choosing one silently.
- The witness actor's host-scoped native parent lineage, principal definitions,
  missing/cyclic/depth-limited states and starts relative to the witness time.
- Native identity overlap with the existing attack pilot and its evaluation
  group. Overlap does not transfer an attack label to an earlier action.

`packets.jsonl` contains the same evidence for programmatic review.
`review_worksheet.json` contains one blank decision row per fixed candidate,
bound to the packet-file SHA-256. `manifest.json` records counts, scope and
input/output fingerprints. All four files stay under ignored `.cache`; full
commands, principal names and telemetry are not committed to GitHub.

The HTML is a static local reader. Source text is escaped and scripts/network
access are disabled by its content policy. It does not submit decisions or save
browser edits. Use an editor to make a separate copy of the worksheet if a human
review is undertaken. The worksheet is not consumed by the dataset-preparation
or training scripts.

## What evidence can support a decision

A reviewer must identify the particular action and time to which a proposed
label applies, provide independently justified action-intent evidence, verify
the native host/UUID/time mapping and record their name and rationale. A node's
participation in one benign action does not establish that all its actions or
all its temporal anchors are benign. A later node classification contract still
needs explicit review before such decisions can become training labels.

Keep the label NULL when evidence is missing or ambiguous. A system executable,
familiar path, ordinary-looking command, pre-attack date, absent CSV entry or
resolved metadata is not sufficient benign evidence. Conversely, a shared
identity or command name is not sufficient attack evidence. Do not replace the
frozen draw after inspecting the evidence or reference membership.

This command assigns no proposed security label and changes neither the
original Event annotations nor the published-reference membership contract.
Existing Event labels remain separate from these node/anchor review candidates.

## Coverage and timing limits

All 500 candidates receive the same object-definition search in the complete
source streams used by the original background window. This run does not
search every object definition in all 37 archives or certify metadata for the
7,034-node universe or a future expanded model cohort. Missing means not found
in the explicitly reviewed sources, not absent from DARPA.

Host/Principal/Subject definitions come from the completed 37-file index.
These offline definitions can be published after the witness or sample anchor.
Starts at or before the witness only check native start-time consistency; they
do not prove the definition arrived before an online detector saw the Event.
All definitions therefore retain `arrival_time_availability_proven: false`.
No packet field has been accepted as a predictive feature.

Object fingerprints distinguish the canonical kind plus cleaned native datum;
the fresh archive scan also retains a full raw-record SHA-256. Cached
Host/Principal/Subject rows only have the datum payload and source position, so
their `raw_sha256` is NULL. Their payload digest is not presented as a full raw
fingerprint. Identical repeats preserve the exact first source position plus
the occurrence count, rather than claiming to list every position.

The candidate Event's security intent is not inferred from actor-chain status.
The source archive counts, local hashes and size/mtime checks support local
reproducibility, not publisher authenticity or complete release coverage.

Four preparation gaps remain: an accepted background training cohort, reviewed
binary node ground truth, enough justified independent whole groups and a fixed
input history horizon. This packet builder is a review aid, not another
training-readiness gate or a completed human annotation pass.

## Software verification

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_review_packets -v
```

The six checks cover exact native witness binding, host-scoped full-payload
conflicts, future/missing/cyclic actor context, deterministic end-to-end output,
rejection of changed frozen labels/order, and safe rendering of source markup.
Test fixtures are small software fixtures; they are not a new ML toy dataset
and are never used to train a model.
