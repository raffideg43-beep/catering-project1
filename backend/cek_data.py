import asyncio
import sys
sys.path.append("backend")

from core.database import get_supabase
from core.config import settings

def cek_data():
    supabase = get_supabase()
    
    # Get first tenant
    t_resp = supabase.table("tenants").select("id").limit(1).execute()
    if not getattr(t_resp, "data", []):
        print("No tenants found!")
        return
    tenant_id = t_resp.data[0]["id"]
    print(f"Tenant ID: {tenant_id}")
    
    first = "2026-03-01"
    last = "2026-03-31"
    
    # 1. Cek table transactions
    print("\n--- TRANSACTIONS (2026-03) ---")
    trx_resp = (
        supabase.table("transactions")
        .select("status")
        .eq("tenant_id", tenant_id)
        .gte("date", first)
        .lte("date", last)
        .execute()
    )
    trx_data = getattr(trx_resp, "data", [])
    grouped = {}
    for d in trx_data:
        st = d.get("status", "unknown")
        grouped[st] = grouped.get(st, 0) + 1
    if not grouped:
        print("0 transactions found.")
    for st, count in grouped.items():
        print(f"Status '{st}': {count} rows")
        
    # 2. Cek table mbg_deliveries
    print("\n--- MBG DELIVERIES (2026-03) ---")
    del_resp = (
        supabase.table("mbg_deliveries")
        .select("id")
        .eq("tenant_id", tenant_id)
        .gte("delivery_date", first)
        .lte("delivery_date", last)
        .execute()
    )
    del_data = getattr(del_resp, "data", [])
    print(f"Total deliveries: {len(del_data)} rows")

if __name__ == "__main__":
    cek_data()
