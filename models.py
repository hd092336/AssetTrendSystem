# -*- coding:utf-8 -*-
import datetime
import hashlib
import secrets

from peewee import SqliteDatabase, Model, CharField, DateTimeField, BooleanField, AutoField, ForeignKeyField, \
    DecimalField

# 使用SQLite示例（可替换为MySQL/PostgreSQL）
db = SqliteDatabase('asset_trend.db')


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    """用户表"""
    id = AutoField(primary_key=True, index=True)
    username = CharField(max_length=50, unique=True)
    email = CharField(max_length=100, unique=True)
    hashed_password = CharField(max_length=128)
    salt = CharField(max_length=32)
    created_at = DateTimeField(default=datetime.datetime.now)
    is_active = BooleanField(default=True)

    def verify_password(self, plain_password):
        return self.hashed_password == self.hash_password(plain_password, self.salt)

    @staticmethod
    def hash_password(password, salt=None):
        if salt is None:
            salt = secrets.token_hex(16)
        # 使用SHA-256哈希算法
        hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
        return hashed

    @classmethod
    def create_user(cls, username, email, password):
        salt = secrets.token_hex(16)
        hashed_password = cls.hash_password(password, salt)
        return cls.create(
            username=username,
            email=email,
            hashed_password=hashed_password,
            salt=salt
        )


class Asset(BaseModel):
    """资产表"""
    id = AutoField(primary_key=True, index=True)
    name = CharField(max_length=50, unique=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    is_deleted = BooleanField(default=False)

    @classmethod
    def create_asset(cls, name):
        return cls.get_or_create(name=name)

    def soft_delete(self):
        self.is_deleted = True
        self.save()


class AssetHistory(BaseModel):
    """资产历史记录表"""
    id = AutoField(primary_key=True, index=True)
    asset = ForeignKeyField(Asset, backref='history')
    value = DecimalField(max_digits=18, decimal_places=2)
    timestamp = DateTimeField(index=True)

    class Meta:
        indexes = (
            (('asset', 'timestamp'), True),  # 复合唯一索引
        )

    @classmethod
    def add_record(cls, asset_id, value, timestamp=None):
        return cls.create(
            asset=asset_id,
            value=value,
            timestamp=timestamp or datetime.datetime.now()
        )


# 创建表
def initialize_db():
    db.connect()
    db.create_tables([User, Asset, AssetHistory], safe=True)
    db.close()
