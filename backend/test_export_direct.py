import asyncio
import os
import sys

from datetime import date
sys.path.append("backend")

from core.database import get_supabase
from core.config import settings

async def force_generate():
    from services.export_service import ExportService
    supabase = get_supabase()
    
    # get first tenant
    t_resp = supabase.table("tenants").select("id").limit(1).execute()
    tenant_id = t_resp.data[0]["id"]
    print(f"Using Tenant: {tenant_id}")
    
    svc = ExportService()
    
    # 1. Manually fetch and print counts
    print("Fetching data...")
    data = svc._fetch_all(supabase, tenant_id, 2026, 3, settings)
    print(f"Deliveries: {len(data['deliveries'])}")
    print(f"Transactions: {len(data['transactions'])}")
    
    # 2. Force generate
    print("Generating Excel...")
    url = await svc.regenerate_monthly_excel(tenant_id, 2026, 3, supabase)
    print(f"Result URL: {url}")

if __name__ == "__main__":
    asyncio.run(force_generate())
