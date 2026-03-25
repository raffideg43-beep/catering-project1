"""
backend/services/ocr_service.py
OCR nota via Google Gemini 1.5 Flash Vision — Modul 7

Alur:
  1. Download foto dari URL (Supabase Storage atau URL publik)
  2. Encode ke base64
  3. Kirim ke Gemini Vision dengan prompt MASTER_PLAN
  4. Parse JSON response
  5. Return dict atau None jika gagal
"""

import base64
import json
import logging
import re
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# Prompt OCR persis seperti di MASTER_PLAN v1.7
OCR_PROMPT = """Ekstrak SEMUA data dari foto nota/struk belanja ini.
Return HANYA JSON valid tanpa teks lain:
{
  "nama_toko": "nama toko asli dari nota atau null",
  "alamat_toko": "alamat toko jika ada atau null",
  "no_telp_toko": "nomor telepon toko jika ada atau null",
  "tanggal": "YYYY-MM-DD atau null",
  "no_nota": "nomor faktur/struk atau null",
  "kasir": "nama kasir jika ada atau null",
  "is_pkp": false,
  "payment_method": "tunai/transfer/hutang atau null",
  "payment_status": "lunas/belum_lunas/cicil atau null",
  "due_date": "YYYY-MM-DD atau null",
  "items": [
    {
      "nama_item": "nama PERSIS seperti di nota",
      "qty": 1.0,
      "satuan": "kg/liter/pcs/gram/ikat/buah/pack/dus/dll",
      "harga_satuan": 0,
      "subtotal": 0,
      "has_ppn": false,
      "kategori": "bahan_pangan/kemasan/operasional/alat_tulis/lainnya"
    }
  ],
  "subtotal_nota": 0,
  "diskon": 0,
  "total": 0,
  "catatan": null,
  "ocr_confidence": 0.95,
  "unclear_items": []
}

Aturan wajib:
- Harga angka bulat tanpa titik/koma ribuan (12000 bukan 12.000)
- nama_item: PERSIS seperti di nota, jangan terjemahkan
- harga_satuan: jika tidak ada di nota, hitung: subtotal / qty
- is_pkp: true jika ada NPWP/Faktur Pajak/nomor FP di nota
- ocr_confidence: 0.0-1.0, turunkan jika foto buram/miring/terpotong
- unclear_items: nama item yang tidak terbaca jelas
- Field tidak ada di nota: isi null, JANGAN tebak atau karang"""


class OCRService:
    """
    Service untuk ekstrak data nota via Google Gemini 1.5 Flash Vision.
    Digunakan oleh ocr_worker (sync context).
    """

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_ocr_model
        self.api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def extract_from_bytes(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> Optional[dict]:
        """
        Kirim bytes gambar ke Gemini Vision, return parsed dict atau None.
        Sync (non-async) karena dipanggil dari RQ worker.
        """
        if not self.api_key:
            logger.error("GEMINI_API_KEY tidak dikonfigurasi")
            return None

        b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": OCR_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192,
            },
        }

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(self.api_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

        try:
            text = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )
            # Strip markdown code fences jika ada
            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*", "", text)
            return json.loads(text.strip())
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            logger.error(f"OCR parse error: {e} | raw: {data}")
            return None

    def extract_from_url(self, photo_url: str) -> Optional[dict]:
        """
        Download foto dari URL lalu extract. Sync.
        """
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(photo_url)
                resp.raise_for_status()
                image_bytes = resp.content
                mime_type = resp.headers.get("content-type", "image/jpeg")
        except Exception as e:
            logger.error(f"Download foto gagal: {e}")
            return None

        return self.extract_from_bytes(image_bytes, mime_type)


ocr_service = OCRService()
