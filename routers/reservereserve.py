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

from utils.send_email import send_email
from sqlalchemy.orm import Session
from fastapi import Depends


logger = logging.getLogger(__name__)

reserve_router_prefix = version_prefix + "reserve"

reserve_router = APIRouter(prefix=reserve_router_prefix)

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
'''
@reserve_router.post(
    "/", status_code=201
)
@rbac_access_checker(
    resource=RBACResource.reserve, rbac_access_type=RBACAccessType.create
)
async def reserve_cv(
    *,
    reserve_in: ReserveCreateSchema,
    background_tasks: BackgroundTasks,
    
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    create a new reserve request
    """
    db = get_db_session()
    user = context_actor_user_data.get()
    reserve_in.reserver_id = user.id
    reserve_repo = ReserveRepository(entity=ReserveModel)
    new_reserve = reserve_repo.send_reserve_request(db, obj_in=reserve_in)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code

    for reserve in new_reserve:
        run_date = datetime.now(timezone.utc) + timedelta(hours=24)
        reminder_date = datetime.now(timezone.utc) + timedelta(hours=23)
        scheduler.add_job(delete_old_pending_reserve, 'date', run_date=run_date, args=[reserve.cv_id, db])
        scheduler.add_job(pending_reserves_notification, 'date', run_date=reminder_date, args=[reserve.cv_id, db])

    title = "Reserve Request"
    description = "Your promoted profile(s) has been reserved. Please accept the reservation within 24 hours, or it will become available for reservation again."

    background_tasks.add_task(send_notification, db, new_reserve[0].owner_id, title, description, "reserve")

    _user = db.query(UserModel).filter(UserModel.id == new_reserve[0].owner_id).first()

    email = _user.email or _user.company.alternative_email

    background_tasks.add_task(func=send_email, email=email, title=title, description=description)

    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
    }
'''
'''
@reserve_router.post("/", status_code=201)
@rbac_access_checker(
    resource=RBACResource.reserve, rbac_access_type=RBACAccessType.create
)
async def reserve_cv(
    *,
    reserve_in: ReserveCreateSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_raw),
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    Create a new reserve request.
    """
    # ✅ Safe user check
    user = context_actor_user_data.get()
    if not user or not getattr(user, "id", None):
        return {
            "status_code": 401,
            "message": "User not authenticated",
            "error": True
        }

    reserve_in.reserver_id = user.id

    reserve_repo = ReserveRepository(entity=ReserveModel)
    new_reserve = reserve_repo.send_reserve_request(db, obj_in=reserve_in)

    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code

    # ✅ Handle empty reserve case to avoid IndexError
    if not new_reserve:
        return {
            "status_code": res_data.status_code,
            "message": res_data.message,
            "error": res_data.error,
        }

    for reserve in new_reserve:
        run_date = datetime.now(timezone.utc) + timedelta(hours=24)
        reminder_date = datetime.now(timezone.utc) + timedelta(hours=23)
        scheduler.add_job(delete_old_pending_reserve, 'date', run_date=run_date, args=[reserve.cv_id, db])
        scheduler.add_job(pending_reserves_notification, 'date', run_date=reminder_date, args=[reserve.cv_id, db])

    title = "Reserve Request"
    description = (
        "Your promoted profile(s) has been reserved. Please accept the reservation within 24 hours, "
        "or it will become available for reservation again."
    )

    owner_id = getattr(new_reserve[0], "owner_id", None)
    if owner_id:
        background_tasks.add_task(send_notification, db, owner_id, title, description, "reserve")

        _user = db.query(UserModel).filter(UserModel.id == owner_id).first()
        if _user:
            email = _user.email or (_user.company.alternative_email if getattr(_user, "company", None) else None)
            if email:
                background_tasks.add_task(send_email, email=email, title=title, description=description)

    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
    }

'''

@reserve_router.post("/", status_code=201)
async def reserve_cv(
    *,
    reserve_in: RecruitmentSetReserveCreateSchema,
    db: Session = Depends(get_db_raw),
    _ = Depends(authentication_context),
    request: Request,
    response: Response
) -> Any:
    """
    Reserve a CV for a recruiter.
    """
    # ✅ Safe user check
    user = getattr(_, "user", None)  # adjust depending on your auth
    if not user or not getattr(user, "id", None):
        return {"status_code": 401, "message": "User not authenticated", "error": True}

    reserve_in.recruitment_id = user.id

    # Use repository
    reserve_repo = ReserveRepository(entity=RecruitmentSetReserveModel)
    new_reserve = reserve_repo.reserve_cv(db, obj_in=reserve_in)

    return {
        "status_code": 201,
        "message": "CV reserved successfully",
        "error": False,
        "data": new_reserve
    }

#this works
@reserve_router.post("/my-not-reserves", status_code=200)
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

    result = reserve_repo.get_not_reserved_by_me(db, user_id=user.id, skip=skip, limit=limit,  nationality=nationality)
    return {
        "status_code": 200,
        "message": "Unreserved CVs fetched successfully",
        "error": None,
        "data": result["data"],
        "count": result["count"],
    }

'''
@reserve_router.post("/reserve-set", status_code=201)
async def reserve_cv(
    *,
    reserve_in: RecruitmentSetReserveCreateSchema,
    db: Session = Depends(get_db_raw),
    request: Request,
    response: Response
) -> Any:
    """
    Reserve a CV for a recruiter (no authentication required).
    """
    # Directly use the recruitment_id passed in request body
    new_reserve = RecruitmentSetReserveModel(
        recruitment_id=reserve_in.recruitment_id,
        cv_id=reserve_in.cv_id,
        status=reserve_in.status
    )

    db.add(new_reserve)
    db.commit()
    db.refresh(new_reserve)

    return {
        "status_code": 201,
        "message": "CV reserved successfully",
        "error": False,
        "data": {
            "recruitment_id": str(new_reserve.recruitment_id),
            "cv_id": str(new_reserve.cv_id),
            "status": new_reserve.status
        }
    }
'''

'''
@reserve_router.post("/reserve-set", status_code=201)
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
        # Check if this combination already exists
        existing = (
            db.query(RecruitmentSetReserveModel)
            .filter(
                RecruitmentSetReserveModel.recruitment_id == reserve_in.recruitment_id,
                RecruitmentSetReserveModel.cv_id == cv_id
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
            cv_id=cv_id,
            status=reserve_in.status
        )
        db.add(new_reserve)
        reserved_records.append(new_reserve)

    db.commit()

    # Refresh all records to ensure all new ones have DB-generated values
    for record in reserved_records:
        db.refresh(record)


    return {
        "status_code": 201,
        "message": f"{len(reserved_records)} CV(s) reserved successfully. {len(skipped_records)} duplicate(s) skipped.",
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

'''

#this creates reserve
@reserve_router.post("/reserve-set", status_code=201)
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

from fastapi import Query
from models.cvmodel import CVModel
from sqlalchemy import or_, and_
@reserve_router.get("/reserve-set", status_code=200)
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








from uuid import UUID
##########
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID

@reserve_router.get("/reserve-promotion-set", status_code=200)
async def get_promoted_cvs(
    nationality: Optional[str] = Query(None, description="Filter promoted CVs by nationality"),
    db: Session = Depends(get_db_raw)
):
    """
    Retrieve promoted CVs and exclude reserved ones.
    """
    # Subquery for reserved employee_ids (cast to UUID)
    reserved_subquery = (
        db.query(cast(RecruitmentAgentPrivateReserveModel.employee_id, UUID))
        .subquery()
    )

    query = (
        db.query(PromotionModel, CVModel)
        .join(UserModel, PromotionModel.user_id == UserModel.id)
        .join(CVModel, CVModel.user_id == UserModel.id)
        # Exclude reserved employees (cast ensures correct type comparison)
        .filter(~CVModel.user_id.in_(reserved_subquery))
    )

    if nationality:
        query = query.filter(CVModel.nationality.ilike(f"%{nationality}%"))

    query = query.filter(PromotionModel.status == PromotionStatusSchema.ACTIVE)

    results = query.all()

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


@reserve_router.post("/private-reserve", status_code=201)
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

@reserve_router.get("/employee/pending-reserves", status_code=200)
async def get_pending_reserves(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Get all pending private reservations for a given employee.
    """
    pending_reserves = db.query(RecruitmentAgentPrivateReserveModel).filter_by(
        employee_id=employee_id,
        status=TransferStatusSchema.PENDING
    ).all()

    if not pending_reserves:
        return {
            "status_code": 200,
            "message": "No pending reservations found",
            "error": False,
            "count": 0,
            "data": []
        }

    data = [
        {
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "agent_id": r.agent_id,
            "sponsor_id": r.sponsor_id,
            "employee_id": r.employee_id,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        }
        for r in pending_reserves
    ]

    return {
        "status_code": 200,
        "message": "Pending reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


@reserve_router.put("/employee/approve-reserve", status_code=200)
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

########

@reserve_router.post("/buyer-request-cv", status_code=200)
async def request_cv_by_buyer(
        request_in: BuyerRequestsCVSchema,
        db: Session = Depends(get_db_raw)
    ) -> Any:
        """
        Allows a buyer (sponsor) to request multiple CVs.
        Updates all RecruitmentSetReserveModel entries that match any of the given cv_ids.
        """

        # Step 1: Validate buyer
        buyer = db.query(UserModel).filter(UserModel.id == request_in.buyer_id).first()
        if not buyer:
            raise HTTPException(status_code=404, detail="Buyer not found.")

        # Step 2: Ensure the buyer is a sponsor
        if buyer.role != "sponsor":
            raise HTTPException(status_code=403, detail="User is not authorized to request CVs.")

        updated_records = []
        skipped_records = []

        # Step 3: Bulk update per CV ID
        for cv_id in request_in.cv_id:
            # Update all matching records in one query
            stmt = (
                update(RecruitmentSetReserveModel)
                .where(RecruitmentSetReserveModel.cv_id == uuid.UUID(str(cv_id)))
                .values(buyer_id=request_in.buyer_id, requested=True)
                .returning(
                    RecruitmentSetReserveModel.cv_id,
                    RecruitmentSetReserveModel.buyer_id,
                    RecruitmentSetReserveModel.requested
                )
            )


            result = db.execute(stmt)
            records = result.fetchall()

            if records:
                for rec in records:
                    updated_records.append({
                        "cv_id": str(rec.cv_id),
                        "buyer_id": str(rec.buyer_id),
                        "requested": rec.requested
                    })
            else:
                skipped_records.append({
                    "cv_id": str(cv_id),
                    "reason": "No records found or already requested"
                })

        db.commit()

        return {
            "status_code": 200,
            "message": "Buyer CV request update completed.",
            "data": {
                "updated_records": updated_records,
                "skipped_records": skipped_records
            }
        }

@reserve_router.get("/recruiter-requests", status_code=200)
async def get_buyer_requests_for_recruiter(
    recruiter_id: uuid.UUID = Query(..., description="Recruiter user ID"),
    db: Session = Depends(get_db_raw)
):
    """
    Fetch all buyer requests linked to a given recruiter.
    Each record includes:
    - CV owner full name (from CVModel via cv_id → user_id)
    - Recruiter full name (from UserModel via recruiter_id)
    """
    try:
        # Step 1: Validate recruiter
        recruiter = db.query(UserModel).filter(UserModel.id == recruiter_id).first()
        if not recruiter:
            raise HTTPException(status_code=404, detail="Recruiter not found.")
        if recruiter.role != "recruitment":
            raise HTTPException(status_code=403, detail="User is not a recruiter.")

        # Step 2: Fetch buyer requests for this recruiter
        requests = db.query(RecruitmentSetReserveModel).filter(
            RecruitmentSetReserveModel.recruitment_id == str(recruiter_id),
            RecruitmentSetReserveModel.requested.is_(True)
        ).all()

        # Step 3: Prepare response data
        data = []
        for req in requests:
            cv_owner_full_name = None
            recruiter_full_name = None

            # --- Get CV owner name ---
            cv = (
                db.query(CVModel)
                .filter(CVModel.user_id == req.cv_id)
                .first()
            )
            if cv:
                cv_owner_full_name = cv.english_full_name

            # --- Get Recruiter name ---
            recruiter_full_name = (
                getattr(recruiter, "english_full_name", None)
                or f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()
            )

            data.append({
                "id": str(req.id),
                "cv_id": str(req.cv_id),
                "buyer_id": str(req.buyer_id),
                "requested": req.requested,
                "status": req.status,
                "approved": req.approved,
                "rejected": req.rejected,
                "cv_owner_full_name": cv_owner_full_name,
                "recruiter_full_name": recruiter_full_name,
            })

        return {
            "status_code": 200,
            "message": "Buyer requests fetched successfully",
            "count": len(data),
            "data": data,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "message": f"Data Source Error: {str(e)}",
            "error": True,
            "status_code": 500
        }

@reserve_router.get("/selfsponsor-requests", status_code=200)
async def get_buyer_requests_for_sponsor(
    promoter_id: uuid.UUID = Query(..., description="Promoter user ID"),
    db: Session = Depends(get_db_raw)
):
    """
    Fetch all buyer requests associated with a self-sponsor (promoter).
    Each record includes:
    - CV owner full name (from CVModel via cv_id → user_id)
    - Promoter full name (from UserModel via promoter_id)
    """
    try:
        # Step 1: Validate promoter
        promoter = db.query(UserModel).filter(UserModel.id == promoter_id).first()
        if not promoter:
            raise HTTPException(status_code=404, detail="Employee not found.")

        # Step 2: Fetch buyer requests for this promoter
        requests = db.query(RecruitmentSetReserveModel).filter(
            RecruitmentSetReserveModel.promoter_id == str(promoter_id),
            RecruitmentSetReserveModel.requested.is_(True)
        ).all()

        # Step 3: Prepare response data
        data = []
        for req in requests:
            cv_owner_full_name = None
            promoter_full_name = None

            # --- Get CV owner full name ---
            cv = (
                db.query(CVModel)
                .filter(CVModel.user_id == req.cv_id)
                .first()
            )
            if cv:
                cv_owner_full_name = cv.english_full_name

            # --- Get Promoter full name ---
            promoter_full_name = (
                getattr(promoter, "english_full_name", None)
                or f"{promoter.first_name or ''} {promoter.last_name or ''}".strip()
            )
            # --- Get Buyer full name ---
            if req.buyer_id:
                buyer = (
                    db.query(UserModel)
                    .filter(UserModel.id == req.buyer_id)
                    .first()
                )
                if buyer:
                    buyer_full_name = (
                        getattr(buyer, "english_full_name", None)
                        or f"{buyer.first_name or ''} {buyer.last_name or ''}".strip()
                    )


            data.append({
                "id": str(req.id),
                "cv_id": str(req.cv_id),
                "buyer_id": str(req.buyer_id),
                "requested": req.requested,
                "status": req.status,
                "approved": req.approved,
                "rejected": req.rejected,
                "cv_owner_full_name": cv_owner_full_name,
                "buyer_full_name": buyer_full_name,
            })

        return {
            "status_code": 200,
            "message": "Buyer requests fetched successfully",
            "count": len(data),
            "data": data,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "message": f"Data Source Error: {str(e)}",
            "error": True,
            "status_code": 500
        }


@reserve_router.post("/review-buyer-request-by-id", status_code=200)
async def review_buyer_request(
    request_in: BuyerReviewRequestSchema,
    db: Session = Depends(get_db_raw)
):
    reserve = (
        db.query(RecruitmentSetReserveModel)
        .filter(
            RecruitmentSetReserveModel.id == request_in.id,
            RecruitmentSetReserveModel.requested == True,
            RecruitmentSetReserveModel.recruitment_id == str(request_in.recruiter_id)  # cast to string
        )
        .first()
    )

    if not reserve:
        raise HTTPException(status_code=404, detail="No buyer request found for this recruiter.")

    if request_in.approve:
        reserve.approved = True
        reserve.rejected = False
    else:
        reserve.approved = False
        reserve.rejected = True

    if request_in.comment:
        reserve.comment = request_in.comment

    db.commit()
    db.refresh(reserve)

    return {
        "status_code": 200,
        "message": "Buyer request reviewed successfully",
        "data": {
            "reserve_id": reserve.id,
            "cv_id": str(reserve.cv_id),
            "buyer_id": str(reserve.buyer_id),
            "approved": reserve.approved,
            "rejected": reserve.rejected,
            "comment": reserve.comment
        }
    }




@reserve_router.post("/review-buyer-request-promotion-by-id",status_code=200)
async def review_buyer_request(
    request_in: BuyerPromoterReviewRequestSchema,
    db: Session = Depends(get_db_raw)
):
    reserve = (
        db.query(RecruitmentSetReserveModel)
        .filter(
            RecruitmentSetReserveModel.id == request_in.id,
            RecruitmentSetReserveModel.requested == True,
            RecruitmentSetReserveModel.promoter_id == str(request_in.promoter_id)  # cast to string
        )
        .first()
    )

    if not reserve:
        raise HTTPException(status_code=404, detail="No buyer request found for this recruiter.")

    if request_in.approve:
        reserve.approved = True
        reserve.rejected = False
    else:
        reserve.approved = False
        reserve.rejected = True

    if request_in.comment:
        reserve.comment = request_in.comment

    db.commit()
    db.refresh(reserve)

    return {
        "status_code": 200,
        "message": "Buyer request reviewed successfully",
        "data": {
            "reserve_id": reserve.id,
            "cv_id": str(reserve.cv_id),
            "buyer_id": str(reserve.buyer_id),
            "approved": reserve.approved,
            "rejected": reserve.rejected,
            "comment": reserve.comment
        }
    }


@reserve_router.get("/buyer-approved-requests", status_code=200)
async def get_buyer_approved_requests(
    buyer_id: uuid.UUID,
    db: Session = Depends(get_db_raw)
):
    """
    Fetch all approved buyer requests.
    For each record:
    - Get CV owner name (CVModel.english_full_name via cv_id → user_id)
    - Get recruiter name (UserModel.english_full_name via recruitment_id)
    """
    try:
        reserves = (
            db.query(RecruitmentSetReserveModel)
            .filter(
                RecruitmentSetReserveModel.buyer_id == buyer_id,
                RecruitmentSetReserveModel.approved == True
            )
            .all()
        )

        results = []

        for reserve in reserves:
            cv_owner_full_name = None
            recruiter_full_name = None

            # --- Get CV English full name (from CVModel) ---
            cv = (
                db.query(CVModel)
                .filter(CVModel.user_id == reserve.cv_id)  # cv_id points to table_users.id
                .first()
            )
            if cv:
                cv_owner_full_name = cv.english_full_name

            # --- Get Recruiter English full name (from UserModel) ---
            if reserve.recruitment_id:
                recruiter = (
                    db.query(UserModel)
                    .filter(UserModel.id == reserve.recruitment_id)
                    .first()
                )
                if recruiter:
                    recruiter_full_name = (
                        getattr(recruiter, "english_full_name", None)
                        or f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()
                    )

            results.append({
                "reserve_id": reserve.id,
                "cv_id": str(reserve.cv_id),
                "buyer_id": str(reserve.buyer_id) if reserve.buyer_id else None,
                "recruitment_id": str(reserve.recruitment_id) if reserve.recruitment_id else None,
                "cv_owner_full_name": cv_owner_full_name,
                "recruiter_full_name": recruiter_full_name,
                "status": reserve.status,
                "approved": reserve.approved,
                "requested": reserve.requested,
                "rejected": reserve.rejected,
                "comment": reserve.comment,
            })

        return {
            "status_code": 200,
            "message": "Approved buyer requests fetched successfully",
            "count": len(results),
            "data": results,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "message": f"Data Source Error: {str(e)}",
            "error": True,
            "status_code": 500
        }

    
@reserve_router.post(
    "/paginated",
    response_model=GenericMultipleResponse[ReserveReadSchema],
    status_code=200,
)
# @rbac_access_checker(
#     resource=RBACResource.reserve, rbac_access_type=RBACAccessType.read_multiple
# )
async def view_reserves(
    *,
    filters: Optional[ReserveFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    search: str = None,
    start_date: str = None,
    end_date: str = None,
    request: Request,
    response: Response
) -> Any:
    """
    View paginated reserves
    """
    db = get_db_session()
    reserve_repo = ReserveRepository(entity=ReserveModel)
    reserves_read = reserve_repo.get_some(
        db,
        skip=skip,
        limit=limit,
        search=search,
        search_schema=UsersSearchSchema,
        start_date=start_date,
        end_date=end_date,
        filters=filters,
    )
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": reserves_read,
        "count": res_data.count,
    }

from fastapi import Depends
from sqlalchemy.orm import Session

@reserve_router.get(
    "/all/employee/paginated",
    response_model=None,
    status_code=200,
)
async def view_all_active_promoted_employee_cvs(
    *,
    skip: int = 0,
    limit: int = 10,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_sessions)
) -> Any:
    """
    View all CVs of actively promoted employees, no auth or filters required
    """
    reserve_repo = ReserveRepository(entity=ReserveModel)
    all_cvs = reserve_repo.get_all_active_promoted_employee_cvs(
        db=db,
        skip=skip,
        limit=limit
    )
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": all_cvs,
        "count": res_data.count,
    }



@reserve_router.post(
    "/employee/paginated",
    response_model=None,
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.cv, rbac_access_type=RBACAccessType.read_multiple
)
async def view_filtered_employee_cvs(
    *,
    search: str = None,
    filters: Optional[ReserveCVFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    request: Request,
    response: Response
) -> Any:
    """
    view filtered employee cvs
    """
    db = get_db_session()
    reserve_repo = ReserveRepository(entity=ReserveModel)
    filtered_reserves = reserve_repo.get_filtered_employee_cvs(
        db,
        skip=skip,
        limit=limit,
        filters=filters,
        search=search,
        search_schema=CVSearchSchema,
    )
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": filtered_reserves,
        "count": res_data.count,
    }



@reserve_router.post(
    "/history",
    response_model=GenericMultipleResponse[BatchReserveReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.reserve, rbac_access_type=RBACAccessType.read_multiple
)
async def view_reserve_history(
    *,
    filters: Optional[ReserveFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    request: Request,
    response: Response
) -> Any:
    """
    Retrieve paginated reserve hisotry.
    """
    db = get_db_session()
    reserve_repo = ReserveRepository(entity=ReserveModel)
    reserves_read = reserve_repo.get_reserver_reserves(
        db,
        skip=skip,
        limit=limit,
        filters=filters,
    )
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": reserves_read,
        "count": res_data.count,
    }


@reserve_router.post(
    "/my-reserves",
    # response_model=GenericMultipleResponse[ReserveReadSchema | BatchReserveReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.reserve, rbac_access_type=RBACAccessType.read_multiple
)
async def view_my_reserves(
    *,
    filters: Optional[ReserveFilterSchema] = None,
    # _=Depends(authentication_context),
    _=Depends(HTTPBearer(scheme_name="bearer")),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10
) -> Any:
    """
    Retrieve my received reserves
    """
    db = get_db_session()
    reserve_repo = ReserveRepository(entity=ReserveModel)
    reserves_read = reserve_repo.get_received_reserve_requests(
        db, skip=skip, limit=limit
    )

    data = []

    try:
        for reserve in reserves_read:
            data.append({
                "id": reserve.id,
                "reserver": {
                    "first_name": reserve.reserver.first_name,
                    "last_name": reserve.reserver.last_name,
                    "role": reserve.reserver.role,
                },
                "created_at": reserve.created_at,
                "updated_at": reserve.updated_at,
            })
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")

    return {"status_code": 200, "message": "Success", "error": False, "data": data}

@reserve_router.post(
    "/my-reserves/detail/paginated",
    # response_model=GenericMultipleResponse[ReserveReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.reserve, rbac_access_type=RBACAccessType.read_multiple
)
async def view_my_reserves_detail(
    *,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    batch_reserve_id: int,
) -> Any:
    """
    View paginated reserve requests received detail
    """
    db = get_db_session()
    reserve_repo = ReserveRepository(entity=ReserveModel)
    reserves_read = reserve_repo.get_received_reserve_requests_details(
        db,
        batch_reserve_id=batch_reserve_id,

    )
    data = []
    try:
        for reserve in reserves_read:
            data.append({
                "id": reserve.id,
                "cv_id": reserve.cv_id,
                "cv": {          
                    "id": reserve.cv.id,
                    "user_id": reserve.cv.user_id,
                    "date_of_birth": reserve.cv.date_of_birth,
                    "height": reserve.cv.height,
                    "weight": reserve.cv.weight,
                    "sex": reserve.cv.sex,
                    "skin_tone": reserve.cv.skin_tone,
                    "religion": reserve.cv.religion,
                    "marital_status": reserve.cv.marital_status,
                    "occupation": reserve.cv.occupation,
                    "nationality": reserve.cv.nationality,
                    "passport_number": reserve.cv.passport_number,
                    "english_full_name": reserve.cv.english_full_name,
                    "arabic_full_name": reserve.cv.arabic_full_name,
                    "amharic_full_name": reserve.cv.amharic_full_name,
                },
                "reason": reserve.reason,
                "status": reserve.status,
                "created_at": reserve.created_at,
            })
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")
    
    return {"status_code": 200, "message": "Success", "error": False, "data": data}


@reserve_router.patch(
    "/", response_model=GenericMultipleResponse[ReserveReadSchema], status_code=200
)
@rbac_access_checker(
    resource=RBACResource.reserve, rbac_access_type=RBACAccessType.update
)
async def accept_decline_reserve(
    *,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    reserve_update: ReserveUpdateSchema,
    request: Request,
    response: Response
) -> Any:
    """
    Update reserve status
    """
    try:
        db = get_db_session()
        reserve_repo = ReserveRepository(entity=ReserveModel)
        reserve_updated = reserve_repo.accept_decline_reserve_request(
            db, filter_obj_in=reserve_update.filter, obj_in=reserve_update.update
        )

        for reserve in reserve_updated:
            status = reserve.status.capitalize()
            name = ""

            if reserve.cv and reserve.cv.english_full_name:
                name = reserve.cv.english_full_name
            else:
                name = f"{reserve.first_name} {reserve.last_name}"

            if status == "accepted":
                title = f"Reserve Request {status}"
                description = f"Your reservation request has been successfully accepted. Please pay the reservation fee within 24 hours to access the full CV of the promoted profile."
            else:
                title = f"Reserve Request {status}"
                description = f"Your reserve request for {name} has been {status}"
           
            background_tasks.add_task(send_notification, db, reserve.reserver_id, title, description, "reserve")

            _user = db.query(UserModel).filter(UserModel.id == reserve.reserver_id).first()

            email = _user.email or _user.company.alternative_email

            background_tasks.add_task(func=send_email, email=email, title=title, description=description)

        res_data = context_set_response_code_message.get()
        response.status_code = res_data.status_code
        return {
            "status_code": res_data.status_code,
            "message": res_data.message,
            "error": res_data.error,
            "data": reserve_updated,
        }
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")


@reserve_router.get("/recruitments")
async def get_recruitment_reserves(
    country: str | None = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role != "sponsor":
            return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")

        recruitments = db.query(UserModel).filter(UserModel.role == "recruitment").all()

        if country:
            recruitments = [
                recruitment for recruitment in recruitments 
                if recruitment.company and recruitment.company.location == country
            ]

        data = []

        for recruitment in recruitments:
            if recruitment.company:
                data.append({
                    "id": recruitment.id,
                    "name": f"{recruitment.first_name} {recruitment.last_name}",
                    "company": recruitment.company.company_name,
                    "location": recruitment.company.location
                })
        return {"data": data}

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")


@reserve_router.post("/recruitment/create")
async def create_recruitment_reserve(
    data: RecruitmentReserveCreate,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role != "sponsor":
            return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")

        existing_reserve = db.query(RecruitmentReserveModel).filter(
            RecruitmentReserveModel.recruitment_id == data.recruitment_id,
            RecruitmentReserveModel.sponsor_id == user.id,
            RecruitmentReserveModel.employee_id == data.employee_id,
            RecruitmentReserveModel.status == "pending"
        ).first()

        if existing_reserve:
            return Response(
                status_code=400,
                content=json.dumps({"message": "A pending recruitment reserve with the same details already exists"}),
                media_type="application/json"
            )
        
        reserve = db.query(ReserveModel).filter(ReserveModel.owner_id == data.employee_id,
                                                 ReserveModel.reserver_id == user.id, ReserveModel.status == "paid").first()

        if not reserve:
            return Response(status_code=404, content=json.dumps({"message": "Opps! You have not reserved this employee"}), media_type="application/json")


        recruitment_reserve = RecruitmentReserveModel(
            recruitment_id=data.recruitment_id,
            sponsor_id=user.id,
            employee_id=data.employee_id,
            status="pending"
        )

        db.add(recruitment_reserve)

        db.commit()
        _user = db.query(UserModel).filter(UserModel.id == user.id).first()

        title = "Employee Process Request"
        description = f"{_user.first_name} {_user.last_name} has requested to process {reserve.cv.english_full_name}"

        background_tasks.add_task(send_notification, db, data.recruitment_id, title, description, "employee_process")

        _user = db.query(UserModel).filter(UserModel.id == data.recruitment_id).first()

        email = _user.email or _user.company.alternative_email

        background_tasks.add_task(send_email, email=email, title=title, description=description)

        return {"message": "Recruitment reserve created successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")


def create_invoice(db, ref: str, amount: float, user_id: uuid.UUID, recruitment_reserve_id: str) -> InvoiceModel:
    invoice = InvoiceModel(
        stripe_session_id=ref,
        status="pending",
        amount=amount,
        created_at=datetime.now(timezone.utc),
        type="employee_process",
        buyer_id=user_id,
        object_id=recruitment_reserve_id,
    )
    db.add(invoice)
    return invoice


def update_invoice(invoice: InvoiceModel, ref: str) -> None:
    invoice.stripe_session_id = ref


@reserve_router.get("/recruitment/payment/info/{recruitment_reserve_id}")
async def get_recruitment_payment_info(
    recruitment_reserve_id: int,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role != "recruitment":
            return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")

        recruitment_reserve = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.id == recruitment_reserve_id, RecruitmentReserveModel.recruitment_id == user.id).first()

        if not recruitment_reserve:
            return Response(status_code=404, content=json.dumps({"message": "Recruitment reserve not found"}), media_type="application/json")

        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == "recruitment", PromotionPackagesModel.category == "employee_process").first()

        if not package:
            return Response(status_code=404, content=json.dumps({"message": "Package not found"}), media_type="application/json")

        return {
            "price": package.price,
            "total_amount": package.price,
            "profile": 1
        }
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")

@reserve_router.patch("/recruitment/status")
async def update_recruitment_reserve_status(
    data: RecruitmentReserveStatusUpdate,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    db = get_db_session()
    user = context_actor_user_data.get()

    if user.role != "recruitment":
        return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")

    recruitment_reserve = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.id == data.id, RecruitmentReserveModel.recruitment_id == user.id).first()

    if not recruitment_reserve:
        return Response(status_code=404, content=json.dumps({"message": "Recruitment not found"}), media_type="application/json")

    if data.status == "declined":
        recruitment_reserve.status = "declined"

        db.commit()

        title = "Employee Process Request Declined"

        description = f"{recruitment_reserve.recruitment.first_name} {recruitment_reserve.recruitment.last_name} has declined to process {recruitment_reserve.employee.cv.english_full_name}"

        background_tasks.add_task(send_notification, db, recruitment_reserve.sponsor_id, title, description, "employee_process")

        email = recruitment_reserve.sponsor.email or recruitment_reserve.sponsor.company.company.alternative_email

        background_tasks.add_task(send_email, email=email, title=title, description=description)


        return {"message": "Recruitment reserve status updated successfully"}

    if data.status == "accepted":        
        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == "recruitment", PromotionPackagesModel.category == "employee_process").first()
        
        return_url = settings.TELR_EMPLOYEE_PROCESS_RETURN_URL.replace("replace", user.role)

        order_response = telr.order(
            order_id=f"ORDER{uuid.uuid4().hex[:8]}",
            amount=package.price,
            currency="AED",
            return_url=return_url,
            return_decl=return_url,
            return_can=return_url,
            description=f"{recruitment_reserve.employee.cv.english_full_name} Employee Process"
        )

        ref = order_response.get("order", {}).get("ref")

        if not ref:
            return Response(status_code=400, content=json.dumps({"message": "Failed to process payment"}), media_type="application/json")

        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.object_id == str(recruitment_reserve.id),
            InvoiceModel.buyer_id == user.id,
            InvoiceModel.status == "pending",
            InvoiceModel.type == "employee_process"
        ).first()

        if invoice:
            update_invoice(invoice, ref)
        else:
            invoice = create_invoice(db, ref, package.price, user.id, recruitment_reserve.id)
            db.add(invoice)

        db.commit()

        return {
            "method": order_response.get("method"),
            "trace": order_response.get("trace"),
            "order": {
                "ref": order_response.get("order", {}).get("ref"),
                "url": order_response.get("order", {}).get("url"),
            },
        }



@reserve_router.patch("/recruitment/sponsor/status")
async def update_recruitment_spnsor_reserve_status(
    data: RecruitmentReserveStatusUpdate,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    db = get_db_session()
    user = context_actor_user_data.get()

    if user.role != "recruitment":
        return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")

    recruitment_reserve = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.id == data.id, RecruitmentReserveModel.recruitment_id == user.id).first()

    if not recruitment_reserve:
        return Response(status_code=404, content=json.dumps({"message": "Recruitment not found"}), media_type="application/json")

    if data.status == "declined":
        recruitment_reserve.status = "declined"

        db.commit()

        title = "Employee Process Request Declined"

        description = f"{recruitment_reserve.recruitment.first_name} {recruitment_reserve.recruitment.last_name} has declined to process {recruitment_reserve.employee.cv.english_full_name}"

        background_tasks.add_task(send_notification, db, recruitment_reserve.sponsor_id, title, description, "employee_process")

        email = recruitment_reserve.sponsor.email or recruitment_reserve.sponsor.company.company.alternative_email

        background_tasks.add_task(send_email, email=email, title=title, description=description)


        return {"message": "Recruitment reserve status updated successfully"}

    if data.status == "accepted":        
        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == "recruitment", PromotionPackagesModel.category == "employee_process").first()
        
        return_url = settings.TELR_SPONSOR_EMPLOYEE_PROCESS_RETURN_URL.replace("replace", user.role)

        order_response = telr.order(
            order_id=f"ORDER{uuid.uuid4().hex[:8]}",
            amount=package.price,
            currency="AED",
            return_url=return_url,
            return_decl=return_url,
            return_can=return_url,
            description=f"{recruitment_reserve.employee.cv.english_full_name} Employee Process"
        )

        ref = order_response.get("order", {}).get("ref")

        if not ref:
            return Response(status_code=400, content=json.dumps({"message": "Failed to process payment"}), media_type="application/json")

        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.object_id == str(recruitment_reserve.id),
            InvoiceModel.buyer_id == user.id,
            InvoiceModel.status == "pending",
            InvoiceModel.type == "employee_process"
        ).first()

        if invoice:
            update_invoice(invoice, ref)
        else:
            invoice = create_invoice(db, ref, package.price, user.id, recruitment_reserve.id)
            db.add(invoice)

        db.commit()

        return {
            "method": order_response.get("method"),
            "trace": order_response.get("trace"),
            "order": {
                "ref": order_response.get("order", {}).get("ref"),
                "url": order_response.get("order", {}).get("url"),
            },
        }



'''
@reserve_router.post("/recruitment/status/callback")
async def update_recruitment_reserve_status_callback(data: TransferRequestPaymentCallback, background_tasks: BackgroundTasks, _=Depends(authentication_context),__=Depends(build_request_context)):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()
        status_response = telr.status(
                order_reference = data.ref
        )
        state = status_response.get("order").get("status").get("text")
        error = status_response.get("error", {})
        card_type = status_response.get("order", {}).get("card", {}).get("type")
        description = status_response.get("order", {}).get("description")
        if error:
            return Response(status_code=400, content=json.dumps({"message": error.get("note", "Failed to process payment")}), media_type="application/json")
        if state.lower()  == "pending":
            return Response(status_code=400, content=json.dumps({"message": "Payment is pending"}), media_type="application/json")
        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.stripe_session_id == data.ref,
            InvoiceModel.buyer_id == user.id,
            InvoiceModel.status == "pending",
            InvoiceModel.type == "employee_process"
        ).first()
        if not invoice:
            return Response(status_code=404, content=json.dumps({"message": "Invoice not found"}), media_type="application/json")
        recruitment_reserve = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.id == invoice.object_id).first()
        if not recruitment_reserve:
            return Response(status_code=404, content=json.dumps({"message": "Recruitment reserve not found"}), media_type="application/json")
        invoice.status = "paid"
        invoice.card = card_type
        invoice.description = description
        recruitment_reserve.status = "accepted"
        db.add(recruitment_reserve)
        db.add(invoice)
        db.commit()
        title = "Employee Process Request Accepted"
        description = f"{recruitment_reserve.recruitment.first_name} {recruitment_reserve.recruitment.last_name} has accepted to process {recruitment_reserve.employee.cv.english_full_name}"
        background_tasks.add_task(send_notification, db, recruitment_reserve.sponsor_id, title, description, "employee_process")
        email = recruitment_reserve.sponsor.email or recruitment_reserve.sponsor.company.company.alternative_email
        background_tasks.add_task(send_email, email=email, title=title, description=description)
        return {"status": "success", "message": "Payment successful"}
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")
'''

@reserve_router.post("/recruitment/status/callback")
async def update_recruitment_reserve_status_callback(data: TransferRequestPaymentCallback, background_tasks: BackgroundTasks, _=Depends(authentication_context),__=Depends(build_request_context)):
    try:
        logger.info(f"Received recruitment status callback for reference: {data.ref}")
        db = get_db_session()
        user = context_actor_user_data.get()
        
        try:
            status_response = telr.status(
                order_reference = data.ref
            )
            logger.debug(f"Telr status response: {status_response}")
        except Exception as e:
            logger.error(f"Failed to get status from Telr: {str(e)}", exc_info=True)
            return Response(
                status_code=500,
                content=json.dumps({"message": "Failed to verify payment status"}),
                media_type="application/json"
            )

        state = status_response.get("order", {}).get("status", {}).get("text")
        error = status_response.get("error", {})
        card_type = status_response.get("order", {}).get("card", {}).get("type")
        description = status_response.get("order", {}).get("description")

        if error:
            logger.error(f"Payment error: {error}")
            return Response(
                status_code=400,
                content=json.dumps({"message": error.get("note", "Failed to process payment")}),
                media_type="application/json"
            )

        if state.lower() == "pending":
            logger.info(f"Payment is pending for reference: {data.ref}")
            return Response(
                status_code=400,
                content=json.dumps({"message": "Payment is pending"}),
                media_type="application/json"
            )

        try:
            invoice = db.query(InvoiceModel).filter(
                InvoiceModel.stripe_session_id == data.ref,
                InvoiceModel.buyer_id == user.id,
                InvoiceModel.status == "pending",
                InvoiceModel.type == "employee_process"
            ).first()

            if not invoice:
                logger.error(f"Invoice not found for reference: {data.ref}")
                return Response(
                    status_code=404,
                    content=json.dumps({"message": "Invoice not found"}),
                    media_type="application/json"
                )

            recruitment_reserve = db.query(RecruitmentReserveModel).filter(
                RecruitmentReserveModel.id == invoice.object_id
            ).first()

            if not recruitment_reserve:
                logger.error(f"Recruitment reserve not found for invoice: {invoice.id}")
                return Response(
                    status_code=404,
                    content=json.dumps({"message": "Recruitment reserve not found"}),
                    media_type="application/json"
                )

            # Update invoice and recruitment reserve status
            invoice.status = "paid"
            invoice.card = card_type
            invoice.description = description
            recruitment_reserve.status = "accepted"

            db.add(recruitment_reserve)
            db.add(invoice)
            db.commit()

            logger.info(f"Successfully updated invoice {invoice.id} and recruitment reserve {recruitment_reserve.id}")

            # Send notifications
            title = "Employee Process Request Accepted"
            description = f"{recruitment_reserve.recruitment.first_name} {recruitment_reserve.recruitment.last_name} has accepted to process {recruitment_reserve.employee.cv.english_full_name}"
            
            try:
                background_tasks.add_task(send_notification, db, recruitment_reserve.sponsor_id, title, description, "employee_process")
                email = recruitment_reserve.sponsor.email or recruitment_reserve.sponsor.company.company.alternative_email
                background_tasks.add_task(send_email, email=email, title=title, description=description)
                logger.info(f"Successfully added notification tasks for recruitment reserve {recruitment_reserve.id}")
            except Exception as e:
                logger.error(f"Failed to add notification tasks: {str(e)}", exc_info=True)
                # Continue execution as notifications are not critical

            return {"status": "success", "message": "Payment successful"}

        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}", exc_info=True)
            db.rollback()
            return Response(
                status_code=500,
                content=json.dumps({"message": "Failed to process payment"}),
                media_type="application/json"
            )

    except Exception as e:
        logger.error(f"Unexpected error in recruitment status callback: {str(e)}", exc_info=True)
        return Response(
            status_code=500,
            content=json.dumps({"message": "An unexpected error occurred"}),
            media_type="application/json"
        )
'''
@reserve_router.get("/recruitment/detail")
async def get_recruitment_reserve_detail(
    recruitment_reserve_id: int,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        _user = db.query(UserModel).filter(UserModel.id == user.id).first()

        if _user.role == "recruitment":
            recruitment_reserve = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.id == recruitment_reserve_id, RecruitmentReserveModel.status == "accepted").first()
            if not recruitment_reserve:
                return Response(status_code=404, content=json.dumps({"message": "Sponsor not found"}), media_type="application/json")
            
            return {
                "phone_number": recruitment_reserve.sponsor.phone_number,
                "company_name": recruitment_reserve.sponsor.company.company_name,
                "name": f"{recruitment_reserve.sponsor.first_name} {recruitment_reserve.sponsor.last_name}",
                "email": recruitment_reserve.sponsor.email,
            }

        if _user.role == "sponsor":
            recruitment_reserve = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.id == recruitment_reserve_id, RecruitmentReserveModel.status == "accepted").first()
            if not recruitment_reserve:
                return Response(status_code=404, content=json.dumps({"message": "Sponsor not found"}), media_type="application/json")

            return {
                "phone_number": recruitment_reserve.recruitment.phone_number,
                "company_name": recruitment_reserve.recruitment.company.company_name,
                "name": f"{recruitment_reserve.recruitment.first_name} {recruitment_reserve.recruitment.last_name}",
                "email": recruitment_reserve.recruitment.email,
            }

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")
'''
'''
@reserve_router.get("/recruitment/detail")
async def get_recruitment_reserve_detail(
    recruitment_reserve_id: int,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        logger.info(f"Fetching recruitment reserve detail for ID: {recruitment_reserve_id}")
        db = get_db_session()
        user = context_actor_user_data.get()

        try:
            _user = db.query(UserModel).filter(UserModel.id == user.id).first()
            if not _user:
                logger.error(f"User not found for ID: {user.id}")
                return Response(
                    status_code=404,
                    content=json.dumps({"message": "User not found"}),
                    media_type="application/json"
                )

            logger.debug(f"User role: {_user.role}")

            if _user.role == "recruitment":
                logger.info(f"Fetching sponsor details for recruitment user {user.id}")
                recruitment_reserve = db.query(RecruitmentReserveModel).filter(
                    RecruitmentReserveModel.id == recruitment_reserve_id,
                    RecruitmentReserveModel.status == "accepted"
                ).first()

                if not recruitment_reserve:
                    logger.error(f"Recruitment reserve not found for ID: {recruitment_reserve_id}")
                    return Response(
                        status_code=404,
                        content=json.dumps({"message": "Recruitment reserve not found"}),
                        media_type="application/json"
                    )

                logger.info(f"Successfully retrieved sponsor details for recruitment reserve {recruitment_reserve_id}")
                return {
                    "phone_number": recruitment_reserve.sponsor.phone_number,
                    "company_name": recruitment_reserve.sponsor.company.company_name,
                    "name": f"{recruitment_reserve.sponsor.first_name} {recruitment_reserve.sponsor.last_name}",
                    "email": recruitment_reserve.sponsor.email,
                }

            if _user.role == "sponsor":
                logger.info(f"Fetching recruitment details for sponsor user {user.id}")
                recruitment_reserve = db.query(RecruitmentReserveModel).filter(
                    RecruitmentReserveModel.id == recruitment_reserve_id,
                    RecruitmentReserveModel.status == "accepted"
                ).first()

                if not recruitment_reserve:
                    logger.error(f"Recruitment reserve not found for ID: {recruitment_reserve_id}")
                    return Response(
                        status_code=404,
                        content=json.dumps({"message": "Recruitment reserve not found"}),
                        media_type="application/json"
                    )

                logger.info(f"Successfully retrieved recruitment details for recruitment reserve {recruitment_reserve_id}")
                return {
                    "phone_number": recruitment_reserve.recruitment.phone_number,
                    "company_name": recruitment_reserve.recruitment.company.company_name,
                    "name": f"{recruitment_reserve.recruitment.first_name} {recruitment_reserve.recruitment.last_name}",
                    "email": recruitment_reserve.recruitment.email,
                }

            logger.error(f"Invalid user role: {_user.role}")
            return Response(
                status_code=403,
                content=json.dumps({"message": "Invalid user role"}),
                media_type="application/json"
            )

        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}", exc_info=True)
            return Response(
                status_code=500,
                content=json.dumps({"message": "Failed to fetch recruitment reserve details"}),
                media_type="application/json"
            )

    except Exception as e:
        logger.error(f"Unexpected error in get_recruitment_reserve_detail: {str(e)}", exc_info=True)
        return Response(
            status_code=500,
            content=json.dumps({"message": "An unexpected error occurred"}),
            media_type="application/json"
        )

'''
@reserve_router.get("/recruitment/detail")
async def get_recruitment_reserve_detail(
    recruitment_reserve_id: int,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        logger.info(f"Fetching recruitment reserve detail for ID: {recruitment_reserve_id}")
        db = get_db_session()
        user = context_actor_user_data.get()

        try:
            _user = db.query(UserModel).filter(UserModel.id == user.id).first()
            if not _user:
                logger.error(f"User not found for ID: {user.id}")
                return Response(
                    status_code=404,
                    content=json.dumps({"message": "User not found"}),
                    media_type="application/json"
                )

            logger.debug(f"User role: {_user.role}")

            if _user.role == "recruitment":
                logger.info(f"Fetching sponsor details for recruitment user {user.id}")
                recruitment_reserve = db.query(RecruitmentReserveModel).filter(
                    RecruitmentReserveModel.id == recruitment_reserve_id,
                    RecruitmentReserveModel.status == "accepted"
                ).first()

                if not recruitment_reserve:
                    logger.error(f"Recruitment reserve not found for ID: {recruitment_reserve_id}")
                    return Response(
                        status_code=404,
                        content=json.dumps({"message": "Recruitment reserve not found"}),
                        media_type="application/json"
                    )

                # Safely get sponsor details with null checks
                sponsor = recruitment_reserve.sponsor
                company = sponsor.company if sponsor else None
                
                logger.info(f"Successfully retrieved sponsor details for recruitment reserve {recruitment_reserve_id}")
                return {
                    "phone_number": sponsor.phone_number if sponsor else None,
                    "company_name": company.company_name if company else None,
                    "name": f"{sponsor.first_name} {sponsor.last_name}".strip() if sponsor else None,
                    "email": sponsor.email if sponsor else None,
                }

            if _user.role == "sponsor":
                logger.info(f"Fetching recruitment details for sponsor user {user.id}")
                recruitment_reserve = db.query(RecruitmentReserveModel).filter(
                    RecruitmentReserveModel.id == recruitment_reserve_id,
                    RecruitmentReserveModel.status == "accepted"
                ).first()

                if not recruitment_reserve:
                    logger.error(f"Recruitment reserve not found for ID: {recruitment_reserve_id}")
                    return Response(
                        status_code=404,
                        content=json.dumps({"message": "Recruitment reserve not found"}),
                        media_type="application/json"
                    )

                # Safely get recruitment details with null checks
                recruitment = recruitment_reserve.recruitment
                company = recruitment.company if recruitment else None
                
                logger.info(f"Successfully retrieved recruitment details for recruitment reserve {recruitment_reserve_id}")
                return {
                    "phone_number": recruitment.phone_number if recruitment else None,
                    "company_name": company.company_name if company else None,
                    "name": f"{recruitment.first_name} {recruitment.last_name}".strip() if recruitment else None,
                    "email": recruitment.email if recruitment else None,
                }

            logger.error(f"Invalid user role: {_user.role}")
            return Response(
                status_code=403,
                content=json.dumps({"message": "Invalid user role"}),
                media_type="application/json"
            )

        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}", exc_info=True)
            return Response(
                status_code=500,
                content=json.dumps({"message": "Failed to fetch recruitment reserve details"}),
                media_type="application/json"
            )

    except Exception as e:
        logger.error(f"Unexpected error in get_recruitment_reserve_detail: {str(e)}", exc_info=True)
        return Response(
            status_code=500,
            content=json.dumps({"message": "An unexpected error occurred"}),
            media_type="application/json"
        )     
'''
@reserve_router.get("/recruitment/income", response_model=list[RecruitmentReserveReadSchema])
async def get_recruitment_income(
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()
        recruitment_reserves = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.recruitment_id == user.id).all()
        if not recruitment_reserves:
            return Response(status_code=404, content=json.dumps({"message": "Recruitment reserves not found"}), media_type="application/json")
        return recruitment_reserves
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")
'''

@reserve_router.get("/recruitment/income", response_model=list[RecruitmentReserveReadSchema])
async def get_recruitment_income(
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()
        recruitment_reserves = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.recruitment_id == user.id).all()
        return recruitment_reserves or []
    except Exception as e:
        logger.error(f"Error in get_recruitment_income: {str(e)}", exc_info=True)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")

'''

@reserve_router.get("/recruitment/process", response_model=list[RecruitmentReserveReadSchema])
async def get_recruitment_process(
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()

        user = context_actor_user_data.get()

        recruitment_reserves = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.sponsor_id == user.id).all()
        
        if not recruitment_reserves:
            return Response(status_code=404, content=json.dumps({"message": "Recruitment reserves not found"}), media_type="application/json")


        return recruitment_reserves
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")

'''
@reserve_router.get("/recruitment/process", response_model=list[RecruitmentReserveReadSchema])
async def get_recruitment_process(
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()
        recruitment_reserves = db.query(RecruitmentReserveModel).filter(RecruitmentReserveModel.sponsor_id == user.id).all()
        return recruitment_reserves or []
    except Exception as e:
        logger.error(f"Error in get_recruitment_process: {str(e)}", exc_info=True)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")
    
@reserve_router.post("/info")
async def reserve_info(
    data: ReservePay,
    _=Depends(authentication_context),
    __=Depends(build_request_context),

):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if not user:
            return Response(status_code=404, content=json.dumps({"message": "User not found"}), media_type="application/json")

        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == user.role, PromotionPackagesModel.category == "reservation").first()

        reservations = db.query(ReserveModel).filter(
                ReserveModel.id.in_(data.metadata.reserve_ids),
                ReserveModel.reserver_id == user.id,
                ReserveModel.status == "accepted"
        ).all()
        
        if not reservations:
            return Response(status_code=404, content=json.dumps({"message": "Reservations not found"}), media_type="application/json")

        amount = package.price * len(reservations)


        return {
            "price": package.price,
            "total_amount": amount,
            "profile": len(reservations)
        }

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")

'''
@reserve_router.get("/company/info/{reserve_batch_id}")
async def reserve_company_info(
    reserve_batch_id: int,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role != "employee":
            return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")

        reserve_batch = db.query(BatchReserveModel).filter(BatchReserveModel.id == reserve_batch_id).first()

        if not reserve_batch:
            return Response(status_code=404, content=json.dumps({"message": "Reserve batch not found"}), media_type="application/json")
 
        if not reserve_batch.reserves or len(reserve_batch.reserves) == 0:
            return Response(status_code=404, content=json.dumps({"message": "Reserves not found"}), media_type="application/json")

        reserve_request = reserve_batch.reserves[0]

        if reserve_request.owner_id != user.id:
            return Response(status_code=403, content=json.dumps({"message": "Oops! You are not the owner of this reserve request"}), media_type="application/json")

        return {
            "batch_id": reserve_batch.id,
            "reserve_id": reserve_request.id,
            "company_name": reserve_request.reserver.company.company_name,
            "name": f"{reserve_request.reserver.first_name} {reserve_request.reserver.last_name}",
            "status": reserve_request.status,
            "reason": reserve_request.reason,
            "cv_id": reserve_request.owner.cv.id
        }

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")


'''


from sqlalchemy.orm import joinedload
from fastapi import Depends, Response

@reserve_router.get("/company/info/{reserve_batch_id}")
async def reserve_company_info(
    reserve_batch_id: int,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        logger.info(f"Starting reserve_company_info for batch_id: {reserve_batch_id}")
        db = get_db_session()
        user = context_actor_user_data.get()
        logger.info(f"User {user.id} (role: {user.role}) requesting company info")
        ''''
        if user.role != "employee":
            logger.warning(f"User {user.id} with role {user.role} attempted to access employee-only endpoint")
            return Response(status_code=403, content=json.dumps({"message": "Forbidden"}), media_type="application/json")
        '''
        reserve_batch = (
            db.query(BatchReserveModel)
            .options(
                joinedload(BatchReserveModel.reserves)
                .joinedload(ReserveModel.reserver)
                .joinedload(UserModel.company),
                joinedload(BatchReserveModel.reserves)
                .joinedload(ReserveModel.owner)
                .joinedload(UserModel.cv)
            )
            .filter(BatchReserveModel.id == reserve_batch_id)
            .first()
        )

        if not reserve_batch:
            logger.warning(f"Reserve batch {reserve_batch_id} not found")
            return Response(status_code=404, content=json.dumps({"message": "Reserve batch not found"}), media_type="application/json")
 
        if not reserve_batch.reserves or len(reserve_batch.reserves) == 0:
            logger.warning(f"No reserves found for batch {reserve_batch_id}")
            return Response(status_code=404, content=json.dumps({"message": "Reserves not found"}), media_type="application/json")

        reserve_request = reserve_batch.reserves[0]
        logger.info(f"Processing reserve request {reserve_request.id}")

        if reserve_request.owner_id != user.id:
            logger.warning(f"User {user.id} attempted to access reserve request owned by {reserve_request.owner_id}")
            return Response(status_code=403, content=json.dumps({"message": "Oops! You are not the owner of this reserve request"}), media_type="application/json")

        # Build response with null values for missing data
        response_data = {
            "batch_id": reserve_batch.id,
            "reserve_id": reserve_request.id,
            "company_name": reserve_request.reserver.company.company_name if reserve_request.reserver.company else None,
            "name": f"{reserve_request.reserver.first_name} {reserve_request.reserver.last_name}" if reserve_request.reserver.first_name and reserve_request.reserver.last_name else None,
            "status": reserve_request.status,
            "reason": reserve_request.reason,
            "cv_id": reserve_request.owner.cv.id if reserve_request.owner and reserve_request.owner.cv else None
        }

        logger.info(f"Successfully processed request for batch {reserve_batch_id}")
        return response_data

    except Exception as e:
        logger.error(f"Error in reserve_company_info for batch {reserve_batch_id}: {str(e)}", exc_info=True)
        return Response(status_code=400, content=json.dumps({"message": "An error occurred"}), media_type="application/json")
    