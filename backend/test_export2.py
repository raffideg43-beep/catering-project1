import json
import logging
import sys
from _decimal import Decimal
sys.path.append("backend")

from core.database import get_supabase
from core.config import settings

def main():
    supabase = get_supabase()
    t_resp = supabase.table("tenants").select("id").limit(1).execute()
    tenant_id = t_resp.data[0]["id"]
    print(f"Tenant ID: {tenant_id}")
    
    from datetime import date
    first = date(2026, 3, 1)
    last = date(2026, 3, 31)

    print("Fetching deliveries...")
    del_resp = (
        supabase.table("mbg_deliveries")
        .select("*, schools(name)")
        .eq("tenant_id", tenant_id)
        .gte("delivery_date", str(first))
        .lte("delivery_date", str(last))
        .execute()
    )
    print("Deliveries:", len(del_resp.data))
    
    print("Fetching transactions...")
    trx_resp = (
        supabase.table("transactions")
        .select("id, date, suppliers(name), supplier_id, total, status")
        .eq("tenant_id", tenant_id)
        .eq("type", "expense")
        .eq("status", "confirmed")
        .gte("date", str(first))
        .lte("date", str(last))
        .execute()
    )
    print("Transactions:", len(trx_resp.data))

if __name__ == "__main__":
    main()
