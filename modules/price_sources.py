"""
站点解析器（分站点维护，避免后期改动混乱）

提供每个站点的价格解析函数：传入 BeautifulSoup 对象与原始 HTML，返回 float 价格，失败返回 0.0。
"""

import re
from bs4 import BeautifulSoup  # 仅用于类型注释/补全，调用方已传 soup


def parse_dd373(soup: BeautifulSoup, html: str) -> float:
    """解析 DD373 的第二条商品价格。

    说明：该站常见 JS 挑战页，若返回挑战页将无法命中选择器，直接返回 0.0。
    """
    try:
        el = soup.select_one('div.good-list-box div:nth-child(2) div.p-r66 p.font12.color666.m-t5')
        if not el:
            return 0.0
        text = el.get_text(strip=True)
        m = re.search(r'(\d+(?:\.\d+)?)', text)
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0


def parse_7881(soup: BeautifulSoup, html: str) -> float:
    """解析 7881 的第二条商品单价（元/个）。

    结构示例：
    <div class="price-unit">
      <p><em>1</em>元=<em>1.587</em>个</p>
      <p><em>0.6300</em>元/个</p>
    </div>
    """
    try:
        el = (
            soup.select_one('div.list-box > div:nth-of-type(2) div.price-unit p:nth-of-type(2) em')
            or soup.select_one('div.price-unit p:nth-of-type(2) em')
            or soup.select_one('div.list-box div.price-unit p:nth-of-type(2) em')
        )
        if el:
            text = el.get_text(strip=True)
            m = re.search(r'(\d+(?:\.\d+)?)', text)
            if m:
                return float(m.group(1))
        # 回退：直接在页面文本中找 “x.xx元/个”
        m2 = re.search(r'(\d+(?:\.\d+)?)\s*元/个', html)
        return float(m2.group(1)) if m2 else 0.0
    except Exception:
        return 0.0


def parse_uu898(soup: BeautifulSoup, html: str) -> float:
    """解析 UU898 的首条商品单价（元/个）。

    策略：
    - 首选首条商品块 li.sp_li1 h6 的文本，用正则提取 “x.xx元/个”
    - 失败则在整页回退正则提取（避免命中 “1元=…” 结构）
    """
    try:
        blk = soup.select_one('li.sp_li1 h6')
        text_src = ' '.join(blk.stripped_strings) if blk else ''
        m = re.search(r'(\d+(?:\.\d+)?)\s*元/个', text_src)
        if not m:
            m = re.search(r'(\d+(?:\.\d+)?)\s*元/个', html)
        return float(m.group(1)) if m else 0.0
    except Exception:
        return 0.0

