"""
Umbrella Demo App (Karamstay PG Rental Service): Database Engine & Connection Manager
Configures SQLAlchemy QueuePool with dynamic pooling, metrics tracking, and auto-seeding.
"""

import importlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

import config
from models import Base, Room, Booking, RentPayment

engine = None
SessionLocal = None


def reload_config():
    """Reloads config from disk."""
    importlib.reload(config)
    return init_db()


def init_db():
    """Initializes or disposes and refreshes the database engine pool."""
    global engine, SessionLocal

    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass

    connect_args = {"check_same_thread": False, "timeout": 20.0} if "sqlite" in config.DATABASE_URL else {}
    engine = create_engine(
        config.DATABASE_URL,
        poolclass=QueuePool,
        pool_size=config.POOL_SIZE,
        max_overflow=config.MAX_OVERFLOW,
        pool_timeout=config.POOL_TIMEOUT,
        connect_args=connect_args
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed_karamstay_rooms()
    return engine, SessionLocal


def get_db():
    """FastAPI database session dependency."""
    global SessionLocal
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_karamstay_rooms():
    """Seeds realistic Karamstay PG room inventory."""
    global SessionLocal
    db = SessionLocal()
    try:
        if db.query(Room).count() == 0:
            room_specs = [
                ("ROOM-101", "Single Bed Deluxe (AC)", 12500.0, 1, "AC, Attached Bath, Study Table, High-Speed WiFi"),
                ("ROOM-102", "Double Sharing Bed (AC)", 8500.0, 1, "AC, Balcony, Attached Bath, WiFi, Daily Cleaning"),
                ("ROOM-103", "Double Sharing Bed (AC)", 8500.0, 1, "AC, Attached Bath, Wardrobe, WiFi"),
                ("ROOM-104", "Triple Sharing Budget", 6500.0, 1, "Spacious Wardrobe, Geyser, RO Water, 3-Meal Food"),
                ("ROOM-201", "Executive Single Suite", 14500.0, 2, "Private Balcony, Smart TV, AC, Fridge, WiFi"),
                ("ROOM-202", "Double Sharing Bed (AC)", 8500.0, 2, "AC, Attached Bath, Daily Housekeeping"),
                ("ROOM-203", "Single Bed Deluxe", 11500.0, 2, "AC, Geyser, High-Speed WiFi, Work Desk"),
                ("ROOM-204", "Triple Sharing Budget", 6500.0, 2, "Power Backup, RO Water, 3-Meal Food"),
                ("ROOM-301", "Penthouse Balcony Studio", 16000.0, 3, "Panoramic Terrace, AC, Microwave, Smart Lock"),
                ("ROOM-302", "Double Sharing Bed (AC)", 8500.0, 3, "AC, Attached Bath, Biometric Entry"),
                ("ROOM-303", "Single Bed Deluxe", 11500.0, 3, "AC, Study Setup, High-Speed Fiber WiFi"),
                ("ROOM-304", "Double Sharing Bed", 7500.0, 3, "Geyser, RO Water, Daily Housekeeping")
            ]
            for r_num, r_type, rent, flr, amen in room_specs:
                r = Room(
                    room_number=r_num,
                    room_type=r_type,
                    monthly_rent=rent,
                    floor=flr,
                    amenities=amen,
                    is_available=True
                )
                db.add(r)
            db.commit()

            # Seed an initial sample booking for testing payments
            initial_room = db.query(Room).first()
            sample_booking = Booking(
                tenant_name="Aarav Sharma",
                phone="+91 98765 43210",
                room_id=initial_room.id if initial_room else 1,
                bed_number="Bed-A",
                status="confirmed"
            )
            db.add(sample_booking)
            db.commit()
    finally:
        db.close()


# Auto-initialize on import
init_db()
