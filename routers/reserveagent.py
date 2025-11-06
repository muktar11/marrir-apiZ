from datetime import datetime, timedelta, timezone
from http.client import HTTPException
import json
from typing import Any, List, Optional 
import uuid
from schemas.promotionschema import PromotionStatusSchema
from schemas.reserveschema import ApproveReserveSchema, PrivateReserveCreateSchema
from repositories.promotion import PromotionRepository
from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, BackgroundTasks
from fastapi.security import HTTPBearer
from starlette.requests import Request
from core.auth import RBACAccessType, RBACResource, rbac_access_checker
from models.batchreservemodel import BatchReserveModel
from models.companyinfomodel import CompanyInfoModel
from models.db import authentication_context, build_request_context, get_db, get_db_raw, get_db_session, get_db_sessions
from models.invoicemodel import InvoiceModel
from models.notificationmodel import Notifications
from models.promotionmodel import DurationEnum, PromotionModel, PromotionPackagesModel
from models.reservemodel import RecruitmentAgentPrivateReserveModel, RecruitmentReserveModel, RecruitmentSetReserveModel, ReserveModel
from models.usermodel import UserModel
from models.employeemodel import EmployeeModel
from repositories.reserve import ReserveRepository
from routers import version_prefix
from sqlalchemy import not_, cast, update
from core.context_vars import context_set_response_code_message, context_actor_user_data
from schemas.base import GenericMultipleResponse, GenericSingleResponse
from schemas.cvschema import CVSearchSchema
from schemas.enumschema import TransferStatusSchema, UserRoleSchema
from schemas.reserveschema import (
    BatchReserveReadSchema,
    BuyerPromoterReviewRequestSchema,
    BuyerRequestsCVSchema,
    GenericMultipleResponseEmployee,
    GenericMultipleResponseManager,
    RecruiterReviewByIdSchema,
    RecruiterReviewRequestSchema,
    RecruitmentReserveCreate,
    RecruitmentReserveReadSchema,
    RecruitmentReserveStatusUpdate,
    RecruitmentReserveSubscriptionBuy,
    RecruitmentSetReserveCreateSchema,
    ReserveBaseSchema,
    ReserveCVFilterSchema,
    ReserveCreateSchema,
    ReserveFilterSchema,
    ReservePay,
    ReserveReadSchema,
    ReserveUpdateSchema,
    BuyerReviewRequestSchema
)

from schemas.transferschema import TransferRequestPaymentCallback
from schemas.userschema import UsersSearchSchema
from cron_jobs import pending_reserves_notification, scheduler, delete_old_pending_reserve  # Import the scheduler and function
from core.security import settings
from telr_payment.api import Telr
import logging
from fastapi import Query
from models.cvmodel import CVModel
from sqlalchemy import or_, and_

from utils.send_email import send_email
from sqlalchemy.orm import Session
from fastapi import Depends


logger = logging.getLogger(__name__)

agent_reserve_router_prefix = version_prefix + "agent_reserve"

agent_reserve_router = APIRouter(prefix=agent_reserve_router_prefix)

telr = Telr(auth_key=settings.TELR_AUTH_KEY, store_id=settings.TELR_STORE_ID, test=settings.TELR_TEST_MODE)

def send_notification(db, user_id, title, description, type):
    notification = Notifications(
        title=title,
        description=description,
        type=type,
        user_id=user_id,
    )
    db.add(notification)

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        db.rollback()



from sqlalchemy import select, exists, and_
from sqlalchemy import select, exists, and_, cast
from sqlalchemy.dialects.postgresql import UUID

# it shows search result for reservation
@agent_reserve_router.get("/reserve-promotion-set", status_code=200)
async def get_promoted_cvs(
    nationality: Optional[str] = Query(None, description="Filter promoted CVs by nationality"),
    db: Session = Depends(get_db_raw)
):
    """
    Retrieve promoted CVs.
    - Joins PromotionModel → UserModel → CVModel
    - Optionally filters by nationality
    """
    # Base query: Promotion → User → CV

    
    query = (
        db.query(PromotionModel, CVModel)
        .join(UserModel, PromotionModel.user_id == UserModel.id)
        .join(CVModel, CVModel.user_id == UserModel.id)
    )
    # Apply filter by nationality (if provided)
    if nationality:
        query = query.filter(CVModel.nationality.ilike(f"%{nationality}%"))

    # ✅ Exclude CVs that were reserved in RecruitmentSetReserveModel
    query = query.filter(
        ~exists(
            select(1).where(
                and_(
                    cast(RecruitmentSetReserveModel.cv_id, UUID) == CVModel.user_id,
                    RecruitmentSetReserveModel.status.in_(["reserved", "APPROVED"])
                )
            )
        )
    )

    # ✅ Exclude CVs reserved in RecruitmentAgentPrivateReserveModel
    query = query.filter(
        ~exists(
            select(1).where(
                and_(
                    cast(RecruitmentAgentPrivateReserveModel.employee_id, UUID) == CVModel.user_id,
                    RecruitmentAgentPrivateReserveModel.status.in_(["accepted"])
                )
            )
        )
    )

    # ✅ Only active promotions
    query = query.filter(PromotionModel.status == PromotionStatusSchema.ACTIVE)

    # ✅ Execute final query
    results = query.all()

    # Format response
    data = [
        {
            "promotion_id": promotion.id,
            "promoted_user_id": promotion.user_id,
            "promoted_by_id": promotion.promoted_by_id,
            "status": promotion.status,
            "start_date": promotion.start_date,
            "end_date": promotion.end_date,
            "cv": {
                "user_id": cv.user_id,
                "passport_number": cv.passport_number,
                "english_full_name": cv.english_full_name,
                "amharic_full_name": cv.amharic_full_name,
                "arabic_full_name": cv.arabic_full_name,
                "nationality": cv.nationality,
                "phone_number": cv.phone_number,
                "email": cv.email,
                "sex": cv.sex,
                "height": cv.height,
                "weight": cv.weight,
                "skin_tone": cv.skin_tone,
                "head_photo": cv.head_photo,
                "date_of_birth": cv.date_of_birth,
            }
        }
        for promotion, cv in results
    ]

    return {
        "status_code": 200,
        "message": "Promoted CVs fetched successfully",
        "error": False,
        "count": len(data),
        "data": data,
    }


from uuid import UUID
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID


@agent_reserve_router.post("/private-reserve", status_code=201)
async def create_private_reserve(
    payload: PrivateReserveCreateSchema,
    db: Session = Depends(get_db_raw),
):
    """
    Create a private recruitment reservation.
    """
    # Use the payload values directly (already UUIDs)
    agent_id = payload.agent_id
    employee_id = payload.employee_id
    recruitment_id = payload.recruitment_id
    sponsor_id = payload.sponsor_id

    # Check for existing reservation by agent + employee
    existing = db.query(RecruitmentAgentPrivateReserveModel).filter_by(
        agent_id=agent_id,
        employee_id=employee_id
    ).first()

    if existing:
        return {
            "status_code": 200,
            "message": "Reservation already exists",
            "error": False,
            "data": {
                "recruitment_id": existing.recruitment_id,
                "agent_id": existing.agent_id,
                "sponsor_id": existing.sponsor_id,
                "employee_id": existing.employee_id,
                "status": existing.status
            }
        }

    # Create new reservation
    employee_id_str = str(payload.employee_id) if payload.employee_id else None
    existing = db.query(RecruitmentAgentPrivateReserveModel).filter_by(
        agent_id=agent_id,
        employee_id=employee_id_str
    ).first()
    new_reserve = RecruitmentAgentPrivateReserveModel(
        recruitment_id=recruitment_id,
        agent_id=agent_id,
        sponsor_id=sponsor_id,
        employee_id=employee_id_str
    )

    db.add(new_reserve)
    db.commit()
    db.refresh(new_reserve)

    return {
        "status_code": 201,
        "message": "Private reservation created successfully",
        "error": False,
        "data": {
            "recruitment_id": new_reserve.recruitment_id,
            "agent_id": new_reserve.agent_id,
            "sponsor_id": new_reserve.sponsor_id,
            "employee_id": new_reserve.employee_id,
            "status": new_reserve.status
        }
    }


from fastapi import Query
from models.cvmodel import CVModel
from sqlalchemy import or_, and_



from fastapi import Query
from models.cvmodel import CVModel
from sqlalchemy import or_, and_

@agent_reserve_router.get("/reserve-set-request-by-recruiter", status_code=200)
async def get_reserved_cvs(
    nationality: str = Query(None, description="Filter reserved CVs by nationality"),
    user_id: str = Query(None, description="Return CVs created by this user_id"),
    db: Session = Depends(get_db_raw)
):
    """
    Retrieve all reserved CVs grouped by RecruitmentSetReserveModel.
    - If `user_id` is provided → return CVs where CVModel.creator_id == user_id
    - If `nationality` is provided → filter CVs by nationality
    - Always include records where `selfsponsor=True`
    - Include only records where `approved=False`
    - Each reserve includes related company info from CompanyInfoModel (using recruitment_id)
    """

    # Base query joining reserves and CVs
    query = (
        db.query(RecruitmentSetReserveModel, CVModel)
        .join(CVModel, RecruitmentSetReserveModel.cv_id == CVModel.user_id)
    )

    # Filter by creator_id (from passed user_id)
    if user_id:
        query = query.filter(CVModel.creator_id == user_id)

    # Filter by nationality if provided
    if nationality:
        query = query.filter(
            or_(
                and_(
                    RecruitmentSetReserveModel.approved == False,
                    CVModel.nationality.ilike(f"%{nationality}%")
                ),
                RecruitmentSetReserveModel.selfsponsor == True
            )
        )
    else:
        query = query.filter(
            or_(
                RecruitmentSetReserveModel.approved == False,
                RecruitmentSetReserveModel.selfsponsor == True
            )
        )

    results = query.all()

    grouped_data = {}

    for reserve, cv in results:
        reserve_id = str(reserve.id)

        # ✅ Use reserve.recruitment_id to fetch company info
        company = (
            db.query(CompanyInfoModel)
            .filter(CompanyInfoModel.user_id == reserve.recruitment_id)
            .first()
        )

        # Convert company info to dict
        company_info = None
        if company:
            company_info = {
                "company_name": company.company_name,
                "alternative_email": company.alternative_email,
                "alternative_phone": company.alternative_phone,
                "location": company.location,
                "year_established": company.year_established,
                "ein_tin": company.ein_tin,
                "company_license": company.company_license,
                "company_logo": company.company_logo,
            }

        # ✅ Group by reserve_id
        if reserve_id not in grouped_data:
            grouped_data[reserve_id] = {
                "reserve_id": reserve.recruitment_id,
                "approved": reserve.approved,
                "selfsponsor": reserve.selfsponsor,
                "status": reserve.status,
                "created_at": getattr(reserve, "created_at", None),
                "updated_at": getattr(reserve, "updated_at", None),
                "company_info": company_info,
                "cvs": []
            }

        grouped_data[reserve_id]["cvs"].append({
            "id": cv.user_id,
            "passport_number": cv.passport_number,
            "summary": cv.summary,
            "email": cv.email,
            "national_id": cv.national_id,
            "amharic_full_name": cv.amharic_full_name,
            "arabic_full_name": cv.arabic_full_name,
            "english_full_name": cv.english_full_name,
            "sex": cv.sex,
            "phone_number": cv.phone_number,
            "height": cv.height,
            "weight": cv.weight,
            "skin_tone": cv.skin_tone,
            "date_of_birth": cv.date_of_birth,
            "nationality": cv.nationality,
            "head_photo": cv.head_photo,
        })

    return {
        "status_code": 200,
        "message": "Reserved CVs grouped by reserve and company info fetched successfully",
        "error": False,
        "count": len(grouped_data),
        "data": list(grouped_data.values()),
    }




import uuid
import uuid
import uuid
from fastapi import HTTPException
import uuid
from fastapi import HTTPException

@agent_reserve_router.post("/reserve-set-agent-accepting-reservation-request", status_code=200)
async def reserve_cv(
    *,
    reserve_in: RecruitmentSetReserveCreateSchema,
    db: Session = Depends(get_db_raw),
    request: Request,
    response: Response
) -> Any:

    updated_records = []

    # Ensure recruitment_id is string
    recruitment_id_str = str(reserve_in.recruitment_id)

    for cv_id in reserve_in.cv_ids:
        # Validate cv_id as UUID
        try:
            cv_uuid = uuid.UUID(str(cv_id))
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid CV UUID: {cv_id}")

        # Find existing reservation
        existing = (
            db.query(RecruitmentSetReserveModel)
            .filter(
               
                RecruitmentSetReserveModel.cv_id == cv_uuid
            )
            .first()
        )

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Reservation not found for recruitment_id={recruitment_id_str}, cv_id={cv_id}"
            )

        # Update approved status
        existing.approved = reserve_in.status.lower() == "approved"
        existing.rejected = reserve_in.status.lower() == "rejected"

        db.add(existing)
        updated_records.append(existing)

    db.commit()

    # Refresh updated records
    for r in updated_records:
        db.refresh(r)

    return {
        "status_code": 200,
        "message": f"{len(updated_records)} CV(s) updated successfully.",
        "error": False,
        "data": [
            {
                "recruitment_id": str(r.recruitment_id),
                "cv_id": str(r.cv_id),
                "approved": r.approved,
                "rejected": r.rejected,
                "message": "Status updated successfully"
            }
            for r in updated_records
        ]
    }


## api endpoint for the recruiter to see all his requested rservation to the agent
@agent_reserve_router.get("/reservations-by-recruiter", status_code=200)
async def get_recruiter_reservations(
    recruiter_id: str = Query(..., description="Recruiter (promoter) ID"),
    db: Session = Depends(get_db_raw)
) -> Any:
    """
    Fetch all RecruitmentSetReserve records for a given recruiter/promoter
    along with the child CVs.
    """

    # Base query: join reserves with CVs
    query = (
        db.query(RecruitmentSetReserveModel, CVModel)
        .join(CVModel, RecruitmentSetReserveModel.cv_id == CVModel.user_id)
        .filter(RecruitmentSetReserveModel.recruitment_id == recruiter_id)
    )

    results = query.all()

    grouped_data = {}

    for reserve, cv in results:
        reserve_id = str(reserve.id)

        if reserve_id not in grouped_data:
            grouped_data[reserve_id] = {
                "reserve_id": reserve_id,
                "recruitment_id": reserve.recruitment_id,
                "status": reserve.status,
                "approved": reserve.approved,
                "rejected": reserve.rejected,
                "selfsponsor": reserve.selfsponsor,
                "comment": reserve.comment,
                "requested": reserve.requested,
                "cvs": []
            }

        # Append child CV
        grouped_data[reserve_id]["cvs"].append({
            "cv_id": str(cv.user_id),
            "english_full_name": cv.english_full_name,
            "amharic_full_name": cv.amharic_full_name,
            "arabic_full_name": cv.arabic_full_name,
            "email": cv.email,
            "phone_number": cv.phone_number,
            "nationality": cv.nationality,
            "passport_number": cv.passport_number,
            "national_id": cv.national_id,
            "sex": cv.sex,
            "summary": cv.summary,
            "height": cv.height,
            "weight": cv.weight,
            "skin_tone": cv.skin_tone,
            "date_of_birth": cv.date_of_birth,
            "head_photo": cv.head_photo,
        })

    return {
        "status_code": 200,
        "message": f"Reservations for recruiter {recruiter_id} fetched successfully",
        "error": False,
        "count": len(grouped_data),
        "data": list(grouped_data.values())
    }




@agent_reserve_router.get("/employee/pending-reserves/agent-request", status_code=200)
async def get_pending_reserves(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Get all pending private reservations for a given employee.
    Includes agent names.
    """
    pending_reserves = db.query(RecruitmentAgentPrivateReserveModel).filter_by(
        employee_id=employee_id,
        status=TransferStatusSchema.PENDING
    ).all()

    data = []
    for r in pending_reserves:
        # Get agent name
        agent_name = None
        if r.agent_id:
            agent = db.query(UserModel).filter(UserModel.id == r.agent_id).first()
            if agent:
                agent_name = getattr(agent, "english_full_name", None) or \
                    f"{agent.first_name or ''} {agent.last_name or ''}".strip()
                
        recruiter_name = None
        if r.recruitment_id:
            recruiter = db.query(UserModel).filter(UserModel.id == r.recruitment_id).first()
            if recruiter:
                recruiter_name =  getattr(recruiter, "english_full_name", None) or \
                    f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()

        data.append({
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "agent_id": r.agent_id,
            "agent_name": agent_name,
            "recruitment_name": recruiter_name,
            "sponsor_id": r.sponsor_id,
            "employee_id": r.employee_id,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Pending reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }




@agent_reserve_router.get("/employee/pending-reserves/agent-request", status_code=200)
async def get_pending_reserves(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Get all pending private reservations for a given employee.
    Includes agent names.
    """
    pending_reserves = db.query(RecruitmentAgentPrivateReserveModel).filter_by(
        employee_id=employee_id,
        status=TransferStatusSchema.PENDING
    ).all()

    data = []
    for r in pending_reserves:
        # Get agent name
        agent_name = None
        if r.agent_id:
            agent = db.query(UserModel).filter(UserModel.id == r.agent_id).first()
            if agent:
                agent_name = getattr(agent, "english_full_name", None) or \
                    f"{agent.first_name or ''} {agent.last_name or ''}".strip()
                
        recruiter_name = None
        if r.recruitment_id:
            recruiter = db.query(UserModel).filter(UserModel.id == r.recruitment_id).first()
            if recruiter:
                recruiter_name =  getattr(recruiter, "english_full_name", None) or \
                    f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()

        data.append({
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "agent_id": r.agent_id,
            "agent_name": agent_name,
            "recruitment_name": recruiter_name,
            "sponsor_id": r.sponsor_id,
            "employee_id": r.employee_id,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Pending reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
@agent_reserve_router.put("/employee/pending-reserves/agent-request/approve", status_code=200)
async def approve_private_reserve(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Approve a pending private reservation by employee_id.
    - Sets the reservation status to 'ACCEPTED'
    - Updates the matching CV record's creator_id to the recruitment_id from the reservation
    """

    try:
        # Validate UUID format if applicable
        employee_uuid = str(uuid.UUID(employee_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee_id UUID")

    # Step 1: Find the pending reserve
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter_by(employee_id=employee_uuid, status=TransferStatusSchema.PENDING)
        .first()
    )

    if not reserve:
        raise HTTPException(status_code=404, detail="Pending reservation not found")

    # Step 2: Approve it (set status to ACCEPTED)
    reserve.status = TransferStatusSchema.ACCEPTED

    # Step 3: Find the CV record by employee_id
    cv_record = db.query(EmployeeModel).filter_by(user_id=employee_uuid).first()
    if not cv_record:
        raise HTTPException(status_code=404, detail="CV not found for given employee_id")

    # Step 4: Update creator_id with the recruitment_id from the reserve
    cv_record.manager_id = reserve.agent_id
    print('cv_manager', cv_record.manager_id)


    try:
        db.commit()
        db.refresh(reserve)
        db.refresh(cv_record)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status_code": 200,
        "message": "Reservation approved and CV creator updated successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "employee_id": employee_uuid,
            "recruitment_id": reserve.recruitment_id,
            "new_cv_manager_id": cv_record.manager_id,
            "status": reserve.status,
        },
    }

import uuid
from fastapi import HTTPException

@agent_reserve_router.get("/employee/pending-reserves/recruiter-request", status_code=200)
async def get_pending_reserves(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Get all pending recruiter reservations for a given employee.
    Includes agent and recruiter names via relationships.
    """

    # Convert employee_id string to UUID
    try:
        employee_uuid = uuid.UUID(employee_id)
        print(employee_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee_id UUID")

    # Fetch pending reservations
    #pending_reserves = db.query(RecruitmentSetReserveModel).filter_by( cv_id=employee_id, ).all()
    pending_reserves = db.query(RecruitmentSetReserveModel).filter(
    RecruitmentSetReserveModel.cv_id == employee_id,
    RecruitmentSetReserveModel.status.ilike("reserved")
)

    data = []
    for reserve in pending_reserves:
        # ✅ Find recruiter from UserModel where UserModel.id == reserve.reserve_id
        recruiter = None
        if getattr(reserve, "recruitment_id", None):
            recruiter = db.query(UserModel).filter_by(id=reserve.recruitment_id).first()

        recruiter_name = None
        if recruiter:
            recruiter_name = f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()

        # ✅ Agent name (if related model exists)
        agent_name = None
        if getattr(reserve, "agent", None):
            agent_name = getattr(reserve.agent, "english_full_name", None) or \
                         f"{getattr(reserve.agent, 'first_name', '')} {getattr(reserve.agent, 'last_name', '')}".strip()

        data.append({
            "id": reserve.id,
            "reserve_id": reserve.recruitment_id,
            "recruiter_name": recruiter_name or "N/A",
            "agent_id": getattr(reserve, "agent_id", None),
            "agent_name": agent_name,
            "employee_id": str(reserve.cv_id),
            "status": getattr(reserve, "status", None),
            "created_at": getattr(reserve, "created_at", None),
            "updated_at": getattr(reserve, "updated_at", None),
        })

    return {
        "status_code": 200,
        "message": "Pending recruiter reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


@agent_reserve_router.put("/employee/pending-reserves/recruiter-request/update", status_code=200)
async def update_recruiter_reserve(
    employee_id: str,
    action: str,   # "approve" or "reject"
    db: Session = Depends(get_db_raw)
):
    """
    Update recruiter reserve for a given employee.
    - Approve or reject a recruiter reservation.
    """

    # Validate employee UUID
    try:
        employee_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee_id UUID")

    # Fetch the pending reservations
    reserve = (
        db.query(RecruitmentSetReserveModel)
        .filter(
            RecruitmentSetReserveModel.cv_id == employee_uuid,
            RecruitmentSetReserveModel.status.ilike("reserved")
        )
        .first()
    )

    if not reserve:
        raise HTTPException(status_code=404, detail="No recruiter reserved CV found")

    # Approve or reject
    if action.lower() == "approve":
        reserve.status = "APPROVED"
        reserve.approved = True
        reserve.rejected = False
    elif action.lower() == "reject":
        reserve.status = "REJECTED"
        reserve.approved = False
        reserve.rejected = True
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'approve' or 'reject'")

    # ✅ OPTIONAL: update CV manager if approved
    if action.lower() == "approve":
        cv_record = db.query(EmployeeModel).filter_by(user_id=employee_uuid).first()

        if not cv_record:
            raise HTTPException(status_code=404, detail="CV not found")

        # recruiter_id is stored in recruitment_id column
        cv_record.manager_id = reserve.recruitment_id

    try:
        db.commit()
        db.refresh(reserve)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status_code": 200,
        "message": f"Recruiter reservation {action}ed successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "employee_id": employee_id,
            "recruiter_id": reserve.recruitment_id,
            "status": reserve.status
        }
    }















@agent_reserve_router.put("/employee/approve-reserve", status_code=200)
async def approve_reservation(
    reserve_id: int,
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    # Convert employee_id to UUID safely
    try:
        employee_uuid = UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee_id UUID format")

    # Fetch pending reservation
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.id == reserve_id,
            RecruitmentAgentPrivateReserveModel.employee_id == str(employee_uuid),
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
        )
        .first()
    )

    if not reserve:
        raise HTTPException(status_code=404, detail="Pending reservation not found for this employee")

    # Ensure agent_id is valid
    if not reserve.agent_id:
        raise HTTPException(status_code=400, detail="Reservation has no agent_id assigned")

   
    cv_agent = db.query(CVModel).filter(CVModel.user_id == employee_uuid).first() 
    if not cv_agent: 
        raise HTTPException(status_code=404, detail="CV not found for the agent") # Update the CV's creator_id with agent_id from the reservation cv.creator_id = reserve.agent_id

    cv_employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == employee_uuid).first()
    
    if not cv_employee:
        raise HTTPException(status_code=404, detail="CV not found for this employee")

    # ✅ Ensure both IDs are strings or UUIDs consistently
    try:
        cv_employee.manager_id = uuid(reserve.agent_id)
        cv_agent.creator_id = reserve.agent_id
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid agent_id: {e}")

    reserve.status = TransferStatusSchema.ACCEPTED

    db.add(cv_employee)  # ensure object is attached
    db.add(cv_agent)  # ensure object is attached
    db.add(reserve)
    db.flush()  # force SQL execution before commit
    db.commit()

    db.refresh(reserve)
    db.refresh(cv_employee)
    db.refresh(cv_agent)

    return {
        "status_code": 200,
        "message": "Reservation approved and CV updated successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "employee_id": reserve.employee_id,
            "agent_id": reserve.agent_id,
            "cv_id": cv_agent.id,
            "cv_creator_id": cv_agent.creator_id,
            "status": reserve.status,
        },
    }
