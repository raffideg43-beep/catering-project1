
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.database import get_supabase
from services.budget_service import budget_service

async def verify():
    # Use the tenant_id from the logs
    tenant_id = "d6014971-0d73-41a0-9319-dcf48e13a2d0"
    year = 2026
    month = 3
    
    print(f"Verifying Budget Summary for {year}-{month}...")
    summary = budget_service.get_monthly_summary(tenant_id, year, month)
    
    print("\n--- Juknis Breakdown ---")
    for key, data in summary["juknis_breakdown"].items():
        print(f"{data['label']}:")
        print(f"  Target: {data['target']}")
        print(f"  Realisasi: {data['realisasi']}")
        print(f"  Pct: {data['pct']}%")

    print("\n--- Totals ---")
    print(f"Total Spent: {summary['total_spent']}")
    print(f"Sisa Anggaran: {summary['sisa_anggaran']}")

if __name__ == "__main__":
    asyncio.run(verify())
