import asyncio
from app.core.database import SessionLocal, get_neo4j_driver
from app.services.ingestion import IngestionService

async def main():
    async with SessionLocal() as db:
        # Get Neo4j driver
        # We need to manually initialize it since get_neo4j_driver is a dependency generator
        # Wait, get_neo4j_driver is an async generator:
        gen = get_neo4j_driver()
        neo4j_driver = await gen.__anext__()
        
        try:
            svc = IngestionService(db=db, neo4j_driver=neo4j_driver)
            
            raw_event = {
                "event_simpleName": "ProcessRollup2",
                "timestamp": "2026-10-01T00:00:00Z",
                "UserSid": "S-1-5-21",
                "SHA256HashData": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "FileName": "malware.exe",
                "CommandLine": "malware.exe --stealth"
            }
            
            # The investigation ID from the user
            inv_id = "49488d13-7fa6-4778-9f02-e62600e577cc"
            
            result = await svc.process_event_batch(
                raw_events=[raw_event],
                investigation_id=inv_id,
                source_type="crowdstrike"
            )
            
            print(f"Accepted: {result.accepted}")
            print(f"Rejected: {result.rejected}")
            if result.errors:
                print(f"Errors: {result.errors}")
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(main())
