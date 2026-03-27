# Prompt Modul 21.5a: Bot Security & Role Protection (Task 1-4)

**STATUS: ✅ READY FOR AGENT** | Est. 2-3 hours | ~200 LOC  
**Priority: 1 (Start Here)**

---

## Tujuan

Implementasi RBAC (Role-Based Access Control) pada Bot Telegram MBG agar fitur sensitif (OCR, Keuangan, Stok) hanya bisa diakses Owner/Admin, sementara Driver bisa akses fitur operasional.

## KONTEKS DATABASE (Sudah Existing)

Tabel `users` di Supabase memiliki:
- `telegram_id` (bigint) — ID Telegram user
- `role` (text) — Nilai: 'owner', 'admin', 'kasir', 'viewer', 'driver'

**Note**: Role 'driver' adalah role BARU yang ditambah untuk operasional lapangan.

---

## TUGAS 1: Role Model Update

**File:** `backend/models/user.py`

TAMBAH method baru ke class `UserInDB`:

```python
def can_access_sensitive(self) -> bool:
    """Return True jika user bisa akses fitur sensitif (OCR, Keuangan, Stok)."""
    return self.role in ["owner", "admin"]

def is_driver(self) -> bool:
    """Return True jika user adalah driver."""
    return self.role == "driver"
```

---

## TUGAS 2: Bot Decorator Security

**File:** `bot/handlers/security.py` (BARU)

Buat decorator `@requires_role` untuk proteksi handler di bot:

```python
from functools import wraps
from typing import List, Callable
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.session import get_role

def requires_role(allowed_roles: List[str]):
    """
    Decorator untuk proteksi handler berdasarkan role.
    
    Usage:
        @requires_role(['owner', 'admin'])
        async def sensitive_handler(update, context):
            ...
    
    Jika role user tidak di allowed_roles:
        → Bot reply: "⛔ Akses Ditolak. Fitur ini hanya untuk [role]."
        → Return ConversationHandler.END
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
            user_role = get_role(context)  # Dari session
            
            if not user_role or user_role not in allowed_roles:
                role_names = ", ".join(allowed_roles)
                await update.message.reply_text(
                    f"⛔ Akses Ditolak.\n\n"
                    f"Fitur ini hanya untuk: {role_names}.\n"
                    f"Role kamu sekarang: {user_role or 'NOT SET'}"
                )
                return ConversationHandler.END
            
            # Role cek passed, jalankan handler
            return await func(update, context)
        
        return wrapper
    return decorator
```

---

## TUGAS 3: Proteksi Handler Existing

Cari dan update handler berikut dengan decorator `@requires_role`:

### Handler Sensitif (Hanya OWNER/ADMIN)

**File:** `bot/handlers/financial_handler.py` (atau file mana pun handler /laba, /summary ada)

```python
@requires_role(['owner', 'admin'])
async def handle_laba(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Laporan laba — hanya owner/admin"""
    pass

@requires_role(['owner', 'admin'])
async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Summary bulanan — hanya owner/admin"""
    pass
```

**File:** `bot/handlers/stok_handler.py`

```python
@requires_role(['owner', 'admin'])
async def handle_stok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Laporan stok — hanya owner/admin"""
    pass
```

**File:** `bot/handlers/nota_handler.py` (OCR)

```python
@requires_role(['owner', 'admin'])
async def handle_catat_nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Upload foto nota belanja via OCR — hanya owner/admin"""
    pass
```

### Handler Driver (Akses Operasional)

**File:** `bot/handlers/serah_handler.py`

```python
@requires_role(['driver', 'admin', 'owner'])
async def handle_serah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """BAST input — driver, admin, owner"""
    pass

@requires_role(['driver', 'admin', 'owner'])
async def handle_compliance_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Compliance check (suhu, sampel, dll) — driver + tim operasional"""
    pass
```

---

## TUGAS 4: Bot Start Handler — Linkage User

**File:** `bot/handlers/auth_handler.py` — Function `handle_start()`

Setelah user login via token, PASTIKAN sistem mengupdate `telegram_id` ke tabel users:

```python
# Saat user login berhasil via token (sudah ada di kode):
telegram_id = update.effective_user.id
token = user_token  # dari input user

api_client = get_api_client(token)
user_data = api_client.get("https://your-backend.com/auth/me")

# ✅ TAMBAH STEP INI: Update telegram_id di backend
if user_data and user_data.get("id"):
    update_resp = api_client.put(
        "https://your-backend.com/users/{user_id}/telegram",
        data={"telegram_id": telegram_id}
    )
    if not update_resp.get("success"):
        await update.message.reply_text(
            "⚠️ Link telegram gagal. Role mungkin belum terdeteksi.\n"
            "Coba /start ulang."
        )

# Session sudah disimpan dengan role (existing logic)
save_session(
    context,
    token=token,
    tenant_id=user_data.get("tenant_id"),
    user_name=user_data.get("name"),
    user_role=user_data.get("role"),  # ← INI dari /auth/me response
    telegram_id=telegram_id
)
```

---

## TUGAS 5: Backend Endpoint Update

**File:** `backend/routers/auth.py` — TAMBAH/UPDATE endpoint:

```python
@router.put("/users/{user_id}/telegram", response_model=Dict[str, Any])
def update_user_telegram(
    user_id: str,
    body: Dict[str, int],  # {"telegram_id": 123456789}
    current_user: UserInDB = Depends(get_current_user)
):
    """Update telegram_id untuk user (untuk bot linkage)."""
    supabase = get_supabase()
    
    telegram_id = body.get("telegram_id")
    if not telegram_id:
        raise HTTPException(400, detail="telegram_id tidak boleh kosong")
    
    # Update ke DB
    resp = supabase.table("users").update({
        "telegram_id": telegram_id,
        "updated_at": datetime.now().isoformat()
    }).eq("id", user_id).eq("tenant_id", current_user.tenant_id).execute()
    
    if not resp.data:
        raise HTTPException(404, detail="User tidak ditemukan")
    
    return {"success": True, "message": "Telegram ID linked", "user_id": user_id}
```

---

## TESTING CHECKLIST

- [ ] Import decorator di handler files
- [ ] Apply @requires_role ke 6 handler (4 sensitif + 2 driver)
- [ ] Test bot /start → user login → role terdeteksi
- [ ] Test user admin ketik /laba → berhasil
- [ ] Test user kasir ketik /laba → reject "⛔ Akses Ditolak"
- [ ] Test user driver ketik /serah → berhasil
- [ ] Test user driver ketik /stok → reject
- [ ] Verifikasi telegram_id ter-save di Supabase

---

## FILE STRUCTURE

```
bot/
├── handlers/
│   ├── security.py           ← BARU (decorator)
│   ├── auth_handler.py       ← UPDATE (linkage)
│   ├── financial_handler.py  ← UPDATE (@requires_role)
│   ├── stok_handler.py       ← UPDATE (@requires_role)
│   ├── nota_handler.py       ← UPDATE (@requires_role)
│   └── serah_handler.py      ← UPDATE (@requires_role untuk driver)

backend/
└── routers/
    └── auth.py               ← UPDATE (PUT endpoint)
    
backend/
└── models/
    └── user.py               ← UPDATE (new methods)
```

---

## GIT COMMIT

```bash
git add bot/handlers/security.py bot/handlers/*.py backend/routers/auth.py backend/models/user.py
git commit -m "feat: bot security RBAC + role-based handler protection (Modul 21.5a)"
```

---

## OUTPUT EXPECTATIONS

✅ Bot sekarang punya 3-layer security:
1. Token-based auth di web/bot start
2. Session role tracking
3. Handler-level decorator protection

✅ Audit trail clear: tiap command keliatan siapa yang execute
✅ Driver bisa kerja operasional tanpa akses data sensitif
