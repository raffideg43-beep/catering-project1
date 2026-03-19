import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Login to get token
        login_resp = await client.post("/auth/login/telegram", json={
            "telegram_id": 820614668,
            "username": "tester",
            "first_name": "Test"
        })
        if login_resp.status_code != 200:
            print(f"Login failed: {login_resp.text}")
            return
        
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Regenerate Excel
        print("Regenerating Excel...")
        reg_resp = await client.post("/reports/excel/regenerate?year=2026&month=3", headers=headers)
        print(f"Regenerate Status: {reg_resp.status_code}")
        print(f"Regenerate Response: {reg_resp.text}")
        
        if reg_resp.status_code == 200:
            url = reg_resp.json().get("data", {}).get("file_url")
            print(f"\nDownloading Excel from: {url}")
            if url:
                # Let's not download, just verifying it succeeds and returns URL
                pass

if __name__ == "__main__":
    asyncio.run(main())
