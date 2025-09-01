# -*- coding:utf-8 -*-
"""
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class AssetBase(BaseModel):
    name: str


class AssetCreate(AssetBase):
    pass


class Asset(AssetBase):
    id: int
    created_at: datetime
    is_deleted: bool = False

    class Config:
        from_attributes = True


class AssetHistoryBase(BaseModel):
    value: float
    timestamp: datetime


class AssetHistoryCreate(AssetHistoryBase):
    asset_id: int


class AssetHistory(AssetHistoryBase):
    id: int
    asset_id: int

    class Config:
        from_attributes = True