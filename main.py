# -*- coding:utf-8 -*-
"""
"""
from datetime import datetime
from typing import List
from io import BytesIO
import base64
import matplotlib

from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import matplotlib.pyplot as plt
import pandas as pd
from peewee import DoesNotExist

from operations import TrendCalculator, AssetManager, UserManager
from schemas import AssetHistoryCreate, AssetCreate, Asset as AssetResp, AssetHistory as AssetHistoryResp, UserCreate
from models import Asset, AssetHistory, User, db, initialize_db

# 设置matplotlib后端以避免线程问题
matplotlib.use('Agg')

app = FastAPI(title="Asset Trend System", description="API for managing assets and viewing trends", version="1.0.0")

# 配置模板
templates = Jinja2Templates(directory="templates")

# HTTP Basic Auth
security = HTTPBasic()


def get_db():
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    user = UserManager.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="无效的用户名或密码")
    return user


@app.post("/users/register")
async def register_user(user: UserCreate):
    try:
        db_user = UserManager.create_user(user.username, user.email, user.password)
        return {"message": "用户创建成功", "user_id": db_user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/users/login")
async def login_user(credentials: HTTPBasicCredentials = Depends(security)):
    user = UserManager.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="无效的用户名或密码")
    return {"message": "登录成功", "user_id": user.id}


@app.post("/assets/", response_model=AssetResp)
async def create_asset(asset: AssetCreate, current_user: User = Depends(get_current_user)):
    try:
        db_asset = Asset.create(name=asset.name)
        return db_asset
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/assets/", response_model=List[AssetResp])
def read_assets(skip: int = 0, limit: int = 100, current_user: User = Depends(get_current_user)):
    assets = Asset.select().where(Asset.is_deleted == False).offset(skip).limit(limit)
    return [asset for asset in assets]


@app.get("/assets/{asset_id}", response_model=AssetResp)
def read_asset(asset_id: int, current_user: User = Depends(get_current_user)):
    try:
        asset = Asset.get((Asset.id == asset_id) & (Asset.is_deleted == False))
        return asset
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Asset not found")


@app.put("/assets/{asset_id}", response_model=AssetResp)
def update_asset(asset_id: int, asset_data: AssetCreate, current_user: User = Depends(get_current_user)):
    try:
        asset = Asset.get(Asset.id == asset_id)
        query = Asset.update(name=asset_data.name).where(Asset.id == asset_id)
        query.execute()
        asset = Asset.get(Asset.id == asset_id)
        return asset
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Asset not found")


@app.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, current_user: User = Depends(get_current_user)):
    try:
        asset = Asset.get(Asset.id == asset_id)
        query = Asset.update(is_deleted=True).where(Asset.id == asset_id)
        query.execute()
        return {"message": "Asset soft deleted"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Asset not found")


@app.post("/history/", response_model=AssetHistoryResp)
def create_asset_history(history: AssetHistoryCreate, current_user: User = Depends(get_current_user)):
    try:
        asset = Asset.get(Asset.id == history.asset_id)
        db_history = AssetHistory.create(
            asset=history.asset_id,
            value=history.value,
            timestamp=history.timestamp
        )
        return db_history
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Asset not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/history/", response_model=List[AssetHistoryResp])
def read_asset_history(asset_id: int, start_time: datetime = None, end_time: datetime = None,
                       current_user: User = Depends(get_current_user)):
    try:
        Asset.get(Asset.id == asset_id)  # 检查资产是否存在
        query = AssetHistory.select().where(AssetHistory.asset == asset_id)
        if start_time:
            query = query.where(AssetHistory.timestamp >= start_time)
        if end_time:
            query = query.where(AssetHistory.timestamp <= end_time)
        histories = query.order_by(AssetHistory.timestamp)
        return [history for history in histories]
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Asset not found")


@app.get("/trend/plot")
def plot_asset_trend(
        request: Request,
        start_date: datetime = None,
        end_date: datetime = None,
        current_user: User = Depends(get_current_user)
):
    """
    生成资产趋势图并以内联HTML形式返回
    """
    # 如果没有提供日期，默认使用最近30天
    if not start_date:
        start_date = datetime.now().replace(year=datetime.now().year - 1)
    if not end_date:
        end_date = datetime.now()

    # 获取所有资产
    assets = AssetManager.list_assets()
    asset_ids = [asset.id for asset in assets]

    # 计算趋势数据
    trend_data = TrendCalculator.get_asset_trend(
        asset_ids=asset_ids,
        start_date=start_date,
        end_date=end_date
    )

    # 生成趋势图
    df = pd.DataFrame.from_dict(
        trend_data,
        orient='index',
        columns=['Total Value']
    )
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['Total Value'], marker='o')
    plt.title('Asset Trend')
    plt.xlabel('Date')
    plt.ylabel('Total Value')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    # 将图像转换为base64编码
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    graphic = base64.b64encode(image_png)
    graphic = graphic.decode('utf-8')

    plt.close()

    # 返回包含图像的HTML
    html_content = f"""
    <html>
        <head>
            <title>Asset Trend</title>
        </head>
        <body>
            <h1>Asset Trend Visualization</h1>
            <img src="data:image/png;base64,{graphic}" alt="Asset Trend Plot"/>
            <p>Start Date: {start_date}</p>
            <p>End Date: {end_date}</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


# 前端页面路由
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login_post(
        request: Request,
        username: str = Form(...),
        password: str = Form(...)
):
    user = UserManager.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "用户名或密码错误"
        })

    # 这里应该设置会话或cookie，但为了简化，我们直接跳转到主页
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": user
    })


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register", response_class=HTMLResponse)
def register_post(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        confirm_password: str = Form(...)
):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "两次输入的密码不一致"
        })

    try:
        user = UserManager.create_user(username, email, password)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "message": "注册成功，请登录"
        })
    except Exception as e:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": str(e)
        })


@app.get("/assets", response_class=HTMLResponse)
def assets_page(request: Request, current_user: User = Depends(get_current_user)):
    assets = AssetManager.list_assets()
    return templates.TemplateResponse("assets.html", {
        "request": request,
        "assets": assets,
        "current_user": current_user
    })


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, current_user: User = Depends(get_current_user)):
    assets = AssetManager.list_assets()
    return templates.TemplateResponse("history.html", {
        "request": request,
        "assets": assets,
        "current_user": current_user
    })


@app.get("/trend", response_class=HTMLResponse)
def trend_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("trend.html", {
        "request": request,
        "current_user": current_user
    })


if __name__ == "__main__":
    import uvicorn

    # 初始化数据库
    initialize_db()

    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000)
