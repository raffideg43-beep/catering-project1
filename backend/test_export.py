import asyncio
import json
import logging
import sys
from _decimal import Decimal
sys.path.append("backend")

from core.database import get_supabase
from core.config import settings
from services.export_service import ExportService

logging.basicConfig(level=logging.INFO)

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        from datetime import date, datetime
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)

async def main():
    supabase = get_supabase()
    
    # Get tenant ID
    t_resp = supabase.table("tenants").select("id").limit(1).execute()
    tenant_id = t_resp.data[0]["id"]
    
    print(f"Tenant ID: {tenant_id}")
    
    svc = ExportService()
    
    try:
        data = svc._fetch_all(supabase, tenant_id, 2026, 3, settings)
        
        print(f"Deliveries count: {len(data['deliveries'])}")
        print(f"Transactions count: {len(data['transactions'])}")
        print(f"Items count: {len(data['items_all'])}")
        
        # Test just the transactions query manually
        from datetime import date, timedelta
        first = date(2026, 3, 1)
        last = date(2026, 3, 31)
        
        trx_resp = (
            supabase.table("transactions")
            .select("id, date, suppliers(name), supplier_id, total, payment_method, status")
            .eq("tenant_id", tenant_id)
            .eq("type", "expense")
            .eq("status", "confirmed")
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .order("date")
            .execute()
        )
        print("Manual transactions fetch:", json.dumps(trx_resp.data, cls=DecimalEncoder, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
