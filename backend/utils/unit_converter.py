"""
backend/utils/unit_converter.py
Konversi satuan: base unit (gram/ml/pcs) ↔ display unit (kg/liter/pcs/dll)

Aturan:
- DB selalu simpan dalam BASE UNIT (gram / ml / pcs)
- Konversi ke display HANYA saat tampil ke user
"""

from typing import Tuple


# ─── Mapping satuan → (base_unit, factor_ke_base) ─────────────────────────────

SATUAN_BERAT = {
    "kg": 1000, "ons": 100, "gram": 1, "g": 1,
}

SATUAN_CAIR = {
    "liter": 1000, "l": 1000, "ml": 1, "cc": 1,
}

SATUAN_COUNTABLE = {
    "pcs": 1, "ikat": 1, "bungkus": 1, "karung": 1,
    "tabung": 1, "buah": 1, "pack": 1, "dus": 1,
    "botol": 1, "porsi": 1, "komponen": 1,
}

ALL_UNITS = {
    **{k: ("gram", v) for k, v in SATUAN_BERAT.items()},
    **{k: ("ml", v) for k, v in SATUAN_CAIR.items()},
    **{k: ("pcs", v) for k, v in SATUAN_COUNTABLE.items()},
}


def get_base_unit(display_unit: str) -> Tuple[str, float]:
    """
    Return (base_unit, conversion_factor) dari display_unit.
    Contoh:
        'kg'    → ('gram', 1000)
        'liter' → ('ml', 1000)
        'pcs'   → ('pcs', 1)
        'ikat'  → ('pcs', 1)
    """
    unit = display_unit.lower().strip()
    result = ALL_UNITS.get(unit)
    if result:
        return result
    # Fallback: pcs × 1
    return ("pcs", 1)


def to_base(value: float, display_unit: str, factor: float = None) -> float:
    """
    Konversi nilai dari display_unit ke base_unit.
    Contoh: to_base(50, 'kg') → 50000 (gram)
    """
    if factor is not None:
        return value * factor
    _, f = get_base_unit(display_unit)
    return value * f


def to_display(base_value: float, conversion_factor: float) -> float:
    """
    Konversi dari base_unit ke display_unit.
    Contoh: to_display(50000, 1000) → 50 (kg)
    """
    if conversion_factor == 0:
        return base_value
    return base_value / conversion_factor


def format_display(
    base_value: float,
    display_unit: str,
    conversion_factor: float,
) -> str:
    """
    Format nilai untuk ditampilkan ke user.
    Contoh: format_display(50000, 'kg', 1000) → '50 kg'
            format_display(200, 'pcs', 1) → '200 pcs'
    """
    display_val = to_display(base_value, conversion_factor)
    if display_val == int(display_val):
        return f"{int(display_val)} {display_unit}"
    return f"{display_val:.2f} {display_unit}"
