import asyncio
import json
import uuid
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncGraphDatabase

from app.main import app
from app.core.config import settings

pytestmark = pytest.mark.asyncio

@pytest.fixture
def auth_headers():
    from jose import jwt
    token = jwt.encode({"sub": "test_owner"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}

async def test_evaluation_scenarios(auth_headers):
    inv_id = str(uuid.uuid4())
    
    # 1. Ingest Dataset
    fixture_path = Path(__file__).parent.parent / "fixtures" / "eval_dataset.json"
    with open(fixture_path, "r") as f:
        events = json.load(f)
        
    payload = {
        "source_type": "crowdstrike",
        "events": [e["raw"] for e in events]
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/investigations", json={"id": inv_id, "title": "Eval"}, headers=auth_headers)
        assert resp.status_code == 200
        
        resp = await ac.post(f"/api/investigations/{inv_id}/events/batch", json=payload, headers=auth_headers)
        assert resp.status_code == 202
        assert resp.json()["accepted"] == len(events)
        
    # 2. Assert Graph state in Neo4j directly
    driver = AsyncGraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    
    async with driver.session() as session:
        # Assertion 1: Admin user accessed DESKTOP-1
        res = await session.run(
            "MATCH (u:User)-[r:ACCESSED]->(h:Host {id: 'DESKTOP-1'}) WHERE r.investigation_id = $inv_id RETURN count(r)",
            inv_id=inv_id
        )
        count1 = (await res.single())[0]
        assert count1 > 0, "Admin user did not access DESKTOP-1"
        
        # Assertion 2: Lateral movement (DESKTOP-1 -> SERVER-1)
        res = await session.run(
            "MATCH (h1:Host {id: 'DESKTOP-1'})-[r:CONNECTED_TO]->(h2:Host {id: 'SERVER-1'}) WHERE r.investigation_id = $inv_id RETURN count(r)",
            inv_id=inv_id
        )
        count2 = (await res.single())[0]
        assert count2 > 0, "Lateral movement not detected"
        
        # Assertion 3: Exfiltration staging (rar.exe on SERVER-1)
        res = await session.run(
            "MATCH (h:Host {id: 'SERVER-1'})<-[:EXECUTED_ON]-(p:Process) WHERE p.name = 'rar.exe' RETURN count(p)"
        )
        count3 = (await res.single())[0]
        assert count3 > 0, "Exfiltration process not detected"
        
        # Assertion 4: Connection to suspicious IP
        res = await session.run(
            "MATCH (h:Host)-[:CONNECTED_TO]->(ip:IpAddress {id: '203.0.113.50'}) RETURN count(h)"
        )
        count4 = (await res.single())[0]
        assert count4 >= 2, "Suspicious IP connection not detected from both hosts"

        # Assertion 5: Temporal Correlation generated combined score > 0
        res = await session.run(
            "MATCH ()-[r:CONNECTED_TO]->() WHERE r.combined_score > 0 RETURN count(r)"
        )
        count5 = (await res.single())[0]
        assert count5 > 0, "Temporal correlation did not enrich relationships"

    await driver.close()
