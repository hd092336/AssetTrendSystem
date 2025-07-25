# -*- coding:utf-8 -*-
"""
"""
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import Asset, AssetHistory
from schemas import Asset, AssetCreate, AssetHistory, AssetHistoryCreate

app = FastAPI()

Base.metadata.create_all(bind=engine)  # 创建数据库表


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/assets/", response_model=Asset)
async def create_asset(asset: AssetCreate, db: Session = Depends(get_db)):
    db_asset = Asset(**asset.model_dump())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset


@app.get("/assets/", response_model=List[Asset])
def read_assets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Asset).filter(Asset.is_deleted == False).offset(skip).limit(limit).all()


@app.get("/assets/{asset_id}", response_model=Asset)
def read_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.asset_id == asset_id, Asset.is_deleted == False).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@app.put("/assets/{asset_id}", response_model=Asset)
def update_asset(asset_id: str, name: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(
        Asset.asset_id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.name = name
    db.commit()
    db.refresh(asset)
    return asset


@app.delete("/assets/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.asset_id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.is_deleted = True
    db.commit()
    return {"message": "Asset soft deleted"}


@app.post("/history/", response_model=AssetHistory)
def create_asset_history(history: AssetHistoryCreate, db: Session = Depends(get_db)):
    db_history = AssetHistory(**history.model_dump())
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history


@app.get("/history/", response_model=List[AssetHistory])
def read_asset_history(
        asset_id: str,
        start_time: datetime = None,
        end_time: datetime = None,
        db: Session = Depends(get_db)
):
    query = db.query(AssetHistory).filter(
        AssetHistory.asset_id == asset_id)
    if start_time:
        query = query.filter(AssetHistory.timestamp >= start_time)
    if end_time:
        query = query.filter(AssetHistory.timestamp <= end_time)
    return query.all()
