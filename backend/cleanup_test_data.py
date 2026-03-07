"""
Script untuk menghapus data test yang dibuat saat debugging.
Jalankan sekali: python cleanup_test_data.py
"""
from core.database import get_supabase

def cleanup():
    supabase = get_supabase()

    # Email-email yang dibuat saat testing
    test_emails = [
        "test@test.com", "test2@test.com", "test3@test.com",
        "test4@test.com", "test5@test.com",
        "abcxyz@test.com",
        "pramanaraffi68@gmail.com",  # jika sudah terdaftar dari percobaan sebelumnya
    ]

    # Slug-slug test
    test_slugs = [
        "test-sppg", "test-sppg2", "test-sppg3", "test-sppg4", "test-sppg5",
        "dummy-xyz", "telur-asin-asax", "ikan-asonn",
    ]

    print("=== Cleanup Test Data ===")

    # Hapus users dulu (karena ada FK ke tenants)
    for email in test_emails:
        r = supabase.table("users").delete().eq("email", email).execute()
        deleted = r.data or []
        if deleted:
            print(f"  ✅ Deleted user: {email}")
        else:
            print(f"  — User not found: {email}")

    # Hapus tenants
    for slug in test_slugs:
        r = supabase.table("tenants").delete().eq("slug", slug).execute()
        deleted = r.data or []
        if deleted:
            print(f"  ✅ Deleted tenant slug: {slug}")
        else:
            print(f"  — Tenant not found: {slug}")

    print("\nDone!")

if __name__ == "__main__":
    cleanup()
