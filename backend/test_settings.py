import asyncio
from core.database import get_supabase
from models.user import UserInDB
from routers.tenants import update_tenant
from models.tenant import TenantUpdate

supabase = get_supabase()
users = supabase.table("users").select("id, tenant_id, role, email, name").eq("email", "amirulmhp3@gmail.com").limit(1).execute()
if not users.data:
    users = supabase.table("users").select("*").limit(1).execute()

u = users.data[0]
user = UserInDB(
    id=u["id"],
    tenant_id=u["tenant_id"],
    email=u.get("email", ""),
    name=u.get("name", ""),
    role=u.get("role", "admin"),
    is_active=True
)

print(f"Testing PUT /tenants/me for user {user.email}")
try:
    payload = TenantUpdate(
        name="telur SPPG",
        contact_name="Amirul",
        phone="0857242623",
        address="Jalan Merdeka",
        business_type="catering",
        sppg_code="SPPG-01"
    )
    res = update_tenant(body=payload, current_user=user)
    print("SUCCESS PUT TENANT:", res)
except Exception as e:
    import traceback
    traceback.print_exc()

print("-" * 50)
from routers.schools import create_school
from models.school import SchoolCreate

print(f"Testing POST /schools for user {user.email}")
try:
    payload_school = SchoolCreate(
        name="SDN 1 Telur",
        contact_person="Bapak Budi",
        default_portions=50,
        address="Jalan Telur 1"
    )
    res_school = create_school(school=payload_school, current_user=user)
    print("SUCCESS POST SCHOOL:", res_school)
except Exception as e:
    import traceback
    traceback.print_exc()
