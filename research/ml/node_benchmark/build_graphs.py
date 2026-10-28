"""Build disk-backed, case-conditioned CDM reference graphs from local archives.

Edges retain native subject/predicate roles; they do not assert information-flow
direction. Published-reference membership is stored separately from graph data.
Unlisted nodes keep NULL labels. This command produces no training splits.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, OrderedDict, deque
from contextlib import closing
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import uuid

from fastavro import reader

from research.ml.data_prep.inspect_fivedirections import natural_key, utc_nanos, uuid_text
from research.ml.data_prep.resolve_references import clean, reusable_files, validate_cached_index

ROOT = Path(__file__).resolve().parents[3]
KINDS = {
    "file": "RECORD_FILE_OBJECT", "netflow": "RECORD_NET_FLOW_OBJECT",
    "subject": "RECORD_SUBJECT",
}
META_KINDS = {"RECORD_HOST", "RECORD_SUBJECT", "RECORD_PRINCIPAL"}
OBJECT_KINDS = {
    "RECORD_FILE_OBJECT", "RECORD_NET_FLOW_OBJECT", "RECORD_MEMORY_OBJECT",
    "RECORD_REGISTRY_KEY_OBJECT", "RECORD_IPC_OBJECT", "RECORD_SRC_SINK_OBJECT",
}
USABLE_VIEW_SQL = """CREATE VIEW usable_event_relations AS
    SELECT e.case_id,e.uuid AS event_uuid,e.timestamp_ns,e.cdm_action,x.*
    FROM edges x JOIN events e ON e.id=x.event_id
    JOIN nodes s ON s.id=x.subject_node_id JOIN nodes p ON p.id=x.predicate_node_id
    WHERE e.conflict=0 AND e.process_context_status='time_valid'
      AND s.metadata_status='resolved' AND p.metadata_status='resolved'
      AND (p.kind<>'RECORD_SUBJECT' OR EXISTS(SELECT 1 FROM subject_context c
        WHERE c.subject_node_id=p.id AND c.status='resolved'
          AND c.maximum_start_ns<=e.timestamp_ns))"""


def text_hash(path):
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def iso_nanos(value):
    if not value.endswith("Z"):
        raise ValueError("UTC source bound required")
    seconds = int(datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    fraction = value[19:-1].removeprefix(".")
    if len(fraction) > 9 or (fraction and not fraction.isdigit()):
        raise ValueError("Invalid nanosecond bound")
    return seconds * 1_000_000_000 + int(fraction.ljust(9, "0") or "0")


def select_sources(files, cases):
    result = {}
    for source in files:
        selected = [c["case_id"] for c in cases
                    if source["filename"].startswith(c["file_prefix"])
                    and iso_nanos(source["min_event_utc"]) < c["end_nanos"]
                    and iso_nanos(source["max_event_utc"]) >= c["start_nanos"]]
        if selected:
            result[source["filename"]] = selected
    return result


class GraphStore:
    def __init__(self, db, initialize=True):
        self.db = db
        self.cache = OrderedDict()
        if not initialize:
            return
        db.executescript("""
        CREATE TABLE cases(case_id TEXT PRIMARY KEY,host_uuid TEXT,start_ns INTEGER,end_ns INTEGER);
        CREATE TABLE sources(id INTEGER PRIMARY KEY,filename TEXT UNIQUE);
        CREATE TABLE nodes(id INTEGER PRIMARY KEY,host_uuid TEXT,uuid TEXT,kind TEXT,subtype TEXT,
          cid INTEGER,start_ns INTEGER,parent_uuid TEXT,principal_uuid TEXT,
          metadata_status TEXT NOT NULL DEFAULT 'unresolved',evidence_source TEXT,
          evidence_record INTEGER,UNIQUE(host_uuid,uuid));
        CREATE TABLE case_nodes(case_id TEXT,node_id INTEGER,observed INTEGER,
          PRIMARY KEY(case_id,node_id));
        CREATE TABLE events(id INTEGER PRIMARY KEY,case_id TEXT,host_uuid TEXT,uuid TEXT,
          timestamp_ns INTEGER,cdm_action TEXT,subject_node_id INTEGER,fingerprint BLOB,
          conflict INTEGER DEFAULT 0,process_context_status TEXT DEFAULT 'unresolved',
          UNIQUE(host_uuid,uuid));
        CREATE TABLE event_sources(event_id INTEGER,source_id INTEGER,record_index INTEGER,
          fingerprint BLOB,PRIMARY KEY(event_id,source_id,record_index));
        CREATE TABLE edges(event_id INTEGER,subject_node_id INTEGER,predicate_node_id INTEGER,
          predicate_role INTEGER,PRIMARY KEY(event_id,predicate_role));
        CREATE TABLE paths(id INTEGER PRIMARY KEY,path TEXT UNIQUE);
        CREATE TABLE node_paths(node_id INTEGER,path_id INTEGER,first_ns INTEGER,last_ns INTEGER,
          PRIMARY KEY(node_id,path_id));
        CREATE TABLE definitions(host_uuid TEXT,uuid TEXT,kind TEXT,subtype TEXT,source_id INTEGER,
          record_index INTEGER,conflict INTEGER DEFAULT 0,PRIMARY KEY(host_uuid,uuid)) WITHOUT ROWID;
        CREATE TABLE metadata_links(child_node_id INTEGER,parent_node_id INTEGER,role TEXT,
          PRIMARY KEY(child_node_id,parent_node_id,role));
        CREATE TABLE subject_context(subject_node_id INTEGER PRIMARY KEY,status TEXT,
          maximum_start_ns INTEGER,process_node_id INTEGER);
        CREATE TABLE published_nodes(case_id TEXT,uuid TEXT,expected_kind TEXT,source_file TEXT,
          source_line INTEGER,PRIMARY KEY(case_id,uuid));
        CREATE TABLE reference_matches(case_id TEXT,uuid TEXT,node_id INTEGER,status TEXT,
          PRIMARY KEY(case_id,uuid,node_id));
        CREATE VIEW node_reference_labels AS
          SELECT cn.case_id,cn.node_id,cn.observed,
          CASE WHEN EXISTS(SELECT 1 FROM reference_matches r WHERE r.case_id=cn.case_id
            AND r.node_id=cn.node_id AND r.status='typed_uuid_match') THEN 1 ELSE NULL END
            AS published_reference_label FROM case_nodes cn;
        """)
        db.execute(USABLE_VIEW_SQL)

    def node(self, host, uid, case_id=None, observed=0):
        if not uid:
            return None
        key = (host, uid)
        node_id = self.cache.get(key)
        if node_id is None:
            self.db.execute("INSERT OR IGNORE INTO nodes(host_uuid,uuid) VALUES (?,?)", key)
            node_id = self.db.execute("SELECT id FROM nodes WHERE host_uuid=? AND uuid=?", key).fetchone()[0]
            self.cache[key] = node_id
            if len(self.cache) > 100_000:
                self.cache.popitem(last=False)
        else:
            self.cache.move_to_end(key)
        if case_id is not None:
            self.db.execute("INSERT INTO case_nodes VALUES (?,?,?) ON CONFLICT(case_id,node_id) "
                            "DO UPDATE SET observed=MAX(observed,excluded.observed)", (case_id,node_id,observed))
        return node_id

    def event(self, case, raw, source_id, index):
        datum, host = raw["datum"], uuid_text(raw["hostId"])
        ts = datum.get("timestampNanos")
        if host != case["host_uuid"] or not isinstance(ts, int) or not case["start_nanos"] <= ts < case["end_nanos"]:
            return False
        uid = uuid_text(datum.get("uuid"))
        if not uid:
            raise ValueError("Selected Event lacks its native UUID")
        fingerprint = hashlib.sha256(json.dumps(clean(raw),sort_keys=True,separators=(",", ":")).encode()).digest()
        old = self.db.execute("SELECT id,fingerprint,case_id FROM events WHERE host_uuid=? AND uuid=?",(host,uid)).fetchone()
        if old:
            if old[2] != case["case_id"]:
                raise ValueError("The same native Event intersects two configured cases")
            event_id = old[0]
            if old[1] != fingerprint:
                self.db.execute("UPDATE events SET conflict=1 WHERE id=?",(event_id,))
        else:
            subject = self.node(host,uuid_text(datum.get("subject")),case["case_id"],1)
            event_id = self.db.execute("INSERT INTO events(case_id,host_uuid,uuid,timestamp_ns,cdm_action,"
                "subject_node_id,fingerprint) VALUES (?,?,?,?,?,?,?)",
                (case["case_id"],host,uid,ts,datum["type"],subject,fingerprint)).lastrowid
            for role in (1,2):
                key = "predicateObject" + ("2" if role == 2 else "")
                target = self.node(host,uuid_text(datum.get(key)),case["case_id"],1)
                if subject is not None and target is not None:
                    self.db.execute("INSERT INTO edges VALUES (?,?,?,?)",(event_id,subject,target,role))
                path = datum.get(key + "Path")
                if target is not None and path:
                    self.db.execute("INSERT OR IGNORE INTO paths(path) VALUES (?)",(path,))
                    path_id = self.db.execute("SELECT id FROM paths WHERE path=?",(path,)).fetchone()[0]
                    self.db.execute("INSERT INTO node_paths VALUES (?,?,?,?) ON CONFLICT(node_id,path_id) "
                        "DO UPDATE SET first_ns=MIN(first_ns,excluded.first_ns),last_ns=MAX(last_ns,excluded.last_ns)",
                        (target,path_id,ts,ts))
        self.db.execute("INSERT INTO event_sources VALUES (?,?,?,?)",(event_id,source_id,index,fingerprint))
        return True

    def object_definitions(self, batch):
        self.db.executemany("INSERT INTO definitions(host_uuid,uuid,kind,subtype,source_id,record_index) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(host_uuid,uuid) DO UPDATE SET conflict=CASE "
            "WHEN definitions.kind<>excluded.kind OR definitions.subtype IS NOT excluded.subtype "
            "THEN 1 ELSE definitions.conflict END", batch)

    def apply_metadata(self, node_id, kind, datum, evidence, record=None, conflict=False):
        old = self.db.execute("SELECT kind,subtype,metadata_status FROM nodes WHERE id=?",(node_id,)).fetchone()
        subtype = datum.get("type")
        conflict = conflict or old[2] == "conflicting" or (old[0] is not None and old[:2] != (kind,subtype))
        if conflict:
            self.db.execute("UPDATE nodes SET kind=NULL,subtype=NULL,cid=NULL,start_ns=NULL,"
                            "parent_uuid=NULL,principal_uuid=NULL,metadata_status='conflicting' WHERE id=?",(node_id,))
        else:
            self.db.execute("UPDATE nodes SET kind=?,subtype=?,cid=?,start_ns=?,parent_uuid=?,principal_uuid=?,"
                "metadata_status='resolved',evidence_source=?,evidence_record=? WHERE id=?",
                (kind,subtype,datum.get("cid"),datum.get("startTimestampNanos"),datum.get("parentSubject"),
                 datum.get("localPrincipal"),evidence,record,node_id))

    def context(self, subject_id):
        seen, maximum, node_id = set(), None, subject_id
        while node_id is not None:
            if node_id in seen:
                return "cycle", maximum, None
            seen.add(node_id)
            row = self.db.execute("SELECT host_uuid,kind,subtype,start_ns,parent_uuid,metadata_status FROM nodes WHERE id=?",(node_id,)).fetchone()
            if row is None or row[5] != "resolved":
                return "unresolved_or_conflicting", maximum, None
            if row[1] != "RECORD_SUBJECT":
                return "wrong_subject_kind", maximum, None
            if not isinstance(row[3], int):
                return "missing_start", maximum, None
            maximum = row[3] if maximum is None else max(maximum,row[3])
            if row[2] == "SUBJECT_PROCESS":
                return "resolved", maximum, node_id
            parent = self.db.execute("SELECT id FROM nodes WHERE host_uuid=? AND uuid=?",(row[0],row[4])).fetchone()
            node_id = parent[0] if parent else None
        return "missing_parent", maximum, None

    def finish_context(self):
        self.db.execute("DELETE FROM subject_context")
        subject_ids = self.db.execute("SELECT id FROM nodes WHERE kind='RECORD_SUBJECT' UNION "
            "SELECT subject_node_id FROM events WHERE subject_node_id IS NOT NULL").fetchall()
        for (node_id,) in subject_ids:
            status, maximum, process = self.context(node_id)
            self.db.execute("INSERT INTO subject_context VALUES (?,?,?,?)",(node_id,status,maximum,process))
        self.db.execute("UPDATE events SET process_context_status=COALESCE((SELECT CASE WHEN c.status='resolved' "
            "THEN CASE WHEN c.maximum_start_ns<=events.timestamp_ns THEN 'time_valid' ELSE 'future_start' END "
            "ELSE c.status END FROM subject_context c WHERE c.subject_node_id=events.subject_node_id),'missing_subject')")
        self.db.execute("WITH RECURSIVE reach(case_id,node_id) AS (SELECT case_id,node_id FROM case_nodes UNION "
            "SELECT r.case_id,l.parent_node_id FROM reach r JOIN metadata_links l ON l.child_node_id=r.node_id) "
            "INSERT OR IGNORE INTO case_nodes SELECT case_id,node_id,0 FROM reach")

    def match_references(self):
        for case,uid,expected in self.db.execute("SELECT case_id,uuid,expected_kind FROM published_nodes").fetchall():
            found = self.db.execute("SELECT n.id,n.kind,n.metadata_status FROM case_nodes c JOIN nodes n ON n.id=c.node_id "
                                   "WHERE c.case_id=? AND n.uuid=?",(case,uid)).fetchall()
            for node_id,kind,status in found:
                outcome = "typed_uuid_match" if status == "resolved" and kind == expected else (
                    "uuid_present_type_mismatch" if status == "resolved" else "uuid_present_" + status)
                self.db.execute("INSERT INTO reference_matches VALUES (?,?,?,?)",(case,uid,node_id,outcome))


def build(source, config_path, public_audit_path, annotation_dir, reference_audit, output, typed_cache=(), max_gib=4):
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Output must be outside the raw source directory")
    output.mkdir(parents=True,exist_ok=True)
    database = output / "graph.sqlite"
    if database.exists() or (output / "manifest.json").exists():
        raise ValueError("Use a new output directory; existing graph outputs are not overwritten")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    public = json.loads(public_audit_path.read_text(encoding="utf-8"))
    if text_hash(reference_audit / "reference_report.json") != public["current_gate"]["reference_report_sha256_utf8_lf"]:
        raise ValueError("Reference audit differs from the pinned source snapshot")
    cases = config["cases"]
    if not cases or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Distinct nonempty case IDs are required")
    for i,case in enumerate(cases):
        if case["start_nanos"] >= case["end_nanos"]:
            raise ValueError("Case window must have positive duration")
        for other in cases[i+1:]:
            if case["host_uuid"] == other["host_uuid"] and max(case["start_nanos"],other["start_nanos"]) < min(case["end_nanos"],other["end_nanos"]):
                raise ValueError("Overlapping same-host cases require an explicit grouping policy")
    files = reusable_files(list(source.rglob("*.gz")),reference_audit)
    selected = select_sources(files,cases)
    paths = {p.name:p for p in source.rglob("*.gz")}
    if len(paths) != len(list(source.rglob("*.gz"))):
        raise ValueError("Ambiguous source basenames")
    if not selected:
        raise ValueError("No downloaded archive bounds intersect the configured cases")
    budget = int(max_gib * 2**30)
    if budget < 16*2**20 or shutil.disk_usage(output).free < budget + 512*2**20:
        raise ValueError("Insufficient available space for the configured graph budget and reserve")
    report = {"status":"building","case_config_sha256_utf8_lf":text_hash(config_path),
        "builder_sha256_utf8_lf":text_hash(Path(__file__)),
        "public_annotation_audit_sha256_utf8_lf":text_hash(public_audit_path),
        "reference_report_sha256_utf8_lf":text_hash(reference_audit / "reference_report.json"),
        "graph_semantics":"Native CDM subject-to-predicate reference roles; no inferred information-flow direction",
        "selection":"All available same-host files whose raw Event bounds intersect each half-open case window",
        "source_files_validated":len(files),"storage_budget_bytes":budget,"scans":[],"typed_cache_provenance":[],
        "cases":[],"models_trained":False,"splits_created":False,"ready_for_training":False}
    save = lambda: (output / "manifest.json").write_bytes((json.dumps(report,indent=2)+"\n").encode())
    save()
    db = sqlite3.connect(database)
    db.execute("PRAGMA page_size=4096")
    db.execute("PRAGMA max_page_count="+str(budget//4096))
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA cache_size=-65536")
    db.execute("PRAGMA temp_store=FILE")
    store = GraphStore(db)
    db.executemany("INSERT INTO cases VALUES (?,?,?,?)",[(c["case_id"],c["host_uuid"],c["start_nanos"],c["end_nanos"]) for c in cases])
    for f in files:
        db.execute("INSERT INTO sources(filename) VALUES (?)",(f["filename"],))
    source_ids = dict(db.execute("SELECT filename,id FROM sources"))
    # Reference lists are loaded separately and do not select graph Events/nodes.
    for case in cases:
        item = next(f for f in public["files"] if f["name"] == case["reference_file"])
        csv_path = annotation_dir / item["name"]
        if hashlib.sha256(csv_path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Published CSV hash mismatch")
        with csv_path.open(encoding="utf-8",newline="") as stream:
            for line,row in enumerate(csv.reader(stream),1):
                uid = uuid.UUID(row[0]).hex
                fields = ast.literal_eval(row[1])
                if len(row) != 3 or len(fields) != 1 or next(iter(fields)) not in KINDS:
                    raise ValueError("Unsupported published node-reference format")
                db.execute("INSERT INTO published_nodes VALUES (?,?,?,?,?)",(case["case_id"],uid,KINDS[next(iter(fields))],item["name"],line))
    try:
        with closing(sqlite3.connect((reference_audit / "references.sqlite").resolve().as_uri()+"?mode=ro",uri=True)) as reference:
            validate_cached_index(reference,files)
        expected = {f["filename"]:f for f in files}
        for name in sorted(selected,key=natural_key):
            relevant = [c for c in cases if c["case_id"] in selected[name]]
            types, selected_count, batch, index = Counter(), 0, [], 0
            with gzip.open(paths[name],"rb") as stream:
                for index,raw in enumerate(reader(stream),1):
                    kind,datum = raw["type"],raw["datum"]
                    types[kind] += 1
                    host,uid = uuid_text(raw.get("hostId")),uuid_text(datum.get("uuid"))
                    if kind in OBJECT_KINDS and host and uid:
                        batch.append((host,uid,kind,datum.get("type"),source_ids[name],index))
                    elif kind == "RECORD_EVENT":
                        for case in relevant:
                            selected_count += store.event(case,raw,source_ids[name],index)
                    if len(batch) >= 5000:
                        store.object_definitions(batch); batch.clear()
                    if index % 100_000 == 0:
                        store.object_definitions(batch); batch.clear(); db.commit()
                    if index % 1_000_000 == 0:
                        print(json.dumps({"file":name,"records":index,"selected_event_records":selected_count,"database_bytes":database.stat().st_size}),flush=True)
            store.object_definitions(batch)
            if index != expected[name]["records"] or dict(types) != expected[name]["record_type_counts"]:
                raise ValueError("Fresh complete scan disagrees with its audited source counts: "+name)
            db.commit()
            report["scans"].append({"filename":name,"records":index,"complete_scan":True,"selected_event_records":selected_count,
                "case_ids":selected[name],"compressed_bytes":expected[name]["compressed_bytes"],"modified_time_ns":expected[name]["modified_time_ns"]})
            save()
        db.execute("UPDATE nodes SET kind=(SELECT d.kind FROM definitions d WHERE d.host_uuid=nodes.host_uuid AND d.uuid=nodes.uuid),"
            "subtype=(SELECT d.subtype FROM definitions d WHERE d.host_uuid=nodes.host_uuid AND d.uuid=nodes.uuid),"
            "metadata_status=CASE WHEN (SELECT d.conflict FROM definitions d WHERE d.host_uuid=nodes.host_uuid AND d.uuid=nodes.uuid)=1 "
            "THEN 'conflicting' ELSE 'resolved' END,evidence_source=(SELECT s.filename FROM definitions d JOIN sources s ON s.id=d.source_id "
            "WHERE d.host_uuid=nodes.host_uuid AND d.uuid=nodes.uuid),evidence_record=(SELECT d.record_index FROM definitions d "
            "WHERE d.host_uuid=nodes.host_uuid AND d.uuid=nodes.uuid) WHERE EXISTS(SELECT 1 FROM definitions d WHERE d.host_uuid=nodes.host_uuid AND d.uuid=nodes.uuid)")
        db.execute("UPDATE nodes SET kind=NULL,subtype=NULL WHERE metadata_status='conflicting'")
        db.commit()
        for folder in typed_cache:
            manifest_path = folder / "manifest.json"
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            for f in old["files"]:
                st = paths[f["filename"]].stat()
                if (st.st_size,st.st_mtime_ns) != (f["compressed_bytes"],f["modified_time_ns"]):
                    raise ValueError("Typed cache source changed")
            with closing(sqlite3.connect((folder / "entities.sqlite").resolve().as_uri()+"?mode=ro",uri=True)) as prior:
                prior.execute("ATTACH DATABASE ? AS graph",(database.resolve().as_uri()+"?mode=ro",))
                rows = prior.execute("SELECT n.id,e.kind,e.payload,e.conflict FROM graph.nodes n JOIN entities e "
                    "ON n.host_uuid=e.host AND n.uuid=e.uuid WHERE e.kind NOT IN ('RECORD_SUBJECT','RECORD_HOST','RECORD_PRINCIPAL')").fetchall()
            for node_id,kind,payload,conflict in rows:
                store.apply_metadata(node_id,kind,json.loads(payload),"typed-cache:"+text_hash(manifest_path),conflict=bool(conflict))
            report["typed_cache_provenance"].append({"path":str(folder),"manifest_sha256_utf8_lf":text_hash(manifest_path),"matched_definitions":len(rows)})
            db.commit()
        db.execute("DROP TABLE definitions")
        db.commit()
        with closing(sqlite3.connect((reference_audit / "references.sqlite").resolve().as_uri()+"?mode=ro",uri=True)) as reference:
            reference.execute("ATTACH DATABASE ? AS graph",(database.resolve().as_uri()+"?mode=ro",))
            queue = deque(r[0] for r in reference.execute("SELECT DISTINCT n.id FROM graph.nodes n JOIN entities e ON e.host=n.host_uuid AND e.uuid=n.uuid"))
            visited = set()
            while queue:
                node_id = queue.popleft()
                if node_id in visited:
                    continue
                visited.add(node_id)
                host,uid = db.execute("SELECT host_uuid,uuid FROM nodes WHERE id=?",(node_id,)).fetchone()
                definitions = reference.execute("SELECT kind,payload,filename,record_index FROM entities WHERE host=? AND uuid=?",(host,uid)).fetchall()
                unique = {(r[0],r[1]) for r in definitions}
                if len(unique) > 1:
                    store.apply_metadata(node_id,None,{},"reference-conflict",conflict=True)
                elif definitions:
                    kind,payload,filename,index = definitions[0]
                    datum = json.loads(payload)
                    store.apply_metadata(node_id,kind,datum,filename,index)
                    if kind == "RECORD_SUBJECT":
                        for field,role in [("parentSubject","parent_subject"),("localPrincipal","local_principal")]:
                            if datum.get(field):
                                target = store.node(host,datum[field])
                                db.execute("INSERT OR IGNORE INTO metadata_links VALUES (?,?,?)",(node_id,target,role))
                                queue.append(target)
        store.finish_context()
        store.match_references()
        db.execute("CREATE INDEX events_time ON events(case_id,timestamp_ns)")
        db.execute("CREATE INDEX edges_target ON edges(predicate_node_id)")
        db.commit()
        report["raw_records_scanned"] = sum(s["records"] for s in report["scans"])
        report["unique_events"] = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if any(db.execute("SELECT COUNT(*) FROM events WHERE case_id=?",(c["case_id"],)).fetchone()[0] == 0 for c in cases):
            raise ValueError("A requested case has no observed Events in the downloaded coverage")
        report["native_event_relations"] = db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        report["nodes"] = db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        report["conflicting_events"] = db.execute("SELECT COUNT(*) FROM events WHERE conflict=1").fetchone()[0]
        report["process_context_counts"] = dict(db.execute("SELECT process_context_status,COUNT(*) FROM events GROUP BY process_context_status"))
        report["metadata_status_counts"] = dict(db.execute("SELECT metadata_status,COUNT(*) FROM nodes GROUP BY metadata_status"))
        report["usable_relation_count"] = db.execute("SELECT COUNT(*) FROM usable_event_relations").fetchone()[0]
        for case in cases:
            cid = case["case_id"]
            missing = [r[0] for r in db.execute("SELECT p.uuid FROM published_nodes p WHERE p.case_id=? AND NOT EXISTS "
                "(SELECT 1 FROM reference_matches m WHERE m.case_id=p.case_id AND m.uuid=p.uuid)",(cid,))]
            report["cases"].append({**case,"start_utc":utc_nanos(case["start_nanos"]),"end_utc_exclusive":utc_nanos(case["end_nanos"]),
                "unique_events":db.execute("SELECT COUNT(*) FROM events WHERE case_id=?",(cid,)).fetchone()[0],
                "observed_nodes":db.execute("SELECT COUNT(*) FROM case_nodes WHERE case_id=? AND observed=1",(cid,)).fetchone()[0],
                "context_only_nodes":db.execute("SELECT COUNT(*) FROM case_nodes WHERE case_id=? AND observed=0",(cid,)).fetchone()[0],
                "reference_status_counts":dict(db.execute("SELECT status,COUNT(*) FROM reference_matches WHERE case_id=? GROUP BY status",(cid,))),
                "published_reference_nodes":db.execute("SELECT COUNT(*) FROM published_nodes WHERE case_id=?",(cid,)).fetchone()[0],
                "not_in_pilot_reference_uuids":missing,
                "reference_label_counts":{str(k):v for k,v in db.execute("SELECT published_reference_label,COUNT(*) FROM node_reference_labels WHERE case_id=? GROUP BY published_reference_label",(cid,))}})
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Graph SQLite integrity check failed")
        # Reclaim the temporary definition spool only when compaction fits budget.
        db.commit()
        before = database.stat().st_size
        if before*2 < budget and shutil.disk_usage(output).free > before + 512*2**20:
            db.execute("VACUUM")
        db.close()
        report["database_bytes"] = database.stat().st_size
        with database.open("rb") as stream:
            report["database_sha256"] = hashlib.file_digest(stream,"sha256").hexdigest()
        report["status"] = "complete_pilot_not_training_ready"
        report["limitations"] = ["Case-conditioned primary-host windows; not a full-release or whole-incident benchmark.",
            "Metadata joins are offline; they do not prove arrival-time availability.",
            "Unlisted nodes have NULL labels, not verified benign labels.",
            "Conflicting Events remain traceable and are excluded from the usable relation view.",
            "Only fields used here (object kind/subtype) are compared for object-definition conflicts.",
            "No model features, train/validation/test partitions or detection metrics were produced."]
        save()
        return report
    except BaseException as error:
        db.close()
        report["status"] = "incomplete_failed"
        report["error"] = str(error)
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--public-audit",type=Path,required=True)
    parser.add_argument("--annotation-dir",type=Path,required=True)
    parser.add_argument("--reference-audit",type=Path,required=True)
    parser.add_argument("--typed-cache",type=Path,action="append",default=[])
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--max-gib",type=float,default=4)
    args = parser.parse_args()
    result = build(args.source,args.config,args.public_audit,args.annotation_dir,args.reference_audit,args.output,args.typed_cache,args.max_gib)
    print(json.dumps({k:result[k] for k in ["status","raw_records_scanned","unique_events","native_event_relations","nodes","database_bytes"]},indent=2))


if __name__ == "__main__":
    main()
