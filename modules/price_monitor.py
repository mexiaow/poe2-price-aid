"""
价格监控模块
实现价格爬取和显示功能
"""

import re
import requests
import time
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QGridLayout, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from modules.config import Config


# 调试开关：
# - 推荐：在运行时添加参数 --debug-price 或 --debug 开启价格抓取调试输出（默认关闭）
# - 兼容：也支持环境变量 POE2_DEBUG_PRICE=1 或 POE2_DEBUG=1 开启
def _env_truth(v: str) -> bool:
    return str(v).lower() in ("1", "true", "yes", "on")

def _cli_flag_present(*flags: str) -> bool:
    try:
        return any(flag in sys.argv for flag in flags)
    except Exception:
        return False

# 优先使用命令行参数开关；若未提供则回退到环境变量
DEBUG_PRICE = _cli_flag_present("--debug-price", "--debug") or _env_truth(os.getenv("POE2_DEBUG_PRICE", os.getenv("POE2_DEBUG", "0")))

def _dlog(msg: str):
    if DEBUG_PRICE:
        try:
            print(f"[price_debug] {msg}")
        except Exception:
            pass


class PriceScraper(QThread):
    """价格爬取线程类"""
    price_updated = pyqtSignal(str, float)
    
    def __init__(self):
        super().__init__()
        self.urls = {
            "divine": "https://www.dd373.com/s-bcntax-c-n80v8p-h32hgr-5g0bqf.html",
            "exalted": "https://www.dd373.com/s-bcntax-c-bkfnrd-h32hgr-5g0bqf.html",
            "chaos": "https://www.dd373.com/s-bcntax-c-mxgtdd-h32hgr-5g0bqf.html",
            "chance": "https://www.dd373.com/s-bcntax-c-apww35-h32hgr-5g0bqf.html"
        }
        
    def run(self):
        """并发抓取价格（最多4并发），并加入轻微错峰延迟"""
        try:
            _dlog("start price refresh with 4 workers (0/50/100/150ms stagger)")
            # 受控并发为4；为每个请求增加微小错峰（0/50/100/150ms），降低瞬时并发尖峰
            items = list(self.urls.items())
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                for i, (currency, url) in enumerate(items):
                    delay_ms = i * 50  # 每个请求递增 50ms 的轻微延迟
                    # 注意：不共享 Session 到多线程，避免线程安全问题；每个任务各自请求
                    futures[executor.submit(self._get_price_with_delay, url, delay_ms)] = currency
                for future in as_completed(futures):
                    currency = futures.get(future)
                    try:
                        price = future.result()
                    except Exception:
                        continue
                    if price > 0:
                        self.price_updated.emit(currency, price)
                        _dlog(f"parsed {currency} => {price}")
                    # 轻微让步，避免过于频繁地触发UI更新
                    self.msleep(10)
        except Exception:
            pass

    def _get_price_with_delay(self, url, delay_ms=0):
        """在请求前增加轻微延迟以错峰，单位毫秒；每个任务独立请求，避免共享会话"""
        try:
            if delay_ms and delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        except Exception:
            pass
        # 使用 requests.get（每次调用内部自建会话），是线程安全的
        return self.get_price(url)
    
    def get_price(self, url, session=None):
        """使用单一解析路径：获取第二个商品的价格；失败直接返回 0.000"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': 'https://www.dd373.com/'
            }
            client = session or requests
            response = client.get(url, headers=headers, timeout=8)
            # 纠正编码，避免解析失败
            try:
                enc = (response.encoding or '').lower()
                if not enc or enc == 'iso-8859-1':
                    response.encoding = getattr(response, 'apparent_encoding', None) or 'utf-8'
            except Exception:
                pass
            _dlog(f"GET {url} status={getattr(response, 'status_code', 'NA')} len={len(getattr(response, 'text', '') or '')} enc={getattr(response, 'encoding', 'NA')}")
            soup = BeautifulSoup(response.text, 'html.parser')

            # 单一路径：第二个商品价格位置
            price_element = soup.select_one('div.good-list-box div:nth-child(2) div.p-r66 p.font12.color666.m-t5')
            if not price_element:
                # 直接失败
                preview = (response.text or '')[:200].replace('\n', ' ')
                _dlog(f"no match; preview='{preview}' -> return 0.000")
                return 0.0

            price_text = price_element.get_text(strip=True)
            _dlog(f"matched text='{price_text[:80]}'")
            m = re.search(r'(\d+(?:\.\d+)?)', price_text)
            if not m:
                _dlog("no number in matched text -> return 0.000")
                return 0.0
            return float(m.group(1))
        except Exception as e:
            _dlog(f"exception for {url}: {e}; return 0.000")
            return 0.0


class PriceMonitorTab(QWidget):
    """价格监控标签页类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化属性
        self.prices = Config.DEFAULT_PRICES.copy()  # 使用默认价格
        self.currency_colors = Config.CURRENCY_COLORS
        self.currency_names = Config.CURRENCY_NAMES
        self.start_time = datetime.now()
        self.countdown_seconds = 600  # 10分钟刷新一次
        
        # 初始化UI
        self.init_ui()
        
        # 启动价格刷新定时器
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown_display)
        self.countdown_timer.start(1000)  # 每秒更新一次倒计时
        
        # 启动价格刷新
        self.refresh_prices()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 减少边距以腾出更多空间
        
        # 创建滚动区域，确保在窗口大小变化时内容可滚动
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 允许内容调整大小
        scroll_area.setFrameShape(QScrollArea.NoFrame)  # 移除边框
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # 价格监控网格布局
        price_grid = QGridLayout()
        price_grid.setSpacing(8)  # 减少网格间距从15到8
        
        # 设置列伸缩因子，合理分配空间
        price_grid.setColumnStretch(0, 1)  # 货币名称列
        price_grid.setColumnStretch(1, 1)  # 价格列 - 减少权重
        price_grid.setColumnStretch(2, 0)  # 输入框列 - 固定宽度，不拉伸
        price_grid.setColumnStretch(3, 1)  # 价值列
        price_grid.setColumnStretch(4, 3)  # 兑换比例列 - 获得更多空间
        
        # 神圣石行 - 第1行
        divine_label = QLabel("神圣石:")
        divine_label.setStyleSheet(f"color: {self.currency_colors['divine']}; font-weight: bold; font-size: 18px;")
        price_grid.addWidget(divine_label, 0, 0)
        
        # 神圣石实时价格
        self.divine_price_label = QLabel("加载中...")
        self.divine_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")
        self.divine_price_label.setMinimumWidth(80)  # 减少最小宽度
        self.divine_price_label.setMaximumWidth(150)  # 添加最大宽度限制
        price_grid.addWidget(self.divine_price_label, 0, 1)
        
        # 神圣石输入框
        self.divine_amount = QLineEdit("1")
        self.divine_amount.textChanged.connect(self.on_divine_amount_changed)
        self.divine_amount.setFocusPolicy(Qt.ClickFocus)
        self.divine_amount.setFixedWidth(80)  # 固定宽度
        self.divine_amount.setStyleSheet("font-size: 18px;")
        price_grid.addWidget(self.divine_amount, 0, 2)
        
        # 神圣石价值
        self.divine_value = QLabel(f"￥{1 * self.prices['divine']:.2f}")
        self.divine_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")
        self.divine_value.setMinimumWidth(70)  # 减少最小宽度
        self.divine_value.setMaximumWidth(120)  # 添加最大宽度限制
        price_grid.addWidget(self.divine_value, 0, 3)
        
        # 神圣石兑换比例 - 简化为单个标签
        self.divine_exchange_label = QLabel("≈<span style='color:#00BFFF'>0E</span> | <span style='color:#FF6347'>0C</span> | <span style='color:#32CD32'>0CH</span>")
        self.divine_exchange_label.setStyleSheet("color: #CCCCCC; font-size: 17px;")
        price_grid.addWidget(self.divine_exchange_label, 0, 4)
        
        # 崇高石行 - 第2行
        exalted_label = QLabel("崇高石:")
        exalted_label.setStyleSheet(f"color: {self.currency_colors['exalted']}; font-weight: bold; font-size: 18px;")
        price_grid.addWidget(exalted_label, 1, 0)
        
        # 崇高石实时价格
        self.exalted_price_label = QLabel("加载中...")
        self.exalted_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")
        self.exalted_price_label.setMinimumWidth(80)  # 减少最小宽度
        self.exalted_price_label.setMaximumWidth(150)  # 添加最大宽度限制
        price_grid.addWidget(self.exalted_price_label, 1, 1)
        
        # 崇高石输入框
        self.exalted_amount = QLineEdit("100")
        self.exalted_amount.textChanged.connect(self.on_exalted_amount_changed)
        self.exalted_amount.setFocusPolicy(Qt.ClickFocus)
        self.exalted_amount.setFixedWidth(80)  # 固定宽度
        self.exalted_amount.setStyleSheet("font-size: 18px;")
        price_grid.addWidget(self.exalted_amount, 1, 2)
        
        # 崇高石价值
        self.exalted_value = QLabel(f"￥{100 * self.prices['exalted']:.2f}")
        self.exalted_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")
        self.exalted_value.setMinimumWidth(70)  # 减少最小宽度
        self.exalted_value.setMaximumWidth(120)  # 添加最大宽度限制
        price_grid.addWidget(self.exalted_value, 1, 3)
        
        # 崇高石兑换比例 - 简化为单个标签
        self.exalted_exchange_label = QLabel("≈<span style='color:#FFFF00'>0D</span> | <span style='color:#FF6347'>0C</span> | <span style='color:#32CD32'>0CH</span>")
        self.exalted_exchange_label.setStyleSheet("color: #CCCCCC; font-size: 17px;")
        price_grid.addWidget(self.exalted_exchange_label, 1, 4)
        
        # 混沌石行 - 第3行
        chaos_label = QLabel("混沌石:")
        chaos_label.setStyleSheet(f"color: {self.currency_colors['chaos']}; font-weight: bold; font-size: 18px;")
        price_grid.addWidget(chaos_label, 2, 0)
        
        # 混沌石实时价格
        self.chaos_price_label = QLabel("加载中...")
        self.chaos_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")
        self.chaos_price_label.setMinimumWidth(80)  # 减少最小宽度
        self.chaos_price_label.setMaximumWidth(150)  # 添加最大宽度限制
        price_grid.addWidget(self.chaos_price_label, 2, 1)
        
        # 混沌石输入框
        self.chaos_amount = QLineEdit("100")
        self.chaos_amount.textChanged.connect(self.on_chaos_amount_changed)
        self.chaos_amount.setFocusPolicy(Qt.ClickFocus)
        self.chaos_amount.setFixedWidth(80)  # 固定宽度
        self.chaos_amount.setStyleSheet("font-size: 18px;")
        price_grid.addWidget(self.chaos_amount, 2, 2)
        
        # 混沌石价值
        self.chaos_value = QLabel(f"￥{100 * self.prices['chaos']:.2f}")
        self.chaos_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")
        self.chaos_value.setMinimumWidth(70)  # 减少最小宽度
        self.chaos_value.setMaximumWidth(120)  # 添加最大宽度限制
        price_grid.addWidget(self.chaos_value, 2, 3)
        
        # 混沌石兑换比例 - 简化为单个标签
        self.chaos_exchange_label = QLabel("≈<span style='color:#FFFF00'>0D</span> | <span style='color:#00BFFF'>0E</span> | <span style='color:#32CD32'>0CH</span>")
        self.chaos_exchange_label.setStyleSheet("color: #CCCCCC; font-size: 17px;")
        price_grid.addWidget(self.chaos_exchange_label, 2, 4)
        
        # 机会石行 - 第4行
        chance_label = QLabel("机会石:")
        chance_label.setStyleSheet(f"color: {self.currency_colors['chance']}; font-weight: bold; font-size: 18px;")
        price_grid.addWidget(chance_label, 3, 0)
        
        # 机会石实时价格
        self.chance_price_label = QLabel("加载中...")
        self.chance_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")
        self.chance_price_label.setMinimumWidth(80)  # 减少最小宽度
        self.chance_price_label.setMaximumWidth(150)  # 添加最大宽度限制
        price_grid.addWidget(self.chance_price_label, 3, 1)
        
        # 机会石输入框
        self.chance_amount = QLineEdit("100")
        self.chance_amount.textChanged.connect(self.on_chance_amount_changed)
        self.chance_amount.setFocusPolicy(Qt.ClickFocus)
        self.chance_amount.setFixedWidth(80)  # 固定宽度
        self.chance_amount.setStyleSheet("font-size: 18px;")
        price_grid.addWidget(self.chance_amount, 3, 2)
        
        # 机会石价值
        self.chance_value = QLabel(f"￥{100 * self.prices['chance']:.2f}")
        self.chance_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")
        self.chance_value.setMinimumWidth(70)  # 减少最小宽度
        self.chance_value.setMaximumWidth(120)  # 添加最大宽度限制
        price_grid.addWidget(self.chance_value, 3, 3)
        
        # 机会石兑换比例 - 简化为单个标签
        self.chance_exchange_label = QLabel("≈<span style='color:#FFFF00'>0D</span> | <span style='color:#00BFFF'>0E</span> | <span style='color:#FF6347'>0C</span>")
        self.chance_exchange_label.setStyleSheet("color: #CCCCCC; font-size: 17px;")
        price_grid.addWidget(self.chance_exchange_label, 3, 4)
        
        # 添加价格网格到内容布局
        content_layout.addLayout(price_grid)
        
        # 底部布局 - 说明文本和倒计时
        bottom_layout = QHBoxLayout()
        
        # 添加说明文本
        price_note = QLabel("说明: 价格数据来自平台，每10分钟自动更新一次。")
        price_note.setStyleSheet("color: #888888; margin-top: 10px; font-size: 16px;")  # 增加字体大小
        bottom_layout.addWidget(price_note)
        
        # 添加弹性空间，将倒计时推到右侧
        bottom_layout.addStretch(1)
        
        # 添加倒计时标签
        self.countdown_label = QLabel("下次刷新: 10:00")
        self.countdown_label.setStyleSheet("color: #888888; margin-top: 10px; font-size: 14px;")
        bottom_layout.addWidget(self.countdown_label)
        
        # 将底部布局添加到内容布局
        content_layout.addLayout(bottom_layout)
        
        # 将内容添加到滚动区域
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
        # 设置最小高度，确保内容不会被过度压缩
        self.setMinimumHeight(250)  # 设置标签页最小高度
    
    def update_price(self, currency, price):
        """更新货币价格并重新计算所有比例"""
        # 更新价格数据
        self.prices[currency] = price
        
        # 更新价格显示 - 保持4位小数，并恢复颜色
        price_label = getattr(self, f"{currency}_price_label", None)
        if price_label:
            price_label.setText(f"￥{price:.4f}/个")  # 恢复"/个"后缀
            price_label.setStyleSheet(f"color: {self.currency_colors[currency]}; font-size: 18px;")  # 恢复颜色并设置一致的字体大小
        
        # 更新价值
        self.calculate_value()
        
        # 重要：直接更新兑换比例，不依赖于calculate_value
        self.update_exchange_rates()
    
    def refresh_prices(self):
        """刷新价格数据"""
        try:
            # 检查是否已经有一个刷新线程在运行
            if hasattr(self, 'price_thread') and self.price_thread.isRunning():
                return
            
            # 更新UI显示为"正在刷新..."
            for currency in self.currency_names:
                price_label = getattr(self, f"{currency}_price_label", None)
                if price_label:
                    price_label.setText("正在刷新...")  # 使用"正在刷新..."而不是"加载中..."
                    price_label.setStyleSheet(f"color: #888888; font-style: italic; font-size: 18px;")  # 使用灰色、斜体并保持字体大小
            
            # 创建新的价格爬取线程
            self.price_thread = PriceScraper()
            self.price_thread.price_updated.connect(self.update_price)
            
            # 添加完成信号处理
            self.price_thread.finished.connect(self.on_price_refresh_finished)
            
            # 启动线程
            self.price_thread.start()
            
            # 重置倒计时
            self.start_time = datetime.now()
            self.countdown_seconds = 600  # 10分钟
            
            # 更新倒计时显示
            self.update_countdown_display()
            
        except Exception as e:
            # 恢复原来的价格显示
            self.update_all_price_displays()
    
    def update_countdown_display(self):
        """更新倒计时显示"""
        try:
            elapsed_seconds = (datetime.now() - self.start_time).total_seconds()
            remaining_seconds = max(0, self.countdown_seconds - elapsed_seconds)
            minutes = int(remaining_seconds // 60)
            seconds = int(remaining_seconds % 60)
            
            self.countdown_label.setText(f"下次刷新: {minutes:02d}:{seconds:02d}")
            self.countdown_label.setStyleSheet("color: #888888; margin-top: 10px; font-size: 14px;")
            
            # 如果倒计时结束，自动刷新价格
            if remaining_seconds <= 0:
                self.refresh_prices()
                
        except:
            self.countdown_label.setText("下次刷新: --:--")
            self.countdown_label.setStyleSheet("color: #888888; margin-top: 10px; font-size: 14px;")
    
    def on_price_refresh_finished(self):
        """价格刷新完成后的处理"""
        # 恢复价格标签的颜色
        for currency in self.currency_names:
            price_label = getattr(self, f"{currency}_price_label", None)
            if price_label:
                price_label.setStyleSheet(f"color: {self.currency_colors[currency]}; font-size: 18px;")  # 恢复颜色并设置一致的字体大小
        
        # 确保所有价格显示都已更新
        self.update_all_price_displays()
        
        # 更新倒计时显示
        self.update_countdown_display()
    
    def update_all_price_displays(self):
        """更新所有价格显示"""
        for currency in self.currency_names:
            price = self.prices[currency]
            price_label = getattr(self, f"{currency}_price_label", None)
            if price_label:
                price_label.setText(f"￥{price:.4f}/个")  # 恢复"/个"后缀
                price_label.setStyleSheet(f"color: {self.currency_colors[currency]}; font-size: 18px;")  # 恢复颜色并设置一致的字体大小
        
        # 重新计算价值和兑换比例
        self.calculate_value()
    
    def calculate_value(self):
        """计算货币价值"""
        try:
            # 获取输入值 - 使用float而不是int，以支持小数输入
            divine_amount = float(self.divine_amount.text() or "0")
            exalted_amount = float(self.exalted_amount.text() or "0")
            chaos_amount = float(self.chaos_amount.text() or "0")
            chance_amount = float(self.chance_amount.text() or "0")
            
            # 计算价值
            divine_value = divine_amount * self.prices["divine"]
            exalted_value = exalted_amount * self.prices["exalted"]
            chaos_value = chaos_amount * self.prices["chaos"]
            chance_value = chance_amount * self.prices["chance"]
            
            # 更新各个价值标签
            self.divine_value.setText(f"￥{divine_value:.2f}")
            self.exalted_value.setText(f"￥{exalted_value:.2f}")
            self.chaos_value.setText(f"￥{chaos_value:.2f}")
            self.chance_value.setText(f"￥{chance_value:.2f}")
            
            # 重要：直接更新兑换比例，不依赖于其他方法
            self.update_exchange_rates()
        except (ValueError, AttributeError) as e:
            # 即使出错，也尝试更新兑换比例
            try:
                self.update_exchange_rates()
            except Exception as e2:
                pass
    
    def update_exchange_rates(self):
        """更新所有兑换比例"""
        # 防止除以零
        if self.prices['divine'] <= 0 or self.prices['exalted'] <= 0 or self.prices['chaos'] <= 0 or self.prices['chance'] <= 0:
            return
        
        try:
            # 获取用户输入的货币数量
            divine_amount = float(self.divine_amount.text() or "0")
            exalted_amount = float(self.exalted_amount.text() or "0")
            chaos_amount = float(self.chaos_amount.text() or "0")
            chance_amount = float(self.chance_amount.text() or "0")
            
            # 计算兑换比例
            
            # Divine to Exalted & Chaos & Chance
            divine_to_exalted = divine_amount * (self.prices['divine'] / self.prices['exalted'])
            divine_to_chaos = divine_amount * (self.prices['divine'] / self.prices['chaos'])
            divine_to_chance = divine_amount * (self.prices['divine'] / self.prices['chance'])
            
            # Exalted to Divine & Chaos & Chance
            exalted_to_divine = exalted_amount * (self.prices['exalted'] / self.prices['divine'])
            exalted_to_chaos = exalted_amount * (self.prices['exalted'] / self.prices['chaos'])
            exalted_to_chance = exalted_amount * (self.prices['exalted'] / self.prices['chance'])
            
            # Chaos to Divine & Exalted & Chance
            chaos_to_divine = chaos_amount * (self.prices['chaos'] / self.prices['divine'])
            chaos_to_exalted = chaos_amount * (self.prices['chaos'] / self.prices['exalted'])
            chaos_to_chance = chaos_amount * (self.prices['chaos'] / self.prices['chance'])
            
            # Chance to Divine & Exalted & Chaos
            chance_to_divine = chance_amount * (self.prices['chance'] / self.prices['divine'])
            chance_to_exalted = chance_amount * (self.prices['chance'] / self.prices['exalted'])
            chance_to_chaos = chance_amount * (self.prices['chance'] / self.prices['chaos'])
            
            # 更新简化的兑换比例标签 - 添加颜色
            self.divine_exchange_label.setText(f"≈<span style='color:#00BFFF'>{divine_to_exalted:.1f}E</span> | <span style='color:#FF6347'>{divine_to_chaos:.1f}C</span> | <span style='color:#32CD32'>{divine_to_chance:.0f}CH</span>")
            self.exalted_exchange_label.setText(f"≈<span style='color:#FFFF00'>{exalted_to_divine:.1f}D</span> | <span style='color:#FF6347'>{exalted_to_chaos:.1f}C</span> | <span style='color:#32CD32'>{exalted_to_chance:.0f}CH</span>")
            self.chaos_exchange_label.setText(f"≈<span style='color:#FFFF00'>{chaos_to_divine:.1f}D</span> | <span style='color:#00BFFF'>{chaos_to_exalted:.1f}E</span> | <span style='color:#32CD32'>{chaos_to_chance:.0f}CH</span>")
            self.chance_exchange_label.setText(f"≈<span style='color:#FFFF00'>{chance_to_divine:.2f}D</span> | <span style='color:#00BFFF'>{chance_to_exalted:.1f}E</span> | <span style='color:#FF6347'>{chance_to_chaos:.1f}C</span>")
            
        except (ValueError, ZeroDivisionError):
            # 出错时恢复到默认显示 - 保持颜色
            self.divine_exchange_label.setText("≈<span style='color:#00BFFF'>0E</span> | <span style='color:#FF6347'>0C</span> | <span style='color:#32CD32'>0CH</span>")
            self.exalted_exchange_label.setText("≈<span style='color:#FFFF00'>0D</span> | <span style='color:#FF6347'>0C</span> | <span style='color:#32CD32'>0CH</span>")
            self.chaos_exchange_label.setText("≈<span style='color:#FFFF00'>0D</span> | <span style='color:#00BFFF'>0E</span> | <span style='color:#32CD32'>0CH</span>")
            self.chance_exchange_label.setText("≈<span style='color:#FFFF00'>0D</span> | <span style='color:#00BFFF'>0E</span> | <span style='color:#FF6347'>0C</span>")
    
    def on_divine_amount_changed(self, text):
        """神圣石数量变更响应函数"""
        if text:
            try:
                # 尝试将输入转换为浮点数
                float(text)
                # 计算价值
                self.calculate_value()
            except ValueError:
                # 如果输入的不是数字，恢复到默认值
                self.divine_amount.setText("1")
    
    def on_exalted_amount_changed(self, text):
        """崇高石数量变更响应函数"""
        if text:
            try:
                # 尝试将输入转换为浮点数
                float(text)
                # 计算价值
                self.calculate_value()
            except ValueError:
                # 如果输入的不是数字，恢复到默认值
                self.exalted_amount.setText("100")
    
    def on_chaos_amount_changed(self, text):
        """混沌石数量变更响应函数"""
        if text:
            try:
                # 尝试将输入转换为浮点数
                float(text)
                # 计算价值
                self.calculate_value()
            except ValueError:
                # 如果输入的不是数字，恢复到默认值
                self.chaos_amount.setText("100")
    
    def on_chance_amount_changed(self, text):
        """机会石数量变更响应函数"""
        if text:
            try:
                # 尝试将输入转换为浮点数
                float(text)
                # 计算价值
                self.calculate_value()
            except ValueError:
                # 如果输入的不是数字，恢复到默认值
                self.chance_amount.setText("100") 
