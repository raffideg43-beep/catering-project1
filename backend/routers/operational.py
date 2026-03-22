"""
Operational costs endpoints.
"""

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.hr import OperationalCostCreate
from models.user import UserInDB

router = APIRouter(prefix="/operational", tags=["financial"])


@router.get("", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def get_operational_costs(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2100),
    current_user: UserInDB = Depends(get_current_user),
):
    """Get operational costs for a specific month."""
    supabase = get_supabase()

    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year

    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    response = (
        supabase.table("operational_costs")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .gte("cost_date", start_date.isoformat())
        .lt("cost_date", end_date.isoformat())
        .order("cost_date", desc=True)
        .execute()
    )
    items = getattr(response, "data", None) or []

    # Calculate summaries
    total = sum(item.get("amount", 0) for item in items)
    
    by_category = {
        "Listrik": 0,
        "Gas LPG": 0,
        "BBM": 0,
        "Sewa": 0,
        "Lainnya": 0
    }
    
    recurring = []
    
    for item in items:
        amt = item.get("amount", 0)
        cat = item.get("name", "Lainnya")
        
        # Simple categorization based on name (if they use standard names)
        # Using name to group since category field is just 'operasional'
        mapped_cat = "Lainnya"
        for key in by_category.keys():
            if key.lower() in cat.lower():
                mapped_cat = key
                break
                
        by_category[mapped_cat] += amt
        
        if item.get("is_recurring"):
            recurring.append(item)

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "by_category": by_category,
            "recurring": recurring
        }
    }


@router.post("", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_operational_cost(
    body: OperationalCostCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Record new operational cost & insert transaction."""
    supabase = get_supabase()

    cost_data = body.model_dump(exclude_unset=True)
    cost_data["tenant_id"] = current_user.tenant_id
    if "cost_date" in cost_data and cost_data["cost_date"]:
        cost_data["cost_date"] = cost_data["cost_date"].isoformat()

    # 1. Insert transaction
    txn_res = supabase.table("transactions").insert({
        "tenant_id": current_user.tenant_id,
        "type": "expense",
        "source": "manual_operational",
        "juknis_category": "operasional",
        "total": float(body.amount),
        "date": cost_data["cost_date"],
        "notes": body.name,
        "status": "confirmed",
        "recorded_by": current_user.id
    }).execute()
    
    txn_data = getattr(txn_res, "data", None)
    if txn_data:
        cost_data["transaction_id"] = txn_data[0]["id"]

    # 2. Insert operational cost
    response = supabase.table("operational_costs").insert(cost_data).execute()
    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(status_code=500, detail="Failed to save operational cost")

    return {"success": True, "data": data[0]}


@router.delete("/{cost_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def delete_operational_cost(
    cost_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Delete operational cost and void transaction."""
    supabase = get_supabase()

    # Get the cost to find transaction_id
    cost_res = supabase.table("operational_costs").select("transaction_id").eq("id", cost_id).eq("tenant_id", current_user.tenant_id).execute()
    costs = getattr(cost_res, "data", None)
    if not costs:
        raise HTTPException(status_code=404, detail="Operational cost not found")
        
    cost = costs[0]
    
    # 1. Delete cost
    supabase.table("operational_costs").delete().eq("id", cost_id).execute()
    
    # 2. Void transaction if exists
    if cost.get("transaction_id"):
        supabase.table("transactions").update({
            "status": "voided"
        }).eq("id", cost["transaction_id"]).execute()

    return {"success": True, "message": "Operational cost deleted and transaction voided"}
