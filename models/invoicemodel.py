import uuid
from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import EntityBaseModel
from .db import Base

class InvoiceModel(Base, EntityBaseModel):
    __tablename__ = "table_invoices"
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_users.id"), nullable=True
    )
    stripe_session_id: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(255), default="unpaid")
    amount: Mapped[float] = mapped_column(Float())
    currency: Mapped[str] = mapped_column(String, default="aed")
    type: Mapped[str] = mapped_column(String, nullable=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("table_users.id"), nullable=True)
    object_id: Mapped[str] = mapped_column(String, nullable=True)
    card = mapped_column(String, nullable=True)
    description = mapped_column(String, nullable=True)

     # 🔥 ADD THIS
    reference = mapped_column(String(255), nullable=True)

        # Invoice identity
    invoice_number = mapped_column(String(50), unique=True, nullable=True)
    invoice_file = mapped_column(String(255), nullable=True)
    # Payment reference
    payment_id = mapped_column(String(255), nullable=True)
    # Status
    type: Mapped[str] = mapped_column(String(50), nullable=True)
    

    # 🧾 SAFE CARD DATA (PCI-COMPLIANT)
    card_holder = mapped_column(String(255), nullable=True)
    card_brand = mapped_column(String(50), nullable=True)
    card_last4 = mapped_column(String(4), nullable=True)

    # 📬 Billing info
    billing_email = mapped_column(String(255), nullable=True)
    billing_phone = mapped_column(String(30), nullable=True)
    billing_country = mapped_column(String(2), nullable=True)    

