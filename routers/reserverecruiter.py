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
from models.reservemodel import  RecruitmentAgentPrivateReserveModel, RecruitmentReserveModel, RecruitmentSetReserveModel, ReserveModel
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

recruiter_reserve_router_prefix = version_prefix + "recruiter_reserve"

recruiter_reserve_router = APIRouter(prefix=recruiter_reserve_router_prefix)

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




#this works
@recruiter_reserve_router.post("/my-not-reserves", status_code=200)
async def get_unreserved_employee_cvs(
    request: Request,
    response: Response,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    nationality: str = None
):
    db = next(get_db_raw())
    user = context_actor_user_data.get()
    reserve_repo = ReserveRepository(entity=ReserveModel)
    result = reserve_repo.get_not_reserved_by_me_recruiter(db, user_id=user.id, skip=skip, limit=limit,  nationality=nationality)
    return {
        "status_code": 200,
        "message": "Unreserved CVs fetched successfully",
        "error": None,
        "data": result["data"],
        "count": result["count"],
    }


#this creates reserve
@recruiter_reserve_router.post("/reserve-set", status_code=201)
async def reserve_cv(
    *,
    reserve_in: RecruitmentSetReserveCreateSchema,
    db: Session = Depends(get_db_raw),
    request: Request,
    response: Response
) -> Any:

    reserved_records = []
    skipped_records = []

    for cv_id in reserve_in.cv_ids:
        # Ensure cv_id is a valid UUID
        try:
            cv_uuid = uuid.UUID(str(cv_id))
        except ValueError:
            skipped_records.append({
                "recruitment_id": str(reserve_in.recruitment_id),
                "cv_id": cv_id,
                "status": "invalid",
                "message": "Invalid CV ID"
            })
            continue

        # Check if this combination already exists
        existing = (
            db.query(RecruitmentSetReserveModel)
            .filter(
                
                RecruitmentSetReserveModel.recruitment_id == str(reserve_in.recruitment_id), 
                RecruitmentSetReserveModel.cv_id == cv_uuid
            )
            .first()
        )

        

        if existing:
            skipped_records.append({
                "recruitment_id": str(existing.recruitment_id),
                "cv_id": str(existing.cv_id),
                "status": existing.status,
                "message": "Already reserved"
            })
            continue

        # Create a new reservation
        new_reserve = RecruitmentSetReserveModel(
            recruitment_id=reserve_in.recruitment_id,
            cv_id=cv_uuid,
            status=reserve_in.status
        )
        db.add(new_reserve)
        db.commit()  # Commit per record to get IDs immediately
        db.refresh(new_reserve)
        reserved_records.append(new_reserve)

        # --- Send notification to agent ---
        cv = db.query(CVModel).filter(CVModel.user_id == cv_uuid).first()
        if cv:
            agent_user = db.query(UserModel).filter(UserModel.id == cv.creator_id).first()
            recruiter_user = db.query(UserModel).filter(UserModel.id == reserve_in.recruitment_id).first()

            if agent_user and recruiter_user:
                notification = Notifications(
                    id=uuid.uuid4(),
                    title="Your CV Has Been Recruited",
                    description=(
                        f"Congratulations! Your CV ({cv.english_full_name or cv.passport_number}) "
                        f"has been reserved by {recruiter_user.first_name or recruiter_user.email}."
                    ),
                    type="cv_recruited",
                    object_id={"cv_id": str(cv.user_id)},
                    extra_data={"recruiter_id": str(recruiter_user.id)},
                    unread=True,
                    user_id=agent_user.id,
                    created_at=datetime.utcnow(),
                )
                db.add(notification)
                db.commit()

    return {
        "status_code": 201,
        "message": f"{len(reserved_records)} CV(s) reserved successfully. {len(skipped_records)} skipped.",
        "error": False,
        "data": [
            {
                "recruitment_id": str(r.recruitment_id),
                "cv_id": str(r.cv_id),
                "status": r.status,
                "message": "Reserved successfully"
            }
            for r in reserved_records
        ] + skipped_records
    }





from sqlalchemy import select, exists, and_
from sqlalchemy import select, exists, and_, cast
from sqlalchemy.dialects.postgresql import UUID

# it shows search result for reservation
@recruiter_reserve_router.get("/reserve-promotion-set", status_code=200)
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


@recruiter_reserve_router.post("/private-reserve", status_code=201)
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
        recruitment_id=recruitment_id,
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
        recruitment_id=recruitment_id,
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




import uuid
from fastapi import HTTPException

@recruiter_reserve_router.get("/selfsponsor/pending-reserves/recruiter-request", status_code=200)
async def get_pending_employer_reserves(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Get all pending private reservations created by employer (sponsor).
    """
    pending_reserves = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.employee_id == employee_id,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.recruitment_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.agent_id.is_(None),
            RecruitmentAgentPrivateReserveModel.sponsor_id.is_(None)
        )
        .all()
    )

    data = []
    for r in pending_reserves:

        # Get recruiter name
        recruiter_name = None
        if r.recruitment_id:
            recruiter = db.query(UserModel).filter(UserModel.id == r.recruitment_id).first()
            if recruiter:
                recruiter_name = getattr(recruiter, "english_full_name", None) or \
                                 f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()

        # Get sponsor name
        sponsor_name = None
        if r.sponsor_id:
            sponsor = db.query(UserModel).filter(UserModel.id == r.sponsor_id).first()
            if sponsor:
                sponsor_name = getattr(sponsor, "english_full_name", None) or \
                               f"{sponsor.first_name or ''} {sponsor.last_name or ''}".strip()

        data.append({
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "recruitment_name": recruiter_name,
            "sponsor_id": r.sponsor_id,
            "sponsor_name": sponsor_name,
            "employee_id": r.employee_id,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Employer private reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


@recruiter_reserve_router.put("/recruit/pending-reserves/recruiterer-request/approve", status_code=200)
async def approve_sponsor_private_reserve(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Approve a pending private reservation created by a sponsor (employer).
    Only approves:
        - sponsor_id IS NOT NULL
        - agent_id IS NULL
        - status = PENDING
        - employee_id matches
    """

    # Validate UUID
    try:
        employee_uuid = str(uuid.UUID(employee_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee_id UUID")

    # Step 1: Find sponsor-created pending reservation
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.employee_id == employee_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.recruitment_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.agent_id.is_(None),
            RecruitmentAgentPrivateReserveModel.sponsor_id.is_(None)

        )
        .first()
    )

    if not reserve:
        raise HTTPException(
            status_code=404,
            detail="Pending sponsor private reservation not found"
        )

    # Step 2: Approve reservation
    reserve.status = TransferStatusSchema.ACCEPTED

    try:
        db.commit()
        db.refresh(reserve)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status_code": 200,
        "message": "Sponsor private reservation approved successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "employee_id": employee_uuid,
            "sponsor_id": reserve.sponsor_id,
            "recruitment_id": reserve.recruitment_id,
            "status": reserve.status,
        },
    }
