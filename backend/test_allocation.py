import asyncio
from core.database import get_supabase
from models.user import UserInDB
from routers.mbg_settings import update_allocation_settings, get_allocation_settings
from models.allocation import AllocationUpdate

supabase = get_supabase()
users = supabase.table("users").select("id, tenant_id, role, email, name").eq("email", "amirulmhp3@gmail.com").limit(1).execute()
u = users.data[0]
user = UserInDB(
    id=u["id"],
    tenant_id=u["tenant_id"],
    email=u.get("email", ""),
    name=u.get("name", ""),
    role=u.get("role", "admin"),
    is_active=True
)

print(f"Testing PUT /mbg/allocation-settings for user {user.email}")
payload = AllocationUpdate(
    price_per_portion=15000,
    budget_food=10000,
    budget_labor=3000,
    budget_ops=2000
)

try:
    res = update_allocation_settings(body=payload, current_user=user)
    print("SUCCESS PUT:", res)
    
    print("Testing GET /mbg/allocation-settings")
    res_get = get_allocation_settings(current_user=user)
    print("SUCCESS GET:", res_get)
except Exception as e:
    import traceback
    if hasattr(e, "message"):
        print(f"PostgREST Error message: {e.message}")
    if hasattr(e, "json"):
        print(f"PostgREST Error dict: {e.json()}")
    if hasattr(e, "details"):
        print(f"PostgREST Error details: {e.details}")
    try:
        err_dict = dict(getattr(e, "args")[0])
        print("Raw Error Dict:", err_dict)
    except:
        pass
    traceback.print_exc()
