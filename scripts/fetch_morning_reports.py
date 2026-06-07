#!/usr/bin/env python3
"""
期货研报自动抓取脚本
运行时间：每个交易日 08:30 (GitHub Actions定时触发)
输出：data/reports.json

依赖：pip install akshare
"""

import json
import os
import re
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# 研报关键词库（用于自动标星）
STAR_KEYWORDS = {
    5: ['强烈推荐','强烈看多','强烈看空','供需逆转','库存新低','库存极低',
        '需求爆发','供给骤降','重大利多','重大利空','突破关键','历史低位','历史高位'],
    4: ['偏强','偏弱','看多','看空','去库','累库','减产','增产',
        'OPEC','非农','CPI','美联储','USDA','MPOB','开工率','地缘'],
    3: ['关注','震荡','波动','短期','中长期','预期','可能','或将'],
}

# 品种关键词映射（从标题/摘要提取关联品种）
PRODUCT_KEYWORDS = {
    'CU': ['铜','沪铜','铜价','精铜','铜矿'],
    'AL': ['铝','沪铝','电解铝','铝锭'],
    'ZN': ['锌','沪锌','精锌'],
    'NI': ['镍','沪镍','镍矿','不锈钢'],
    'SN': ['锡','沪锡','精锡'],
    'AU': ['黄金','金价','沪金','COMEX金'],
    'AG': ['白银','银价','沪银','COMEX银','光伏用银'],
    'RB': ['螺纹钢','螺纹','钢材','钢铁'],
    'HC': ['热卷','热轧','卷板'],
    'I': ['铁矿石','铁矿','矿山'],
    'JM': ['焦煤','炼焦煤','煤炭'],
    'J': ['焦炭','冶金焦'],
    'SA': ['纯碱','重碱','轻碱'],
    'FG': ['玻璃','浮法玻璃','平板玻璃'],
    'SC': ['原油','油价','INE原油','OPEC','EIA','API'],
    'FU': ['燃油','燃料油'],
    'BU': ['沥青','石油沥青'],
    'TA': ['PTA','聚酯','涤纶'],
    'MA': ['甲醇','MTO'],
    'M': ['豆粕','豆粉','饲料','USDA','压榨'],
    'Y': ['豆油','大豆油','油脂'],
    'P': ['棕榈油','棕榈','MPOB','B40'],
    'RM': ['菜粕','菜籽粕','水产'],
    'OI': ['菜油','菜籽油'],
    'CF': ['棉花','棉价','棉纺'],
    'SR': ['白糖','食糖','甘蔗'],
    'C': ['玉米','饲用玉米'],
    'LH': ['生猪','猪肉','猪周期','存栏','出栏'],
    'IF': ['沪深300','股指','A股','大盘'],
    'T': ['国债','利率','央行','MLF','LPR','降息'],
}


def score_report(title, summary):
    """根据关键词自动评分"""
    text = (title + ' ' + summary).lower()
    score = 2
    for s in [5, 4, 3]:
        for kw in STAR_KEYWORDS[s]:
            if kw.lower() in text:
                return s
    return score


def match_products(title, summary):
    """匹配研报涉及的品种"""
    text = title + ' ' + summary
    matched = []
    for code, keywords in PRODUCT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.append(code)
                break
    return matched


def fetch_reports_em():
    """从东方财富研报中心抓取（网页解析方式）"""
    reports = []
    try:
        import requests
        from bs4 import BeautifulSoup

        # 东方财富期货研报页面
        urls = [
            'https://data.eastmoney.com/report/industry/futures.html',
        ]
        for url in urls:
            try:
                resp = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }, timeout=15)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    # 提取研报列表（选择器可能需根据实际页面调整）
                    items = soup.select('.report-item, .report_list li, .list_item')
                    for item in items[:30]:
                        title_el = item.select_one('.title, h3, a')
                        source_el = item.select_one('.source, .author, .org')
                        date_el = item.select_one('.date, .time')
                        if title_el:
                            title = title_el.get_text(strip=True)
                            source = source_el.get_text(strip=True) if source_el else '东方财富'
                            date = date_el.get_text(strip=True) if date_el else datetime.now().strftime('%Y-%m-%d')
                            summary = item.get_text(strip=True)[:200]
                            url_link = title_el.get('href', '') if title_el.name == 'a' else ''

                            products = match_products(title, summary)
                            sector = 'macro'  # default
                            # 简化板块判断
                            for p in products:
                                if p in ['RB','HC','I','JM','J','SF','SM']: sector = 'black'
                                elif p in ['CU','AL','ZN','PB','NI','SN','AO']: sector = 'nonferrous'
                                elif p in ['AU','AG']: sector = 'precious'
                                elif p in ['SC','FU','BU','TA','MA','SA','FG','V','PP','L','EG','EB','UR']: sector = 'chemical'
                                elif p in ['M','Y','P','RM','OI','CF','SR','C','LH']: sector = 'agri'
                                elif p in ['IF','IC','IH','IM','TS','TF','T','TL']: sector = 'financial'
                                break

                            reports.append({
                                'title': title,
                                'source': source,
                                'date': date,
                                'products': products,
                                'sector': sector,
                                'stars': score_report(title, summary),
                                'summary': summary[:300],
                                'keywords': [kw for kw_list in STAR_KEYWORDS.values() for kw in kw_list if kw in (title + summary)],
                                'url': url_link or '#',
                            })
            except Exception as e:
                print(f"  ⚠ URL {url} 抓取失败: {e}")

    except ImportError:
        print("  ⚠ requests/bs4未安装: pip install requests beautifulsoup4")
    except Exception as e:
        print(f"  ⚠ 研报抓取失败: {e}")

    return reports


def main():
    print(f"📄 期货研报抓取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    os.makedirs(DATA_DIR, exist_ok=True)

    # 抓取研报
    reports = fetch_reports_em()

    if reports:
        # 按星级排序
        reports.sort(key=lambda r: (r['stars'], r['date']), reverse=True)

        output = {
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total': len(reports),
            'reports': reports,
        }

        with open(os.path.join(DATA_DIR, 'reports.json'), 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 研报已保存 ({len(reports)} 篇)")
        # 打印标星分布
        stars5 = sum(1 for r in reports if r['stars'] >= 5)
        stars4 = sum(1 for r in reports if r['stars'] == 4)
        print(f"  ⭐⭐⭐⭐⭐ 强烈关注: {stars5} 篇")
        print(f"  ⭐⭐⭐⭐ 值得关注: {stars4} 篇")
    else:
        print("  ⚠ 未获取到研报数据（非交易日前夜或网络异常）")

    print(f"\n✅ 完成: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
