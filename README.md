# TraceGraph 🛡️

> **AI-Assisted, Graph-Based Security Investigation Platform for SOC Incident Reconstruction**

TraceGraph is a modern security investigation workspace designed for Security Operations Center (SOC) analysts and incident responders. It ingests multi-source security telemetry (Sysmon, EDR, SIEM, Auth, Network logs), automatically extracts entities and temporal correlations, builds an interactive graph of attacker movement, and generates grounded AI incident narratives.

---

## 🌟 Key Features

* **Interactive Entity Graph**: Visualizes relationships between Users, Hosts, IPs, Processes, and Files using Cytoscape.js with force-directed layouts.
* **Chronological Event Timeline**: Filterable event stream categorized by threat level, event type (`Auth`, `Process`, `Network`, `File`), and cross-linked entity highlights.
* **Multi-Source Ingestion Pipeline**: Parsers and normalizers for Sysmon, EDR, SIEM, Authentication, and Network traffic.
* **Dual-Database Architecture**: 
  * **PostgreSQL** for relational event logs, investigations, and audit trails.
  * **Neo4j** for graph entity topology and fast multi-hop relationship traversal.
* **AI-Assisted Incident Summaries**: Grounded LLM narrative generation summarizing key compromise milestones, lateral movement vectors, and evidence references.
* **Out-of-the-Box Demo Seeding**: Automatically seeds realistic APT-29 compromise data on initial startup so developers and analysts can immediately test the workspace.

---

## 🏗️ Architecture

```
                       +------------------------+
                       |   React + Vite UI      |
                       |  (Port 5173 / Nginx)   |
                       +-----------+------------+
                                   |
                                   v  (REST API / JWT)
                       +-----------+------------+
                       |   FastAPI Backend      |
                       |      (Port 8000)       |
                       +-----+------------+-----+
                             |            |
           (SQLAlchemy /     |            |  (Bolt / Async
            Asyncpg)         v            v   Neo4j Driver)
                   +---------+--+      +--+---------+
                   | PostgreSQL |      |   Neo4j    |
                   | (Port 5432)|      | (Port 7687)|
                   +------------+      +------------+
```

---

## 🚀 Quick Start (Docker - Recommended)

The fastest way to get TraceGraph up and running is using Docker Compose.

### 1. Clone & Start Containers
```bash
git clone https://github.com/kaustubhvanshiv/tracegraph.git
cd tracegraph

# Build and start all 4 services (Postgres, Neo4j, Backend, Frontend)
docker compose up -d --build
```

### 2. Access the Application
* **Frontend Workspace**: [http://localhost:5173](http://localhost:5173)
* **Backend REST API**: [http://localhost:8000](http://localhost:8000)
* **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Neo4j Browser**: [http://localhost:7474](http://localhost:7474)

### 3. Demo Credentials
* **User**: `analyst@tracegraph.io` (or `pramit.0904@gmail.com`)
* **Password**: `password123`

---

## 🌱 Automated Test Data Seeding

On startup, TraceGraph automatically detects if the database is empty and pre-loads a complete **APT-29 Lateral Movement & Privilege Escalation** investigation containing:

* **14 Entity Graph Nodes**: Hosts (`WS-FIN-01`, `DC-01`, `FILE-SERVER-02`), Users (`jsmith`, `Administrator`, `NT AUTHORITY\SYSTEM`), Processes (`cmd.exe`, `powershell.exe`, `rundll32.exe`), Files (`lsass_dump.dmp`), and IPs.
* **10 Security Events**: Sysmon process executions, Kerberos/NTLM logins, HTTPS C2 beaconing, SMB share accesses, and LSASS credential dumping detections.

To manually trigger or reset demo data at any time:
```bash
docker compose exec backend python seed_demo_data.py
```

---

## 💻 Local Terminal Development

If you want to run the backend and frontend directly in your local terminal for hot-reloading:

### Step 1: Start Databases in Docker
```bash
docker compose up -d postgres neo4j
```

### Step 2: Run Backend (Python 3.11+)
```bash
cd backend

# Create & activate virtualenv
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Start Uvicorn dev server
python -m uvicorn app.main:app --reload --port 8000
```

### Step 3: Run Frontend (Node.js 18+)
```bash
cd frontend

# Install dependencies & run Vite dev server
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Testing & Quality Assurance

### Run Backend Test Suite (Pytest)
```bash
cd backend
pytest tests/unit tests/property
```
> Evaluates **276 unit and property-based tests** covering ingestion parsing, entity normalization, temporal correlation algorithms, JWT auth isolation, and AI summary context generation.

### Run Frontend Typecheck & Build
```bash
cd frontend
npm run build
```

---

## 📑 API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/token` | Issue signed JWT access token |
| `GET` | `/health/ready` | Liveness & database readiness health probes |
| `GET/POST` | `/api/investigations` | List or create security investigations |
| `GET` | `/api/investigations/{id}` | Retrieve single investigation details |
| `POST` | `/api/investigations/{id}/events/batch` | Ingest raw telemetry batch (Sysmon, EDR, Auth, Network) |
| `GET` | `/api/investigations/{id}/graph` | Fetch Cytoscape entity graph (nodes & edges) |
| `GET` | `/api/investigations/{id}/timeline` | Fetch chronological security event stream |
| `GET/POST` | `/api/investigations/{id}/summary` | Retrieve or generate grounded AI narrative summary |

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for details.
