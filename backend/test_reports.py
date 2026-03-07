import asyncio
from datetime import date
from core.database import get_supabase
from models.user import UserInDB
from routers.reports import get_monthly_report, get_daily_report

supabase = get_supabase()
users = supabase.table("users").select("id, tenant_id, role, email, name").eq("email", "amirulmhp3@gmail.com").limit(1).execute()
if not users.data:
    users = supabase.table("users").select("id, tenant_id, role, email, name").neq("email", "owner@uji-coba.local").limit(1).execute()

u = users.data[0]
user = UserInDB(
    id=u["id"],
    tenant_id=u["tenant_id"],
    email=u["email"],
    name=u["name"],
    role=u["role"],
    is_active=True
)

print(f"Testing reports for {user.email}...")

print("\n--- Testing get_monthly_report ---")
try:
    res = get_monthly_report(year=2026, month=3, current_user=user)
    print("Success monthly!")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\n--- Testing get_daily_report ---")
try:
    res = get_daily_report(date_param=None, current_user=user)
    print("Success daily!")
except Exception as e:
    import traceback
    traceback.print_exc()
