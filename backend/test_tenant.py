import asyncio
from core.database import get_supabase
from models.user import UserInDB
from routers.tenants import update_tenant
from models.tenant import TenantUpdate

supabase = get_supabase()
# Get main user
users = supabase.table("users").select("id, tenant_id, role, email, name").eq("email", "amirulmhp3@gmail.com").limit(1).execute()
if not users.data:
    users = supabase.table("users").select("*").limit(1).execute()

u = users.data[0]
user = UserInDB(
    id=u["id"],
    tenant_id=u["tenant_id"],
    email=u.get("email", ""),
    name=u.get("name", ""),
    role="owner",
    is_active=True
)

update_body = TenantUpdate(
    contact_name="Supriyadi - Developer Testing"
)

print(f"Testing PUT /tenants/me for user {user.email} with tenant {user.tenant_id}...")

try:
    res = update_tenant(body=update_body, current_user=user)
    print("SUCCESS: ", res)
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
