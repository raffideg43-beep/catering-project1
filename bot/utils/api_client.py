"""
HTTP client untuk komunikasi dengan FastAPI backend.
"""

import httpx


class APIClient:
    """
    Async HTTP client untuk FastAPI backend.

    Usage:
        api_client = APIClient("http://localhost:8000")
        user = await api_client.get("/auth/me", token="xyz")
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.timeout = 30

    def _build_headers(self, token: str | None = None) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def get(
        self,
        endpoint: str,
        token: str | None = None,
        params: dict | None = None,
    ) -> dict:
        """GET request ke backend."""
        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers(token)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Request timeout — backend tidak merespons")
        except httpx.HTTPStatusError as e:
            error_msg = "Unknown error"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", error_data.get("detail", str(e)))
            except Exception:
                error_msg = str(e)
            raise Exception(f"Backend error: {error_msg}")
        except Exception as e:
            raise Exception(f"Request error: {str(e)}")

    async def post(
        self,
        endpoint: str,
        data: dict | None = None,
        token: str | None = None,
        files: dict | None = None,
    ) -> dict:
        """POST request ke backend."""
        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers(token)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if files:
                    # Jika ada file, gunakan multipart form
                    response = await client.post(
                        url,
                        headers={"Authorization": headers.get("Authorization", "")},
                        data=data,
                        files=files,
                    )
                else:
                    response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Request timeout — backend tidak merespons")
        except httpx.HTTPStatusError as e:
            error_msg = "Unknown error"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", error_data.get("detail", str(e)))
            except Exception:
                error_msg = str(e)
            raise Exception(f"Backend error: {error_msg}")
        except Exception as e:
            raise Exception(f"Request error: {str(e)}")

    async def put(
        self,
        endpoint: str,
        data: dict | None = None,
        token: str | None = None,
    ) -> dict:
        """PUT request ke backend."""
        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers(token)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(url, headers=headers, json=data)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Request timeout — backend tidak merespons")
        except httpx.HTTPStatusError as e:
            error_msg = "Unknown error"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", error_data.get("detail", str(e)))
            except Exception:
                error_msg = str(e)
            raise Exception(f"Backend error: {error_msg}")
        except Exception as e:
            raise Exception(f"Request error: {str(e)}")


    async def delete(
        self,
        endpoint: str,
        token: str | None = None,
    ) -> dict:
        """DELETE request ke backend."""
        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers(token)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Request timeout — backend tidak merespons")
        except httpx.HTTPStatusError as e:
            error_msg = "Unknown error"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", error_data.get("detail", str(e)))
            except Exception:
                error_msg = str(e)
            raise Exception(f"Backend error: {error_msg}")
        except Exception as e:
            raise Exception(f"Request error: {str(e)}")


# Singleton instance
def get_api_client(base_url: str) -> APIClient:
    """Factory untuk membuat API client."""
    return APIClient(base_url)
