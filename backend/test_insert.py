import asyncio
from core.database import get_supabase
from core.security import get_password_hash

async def test_insert():
    supabase = get_supabase()
    
    # 1. create dummy tenant
    print("insert tenant...")
    t = supabase.table("tenants").insert({
        "name": "Dummy Tenant XYZ",
        "slug": "dummy-xyz",
        "owner_email": "abcxyz@test.com",
    }).execute()
    
    t_id = t.data[0]["id"]
    print("tenant created:", t_id)
    
    # 2. create user
    print("insert user...")
    pwd = get_password_hash("password123")
    print(f"hashed: {pwd} (len: {len(pwd)})")
    
    try:
        u = supabase.table("users").insert({
            "tenant_id": t_id,
            "email": "abcxyz@test.com",
            "name": "Owner XYZ",
            "role": "owner",
            "password_hash": pwd,
            "is_active": True
        }).execute()
        print("user created:", u.data)
    except Exception as e:
        print("ERROR:", str(e))

if __name__ == "__main__":
    asyncio.run(test_insert())
