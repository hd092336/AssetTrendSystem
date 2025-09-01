# -*- coding:utf-8 -*-
from peewee import SqliteDatabase, Model, CharField, DateTimeField, BooleanField, AutoField, ForeignKeyField, \
    DecimalField
import datetime

# 使用SQLite示例（可替换为MySQL/PostgreSQL）
db = SqliteDatabase('asset_trend.db')


class BaseModel(Model):
    class Meta:
        database = db


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
    db.create_tables([Asset, AssetHistory], safe=True)
    db.close()
