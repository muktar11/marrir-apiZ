from datetime import datetime
from http.client import HTTPException
from operator import or_
from typing import Any, Dict, Optional, Union, Generic, List, cast
import uuid
from sqlalchemy import not_, cast

from fastapi import File, UploadFile
from fastapi.encoders import jsonable_encoder
import pandas as pd
from core.auth import RBACAccessType
from core.context_vars import context_set_response_code_message, context_actor_user_data
from sqlalchemy import select
from sqlalchemy import BinaryExpression, and_, column, update
from sqlalchemy.sql.operators import like_op
from sqlalchemy.orm import Session, joinedload
from models.batchreservemodel import BatchReserveModel
from models.cvmodel import CVModel
from models.employeemodel import EmployeeModel
from models.notificationmodel import NotificationModel, Notifications
from models.promotionmodel import PromotionModel
from models.reservemodel import RecruitmentReserveModel, RecruitmentSetReserveModel, ReserveModel
from sqlalchemy.sql import exists
from models.agentrecruitmentmodel import AgentRecruitmentModel
from models.usermodel import UserAgentRecruitment, UserModel

from repositories.base import (
    BaseRepository,
    EntityType,
    UpdateSchemaType,
    CreateSchemaType,
    FilterSchemaType,
)
from repositories.notification import NotificationRepository
from schemas.base import BaseGenericResponse
from schemas.notificationschema import (
    NotificationCreateSchema,
    NotificationReceipentTypeSchema,
    NotificationTypeSchema,
)
from schemas.reserveschema import (
    MultipleReserveFilterSchema,
    RecruitmentSetReserveCreateSchema,
    ReserveCVFilterSchema,
    ReserveCreateSchema,
    ReserveFilterSchema,
    ReserveSingleCreateSchema,
)
from schemas.transferschema import TransferStatusSchema
from schemas.userschema import UserRoleSchema
import logging
import traceback

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID

# Configure logging
logger = logging.getLogger(__name__)

class ReserveRepository(
    BaseRepository[ReserveModel, ReserveCreateSchema, ReserveCreateSchema]
):
    def get_received_reserve_requests(self, db: Session, skip: int, limit: int):
        user = context_actor_user_data.get()
        reserves = db.query(ReserveModel).filter_by(owner_id=user.id).all()
        # Get the reservers batch reserve
        batch_reserve_ids = [reserve.batch_id for reserve in reserves]
        batch_reserves = (
            db.query(BatchReserveModel)
            .filter(BatchReserveModel.id.in_(batch_reserve_ids))
            .all()
        )
        return batch_reserves

    def get_received_reserve_requests_details(
        self,
        db: Session,
        batch_reserve_id: int
        ) -> list[EntityType]:
        # Get the reservers from the batch reserve
        reservers = db.query(ReserveModel).filter_by(batch_id=batch_reserve_id).all()

        return reservers

        user = context_actor_user_data.get()
        query = (
            db.query(ReserveModel)
            .join(CVModel, ReserveModel.cv_id == CVModel.id)
            .join(EmployeeModel, CVModel.user_id == EmployeeModel.user_id)
            .filter(
                ReserveModel.batch_id == batch_reserve_id,
                EmployeeModel.manager_id == user.id
            )
            .options(
                joinedload(ReserveModel.cv),
                joinedload(ReserveModel.reserver),
            )
        )
        if search:
            search_filter = self.build_generic_search_filter(
                CVModel, search_schema, search
            )
            if search_filter is not None:
                query = query.filter(search_filter)

        filters_conditions = self.custom_cv_filter(
            CVModel, filters.__dict__ if filters else {}
        )

        query = query.filter(filters_conditions)
        total_count = query.count()

        entities = query.offset(skip).limit(limit).all()

        context_set_response_code_message.set(
            BaseGenericResponse(
                error=False,
                message=f"{self.entity.get_resource_name(ReserveModel.__name__)}s found",
                status_code=200,
                count=total_count,
            )
        )
        return entities


    def get_reserve_requests_sent(
        self,
        db: Session,
        skip: int,
        limit: int,
        filters: FilterSchemaType,
    ) -> List[EntityType]:
        query = db.query(BatchReserveModel)
        filters_conditions = self.build_filters(
            BatchReserveModel, filters.__dict__ if filters else {}
        )
        query = query.filter(filters_conditions)
        total_count = query.count()

        entities = query.offset(skip).limit(limit).all()
        can_not_read = [
            self.is_allowed_or_is_owner(entity, RBACAccessType.read_multiple)
            for entity in entities
        ].__contains__(False)

        if can_not_read:
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"{self.entity.get_resource_name(ReserveModel.__name__)}s not found / not found in the ",
                    status_code=404,
                )
            )
        elif len(entities) == 0:
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"No {self.entity.get_resource_name(ReserveModel.__name__)}s found",
                    status_code=200,
                    count=0,
                )
            )
        else:
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"{self.entity.get_resource_name(ReserveModel.__name__)}s found",
                    status_code=200,
                    count=total_count,
                )
            )
        return entities

    def get_reserver_reserves(
        self,
        db: Session,
        skip: int,
        limit: int,
        filters: Optional[ReserveFilterSchema] = None,
    ):
        query = db.query(BatchReserveModel).filter_by(reserver_id=filters.reserver_id)
        total_count = query.count()

        entities = query.offset(skip).limit(limit).all()

        can_not_read = [
            self.is_allowed_or_is_owner(entity, RBACAccessType.read_multiple)
            for entity in entities
        ].__contains__(False)

        if can_not_read:
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"{self.entity.get_resource_name(self.entity.__name__)}s not found / not found in the ",
                    status_code=404,
                )
            )
        elif len(entities) == 0:
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"No {self.entity.get_resource_name(self.entity.__name__)}s found",
                    status_code=200,
                    count=0,
                )
            )
        else:
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"{self.entity.get_resource_name(self.entity.__name__)}s found",
                    status_code=200,
                    count=total_count,
                )
            )
        return entities

    def get_filtered_employee_cvs(
        self,
        db: Session,
        skip: int,
        limit: int,
        search: Optional[str],
        search_schema: Optional[any],
        filters: Optional[ReserveCVFilterSchema] = None,
    ):
        user = context_actor_user_data.get()

        # Get user IDs of employees who are in the PromotionModel
        promoted_employee_ids = (
                db.query(PromotionModel.user_id)
                .filter(PromotionModel.status == "active", PromotionModel.promoted_by_id != user.id)
                .distinct()
                .all()
            )
        promoted_employee_ids = [id[0] for id in promoted_employee_ids]

        query = (
            db.query(CVModel)
            .filter(
                CVModel.user_id.in_(promoted_employee_ids),  # Only include promoted employees
                ~db.query(ReserveModel)
                .filter(
                    ReserveModel.cv_id == CVModel.id,
                    ReserveModel.status.in_([TransferStatusSchema.PENDING, TransferStatusSchema.ACCEPTED])
                )
                .exists()
            )
        )

        if search:
            search_filter = self.build_generic_search_filter(CVModel, search_schema, search)
            if search_filter is not None:
                query = query.filter(search_filter)


        # Apply additional filters
        # TODO: make the frontend send none or empty dict if they are not filtering
        # filters_conditions = self.custom_cv_filter(CVModel, filters.__dict__ if filters else {})
        # query = query.filter(filters_conditions)

        total_count = query.count()

        cv_info = query.offset(skip).limit(limit).all()

        context_set_response_code_message.set(
            BaseGenericResponse(
                error=False,
                message="Filtered promoted employees' CVs found",
                status_code=200,
                count=total_count,
            )
        )

        return cv_info

    def get_all_active_promoted_employee_cvs(
        self,
        db: Session,
        skip: int,
        limit: int
    ):
        # Get user IDs of actively promoted employees (no self-promotion check)
        promoted_employee_ids = (
            db.query(PromotionModel.user_id)
            .filter(PromotionModel.status == "active")
            .distinct()
            .all()
        )
        promoted_employee_ids = [id[0] for id in promoted_employee_ids]

        # Query CVs for those users, excluding ones already in Reserve with pending or accepted status
        query = (
            db.query(CVModel)
            .filter(
                CVModel.user_id.in_(promoted_employee_ids),
                ~db.query(ReserveModel)
                .filter(
                    ReserveModel.cv_id == CVModel.id,
                    ReserveModel.status.in_([
                        TransferStatusSchema.PENDING,
                        TransferStatusSchema.ACCEPTED
                    ])
                )
                .exists()
            )
        )

        total_count = query.count()

        cv_info = query.offset(skip).limit(limit).all()

        context_set_response_code_message.set(
            BaseGenericResponse(
                error=False,
                message="Active promoted employees' CVs found",
                status_code=200,
                count=total_count,
            )
        )

        return cv_info


    def custom_cv_filter(self, model, filters_dict):
        conditions = []

        for key, value in filters_dict.items():
            if (
                value is not None
                and not key.startswith("min_")
                and not key.startswith("max_")
                and key not in ["nationality", "occupation", "education_level"]
            ):
                field = getattr(model, key, None)
                if field is not None:
                    conditions.append(field == value)                

        array_filters = ["nationality", "occupation"]

        for key in array_filters:
            values = filters_dict.get(key)
            if values:
                model_field = getattr(model, key, None)
                if model_field is not None and values:
                    conditions.append(model_field.in_(values))

        range_filters = [
            ("min_height", "max_height", "height"),
            ("min_weight", "max_weight", "weight"),
            ("min_age", "max_age", "age"),
        ]

        for min_key, max_key, model_field in range_filters:
            min_value = filters_dict.get(min_key)
            max_value = filters_dict.get(max_key)
            field = getattr(model, model_field, None)

            if field is not None:
                if min_value is not None:
                    conditions.append(field >= min_value)
                if max_value is not None:
                    conditions.append(field <= max_value)

        return and_(*conditions)

    


    def send_reserve_request(self, db: Session, *, obj_in: ReserveCreateSchema) -> Any:
        try:
            user = context_actor_user_data.get()
            if not user or not getattr(user, "id", None):
                logger.debug("[TRACE] No user found in context")
                context_set_response_code_message.set(
                    BaseGenericResponse(
                        error=True,
                        message="User not authenticated. Please log in first.",
                        status_code=401,
                    )
                )
                return None

            logger.debug(f"[TRACE] User from context: id={getattr(user, 'id', None)}, email={getattr(user, 'email', None)}")

            reserves = []
            skipped_cvs = []

            batch_reserve = BatchReserveModel(reserver_id=user.id)
            db.add(batch_reserve)
            db.commit()
            db.refresh(batch_reserve)
            logger.debug(f"[TRACE] Created batch_reserve with ID: {batch_reserve.id}")

            for cv_id in obj_in.cv_id:
                logger.debug(f"[TRACE] Processing CV ID: {cv_id}")

                pending_reserve = (
                    db.query(ReserveModel)
                    .filter(
                        ReserveModel.cv_id == cv_id,
                        ReserveModel.reserver_id == user.id,
                        ReserveModel.status == TransferStatusSchema.PENDING,
                    )
                    .first()
                )

                if pending_reserve:
                    skipped_cvs.append(cv_id)
                    continue

                cv = db.query(CVModel).filter_by(id=cv_id).first()
                if not cv:
                    skipped_cvs.append(cv_id)
                    continue

                single_reserve = ReserveSingleCreateSchema(cv_id=cv_id, reserver_id=user.id)
                obj_in_data = jsonable_encoder(single_reserve)
                db_obj = self.entity(**obj_in_data)
                db_obj.batch_id = batch_reserve.id
                reserves.append(db_obj)

            if reserves:
                db.bulk_save_objects(reserves)
                db.commit()

            # Build response
            message = f"{self.entity.get_resource_name(self.entity.__name__)} requested for {len(reserves)} employees."
            if skipped_cvs:
                message += f" Skipped {len(skipped_cvs)} CV(s): {', '.join(map(str, skipped_cvs))} (already reserved or not found)."

            context_set_response_code_message.set(
                BaseGenericResponse(error=False, message=message, status_code=200)
            )
            return reserves

        except Exception as e:
            logger.error("Error in send_reserve_request", exc_info=True)
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=True,
                    message=f"An error occurred while processing the reserve request: {str(e)}",
                    status_code=500,
                )
            )
            return None



    def accept_decline_reserve_request(
        self,
        db: Session,
        filter_obj_in: MultipleReserveFilterSchema,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> EntityType:
        reserves = []
        for cv_id in filter_obj_in.cv_ids:
            query = update(self.entity)
            entity = (
                db.query(ReserveModel)
                .filter_by(cv_id=cv_id, batch_id=filter_obj_in.batch_id)
                .first()
            )

            # can not update must check ownership. temporarly commented out
            # can_not_update = (
            #     self.is_allowed_or_is_owner(
            #         entity=entity, access_type=RBACAccessType.update
            #     )
            #     is False
            # )

            if entity is None:
                context_set_response_code_message.set(
                    BaseGenericResponse(
                        error=True,
                        message=f"{self.entity.get_resource_name(self.entity.__name__)} not found while trying to update",
                        status_code=404,
                    )
                )
                return []

            if isinstance(obj_in, dict):
                update_data = obj_in
            else:
                update_data = obj_in.dict(exclude_unset=True)

            if update_data["status"] == TransferStatusSchema.ACCEPTED:
                entity.status = TransferStatusSchema.ACCEPTED
                cv = db.query(CVModel).filter(CVModel.id == cv_id).first()
                name = cv.english_full_name
                if not cv.english_full_name:
                    user = db.query(UserModel.first_name, UserModel.last_name).filter_by(id = cv.user_id).first()
                    name = user[0] + " " + user[1]
                reserves.append(entity)

            elif update_data["status"] == TransferStatusSchema.DECLINED:
                entity.status = TransferStatusSchema.DECLINED
                entity.reason = update_data["reason"]
                reserves.append(entity)
                
        context_set_response_code_message.set(
            BaseGenericResponse(
                error=False,
                message=f"{len(reserves)} reserve requests updated successfully",
                status_code=200,
            )
        )
        return reserves
    
    '''
    def get_not_reserved_by_me(self, db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 10):
        # Subquery: CVs reserved by me
        reserved_cv_user_ids_subquery = (
            select(CVModel.user_id)
            .join(ReserveModel, ReserveModel.cv_id == CVModel.id)
            .filter(ReserveModel.reserver_id == user_id)
            .subquery()
        )
        # Final query: promotions not promoted by me, and whose users I haven't reserved their CVs
        query = db.query(PromotionModel).filter(
            PromotionModel.promoted_by_id != user_id,
            PromotionModel.user_id.notin_(select(reserved_cv_user_ids_subquery.c.user_id))
        )
        total_count = query.count()
        promotions = query.offset(skip).limit(limit).all()
        return {
            "data": [
                {
                    **promotion.__dict__,
                    "promoter": {
                        "id": promotion.promoted_by.id,
                        "full_name": f"{promotion.promoted_by.first_name or ''} {promotion.promoted_by.last_name or ''}".strip(),
                        "email": promotion.promoted_by.email,
                        "phone_number": promotion.promoted_by.phone_number,
                        "role": promotion.promoted_by.role,
                    }
                }
                for promotion in promotions
            ],
            "count": total_count
        }

    '''
    '''
    def get_not_reserved_by_me(
        self,
        db: Session,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        nationality: str = None,
    ):
        # Base query
        query = db.query(CVModel)

        # Apply nationality filter if provided
        if nationality:
            query = query.filter(CVModel.nationality == nationality)

        # Count BEFORE applying pagination
        total_count = query.count()

        # Apply pagination
        cvs = query.offset(skip).limit(limit).all()

        # Build results (no need to query PromotionModel since you're returning CVs)
        results = []
        for cv in cvs:
            results.append({
                **cv.__dict__,
                "cv": {
                    "id": cv.id,
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
                }
            })

        return {
            "data": results,
            "count": total_count
        }

    '''

    
    '''
    def get_not_reserved_by_me(
        self,
        db: Session,
        user_id: uuid.UUID,
        nationality: str = None,
        skip: int = 0,
        limit: int = 10,
    ):
        # Step 1: get related recruitment/agent IDs
        related_recruitment_ids = (
            db.query(UserAgentRecruitment.recruitment_id)
            .filter(UserAgentRecruitment.agent_id == user_id)
            .subquery()
        )

        related_agent_ids = (
            db.query(UserAgentRecruitment.agent_id)
            .filter(UserAgentRecruitment.recruitment_id == user_id)
            .subquery()
        )

        query = None

        # Step 2: determine if user is agent or recruitment
        if db.query(UserAgentRecruitment).filter(UserAgentRecruitment.agent_id == user_id).first():
            # user is agent → get CVs of recruitments
            query = (
                db.query(CVModel)
                .join(UserModel, cast(CVModel.creator_id, UUID) == UserModel.id)
                .filter(UserModel.id.in_(related_recruitment_ids))
            )
        elif db.query(UserAgentRecruitment).filter(UserAgentRecruitment.recruitment_id == user_id).first():
            # user is recruitment → get CVs promoted by agents
            query = (
                db.query(CVModel)
                .join(UserModel, cast(CVModel.creator_id, UUID) == UserModel.id)
                .filter(UserModel.id.in_(related_agent_ids))
            )
        
        if not query:
            return {"data": [], "count": 0}

        # Step 3: filter by nationality if provided
        if nationality:
            query = query.filter(CVModel.nationality == nationality)

        # Step 4: count total
        total_count = query.count()

        # Step 5: apply pagination
        cvs = query.offset(skip).limit(limit).all()

        # Step 6: build response
        results = [
            {
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
                "expected_salary": cv.expected_salary,
                "currency":cv.currency,
            }
            for cv in cvs
        ]

        return {"data": results, "count": total_count}
    '''
    def get_not_reserved_by_me(
        self,
        db: Session,
        user_id: uuid.UUID,
        nationality: str = None,
        skip: int = 0,
        limit: int = 10,
        reserve_in: Optional[RecruitmentSetReserveCreateSchema] = None,  # ✅ allow optional input
    ):
        """
        Get all CVs created by agents that are linked to a specific recruiter.
        If reserve_in is provided (during save), send a notification to the agent that their CV was recruited.
        """

        # Step 1️⃣: Get current user
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return {"data": [], "count": 0}

        # Step 2️⃣: Ensure the user is a recruiter
        if user.role.lower() != "recruitment":
            return {"data": [], "count": 0}

        # Step 3️⃣: Get all related agent IDs from AgentRecruitmentModel
        related_agent_ids = (
            db.query(AgentRecruitmentModel.agent_id)
            .filter(AgentRecruitmentModel.recruitment_id == user_id)
            .all()
        )
        related_agent_ids = [row.agent_id for row in related_agent_ids]
        if not related_agent_ids:
            return {"data": [], "count": 0}

        # Step 4️⃣: Query CVs created by these agents
        query = (
            db.query(CVModel)
            .join(UserModel, cast(CVModel.creator_id, UUID) == UserModel.id)
            .filter(UserModel.id.in_(related_agent_ids))
        )

        # Step 5️⃣: Get all reserved CV IDs
        reserved_cv_ids = [row.cv_id for row in db.query(RecruitmentSetReserveModel.cv_id).all()]
        if reserved_cv_ids:
            query = query.filter(not_(CVModel.user_id.in_(reserved_cv_ids)))

        # Step 6️⃣: Optional nationality filter
        if nationality:
            query = query.filter(CVModel.nationality == nationality)

        # Step 7️⃣: Count before pagination
        total_count = query.count()

        # Step 8️⃣: Apply pagination
        cvs = query.offset(skip).limit(limit).all()

       

        # Step 🔟: Build response
        results = [
            {
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
                "expected_salary": getattr(cv, "expected_salary", None),
                "currency": getattr(cv, "currency", None),
            }
            for cv in cvs
        ]

        return {"data": results, "count": total_count}




    def reserve_cv(self, db: Session, obj_in: RecruitmentSetReserveCreateSchema):
        # Check if the CV is already reserved
        existing_reserve = db.query(self.entity).filter(
            self.entity.cv_id == obj_in.cv_id
        ).first()

        if existing_reserve:
            raise HTTPException(
                status_code=400,
                detail="This CV is already reserved."
            )

        new_reserve = self.entity(
            recruitment_id=obj_in.recruitment_id,
            cv_id=obj_in.cv_id,
            status=obj_in.status
        )

        db.add(new_reserve)
        db.commit()
        db.refresh(new_reserve)
        return new_reserve

    '''
    def get_not_reserved_by_me(self, db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 10):
        # Subquery: user_ids whose CVs I reserved
        reserved_cv_user_ids_by_me = (
            select(CVModel.user_id)
            .join(ReserveModel, ReserveModel.cv_id == CVModel.id)
            .filter(ReserveModel.reserver_id == user_id)
            .subquery()
        )

        # Subquery: all reserved cv_ids
        all_reserved_cv_ids = (
            select(ReserveModel.cv_id)
            .subquery()
        )

        # Subquery: Promotions not promoted by me and not among the CVs I reserved
        unpromoted_user_ids = (
            select(PromotionModel.user_id)
            .filter(
                PromotionModel.promoted_by_id != user_id,
                PromotionModel.user_id.notin_(select(reserved_cv_user_ids_by_me.c.user_id))
            )
            .subquery()
        )

        # Final query: Get CVs for unpromoted users, not reserved by anyone
        query = db.query(CVModel).filter(
            CVModel.user_id.in_(select(unpromoted_user_ids.c.user_id)),
            CVModel.id.notin_(select(all_reserved_cv_ids.c.cv_id))
        )

        total_count = query.count()
        cvs = query.offset(skip).limit(limit).all()

        return {
            "data": cvs,
            "count": total_count
        }
    '''

    '''
    def get_not_reserved_by_me(self, db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 10):
        # Subquery: user_ids whose CVs I reserved
        reserved_cv_user_ids_by_me = (
            select(CVModel.user_id)
            .join(ReserveModel, ReserveModel.cv_id == CVModel.id)
            .filter(ReserveModel.reserver_id == user_id)
            .subquery()
        )

        # Subquery: all reserved cv_ids
        all_reserved_cv_ids = (
            select(ReserveModel.cv_id)
            .subquery()
        )

        # Subquery: Promotions not promoted by me and not among the CVs I reserved
        unpromoted_user_ids = (
            select(PromotionModel.user_id)
            .filter(
                PromotionModel.promoted_by_id != user_id,
                PromotionModel.user_id.notin_(select(reserved_cv_user_ids_by_me.c.user_id))
            )
            .subquery()
        )

        # Main query: Join CVs to Promotions and Promoter User (manually)
        query = (
            db.query(
                CVModel,
                PromotionModel,
                UserModel
            )
            .join(PromotionModel, PromotionModel.user_id == CVModel.user_id)
            .join(UserModel, UserModel.id == PromotionModel.promoted_by_id)
            .filter(
                CVModel.user_id.in_(select(unpromoted_user_ids.c.user_id)),
                CVModel.id.notin_(select(all_reserved_cv_ids.c.cv_id))
            )
        )

        total_count = query.count()
        rows = query.offset(skip).limit(limit).all()

        # Structure the response manually
        result = []
        for cv, promotion, promoter in rows:
            result.append({
                **cv.__dict__,
                "promoter": {
                    "id": promoter.id,
                    "full_name": f"{promoter.first_name or ''} {promoter.last_name or ''}".strip(),
                    "email": promoter.email,
                    "phone_number": promoter.phone_number,
                    "role": promoter.role,
                }
            })

        return {
            "data": result,
            "count": total_count
        }
    '''

    '''
    def get_not_reserved_by_me(self, db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 10):
        # Subquery: CVs reserved by me
        reserved_cv_user_ids_subquery = (
            select(CVModel.user_id)
            .join(ReserveModel, ReserveModel.cv_id == CVModel.id)
            .filter(ReserveModel.reserver_id == user_id)
            .subquery()
        )

        # Query promotions not promoted by me and not already reserved by me
        query = (
            db.query(PromotionModel)
            .join(PromotionModel.promoted_by)
            .options(joinedload(PromotionModel.promoted_by))
            .filter(
                PromotionModel.promoted_by_id != user_id,
                PromotionModel.user_id.notin_(select(reserved_cv_user_ids_subquery.c.user_id)),
                UserModel.role.in_(["employee", "selfsponsor"])
            )
        )

        total_count = query.count()
        promotions = query.offset(skip).limit(limit).all()

        return {
            "data": [
                {
                    **promotion.__dict__,
                    "promoter": {
                        "id": promotion.promoted_by.id,
                        "full_name": f"{promotion.promoted_by.first_name or ''} {promotion.promoted_by.last_name or ''}".strip(),
                        "email": promotion.promoted_by.email,
                        "phone_number": promotion.promoted_by.phone_number,
                        "role": promotion.promoted_by.role,
                    }
                }
                for promotion in promotions
            ],
            "count": total_count
        }

    '''
