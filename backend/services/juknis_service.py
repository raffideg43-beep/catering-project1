"""
backend/services/juknis_service.py
Auto-kategorisasi juknis MBG berdasarkan keyword item belanja.
Fallback ke Gemini jika tidak ada keyword match.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

KEYWORD_MAP = {
    "bahan_pangan": [
        "beras", "ayam", "daging", "ikan",
        "telur", "tahu", "tempe", "sayur",
        "buah", "minyak", "tepung", "gula",
        "garam", "bumbu", "santan", "susu",
        "pisang", "wortel", "bayam", "kol",
        "kentang", "bawang", "cabai", "cabe",
        "tomat", "sarden", "kornet", "keju",
        "mentega", "margarin", "kecap", "saos",
        "sambal", "terasi", "kelapa", "jagung",
        "udang", "cumi", "tuna", "lele",
        "nila", "bandeng", "patin", "tongkol",
        "sosis", "nugget", "bakso", "mie",
        "makaroni", "pasta", "roti", "selai",
    ],
    "operasional": [
        "gas", "lpg", "listrik", "bensin",
        "solar", "bbm", "sewa", "plastik",
        "kemasan", "kardus", "sabun", "tissue",
        "deterjen", "tisu", "sarung tangan",
        "masker", "air galon", "transportasi",
        "galon", "tabung", "elpiji", "styrofoam",
        "aluminium foil", "plastik wrap",
        "tusuk gigi", "sedotan", "sendok",
    ],
    "insentif": [
        "upah", "gaji", "honor", "insentif",
        "transport", "uang makan", "ongkos",
        "tunjangan", "lembur", "bonus",
    ],
}


def auto_categorize(
    items: List[str],
    tenant_id: Optional[str] = None,
) -> str:
    """
    Kategorisasi otomatis berdasarkan keyword.
    Return juknis_category string.

    Prioritas: keyword match → 'bahan_pangan' fallback.
    Gemini fallback bisa ditambahkan di masa depan.
    """
    if not items:
        return "bahan_pangan"

    combined = " ".join(items).lower()

    for category, keywords in KEYWORD_MAP.items():
        if any(kw in combined for kw in keywords):
            return category

    # Default: bahan_pangan (most common for SPPG)
    logger.info(f"Juknis auto-categorize fallback to bahan_pangan for items: {items[:3]}")
    return "bahan_pangan"


def get_category_label(category: str) -> str:
    """Return human-readable label for juknis category."""
    labels = {
        "bahan_pangan": "Bahan Pangan",
        "operasional": "Operasional",
        "insentif": "Insentif",
        "dana_masuk": "Dana Masuk",
        "lainnya": "Lainnya",
    }
    return labels.get(category, category or "—")
