"""
Payroll management endpoints.
"""

from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.hr import PayrollPeriodCreate
from models.user import UserInDB
from services.pdf_service import pdf_service

router = APIRouter(prefix="/payroll", tags=["hr"])


@router.post("/periods", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def create_payroll_period(
    body: PayrollPeriodCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Create a new payroll period and auto-calculate items for active employees."""
    supabase = get_supabase()

    # 1. Get active employees
    emp_res = (
        supabase.table("employees")
        .select("id, position_id, job_positions(name, base_salary)")
        .eq("tenant_id", current_user.tenant_id)
        .eq("is_active", True)
        .execute()
    )
    employees = getattr(emp_res, "data", None) or []
    
    if not employees:
        raise HTTPException(status_code=400, detail="Tidak ada karyawan aktif untuk digaji")

    # 2. Get attendances for the period
    att_res = (
        supabase.table("attendances")
        .select("employee_id")
        .eq("tenant_id", current_user.tenant_id)
        .gte("date", body.start_date.isoformat())
        .lte("date", body.end_date.isoformat())
        .execute()
    )
    attendances = getattr(att_res, "data", None) or []
    
    # Count absences per employee
    absent_counts = {}
    for att in attendances:
        eid = att["employee_id"]
        absent_counts[eid] = absent_counts.get(eid, 0) + 1

    # 3. Calculate payroll items & total amount
    total_amount = 0
    items_to_insert = []
    
    for emp in employees:
        pos = emp.get("job_positions") or {}
        pos_name = pos.get("name", "Tanpa Jabatan")
        base_salary = pos.get("base_salary", 0)
        
        absent_days = absent_counts.get(emp["id"], 0)
        present_days = max(0, body.working_days - absent_days)
        gross_amount = present_days * base_salary
        net_amount = gross_amount # deductions = 0 for now
        
        total_amount += net_amount
        
        items_to_insert.append({
            "tenant_id": current_user.tenant_id,
            "employee_id": emp["id"],
            "position_name": pos_name,
            "base_salary": base_salary,
            "working_days": body.working_days,
            "absent_days": absent_days,
            "present_days": present_days,
            "gross_amount": gross_amount,
            "deductions": 0,
            "net_amount": net_amount,
        })

    # 4. Insert period
    period_res = supabase.table("payroll_periods").insert({
        "tenant_id": current_user.tenant_id,
        "name": body.name,
        "start_date": body.start_date.isoformat(),
        "end_date": body.end_date.isoformat(),
        "working_days": body.working_days,
        "notes": body.notes,
        "total_amount": total_amount,
        "status": "draft"
    }).execute()
    
    period = getattr(period_res, "data", None)[0]
    period_id = period["id"]
    
    # 5. Insert items
    for item in items_to_insert:
        item["period_id"] = period_id
        
    supabase.table("payroll_items").insert(items_to_insert).execute()

    return {"success": True, "data": period}


@router.get("/periods", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def list_payroll_periods(
    current_user: UserInDB = Depends(get_current_user),
):
    """List payroll periods."""
    supabase = get_supabase()
    
    response = (
        supabase.table("payroll_periods")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .order("start_date", desc=True)
        .execute()
    )
    data = getattr(response, "data", None) or []
    
    # Count employees per period (optional, maybe not needed if not too slow)
    # Actually just querying is ok, we can do it via a view or separate query.
    # We will just fetch items count
    if data:
        items_res = (
            supabase.table("payroll_items")
            .select("period_id")
            .eq("tenant_id", current_user.tenant_id)
            .execute()
        )
        items = getattr(items_res, "data", None) or []
        counts = {}
        for it in items:
            pid = it["period_id"]
            counts[pid] = counts.get(pid, 0) + 1
            
        for d in data:
            d["employee_count"] = counts.get(d["id"], 0)

    return {"success": True, "data": data}


@router.get("/periods/{period_id}", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner", "admin"]))])
def get_payroll_period_details(
    period_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Get single payroll period details including items."""
    supabase = get_supabase()
    
    period_res = supabase.table("payroll_periods").select("*").eq("id", period_id).eq("tenant_id", current_user.tenant_id).execute()
    period = getattr(period_res, "data", None)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
        
    items_res = (
        supabase.table("payroll_items")
        .select("*, employees(name)")
        .eq("period_id", period_id)
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    items = getattr(items_res, "data", None) or []
    
    for item in items:
        item["employee_name"] = item.get("employees", {}).get("name", "Unknown")

    return {
        "success": True,
        "data": {
            "period": period[0],
            "items": items
        }
    }


@router.put("/periods/{period_id}/approve", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner"]))])
def approve_payroll_period(
    period_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Approve a payroll period."""
    supabase = get_supabase()
    
    response = (
        supabase.table("payroll_periods")
        .update({"status": "approved"})
        .eq("id", period_id)
        .eq("status", "draft")
        .eq("tenant_id", current_user.tenant_id)
        .execute()
    )
    data = getattr(response, "data", None) or []
    if not data:
        raise HTTPException(status_code=400, detail="Periode tidak ditemukan atau bukan berstatus draft")

    return {"success": True, "data": data[0]}


@router.post("/periods/{period_id}/pay", response_model=Dict[str, Any], dependencies=[Depends(require_role(["owner"]))])
def pay_payroll_period(
    period_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Pay a payroll period, creating transactions."""
    supabase = get_supabase()
    
    # 1. Validate status
    period_res = supabase.table("payroll_periods").select("*").eq("id", period_id).eq("tenant_id", current_user.tenant_id).execute()
    periods = getattr(period_res, "data", None)
    if not periods:
        raise HTTPException(status_code=404, detail="Period not found")
        
    period = periods[0]
    if period["status"] != "approved":
        raise HTTPException(status_code=400, detail="Periode harus di-approve sebelum bisa dibayar")
        
    # 2. Update status to paid
    today_str = date.today().isoformat()
    supabase.table("payroll_periods").update({
        "status": "paid",
        "paid_date": today_str
    }).eq("id", period_id).execute()
    
    # 3. Get items & employees
    items_res = (
        supabase.table("payroll_items")
        .select("*, employees(name)")
        .eq("period_id", period_id)
        .execute()
    )
    items = getattr(items_res, "data", None) or []
    
    for item in items:
        emp_name = item.get("employees", {}).get("name", "Unknown")
        net = item["net_amount"]
        
        # Insert transaction
        txn_res = supabase.table("transactions").insert({
            "tenant_id": current_user.tenant_id,
            "type": "expense",
            "source": "payroll",
            "juknis_category": "insentif",
            "total": net,
            "date": today_str,
            "notes": f"Gaji {emp_name} - {period['name']}",
            "status": "confirmed",
            "recorded_by": current_user.id
        }).execute()
        
        txn_data = getattr(txn_res, "data", None)
        if txn_data:
            # Update item with transaction_id
            supabase.table("payroll_items").update({
                "transaction_id": txn_data[0]["id"]
            }).eq("id", item["id"]).execute()
            
    return {"success": True, "total_paid": period.get("total_amount", 0)}


@router.get("/periods/{period_id}/slip/{employee_id}", dependencies=[Depends(require_role(["owner", "admin"]))])
def download_payslip(
    period_id: str,
    employee_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Download single payslip PDF."""
    supabase = get_supabase()
    
    # Needs to be implemented in pdf_service
    pdf_bytes = pdf_service.generate_payslip(
        supabase=supabase,
        tenant_id=current_user.tenant_id,
        period_id=period_id,
        employee_id=employee_id
    )
    
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate payslip")
        
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=payslip_{employee_id}.pdf"}
    )


@router.post("/periods/{period_id}/slip/batch", dependencies=[Depends(require_role(["owner", "admin"]))])
def download_payslip_batch(
    period_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Download all payslips for a period as ZIP."""
    supabase = get_supabase()
    
    zip_bytes = pdf_service.generate_payslip_batch(
        supabase=supabase,
        tenant_id=current_user.tenant_id,
        period_id=period_id
    )
    
    if not zip_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate payslips zip")
        
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=payslips_period_{period_id}.zip"}
    )
