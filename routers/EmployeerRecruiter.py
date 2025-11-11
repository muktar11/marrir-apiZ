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
