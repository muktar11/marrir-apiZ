from datetime import datetime, timezone
import json
from typing import Any, List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Response, UploadFile, BackgroundTasks
from starlette.requests import Request
from core.auth import RBACAccessType, RBACResource, rbac_access_checker
from models.db import SessionLocal, authentication_context, build_request_context, get_db_session, get_db_sessions
from models.invoicemodel import InvoiceModel
from models.jobapplicationmodel import JobApplicationModel
from models.jobmodel import JobModel
from models.promotionmodel import PromotionPackagesModel
from repositories.job import JobRepository
from repositories.jobapplication import JobApplicationRepository
from routers import version_prefix
from core.context_vars import context_set_response_code_message, context_actor_user_data
from schemas.base import GenericMultipleResponse, GenericSingleResponse
from schemas.jobschema import (
    ApplicationStatusUpdateSchema,
    ApplyJobMultipleBaseSchema,
    ApplyJobReadSchema,
    ApplyJobSingleBaseSchema,
    ApplyJobSingleReadSchema,
    JobApplicationDeleteSchema,
    JobApplicationPaymentInfoSchema,
    JobBaseSchema,
    JobCreateSchema,
    JobReadSchema,
    JobUpdateSchema,
    JobsFilterSchema,
    JobsSearchSchema,
)
import logging
from telr_payment.api import Telr

from schemas.transferschema import TransferRequestPaymentCallback
from utils.send_email import send_email
from models.notificationmodel import Notifications
from core.security import settings
logger = logging.getLogger(__name__)

job_router_prefix = version_prefix + "job"

job_router = APIRouter(prefix=job_router_prefix)

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


@job_router.post(
    "/", response_model=GenericSingleResponse[JobReadSchema], status_code=201
)
@rbac_access_checker(resource=RBACResource.job, rbac_access_type=RBACAccessType.create)
async def create_job_post(
    *,
    job_in: JobCreateSchema,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    create a new job post
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    new_job = job_repo.create(db, obj_in=job_in)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": new_job,
    }


@job_router.post("/bulk", response_model=None, status_code=201)
async def bulk_create_job(
    *,
    file: UploadFile,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    create many new jobs.
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    job_created = job_repo.bulk_upload(db, file=file)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {}


@job_router.post(
    "/paginated", response_model=GenericMultipleResponse[JobReadSchema], status_code=200
)
@rbac_access_checker(
    resource=RBACResource.job, rbac_access_type=RBACAccessType.read_multiple
)
async def read_job_posts(
    *,
    filters: Optional[JobsFilterSchema] = None,
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
    Retrieve paginated job posts.
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    jobs_read = job_repo.get_some(
        db,
        skip=skip,
        limit=limit,
        search=search,
        search_schema=JobsSearchSchema,
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
        "data": jobs_read,
        "count": res_data.count,
    }


@job_router.post(
    "/single", response_model=GenericSingleResponse[JobReadSchema], status_code=200
)
@rbac_access_checker(resource=RBACResource.job, rbac_access_type=RBACAccessType.read)
async def read_job_post(
    *,
    filters: Optional[JobsFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    Retrieve single job post.
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    job_read = job_repo.get(db, filters=filters)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": job_read,
    }


@job_router.patch(
    "/", response_model=GenericSingleResponse[JobReadSchema], status_code=200
)
@rbac_access_checker(resource=RBACResource.job, rbac_access_type=RBACAccessType.update)
async def update_job_post(
    *,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    job_update: JobUpdateSchema,
    request: Request,
    response: Response
) -> Any:
    """
    Update a job post
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    job_updated = job_repo.update(
        db, filter_obj_in=job_update.filter, obj_in=job_update.update
    )

    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": job_updated,
    }


@job_router.delete(
    "/close", response_model=GenericSingleResponse[JobReadSchema], status_code=200
)
@rbac_access_checker(
    resource=RBACResource.job, rbac_access_type=RBACAccessType.soft_delete
)
async def close_job_post(
    *,
    filters: Optional[JobsFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    close a job post
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    job_deleted = job_repo.soft_delete(db, filters)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": job_deleted,
    }


@job_router.delete(
    "/", response_model=GenericSingleResponse[JobReadSchema], status_code=200
)
@rbac_access_checker(resource=RBACResource.job, rbac_access_type=RBACAccessType.delete)
async def remove_job_post(
    *,
    filters: Optional[JobsFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    delete a job post
    """
    db = get_db_session()
    job_repo = JobRepository(entity=JobModel)
    job_deleted = job_repo.delete(db, filters)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": job_deleted,
    }


@job_router.post(
    "/apply",
    response_model=GenericMultipleResponse[ApplyJobReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.job_application, rbac_access_type=RBACAccessType.create
)
async def apply_for_job(
    *,
    job_in: ApplyJobMultipleBaseSchema,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    apply for a job post
    """
    db = get_db_session()
    job_application_repo = JobApplicationRepository(entity=JobApplicationModel)
    new_job_application = job_application_repo.apply(db, obj_in=job_in)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": new_job_application,
    }


@job_router.delete(
    "/apply/remove",
    response_model=GenericSingleResponse[ApplyJobSingleReadSchema],
    status_code=200,
)
async def remove_job_application(
    *,
    filters: Optional[JobApplicationDeleteSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    remove application for a job post
    """
    db = get_db_session()
    job_application_repo = JobApplicationRepository(entity=JobApplicationModel)
    job_application_deleted = job_application_repo.delete(db, filters)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        # "status_code": 200,
        # "message": "message",
        # "error": False,
        # "data": {
        #     "user_email": "",
        #     "job_id": 1
        # },
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": job_application_deleted,
    }

@job_router.get("/my-applications/{job_id}", response_model=list[ApplyJobReadSchema])
async def get_my_applications(job_id: int,_=Depends(authentication_context),__=Depends(build_request_context)):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role != "recruitment" and user.role != "sponsor":
            return Response(status_code=403, content=json.dumps({"message": "Unauthorized"}), media_type="application/json")
        
        jobs = db.query(JobModel).filter(JobModel.id == job_id, JobModel.posted_by == user.id).first()

        if not jobs:
            return Response(status_code=404, content=json.dumps({"message": "Job not found"}), media_type="application/json")
        
        return jobs.job_applications

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": str(e)}), media_type="application/json")
from datetime import datetime
import uuid

def generate_invoice_number():
    return f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

from datetime import datetime
import uuid
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

INVOICE_DIR = "media/invoices"
os.makedirs(INVOICE_DIR, exist_ok=True)
#from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
import os

TEMPLATE_DIR = "templates"
INVOICE_DIR = "media/invoices"
os.makedirs(INVOICE_DIR, exist_ok=True)

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
def generate_invoice_pdf(invoice):
    template = env.get_template("invoice.html")

    vat = round(invoice.amount * 0.05, 2)
    total = invoice.amount + vat

    html_content = template.render(
        invoice={
            "invoice_number": invoice.invoice_number,
            "payment_id": invoice.payment_id,
            "amount": f"{invoice.amount:.2f}",
            "vat": f"{vat:.2f}",
            "total": f"{total:.2f}",
            "description": invoice.description or "Service",
            "billing_email": invoice.billing_email,
            "billing_country": invoice.billing_country,
            "card_holder": invoice.card_holder,
            "date": invoice.created_at.strftime("%d %B %Y"),
        }
    )

    file_path = f"{INVOICE_DIR}/{invoice.invoice_number}.pdf"
    HTML(string=html_content).write_pdf(file_path)

    return file_path

def create_invoice(
    db, reference: str, amount: float, user_id: uuid.UUID, job_id: str
) -> InvoiceModel:
    invoice = InvoiceModel(
        reference=reference,       # <-- SAVE checkout_id HERE
        status="pending",
        amount=amount,
        created_at=datetime.now(timezone.utc),
        type="job_application",
        buyer_id=user_id,
        object_id=job_id,
    )
    db.add(invoice)
    return invoice

def update_invoice(invoice: InvoiceModel, reference: str) -> None:
    invoice.reference = reference   # <-- UPDATE checkout_id here

def generate_invoice_number():
    return f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def finalize_invoice(db, invoice):
    if not invoice.invoice_number:
        invoice.invoice_number = generate_invoice_number()

    if not invoice.invoice_file:
        invoice.invoice_file = generate_invoice_pdf(invoice)




@job_router.patch("/my-applications/{job_id}/status")
async def update_job_application_status(data: ApplicationStatusUpdateSchema, job_id: int, background_tasks: BackgroundTasks, _=Depends(authentication_context),__=Depends(build_request_context)):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role != "recruitment" and user.role != "sponsor":
            return Response(status_code=403, content=json.dumps({"message": "Unauthorized"}), media_type="application/json")

        job = db.query(JobModel).filter(JobModel.id == job_id).first()

        if not job:
            return Response(status_code=404, content=json.dumps({"message": "Job not found"}), media_type="application/json")

        jobs_applications: List[JobApplicationModel] = db.query(JobApplicationModel).filter(JobApplicationModel.job_id == job_id, JobApplicationModel.id.in_(data.job_application_ids), JobApplicationModel.status == "pending").all()
        
        if not jobs_applications:
            return Response(status_code=404, content=json.dumps({"message": "Job applications not found"}), media_type="application/json")

        for job_application in jobs_applications:
            if job_application.job.posted_by != user.id:
                return Response(status_code=403, content=json.dumps({"message": "Unauthorized"}), media_type="application/json")

        if data.status == "declined":
            for job_application in jobs_applications:
                job_application.status = "declined"
                db.add(job_application)

            db.commit()

            title = "Job Application Declined"

            description = f"{job.job_poster.first_name} {job.job_poster.last_name} has declined the job application for {job.name}"

            background_tasks.add_task(send_notification, db, job_application.user_id, title, description, "job_application")

            email = job_application.user.email or job_application.user.cv.email

            background_tasks.add_task(send_email, email=email, title=title, description=description)

            return {"message": "Job applications status updated successfully"}

        if data.status == "accepted":
            package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == user.role, PromotionPackagesModel.category == "job_application").first()

#            return_url = f"{settings.TELR_JOB_APPLICATION_RETURN_URL.replace("replace", user.role)}/{job_id}"
            return_url = f"{settings.TELR_JOB_APPLICATION_RETURN_URL.replace('replace', user.role)}/{job_id}"

            for job_application in jobs_applications:

                job_application = db.query(JobApplicationModel).filter(JobApplicationModel.user_id == job_application.user_id, JobApplicationModel.status == "accepted").first()

                if job_application:
                    return Response(status_code=400, content=json.dumps({"message": f"{job_application.user.first_name} {job_application.user.last_name} has already been accepted for other job"}), media_type="application/json")

            order_response = telr.order(
                order_id=f"ORDER{uuid.uuid4().hex[:8]}",
                amount=package.price * len(jobs_applications),
                currency="AED",
                return_url=return_url,
                return_decl=return_url,
                return_can=return_url,
                description=f"Job Application"
            )

            ref = order_response.get("order", {}).get("ref")

            if not ref:
                return Response(status_code=400, content=json.dumps({"message": "Failed to process payment"}), media_type="application/json")

            ids = ",".join([str(tr.id) for tr in jobs_applications])

            invoice = db.query(InvoiceModel).filter(
                InvoiceModel.buyer_id == user.id,
                InvoiceModel.status == "pending",
                InvoiceModel.type == "job_application"
            ).first()

            if invoice:
                update_invoice(invoice, ref)
            else:
                invoice = create_invoice(db, ref, len(jobs_applications) * 10, user.id, ids)
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

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": str(e)}), media_type="application/json")






'''
@job_router.patch("/my-applications/{job_id}/status/hyper")
async def update_job_application_status(
    data: ApplicationStatusUpdateSchema,
    job_id: int,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role not in ["recruitment", "sponsor"]:
            return Response(status_code=403,
                content=json.dumps({"message": "Unauthorized"}),
                media_type="application/json"
            )

        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return Response(status_code=404,
                content=json.dumps({"message": "Job not found"}),
                media_type="application/json"
            )

        jobs_applications: List[JobApplicationModel] = (
            db.query(JobApplicationModel)
            .filter(
                JobApplicationModel.job_id == job_id,
                JobApplicationModel.id.in_(data.job_application_ids),
                JobApplicationModel.status == "pending",
            )
            .all()
        )

        if not jobs_applications:
            return Response(status_code=404,
                content=json.dumps({"message": "Job applications not found"}),
                media_type="application/json"
            )

        # 🔒 Permission check
        for app in jobs_applications:
            if app.job.posted_by != user.id:
                return Response(status_code=403,
                    content=json.dumps({"message": "Unauthorized"}),
                    media_type="application/json"
                )

        # ❌ Decline logic stays unchanged
        if data.status == "declined":
            for app in jobs_applications:
                app.status = "declined"
                db.add(app)

            db.commit()

            title = "Job Application Declined"
            description = (
                f"{job.job_poster.first_name} {job.job_poster.last_name} "
                f"has declined the job application for {job.name}"
            )

            background_tasks.add_task(
                send_notification, db, app.user_id, title, description, "job_application"
            )
            email = app.user.email or app.user.cv.email
            background_tasks.add_task(send_email, email, title, description)

            return {"message": "Job applications status updated successfully"}

        # 🔥 ACCEPT → PAYMENT REQUIRED
        if data.status == "accepted":

            # Get correct package
            package = (
                db.query(PromotionPackagesModel)
                .filter(
                    PromotionPackagesModel.role == user.role,
                    PromotionPackagesModel.category == "job_application",
                )
                .first()
            )

            if not package:
                return Response(status_code=404,
                    content=json.dumps({"message": "Package not found"}),
                    media_type="application/json"
                )

            # ❌ Prevent accepting user already accepted somewhere else
            for app in jobs_applications:
                existing = (
                    db.query(JobApplicationModel)
                    .filter(
                        JobApplicationModel.user_id == app.user_id,
                        JobApplicationModel.status == "accepted",
                    )
                    .first()
                )
                if existing:
                    return Response(status_code=400,
                        content=json.dumps({
                            "message": f"{existing.user.first_name} {existing.user.last_name} is already accepted for another job"
                        }),
                        media_type="application/json"
                    )

            # Price × applicants count
            total_amount = package.price * len(jobs_applications)

            # 🔗 Return URL (MUST include job_id)
            return_url = (
                f"{settings.HYPERPAY_JOB_RETURN_URL.replace('replace', user.role)}/{job_id}"
            )

            # -----------------------------------------
            # 🔥 Step 1 — Create HyperPay Checkout
            # -----------------------------------------
            merchant_ref = f"JOBAPP-{uuid.uuid4().hex[:10]}"


            payload = {
                "entityId": settings.HYPERPAY_ENTITY_ID,
                "amount": f"{total_amount:.2f}",
                "currency": "AED",
                "paymentType": "DB",
                "merchantTransactionId": merchant_ref,
                "shopperResultUrl": f"https://marrir.com/sponsor/jobs/{job_id}?ref={merchant_ref}",
                "notificationUrl": "https://api.marrir.com/api/v1/job/my-applications/status/callback/hyper",
            }



            import requests
            headers = {"Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}"}

            hp_res = requests.post(
                "https://test.oppwa.com/v1/checkouts",
                data=payload,
                headers=headers
            ).json()

            checkout_id = hp_res.get("id")

            if not checkout_id:
                return Response(
                    status_code=400,
                    content=json.dumps({"message": "Failed to initialize HyperPay payment"}),
                    media_type="application/json"
                )

            object_ids = ",".join([str(a.id) for a in jobs_applications])

            # 🔍 Look for existing pending invoice for same user + type
            invoice = (
                db.query(InvoiceModel)
                .filter(
                    InvoiceModel.buyer_id == user.id,
                    InvoiceModel.status == "pending",
                    InvoiceModel.type == "job_application",
                )
                .first()
            )

            if invoice:
                # update invoice reference → checkout_id
                update_invoice(invoice, checkout_id)
            else:
                # create invoice with reference → checkout_id
                invoice = create_invoice(
                    db, checkout_id, total_amount, user.id, object_ids
                )
                db.add(invoice)

            db.commit()

            return {
                "checkoutId": checkout_id,
                "redirectUrl": f"https://test.oppwa.com/v1/paymentWidgets.js?checkoutId={checkout_id}",
                "ref": checkout_id   # return checkout_id to frontend
            }


    except Exception as e:
                    print(e)
                    return Response(
                        status_code=400,
                        content=json.dumps({"message": str(e)}),
                        media_type="application/json"
                    )
'''
# --- Payment initiation for job applications ---
'''
@job_router.patch("/my-applications/{job_id}/status/hyper")
async def update_job_application_status(
    data: ApplicationStatusUpdateSchema,
    job_id: int,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role not in ["recruitment", "sponsor"]:
            return Response(status_code=403, content=json.dumps({"message": "Unauthorized"}), media_type="application/json")

        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return Response(status_code=404, content=json.dumps({"message": "Job not found"}), media_type="application/json")

        jobs_applications: List[JobApplicationModel] = (
            db.query(JobApplicationModel)
            .filter(
                JobApplicationModel.job_id == job_id,
                JobApplicationModel.id.in_(data.job_application_ids),
                JobApplicationModel.status == "pending",
            )
            .all()
        )
        if not jobs_applications:
            return Response(status_code=404, content=json.dumps({"message": "Job applications not found"}), media_type="application/json")

        # Permission check
        for app in jobs_applications:
            if app.job.posted_by != user.id:
                return Response(status_code=403, content=json.dumps({"message": "Unauthorized"}), media_type="application/json")

        # DECLINED
        if data.status == "declined":
            for app in jobs_applications:
                app.status = "declined"
                db.add(app)
            db.commit()

            title = "Job Application Declined"
            description = f"{job.job_poster.first_name} {job.job_poster.last_name} has declined the job application for {job.name}"

            for app in jobs_applications:
                background_tasks.add_task(send_notification, db, app.user_id, title, description, "job_application")
                email = app.user.email or app.user.cv.email
                background_tasks.add_task(send_email, email, title, description)

            return {"message": "Job applications status updated successfully"}

        # ACCEPTED → HyperPay payment initiation
        if data.status == "accepted":
            package = db.query(PromotionPackagesModel).filter(
                PromotionPackagesModel.role == user.role,
                PromotionPackagesModel.category == "job_application",
            ).first()
            if not package:
                return Response(status_code=404, content=json.dumps({"message": "Package not found"}), media_type="application/json")

            # Prevent user already accepted elsewhere
            for app in jobs_applications:
                existing = db.query(JobApplicationModel).filter(
                    JobApplicationModel.user_id == app.user_id,
                    JobApplicationModel.status == "accepted",
                ).first()
                if existing:
                    return Response(status_code=400, content=json.dumps({"message": f"{existing.user.first_name} {existing.user.last_name} is already accepted for another job"}), media_type="application/json")

            total_amount = package.price * len(jobs_applications)
            return_url = f"{settings.HYPERPAY_JOB_RETURN_URL.replace('replace', user.role)}/{job_id}"
            merchant_ref = f"JOBAPP-{uuid.uuid4().hex[:10]}"

            payload = {
                "entityId": settings.HYPERPAY_ENTITY_ID,
                "amount": f"{total_amount:.2f}",
                "currency": "AED",
                "paymentType": "DB",
                "merchantTransactionId": merchant_ref,
                "shopperResultUrl": f"https://marrir.com/sponsor/jobs/{job_id}?ref={merchant_ref}",
                "notificationUrl": "https://api.marrir.com/api/v1/job/my-applications/status/callback/hyper",
            }

            headers = {"Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}"}
            hp_res = requests.post("https://test.oppwa.com/v1/checkouts", data=payload, headers=headers).json()
            checkout_id = hp_res.get("id")

            if not checkout_id:
                return Response(status_code=400, content=json.dumps({"message": "Failed to initialize HyperPay payment"}), media_type="application/json")

            object_ids = ",".join([str(a.id) for a in jobs_applications])

            invoice = db.query(InvoiceModel).filter(
                InvoiceModel.buyer_id == user.id,
                InvoiceModel.status == "pending",
                InvoiceModel.type == "job_application"
            ).first()

            if invoice:
                update_invoice(invoice, checkout_id)
            else:
                invoice = create_invoice(db, checkout_id, total_amount, user.id, object_ids)
                db.add(invoice)

            db.commit()

            return {
                "checkoutId": checkout_id,
                "redirectUrl": f"https://test.oppwa.com/v1/paymentWidgets.js?checkoutId={checkout_id}",
                "ref": checkout_id
            }

    except Exception as e:
        logger.exception("Error in job application status update")
        return Response(status_code=400, content=json.dumps({"message": str(e)}), media_type="application/json")
'''

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


@job_router.patch("/my-applications/{job_id}/status/hyper")
async def update_job_application_status(
    data: ApplicationStatusUpdateSchema,
    job_id: int,
    background_tasks: BackgroundTasks,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        if user.role not in ["recruitment", "sponsor"]:
            return Response(status_code=403, content="Unauthorized")

        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return Response(status_code=404, content="Job not found")

        applications = (
            db.query(JobApplicationModel)
            .filter(
                JobApplicationModel.job_id == job_id,
                JobApplicationModel.id.in_(data.job_application_ids),
                JobApplicationModel.status == "pending",
            )
            .all()
        )

        if not applications:
            return Response(status_code=404, content="Job applications not found")

        for app in applications:
            if app.job.posted_by != user.id:
                return Response(status_code=403, content="Unauthorized")

        # ---------- DECLINED ----------
        if data.status == "declined":
            for app in applications:
                app.status = "declined"
            db.commit()
            return {"message": "Job applications declined"}

        # ---------- ACCEPTED → PAY ----------
        if data.status == "accepted":
            package = (
                db.query(PromotionPackagesModel)
                .filter(
                    PromotionPackagesModel.role == user.role,
                    PromotionPackagesModel.category == "job_application",
                )
                .first()
            )
            if not package:
                return Response(status_code=404, content="Package not found")

            for app in applications:
                existing = (
                    db.query(JobApplicationModel)
                    .filter(
                        JobApplicationModel.user_id == app.user_id,
                        JobApplicationModel.status == "accepted",
                    )
                    .first()
                )
                if existing:
                    return Response(
                        status_code=400,
                        content=f"{existing.user.first_name} already accepted elsewhere",
                    )

            amount = package.price * len(applications)
            merchant_tx_id = "JOBAPP-" + ",".join(str(a.id) for a in applications)
            payload = {
                "entityId": settings.HYPERPAY_ENTITY_ID,
                "amount": f"{amount:.2f}",
                "currency": "AED",
                "paymentType": "DB",

                "merchantTransactionId": merchant_tx_id,
                "customParameters[3DS2_enrolled]": "true",

                "shopperResultUrl": f"https://marrir.com/sponsor/jobs/{job_id}?ref={merchant_tx_id}",
                "notificationUrl": "https://api.marrir.com/api/v1/job/packages/callback/hyper",
            }

            headers = {
                "Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            res = requests.post(
                "https://test.oppwa.com/v1/checkouts",
                data=payload,
                headers=headers,
                timeout=30,
            ).json()


            checkout_id = res.get("id")
            if not checkout_id:
                return Response(status_code=400, content=json.dumps(res))

            invoice = InvoiceModel(
                reference=merchant_tx_id,
                buyer_id=user.id,
                amount=amount,
                status="pending",
                type="job_application",
                object_id=",".join(str(a.id) for a in applications),
            )

            db.add(invoice)
            db.commit()
            db.refresh(invoice)

            return {
                "checkoutId": checkout_id,
                "merchantTransactionId": merchant_tx_id,
                "amount": amount,
            }

    except Exception as e:
        logger.exception("Job HyperPay initiation failed")
        return Response(status_code=500, content=str(e))


from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import binascii
import json

HYPERPAY_ENCRYPTION_KEY="52C78392A3658DEC1CAA6AD8D98B1B78EE3FEB1CA7369FA3531E67FEDF9B0EBE"



def decrypt_hyperpay_payload(encrypted_hex: str) -> dict:
    encrypted_bytes = binascii.unhexlify(encrypted_hex)
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    key = binascii.unhexlify(HYPERPAY_ENCRYPTION_KEY)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return json.loads(decrypted.decode("utf-8"))


@job_router.post("/packages/callback/hyper")
async def job_hyperpay_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    data = {}

    try:
        body = await request.json()
        if isinstance(body, dict):
            data.update(body)
    except Exception:
        pass

    logger.info("HyperPay JOB webhook received: %s", data)

    # 🔐 ENCRYPTED CALLBACK (REAL FIX)
    if "encryptedBody" in data:    
        background_tasks.add_task(
                    process_job_payment_by_payment_id,
                    payment_id,
                )
        return {"status": "processed"}

        

        

    # 🔁 NORMAL CALLBACK
    payment_id = data.get("id")
    if payment_id:
        background_tasks.add_task(
            process_job_payment_by_payment_id,
            payment_id,
        )

    return {"status": "received"}


def process_job_payment_by_payment_id(payment_id: str):
    db = SessionLocal()
    try:
        res = requests.get(
            f"https://test.oppwa.com/v1/payments/{payment_id}",
            params={"entityId": settings.HYPERPAY_ENTITY_ID},
            headers=get_hyperpay_auth_header(),
            timeout=30,
        ).json()

        code = res.get("result", {}).get("code", "")
        if not code.startswith(("000.000", "000.100", "000.200")):
            return

        merchant_tx_id = res.get("merchantTransactionId")
        if not merchant_tx_id:
            return

        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.reference == merchant_tx_id,
            InvoiceModel.status != "paid",
            InvoiceModel.type == "job_application",
        ).first()

        if not invoice:
            return

        invoice.status = "paid"
        invoice.payment_id = payment_id

        app_ids = [int(i) for i in invoice.object_id.split(",")]
        applications = db.query(JobApplicationModel).filter(
            JobApplicationModel.id.in_(app_ids)
        ).all()

        for app in applications:
            app.status = "accepted"

        db.commit()

    except Exception:
        logger.exception("Job payment verification failed")
        db.rollback()
    finally:
        db.close()

def poll_pending_job_payments():
    db = SessionLocal()
    try:
        invoices = db.query(InvoiceModel).filter(
            InvoiceModel.status == "pending",
            InvoiceModel.type == "job_application",
        ).all()

        for invoice in invoices:
            res = requests.get(
                "https://test.oppwa.com/v1/payments",
                params={
                    "entityId": settings.HYPERPAY_ENTITY_ID,
                    "merchantTransactionId": invoice.reference,
                },
                headers=get_hyperpay_auth_header(),
                timeout=30,
            ).json()

            for p in res.get("payments", []):
                code = p.get("result", {}).get("code", "")
                if not code.startswith(("000.000", "000.100", "000.200")):
                    continue

                if invoice.status == "paid":
                    continue

                invoice.status = "paid"
                invoice.payment_id = p.get("id")

                app_ids = [int(i) for i in invoice.object_id.split(",")]
                applications = db.query(JobApplicationModel).filter(
                    JobApplicationModel.id.in_(app_ids)
                ).all()

                for app in applications:
                    app.status = "accepted"

                db.commit()

    except Exception:
        logger.exception("Job polling failed")
        db.rollback()
    finally:
        db.close()







@job_router.get("/my-applications/status/callback/hyper")
async def pay_status(
    merchantTransactionId: str,
    db: Session = Depends(get_db_session),
):
    invoice = db.query(InvoiceModel).filter(
        InvoiceModel.reference == merchantTransactionId,
        InvoiceModel.type == "job_application",
    ).first()

    if not invoice:
        return {"status": "not_found"}

    return {
        "status": invoice.status,
        "amount": invoice.amount,
    }




from fastapi import Query
from sqlalchemy.orm import Session
'''
@job_router.get("/my-applications/status/callback/hyper")
async def hyperpay_job_application_callback(
    background_tasks: BackgroundTasks,
    ref: str = Query(...),
 
    db: Session = Depends(get_db_sessions)
):
    try:
        # Lookup invoice by merchantTransactionId
        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.reference == ref,
            InvoiceModel.type == "job_application"
        ).first()

        if not invoice:
            return {"status": "failed", "message": "Invoice not found"}
      
        invoice.status = "paid"
        db.add(invoice)
        db.commit()
        # Find job applications linked to invoice
        application_ids = list(map(int, invoice.object_id.split(",")))
        job_applications = db.query(JobApplicationModel).filter(
            JobApplicationModel.id.in_(application_ids)
        ).all()

        if not job_applications:
            return {"status": "failed", "message": "Job applications not found"}

        # Optionally, send notifications again if needed
        first_app = job_applications[0]
        job = db.query(JobModel).filter(JobModel.id == first_app.job_id).first()

        title = "Job Application Accepted"
        description = f"{job.job_poster.first_name} {job.job_poster.last_name} has accepted your application for {job.name}"

        for app in job_applications:
            background_tasks.add_task(
                send_notification,
                db,
                app.user_id,
                title,
                description,
                "job_application"
            )
            email = app.user.email or app.user.cv.email
            background_tasks.add_task(send_email, email, title, description)

        return {"status": "successful", "message": "Payment completed"}

    except Exception as e:
        logger.error(f"Callback Error: {e}")
        return {"status": "failed", "message": str(e)}
'''


@job_router.post("/my-applications/payment/info")
async def get_job_application_payment_info(data: JobApplicationPaymentInfoSchema, _=Depends(authentication_context),__=Depends(build_request_context)):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        jobs_applications: List[JobApplicationModel] = db.query(JobApplicationModel).filter(JobApplicationModel.job_id == data.job_id, JobApplicationModel.id.in_(data.job_application_ids), JobApplicationModel.status == "pending").all()
        
        if not jobs_applications:
            return Response(status_code=404, content=json.dumps({"message": "Job applications not found"}), media_type="application/json")

        for job_application in jobs_applications:
            if job_application.job.posted_by != user.id:
                return Response(status_code=403, content=json.dumps({"message": "Unauthorized"}), media_type="application/json")

        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == user.role, PromotionPackagesModel.category == "job_application").first()

        return {
            "price": package.price,
            "total_amount": package.price * len(jobs_applications),
            "profile": len(jobs_applications)
        }

    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": str(e)}), media_type="application/json")
