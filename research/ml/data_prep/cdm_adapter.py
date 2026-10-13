"""Conservative offline CDM mappings; annotation evidence is never an input."""
import ipaddress
import json
import shlex

from app.schemas.parser import ParsedEvent, ParseError
from research.ml.data_prep.inspect_fivedirections import utc_nanos, uuid_text


ENTITY_KINDS = {"RECORD_SUBJECT", "RECORD_HOST", "RECORD_PRINCIPAL",
                "RECORD_FILE_OBJECT", "RECORD_NET_FLOW_OBJECT", "RECORD_MEMORY_OBJECT",
                "RECORD_REGISTRY_KEY_OBJECT", "RECORD_IPC_OBJECT", "RECORD_SRC_SINK_OBJECT"}
FILE_ACCESS = {"EVENT_OPEN", "EVENT_READ", "EVENT_WRITE", "EVENT_CLOSE",
               "EVENT_CHECK_FILE_ATTRIBUTES", "EVENT_MODIFY_FILE_ATTRIBUTES",
               "EVENT_CREATE_OBJECT", "EVENT_TRUNCATE", "EVENT_UNLINK"}
NETWORK_ACTIONS = {"EVENT_CONNECT": "connect", "EVENT_ACCEPT": "accept",
                   "EVENT_SENDTO": "send", "EVENT_SENDMSG": "send",
                   "EVENT_RECVFROM": "receive", "EVENT_RECVMSG": "receive",
                   "EVENT_BIND": "bind"}


def json_safe(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def executable(command):
    """Extract an image only from an unambiguous command-line first token."""
    if not isinstance(command, str) or not command.strip():
        return None
    try:
        token = shlex.split(command, posix=False)[0].strip('"')
    except (ValueError, IndexError):
        return None
    if token.lower().endswith(".exe") or token.startswith("/"):
        return token
    return None


def valid_ip(value):
    try:
        return str(ipaddress.ip_address(value)) if value else None
    except ValueError:
        return None


class EntityResolver:
    def __init__(self, db):
        self.db = db

    def get(self, host, uid):
        if not host or not uid:
            return None
        row = self.db.execute("SELECT kind,payload,conflict FROM entities WHERE host=? AND uuid=?", (host, uid)).fetchone()
        if not row or row[2]:
            return None
        return {"kind": row[0], "datum": json.loads(row[1])}

    def subject(self, host, uid, timestamp):
        chain, seen, process = [], set(), None
        reason = "missing_subject"
        while uid and uid not in seen:
            seen.add(uid)
            entity = self.get(host, uid)
            if not entity or entity["kind"] != "RECORD_SUBJECT":
                reason = "missing_or_conflicting_reference"
                break
            datum = entity["datum"]
            chain.append({"uuid": uid, "type": datum.get("type"), "cid": datum.get("cid")})
            start = datum.get("startTimestampNanos")
            if not isinstance(start, int) or start > timestamp:
                reason = "missing_or_future_start_time"
                break
            if datum.get("type") == "SUBJECT_PROCESS":
                process, reason, uid = datum, None, None
                break
            if datum.get("type") != "SUBJECT_THREAD":
                reason = "unsupported_subject_type"
                break
            uid = datum.get("parentSubject")
        if process is None and uid in seen and reason == "missing_subject":
            reason = "cyclic_subject_chain"
        return process, {"chain": chain, "unresolved_uuid": uid,
                         "process_resolved": process is not None, "reason": reason}


class CDMReviewAdapter:
    source_type = "darpa_cdm"

    def __init__(self, resolver=None):
        self.resolver = resolver

    def parse(self, raw):
        try:
            datum = raw["datum"]
            timestamp = datum["timestampNanos"]
            if raw["type"] != "RECORD_EVENT" or type(timestamp) is not int:
                raise ValueError("Expected a timestamped CDM Event")
            uid, host, action = uuid_text(datum["uuid"]), uuid_text(raw.get("hostId")), datum["type"]
            if not uid or not isinstance(action, str):
                raise ValueError("Missing Event UUID or action")
            target = self.resolver.get(host, uuid_text(datum.get("predicateObject"))) if self.resolver else None
            actor, resolution = self.resolver.subject(host, uuid_text(datum.get("subject")), timestamp) if self.resolver else (None, {"process_resolved": False, "reason": "no_entity_index"})
            fields = {"event_type": "cdm_event", "action": action}
            if actor:
                fields["process"] = executable(actor.get("cmdLine"))
            if self.resolver:
                machine = self.resolver.get(host, host)
                if machine and machine["kind"] == "RECORD_HOST":
                    fields["source_host"] = machine["datum"].get("hostName")
                principal = self.resolver.get(host, actor.get("localPrincipal")) if actor else None
                if principal and principal["kind"] == "RECORD_PRINCIPAL":
                    fields["user"] = principal["datum"].get("username")
            kind = target["kind"] if target else None
            target_data = target["datum"] if target else {}
            if action in NETWORK_ACTIONS:
                fields.update(event_type="network", action=NETWORK_ACTIONS[action])
                if action in {"EVENT_ACCEPT", "EVENT_RECVFROM", "EVENT_RECVMSG"}:
                    fields["destination_host"] = fields.pop("source_host", None)
                if kind == "RECORD_NET_FLOW_OBJECT":
                    local, remote = valid_ip(target_data.get("localAddress")), valid_ip(target_data.get("remoteAddress"))
                    # Sender and receiver orientation is explicit in CDM actions.
                    if action in {"EVENT_ACCEPT", "EVENT_RECVFROM", "EVENT_RECVMSG"}:
                        fields.update(source_ip=remote, destination_ip=local)
                    else:
                        fields.update(source_ip=local, destination_ip=remote)
            elif action in {"EVENT_LOGIN", "EVENT_LOGOUT"}:
                fields.update(event_type="authentication", action="login" if action == "EVENT_LOGIN" else "logout")
            elif action == "EVENT_CREATE_THREAD":
                fields.update(event_type="thread", action="create_thread")
            elif action in {"EVENT_FORK", "EVENT_CLONE", "EVENT_EXIT"}:
                fields.update(event_type="process", action=action.removeprefix("EVENT_").lower())
            elif action == "EVENT_EXECUTE":
                fields.update(event_type="process", action="execute", process=None)
                # Execution target differs from the process issuing the action.
                if kind == "RECORD_FILE_OBJECT":
                    fields["process"] = datum.get("predicateObjectPath") or None
            elif action in FILE_ACCESS and kind == "RECORD_FILE_OBJECT":
                mapped = {"EVENT_CLOSE": "close", "EVENT_CREATE_OBJECT": "create", "EVENT_UNLINK": "delete",
                          "EVENT_TRUNCATE": "truncate", "EVENT_MODIFY_FILE_ATTRIBUTES": "modify"}.get(action, "access")
                fields.update(event_type="file", action=mapped, file=datum.get("predicateObjectPath") or None)
            elif action in FILE_ACCESS and kind in {"RECORD_MEMORY_OBJECT", "RECORD_REGISTRY_KEY_OBJECT", "RECORD_NET_FLOW_OBJECT", "RECORD_IPC_OBJECT"}:
                category = {"RECORD_MEMORY_OBJECT": "memory", "RECORD_REGISTRY_KEY_OBJECT": "registry",
                            "RECORD_NET_FLOW_OBJECT": "network", "RECORD_IPC_OBJECT": "ipc"}[kind]
                fields.update(event_type=category, action=action.removeprefix("EVENT_").lower())
            return ParsedEvent(event_id=uid, source_type=self.source_type, timestamp_raw=utc_nanos(timestamp),
                               **fields, extra_fields={"cdm": json_safe(raw), "subject_resolution": resolution,
                                                       "predicate_kind": kind, "semantic_mapping_version": 1})
        except (KeyError, TypeError, ValueError) as error:
            return ParseError(reason=str(error), raw_event=json_safe(raw))
