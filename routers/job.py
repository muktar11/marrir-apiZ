from datetime import datetime, timezone
import json
from typing import Any, List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Response, UploadFile, BackgroundTasks
from starlette.requests import Request
from core.auth import RBACAccessType, RBACResource, rbac_access_checker
from models.db import SessionLocal, authentication_context, build_request_context, get_db, get_db_session, get_db_sessions
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



HYPERPAY_BASE_URL = "https://eu-test.oppwa.com"

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
            merchant_tx_id = secrets.token_hex(6)
            
            


            user_email = app.user.email
            user_first = app.user.first_name
            user_last = app.user.last_name
            

            billing = data.billing

            if data.status == "accepted" and not data.billing:
                raise HTTPException(
                    status_code=400,
                    detail="Billing information is required to proceed with payment"
                )

            payload = {
                "entityId": settings.HYPERPAY_ENTITY_ID,
                "amount": f"{amount:.2f}",
                "currency": "AED",
                "paymentType": "DB",

                "merchantTransactionId": merchant_tx_id,
                "customParameters[3DS2_enrolled]": "true",
                "integrity": "true",
                "customer.email": user_email,
                "customer.givenName": user_first,
                "customer.surname": user_last,

                "billing.street1": billing.street1,
                "billing.city": billing.city,
                "billing.state": billing.state or "N/A",
                "billing.country": billing.country,
                "billing.postcode": billing.postcode,

                
                "shopperResultUrl": f"https://marrir.com/recruitment/jobs/{job_id}",
                "notificationUrl": "https://api.marrir.com/api/v1/job/packages/callback/hyper",
            }




            headers = {
                "Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            res = requests.post(
                f"{HYPERPAY_BASE_URL}/v1/checkouts",
                data=payload,
                headers=headers,
                timeout=30,
            ).json()




            checkout_id = res.get("id")
            integrity_value = res.get("integrity")
            if not checkout_id:
                return Response(status_code=400, content=json.dumps(res))

            invoice = InvoiceModel(
                reference=merchant_tx_id,
                payment_id=checkout_id,
                buyer_id=user.id,
                amount=amount,
                status="pending",
                type="job_application",
                object_id=",".join(str(a.id) for a in applications),
                integrity=integrity_value,

               
                billing_country=billing.country.upper(),
                billing_street=billing.street1,
                billing_city=billing.city,
                billing_state=billing.state,
                billing_postcode=billing.postcode,
            )

            db.add(invoice)
            db.commit()
            db.refresh(invoice)

            return {
                "checkoutId": checkout_id,
                "merchantTransactionId": merchant_tx_id,
                "integrity": integrity_value,
                "amount": amount,
            }

    except Exception as e:
        logger.exception("Job HyperPay initiation failed")
        return Response(status_code=500, content=str(e))





from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import binascii
import json

JOB_HYPERPAY_ENCRYPTION_KEY="1C5B3C2E18A085E5BCAC566B8F7F8E9B23F8B35431F7C015CB356C20B1EAB997"





from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
import json

def decrypt_hyperpay_payload(encrypted_b64: str) -> dict:
    encrypted_bytes = base64.b64decode(encrypted_b64)

    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    key = bytes.fromhex(JOB_HYPERPAY_ENCRYPTION_KEY)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)

    return json.loads(decrypted.decode("utf-8"))


from fastapi import Request, status
from fastapi import Header, HTTPException
from starlette.responses import JSONResponse
from fastapi import Request, BackgroundTasks
from fastapi.responses import JSONResponse


'''
@job_router.post("/packages/callback/hyper")
async def job_hyperpay_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    try:
        data = {}

        try:
            form = await request.form()
            data.update(form)
        except:
            pass

        try:
            body = await request.json()
            if isinstance(body, dict):
                data.update(body)
        except:
            pass

        data.update(dict(request.query_params))

        # encrypted callback
        if "encryptedBody" in data:
            logger.info("Encrypted JOB webhook received — starting polling")
            background_tasks.add_task(poll_pending_job_payments)

        # normal callback
        payment_id = data.get("id")
        if payment_id:
            background_tasks.add_task(
                process_job_payment_by_payment_id,
                payment_id
            )

    except Exception as e:
        logger.error(f"Callback error: {e}")

    return JSONResponse(status_code=200, content={"status": "received"})
'''

'''

@job_router.post("/packages/callback/hyper")
async def job_hyperpay_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    try:
        data: dict = {}

        # Try to collect form data
        try:
            form = await request.form()
            data.update(form)
        except Exception:
            pass

        # Try to collect JSON body
        try:
            body = await request.json()
            if isinstance(body, dict):
                data.update(body)
        except Exception:
            pass

        # Include query params
        data.update(dict(request.query_params))

        # ---------- Encrypted callback ----------
        if "encryptedBody" in data:
            try:
                logger.info("Encrypted JOB webhook received — decrypting payload")
                print("Encrypted payload:", data["encryptedBody"][:50] + "...")  # Log start of encrypted payload
                decrypted = decrypt_hyperpay_payload(data["encryptedBody"])

                # Merge decrypted data so you can inspect it if needed
                if isinstance(decrypted, dict):
                    data.update(decrypted)

                payment_id = decrypted.get("id")
                if payment_id:
                    print("Decrypted payload:", decrypted)  # Log decrypted payload
                    logger.info(f"Decrypted JOB payment_id={payment_id}, queueing verification")
                    background_tasks.add_task(
                        process_job_payment_by_payment_id,
                        payment_id,
                    )
                else:
                    # Fallback: trigger polling if no direct id
                    logger.info("No payment_id in decrypted payload, starting polling")
                    background_tasks.add_task(poll_pending_job_payments)

            except Exception as e:
                logger.error(f"Failed to decrypt HyperPay payload: {e}")
                # As a safety net, still start polling
                background_tasks.add_task(poll_pending_job_payments)

        # ---------- Plain callback with id ----------
        payment_id = data.get("id")
        if payment_id:
            print("Plain callback data:", data)  # Log received data
            logger.info(f"Plain JOB webhook with payment_id={payment_id}, queueing verification")
            background_tasks.add_task(
                process_job_payment_by_payment_id,
                payment_id,
            )

    except Exception as e:
        print(f"Error processing HyperPay callback: {e}")
        logger.error(f"Callback error: {e}")

    return JSONResponse(status_code=200, content={"status": "received"})

from schemas.offerschema import OfferTypeSchema

def process_job_payment_by_payment_id(payment_id: str):
    db = SessionLocal()
    try:
        # 🔹 Use webhook payment_id directly
        res = requests.get(
            f"{HYPERPAY_BASE_URL}/v1/payments/{payment_id}",
            params={"entityId": settings.HYPERPAY_ENTITY_ID},
            headers=get_hyperpay_auth_header(),
            timeout=30,
        ).json()

        code = res.get("result", {}).get("code", "")
        if not code.startswith(("000.000", "000.100", "000.200")):
            print(f"Payment not successful. Code: {code}")
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
            print(f"No pending invoice found for merchantTransactionId: {merchant_tx_id}")
            return

        invoice.status = "paid"
        invoice.payment_id = payment_id  # now real payment_id

        app_ids = [int(i) for i in invoice.object_id.split(",")]
        applications = db.query(JobApplicationModel).filter(
            JobApplicationModel.id.in_(app_ids)
        ).all()

        for app in applications:
            app.status = OfferTypeSchema.ACCEPTED

        db.commit()
        logger.error("COMMIT DONE FOR JOB APPLICATION UPDATE")

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
            print(f"Polling invoice {invoice.id} with reference {invoice.reference}")
            logger.info(f"Polling invoice {invoice.id} with reference {invoice.reference}")

            res = requests.get(                
                f"{HYPERPAY_BASE_URL}/v1/payments",
                params={
                    "entityId": settings.HYPERPAY_ENTITY_ID,
                    "merchantTransactionId": invoice.reference,
                },
                headers=get_hyperpay_auth_header(),
                timeout=30,
            ).json()

            logger.info(f"HyperPay response: {res}")
            print(f"HyperPay response: {res}")
            payments = res.get("payments", [])
            if not payments:
                logger.info("No payments found")
                continue

            payment = payments[0]
            code = payment.get("result", {}).get("code", "")

            if not code.startswith(("000.000", "000.100", "000.200")):
                print(f"Payment not successful. Code: {code}")
                logger.info(f"Payment not successful. Code: {code}")
                continue

            # ✅ ONLY NOW mark as paid
            invoice.status = "paid"
            invoice.payment_id = payment.get("id")

            app_ids = [int(i) for i in invoice.object_id.split(",")]
            applications = db.query(JobApplicationModel).filter(
                JobApplicationModel.id.in_(app_ids)
            ).all()

            for app in applications:
                app.status = OfferTypeSchema.ACCEPTED

            db.commit()
            print(f"Invoice {invoice.id} marked as PAID")
            logger.info(f"Invoice {invoice.id} marked as PAID")

    finally:
        db.close()
'''
import base64
import json
import logging
from Crypto.Cipher import AES
from fastapi import APIRouter, Request, BackgroundTasks
import requests
from schemas.offerschema import OfferTypeSchema

logger = logging.getLogger("routers.job")
router = APIRouter()

HYPERPAY_BASE_URL = "https://eu-test.oppwa.com"


def get_hyperpay_auth_header():
    return {
        "Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}"
    }


def decrypt_hyperpay_payload(encrypted_hex: str) -> dict:
    """
    Decrypt HyperPay's encryptedBody
    """
    try:
        # Convert hex to bytes
        data_bytes = bytes.fromhex(encrypted_hex)

        key = JOB_HYPERPAY_ENCRYPTION_KEY.encode("utf-8")  # 16/24/32 bytes
        iv = JOB_HYPERPAY_ENCRYPTION_KEY.encode("utf-8")    # 16 bytes

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(data_bytes)

        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]

        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return {}


def is_successful_payment(code: str) -> bool:
    return code.startswith(("000.000", "000.100", "000.200"))


def poll_checkout(checkout_id: str):
    """
    Poll a single checkout to verify payment
    """
    db: Session = SessionLocal()
    try:
        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.checkout_id == checkout_id,
            InvoiceModel.status == "pending"
        ).first()

        if not invoice:
            logger.info(f"No pending invoice for checkout {checkout_id}")
            return

        res = requests.get(
            f"{HYPERPAY_BASE_URL}/v1/checkouts/{checkout_id}/payment",
            params={"entityId": settings.HYPERPAY_ENTITY_ID},
            headers=get_hyperpay_auth_header(),
            timeout=30
        ).json()

        result_code = res.get("result", {}).get("code", "")

        if not is_successful_payment(result_code):
            logger.info(f"Payment not completed for checkout {checkout_id}: {result_code}")
            return

        # Mark invoice as paid
        invoice.status = "paid"
        invoice.payment_id = res.get("id")

        # Update related job applications
        app_ids = [int(i) for i in invoice.object_id.split(",")]
        applications = db.query(JobApplicationModel).filter(
            JobApplicationModel.id.in_(app_ids)
        ).all()

        for app in applications:
            app.status = OfferTypeSchema.ACCEPTED

        db.commit()
        logger.info(f"Invoice {invoice.id} marked PAID for checkout {checkout_id}")

    except Exception:
        logger.exception(f"Polling checkout failed: {checkout_id}")
        db.rollback()
    finally:
        db.close()


@router.post("/packages/callback/hypers")
async def hyperpay_callback(request: Request, background_tasks: BackgroundTasks):
    """
    HyperPay webhook callback
    """
    body = await request.json()
    encrypted_body = body.get("encryptedBody")

    if not encrypted_body:
        logger.warning("Missing encryptedBody in HyperPay callback")
        return {"status": "ok"}

    payload = decrypt_hyperpay_payload(encrypted_body)
    if not payload:
        return {"status": "ok"}  # just acknowledge, don't block webhook

    checkout_id = payload.get("id")
    if not checkout_id:
        logger.warning("Missing checkout_id in decrypted payload")
        return {"status": "ok"}

    logger.info(f"HyperPay callback received for checkout {checkout_id}")

    # Poll only this checkout
    background_tasks.add_task(poll_checkout, checkout_id)

    return {"status": "ok"}

@job_router.get("/my-applications/status/callback/hyper")
async def pay_status(
    merchantTransactionId: str,
    db: Session = Depends(get_db_sessions),  # ← THIS IS THE FIX
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



from fastapi import APIRouter, Depends
import requests
import uuid
from sqlalchemy.orm import Session

router = APIRouter()

@job_router.post("/payment/test")
def create_test_checkout(db: Session = Depends(get_db)):

    merchant_tx_id = str(uuid.uuid4())

    payload = {
        "entityId": settings.HYPERPAY_ENTITY_ID,
        "amount": "10.00",
        "currency": "EUR",
        "paymentType": "DB",
        "merchantTransactionId": merchant_tx_id,
        "billing.street1": "Test Street",
        "billing.city": "Dubai",
        "billing.country": "AE",
        "billing.postcode": "00000",
        "customer.email": "test@test.com",
    }

    res = requests.post(
        f"{HYPERPAY_BASE_URL}/v1/checkouts",
        data=payload,
        headers=get_hyperpay_auth_header(),
    ).json()

    checkout_id = res.get("id")

    invoice = InvoiceModel(
        reference=merchant_tx_id,
        checkout_id=checkout_id,
        amount=10.00,
        status="pending",
        type="job_application",
        object_id="1,2"
    )

    db.add(invoice)
    db.commit()

    return {
        "checkoutId": checkout_id
    }

# --------------- Verify Payment Endpoint ----------------
from fastapi import Query

@job_router.get("/payment/verify")
def verify_payment(
    id: str = Query(None),
    resourcePath: str = Query(None),
    db: Session = Depends(get_db)
):

    try:

        res = requests.get(
            f"{HYPERPAY_BASE_URL}{resourcePath}",
            params={"entityId": settings.HYPERPAY_ENTITY_ID},
            headers=get_hyperpay_auth_header()
        ).json()

        result_code = res.get("result", {}).get("code", "")

        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.checkout_id == id
        ).first()

        if not invoice:
            return {"status": "not_found"}

        if result_code.startswith(("000.000", "000.100", "000.200")):

            invoice.status = "paid"
            invoice.payment_id = res.get("id")

            db.commit()

            return {
                "status": "paid"
            }

        else:

            invoice.status = "failed"
            db.commit()

            return {
                "status": "failed"
            }

    except Exception as e:

        db.rollback()

        return {
            "status": "error",
            "message": str(e)
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
