# Evidence needed for a supervised DARPA benchmark

Use this checklist for a qualified human/provider review. The
[empty intake CSV](../../../data/ml/datasets/darpa/annotation_intake_20261102.csv)
contains column headers only. It is a collection form, not accepted annotations
or a training dataset. Keep the current canonical `review_annotations.json`
unchanged until the evidence and native mapping have been reviewed.

## Required evidence per action

| Field | Required meaning |
|---|---|
| Native identity | Publishing host UUID and native CDM Event UUID; stream/release scope |
| Raw location | Exact gzip basename, one-based record position and canonical raw-record fingerprint |
| Action and actor | Native action, subject UUID and relevant predicate UUIDs; host-scoped joins |
| Native time | Integer Unix-epoch nanoseconds and derived UTC time; source timezone and clock reliability |
| Security decision | Documented ACT attack action (1), explicitly verified benign action (0), or unknown |
| Source evidence | Source file/version/hash, page or annotation row, and exact action-specific matching explanation |
| Incident and group | Attack incident ID where applicable; group identity and evidence supporting separation from other groups |
| Eligibility | Whether the action is eligible for supervised partitions; any exclusion reason |
| Reviewer | Reviewer identity, review date and scope/limitations of the decision |

Do not identify a process using PID alone. Account for process versus thread
CID, process lifetimes, missing parents, conflicting definitions and source-clock
semantics. An offline metadata match does not prove those attributes were
available to an online detector.

## Benign evidence must establish purpose

A verified benign action needs source-backed benign intent and an exact native
mapping. A missing attack annotation, familiar process name, low reconstruction
error, date before a reported attack, or absence from a published node list does
not establish label 0. An operational maintenance note labels only the actions
whose purpose, host and time can be established; it does not label an entire
window or machine as benign.

The reviewed May 7 BCDEDIT execution is already labelled benign for review but
excluded from splits. Its mixed clock epochs must be independently calibrated
before it can become eligible. Do not select an offset because it gives a
desired label match.

For the ACT report page-135 SCP example, authoritative clarification must state:

- Whether 03:38:26.71 denotes occurrence, receipt or alarm creation; its timezone
  and 12/24-hour format.
- Whether `pid=680` is decimal, hexadecimal, a process CID, thread CID or an
  internal identifier.
- The native CDM host, Event, Subject and predicate UUIDs corresponding to
  CDL Subject 119657/Object 835986. Integer CDL IDs must not be converted into
  guessed UUIDs.

This is a prepared review checklist. No message has been sent to a provider.

## Split acceptance before model evaluation

Keep each attack incident and inseparable related context in one partition.
Order independent groups chronologically and purge the selected past-only input
history at boundaries. Both classes must occur in every evaluable partition.
More rows from the same incident do not increase incident independence.

The current two named positive groups cannot provide independent positives in
three partitions. At least one additional independently justified positive
group and eligible benign coverage are necessary; the structural minimum does
not guarantee a statistically useful sample. Document class balance, incident
counts and uncertainty before choosing a model or security threshold.

Do not fit new thresholds or hyperparameters on the reconstruction test cohort
after examining its residuals. Any retrospective reuse must be disclosed; an
independent security claim needs a predeclared and suitable evaluation protocol.

After review, retain unknowns and exclusions, import only accepted action-level
annotations, rerun `reviewed_label`/`make_splits` checks through canonical
preparation, and review graph/feature compatibility. Preserve original reports
and raw files. A passed ingestion check alone is not expert label certification.
