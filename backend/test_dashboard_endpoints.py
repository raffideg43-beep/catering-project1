import httpx
from jose import jwt
from datetime import datetime, timedelta, timezone

from core.config import settings

# 1. Generate local token
secret = settings.secret_key
algo = settings.algorithm

# Kita butuh tenant ID dan sub. Mengambil user valid.
from core.database import get_supabase
supabase = get_supabase()
users = supabase.table("users").select("id, tenant_id, role, email").eq("email", "amirulmhp3@gmail.com").limit(1).execute()
if not users.data:
    users = supabase.table("users").select("id, tenant_id, role, email").neq("email", "owner@uji-coba.local").limit(1).execute()

user = users.data[0] if users.data else None

if not user:
    print("Tidak ada user di database!")
    exit(1)

to_encode = {
    "user_id": str(user["id"]),
    "email": user["email"],
    "role": user["role"],
    "tenant_id": user["tenant_id"],
    "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
}
token = jwt.encode(to_encode, secret, algorithm=algo)

print(f"Menggunakan user {user['email']} (Tenant: {user['tenant_id']})")

headers = {
    "Authorization": f"Bearer {token}"
}

endpoints = [
    "/reports/daily",
    "/reports/monthly",
    "/transactions?limit=10&sort=created_at_desc",
    "/auth/me"
]

base_url = "http://localhost:8000"

for ep in endpoints:
    url = f"{base_url}{ep}"
    try:
        r = httpx.get(url, headers=headers)
        if r.status_code != 200:
            print(f"FAILED {ep} => ERROR {r.status_code}: {r.text}")
        else:
            print(f"PASS {ep} => OK")
    except Exception as e:
        print(f"FAILED {ep} => GAGAL REQUEST: {e}")
