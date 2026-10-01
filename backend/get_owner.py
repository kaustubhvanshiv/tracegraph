import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.investigation import InvestigationModel

async def main():
    async with AsyncSessionLocal() as db:
        stmt = select(InvestigationModel).where(InvestigationModel.investigation_id == "49488d13-7fa6-4778-9f02-e62600e577cc")
        result = await db.execute(stmt)
        inv = result.scalar_one_or_none()
        if inv:
            print(f"Owner: {inv.owner_id}")
        else:
            print("Investigation not found")

if __name__ == "__main__":
    asyncio.run(main())
