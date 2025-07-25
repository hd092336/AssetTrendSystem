# -*- coding:utf-8 -*-
from sqlalchemy import Column, String, Numeric, TIMESTAMP, ForeignKey, Boolean, func, Index, Integer
from sqlalchemy.orm import relationship
from database import Base


class Asset(Base):

    __tablename__ = 'assets'

    asset_id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())
    is_deleted = Column(Boolean, default=False)
    history_records = relationship("AssetHistory", back_populates="asset")


class AssetHistory(Base):

    __tablename__ = 'asset_history'

    record_id = Column(String(36), primary_key=True)
    asset_id = Column(String(36), ForeignKey('assets.asset_id'), nullable=False)
    value = Column(Numeric(18, 2), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    asset = relationship("Asset", back_populates="history_records")


__table_args__ = (
    Index('idx_asset_id', 'asset_id'),
    Index('idx_timestamp', 'timestamp'),
)
