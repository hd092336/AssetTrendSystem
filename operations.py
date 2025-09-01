# -*- coding:utf-8 -*-
from models import *
import matplotlib.pyplot as plt
import pandas as pd


class AssetManager:
    """资产CRUD操作"""

    @staticmethod
    def list_assets(include_deleted=False):
        query = Asset.select()
        if not include_deleted:
            query = query.where(Asset.is_deleted == False)
        return list(query)

    @staticmethod
    def update_asset(asset_id, new_name):
        query = Asset.update(name=new_name).where(Asset.id == asset_id)
        return query.execute()


class TrendCalculator:
    """趋势计算引擎"""

    @staticmethod
    def get_asset_trend(asset_ids, start_date, end_date):
        """
        获取资产组合的趋势数据
        返回: {timestamp: total_value} 字典
        """
        # 获取时间范围内所有记录点
        timestamps = (
            AssetHistory.select(AssetHistory.timestamp)
            .where(
                (AssetHistory.timestamp.between(start_date, end_date)) &
                (AssetHistory.asset.in_(asset_ids))
            )
            .group_by(AssetHistory.timestamp)
            .order_by(AssetHistory.timestamp)
        )

        # 计算每个时间点的总价值
        trend_data = {}
        for ts in timestamps:
            total = 0
            for asset_id in asset_ids:
                latest = (
                    AssetHistory.select()
                    .where(
                        (AssetHistory.asset == asset_id) &
                        (AssetHistory.timestamp <= ts.timestamp)
                    )
                    .order_by(AssetHistory.timestamp.desc())
                    .first()
                )
                if latest:
                    total += float(latest.value)
            trend_data[ts.timestamp] = round(total, 2)

        return trend_data

    @staticmethod
    def plot_trend(trend_data, title="Asset Trend"):
        """使用Matplotlib绘制趋势图"""
        df = pd.DataFrame.from_dict(
            trend_data,
            orient='index',
            columns=['Total Value']
        )
        df.plot(figsize=(10, 5))
        plt.title(title)
        plt.ylabel("Value")
        plt.grid(True)
        plt.show()