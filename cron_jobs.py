from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from models.db import get_db_session
from models.notificationmodel import Notifications
from models.promotionmodel import PromotionPackagesModel, PromotionSubscriptionModel, PromotionModel
from models.reservemodel import ReserveModel, RecruitmentAgentPrivateReserveModel
from models.batchreservemodel import BatchReserveModel
from models.transferrequestmodel import TransferRequestModel
from models.batchtransfermodel import BatchTransferModel
from core.context_vars import context_set_response_code_message
from schemas.base import BaseGenericResponse
from utils.send_email import send_email

def pending_reserves_notification(reserve_id: int, db: Session):
    try:
        reserve = db.query(ReserveModel).filter(ReserveModel.cv_id == reserve_id).first()
        
        if reserve and reserve.status == 'pending':
            notifications = Notifications(
                title="Reserve pay alert",
                description=f"Dear {reserve.cv.english_full_name}, you have reserved a profile, and it has been accepted, but you haven't made the payment yet. Please pay within 1 hour, or the profile will become available for reservation again.",
                user_id=reserve.owner_id,
                type="reserve",
                object_id=reserve_id,
            )
            
            db.add(notifications)
            db.commit()

            email = reserve.owner.email or reserve.owner.company.alternative_email

            send_email(email, notifications.title, notifications.description)
    except Exception as e:
        print(f"Error sending notification to user for reserve with ID {reserve_id}: {str(e)}")


def delete_old_pending_reserve(reserve_id: int, db: Session):
    try:
        reserve = db.query(ReserveModel).filter(ReserveModel.cv_id == reserve_id).first()
        if reserve and reserve.status == 'pending':
            # Assuming ReserveModel has a foreign key to BatchModel
            batch_id = reserve.batch_id
            db.delete(reserve)
            
            other_reserves = db.query(ReserveModel).filter(ReserveModel.batch_id == batch_id).count()
            if other_reserves == 0:
                batch = db.query(BatchReserveModel).filter(BatchReserveModel.id == batch_id).first()
                if batch:
                    db.delete(batch)

            db.commit()
            context_set_response_code_message.set(
                BaseGenericResponse(
                    error=False,
                    message=f"Pending reserve with ID {reserve_id} and associated batch deleted successfully",
                    status_code=200,
                )
            )
    except Exception as e:
        db.rollback()
        context_set_response_code_message.set(
            BaseGenericResponse(
                error=True,
                message=f"Error deleting pending reserve with ID {reserve_id} and associated batch: {str(e)}",
                status_code=500,
            )
        )

def delete_declined_and_cancelled_reserves(db: Session):
    try:
        declined_and_cancelled_reserves = db.query(ReserveModel).filter(
            ReserveModel.status.in_(['declined', 'cancelled', "accepted"])
        ).all()

        for reserve in declined_and_cancelled_reserves:
            # Assuming ReserveModel has a foreign key to BatchModel
            batch_id = reserve.batch_id
            db.delete(reserve)
            
            other_reserves = db.query(ReserveModel).filter(ReserveModel.batch_id == batch_id).count()
            if other_reserves == 0:
                batch = db.query(BatchReserveModel).filter(BatchReserveModel.id == batch_id).first()
                if batch:
                    db.delete(batch)

        db.commit()
        print("Declined and cancelled reserves deleted successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error deleting declined and cancelled reserves: {str(e)}")


def inactive_expired_promotion(db: Session):
    try:
        expired_promotions_subscription = db.query(PromotionSubscriptionModel).filter(
            PromotionSubscriptionModel.status == 'active',
            PromotionSubscriptionModel.end_date < datetime.now(timezone.utc)
        ).all()

        expired_promotions = db.query(PromotionModel).filter(
            PromotionModel.status == 'active',
            PromotionModel.end_date < datetime.now(timezone.utc)
        ).all()

        print(f"Expired promotions s: {expired_promotions_subscription}")
        print(f"Expired promotions: {expired_promotions}")

        for subscription in expired_promotions_subscription:
            subscription.status = 'inactive'
            db.add(subscription)
        
        for promotion in expired_promotions:
            promotion.status = 'inactive'
            db.add(promotion)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error setting expired promotions to inactive: {str(e)}")

def delete_unpaid_private_reserves(db: Session):
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        unpaid_reserves = db.query(RecruitmentAgentPrivateReserveModel).filter(
            RecruitmentAgentPrivateReserveModel.is_paid == False,
            RecruitmentAgentPrivateReserveModel.created_at < cutoff,
        ).all()

        count = len(unpaid_reserves)
        for reserve in unpaid_reserves:
            db.delete(reserve)

        db.commit()
        print(f"Deleted {count} unpaid private reserves older than 24 hours.")
    except Exception as e:
        db.rollback()
        print(f"Error deleting unpaid private reserves: {str(e)}")


def delete_pending_transfer_requests(db: Session):
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        pending_transfers = db.query(TransferRequestModel).filter(
            TransferRequestModel.status == "pending",
            TransferRequestModel.created_at < cutoff,
        ).all()

        count = len(pending_transfers)
        batch_ids = set()
        for transfer in pending_transfers:
            batch_ids.add(transfer.batch_id)
            db.delete(transfer)

        for batch_id in batch_ids:
            remaining = db.query(TransferRequestModel).filter(
                TransferRequestModel.batch_id == batch_id
            ).count()
            if remaining == 0:
                batch = db.query(BatchTransferModel).filter(
                    BatchTransferModel.id == batch_id
                ).first()
                if batch:
                    db.delete(batch)

        db.commit()
        print(f"Deleted {count} pending transfer requests older than 24 hours.")
    except Exception as e:
        db.rollback()
        print(f"Error deleting pending transfer requests: {str(e)}")


scheduler = BackgroundScheduler()
scheduler.start()
