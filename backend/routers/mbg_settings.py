"""
MBG settings and allocation management.
"""

from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.user import UserInDB

router = APIRouter(prefix="/mbg", tags=["mbg"])


@router.get("/allocation-settings", response_model=Dict[str, Any])
def get_allocation_settings(current_user: UserInDB = Depends(get_current_user)):
    """Get current MBG allocation settings."""
    supabase = get_supabase()

    response = (
        supabase.table("mbg_allocation_settings")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .order("effective_date", desc=True)
        .limit(1)
        .execute()
    )

    data = getattr(response, "data", None) or []
    if not data:
        # Return default allocation
        defaults = {
            "price_per_portion": 15000,
            "food_per_portion": 10000,
            "labor_per_portion": 2250,
            "ops_per_portion": 2750,
        }
        return {"success": True, "data": defaults}

    return {"success": True, "data": data[0]}


@router.put("/allocation-settings", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner"]))])
def update_allocation_settings(
    body: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_user),
):
    """Update MBG allocation settings."""
    supabase = get_supabase()

    insert_data = {
        "tenant_id": current_user.tenant_id,
        "price_per_portion": Decimal(str(body.get("price_per_portion", 15000))),
        "food_per_portion": Decimal(str(body.get("food_per_portion", 10000))),
        "labor_per_portion": Decimal(str(body.get("labor_per_portion", 2250))),
        "ops_per_portion": Decimal(str(body.get("ops_per_portion", 2750))),
        "effective_date": body.get("effective_date", "TODAY"),
        "notes": body.get("notes"),
    }

    response = supabase.table("mbg_allocation_settings").insert(insert_data).execute()

    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update allocation settings",
        )

    return {"success": True, "data": data[0]}
