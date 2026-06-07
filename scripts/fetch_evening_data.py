#!/usr/bin/env python3
"""
期货盘后数据抓取脚本
抓取内容：仓单日报、库存数据、持仓排名
输出格式：JSON文件，供前端面板加载
运行时间：每个交易日 18:00 (GitHub Actions定时触发)

依赖安装：pip install akshare
"""

import json
import os
import sys
from datetime import datetime, timedelta

# ====================== 配置 ======================
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
TRADE_DATE = None  # None = 自动获取最近交易日

# 需要抓取的品种及代码（与前端PRODUCTS配置对应）
PRODUCT_CODES = [
    # 上期所 SHFE
    'CU','AL','ZN','PB','NI','SN','AO','AU','AG',
    'RB','HC','FU','BU','RU','NR','SP',
    # 大商所 DCE
    'I','JM','J','M','Y','P','C','CS','JD','LH','EG','EB','PP','L','V','PG',
    # 郑商所 CZCE
    'TA','MA','SA','FG','UR','CF','SR','RM','OI','PK','SM','SF','AP','CJ',
    # 能源中心 INE
    'SC','LU','BC',
    # 中金所 CFFEX (持仓排名)
    'IF','IC','IH','IM','TS','TF','T','TL',
]

def get_trade_date():
    """获取最近交易日"""
    if TRADE_DATE:
        return TRADE_DATE
    today = datetime.now()
    # 简单判断：周末回退到周五
    if today.weekday() == 5:  # 周六
        today = today - timedelta(days=1)
    elif today.weekday() == 6:  # 周日
        today = today - timedelta(days=2)
    return today.strftime('%Y%m%d')


def fetch_warehouse_receipts():
    """抓取仓单数据"""
    print("📦 抓取仓单数据...")
    try:
        import akshare as ak
        date_str = get_trade_date()
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # 使用AKShare统一仓单接口
        df = ak.get_receipt(
            start_date=date_fmt,
            end_date=date_fmt,
            vars_list=PRODUCT_CODES
        )

        if df is None or df.empty:
            print("  ⚠ 仓单数据为空，使用缓存")
            return None

        # 转换为前端格式
        results = []
        grouped = df.groupby('var') if 'var' in df.columns else None

        if grouped:
            for code, group in grouped:
                latest = group.iloc[-1] if len(group) > 0 else None
                if latest is not None:
                    receipt = int(latest.get('receipt', 0) or 0)
                    change = int(latest.get('receipt_chg', 0) or 0)
                    results.append({
                        'code': code,
                        'receipt': receipt,
                        'change': change,
                        'changePct': round(change / receipt * 100, 2) if receipt > 0 else 0,
                    })
        else:
            # 如果groupby失败，尝试按行处理
            for _, row in df.iterrows():
                code = row.get('var', '') or row.get('品种', '')
                receipt = int(row.get('receipt', 0) or row.get('仓单量', 0) or 0)
                change = int(row.get('receipt_chg', 0) or row.get('变化量', 0) or 0)
                if code and receipt > 0:
                    results.append({
                        'code': code,
                        'receipt': receipt,
                        'change': change,
                        'changePct': round(change / receipt * 100, 2) if receipt > 0 else 0,
                    })

        output = {
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tradeDate': date_fmt,
            'source': '上海期货交易所/大连商品交易所/郑州商品交易所/广州期货交易所',
            'data': results,
        }

        with open(os.path.join(DATA_DIR, 'warehouse_receipt.json'), 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 仓单数据已保存 ({len(results)} 个品种)")
        return output

    except ImportError:
        print("  ❌ akshare未安装，请运行: pip install akshare")
        return None
    except Exception as e:
        print(f"  ⚠ 仓单抓取失败: {e}")
        return None


def fetch_position_ranking():
    """抓取持仓排名数据"""
    print("📊 抓取持仓排名...")
    try:
        import akshare as ak
        date_str = get_trade_date()
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # 使用AKShare统一持仓排名接口
        df = ak.get_rank_sum(
            date=date_str,
            vars_list=[c for c in PRODUCT_CODES if c not in ('IF','IC','IH','IM','TS','TF','T','TL')]
        )

        if df is None or df.empty:
            print("  ⚠ 持仓排名数据为空")
            return None

        results = []
        grouped = df.groupby('var') if 'var' in df.columns else None

        if grouped:
            for code, group in grouped:
                try:
                    long_vol = int(group.get('long_vol', group.iloc[0].get('vol', 0)) or 0)
                    short_vol = int(group.get('short_vol', 0) or 0)
                    long_chg = int(group.get('long_chg', 0) or 0)
                    short_chg = int(group.get('short_chg', 0) or 0)
                    results.append({
                        'code': code,
                        'longVolume': long_vol,
                        'shortVolume': short_vol,
                        'netPosition': long_vol - short_vol,
                        'longChange': long_chg,
                        'shortChange': short_chg,
                    })
                except Exception:
                    pass

        output = {
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tradeDate': date_fmt,
            'source': '四大期货交易所前20会员持仓排名',
            'data': results,
        }

        with open(os.path.join(DATA_DIR, 'position_ranking.json'), 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 持仓排名已保存 ({len(results)} 个品种)")
        return output

    except ImportError:
        print("  ❌ akshare未安装")
        return None
    except Exception as e:
        print(f"  ⚠ 持仓排名抓取失败: {e}")
        return None


def fetch_inventory_data():
    """抓取交易所库存数据（上期所每周库存报告等）"""
    print("📋 抓取库存数据...")
    try:
        import akshare as ak
        date_str = get_trade_date()
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # 上期所库存周报
        results = []
        try:
            df_shfe = ak.futures_shfe_warehouse_receipt(date=date_fmt)
            if df_shfe is not None and not df_shfe.empty:
                for _, row in df_shfe.iterrows():
                    results.append({
                        'code': str(row.get('品种代码', row.get('var', ''))),
                        'name': str(row.get('品种名称', '')),
                        'receipt': int(row.get('仓单数量', row.get('receipt', 0)) or 0),
                        'change': int(row.get('增减', row.get('receipt_chg', 0)) or 0),
                        'exchange': 'SHFE',
                    })
        except Exception:
            pass

        if results:
            output = {
                'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tradeDate': date_fmt,
                'source': '上海期货交易所库存周报',
                'data': results,
            }
            with open(os.path.join(DATA_DIR, 'inventory.json'), 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 库存数据已保存 ({len(results)} 条)")

        return results

    except Exception as e:
        print(f"  ⚠ 库存抓取失败: {e}")
        return None


def main():
    print(f"🚀 期货盘后数据抓取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 交易日期: {get_trade_date()}")
    print("-" * 50)

    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. 仓单数据
    receipt_result = fetch_warehouse_receipts()

    # 2. 持仓排名
    position_result = fetch_position_ranking()

    # 3. 库存数据
    inventory_result = fetch_inventory_data()

    print("-" * 50)
    success = sum(1 for r in [receipt_result, position_result] if r is not None)
    print(f"✅ 完成: {success}/3 项数据抓取成功")

    if success < 3:
        print("💡 提示: 非交易日或网络异常可能导致部分数据为空，前端将使用缓存数据")


if __name__ == '__main__':
    main()
