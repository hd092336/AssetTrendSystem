# -*- coding:utf-8 -*-
"""
"""
from datetime import datetime

from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class User(UserBase):
    id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


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
