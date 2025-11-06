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
from models.reservemodel import  RecruitmentReserveModel, RecruitmentSetReserveModel, ReserveModel
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
