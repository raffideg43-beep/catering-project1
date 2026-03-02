from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers import auth as auth_router

app = FastAPI(title="MBG Catering Backend", version="1.0.0")

origins = [
    settings.web_url,
    "http://localhost:3000",
    "https://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    # Mengikuti spesifikasi modul: response sederhana tanpa wrapper.
    return {"status": "ok", "version": "1.0.0"}


app.include_router(auth_router.router)


