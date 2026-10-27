# ML-02.4 public-annotation case review - 2026-10-27

**The case comparison is complete; supervised dataset preparation is still
blocked.** The four pinned PIDSMaker files corroborate the artifact UUIDs of
all five attack-related Events in our existing review set. Three already have
action-specific positive labels. Two remain unknown because their process
parent is still missing under our current review rules.

No new label, independent incident, benign example or trained model is claimed.
The original annotation file is unchanged. Its UTF-8/LF SHA-256 remains
`f3c129e55ed3117f4b69b19c0cc3c15b8c12ce2f7a19af6391682aedbb8ce2be`.

## Work performed and scope

The [public-source research](ml02_public_source_research_20261027.md) found
158 rows / 157 distinct node UUIDs at PIDSMaker commit
`438a05a7c55256f639e5b5945cf4828fe3ee078e`. This follow-up:

1. Verified all four CSV SHA-256 hashes and checked the prepared review rows
   against the current annotations.
2. Revalidated source size/modification-time provenance and definition counts
   for the existing 37-file reference index, opened read-only.
3. Freshly decoded 2,000,000 records from host-1 part 121 and 100,000 from
   host-2 part 16. These are bounded prefixes containing our five selected
   attack/candidate Events. Each Event's complete cleaned raw CDM record and
   exact source position agree with its previously prepared record.
4. Compared direct Subjects, referenced objects and valid resolved parent
   processes separately. Kept host scoping and start-time checks intact.
5. Checked additional file/network UUIDs against the two existing typed entity
   caches. Those cache lookups are not new full-corpus object scans.
6. Visually rechecked ACT report pages 126-127 and revalidated all six canonical
   SecurityEvents. Reran the existing split gate; it remains blocked.

The new repeatable command produced the same comparison as the initial scan.
That is two passes over the same 2.1-million-record prefixes, not 4.2 million
additional dataset records. The corpus remains the previously audited 37-file
subset with 345,099,571 raw records. No additional archive was downloaded.

## Case-by-case result

| Published case | Subject definitions in full existing metadata | File definitions in bounded typed caches | Evidence for the six reviewed Events |
|---|---:|---:|---|
| Copykatz, May 9 | 17 | 2 | Both `tropical` output actions match the published target FileObject and the valid Firefox parent process |
| BITS, May 15 | 0 | 3 | Existing file objects alone do not establish an attack Event; no selected reviewed Event matches |
| DNS, May 17 | 0 | 0 | No selected reviewed Event matches; absence from these caches is not absence from the release |
| Drakon, May 17 | 2 | 3 | All three generated-artifact OPEN actions match both the published direct thread and target FileObject |

These counts identify **19 Subjects and eight FileObjects** across the scopes
shown. The earlier 19-Subject result did not inspect FileObject definitions.
No NetFlowObject UUID matches were found in these two bounded typed caches.
See [object-cache matches and source-cache provenance](public_object_cache_alignment_20261027.json).

The fourth published Drakon file node, `852e765f30d142398398b3107bc1b24e`
with descriptive path `\Device\Afd`, was not resolved in those bounded caches.
Its path is not substituted for a typed definition.

## Action decisions

| Event / artifact | Published evidence confirmed | Current decision |
|---|---|---|
| `cba5c7333a594b0b9b6f7b3e6489d9c2` / PD2GziBJ2wpDwP | Direct thread and exact artifact FileObject, compatible case window | Keep unknown; parent process `1fca97f4e4134d05869b31eb09df8770` is unresolved |
| `8f5db838a1504f5b9b0ce074a1e356a0` / 7B4qoq3yWIKPQh | Same direct thread and exact artifact FileObject, compatible case window | Keep unknown for the same actor gap |
| `b2f735d934fc4f92ac98996118533f5c` / DXu0yAtkCpuUTo | Direct thread, exact artifact FileObject and valid process lineage | Keep existing reviewed positive |
| `1d92d20361b242f7984f23422ef135be` / tropical CREATE_OBJECT | Exact FileObject and valid Firefox parent UUID | Keep existing reviewed positive |
| `fb20dd62334c48e9a9ea6972c43501f0` / tropical WRITE | Same FileObject and parent UUID, distinct thread and action | Keep existing reviewed positive, same incident/group |
| `fce7334c4dc6494b82d4f35cd1b2f8d6` / BCDEDIT EXECUTE | No published-node correspondence | Keep reviewed benign label and its clock-based split exclusion |

The two Copykatz direct threads are not themselves listed in the published CSV;
the correspondence is through their validated parent process and target object.
That distinction is preserved in the [Event-level comparison](public_event_alignment_20261027.json).
The benign Event was checked from its unchanged prepared raw record; its source
archive was not reread in this step.

The ACT report explicitly connects the generated filenames with attempts to
trigger the elevation driver. Pages 126-127 also distinguish an initial
attempt that still reports `admin` from subsequent `SYSTEM` output. A matching
OPEN is not, by itself, evidence that a particular attempt gained SYSTEM.
Neither PID, process image nor privilege outcome is fabricated for the two
unknown candidates.

The report source is the existing local `TA51_Final_report_E5.pdf`, physical
pages 126-127, SHA-256
`95785dd6e32e1585e3a3b49f7f69aac785ca9d2db05593ad919b1b627897f0a1`.
The CSV source links, row numbers, fresh raw-record fingerprints, source
positions, actor-chain results and window comparisons are in the Event audit.

## Why candidate counts do not become labels

Within the two scanned prefixes and their corresponding upstream windows,
the direct-node-touch diagnostic counts 5,420 raw Event records for Copykatz
and 3,570 for Drakon. BITS and DNS yield zero in this particular scan.
These counts are neither unique training samples nor independently verified
attack actions. The scanner has not deduplicated these diagnostic counts.

All four May-2019 upstream windows were compared using their configured
US/Eastern convention, interpreted as EDT UTC-04:00 for those dates. Raw Event
nanoseconds are unchanged. This convention does not calibrate the separate
MARPLE SCP alarm or justify applying an offset to other records.

Importing every node-touch record would change the current label contract.
No such import was performed. The shared file node across the published
Copykatz/BITS lists also means case filenames alone do not establish independent
split groups.

## Reproduce

Run from the repository root using the existing ML environment. This command
uses `fastavro` and the standard library; CUDA/PyTorch are unnecessary.

Prerequisites are the current 37-file reference cache, the existing combined
six-event review, and the four CSVs linked in the public-source research note.
Save the original CSV bytes in `.cache/ml-runs/public-source-research-20261027`.
The command verifies their pinned hashes and fails if annotations or source
provenance have changed. Prior reference/preparation steps are documented in
[the ML README](../../../../research/ml/README.md).

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.data_prep.review_public_annotations `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --annotation-dir ".cache/ml-runs/public-source-research-20261027" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --prepared-events ".cache/ml-runs/combined-review-preparation-20261027/review_events.jsonl" `
  --output ".cache/ml-runs/public-case-review-20261027/reproduced"
```

Output is a comparison report, not a new annotation file or a prepared split.
The script rejects output inside the raw-data directory and altered CSV bytes;
both rejection paths were checked. The initial and command-generated reports
agree exactly after the diagnostic count field was given its explicit raw-record
name. Do not use the intentionally modified CSV fixtures retained in the local
guard-check folder.

To reproduce the supplementary typed-cache lookup, query each published UUID
on each known publishing host in the existing preparation databases:

```sql
SELECT kind, conflict, payload
FROM entities WHERE host = ? AND uuid = ?;
```

Use `ml02-label-preparation-20261017/entities.sqlite` and
`host2-case-preparation-20261027/entities.sqlite` under `.cache/ml-runs/`.
Check the corresponding preparation manifests before reuse; retain kind and
conflict status. These definitions do not carry a new Event occurrence time.

## Conclusion and next evidence needed

[The refreshed gate](public_alignment_gate_20261027.json) validates six canonical
Events and records unchanged reviewed labels: three attacks, one benign action
excluded for clock uncertainty, and two unknowns. Eligible labels remain
**three attack actions across two incident groups / zero benign actions**.

ML-02.4 therefore remains incomplete. The next useful evidence is a verified
benign action with reliable time and independent case provenance, or authoritative
metadata resolving the two candidates' actor parent. More matches in these
same two attack groups cannot, on their own, supply valid three-way splits.
Adopting a different node-level benchmark or labeling protocol requires the
user's approval before implementation.
