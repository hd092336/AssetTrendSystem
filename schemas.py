# -*- coding:utf-8 -*-
"""
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class AssetBase(BaseModel):
    name: str


class AssetCreate(AssetBase):
    asset_id: Optional[str] = None


class Asset(AssetBase):
    created_at: datetime = datetime.now()
    is_deleted: bool = False

    class Config:
        orm_mode = True


class AssetHistoryBase(BaseModel):
    value: float
    timestamp: datetime


class AssetHistoryCreate(AssetHistoryBase):
    record_id: Optional[str] = None
    asset_id: str


class AssetHistory(AssetHistoryBase):
    record_id: str
    asset_id: str

    class Config:
        orm_mode = True
