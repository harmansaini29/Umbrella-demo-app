"""
Umbrella Demo App (Karamstay PG Rental Service): SQLAlchemy Models
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Room(Base):
    """Represents a room in the Karamstay PG property."""
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(50), unique=True, index=True, nullable=False)
    room_type = Column(String(100), default="Single Bed Deluxe")
    monthly_rent = Column(Float, default=9500.0)
    floor = Column(Integer, default=1)
    amenities = Column(String(255), default="High-Speed WiFi, AC, Daily Housekeeping, RO Water")
    is_available = Column(Boolean, default=True)

    bookings = relationship("Booking", back_populates="room")


class Booking(Base):
    """Represents a tenant's room booking."""
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_name = Column(String(100), nullable=False)
    phone = Column(String(20), default="+91 98765 43210")
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    bed_number = Column(String(10), default="Bed-A")
    status = Column(String(50), default="confirmed")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    room = relationship("Room", back_populates="bookings")
    payments = relationship("RentPayment", back_populates="booking")


class RentPayment(Base):
    """Represents a monthly rent transaction."""
    __tablename__ = "rent_payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    tenant_name = Column(String(100), nullable=False)
    amount = Column(Float, default=8500.0)
    payment_method = Column(String(50), default="UPI / Razorpay")
    status = Column(String(50), default="completed")
    transaction_ref = Column(String(100), unique=True, index=True)
    invoice_id = Column(String(100), unique=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    booking = relationship("Booking", back_populates="payments")
