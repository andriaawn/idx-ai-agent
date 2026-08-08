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
