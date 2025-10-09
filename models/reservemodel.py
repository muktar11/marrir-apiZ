from typing import Optional
import uuid

from sqlalchemy import ForeignKey, Integer, String, Enum, DECIMAL, DateTime, Boolean
from models.base import EntityBaseModel
from models.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

from schemas.transferschema import TransferStatusSchema

class ReserveModel(Base, EntityBaseModel):
    __tablename__ = "table_reserves"
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("table_batch_reserves.id"), primary_key=True, nullable=False
    )

    cv_id: Mapped[int] = mapped_column(
        ForeignKey("table_cvs.id"), primary_key=True, nullable=False
    )
    reserver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), primary_key=True, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, default=TransferStatusSchema.PENDING)
    reason: Mapped[str] = mapped_column(String(255), nullable=True)
    batch_reserve = relationship("BatchReserveModel", back_populates="reserves")
    cv = relationship("CVModel", backref="reserve", lazy="select", foreign_keys=[cv_id])
    reserver = relationship("UserModel", backref="reserve", lazy="select", foreign_keys=[reserver_id])
    owner = relationship("UserModel", backref="owned_reserve", lazy="select", foreign_keys=[owner_id])


class RecruitmentSetReserveModel(Base):
    __tablename__ = "table_recruitment_reserves_set"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recruitment_id = mapped_column(String, nullable=True)
    promoter_id = mapped_column(String, nullable=True)
    cv_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), primary_key=True, nullable=False
    )
    buyer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("table_users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String)
    requested: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(default=False)
    rejected: Mapped[bool] = mapped_column(default=False)
    selfsponsor: Mapped[bool] = mapped_column(default=False)
    comment: Mapped[Optional[str]] = mapped_column(nullable=True)

class RecruitmentReserveModel(Base, EntityBaseModel):
    __tablename__ = "table_recruitment_reserves"
    recruitment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), primary_key=True, nullable=False
    )
    
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), primary_key=True, nullable=False
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String, default=TransferStatusSchema.PENDING)

    recruitment = relationship("UserModel", backref="recruitment_reserve", lazy="select", foreign_keys=[recruitment_id])

    sponsor = relationship("UserModel", backref="sponsor_reserve", lazy="select", foreign_keys=[sponsor_id])

    employee = relationship("UserModel", backref="employee_reserve", lazy="select", foreign_keys=[employee_id])

