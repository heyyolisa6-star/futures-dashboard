#!/usr/bin/env python3
"""
期货研报自动抓取脚本 v2
数据源：AKShare 研报接口（可访问国内数据API）
运行时间：每个交易日 08:30 (GitHub Actions)

依赖：pip install akshare
"""

import json
import os
import sys
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

STAR_KEYWORDS = {
    5: ['强烈推荐','强烈看多','强烈看空','供需逆转','库存新低','库存极低',
        '需求爆发','供给骤降','重大利多','重大利空','突破关键','历史低位','历史高位'],
    4: ['偏强','偏弱','看多','看空','去库','累库','减产','增产',
        'OPEC','非农','CPI','美联储','USDA','MPOB','开工率','地缘','央行'],
    3: ['关注','震荡','波动','短期','中长期','预期','可能','或将'],
}

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
    'LC': ['碳酸锂','锂价','锂电池','新能源车','正极材料'],
    'SI': ['工业硅','金属硅','硅价','有机硅'],
    'PS': ['多晶硅','硅料','光伏'],
    'PT': ['铂','铂金','铂族'],
    'PD': ['钯','钯金','铂族'],
}


def score_report(title, summary):
    text = (title + ' ' + summary).lower()
    for s in [5, 4, 3]:
        for kw in STAR_KEYWORDS[s]:
            if kw.lower() in text:
                return s
    return 2


def match_products(title, summary):
    text = title + ' ' + summary
    matched = []
    for code, keywords in PRODUCT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.append(code)
                break
    return matched


def determine_sector(products):
    for p in products:
        if p in ['RB','HC','I','JM','J','SF','SM']: return 'black'
        if p in ['CU','AL','ZN','PB','NI','SN','AO']: return 'nonferrous'
        if p in ['AU','AG','PT','PD']: return 'precious'
        if p in ['SC','FU','BU','TA','MA','SA','FG','V','PP','L','EG','EB','UR','SI','LC','PS']: return 'chemical'
        if p in ['M','Y','P','RM','OI','CF','SR','C','CS','JD','LH','PK']: return 'agri'
        if p in ['IF','IC','IH','IM','TS','TF','T','TL']: return 'financial'
    return 'macro'


def fetch_via_akshare():
    """使用 AKShare 原生接口获取研报"""
    reports = []
    try:
        import akshare as ak

        # 尝试 AKShare 的研报接口
        # stock_research_report_em 获取东方财富个股研报
        try:
            df = ak.stock_research_report_em(symbol="", date="")
            if df is not None and not df.empty:
                for _, row in df.head(50).iterrows():
                    title = str(row.get('research_report_title', row.get('title', '')))
                    summary = str(row.get('research_report_summary', row.get('summary', '')))[:300]
                    org = str(row.get('org_name', row.get('source', row.get('research_report_org', '未知'))))
                    date_str = str(row.get('date', row.get('create_date', '')))[:10]

                    if not title or len(title) < 5:
                        continue

                    products = match_products(title, summary)
                    sector = determine_sector(products)

                    reports.append({
                        'title': title,
                        'source': org,
                        'date': date_str or datetime.now().strftime('%Y-%m-%d'),
                        'products': products,
                        'sector': sector,
                        'stars': score_report(title, summary),
                        'summary': summary[:300] if summary else title,
                        'keywords': [kw for kw_list in STAR_KEYWORDS.values() for kw in kw_list if kw in (title + summary)],
                        'url': f'https://search.eastmoney.com/search?m=0&t=4&k={title[:30]}',
                    })
                print(f"  ✅ AKShare stock_research_report_em: {len(reports)} 篇")
        except Exception as e:
            print(f"  ⚠ stock_research_report_em 失败: {e}")

        # 备选：尝试期货特定研报接口
        if len(reports) < 5:
            try:
                # 尝试获取期货相关的研报列表
                df2 = ak.stock_research_report_em(symbol="期货")
                if df2 is not None and not df2.empty:
                    for _, row in df2.head(30).iterrows():
                        title = str(row.get('research_report_title', ''))
                        summary = str(row.get('research_report_summary', ''))[:300]
                        if not title or len(title) < 5:
                            continue
                        products = match_products(title, summary)
                        sector = determine_sector(products)
                        reports.append({
                            'title': title,
                            'source': str(row.get('org_name', '未知')),
                            'date': str(row.get('date', ''))[:10] or datetime.now().strftime('%Y-%m-%d'),
                            'products': products, 'sector': sector,
                            'stars': score_report(title, summary),
                            'summary': summary[:300] if summary else title,
                            'keywords': [kw for kw_list in STAR_KEYWORDS.values() for kw in kw_list if kw in (title + summary)],
                            'url': f'https://search.eastmoney.com/search?m=0&t=4&k={title[:30]}',
                        })
            except Exception as e:
                print(f"  ⚠ 备选接口也失败: {e}")

    except ImportError:
        print("  ❌ akshare 未安装")
    except Exception as e:
        print(f"  ⚠ AKShare 抓取异常: {e}")

    return reports


def main():
    print(f"📄 期货研报抓取 v2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    os.makedirs(DATA_DIR, exist_ok=True)

    # 抓取研报
    reports = fetch_via_akshare()

    # 去重 + 排序
    seen = set()
    unique = []
    for r in reports:
        key = r['title'][:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda r: (r['stars'], r['date']), reverse=True)

    print(f"\n  共获取 {len(unique)} 篇研报（去重后）")
    if unique:
        stars5 = sum(1 for r in unique if r['stars'] >= 5)
        stars4 = sum(1 for r in unique if r['stars'] == 4)
        print(f"  ⭐⭐⭐⭐⭐ 强烈关注: {stars5} 篇")
        print(f"  ⭐⭐⭐⭐ 值得关注: {stars4} 篇")

    # 始终生成 JSON（即使为空）
    output = {
        'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'total': len(unique),
        'reports': unique,
    }

    out_path = os.path.join(DATA_DIR, 'reports.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 已保存到 {out_path}")
    print(f"✅ 完成: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
