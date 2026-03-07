import asyncio
from core.database import get_supabase
from core.security import verify_token
from models.user import UserInDB
from fastapi.security import HTTPAuthorizationCredentials

from jose import jwt
from datetime import datetime, timedelta, timezone
from core.config import settings

secret = settings.secret_key
algo = settings.algorithm
supabase = get_supabase()

users = supabase.table("users").select("id, tenant_id, role, email").limit(1).execute()
user = users.data[0]

to_encode = {
    "user_id": str(user["id"]),
    "email": user["email"],
    "role": user["role"],
    "tenant_id": user["tenant_id"],
    "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
}
token = jwt.encode(to_encode, secret, algorithm=algo)

print("Mencoba verify_token...")
try:
    payload = verify_token(token)
    user_id = payload.get("user_id")
    print(f"Token valid. user_id: {user_id}")
    
    print("Mencari user di database...")
    response = supabase.table("users").select("*").eq("id", user_id).single().execute()
    user_data = getattr(response, "data", None)
    
    if not user_data:
        print("User not found!")
    else:
        print("User ditemukan, parsing ke UserInDB...")
        try:
            u = UserInDB(**user_data)
            print("OK, model valid!")
        except Exception as ex:
            with open("error_deps.log", "w", encoding="utf-8") as f:
                f.write(f"ERROR: {str(ex)}\n\nRAW DATA: {user_data}")
            print("Error tertulis di error_deps.log")
except Exception as e:
    import traceback
    traceback.print_exc()

