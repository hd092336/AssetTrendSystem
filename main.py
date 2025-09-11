# -*- coding:utf-8 -*-
"""
"""
import base64
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import List

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Request, Form, Response
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from peewee import DoesNotExist

from models import Asset, AssetHistory, User, db, initialize_db
from operations import TrendCalculator, AssetManager, UserManager
from schemas import AssetHistoryCreate, AssetCreate, Asset as AssetResp, AssetHistory as AssetHistoryResp, UserCreate

# 设置matplotlib后端以避免线程问题
matplotlib.use('Agg')

app = FastAPI(title="Asset Trend System", description="API for managing assets and viewing trends", version="1.0.0")

# 配置模板
templates = Jinja2Templates(directory="templates")

# HTTP Basic Auth
security = HTTPBasic()

# Session配置
SESSION_KEY = "session_token"
SESSIONS = {}  # 简单的内存session存储，实际应用中应使用Redis等
SESSION_TIMEOUT = timedelta(minutes=30)  # 30分钟无操作自动退出

# 定义北京时间时区
BEIJING_TZ = timezone(timedelta(hours=8))


class SessionData:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.last_activity = datetime.now(BEIJING_TZ)
    
    def is_valid(self):
        return datetime.now(BEIJING_TZ) - self.last_activity < SESSION_TIMEOUT
    
    def update_activity(self):
        self.last_activity = datetime.now(BEIJING_TZ)


def get_db():
    try:
        yield db
    finally:
        db.close()


def get_current_user_from_session(request: Request):
    """从session中获取当前用户"""
    session_token = request.cookies.get(SESSION_KEY)
    if not session_token or session_token not in SESSIONS:
        return None
    
    session_data = SESSIONS[session_token]
    if not session_data.is_valid():
        # Session过期，删除它
        del SESSIONS[session_token]
        return None
    
    # 更新活动时间
    session_data.update_activity()
    return session_data


def get_current_user(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    """获取当前用户 - 支持session和HTTP Basic认证"""
    # 首先检查session
    session_user = get_current_user_from_session(request)
    if session_user:
        try:
            return User.get(User.id == session_user.user_id)
        except User.DoesNotExist:
            pass
    
    # 如果没有有效session，尝试HTTP Basic认证
    if credentials:
        user = UserManager.authenticate_user(credentials.username, credentials.password)
        if user:
            return user
    
    # 认证失败
    raise HTTPException(status_code=401, detail="无效的用户名或密码")


def create_session_response(response: Response, user: User):
    """创建带有session cookie的响应"""
    # 生成session token
    session_token = secrets.token_urlsafe(32)
    
    # 存储session数据
    SESSIONS[session_token] = SessionData(user.id, user.username)
    
    # 设置cookie，转换为UTC时间以满足usegmt=True的要求
    beijing_time = datetime.now(BEIJING_TZ) + SESSION_TIMEOUT
    utc_time = beijing_time.astimezone(timezone.utc)
    
    response.set_cookie(
        key=SESSION_KEY,
        value=session_token,
        httponly=True,
        max_age=int(SESSION_TIMEOUT.total_seconds()),
        expires=utc_time
    )
    
    return response


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
    session_user = get_current_user_from_session(request)
    context = {"request": request}
    if session_user:
        context["current_user"] = {"username": session_user.username}
    return templates.TemplateResponse("index.html", context)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    session_user = get_current_user_from_session(request)
    if session_user:
        # 如果已经登录，重定向到主页
        return templates.TemplateResponse("index.html", {
            "request": request,
            "current_user": {"username": session_user.username}
        })
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login_post(
        request: Request,
        response: Response,
        username: str = Form(...),
        password: str = Form(...)
):
    user = UserManager.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "用户名或密码错误"
        })

    # 创建session并设置cookie
    resp = templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": user
    })
    create_session_response(resp, user)
    return resp


@app.get("/logout", response_class=HTMLResponse)
def logout(request: Request, response: Response):
    session_token = request.cookies.get(SESSION_KEY)
    if session_token and session_token in SESSIONS:
        del SESSIONS[session_token]
    
    response = templates.TemplateResponse("index.html", {"request": request})
    response.delete_cookie(SESSION_KEY)
    return response


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
def assets_page(request: Request):
    session_user = get_current_user_from_session(request)
    if not session_user:
        # 未登录重定向到登录页
        return templates.TemplateResponse("login.html", {"request": request})
    
    try:
        user = User.get(User.id == session_user.user_id)
        assets = AssetManager.list_assets()
        return templates.TemplateResponse("assets.html", {
            "request": request,
            "assets": assets,
            "current_user": user
        })
    except User.DoesNotExist:
        return templates.TemplateResponse("login.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    session_user = get_current_user_from_session(request)
    if not session_user:
        # 未登录重定向到登录页
        return templates.TemplateResponse("login.html", {"request": request})
    
    try:
        user = User.get(User.id == session_user.user_id)
        assets = AssetManager.list_assets()
        return templates.TemplateResponse("history.html", {
            "request": request,
            "assets": assets,
            "current_user": user
        })
    except User.DoesNotExist:
        return templates.TemplateResponse("login.html", {"request": request})


@app.get("/trend", response_class=HTMLResponse)
def trend_page(request: Request):
    session_user = get_current_user_from_session(request)
    if not session_user:
        # 未登录重定向到登录页
        return templates.TemplateResponse("login.html", {"request": request})
    
    try:
        user = User.get(User.id == session_user.user_id)
        return templates.TemplateResponse("trend.html", {
            "request": request,
            "current_user": user
        })
    except User.DoesNotExist:
        return templates.TemplateResponse("login.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    # 初始化数据库
    initialize_db()

    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000)
