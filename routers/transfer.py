from datetime import datetime, timezone
import json
from typing import Any, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Response, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy import UUID
from starlette.requests import Request
from stripe import Webhook
import stripe
from core.auth import RBACAccessType, RBACResource, rbac_access_checker
from models.agentrecruitmentmodel import AgentRecruitmentModel
from models.batchtransfermodel import BatchTransferModel
from models.companyinfomodel import CompanyInfoModel
from models.cvmodel import CVModel
from models.db import authentication_context, build_request_context, get_db_session, get_db_sessions
from models.employeemodel import EmployeeModel
from models.invoicemodel import InvoiceModel
from models.notificationmodel import Notifications
from models.promotionmodel import PromotionPackagesModel
from models.transfermodel import TransferModel
from models.transferrequestmodel import TransferRequestModel
from models.usermodel import UserModel
from repositories.transfer import TransferRepository
from routers import version_prefix
from core.context_vars import context_set_response_code_message, context_actor_user_data
from schemas.base import GenericMultipleResponse, GenericSingleResponse
from schemas.cvschema import CVSearchSchema
from schemas.reserveschema import ReserveCVFilterSchema
from schemas.transferschema import (
    AllTransfersReadSchema,
    BatchTransferFilterSchema,
    BatchTransferReadSchema,
    BillingInfoSchema,
    TransferBaseSchema,
    TransferCreateSchema,
    TransferInfoSchema,
    TransferPaySchema,
    TransferReadSchema,
    TransferRequest,
    TransferRequestBaseSchema,
    TransferRequestCreateSchema,
    TransferRequestPaymentCallback,
    TransferRequestPaymentSchema,
    TransferRequestReadSchema,
    TransferRequestReturn,
    TransferRequestStatusSchema,
    TransferRequestUpdateSchema,
    TransferStatusSchema,
    TransferUpdateSchema,
    TransferFilterSchema,
)
from schemas.userschema import UsersSearchSchema
from telr_payment.api import Telr
from core.security import settings
import logging

from utils.send_email import send_email

logger = logging.getLogger(__name__)

telr = Telr(auth_key=settings.TELR_AUTH_KEY, store_id=settings.TELR_STORE_ID, test=settings.TELR_TEST_MODE)

transfer_router_prefix = version_prefix + "transfer"

transfer_router = APIRouter(prefix=transfer_router_prefix)

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

@transfer_router.post(
    "/", response_model=GenericMultipleResponse[TransferReadSchema], status_code=201
)
@rbac_access_checker(
    resource=RBACResource.transfer, rbac_access_type=RBACAccessType.create
)
async def make_transfer(
    *,
    transfer_in: TransferRequestBaseSchema,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    request: Request,
    response: Response
) -> Any:
    """
    make transfer
    """
    db = get_db_session()
    transfer_repo = TransferRepository(entity=TransferModel)
    new_transfer = transfer_repo.make_transfer(db=db, obj_in=transfer_in)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": new_transfer,
    }


@transfer_router.post(
    "/paginated",
    response_model=GenericMultipleResponse[AllTransfersReadSchema],
    status_code=200,
)
# @rbac_access_checker(
#     resource=RBACResource.transfer, rbac_access_type=RBACAccessType.read_multiple
# )
async def view_transfers(
    *,
    filters: Optional[TransferFilterSchema] = None,
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
    View paginated transfers
    """
    db = get_db_session()
    transfer_repo = TransferRepository(entity=TransferModel)
    transfers_read = transfer_repo.get_some(
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
        "data": transfers_read,
        "count": res_data.count,
    }

'''
@transfer_router.post(
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
    transfer_repo = TransferRepository(entity=TransferModel)
    filtered_transfers = transfer_repo.get_filtered_employee_cvs(
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
        "data": filtered_transfers,
        "count": res_data.count,
    }
'''
    
'''
@transfer_router.post(
    "/requests/paginated",
    response_model=GenericMultipleResponse[BatchTransferReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.transfer, rbac_access_type=RBACAccessType.read_multiple
)
async def view_sent_transfer_requests(
    *,
    filters: Optional[BatchTransferFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    request: Request,
    response: Response
) -> Any:
    """
    View paginated transfer requests sent
    """
    db = get_db_session()
    transfer_repo = TransferRepository(entity=TransferModel)
    transfers_read = transfer_repo.get_transfer_requests_sent(
        db, skip=skip, limit=limit, filters=filters
    )
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": transfers_read,
        "count": res_data.count,
    }

'''

@transfer_router.post(
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
    transfer_repo = TransferRepository(entity=TransferModel)
    filtered_transfers = transfer_repo.get_filtered_employee_cvs(
        db,
        skip=skip,
        limit=limit,
        filters=filters,
        search=search,
        search_schema=CVSearchSchema,
    )
    print('filtered', filtered_transfers)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": filtered_transfers,
        "count": res_data.count,
    }


@transfer_router.post(
    "/requests/status/paginated",
    response_model=GenericMultipleResponse[BatchTransferReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.transfer, rbac_access_type=RBACAccessType.read_multiple
)
async def view_received_transfer_requests(
    *,
    filters: Optional[TransferFilterSchema] = None,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    request: Request,
    response: Response
) -> Any:
    """
    View paginated transfer requests received
    """
    db = get_db_session()
    transfer_repo = TransferRepository(entity=TransferModel)
    transfers_read = transfer_repo.get_my_transfer_requests(db, skip=skip, limit=limit)
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": transfers_read,
        "count": res_data.count,
    }


@transfer_router.post(
    "/requests/status/detail/paginated",
    response_model=GenericMultipleResponse[TransferRequestReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.transfer, rbac_access_type=RBACAccessType.read_multiple
)
async def view_received_transfer_request_detail(
    *,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    skip: int = 0,
    limit: int = 10,
    batch_transfer_id: int,
    search: str = None,
    filters: Optional[ReserveCVFilterSchema] = None,
    request: Request,
    response: Response
) -> Any:
    """
    View paginated transfer requests received detail
    """
    db = get_db_session()
    transfer_repo = TransferRepository(entity=TransferModel)
    transfers_read = transfer_repo.get_my_transfer_request_details(
        db,
        skip=skip,
        limit=limit,
        batch_transfer_id=batch_transfer_id,
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
        "data": transfers_read,
        "count": res_data.count,
    }


@transfer_router.patch(
    "/",
    response_model=GenericMultipleResponse[TransferRequestReadSchema],
    status_code=200,
)
@rbac_access_checker(
    resource=RBACResource.transfer, rbac_access_type=RBACAccessType.update
)
async def accept_decline_transfer(
    *,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
    transfer_request_update: TransferRequestUpdateSchema,
    request: Request,
    response: Response
) -> Any:
    """
    Update transfer status
    """
    db = get_db_session()
    transfer_repo = TransferRepository(entity=TransferModel)
    transfer_updated = transfer_repo.review_transfer(
        db,
        filter_obj_in=transfer_request_update.filter,
        obj_in=transfer_request_update.update,
    )
    res_data = context_set_response_code_message.get()
    response.status_code = res_data.status_code
    return {
        "status_code": res_data.status_code,
        "message": res_data.message,
        "error": res_data.error,
        "data": transfer_updated,
    }


# @transfer_router.post("/session/{invoice_id}")
# async def create_checkout_session(
#         *,
#     _=Depends(authentication_context),
#     __=Depends(build_request_context),
#     invoice_id: UUID,
#     request: Request,
#     response: Response
# ) -> Any:
#     """
#     Update transfer status
#     """
#     db = get_db_session()
#     transfer_repo = TransferRepository(entity=TransferModel)
#     transfer_paid = transfer_repo.review_transfer(
#         db, filter_obj_in=transfer_update.filter, obj_in=transfer_update.update
#     )
#     res_data = context_set_response_code_message.get()
#     response.status_code = res_data.status_code
#     return {
#         "status_code": res_data.status_code,
#         "message": res_data.message,
#         "error": res_data.error,
#         "data": transfer_updated,
#     }

#     current_user: Customer = Depends(get_current_active_user)
# ):
'''
@transfer_router.get("/")
async def get_agency_recruitment(_=Depends(HTTPBearer(scheme_name="bearer")), __=Depends(build_request_context)):
    db = get_db_session()
    user = context_actor_user_data.get()
    related_data = []
    unrelated_data = []
    if user.role == "agent":
        recruitment = db.query(UserModel).filter(UserModel.role == "recruitment").all()
        related_recruitment = db.query(UserModel).join(AgentRecruitmentModel, AgentRecruitmentModel.recruitment_id == UserModel.id).filter(
            AgentRecruitmentModel.agent_id == user.id, AgentRecruitmentModel.status == "approved"
        ).all()

        unrelated_recruitment = [r for r in recruitment if r not in related_recruitment]

        for r in related_recruitment:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == r.id).first()
            if company_info:
                related_data.append({"user_id": r.id, "name": company_info.company_name})

        for r in unrelated_recruitment:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == r.id).first()
            if company_info:
                unrelated_data.append({"user_id": r.id, "name": company_info.company_name})

    if user.role == "recruitment":
        agents = db.query(UserModel).filter(UserModel.role == "agent").all()
        
        related_agents = db.query(UserModel).join(AgentRecruitmentModel, AgentRecruitmentModel.agent_id == UserModel.id).filter(
            AgentRecruitmentModel.recruitment_id == user.id, AgentRecruitmentModel.status == "approved"
        ).all()

        unrelated_agents = [a for a in agents if a not in related_agents]

        for a in related_agents:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == a.id).first()
            if company_info:
                related_data.append({"user_id": a.id, "name": company_info.company_name})

        for a in unrelated_agents:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == a.id).first()
            if company_info:
                unrelated_data.append({"user_id": a.id, "name": company_info.company_name})

    return {"unrelated": unrelated_data, "related": related_data}
'''



@transfer_router.get("/")
async def get_agency_recruitment(
    _=Depends(HTTPBearer(scheme_name="bearer")),
    __=Depends(build_request_context)
):
    db: Session = get_db_session()
    user = context_actor_user_data.get()
    logger.debug(f"Authenticated user: {user.id}, role: {user.role}")

    related_data = []
    unrelated_data = []

    try:
        all_users = db.query(UserModel).filter(UserModel.role.in_(["agent", "recruitment", "sponsor"])).all()
        logger.debug(f"All agent/recruitment/sponsor user IDs: {[u.id for u in all_users]}")

        related_user_ids = []

        if user.role == "agent":
            logger.debug("Fetching related recruiters for agent")
            related_users = db.query(UserModel).join(
                AgentRecruitmentModel,
                AgentRecruitmentModel.recruitment_id == UserModel.id
            ).filter(
                AgentRecruitmentModel.agent_id == user.id,
                AgentRecruitmentModel.status == "approved"
            ).all()
            related_user_ids = [u.id for u in related_users]

        elif user.role == "recruitment":
            logger.debug("Fetching related agents for recruitment")
            related_users = db.query(UserModel).join(
                AgentRecruitmentModel,
                AgentRecruitmentModel.agent_id == UserModel.id
            ).filter(
                AgentRecruitmentModel.recruitment_id == user.id,
                AgentRecruitmentModel.status == "approved"
            ).all()
            related_user_ids = [u.id for u in related_users]

        else:
            logger.warning(f"No relationship mapping logic for role: {user.role}")
            related_users = []

        logger.debug(f"Related user IDs: {related_user_ids}")

        # Add related user company info
        for r in related_users:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == r.id).first()
            if company_info:
                related_data.append({"user_id": r.id, "name": company_info.company_name})

        # Unrelated = all valid users - related users
        #unrelated_users = [u for u in all_users if u.id not in related_user_ids]
        #unrelated_users = [u for u in all_users if u.id not in related_user_ids and u.id != user.id]

        #logger.debug(f"Unrelated user IDs: {[u.id for u in unrelated_users]}")

        # Unrelated = all valid users - related users - current user
        unrelated_users = [u for u in all_users if u.id not in related_user_ids and u.id != user.id]

        logger.debug(f"Unrelated user IDs (excluding current user): {[u.id for u in unrelated_users]}")
        '''
        for u in unrelated_users:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == u.id).first()
            if company_info:
                unrelated_data.append({"user_id": u.id, "name": company_info.company_name})
        '''
        for u in unrelated_users:
            company_info = db.query(CompanyInfoModel).filter(CompanyInfoModel.user_id == u.id).first()
            if company_info:
                unrelated_data.append({"user_id": u.id, "name": company_info.company_name}) 
                logger.debug(f"Returning related: {len(related_data)}, unrelated: {len(unrelated_data)}")

        return {
            "related": related_data,
            "unrelated": unrelated_data
        }

    except Exception as e:
        logger.error(f"Error in get_agency_recruitment: {str(e)}", exc_info=True)
        raise


@transfer_router.get("/search")
async def search_agency_recruitment(_=Depends(HTTPBearer(scheme_name="bearer")), __=Depends(build_request_context)):
    db = get_db_session()
    
    user = context_actor_user_data.get()

    user_data = []

    # Get the employee's from the EmployeeModel table
    employees = db.query(EmployeeModel).filter(EmployeeModel.manager_id == user.id).all()

    # Get user info from UserModel table and get sex,religion,nationality,marital_status and occupation from CVModel table
    for employee in employees:
        user_info = db.query(UserModel).filter(UserModel.id == employee.user_id).first()
        cv_info = db.query(CVModel).filter(CVModel.user_id == employee.user_id).first()
        if user_info and cv_info:
            user_data.append({
                "user_id": user_info.id,
                "name": cv_info.english_full_name,
                "job_title": cv_info.occupation,
                "sex": cv_info.sex,
                "religion": cv_info.religion,
                "nationality": cv_info.nationality,
                "marital_status": cv_info.marital_status
            })
    
    return {"data": user_data}


# @transfer_router.post("/employee")
# async def transfer_employee(data: TransferRequest, _=Depends(HTTPBearer(scheme_name="bearer")), __=Depends(build_request_context)):
#     db = get_db_session()

#     user = context_actor_user_data.get()

#     role = user.role

#     for user_id in data.user_ids:
#         employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == user_id, EmployeeModel.manager_id == user.id).first()
#         if not employee:
#             return Response(status_code=400, content=f"You are not authorized to transfer employee with user_id {user_id}")
    
#     if role == "agent":
#         relationship = db.query(AgentRecruitmentModel).filter(AgentRecruitmentModel.agent_id == user.id, AgentRecruitmentModel.recruitment_id == data.receiver_id).first()
#         if relationship:
#             batch_transfer = BatchTransferModel(
#                 receiver_id=data.receiver_id,
#                 requester_id=user.id
#             )
#             try:
#                 db.add(batch_transfer)
#                 db.commit()

#                 for user_id in data.user_ids:
#                     transfer_request = TransferRequestModel(
#                         batch_id=batch_transfer.id,
#                         user_id=user_id,
#                         requester_id=data.receiver_id,
#                         manager_id=user.id,
#                         status="done"
#                     )

#                     employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == user_id).first()

#                     if employee:
#                         employee.manager_id = data.receiver_id

#                     db.add(transfer_request)
#                     db.add(employee)
#                     db.commit()

#                 return {"status": "success", "message": "Batch transfer created"}

#             except Exception as e:
#                 print(e)
#                 db.rollback()
#                 return Response(status_code=500, content="Failed to create transfer")
        
#         batch_transfer = BatchTransferModel(
#             receiver_id=data.receiver_id,
#             requester_id=user.id
#         )

#         try:
#             db.add(batch_transfer)
#             db.commit()

#             for user_id in data.user_ids:
#                 transfer_request = TransferRequestModel(
#                     batch_id=batch_transfer.id,
#                     user_id=user_id,
#                     requester_id=data.receiver_id,
#                     manager_id=user.id,
#                     status="pending"
#                 )

#                 db.add(transfer_request)
#                 db.commit()

#             return {"status": "success", "message": "Batch transfer created"}

#         except Exception as e:
#             print(e)
#             db.rollback()
#             return Response(status_code=500, content="Failed to create transfer")

#     if role == "recruitment":
#         relationship = db.query(AgentRecruitmentModel).filter(AgentRecruitmentModel.recruitment_id == user.id, AgentRecruitmentModel.agent_id == data.receiver_id).first()
#         if relationship:
#             batch_transfer = BatchTransferModel(
#                 receiver_id=data.receiver_id,
#                 requester_id=user.id
#             )
#             try:
#                 db.add(batch_transfer)
#                 db.commit()

#                 for user_id in data.user_ids:
#                     transfer_request = TransferRequestModel(
#                         batch_id=batch_transfer.id,
#                         user_id=user_id,
#                         requester_id=data.receiver_id,
#                         manager_id=user.id,
#                         status="done"
#                     )

#                     employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == user_id).first()

#                     if employee:
#                         employee.manager_id = data.receiver_id

#                     db.add(transfer_request)
#                     db.add(employee)
#                     db.commit()

#                 return {"status": "success", "message": "Batch transfer created"}

#             except Exception as e:
#                 print(e)
#                 db.rollback()
#                 return Response(status_code=500, content="Failed to create transfer")
        
#         batch_transfer = BatchTransferModel(
#             receiver_id=data.receiver_id,
#             requester_id=user.id
#         )

#         try:
#             db.add(batch_transfer)
#             db.commit()

#             for user_id in data.user_ids:
#                 transfer_request = TransferRequestModel(
#                     batch_id=batch_transfer.id,
#                     user_id=user_id,
#                     requester_id=data.receiver_id,
#                     manager_id=user.id,
#                     status="pending"
#                 )

#                 db.add(transfer_request)
#                 db.commit()

#             return {"status": "success", "message": "Batch transfer created"}

#         except Exception as e:
#             print(e)
#             db.rollback()
#             return Response(status_code=500, content="Failed to create transfer")

def create_batch_transfer(db, receiver_id, requester_id):
    batch_transfer = BatchTransferModel(
        receiver_id=receiver_id,
        requester_id=requester_id
    )
    db.add(batch_transfer)
    db.commit()
    return batch_transfer

def create_transfer_request(db, batch_transfer_id, user_id, receiver_id, manager_id, status):
    transfer_request = TransferRequestModel(
        batch_id=batch_transfer_id,
        user_id=user_id,
        requester_id=receiver_id,
        manager_id=manager_id,
        status=status
    )
    db.add(transfer_request)
    db.commit()

def update_employee_manager(db, user_id, new_manager_id):
    employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == user_id).first()
    if employee:
        employee.manager_id = new_manager_id
        db.add(employee)
        db.commit()

def handle_transfer(db, user, data, status, connection: bool):
    batch_transfer = create_batch_transfer(db, data.receiver_id, user.id)
    for user_id in data.user_ids:
        create_transfer_request(db, batch_transfer.id, user_id, data.receiver_id, user.id, status)
        if status == "done":
            update_employee_manager(db, user_id, data.receiver_id)
    if connection:
        return {"status": "success", "message": "You have successfully transferred the employee(s)", "connection": connection}
    return {"status": "success", "message": "Batch transfer created", "connection": connection}

@transfer_router.post("/employee")
async def transfer_employee(data: TransferRequest,background_tasks: BackgroundTasks, _=Depends(HTTPBearer(scheme_name="bearer")), __=Depends(build_request_context)):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()
        role = user.role

        for user_id in data.user_ids:
            employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == user_id, EmployeeModel.manager_id == user.id).first()
            if not employee:
                return Response(status_code=400, content=json.dumps({"message": f"You are not authorized to transfer employee with user_id {user_id}"}), media_type="application/json")
    
            status = "pending"
    
            _user = db.query(UserModel).filter(UserModel.id == user.id).first()
    
            name = ""

            if not employee.employee.first_name and not employee.employee.last_name:
                name = employee.employee.cv.english_full_name
            else:
                name = f"{employee.employee.first_name} {employee.employee.last_name}"


        receiver_user = db.query(UserModel).filter(UserModel.id == data.receiver_id).first()

        email = receiver_user.email or receiver_user.company.alternative_email

        try:
            if role == "agent":
                relationship = db.query(AgentRecruitmentModel).filter(AgentRecruitmentModel.agent_id == user.id, AgentRecruitmentModel.recruitment_id == data.receiver_id, AgentRecruitmentModel.status == "approved").first()
                if relationship:
                    status = "done"
                    background_tasks.add_task(send_notification, db, data.receiver_id, "Transfer", f"{_user.company.company_name} has transferred {name} to you", "transfer")
                    background_tasks.add_task(send_email, email=email, title="Transfer", description=f"{_user.company.company_name} has transferred {name} to you")
                    return handle_transfer(db, user, data, status, True)
                else:
                    background_tasks.add_task(send_notification, db, data.receiver_id, "Transfer Request", f"Transfer request from {_user.company.company_name} for {name}", "transfer")
                    background_tasks.add_task(send_email, email=email, title="Transfer Request", description=f"Transfer request from {_user.company.company_name} for {name}")
                    return handle_transfer(db, user, data, status, False)

            elif role == "recruitment":
                relationship = db.query(AgentRecruitmentModel).filter(AgentRecruitmentModel.recruitment_id == user.id, AgentRecruitmentModel.agent_id == data.receiver_id, AgentRecruitmentModel.status == "approved").first()
                if relationship:
                    background_tasks.add_task(send_notification, db, data.receiver_id, "Transfer", f"{_user.company.company_name} has transferred {name} to you", "transfer")
                    background_tasks.add_task(send_email, email=email, title="Transfer", description=f"{_user.company.company_name} has transferred {name} to you")
                    return handle_transfer(db, user, data, status, True)
                else:
                    background_tasks.add_task(send_notification, db, data.receiver_id, "Transfer Request", f"Transfer request from {_user.company.company_name} for {name}", "transfer")
                    background_tasks.add_task(send_email, email=email, title="Transfer Request", description=f"Transfer request from {_user.company.company_name} for {name}")
                    return handle_transfer(db, user, data, status, False)
                
        except Exception as e:
            print(e)
            db.rollback()
            return Response(status_code=400, content=json.dumps({"message": "Failed to create transfer"}), media_type="application/json")
    except Exception as e:
        print(e)

@transfer_router.post("/request/status")
async def update_transfer_request_status(data: TransferRequestStatusSchema, background_tasks: BackgroundTasks, _=Depends(HTTPBearer(scheme_name="bearer")), __=Depends(build_request_context)):
    db = get_db_session()

    user = context_actor_user_data.get()
    try:
        transfer_requests = db.query(TransferRequestModel).filter(TransferRequestModel.id.in_(data.transfer_request_id), TransferRequestModel.requester_id == user.id, TransferRequestModel.status == "pending").all()

        if not transfer_requests:
            return Response(status_code=404, content=json.dumps({"message": "Transfer requests not found"}), media_type="application/json")  

        for transfer_request in transfer_requests:
            transfer_request.status = data.status
            transfer_request.reason = data.reason
            db.add(transfer_request)


        db.commit()
        background_tasks.add_task(send_notification, db, transfer_requests[0].manager_id, "Transfer Request", f"Transfer requests has been {data.status}", "transfer")

        _user = db.query(UserModel).filter(UserModel.id == transfer_requests[0].manager_id).first() 

        email = _user.email or _user.company.alternative_email

        background_tasks.add_task(send_email, email=email, title="Transfer Request", description=f"Transfer requests has been {data.status}")

        return {"status": "success", "message": "Transfer request status updated"}

    except Exception as e:
        print(e)
        db.rollback()
        return Response(status_code=400, content=json.dumps({"message": "Failed to update transfer request status"}), media_type="application/json")


'''
def create_invoice(db, ref: str, amount: float, user_id: int, transfer_request_id: int) -> InvoiceModel:
    invoice = InvoiceModel(
        stripe_session_id=ref,
        status="pending",
        amount=amount,
        created_at=datetime.now(),
        type="transfer",
        buyer_id=user_id,
        object_id=transfer_request_id,
    )
    db.add(invoice)
    return invoice

def update_invoice(invoice: InvoiceModel, ref: str) -> None:
    invoice.stripe_session_id = ref

    '''

def create_invoice(
    db, reference: str, amount: float, user_id: uuid.UUID, 
) -> InvoiceModel:
    invoice = InvoiceModel(
        reference=reference,       # <-- SAVE checkout_id HERE
        status="pending",
        amount=amount,
        created_at=datetime.now(timezone.utc),
        type="transfer",
        buyer_id=user_id,
        
    )
    db.add(invoice)
    return invoice

def update_invoice(invoice: InvoiceModel, reference: str) -> None:
    invoice.reference = reference   # <-- UPDATE checkout_id here


'''
@transfer_router.post("/pay")
async def pay_transfer(
    data: TransferRequestPaymentSchema,
    _=Depends(HTTPBearer(scheme_name="bearer")),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == user.role, PromotionPackagesModel.category == "transfer").first()
        transfer_requests = db.query(TransferRequestModel).filter(
            TransferRequestModel.id.in_(data.transfer_request_ids),
            TransferRequestModel.manager_id == user.id,
            TransferRequestModel.status == "accepted"
        ).all()
    except Exception as e:
        print(e)

    if not transfer_requests:
        return Response(status_code=404, content=json.dumps({"message": "Transfer request not found"}))

    return_url = settings.TELR_TRANSFER_RETURN_URL.replace("replace", user.role)

    amount = package.price * len(transfer_requests)

    order_response = telr.order(
        order_id=f"ORDER{uuid.uuid4().hex[:8]}",
        amount=amount,
        return_url=return_url,
        return_decl=return_url,
        return_can=return_url,
        description="Transfer payment",
    )
    ref = order_response.get("order", {}).get("ref")

    if not ref:
        return Response(status_code=400, content=json.dumps({"message": "Failed to create order"}), media_type="application/json")

    ids = ",".join([str(tr.id) for tr in transfer_requests])

    invoice = db.query(InvoiceModel).filter(
        InvoiceModel.object_id == ids,
        InvoiceModel.buyer_id == user.id,
        InvoiceModel.status == "pending",
        InvoiceModel.type == "transfer"
    ).first()

    try:
        if invoice:
            update_invoice(invoice, ref)
        else:
            invoice = create_invoice(db, ref, amount, user.id, ids)
            db.add(invoice)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to process invoice: {e}")
        db.rollback()
        return Response(status_code=400, content="Failed to process invoice")

    return {
        "method": order_response.get("method"),
        "trace": order_response.get("trace"),
        "order": {
            "ref": order_response.get("order", {}).get("ref"),
            "url": order_response.get("order", {}).get("url"),
        },
    }

'''



@transfer_router.post("/pay")
async def pay_transfer(
    data: TransferRequestPaymentSchema,
    _=Depends(HTTPBearer(scheme_name="bearer")),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == user.role, PromotionPackagesModel.category == "transfer").first()
        transfer_requests = db.query(TransferRequestModel).filter(
            TransferRequestModel.id.in_(data.transfer_request_ids),
            TransferRequestModel.manager_id == user.id,
            TransferRequestModel.status == "accepted"
        ).all()
    except Exception as e:
        print(e)

    if not transfer_requests:
        return Response(status_code=404, content=json.dumps({"message": "Transfer request not found"}))

    return_url = settings.TELR_TRANSFER_RETURN_URL.replace("replace", user.role)

    amount = package.price * len(transfer_requests)

    order_response = telr.order(
        order_id=f"ORDER{uuid.uuid4().hex[:8]}",
        amount=amount,
        return_url=return_url,
        return_decl=return_url,
        return_can=return_url,
        description="Transfer payment",
    )
    ref = order_response.get("order", {}).get("ref")

    if not ref:
        return Response(status_code=400, content=json.dumps({"message": "Failed to create order"}), media_type="application/json")

    ids = ",".join([str(tr.id) for tr in transfer_requests])

    invoice = db.query(InvoiceModel).filter(
        InvoiceModel.object_id == ids,
        InvoiceModel.buyer_id == user.id,
        InvoiceModel.status == "pending",
        InvoiceModel.type == "transfer"
    ).first()

    try:
        if invoice:
            update_invoice(invoice, ref)
        else:
            invoice = create_invoice(db, ref, amount, user.id, ids)
            db.add(invoice)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to process invoice: {e}")
        db.rollback()
        return Response(status_code=400, content="Failed to process invoice")

    return {
        "method": order_response.get("method"),
        "trace": order_response.get("trace"),
        "order": {
            "ref": order_response.get("order", {}).get("ref"),
            "url": order_response.get("order", {}).get("url"),
        },
    }
'''
from fastapi import Depends
from sqlalchemy.orm import Session
import requests
import logging
logger = logging.getLogger("hyperpay")
from pydantic import BaseModel

def get_hyperpay_auth_header() -> dict:
    return {
        "Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}"
    }



class PaymentRequest(BaseModel):
    amount: float
    currency: str = "AED"

@transfer_router.post("/pay/hyper")
async def pay_transfer(
    data: TransferRequestPaymentSchema,
    _=Depends(HTTPBearer(scheme_name="bearer")),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        # 1️⃣ Fetch package for transfer payments
        package = (
            db.query(PromotionPackagesModel)
            .filter(
                PromotionPackagesModel.role == user.role,
                PromotionPackagesModel.category == "transfer"
            )
            .first()
        )
        if not package:
            return Response(
                status_code=404,
                content=json.dumps({"message": "Package not found"})
            )

        # 2️⃣ Fetch accepted transfer requests
        transfer_requests = (
            db.query(TransferRequestModel)
            .filter(
                TransferRequestModel.id.in_(data.transfer_request_ids),
                TransferRequestModel.manager_id == user.id,
                TransferRequestModel.status == "accepted",
            )
            .all()
        )
        if not transfer_requests:
            return Response(
                status_code=404,
                content=json.dumps({"message": "Transfer request not found"})
            )

        # 3️⃣ Total amount
        amount = package.price * len(transfer_requests)



        # 5️⃣ Create HyperPay checkout session
        import requests
        payload = {
            "entityId": settings.HYPERPAY_ENTITY_ID,
            "amount": f"{amount:.2f}",
            "currency": "AED",
            "paymentType": "DB",
            "shopperResultUrl": f"https://marrir.com/agent/transfer-history",
            "notificationUrl": "https://api.marrir.com/api/v1/transfer/pay/callback",
        }

        headers = {"Authorization": 
                   f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}",
                    "Content-Type": "application/x-www-form-urlencoded",
                }

        try:
            res = requests.post(
                "https://test.oppwa.com/v1/checkouts",
                data=payload,
                headers=headers
            ).json()
        except Exception as e:
            return Response(
                status_code=500,
                content=json.dumps({"message": "Payment initialization failed", "error": str(e)})
            )

        checkout_id = res.get("id")
        if not checkout_id:
            return Response(
                status_code=400,
                content=json.dumps({"message": "HyperPay checkout failed"})
            )

        # 7️⃣ Create/update invoice
        invoice = InvoiceModel(
                reference=checkout_id,
                buyer_id=user.id,
                amount=amount,
                status="pending",
                type="transfer",
                object_id=",".join(str(tr.id) for tr in transfer_requests)
        
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)



            # 8️⃣ Response to frontend
        return {
                "checkoutId": checkout_id,
                "redirectUrl": f"https://test.oppwa.com/v1/paymentWidgets.js?checkoutId={checkout_id}",
            
                "amount": amount,
            }
    except Exception as e:
                    print(e)
                    return Response(
        status_code=400,
        content=json.dumps({"message": str(e)}),  # show full error
        media_type="application/json"
    )            


from fastapi import Query, Response
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks, Depends
import json
@transfer_router.get("/pay/callback")
async def pay_transfer_callback(
    background_tasks: BackgroundTasks,
    ref: str,   # This is checkoutId
    db: Session = Depends(get_db_sessions)
):
    try:
    
        # 2️⃣ Find invoice by checkoutId
        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.reference == ref,
            InvoiceModel.type == "transfer"
        ).first()

        if not invoice:
            return Response(
                status_code=404,
                content=json.dumps({"message": "Invoice not found"}),
                media_type="application/json"
            )

        # 3️⃣ Mark invoice as paid
        invoice.status = "paid"
        db.add(invoice)
        db.commit()

        # 4️⃣ Load transfer requests using invoice.object_id
        transfer_ids = list(map(int, invoice.object_id.split(",")))

        transfer_requests = db.query(TransferRequestModel).filter(
            TransferRequestModel.id.in_(transfer_ids),
            TransferRequestModel.status == "accepted"
        ).all()

        if not transfer_requests:
            return {"status": "failed", "message": "Transfer requests not found"}

        # Find manager and requester
        first_tr = transfer_requests[0]

        manager_user = db.query(UserModel).filter(
            UserModel.id == first_tr.manager_id
        ).first()

        requester_user = db.query(UserModel).filter(
            UserModel.id == first_tr.requester_id
        ).first()

        # 5️⃣ Process employee transfer
        employee = None
        for tr in transfer_requests:
            employee = db.query(EmployeeModel).filter(
                EmployeeModel.user_id == tr.user_id
            ).first()

            if employee:
                employee.manager_id = tr.requester_id
                db.add(employee)

            tr.status = "done"
            db.add(tr)

        db.commit()

        # 6️⃣ Prepare notifications
        employee_name = ""
        if employee:
            emp = employee.employee
            employee_name = (
                emp.cv.english_full_name
                if not emp.first_name and not emp.last_name
                else f"{emp.first_name} {emp.last_name}"
            )

        # Emails
        manager_email = manager_user.email or manager_user.company.alternative_email
        requester_email = requester_user.email or requester_user.company.alternative_email

        # 7️⃣ Send notifications
        title = "Transfer"
        description = (
            f"{manager_user.company.company_name} has transferred {employee_name} to you. "
            f"Contact Info: {manager_email}, {manager_user.phone_number}, {manager_user.company.location}."
        )

        background_tasks.add_task(
            send_notification, db, requester_user.id, title, description, "transfer"
        )
        background_tasks.add_task(
            send_email, requester_email, title, description
        )

        # Manager notification
        title2 = "Transfer Finished"
        description2 = (
            f"Contact info for {requester_user.company.company_name}: "
            f"{requester_email}, {requester_user.phone_number}, {requester_user.company.location}."
        )

        background_tasks.add_task(
            send_notification, db, manager_user.id, title2, description2, "transfer"
        )
        background_tasks.add_task(
            send_email, manager_email, title2, description2
        )

        return {"status": "success", "message": "Payment successful"}

    except Exception as e:
        print("Callback error:", e)
        db.rollback()
        return Response(
            status_code=400,
            content=json.dumps({"message": "Failed to process payment"}),
            media_type="application/json"
        )

'''



from pydantic import BaseModel, EmailStr
class TransferRequestPaymentSchema(BaseModel):
    transfer_request_ids: list[int]
    billing: BillingInfoSchema


from fastapi import Depends
from sqlalchemy.orm import Session
import requests
import logging
logger = logging.getLogger("hyperpay")
from pydantic import BaseModel

import json
import secrets
import logging
import requests



def get_hyperpay_auth_header() -> dict:
    return {
        "Authorization": f"Bearer {settings.HYPERPAY_ACCESS_TOKEN}"
    }



class PaymentRequest(BaseModel):
    amount: float
    currency: str = "AED"

logger = logging.getLogger("hyperpay")



@transfer_router.post("/pay/hyper")
async def pay_transfer(
    data: TransferPaySchema,
    _=Depends(HTTPBearer(scheme_name="bearer")),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        package = (
            db.query(PromotionPackagesModel)
            .filter(
                PromotionPackagesModel.role == user.role,
                PromotionPackagesModel.category == "transfer",
            )
            .first()
        )
        if not package:
            return Response(status_code=404, content="Package not found")

        transfers = (
            db.query(TransferRequestModel)
            .filter(
                TransferRequestModel.id.in_(data.transfer_request_ids),
                TransferRequestModel.manager_id == user.id,
                TransferRequestModel.status == "accepted",
            )
            .all()
        )

        if not transfers:
            return Response(status_code=404, content="Transfer requests not found")

        amount = package.price * len(transfers)
        merchant_tx_id = secrets.token_hex(12)
        b = data.billing

        payload = {
            "entityId": settings.HYPERPAY_ENTITY_ID,
            "amount": f"{amount:.2f}",
            "currency": "AED",
            "paymentType": "DB",

            "merchantTransactionId": merchant_tx_id,
            "customParameters[3DS2_enrolled]": "true",

            "customer.email": b.email,
            "customer.givenName": b.given_name,
            "customer.surname": b.surname,

            "billing.street1": b.street1,
            "billing.city": b.city,
            "billing.state": b.state,
            "billing.country": b.country.upper(),
            "billing.postcode": b.postcode,

            "shopperResultUrl": "https://marrir.com/transfer-history",
            "notificationUrl": "https://api.marrir.com/api/v1/transfer/pay/callback",
        }

        res = requests.post(
            "https://test.oppwa.com/v1/checkouts",
            data=payload,
            headers=get_hyperpay_auth_header(),
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
            type="transfer",
            object_id=",".join(str(t.id) for t in transfers),
        )
        db.add(invoice)
        db.commit()

        return {
            "checkoutId": checkout_id,
            "merchantTransactionId": merchant_tx_id,
            "amount": amount,
        }

    except Exception as e:
        return Response(status_code=500, content=str(e))





def verify_hyperpay_payment(payment_id: str) -> bool:
    url = f"https://test.oppwa.com/v1/payments/{payment_id}"
    params = {"entityId": settings.HYPERPAY_ENTITY_ID}
    headers = get_hyperpay_auth_header()

    res = requests.get(url, params=params, headers=headers).json()
    logger.info(f"HyperPay verify response: {res}")

    code = res.get("result", {}).get("code", "")
    return code.startswith(("000.000", "000.100", "000.200"))

'''
@transfer_router.post("/pay/callback")
async def pay_transfer_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Accept everything
    data = dict(request.query_params)

    try:
        body = await request.json()
        data.update(body)
    except Exception:
        pass

    try:
        form = await request.form()
        data.update(form)
    except Exception:
        pass

    logger.info(f"HyperPay callback received: {data}")
    print(f"HyperPay callback received: {data}")

    payment_id = data.get("id")
    if not payment_id:
        # Always return 200
        return {"status": "ignored"}

    background_tasks.add_task(process_transfer_payment_by_payment_id, payment_id)
    return {"status": "received"}
'''

from fastapi import Header, HTTPException
from starlette.responses import JSONResponse

HYPERPAY_WEBHOOK_KEY = "CAF9E1160305904826E5F2258199C59845E06A55617E2D5807616C840A014B1F"





@transfer_router.post("/pay/callback")
async def pay_transfer_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    data = {}

    try:
        form = await request.form()
        data.update(form)
    except Exception:
        pass

    try:
        body = await request.json()
        if isinstance(body, dict):
            data.update(body)
    except Exception:
        pass

    logger.info("HyperPay webhook received: %s", data)

    # 🔐 Encrypted callback → poll payments
    if "encryptedBody" in data:
        logger.info("Encrypted webhook received — starting polling")
        background_tasks.add_task(poll_pending_transfer_payments)
        return JSONResponse(status_code=200, content={"status": "received"})

    payment_id = data.get("id")
    if payment_id:
        background_tasks.add_task(process_transfer_payment_by_payment_id, payment_id)

    return JSONResponse(status_code=200, content={"status": "received"})


def poll_pending_transfer_payments():
    db = get_db_session()
    try:
        invoices = db.query(InvoiceModel).filter(
            InvoiceModel.status == "pending",
            InvoiceModel.type == "transfer",
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

            payments = res.get("payments", [])
            for p in payments:
                code = p.get("result", {}).get("code", "")
                if code.startswith(("000.000", "000.100", "000.200")):
                    invoice.status = "paid"
                    invoice.payment_id = p.get("id")
                    db.commit()

    except Exception:
        logger.exception("Polling failed")
        db.rollback()
    finally:
        db.close()

def process_transfer_payment_by_payment_id(payment_id: str):
    db = get_db_session()
    try:
        url = f"https://test.oppwa.com/v1/payments/{payment_id}"
        res = requests.get(
            url,
            params={"entityId": settings.HYPERPAY_ENTITY_ID},
            headers=get_hyperpay_auth_header(),
            timeout=30,
        ).json()

        logger.info(f"HyperPay verify response: {res}")

        code = res.get("result", {}).get("code", "")
        if not code.startswith(("000.000", "000.100", "000.200")):
            return

        merchant_tx_id = res.get("merchantTransactionId")
        if not merchant_tx_id:
            logger.error("merchantTransactionId missing in verification")
            return

        invoice = db.query(InvoiceModel).filter(
            InvoiceModel.reference == merchant_tx_id,
            InvoiceModel.status != "paid"
        ).first()

        if not invoice:
            return

        invoice.status = "paid"
        invoice.payment_id = payment_id
        db.commit()

    except Exception:
        logger.exception("Payment processing failed")
        db.rollback()
    finally:
        db.close()


@transfer_router.get("/pay/status")
async def pay_status(
    merchantTransactionId: str,
    db: Session = Depends(get_db_sessions),
):
    invoice = db.query(InvoiceModel).filter(
        InvoiceModel.reference == merchantTransactionId,
        InvoiceModel.type == "transfer"
    ).first()

    if not invoice:
        return {"status": "not_found"}

    return {
        "status": invoice.status,  # pending | paid
        "amount": invoice.amount
    }


'''

@transfer_router.post("/pay/callback")
async def pay_transfer_callback(data: TransferRequestPaymentCallback, background_tasks: BackgroundTasks, _=Depends(HTTPBearer (scheme_name="bearer")),__=Depends(build_request_context)):
    db = get_db_session()

    user = context_actor_user_data.get()
    status_response = telr.status(
            order_reference = data.ref
    )
        
    state = status_response.get("order", {}).get("status", {}).get("text", "")

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
        InvoiceModel.type == "transfer"
    ).first()

    if not invoice:
        return Response(status_code=404, content=json.dumps({"message": "Invoice not found"}), media_type="application/json")

    transfer_requests = db.query(TransferRequestModel).filter(
            TransferRequestModel.id.in_(map(int, invoice.object_id.split(','))),
            TransferRequestModel.manager_id == user.id,
            TransferRequestModel.status == "accepted"
    ).all()

    if not transfer_requests:
        return Response(status_code=404, content=json.dumps({"message": "Transfer requests not found"}), media_type="application/json")

    try:
        employee = None  # Define employee before the loop
        for transfer_request in transfer_requests:
            employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == transfer_request.user_id).first()
            if employee:
                employee.manager_id = transfer_request.requester_id
                db.add(employee)

            transfer_request.status = "done"

            db.add(transfer_request)

        invoice.status = "paid"
        invoice.description = description
        invoice.card = card_type
        db.add(invoice)
        manager_user = db.query(UserModel).filter(UserModel.id == user.id).first()
    
        name = ""

        if employee and not employee.employee.first_name and not employee.employee.last_name:
            name = employee.employee.cv.english_full_name
        elif employee:
            name = f"{employee.employee.first_name} {employee.employee.last_name}"

        db.commit()

        manager_email = manager_user.email or manager_user.company.alternative_email

        requester_user = db.query(UserModel).filter(UserModel.id == transfer_requests[0].requester_id).first()

        requester_email = requester_user.email or requester_user.company.alternative_email

        title = "Transfer"

        description = (
            f"{manager_user.company.company_name} has transferred {name} to you. "
            f"The contact information for {manager_user.company.company_name} are: {manager_email}, {manager_user.phone_number}, {manager_user.company.location}."
        )

        background_tasks.add_task(send_notification, db, requester_user.id, title, description, "transfer")

        background_tasks.add_task(send_email, email=requester_email, title=title, description=description)

        title = "Transfer Finished"

        description = f"The contact information for {requester_user.company.company_name} are: {requester_email}, {requester_user.phone_number}, {requester_user.company.location}."

        background_tasks.add_task(send_notification, db, manager_user.id, title, description, "transfer")

        background_tasks.add_task(send_email, email=manager_email, title=title, description=description)

        return {"status": "success", "message": "Payment successful"}
    except Exception as e:
        print(e)
        db.rollback()
        return Response(status_code=400, content=json.dumps({"message": "Failed to process payment"}), media_type="application/json")

'''
@transfer_router.post("/return")
async def transfer_return_employee(data: TransferRequestReturn, background_tasks: BackgroundTasks, _=Depends(authentication_context), __=Depends(build_request_context)):
    db = get_db_session()
    
    user = context_actor_user_data.get()

    request_transfer = db.query(TransferRequestModel).filter(TransferRequestModel.user_id == data.id, TransferRequestModel.manager_id == user.id, TransferRequestModel.status == "done").first()
    
    if not request_transfer:
        return Response(status_code=400, content=json.dumps({"message": "Transfer request not found"}), media_type="application/json")
    
    # Check if the user have related agent or recruitment
    if user.role == "agent":
        relationship = db.query(AgentRecruitmentModel).filter(AgentRecruitmentModel.agent_id == user.id, AgentRecruitmentModel.recruitment_id == request_transfer.requester_id).first()
        if not relationship:
            return Response(status_code=400, content=json.dumps({"message": "You are not authorized to return this employee"}), media_type="application/json")

    if user.role == "recruitment":
        relationship = db.query(AgentRecruitmentModel).filter(AgentRecruitmentModel.recruitment_id == user.id, AgentRecruitmentModel.agent_id == request_transfer.requester_id).first()
        if not relationship:
            return Response(status_code=400, content=json.dumps({"message": "You are not authorized to return this employee"}), media_type="application/json")
    
    employee = db.query(EmployeeModel).filter(EmployeeModel.user_id == data.id).first()


    if employee:
        employee.manager_id = user.id
        db.add(employee)
    
    request_transfer.status = "returned"

    db.add(request_transfer)
    _user = db.query(UserModel).filter(UserModel.id == user.id).first()

    name = ""

    if not employee.employee.first_name and not employee.employee.last_name:
        name = employee.employee.cv.english_full_name
    else:
        name = f"{employee.employee.first_name} {employee.employee.last_name}"

    try:
        db.commit()
        background_tasks.add_task(send_notification, db, request_transfer.requester_id, "Transfer", f"{_user.company.company_name} has took back {name}", "transfer")
        _user = db.query(UserModel).filter(UserModel.id == request_transfer.requester_id).first()

        email = _user.email or _user.company.alternative_email

        background_tasks.add_task(func=send_email, email=email, title="Transfer", description=f"{_user.company.company_name} has took back {name}")
        return {"status": "success", "message": "Employee returned"}
    
    except Exception as e:
        print(e)
        db.rollback()
        return Response(status_code=400, content=json.dumps({"message": "Failed to return employee"}), media_type="application/json")

@transfer_router.get("/income", response_model=list[BatchTransferReadSchema])
async def get_income_transfer(_=Depends(HTTPBearer(scheme_name="bearer")), __
=Depends(build_request_context)):
    db = get_db_session()

    user = context_actor_user_data.get()

    batch = db.query(BatchTransferModel).filter(
        BatchTransferModel.receiver_id == user.id).all()

    return batch

@transfer_router.get("/process", response_model=list[BatchTransferReadSchema])
async def get_process_transfer(_=Depends(HTTPBearer(scheme_name="bearer")), __
=Depends(build_request_context)):
    try:
        db = get_db_session()

        user = context_actor_user_data.get()

        batch = db.query(BatchTransferModel).filter(
            BatchTransferModel.requester_id == user.id).all()
        batch_data = []

        for batch in batch:
            agent = None
            recruitment = None
            if batch.receiver.role == "agent":
                agent = batch.receiver.id
            elif batch.receiver.role == "recruitment":
                recruitment = batch.receiver.id
            
            if batch.requester.role == "agent":
                agent = batch.requester.id
            elif batch.requester.role == "recruitment":
                recruitment = batch.requester.id

            relationship = None
            if agent and recruitment:  # Only query if both agent and recruitment are not None
                relationship = db.query(AgentRecruitmentModel).filter(
                    AgentRecruitmentModel.agent_id == agent,
                    AgentRecruitmentModel.recruitment_id == recruitment,
                    AgentRecruitmentModel.status == "approved"
                ).first()

            batch_data.append({
                "id": batch.id,
                "receiver_id": batch.receiver_id,
                "receiver": batch.receiver,
                "requester_id": batch.requester_id,
                "requester": batch.requester,
                "transfers": batch.transfers,
                "created_at": batch.created_at,
                "relationship": bool(relationship),
            })

        return batch_data
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "Failed to get process transfer"}), media_type="application/json")


@transfer_router.post("/info")
async def transfer_pay_info(
    data: TransferInfoSchema,
    _=Depends(authentication_context),
    __=Depends(build_request_context),
):
    try:
        db = get_db_session()
        user = context_actor_user_data.get()

        package = (
            db.query(PromotionPackagesModel)
            .filter(
                PromotionPackagesModel.role == user.role,
                PromotionPackagesModel.category == "transfer",
            )
            .first()
        )
        if not package:
            return Response(status_code=404, content="Package not found")

        transfers = (
            db.query(TransferRequestModel)
            .filter(
                TransferRequestModel.id.in_(data.transfer_request_ids),
                TransferRequestModel.manager_id == user.id,
                TransferRequestModel.status == "accepted",
            )
            .all()
        )

        if not transfers:
            return Response(status_code=404, content="Transfer request not found")

        total_amount = package.price * len(transfers)

        return {
            "price": package.price,
            "profile": len(transfers),
            "total_amount": total_amount,
        }

    except Exception as e:
        return Response(status_code=400, content="Failed to get transfer info")


'''
@transfer_router.post("/info")
async def transfer_pay_info(
    data: TransferRequestPaymentSchema,
    _=Depends(authentication_context),
    __=Depends(build_request_context)
):
    try:
        db = get_db_session()
 
        user = context_actor_user_data.get()

        package = db.query(PromotionPackagesModel).filter(PromotionPackagesModel.role == user.role, PromotionPackagesModel.category == "transfer").first()

        transfer_requests = db.query(TransferRequestModel).filter(
            TransferRequestModel.id.in_(data.transfer_request_ids),
            TransferRequestModel.manager_id == user.id,
            TransferRequestModel.status == "accepted"
        ).all()

        if not transfer_requests:
            return Response(status_code=404, content=json.dumps({"message": "Transfer request not found"}))

        amount = package.price * len(transfer_requests)

        return {
            "price": package.price,
            "total_amount": amount,
            "profile": len(transfer_requests)
        }
 
    except Exception as e:
        print(e)
        return Response(status_code=400, content=json.dumps({"message": "Failed to get transfer pay info"}), media_type="application/json")
        '''
