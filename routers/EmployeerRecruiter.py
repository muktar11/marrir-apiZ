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
from sqlalchemy.orm import aliased
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import UUID

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

from sqlalchemy import select, exists, and_
from sqlalchemy import select, exists, and_, cast
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

logger = logging.getLogger(__name__)

recruiter_reserve_employeer_router_prefix = version_prefix + "recruiter_reserve_employeer"

recruiter_reserve_employeer_router = APIRouter(prefix=recruiter_reserve_employeer_router_prefix)

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

# it shows search result for reservation
@recruiter_reserve_employeer_router.get("/reserve-promotion-set-for-employeer", status_code=200)
async def get_promoted_cvs(
    nationality: Optional[str] = Query(None, description="Filter promoted CVs by nationality"),
    recruiter_residence: Optional[str] = Query(None, description="Filter promoted CVs by recruiter residence"),
    db: Session = Depends(get_db_raw)
):
   
    # Base query: Promotion → User → CV

    

    
    query = (db.query(CVModel))
        # Filter nationality
    if nationality:
            query = query.filter(
                CVModel.nationality.ilike(f"%{nationality}%")
            )




    if recruiter_residence and recruiter_residence.lower() != "null":
        query = query.filter(
            UserModel.country.ilike(f"%{recruiter_residence}%")
        )

            

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



    # ✅ Execute final query
    results = query.all()

    # Format response
    data = [
        {
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
        for cv in results
    ]

    return {
        "status_code": 200,
        "message": "Promoted CVs fetched successfully",
        "error": False,
        "count": len(data),
        "data": data,
    }

'''

from sqlalchemy import cast, exists, and_, select
from sqlalchemy.dialects.postgresql import UUID


'''
@recruiter_reserve_employeer_router.get(
    "/reserve-promotion-set-for-employeer",
    status_code=200
)
async def get_promoted_cvs(
    nationality: Optional[str] = Query(None),
    recruiter_residence: Optional[str] = Query(None),
    db: Session = Depends(get_db_raw)
):
    """
    Retrieve CVs excluding:
    - any record in RecruitmentSetReserveModel (reserved/approved/pending)
    - any record in RecruitmentAgentPrivateReserveModel (regardless of status)
    """

    # ✅ JOIN UserModel (for recruiter_residence filter)
    query = db.query(CVModel).join(UserModel, UserModel.id == CVModel.user_id)

    # ✅ Filter nationality
    if nationality:
        query = query.filter(CVModel.nationality.ilike(f"%{nationality}%"))

    # ✅ Filter recruiter residence
    if recruiter_residence and recruiter_residence.lower() != "null":
        query = query.filter(UserModel.country.ilike(f"%{recruiter_residence}%"))

    # ✅ Exclude RecruitmentSetReserveModel (reserved/approved/pending)
    query = query.filter(
        ~exists(
            select(1).where(
                and_(
                    cast(RecruitmentSetReserveModel.cv_id, UUID) == CVModel.user_id,
                    RecruitmentSetReserveModel.status.in_(["reserved", "APPROVED", "PENDING"])
                )
            )
        )
    )

    # ✅ Exclude all private reserves (regardless of status)
    query = query.filter(
        ~exists(
            select(1).where(
                cast(
                    RecruitmentAgentPrivateReserveModel.employee_id,
                    UUID
                ) == CVModel.user_id
            )
        )
    )

    results = query.all()

    # Format response
    data = [
        {
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
        for cv in results
    ]

    return {
        "status_code": 200,
        "message": "Available CVs fetched successfully",
        "error": False,
        "count": len(data),
        "data": data,
    }
'''

from pydantic import BaseModel

class ApproveAgencyReserveSchema(BaseModel):
    with_passport: bool


from sqlalchemy.orm import aliased
from sqlalchemy import and_, exists, cast
from sqlalchemy.dialects.postgresql import UUID

@recruiter_reserve_employeer_router.get(
    "/reserve-promotion-set-for-employeer",
    status_code=200
)
async def get_promoted_cvs(
    nationality: Optional[str] = Query(None),
    recruiter_residence: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db_raw)
):

    # 🔹 alias for creator user
    CreatorUser = aliased(UserModel)
    # 🔹 Main query with JOIN and LEFT JOIN for creator
    query = (
        db.query(CVModel, CreatorUser.role.label("creator_role"))
        .join(UserModel, UserModel.id == CVModel.user_id)
        .outerjoin(
            CreatorUser,
            CreatorUser.id == func.cast(CVModel.creator_id, UUID)
        )
    )

    # ✅ Filter nationality
    if nationality:
        query = query.filter(CVModel.nationality.ilike(f"%{nationality}%"))

    # ✅ Filter recruiter residence
    if recruiter_residence:
        query = query.filter(CompanyInfoModel.location.ilike(f"%{recruiter_residence}%"))

    # ✅ Filter category
    #if category:
    #    query = query.filter(CVModel.employment_types.ilike(f"%{category}%"))

    if category:
        query = query.filter(
            or_(
                CVModel.employment_types.ilike(f"{{{category}}}"),            # only one value
                CVModel.employment_types.ilike(f"{{{category},%"),            # at start
                CVModel.employment_types.ilike(f"%,{category},%"),            # middle
                CVModel.employment_types.ilike(f"%,{category}}}")             # at end
            )
        )

    # ✅ Exclude RecruitmentSetReserveModel
    query = query.filter(
        ~exists(
           select(1).where(
                and_(
                    cast(RecruitmentSetReserveModel.cv_id, UUID) == CVModel.user_id,
                    RecruitmentSetReserveModel.status.in_(["reserved", "APPROVED", "PENDING"])
                )
            )
        )
    )

    # ✅ Exclude all private reserves
    query = query.filter(
        ~exists(
            select(1).where(
                cast(
                    RecruitmentAgentPrivateReserveModel.employee_id,
                    UUID
                ) == CVModel.user_id
            )
        )
    )

    results = query.all()
    data = []
    for cv, creator_role in results:
        data.append({
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
                "creator_id": cv.creator_id,
                "creator_role": creator_role if cv.creator_id else None
            }
        })

    return {
        "status_code": 200,
        "message": "Available CVs fetched successfully",
        "error": False,
        "count": len(data),
        "data": data,
    }
from uuid import UUID
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID
"""
@recruiter_reserve_employeer_router.post("/private-reserve-employeer", status_code=201)
async def sponsor_create_private_reserve(
    payload: PrivateReserveCreateSchema,
    db: Session = Depends(get_db_raw),
):
    
    sponsor_id = payload.sponsor_id
    employee_id = payload.employee_id
    recruitment_id = payload.recruitment_id

    # Check duplicate for sponsor + employee
    existing = db.query(RecruitmentAgentPrivateReserveModel).filter_by(
        sponsor_id=sponsor_id,
        employee_id=employee_id
    ).first()

    if existing:
        return {
            "status_code": 200,
            "message": "Reservation already exists (sponsor)",
            "error": False,
            "data": {
                "recruitment_id": existing.recruitment_id,
                "sponsor_id": existing.sponsor_id,
                "employee_id": existing.employee_id,
                "status": existing.status
            }
        }

    # Create new reservation
    new_reserve = RecruitmentAgentPrivateReserveModel(
        recruitment_id=recruitment_id,
        sponsor_id=sponsor_id,
        employee_id=str(employee_id),
        agent_id=None  # Agent not part of this endpoint
    )

    db.add(new_reserve)
    db.commit()
    db.refresh(new_reserve)

    return {
        "status_code": 201,
        "message": "Private reservation created successfully by sponsor",
        "error": False,
        "data": {
            "recruitment_id": new_reserve.recruitment_id,
            "sponsor_id": new_reserve.sponsor_id,
            "employee_id": new_reserve.employee_id,
            "status": new_reserve.status
        }
    }
"""

@recruiter_reserve_employeer_router.post(
    "/private-reserve-employeer",
    status_code=201
)
async def sponsor_create_private_reserve(
    payload: PrivateReserveCreateSchema,
    db: Session = Depends(get_db_raw),
):
    """
    Sponsor creates a private reservation.
    """


    # Ensure at least one target exists
    if not payload.employee_id and not payload.recruitment_id and not payload.agent_id and not payload.selfsponsor_id:
        raise HTTPException(
            status_code=400,
            detail="One of employee_id, recruitment_id, agent_id or selfsponsor_id must be provided"
        )

    # Check duplicate correctly based on type
    existing = db.query(RecruitmentAgentPrivateReserveModel).filter(
        RecruitmentAgentPrivateReserveModel.sponsor_id == payload.sponsor_id,
        RecruitmentAgentPrivateReserveModel.selfsponsor_id == payload.selfsponsor_id,
        RecruitmentAgentPrivateReserveModel.employee_id == payload.employee_id,
        RecruitmentAgentPrivateReserveModel.recruitment_id == payload.recruitment_id,
        RecruitmentAgentPrivateReserveModel.agent_id == payload.agent_id,
    ).first()

    if existing:
        return {
            "status_code": 200,
            "message": "Reservation already exists",
            "error": False,
            "data": {
                "recruitment_id": existing.recruitment_id,
                "sponsor_id": existing.sponsor_id,
                "employee_id": existing.employee_id,
                "agent_id": existing.agent_id,
                "status": existing.status
            }
        }

    # Create new reservation
    new_reserve = RecruitmentAgentPrivateReserveModel(
        sponsor_id=payload.sponsor_id,
        selfsponsor_id=payload.selfsponsor_id,
        employee_id=payload.employee_id,
        recruitment_id=payload.recruitment_id,
        agent_id=payload.agent_id
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
            "sponsor_id": new_reserve.sponsor_id,
            "employee_id": new_reserve.employee_id,
            "agent_id": new_reserve.agent_id,
            "selfsponsor_id": new_reserve.selfsponsor_id,
            "status": new_reserve.status
        }
    }

@recruiter_reserve_employeer_router.get("/employee/pending-reserves/recruiter-request", status_code=200)
async def get_pending_reserves_recruiter(
    employee_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Return pending reserves created by RECRUITERS only.
    Conditions:
    - recruitment_id IS NOT NULL
    - agent_id IS NULL
    - sponsor_id IS NULL
    """
    
    pending_reserves = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.employee_id == employee_id,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.agent_id.is_(None),
            RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None)
        )
        .all()
    )

    data = []
    for r in pending_reserves:
        recruiter_name = None

        if r.recruitment_id:
            recruiter = db.query(UserModel).filter(UserModel.id == r.recruitment_id).first()
            if recruiter:
                recruiter_name = getattr(recruiter, "english_full_name", None) or \
                                 f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()

        data.append({
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "recruitment_name": recruiter_name,
            "employee_id": r.employee_id,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Recruiter-created pending reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }




from uuid import UUID
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID



from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError


import uuid
from fastapi import HTTPException

# for self sponsor to see employer created pending reserves, which have no recruitment_id and no agent_id, but have sponsor_id
@recruiter_reserve_employeer_router.get("/employee/pending-reserves/employer-request", status_code=200)
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
            RecruitmentAgentPrivateReserveModel.sponsor_id == employee_id,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.agent_id.is_(None),
            RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None)
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

#for recruitemnt to see employer created pending reserves, which have no sponsor_id and no agent_id, but have recruitment_id
@recruiter_reserve_employeer_router.get(
    "/recruitment/pending-reserves/employer-request",
    status_code=200
)
async def get_pending_employer_reserves_for_recruitment(
    recruiter_id: str,   # receive as string from query
    db: Session = Depends(get_db_raw)
):
    # Convert string to UUID
    try:
        recruiter_uuid = uuid.UUID(recruiter_id)
        print(f"Converted recruiter_id to UUID: {recruiter_uuid}")
    except ValueError:
        return {
            "status_code": 400,
            "message": "Invalid recruiter_id format",
            "error": True,
        }

    pending_reserves = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.recruitment_id == recruiter_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.agent_id.is_(None),
        )
        .all()
    )

    all_reserves = db.query(RecruitmentAgentPrivateReserveModel).all()
    for r in all_reserves:
        print(r.id, r.sponsor_id, r.agent_id, r.recruitment_id, r.status)
    
    data = []
    for r in pending_reserves:

        # Get recruiter name
        recruiter_name = None
        if r.recruitment_id:
            recruiter = (
                db.query(UserModel)
                .filter(UserModel.id == r.recruitment_id)
                .first()
            )
            if recruiter:
                recruiter_name = (
                    getattr(recruiter, "english_full_name", None)
                    or f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip()
                )

        data.append({
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "recruitment_name": recruiter_name,
            "sponsor_id": r.sponsor_id,  # should be None
            "sponsor_name": None,        # always None in this case
            "employee_id": r.employee_id,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Employer private reservations for recruitment fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


#for agent to see employer created pending reserves, which have no sponsor_id and no recruitment_id, but have agent_id
@recruiter_reserve_employeer_router.get(
    "/agent/pending-reserves/employer-request",
    status_code=200
)
async def get_pending_employer_reserves_for_recruitment(
    agent_id: str,   # receive as string from query
    db: Session = Depends(get_db_raw)
):
    # Convert string to UUID
    try:
        agent_uuid = uuid.UUID(agent_id)
        print(f"Converted agent_id to UUID: {agent_uuid}")
    except ValueError:
        return {
            "status_code": 400,
            "message": "Invalid agent_id format",
            "error": True,
        }

    pending_reserves = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.agent_id == agent_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None),
        )
        .all()
    )

    all_reserves = db.query(RecruitmentAgentPrivateReserveModel).all()
    for r in all_reserves:
        print(r.id, r.sponsor_id, r.agent_id, r.recruitment_id, r.status)
    
    data = []
    for r in pending_reserves:

        # Get agent name
        agent_name = None
        if r.agent_id:
            agent = (
                db.query(UserModel)
                .filter(UserModel.id == r.agent_id)
                .first()
            )
            if agent:
                recruiter_name = (
                    getattr(agent, "english_full_name", None)
                    or f"{agent.first_name or ''} {agent.last_name or ''}".strip()
                )

        data.append({
            "id": r.id,
            "recruitment_id": r.recruitment_id,
            "recruitment_name": recruiter_name,
            "sponsor_id": r.sponsor_id,  # should be None
            "sponsor_name": None,        # always None in this case
            "employee_id": r.employee_id,
            "agent_id": r.agent_id,
            "agent_name": agent_name,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Employer private reservations for recruitment fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


#for employee to retireve approved requests coming from employer, which have no recruitment_id and no agent_id, but have sponsor_id, and status is accepted
@recruiter_reserve_employeer_router.get(
    "/selfsponsor/my-reserve-requests-all",
    status_code=200
)
async def get_employer_reserve_requests(
    employer_id: str,
    db: Session = Depends(get_db_raw)
):

    Employee = aliased(UserModel)
    Recruitment = aliased(UserModel)
    Agent = aliased(UserModel)

    reserves = (
        db.query(
            RecruitmentAgentPrivateReserveModel,
            Employee,
            Recruitment,
            Agent
        )
        .outerjoin(
            Employee,
            Employee.id == cast(
                RecruitmentAgentPrivateReserveModel.employee_id,
                UUID
            )
        )
        .outerjoin(
            Recruitment,
            Recruitment.id == RecruitmentAgentPrivateReserveModel.recruitment_id
        )
        .outerjoin(
            Agent,
            Agent.id == RecruitmentAgentPrivateReserveModel.agent_id
        )
        .filter(
            RecruitmentAgentPrivateReserveModel.sponsor_id == cast(employer_id, UUID)
        )
        .order_by(
            RecruitmentAgentPrivateReserveModel.created_at.desc()
        )
        .all()
    )

    data = []

    for reserve, employee, recruitment, agent in reserves:

        def get_name(user):
            if not user:
                return None
            return (
                getattr(user, "english_full_name", None)
                or f"{user.first_name or ''} {user.last_name or ''}".strip()
            )

        data.append({
            "reserve_id": reserve.id,
            "employee_id": reserve.employee_id,
            "employee_name": get_name(employee),
            "recruitment_id": reserve.recruitment_id,
            "recruitment_name": get_name(recruitment),
            "agent_id": reserve.agent_id,
            "agent_name": get_name(agent),
            "status": reserve.status,
            "created_at": reserve.created_at,
            "updated_at": reserve.updated_at
        })

    return {
        "status_code": 200,
        "message": "Employer reservation requests fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }




#for selfsponsor to retireve approved requests coming from Employyer Company, which have no recruitment_id and no employee_id, but have selfsponsor_id, and status is accepted
@recruiter_reserve_employeer_router.get(
    "/selfsponsor/compnay/my-reserve-requests-all",
    status_code=200
)
async def get_employeer_company_reserve_requests(
    employer_id: str,
    db: Session = Depends(get_db_raw)
):

    Employee = aliased(UserModel)
    Recruitment = aliased(UserModel)
    Employeer = aliased(UserModel)
    employeer_uuid = uuid.UUID(employer_id)
    print("Passed employeer_uuid:", employeer_uuid)
    all_reserves = db.query(RecruitmentAgentPrivateReserveModel).all()

    for r in all_reserves:
        print("ID:", r.id)
        print("employee_id:", r.employee_id)
        print("agent_id:", r.agent_id)
        print("sponsor_id:", r.sponsor_id)
        print("selfsponsor_id:", r.selfsponsor_id)
        print("recruitment_id:", r.recruitment_id)
        print("status:", r.status)
        print("created_at:", r.created_at)
        print("-----")


    reserves = (
    db.query(
        RecruitmentAgentPrivateReserveModel,
        Employee,
        Recruitment,
        Employeer
    )
    .outerjoin(
        Employee,
        Employee.id == cast(
            RecruitmentAgentPrivateReserveModel.employee_id,
            UUID
        )
    )
    .outerjoin(
        Recruitment,
        Recruitment.id == RecruitmentAgentPrivateReserveModel.recruitment_id
    )
    .outerjoin(
        Employeer,
        Employeer.id == RecruitmentAgentPrivateReserveModel.selfsponsor_id
    )
    .filter(
        RecruitmentAgentPrivateReserveModel.selfsponsor_id == employeer_uuid,
        RecruitmentAgentPrivateReserveModel.status == "pending",
        #RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None),
        #RecruitmentAgentPrivateReserveModel.employee_id.is_(None)
    )
    .order_by(
        RecruitmentAgentPrivateReserveModel.created_at.desc()
    )
    .all()
)
    
    data = []

    for reserve, employee, recruitment, employeer in reserves:

        def get_name(user):
            if not user:
                return None
            return (
                getattr(user, "english_full_name", None)
                or f"{user.first_name or ''} {user.last_name or ''}".strip()
            )

        data.append({
            "reserve_id": reserve.id,
            "employee_id": reserve.employee_id,
            "employee_name": get_name(employee),
            "recruitment_id": reserve.recruitment_id,
            "recruitment_name": get_name(recruitment),
            "agent_id": reserve.agent_id,
            "agent_name": get_name(employeer),  # you may want to fix naming here
            "status": reserve.status,
            "created_at": reserve.created_at,
            "updated_at": reserve.updated_at
        })

    return {
        "status_code": 200,
        "message": "Employyer Company reservation requests fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


#selfsponsor to approve employer created pending reserve, which have no recruitment_id and no agent_id, but have sponsor_id
@recruiter_reserve_employeer_router.put(
    "/selfsponsor/pending-reserves/employer-request/approval", status_code=200
)
async def approve_sponsor_private_reserve_for_selfsponsor(
    reserve_id: int,   # ✅ FIX HERE
    payload: ApproveAgencyReserveSchema,
    db: Session = Depends(get_db_raw),
):
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.id == reserve_id,  # ✅ FIX
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
        )
        .first()
    )

    if not reserve:
        raise HTTPException(
            status_code=404,
            detail="Pending reservation not found"
        )

    reserve.with_passport = payload.with_passport
    reserve.status = TransferStatusSchema.ACCEPTED

    try:
        db.commit()
        db.refresh(reserve)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status_code": 200,
        "message": "Approved successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "status": reserve.status,
        },
    }



@recruiter_reserve_employeer_router.get(
    "/all/pending-reserves/reserves/incoming",
    status_code=200
)
async def get_accepted_reserves_by_role(
    user_id: str,  # UUID of current user
    role: str,     # "recruiter" | "agent" | "sponsor"
    db: Session = Depends(get_db_raw)
):
    """
    Retrieve ACCEPTED RecruitmentAgentPrivateReserveModel by role.
    """

    # Validate UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    # Base query: only ACCEPTED reserves

    user_uuid = str(uuid.UUID(user_id))
    query = db.query(RecruitmentAgentPrivateReserveModel).filter(
        RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING
    )

    if role == "recruiter":
        query = query.filter(
            RecruitmentAgentPrivateReserveModel.recruitment_id == cast(user_uuid, pgUUID)
        )
    elif role == "agent":
        query = query.filter(
            RecruitmentAgentPrivateReserveModel.agent_id == cast(user_uuid, pgUUID)
        )
    elif role == "sponsor":
        query = query.filter(
            RecruitmentAgentPrivateReserveModel.sponsor_id == cast(user_uuid, pgUUID)
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Execute query
    try:
        reserves = query.order_by(
            RecruitmentAgentPrivateReserveModel.created_at.desc()
        ).all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Build response
    data = []
    for reserve in reserves:
        data.append({
            "reserve_id": reserve.id,
            "recruitment_id": reserve.recruitment_id,
            "agent_id": reserve.agent_id,
            "sponsor_id": reserve.sponsor_id,
            "selfsponsor_id": reserve.selfsponsor_id,
            "employee_id": reserve.employee_id,
            "status": reserve.status,
            "with_passport": reserve.with_passport,
            "price": reserve.price,
            "created_at": reserve.created_at,
            "updated_at": reserve.updated_at,
        })

    return {
        "status_code": 200,
        "message": f"{role} accepted reserves fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }



@recruiter_reserve_employeer_router.get(
    "/selfsponsor/pending-reserves/reserves/accepted",
    status_code=200
)
async def get_accepted_reserves_by_role(
    user_id: str,  # UUID of current user
    role: str,     # "recruiter" | "agent" | "sponsor"
    db: Session = Depends(get_db_raw)
):
    """
    Retrieve ACCEPTED RecruitmentAgentPrivateReserveModel by role.
    """

    # Validate UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    # Base query: only ACCEPTED reserves

    user_uuid = str(uuid.UUID(user_id))
    query = db.query(RecruitmentAgentPrivateReserveModel).filter(
        RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.ACCEPTED
    )

    if role == "recruiter":
        query = query.filter(
            RecruitmentAgentPrivateReserveModel.recruitment_id == cast(user_uuid, pgUUID)
        )
    elif role == "agent":
        query = query.filter(
            RecruitmentAgentPrivateReserveModel.agent_id == cast(user_uuid, pgUUID)
        )
    elif role == "sponsor":
        query = query.filter(
            RecruitmentAgentPrivateReserveModel.sponsor_id == cast(user_uuid, pgUUID)
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Execute query
    try:
        reserves = query.order_by(
            RecruitmentAgentPrivateReserveModel.created_at.desc()
        ).all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Build response
    data = []
    for reserve in reserves:
        data.append({
            "reserve_id": reserve.id,
            "recruitment_id": reserve.recruitment_id,
            "agent_id": reserve.agent_id,
            "sponsor_id": reserve.sponsor_id,
            "selfsponsor_id": reserve.selfsponsor_id,
            "employee_id": reserve.employee_id,
            "status": reserve.status,
            "with_passport": reserve.with_passport,
            "price": reserve.price,
            "created_at": reserve.created_at,
            "updated_at": reserve.updated_at,
        })

    return {
        "status_code": 200,
        "message": f"{role} accepted reserves fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }


HYPERPAY_BASE_URL = "https://eu-test.oppwa.com"

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import binascii
import json
JOB_HYPERPAY_ENCRYPTION_KEY="1C5B3C2E18A085E5BCAC566B8F7F8E9B23F8B35431F7C015CB356C20B1EAB997"
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
import json

import json
import uuid
import logging
import requests
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks, Request, Response, HTTPException
from fastapi.security import HTTPBearer
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import secrets
# --- Payment initiation for job applications ---


def get_hyperpay_auth_header() -> dict:
    return {
        "Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}"
    }

from pydantic import BaseModel

class ReservePaymentSchema(BaseModel):
    reserve_id: int


@recruiter_reserve_employeer_router.post("/reserve/payment/init")
def create_reserve_checkout(
    payload: ReservePaymentSchema,
    db: Session = Depends(get_db),
    _=Depends(authentication_context),
    __=Depends(build_request_context),  # ✅ get logged user
):
    logger.info("Creating reserve payment...")

    user = context_actor_user_data.get()  # ✅ current user

    reserve_id = payload.reserve_id

    reserve = db.query(RecruitmentAgentPrivateReserveModel).filter(
        RecruitmentAgentPrivateReserveModel.id == reserve_id,
        RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.ACCEPTED,
    ).first()

    if not reserve:
        raise HTTPException(status_code=404, detail="Reserve not found")

    # ✅ Prevent double payment
    if getattr(reserve, "is_paid", False):
        return {"message": "Already paid"}

    merchant_tx_id = str(uuid.uuid4())
    amount = reserve.price or 10.00


    # ✅ DO NOT overwrite payload
    hyperpay_payload = {
        "entityId": settings.HYPERPAY_ENTITY_ID,
        "amount": f"{amount:.2f}",
        "currency": "AED",
        "paymentType": "DB",
        "merchantTransactionId": merchant_tx_id,
        "customParameters[3DS2_enrolled]": "true",
        "integrity": "true",


       
        "customer.email": "test@test.com",  
        "customer.givenName": "first",
        "customer.surname": "last",

        "billing.street1": "Reserve Payment",
        "billing.city": "Dubai",
        "billing.country": "AE",
        "billing.postcode": "00000",
        "customer.email": "test@test.com",
    }

    try:
        response = requests.post(
            f"{HYPERPAY_BASE_URL}/v1/checkouts",
            data=hyperpay_payload,
            headers=get_hyperpay_auth_header(),
            timeout=30
        )

        res = response.json()
        logger.info(f"HyperPay response: {res}")

        checkout_id = res.get("id")

        if not checkout_id:
            raise HTTPException(status_code=400, detail=res)

        # ✅ SAVE INVOICE PROPERLY
        invoice = InvoiceModel(
            reference=merchant_tx_id,
            checkout_id=checkout_id,
            amount=amount,
            status="pending",
            type="reserve",
            object_id=str(reserve_id),
            buyer_id=user.id,   # ✅ VERY IMPORTANT
        )

        db.add(invoice)
        db.commit()

        return {
            "checkoutId": checkout_id
        }

    except Exception as e:
        logger.exception("Error creating reserve checkout")
        raise HTTPException(status_code=500, detail=str(e))
    
    
@recruiter_reserve_employeer_router.get("/hyper/payment/verify")
def verify_payment(
    id: str = Query(None),
    resourcePath: str = Query(None),
    db: Session = Depends(get_db)
):

    logger.info("Verifying payment...")

    if not id or not resourcePath:
        return {"status": "failed"}

    try:
        response = requests.get(
            f"{HYPERPAY_BASE_URL}{resourcePath}",
            params={"entityId": settings.HYPERPAY_ENTITY_ID},
            headers=get_hyperpay_auth_header(),
            timeout=30
        )

        res = response.json()

        result_code = res.get("result", {}).get("code", "")
        description = res.get("result", {}).get("description", "")

        logger.info(f"Result code: {result_code}")
        logger.info(f"Description: {description}")

        # 🔥 safer lookup
        merchant_tx_id = res.get("merchantTransactionId")

        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.reference == merchant_tx_id
        ).first()

        if not invoice:
            return {"status": "not_found"}

        SUCCESS_CODES = [
            "000.000.000",
            "000.000.100",
            "000.000.110",
            "000.100.110"
        ]

        if result_code in SUCCESS_CODES:

            invoice.status = "paid"
            invoice.payment_id = res.get("id")

            # ===============================
            # 🔥 JOB APPLICATION PAYMENT
            # ===============================
            

            if invoice.type == "reserve":
                reserve = db.query(RecruitmentAgentPrivateReserveModel).filter(
                    RecruitmentAgentPrivateReserveModel.recruitment_id == invoice.buyer_id
                ).first()

                

                if not reserve:
                    raise HTTPException(status_code=404, detail="Reserve not found")

                employeer_id = reserve.agent_id
                recruitment_id = reserve.recruitment_id


                # ✅ CV lookup (UUID match)
                cv_agent = db.query(CVModel).filter(
                    CVModel.user_id == employeer_id
                ).first()

                if not cv_agent:
                    raise HTTPException(status_code=404, detail="CV not found")
                cv_agent.creator_id = recruitment_id  # string field ✅
                # ✅ APPROVE RESERVE
                reserve.status = TransferStatusSchema.ACCEPTED
                db.add(cv_agent)
                db.add(reserve)

                db.commit()

            return {
                "status": "paid",
                "type": invoice.type
            }

        else:

            invoice.status = "failed"
            db.commit()

            return {
                "status": "failed",
                "code": result_code,
                "description": description
            }
    except Exception as e:
        logger.exception("Error creating reserve checkout")
        raise HTTPException(status_code=500, detail=str(e))
   

    


@recruiter_reserve_employeer_router.get("/reserve/{reserve_id}/cv")
def download_cv(
    reserve_id: int,
    db: Session = Depends(get_db)
):
    reserve = db.query(RecruitmentAgentPrivateReserveModel).filter(
        RecruitmentAgentPrivateReserveModel.id == reserve_id
    ).first()

    if not reserve or not reserve.is_paid:
        raise HTTPException(status_code=403, detail="Payment required")

    employee = db.query(UserModel).filter(
        UserModel.id == reserve.employee_id
    ).first()

    if not employee or not employee.cv_file:
        raise HTTPException(status_code=404, detail="CV not found")

    return FileResponse(employee.cv_file)



from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy import cast

#for Employeer Company to retireve approved requests coming from employee, which have no recruitment_id and no employe_id, but have employeer_id, and status is accepted
@recruiter_reserve_employeer_router.get(
    "/employeer-company/my-reserve-requests-all",
    status_code=200
)
async def get_employeer_reserve_requests(
    employeer_id: str,
    db: Session = Depends(get_db_raw)
):

    Employee = aliased(UserModel)
    Recruitment = aliased(UserModel)
    Employeer = aliased(UserModel)

    employeer_uuid = uuid.UUID(employeer_id)

    all_reserves = db.query(RecruitmentAgentPrivateReserveModel).all()

    for r in all_reserves:
        print("ID:", r.id)
        print("employee_id:", r.employee_id)
        print("agent_id:", r.agent_id)
        print("sponsor_id:", r.sponsor_id)
        print("recruitment_id:", r.recruitment_id)
        print("status:", r.status)
        print("created_at:", r.created_at)
        print("-----")

    reserves = (
        db.query(
            RecruitmentAgentPrivateReserveModel,
            Employee,
            Recruitment,
            Employeer
        )
        .outerjoin(
            Employee,
            Employee.id == cast(
                RecruitmentAgentPrivateReserveModel.employee_id,
                UUID
            )
        )
        .outerjoin(
            Recruitment,
            Recruitment.id == RecruitmentAgentPrivateReserveModel.recruitment_id
        )
        .outerjoin(
            Employeer,
            Employeer.id == RecruitmentAgentPrivateReserveModel.sponsor_id
        )
        .filter(
            RecruitmentAgentPrivateReserveModel.sponsor_id == employeer_uuid,
            RecruitmentAgentPrivateReserveModel.status == "pending",
            RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None)
        )
        .order_by(
            RecruitmentAgentPrivateReserveModel.created_at.desc()
        )
        .all()
    )

    data = []

    for reserve, employee, recruitment, employeer in reserves:

        def get_name(user):
            if not user:
                return None
            return (
                getattr(user, "english_full_name", None)
                or f"{user.first_name or ''} {user.last_name or ''}".strip()
            )

        data.append({
            "reserve_id": reserve.id,
            "employee_id": reserve.employee_id,
            "employee_name": get_name(employee),
            "recruitment_id": reserve.recruitment_id,
            "recruitment_name": get_name(recruitment),
            "employeer_id": reserve.sponsor_id,   # ✅ correct field
            "employeer_name": get_name(employeer),
            "status": reserve.status,
            "created_at": reserve.created_at,
            "updated_at": reserve.updated_at
        })

    return {
        "status_code": 200,
        "message": "Employer Company reservation requests fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }

# endpoint for selfsponsor to approve the request coming from employer, which have no recruitment_id and no agent_id, but have sponsor_id
@recruiter_reserve_employeer_router.put("/employee/pending-reserves/employer-request/approve", status_code=200)
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

# for employer company to retireve accepted requests coming from employee, which have no recruitment_id and no employe_id, but have employeer_id, and status is accepted
@recruiter_reserve_employeer_router.get(
    "/employer-company/accepted-private-reserves",
    status_code=200
)
async def get_employer_company_accepted_reserves(
    sponsor_id: str,
    db: Session = Depends(get_db_raw)
):
    """
    Employer company fetches accepted private reservations
    created by them.
    """

    try:
        sponsor_uuid = uuid.UUID(sponsor_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid sponsor_id format"
        )

    reserves = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.sponsor_id == sponsor_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.ACCEPTED
        )
        .all()
    )

    data = []

    for r in reserves:

        employee_name = None
        if r.employee_id:
            employee = db.query(UserModel).filter(
                UserModel.id == r.employee_id
            ).first()

            if employee:
                employee_name = (
                    getattr(employee, "english_full_name", None)
                    or f"{employee.first_name or ''} {employee.last_name or ''}".strip()
                )

        data.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": employee_name,
            "recruitment_id": r.recruitment_id,
            "agent_id": r.agent_id,
            "selfsponsor_id": r.selfsponsor_id,
            "price": r.price,
            "with_passport": r.with_passport,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })

    return {
        "status_code": 200,
        "message": "Accepted private reservations fetched successfully",
        "error": False,
        "count": len(data),
        "data": data
    }



# endpoint for selfsponsor to approve the request coming from agency, which have no recruitment_id and no sponsor_id, but have agency_id
@recruiter_reserve_employeer_router.put("/employee/pending-reserves/agency-request/approve", status_code=200)
async def approve_agency_private_reserve(
    employee_id: str,
    payload: ApproveAgencyReserveSchema,
    db: Session = Depends(get_db_raw)
    
):
    """
    Approve a pending private reservation created by an agency.
    Only approves:
        - agency_id IS NOT NULL
        - sponsor_id IS NULL
        - status = PENDING
        - employee_id matches
    """

        # Validate UUID

    try:
        uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee_id UUID")


    # Step 1: Find sponsor-created pending reservation
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.employee_id == employee_id,  # ✅ correct column
            RecruitmentAgentPrivateReserveModel.agent_id.isnot(None),        # ✅ must have agency
            RecruitmentAgentPrivateReserveModel.sponsor_id.is_(None),        # ✅ no sponsor
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            
        )
        .first()
    )

    if not reserve:
        raise HTTPException(
            status_code=404,
            detail="Pending agent private reservation not found"
        )

    # Step 2: Approve reservation
    reserve.with_passport = payload.with_passport
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
            "employee_id": employee_id,
            "sponsor_id": reserve.sponsor_id,
            "recruitment_id": reserve.recruitment_id,
            "status": reserve.status,
        },
    }

# Endpoint for recruiter to approve employer-created pending reserves
@recruiter_reserve_employeer_router.put(
    "/recruiter/pending-reserves/employer-request/approve", status_code=200
)
async def approve_sponsor_private_reserve_for_recruiter(
    recruiter_id: str,  # UUID of the recruiter approving
    db: Session = Depends(get_db_raw),
):
    """
    Approve a pending private reservation created by a sponsor (employer) for a recruiter.
    Only approves reservations that:
        - recruitment_id IS NOT NULL and matches recruiter_id
        - sponsor_id IS NOT NULL
        - agent_id IS NULL
        - status = PENDING
    """

    # Validate UUID
    try:
        recruiter_uuid = str(uuid.UUID(recruiter_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recruiter_id UUID")

    # Step 1: Find pending reservation for this recruiter
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.recruitment_id == recruiter_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.agent_id.is_(None),
        )
        .first()
    )

    if not reserve:
        raise HTTPException(
            status_code=404,
            detail="Pending sponsor private reservation for recruiter not found"
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
        "message": "Sponsor private reservation for recruiter approved successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "recruitment_id": reserve.recruitment_id,
            "sponsor_id": reserve.sponsor_id,
            "employee_id": reserve.employee_id,
            "status": reserve.status,
        },
    }


# Endpoint for agent to approve employer-created pending reserves
@recruiter_reserve_employeer_router.put(
    "/agent/pending-reserves/employer-request/approve", status_code=200
)
async def approve_sponsor_private_reserve_for_agent(
    agent_id: str,  # UUID of the agent approving
    payload: ApproveAgencyReserveSchema,
    db: Session = Depends(get_db_raw),
):
    """
    Approve a pending private reservation created by a sponsor (employer) for an agent.
    Only approves reservations that:
        - recruitment_id IS NOT NULL and matches agent_id
        - sponsor_id IS NOT NULL
        - agent_id IS NOT NULL and matches agent_id
        - status = PENDING
    """

    # Validate UUID
    try:            
        agent_uuid = str(uuid.UUID(agent_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent_id UUID")

    # Step 1: Find pending reservation for this agent
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.agent_id == agent_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            #RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            #RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None),
        )
        .first()
    )

    if not reserve:
        raise HTTPException(
            status_code=404,
            detail="Pending sponsor private reservation for agent not found"
        )

    # Step 2: Approve reservation
    reserve.with_passport = payload.with_passport
    reserve.status = TransferStatusSchema.ACCEPTED

    try:
        db.commit()
        db.refresh(reserve)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status_code": 200,
        "message": "Sponsor private reservation for agent approved successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "recruitment_id": reserve.recruitment_id,
            "agent_id": reserve.agent_id,
            "sponsor_id": reserve.sponsor_id,
            "employee_id": reserve.employee_id,
            "status": reserve.status,
        },
    }



# Endpoint for selfsponsor to approve employer-created pending reserves
@recruiter_reserve_employeer_router.put(
    "/selfsponsor/pending-reserves/employer-request/approve", status_code=200
)
async def approve_sponsor_private_reserve_for_selfsponsor(
    selfsponsor_id: str,  # UUID of the selfsponsor approving
    payload: ApproveAgencyReserveSchema,
    db: Session = Depends(get_db_raw),
):
    """
    Approve a pending private reservation created by a sponsor (employer) for a selfsponsor     .
    Only approves reservations that:
        - recruitment_id IS NOT NULL and matches selfsponsor_id
        - sponsor_id IS NOT NULL
        - selfsponsor_id IS NOT NULL and matches selfsponsor_id
        - status = PENDING
    """

    # Validate UUID
    try:            
        selfsponsor_uuid = str(uuid.UUID(selfsponsor_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid selfsponsor_id UUID")

    # Step 1: Find pending reservation for this selfsponsor

    # Step 1: Find pending reservation for this agent
    reserve = (
        db.query(RecruitmentAgentPrivateReserveModel)
        .filter(
            RecruitmentAgentPrivateReserveModel.selfsponsor_id == selfsponsor_uuid,
            RecruitmentAgentPrivateReserveModel.status == TransferStatusSchema.PENDING,
            RecruitmentAgentPrivateReserveModel.sponsor_id.isnot(None),
            RecruitmentAgentPrivateReserveModel.recruitment_id.is_(None),
        )
        .first()
    )

    if not reserve:
        raise HTTPException(
            status_code=404,
            detail="Pending sponsor private reservation for agent not found"
        )

    # Step 2: Approve reservation
    reserve.with_passport = payload.with_passport
    reserve.status = TransferStatusSchema.ACCEPTED

    try:
        db.commit()
        db.refresh(reserve)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status_code": 200,
        "message": "Sponsor private reservation for agent approved successfully",
        "error": False,
        "data": {
            "reserve_id": reserve.id,
            "recruitment_id": reserve.recruitment_id,
            "agent_id": reserve.agent_id,
            "sponsor_id": reserve.sponsor_id,
            "employee_id": reserve.employee_id,
            "status": reserve.status,
            "selfsponsor_id": reserve.selfsponsor_id,
        },
    }



@recruiter_reserve_employeer_router.post("/employee/pending-reserves/employer-request/purchase", status_code=500)
async def public_test_200():
    """
    Public endpoint that always returns 200.
    """
    return Response(
        content="Payment callback response created successfully",
        status_code=status.HTTP_200_OK
    )


@recruiter_reserve_employeer_router.post("/recruiter/pending-reserves/employer-request/purchase", status_code=500)
async def public_test_200():
    """
    Public endpoint that always returns 200.
    """
    return Response(
        content="Payment callback response created successfully",
        status_code=status.HTTP_200_OK
    )


@recruiter_reserve_employeer_router.post("/acquire-recruiter/pending-reserves/employer-request/purchase", status_code=500)
async def public_test_200():
    """
    Public endpoint that always returns 200.
    """
    return Response(
        content="Payment callback response created successfully",
        status_code=status.HTTP_200_OK
    )

@recruiter_reserve_employeer_router.post("/acquire-recruiter/pending-reserves/employer-request/purchase", status_code=500)
async def public_test_200():
    """
    Public endpoint that always returns 200.
    """
    return Response(
        content="Payment callback response created successfully",
        status_code=status.HTTP_200_OK
    )


@recruiter_reserve_employeer_router.post("/agent/pending-reserves/employer-request/purchase", status_code=500)
async def public_test_200():
    """
    Public endpoint that always returns 200.
    """
    return Response(
        content="Payment callback response created successfully",
        status_code=status.HTTP_200_OK
    )

#this works
@recruiter_reserve_employeer_router.post("/my-not-reserves-for-recruiter", status_code=200)
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
@recruiter_reserve_employeer_router.post("/reserve-set", status_code=201)
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
@recruiter_reserve_employeer_router.get("/reserve-set", status_code=200)
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




@recruiter_reserve_employeer_router.post("/buyer-request-cv", status_code=200)
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



@recruiter_reserve_employeer_router.get("/recruiter-requests", status_code=200)
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
    

@recruiter_reserve_employeer_router.get("/recruiter-requests", status_code=200)
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



@recruiter_reserve_employeer_router.post("/review-buyer-request-by-id", status_code=200)
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




@recruiter_reserve_employeer_router.post("/review-buyer-request-promotion-by-id",status_code=200)
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


@recruiter_reserve_employeer_router.get("/buyer-approved-requests", status_code=200)
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


from fastapi import APIRouter, Response, status
@recruiter_reserve_employeer_router.post("/packages/callback/hyper")
async def buy_promotion_package_callback():
    return Response(
        status_code=status.HTTP_200_OK,
        content="OK"
    )
