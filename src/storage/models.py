from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Instrument(Base):
    __tablename__ = "instruments"

    ticker = Column(String, primary_key=True, index=True)
    name = Column(String)
    sector = Column(String, nullable=True)
    listing_status = Column(String, default="ACTIVE")
    last_updated = Column(DateTime, default=datetime.utcnow)

    market_data = relationship("MarketData", back_populates="instrument")
    signals = relationship("Signal", back_populates="instrument")


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticker = Column(String, ForeignKey("instruments.ticker"), index=True)
    timestamp = Column(DateTime, index=True)
    timeframe = Column(String, index=True)  # e.g., '1D', '1H'
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)

    instrument = relationship("Instrument", back_populates="market_data")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticker = Column(String, ForeignKey("instruments.ticker"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    signal_type = Column(String)  # BUY, SELL, WATCHLIST
    setup_name = Column(String)
    score = Column(Float)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    target_1 = Column(Float)
    risk_reward = Column(Float)
    status = Column(String, default="ACTIVE")  # ACTIVE, HIT_TP1, STOPPED, INVALIDATED

    instrument = relationship("Instrument", back_populates="signals")


class ScanRun(Base):
    """One completed market-wide scan shared by every bot user.

    Scan output is intentionally independent of ``Instrument`` so a failed
    universe synchronisation cannot discard a useful research snapshot.
    """
    __tablename__ = "scan_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    total_scanned = Column(Integer, nullable=False, default=0)
    candidate_count = Column(Integer, nullable=False, default=0)

    candidates = relationship("ScanCandidate", back_populates="scan_run", cascade="all, delete-orphan")


class ScanCandidate(Base):
    """A ranked candidate captured as part of a :class:`ScanRun`."""
    __tablename__ = "scan_candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False, index=True)
    signal_type = Column(String, nullable=False)
    setup_name = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    reference_price = Column(Float, nullable=True)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_1 = Column(Float, nullable=True)
    risk_reward = Column(Float, nullable=True)

    scan_run = relationship("ScanRun", back_populates="candidates")


class UserProfile(Base):
    """Minimal account record keyed by Telegram's stable user identifier."""
    __tablename__ = "user_profiles"

    telegram_user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    subscription_tier = Column(String, nullable=False, default="FREE")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    followed_candidates = relationship("FollowedCandidate", back_populates="user", cascade="all, delete-orphan")


class FollowedCandidate(Base):
    """A user-selected candidate copied from a scan snapshot for monitoring."""
    __tablename__ = "followed_candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, ForeignKey("user_profiles.telegram_user_id"), nullable=False, index=True)
    ticker = Column(String, nullable=False)
    followed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source_scan_run_id = Column(Integer, ForeignKey("scan_runs.id"), nullable=False)
    signal_type = Column(String, nullable=False)
    setup_name = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    reference_price = Column(Float, nullable=True)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_1 = Column(Float, nullable=True)
    risk_reward = Column(Float, nullable=True)

    user = relationship("UserProfile", back_populates="followed_candidates")


class AlertEvent(Base):
    """A deduplication record for a notification sent to one user."""
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    followed_candidate_id = Column(Integer, ForeignKey("followed_candidates.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    price = Column(Float, nullable=False)


class AlertPreference(Base):
    __tablename__ = "alert_preferences"

    telegram_user_id = Column(BigInteger, ForeignKey("user_profiles.telegram_user_id"), primary_key=True)
    entry_zone_enabled = Column(Integer, nullable=False, default=1)
    breakout_enabled = Column(Integer, nullable=False, default=1)
    target_1_enabled = Column(Integer, nullable=False, default=1)
