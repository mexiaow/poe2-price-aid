import sys
import requests
from bs4 import BeautifulSoup
import re
import webbrowser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox,
                            QGridLayout, QFrame, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
                            QMessageBox, QProgressDialog)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
import json
import os
import time
from datetime import datetime
import subprocess
import tempfile
import urllib.request
import shutil
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 在程序启动时确保能找到Python DLL
if getattr(sys, 'frozen', False):
    # 将应用程序目录添加到DLL搜索路径
    os.environ['PATH'] = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)) + os.pathsep + os.environ['PATH']
    
    # 使用ctypes预加载python DLL
    import ctypes
    try:
        dll_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'python310.dll')
        if os.path.exists(dll_path):
            ctypes.CDLL(dll_path)
    except Exception as e:
        pass

class PriceScraper(QThread):
    price_updated = pyqtSignal(str, float)
    
    def __init__(self):
        super().__init__()
        self.urls = {
            "divine": "https://www.dd373.com/s-3hcpqw-c-8rknmp-bwgvrk-1mbdfs.html",
            "exalted": "https://www.dd373.com/s-3hcpqw-c-tqcbc6-bwgvrk-1mbdfs.html",
            "chaos": "https://www.dd373.com/s-3hcpqw-c-henjrw-bwgvrk-1mbdfs.html"
        }
        
    def run(self):
        for currency, url in self.urls.items():
            try:
                price = self.get_price(url)
                if price > 0:  # 只有当价格有效时才发送信号
                    self.price_updated.emit(currency, price)
                    # 添加短暂延迟，避免请求过快
                    self.msleep(500)
            except Exception as e:
                pass
    
    def get_price(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 首先尝试用户提供的CSS选择器
            css_selector = "div.good-list-box > div:nth-child(1) > div.width233.p-l30 > div.p-r66 > p.font12.color666.m-t5"
            price_element = soup.select_one(css_selector)
            
            # 如果上面的选择器失败，尝试一个更简化的版本
            if not price_element:
                price_element = soup.select_one('div.good-list-box div:first-child div.p-r66 p.font12.color666.m-t5')
            
            # 如果还是失败，尝试原始的选择器
            if not price_element:
                price_element = soup.select_one('p.font12.color666.m-t5')
            
            if not price_element:
                price_element = soup.select_one('.good-list-box div:first-child .p-r66 p.font12')
            
            # 尝试精确匹配用户提供的XPath对应的元素
            if not price_element:
                price_element = soup.select_one('div.main div.goods-list-content div div.sell-goods div.good-list-box div:first-child div.width233.p-l30 div.p-r66 p.font12.color666.m-t5')
            
            if price_element:
                price_text = price_element.text.strip()
                match = re.search(r'(\d+\.\d+)', price_text)
                if match:
                    price = float(match.group(1))
                    return price
            else:
                # 如果所有选择器都失败，尝试使用更通用的方法
                all_price_elements = soup.select('p.font12.color666')
                for element in all_price_elements:
                    price_text = element.text.strip()
                    match = re.search(r'(\d+\.\d+)', price_text)
                    if match:
                        price = float(match.group(1))
                        return price
        except Exception as e:
            pass
        
        # 价格获取失败时返回0
        return 0.0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 版本信息
        self.current_version = "1.0.6"  # 确保在使用之前初始化
        self.update_url = "https://gitee.com/mexiaow/poe2-price-aid/raw/main/update.json?v=1.0.6"
        
        # 添加更新标志，避免重复检查
        self.is_updating = False
        
        # 添加一个属性来跟踪取消状态
        self.download_canceled = False
        
        # 清理缓存，确保字体大小一致
        self.clear_app_cache()
        
        # 在窗口标题中添加版本号
        self.setWindowTitle(f"POE2PriceAid v{self.current_version}")
        self.setMinimumSize(900, 350)  # 调整宽度到900
        
        # 设置深色主题
        self.setup_dark_theme()
        
        # 价格数据
        self.prices = {"divine": 0.00, "exalted": 0.00, "chaos": 0.00}
        self.currency_names = {"divine": "神圣石", "exalted": "崇高石", "chaos": "混沌石"}
        self.currency_colors = {"divine": "#FFD700", "exalted": "#00BFFF", "chaos": "#FF6347"}
        
        # 增强DPI感知设置
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 强制设置应用程序字体大小
        app = QApplication.instance()
        font = app.font()
        font.setPointSize(16)  # 将14px调整为16px，更适合大多数显示器
        app.setFont(font)
        
        # 禁用系统DPI缩放，使用自定义缩放
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
        os.environ["QT_SCALE_FACTOR"] = "1"
        
        # 创建UI
        self.init_ui()
        
        # 启动价格更新线程
        self.price_thread = PriceScraper()
        self.price_thread.price_updated.connect(self.update_price)
        self.price_thread.finished.connect(self.on_price_refresh_finished)  # 添加完成信号处理
        self.price_thread.start()
        
        # 注释掉自动更新检查
        # self.update_timer = QTimer(self)
        # self.update_timer.timeout.connect(self.check_for_updates)
        # self.update_timer.start(3600000)  # 每小时检查一次更新 (3600000毫秒)
        # 
        # # 启动时检查更新
        # 设置自动更新检查
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start(3600000)  # 每小时检查一次更新 (3600000毫秒)
        
        # 启动时检查更新
        QTimer.singleShot(5000, self.check_for_updates)  # 启动5秒后检查更新
    
    def setup_dark_theme(self):
        # 设置深色主题
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        
        self.setPalette(dark_palette)
        
        # 设置样式表 - 更扁平化的设计，使用微软雅黑字体，更圆润
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
                font-size: 16px; /* 从14px调整为16px */
            }
            QTabWidget::pane {
                border: none;
                background-color: #1E1E1E;
                border-radius: 8px;
                margin-top: 5px; /* 增加标签页内容与标签的间距 */
            }
            QTabBar::tab {
                background-color: #2D2D2D;
                color: #CCCCCC;
                padding: 12px 24px;
                margin-right: 6px;
                border: none;
                border-radius: 6px 6px 0 0;
                font-size: 16px; /* 从14px调整为16px */
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border-bottom: 3px solid #0078D7; /* 增加底部边框厚度 */
            }
            QTabBar::tab:hover:!selected {
                background-color: #353535;
                color: #FFFFFF;
            }
            QGroupBox {
                background-color: #2D2D2D;
                border: none;
                border-radius: 8px;
                padding: 15px;
                margin-top: 25px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                background-color: #2D2D2D;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QLineEdit, QComboBox {
                background-color: #3E3E3E;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #0078D7;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078D7;
            }
            QTableWidget {
                background-color: #2D2D2D;
                alternate-background-color: #353535;
                gridline-color: #444444;
                border: none;
                border-radius: 5px;
                selection-background-color: #0078D7;
            }
            QHeaderView::section {
                background-color: #383838;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 0px;
            }
            QTableWidget::item {
                padding: 5px;
                border: none;
                border-radius: 0px;
            }
            QTableWidget::item:selected {
                background-color: #0078D7;
            }
            QScrollBar:vertical {
                border: none;
                background: #2D2D2D;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QLabel {
                background: transparent;
            }
            QFrame {
                border: none;
            }
        """)
    
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.create_header(main_layout)
        self.create_tabs(main_layout)
        
        self.setCentralWidget(main_widget)
        
        # 添加事件过滤器，处理点击其他区域时清除焦点
        main_widget.installEventFilter(self)
        
        # 初始计算
        self.calculate_value()
        
        # 在GUI初始化末尾处理图标
        # 使用绝对路径获取图标
        if getattr(sys, 'frozen', False):
            # 如果是打包后的程序
            base_path = sys._MEIPASS
        else:
            # 如果是源代码运行
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        icon_path = os.path.join(base_path, 'app.ico')
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # 设置应用程序图标，影响任务栏
            if hasattr(app, 'setWindowIcon'):
                app.setWindowIcon(QIcon(icon_path))
        else:
            # 尝试在当前目录直接查找
            if os.path.exists('app.ico'):
                self.setWindowIcon(QIcon('app.ico'))
                if hasattr(app, 'setWindowIcon'):
                    app.setWindowIcon(QIcon('app.ico'))
    
    def create_header(self, parent_layout):
        """创建标题和按钮"""
        # 顶部标题和按钮
        header_layout = QHBoxLayout()  # 使用水平布局，所有元素在同一行
        
        # 左侧标题
        title_label = QLabel("POE2PriceAid")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # 添加导航按钮 - 放在标题右侧，功能按钮左侧
        # 导航按钮样式 - 更大的字体和统一的颜色
        nav_button_style = """
            QPushButton {
                background-color: transparent;
                color: #0078D7;
                border: none;
                padding: 4px 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #1C86E0;
                border-bottom: 2px solid #1C86E0;
            }
            QPushButton:pressed {
                color: #005A9E;
            }
        """
        
        # 创建导航按钮函数
        def create_nav_button(text, url):
            button = QPushButton(text)
            button.setStyleSheet(nav_button_style)
            button.clicked.connect(lambda: webbrowser.open(url))
            button.setFixedHeight(30)  # 增加高度，使按钮更大
            return button
        
        # 添加导航按钮
        nav_buttons = [
            ("编年史", "https://poe2db.tw/cn/"),
            ("官网", "https://pathofexile2.com/home"),
            ("市集", "https://www.pathofexile.com/trade2/search/poe2/Standard"),
            ("忍者", "https://poe2.ninja/builds/"),
            ("踩蘑菇", "https://www.caimogu.cc/circle/449.html")
        ]
        
        # 添加一个小的分隔符
        header_layout.addSpacing(15)
        
        # 添加导航按钮
        for text, url in nav_buttons:
            header_layout.addWidget(create_nav_button(text, url))
        
        # 添加弹性空间，将功能按钮推到右侧
        header_layout.addStretch()
        
        # 右侧按钮组 - 使用水平布局将按钮放在一起
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)  # 设置按钮之间的间距
        
        # 刷新价格按钮
        refresh_button = QPushButton("刷新价格")
        refresh_button.clicked.connect(self.refresh_prices)
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        buttons_layout.addWidget(refresh_button)
        
        # 检查更新按钮
        check_update_button = QPushButton("检查更新")
        check_update_button.clicked.connect(self.check_updates_manually)
        check_update_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        buttons_layout.addWidget(check_update_button)
        
        # 将按钮组添加到标题栏
        header_layout.addLayout(buttons_layout)
        
        # 将整个头部布局添加到主布局
        parent_layout.addLayout(header_layout)

    def create_tabs(self, parent_layout):
        """创建选项卡"""
        # 选项卡
        tab_widget = QTabWidget()
        
        # 价格监控选项卡
        price_tab = QWidget()
        price_layout = QVBoxLayout(price_tab)
        price_layout.setContentsMargins(20, 20, 20, 20)
        
        # 价格监控网格布局 - 直接添加到价格标签页
        price_grid = QGridLayout()
        price_grid.setSpacing(10)  # 设置网格间距
        
        # 移除表头，直接从第1行开始
        
        # 神圣石行 - 第1行
        divine_label = QLabel("神圣石:")
        divine_label.setStyleSheet(f"color: {self.currency_colors['divine']}; font-weight: bold; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(divine_label, 0, 0)
        
        # 神圣石实时价格
        self.divine_price_label = QLabel("加载中...")
        self.divine_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.divine_price_label, 0, 1)
        
        # 神圣石输入框
        self.divine_amount = QLineEdit("1")
        self.divine_amount.textChanged.connect(self.on_divine_amount_changed)
        self.divine_amount.setFocusPolicy(Qt.ClickFocus)
        self.divine_amount.setFixedWidth(80)  # 固定宽度
        self.divine_amount.setStyleSheet("font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.divine_amount, 0, 2)
        
        # 神圣石价值
        self.divine_value = QLabel(f"￥{100 * self.prices['divine']:.2f}")
        self.divine_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.divine_value, 0, 3)
        
        # 神圣石兑换比例 - 放在同一单元格中
        divine_exchange = QHBoxLayout()
        self.divine_to_exalted = QLabel(f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>0E</span>")
        self.divine_to_exalted.setStyleSheet("font-size: 18px;")  # 增加字体大小
        self.divine_to_chaos = QLabel(f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>0C</span>")
        self.divine_to_chaos.setStyleSheet("font-size: 18px;")  # 增加字体大小
        divine_exchange.addWidget(self.divine_to_exalted)
        divine_exchange.addWidget(self.divine_to_chaos)
        divine_exchange_widget = QWidget()
        divine_exchange_widget.setLayout(divine_exchange)
        price_grid.addWidget(divine_exchange_widget, 0, 4, 1, 2)
        
        # 崇高石行 - 第2行
        exalted_label = QLabel("崇高石:")
        exalted_label.setStyleSheet(f"color: {self.currency_colors['exalted']}; font-weight: bold; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(exalted_label, 1, 0)
        
        # 崇高石实时价格
        self.exalted_price_label = QLabel("加载中...")
        self.exalted_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.exalted_price_label, 1, 1)
        
        # 崇高石输入框
        self.exalted_amount = QLineEdit("100")
        self.exalted_amount.textChanged.connect(self.on_exalted_amount_changed)
        self.exalted_amount.setFocusPolicy(Qt.ClickFocus)
        self.exalted_amount.setFixedWidth(80)  # 固定宽度
        self.exalted_amount.setStyleSheet("font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.exalted_amount, 1, 2)
        
        # 崇高石价值
        self.exalted_value = QLabel(f"￥{100 * self.prices['exalted']:.2f}")
        self.exalted_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.exalted_value, 1, 3)
        
        # 崇高石兑换比例 - 放在同一单元格中
        exalted_exchange = QHBoxLayout()
        self.exalted_to_divine = QLabel(f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>0D</span>")
        self.exalted_to_divine.setStyleSheet("font-size: 18px;")  # 增加字体大小
        self.exalted_to_chaos = QLabel(f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>0C</span>")
        self.exalted_to_chaos.setStyleSheet("font-size: 18px;")  # 增加字体大小
        exalted_exchange.addWidget(self.exalted_to_divine)
        exalted_exchange.addWidget(self.exalted_to_chaos)
        exalted_exchange_widget = QWidget()
        exalted_exchange_widget.setLayout(exalted_exchange)
        price_grid.addWidget(exalted_exchange_widget, 1, 4, 1, 2)
        
        # 混沌石行 - 第3行
        chaos_label = QLabel("混沌石:")
        chaos_label.setStyleSheet(f"color: {self.currency_colors['chaos']}; font-weight: bold; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(chaos_label, 2, 0)
        
        # 混沌石实时价格
        self.chaos_price_label = QLabel("加载中...")
        self.chaos_price_label.setStyleSheet(f"color: #888888; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.chaos_price_label, 2, 1)
        
        # 混沌石输入框
        self.chaos_amount = QLineEdit("100")
        self.chaos_amount.textChanged.connect(self.on_chaos_amount_changed)
        self.chaos_amount.setFocusPolicy(Qt.ClickFocus)
        self.chaos_amount.setFixedWidth(80)  # 固定宽度
        self.chaos_amount.setStyleSheet("font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.chaos_amount, 2, 2)
        
        # 混沌石价值
        self.chaos_value = QLabel(f"￥{100 * self.prices['chaos']:.2f}")
        self.chaos_value.setStyleSheet("color: #00FF00; font-weight: bold; font-size: 18px;")  # 增加字体大小
        price_grid.addWidget(self.chaos_value, 2, 3)
        
        # 混沌石兑换比例 - 放在同一单元格中
        chaos_exchange = QHBoxLayout()
        self.chaos_to_divine = QLabel(f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>0D</span>")
        self.chaos_to_divine.setStyleSheet("font-size: 18px;")  # 增加字体大小
        self.chaos_to_exalted = QLabel(f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>0E</span>")
        self.chaos_to_exalted.setStyleSheet("font-size: 18px;")  # 增加字体大小
        chaos_exchange.addWidget(self.chaos_to_divine)
        chaos_exchange.addWidget(self.chaos_to_exalted)
        chaos_exchange_widget = QWidget()
        chaos_exchange_widget.setLayout(chaos_exchange)
        price_grid.addWidget(chaos_exchange_widget, 2, 4, 1, 2)
        
        # 添加价格网格到价格标签页
        price_layout.addLayout(price_grid)
        
        # 添加说明文本
        price_note = QLabel("说明: 价格数据来自平台，每5分钟自动更新一次。")
        price_note.setStyleSheet("color: #888888; margin-top: 10px; font-size: 16px;")  # 增加字体大小
        price_layout.addWidget(price_note)
        
        # 添加弹性空间
        price_layout.addStretch(1)
        
        # A大补丁选项卡 - 使用更紧凑的布局
        tools_tab = QWidget()
        tools_layout = QVBoxLayout(tools_tab)
        tools_layout.setContentsMargins(20, 15, 20, 15)  # 减小边距
        tools_layout.setSpacing(5)  # 减小间距
        
        # 标题和内容样式
        title_style = "font-size: 24px; margin-bottom: 10px; font-weight: bold;"
        content_style = "font-size: 18px; margin-bottom: 5px;"
        # 为易刷、一乐过滤和繁体化标题创建小一号的标题样式
        subtitle_style = "font-size: 20px; margin-bottom: 10px; font-weight: bold;"
        
        # 下载部分 - 标题和链接分行显示
        # 移除水平布局，直接添加到主布局
        download_title = QLabel("最新版本：")
        download_title.setStyleSheet(title_style)
        tools_layout.addWidget(download_title)
        
        # 增加链接字体大小
        download_link = QLabel("<a href='https://cloud.xiaow.org:8443/s/vmIj' style='color: #0078d7;'>https://cloud.xiaow.org:8443/s/vmIj</a>")
        download_link.setOpenExternalLinks(True)
        download_link.setStyleSheet("font-size: 24px; margin-bottom: 5px;")  # 增加字体大小到24px
        tools_layout.addWidget(download_link)
        
        # 添加一些空间，但减少高度
        spacer = QLabel("")
        spacer.setStyleSheet("margin-top: 10px;")
        tools_layout.addWidget(spacer)
        
        # 使用方法部分
        usage_title = QLabel("使用方法：")
        usage_title.setStyleSheet(title_style)
        tools_layout.addWidget(usage_title)
        
        # 使用垂直布局来放置步骤
        steps_layout = QVBoxLayout()
        steps_layout.setSpacing(2)  # 减小步骤之间的间距
        
        # 使用单独的标签显示每个步骤
        step1 = QLabel("1.打开VisualGGPK3")
        step2 = QLabel("2.选择POE2根目录Content.ggpk")
        step3 = QLabel("3.然后将你需要的补丁zip压缩包直接拖进VisualGGPK3窗口")
        
        # 为步骤设置更大的字体
        steps_style = content_style.replace("18px", "22px")  # 将字体从18px增加到22px
        
        for step in [step1, step2, step3]:
            step.setStyleSheet(steps_style)
            steps_layout.addWidget(step)
        
        tools_layout.addLayout(steps_layout)
        
        # 不需要太多的弹性空间
        tools_layout.addStretch(1)
        
        # 添加易刷查价选项卡
        easy_refresh_tab = QWidget()
        easy_refresh_layout = QVBoxLayout(easy_refresh_tab)
        easy_refresh_layout.setContentsMargins(20, 15, 20, 15)  # 减小边距
        easy_refresh_layout.setSpacing(5)  # 减小间距
        
        # 最新版本部分 - 使用小一号的标题样式
        er_download_title = QLabel("易刷最新版本：")
        er_download_title.setStyleSheet(subtitle_style)  # 使用小一号标题样式
        easy_refresh_layout.addWidget(er_download_title)
        
        # 增加链接字体大小
        er_download_link = QLabel("<a href='https://efarm-gjf-release3.710421059.xyz/' style='color: #0078d7;'>https://efarm-gjf-release3.710421059.xyz/</a>")
        er_download_link.setOpenExternalLinks(True)
        er_download_link.setStyleSheet("font-size: 22px; margin-bottom: 5px;")  # 增加字体大小到24px
        easy_refresh_layout.addWidget(er_download_link)
        
        # 添加一些空间，但减少高度
        er_spacer = QLabel("")
        er_spacer.setStyleSheet("margin-top: 10px;")
        easy_refresh_layout.addWidget(er_spacer)

        # 一乐过滤部分 - 使用小一号的标题样式
        er_download_title = QLabel("一乐过滤：")
        er_download_title.setStyleSheet(subtitle_style)  # 使用小一号标题样式
        easy_refresh_layout.addWidget(er_download_title)
        
        # 增加链接字体大小，但比其他链接小一号
        er_download_link = QLabel("<a href='https://cloud.xiaow.org:8443/s/wRSz' style='color: #0078d7;'>https://cloud.xiaow.org:8443/s/wRSz</a>")
        er_download_link.setOpenExternalLinks(True)
        er_download_link.setStyleSheet("font-size: 22px; margin-bottom: 5px;")  # 字体调小到22px
        easy_refresh_layout.addWidget(er_download_link)
        
        # 添加一些空间，但减少高度
        er_spacer = QLabel("")
        er_spacer.setStyleSheet("margin-top: 10px;")
        easy_refresh_layout.addWidget(er_spacer)

        # poe2网页市集繁体化部分 - 使用小一号的标题样式
        er_download_title = QLabel("poe2网页市集繁体化：")
        er_download_title.setStyleSheet(subtitle_style)  # 使用小一号标题样式
        easy_refresh_layout.addWidget(er_download_title)
        
        # 增加链接字体大小
        er_download_link = QLabel("<a href='https://greasyfork.org/zh-CN/scripts/520190-poe2-trade-%E7%B9%81%E4%BD%93' style='color: #0078d7;'>https://greasyfork.org/zh-CN/scripts/520190-poe2-trade-%E7%B9%81%E4%BD%93</a>")
        er_download_link.setOpenExternalLinks(True)
        er_download_link.setStyleSheet("font-size: 22px; margin-bottom: 5px;")  # 增加字体大小到24px
        easy_refresh_layout.addWidget(er_download_link)
        
        # 不需要太多的弹性空间
        easy_refresh_layout.addStretch(1)
        
        # 添加BD监控选项卡
        bd_monitor_tab = QWidget()
        bd_monitor_layout = QVBoxLayout(bd_monitor_tab)
        bd_monitor_layout.setContentsMargins(20, 15, 20, 15)  # 减小边距
        bd_monitor_layout.setSpacing(5)  # 减小间距
        
        # 添加主选项卡
        tab_widget.clear()  # 清除所有现有标签
        tab_widget.addTab(price_tab, "价格监控")
        tab_widget.addTab(bd_monitor_tab, "BD监控")
        tab_widget.addTab(tools_tab, "A大补丁")
        tab_widget.addTab(easy_refresh_tab, "查价过滤汉化")
        
        parent_layout.addWidget(tab_widget)
    
    def update_price(self, currency, price):
        """更新货币价格并重新计算所有比例"""
        # 更新价格数据
        self.prices[currency] = price
        
        # 更新价格显示 - 保持4位小数，并恢复颜色
        price_label = getattr(self, f"{currency}_price_label", None)
        if price_label:
            price_label.setText(f"￥{price:.4f}/个")  # 恢复"/个"后缀
            price_label.setStyleSheet(f"color: {self.currency_colors[currency]};")  # 恢复颜色
        
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
            
            # 更新UI显示为"加载中..."
            for currency in self.currency_names:
                price_label = getattr(self, f"{currency}_price_label", None)
                if price_label:
                    price_label.setText("加载中...")  # 统一使用"加载中..."
                    price_label.setStyleSheet(f"color: #888888;")  # 设置为灰色
            
            # 创建新的价格爬取线程
            self.price_thread = PriceScraper()
            self.price_thread.price_updated.connect(self.update_price)
            
            # 添加完成信号处理
            self.price_thread.finished.connect(self.on_price_refresh_finished)
            
            # 启动线程
            self.price_thread.start()
        except Exception as e:
            # 恢复原来的价格显示
            self.update_all_price_displays()

    def on_price_refresh_finished(self):
        """价格刷新完成后的处理"""
        # 恢复价格标签的颜色
        for currency in self.currency_names:
            price_label = getattr(self, f"{currency}_price_label", None)
            if price_label:
                price_label.setStyleSheet(f"color: {self.currency_colors[currency]};")
        
        # 确保所有价格显示都已更新
        self.update_all_price_displays()

    def update_all_price_displays(self):
        """更新所有价格显示"""
        for currency in self.currency_names:
            price = self.prices[currency]
            price_label = getattr(self, f"{currency}_price_label", None)
            if price_label:
                price_label.setText(f"￥{price:.4f}/个")  # 恢复"/个"后缀
                price_label.setStyleSheet(f"color: {self.currency_colors[currency]};")
        
        # 重新计算价值和兑换比例
        self.calculate_value()
    
    def calculate_value(self):
        """计算货币价值"""
        try:
            # 获取输入值 - 使用float而不是int，以支持小数输入
            divine_amount = float(self.divine_amount.text() or "0")
            exalted_amount = float(self.exalted_amount.text() or "0")
            chaos_amount = float(self.chaos_amount.text() or "0")
            
            # 计算价值
            divine_value = divine_amount * self.prices["divine"]
            exalted_value = exalted_amount * self.prices["exalted"]
            chaos_value = chaos_amount * self.prices["chaos"]
            
            # 更新各个价值标签
            self.divine_value.setText(f"￥{divine_value:.2f}")
            self.exalted_value.setText(f"￥{exalted_value:.2f}")
            self.chaos_value.setText(f"￥{chaos_value:.2f}")
            
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
        if self.prices['divine'] <= 0 or self.prices['exalted'] <= 0 or self.prices['chaos'] <= 0:
            return
        
        try:
            # 获取用户输入的货币数量
            divine_amount = float(self.divine_amount.text() or "0")
            exalted_amount = float(self.exalted_amount.text() or "0")
            chaos_amount = float(self.chaos_amount.text() or "0")
            
            # 计算兑换比例
            # 神圣石兑换比例
            divine_to_exalted_ratio = self.prices["divine"] / self.prices["exalted"] if self.prices["exalted"] > 0 else 0
            divine_to_chaos_ratio = self.prices["divine"] / self.prices["chaos"] if self.prices["chaos"] > 0 else 0
            
            # 崇高石兑换比例
            exalted_to_divine_ratio = 1 / divine_to_exalted_ratio if divine_to_exalted_ratio > 0 else 0
            exalted_to_chaos_ratio = self.prices["exalted"] / self.prices["chaos"] if self.prices["chaos"] > 0 else 0
            
            # 混沌石兑换比例
            chaos_to_divine_ratio = 1 / divine_to_chaos_ratio if divine_to_chaos_ratio > 0 else 0
            chaos_to_exalted_ratio = 1 / exalted_to_chaos_ratio if exalted_to_chaos_ratio > 0 else 0
            
            # 更新兑换比例标签 - 使用HTML格式和颜色，简化显示
            divine_to_exalted_text = f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>{int(divine_amount * divine_to_exalted_ratio)}E</span>"
            divine_to_chaos_text = f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>{int(divine_amount * divine_to_chaos_ratio)}C</span>"
            
            self.divine_to_exalted.setText(divine_to_exalted_text)
            self.divine_to_chaos.setText(divine_to_chaos_text)
            
            exalted_to_divine_text = f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>{int(exalted_amount * exalted_to_divine_ratio)}D</span>"
            exalted_to_chaos_text = f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>{int(exalted_amount * exalted_to_chaos_ratio)}C</span>"
            
            self.exalted_to_divine.setText(exalted_to_divine_text)
            self.exalted_to_chaos.setText(exalted_to_chaos_text)
            
            chaos_to_divine_text = f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>{int(chaos_amount * chaos_to_divine_ratio)}D</span>"
            chaos_to_exalted_text = f"<span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>{int(chaos_amount * chaos_to_exalted_ratio)}E</span>"
            
            self.chaos_to_divine.setText(chaos_to_divine_text)
            self.chaos_to_exalted.setText(chaos_to_exalted_text)
        except Exception as e:
            print(f"更新兑换比例时出错: {e}")

    def eventFilter(self, obj, event):
        # 当点击主窗口其他区域时，清除所有输入框的焦点
        if event.type() == event.MouseButtonPress:
            focused_widget = QApplication.focusWidget()
            if focused_widget in [self.divine_amount, self.exalted_amount, self.chaos_amount]:
                focused_widget.clearFocus()
        
        return super().eventFilter(obj, event)

    def check_for_updates(self):
        # 如果正在更新，则跳过
        if self.is_updating:
            return
        
        try:
            # 从本地文件读取更新信息
            # 自动检查不显示状态对话框，直接进行检查
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 警告：这会降低安全性，仅在测试环境使用
            response = requests.get(self.update_url, headers=headers, timeout=5, verify=True)
            update_info = json.loads(response.text)
            
            latest_version = update_info.get("version")
            download_url = update_info.get("download_url")
            
            # 比较版本号
            version_comparison = self.compare_versions(latest_version, self.current_version)
            
            if version_comparison > 0:
                # 有新版本可用，显示更新提示
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setWindowTitle("发现新版本")
                msg_box.setText(f"发现新版本 {latest_version}，当前版本 {self.current_version}")
                msg_box.setInformativeText("是否立即更新？")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.Yes)
                
                if msg_box.exec_() == QMessageBox.Yes:
                    # 用户选择更新，下载并替换当前程序
                    self.download_and_replace(download_url)
            # 如果是最新版本，不显示任何提示
        
        except Exception as e:
            # 自动检查时出错，不显示提示，只记录日志
            print(f"自动检查更新时出错: {e}")

    def compare_versions(self, version1, version2):
        """比较两个版本号，返回 1 如果 version1 > version2，返回 -1 如果 version1 < version2，返回 0 如果相等"""
        v1_parts = list(map(int, version1.split('.')))
        v2_parts = list(map(int, version2.split('.')))
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        
        return 0

    def download_and_replace(self, download_url):
        try:
            # 设置更新标志
            self.is_updating = True
            
            # 获取当前程序路径和名称
            current_exe = sys.executable
            exe_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            
            # 从update.json获取新版本号
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            new_version = update_info.get("version", "unknown")
            
            # 使用新版本号创建目标文件名
            new_exe_name = f"POE2PriceAid_v{new_version}.exe"
            
            # 检查是否已经有版本号
            if not re.search(r'_v[0-9.]+\.exe$', exe_name):
                # 创建带版本号的文件名
                new_name = os.path.join(exe_dir, f"POE2PriceAid_v{self.current_version}.exe")
                
                # 复制当前程序到新名称
                try:
                    shutil.copy2(current_exe, new_name)
                    # 启动新程序
                    subprocess.Popen([new_name])
                    # 退出当前程序
                    sys.exit(0)
                except Exception as e:
                    pass
            
            # 创建进度对话框
            self.progress_dialog = QProgressDialog("正在下载更新...", "取消", 0, 100, self)
            self.progress_dialog.setWindowTitle("更新")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setAutoClose(True)
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
            QApplication.processEvents()
            
            # 在progress_dialog中设置取消按钮连接
            self.progress_dialog.canceled.connect(self.cancel_download)
            
            # 使用requests下载
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 使用stream=True来启用流式下载
            response = requests.get(download_url, headers=headers, stream=True, timeout=30)
            
            # 检查状态码
            if response.status_code != 200:
                self.progress_dialog.close()
                QMessageBox.critical(self, "下载失败", f"服务器返回错误状态码: {response.status_code}")
                self.is_updating = False
                return
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                self.progress_dialog.close()
                QMessageBox.critical(self, "下载失败", "无法获取文件大小信息，可能是下载链接无效")
                self.is_updating = False
                return
            
            # 下载并保存文件到临时文件名
            temp_file = os.path.join(exe_dir, "POE2PriceAid_new.exe")
            downloaded_size = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # 过滤掉保持连接活跃的空块
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # 更新进度
                        progress = int(downloaded_size * 100 / total_size)
                        self.progress_dialog.setValue(progress)
                        QApplication.processEvents()
                        
                    # 检查是否取消
                    if self.progress_dialog.wasCanceled():
                        f.close()
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        self.progress_dialog.close()
                        self.is_updating = False
                        return
            
            # 检查下载是否完成且文件大小正确
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                self.progress_dialog.close()
                QMessageBox.critical(self, "更新失败", "下载的文件为空或者不存在")
                self.is_updating = False
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return
            
            # 关闭进度对话框
            self.progress_dialog.close()
            
            # 创建更新批处理脚本
            updater_script = os.path.join(exe_dir, "update.bat")
            with open(updater_script, "w", encoding="gbk") as f:  # 使用GBK编码，适合中文Windows
                f.write(f"""@echo off
chcp 936 > nul
echo 正在更新POE2PriceAid...
echo 请等待程序关闭...

rem 等待原程序退出
timeout /t 5 /nobreak > nul

rem 替换文件 (使用强制删除)
echo 正在替换文件...
del /f /q "{current_exe}"
if exist "{current_exe}" (
  echo 无法删除原文件，请手动更新
  echo 源文件: {temp_file}
  echo 目标文件: {exe_dir}\\{new_exe_name}
  pause
  exit /b 1
)

rem 移动新文件到带版本号的文件名
move /y "{temp_file}" "{exe_dir}\\{new_exe_name}"
if errorlevel 1 (
  echo 移动文件失败，请手动更新
  pause
  exit /b 1
)

echo 更新成功！请手动启动程序。

rem 延迟删除自身
ping 127.0.0.1 -n 2 > nul
del "%~f0"
exit
""")
            
            # 提示用户更新，使用新版本号
            QMessageBox.information(self, "下载完成", f"更新已下载完成，程序将关闭并进行更新。\n更新完成后请手动启动 {new_exe_name}。")

            # 启动更新脚本并退出
            subprocess.Popen([updater_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
            QTimer.singleShot(500, self.close)
            QTimer.singleShot(1000, lambda: sys.exit(0))
        
        except Exception as e:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, "更新失败", f"更新过程中出错: {e}")

    def check_updates_manually(self):
        # 如果正在更新，则跳过
        if self.is_updating:
            QMessageBox.information(self, "正在更新", "更新已在进行中，请稍候...", QMessageBox.Ok)
            return
        
        try:
            # 创建可关闭的状态对话框
            status_dialog = QMessageBox(self)
            status_dialog.setWindowTitle("检查更新")
            status_dialog.setText("正在检查更新，请稍候...")
            status_dialog.setStandardButtons(QMessageBox.Cancel)
            status_dialog.setIcon(QMessageBox.Information)
            
            # 创建一个定时器，如果检查时间过长，允许用户取消
            check_timer = QTimer(self)
            check_timer.setSingleShot(True)
            check_timer.timeout.connect(lambda: self._perform_manual_update_check(status_dialog))
            check_timer.start(0)  # 立即开始检查
            
            # 显示对话框并等待用户响应
            result = status_dialog.exec_()
            
            # 如果用户取消，则停止检查
            if result == QMessageBox.Cancel:
                return
        
        except Exception as e:
            QMessageBox.critical(self, "检查更新", f"检查更新时出错: {e}", QMessageBox.Ok)

    def _perform_manual_update_check(self, status_dialog):
        try:
            # 发送请求获取最新版本信息
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 使用超时参数，避免长时间等待
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            
            # 关闭状态对话框
            status_dialog.done(0)
            
            latest_version = update_info.get("version")
            download_url = update_info.get("download_url")
            
            # 比较版本号
            version_comparison = self.compare_versions(latest_version, self.current_version)
            
            if version_comparison > 0:
                # 有新版本可用，显示更新提示
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setWindowTitle("发现新版本")
                msg_box.setText(f"发现新版本 {latest_version}，当前版本 {self.current_version}")
                msg_box.setInformativeText("是否立即更新？")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.Yes)
                
                if msg_box.exec_() == QMessageBox.Yes:
                    # 用户选择更新，下载并替换当前程序
                    self.download_and_replace(download_url)
            else:
                # 已经是最新版本，显示提示
                QMessageBox.information(self, "检查更新", "当前已是最新版本。", QMessageBox.Ok)
        
        except requests.exceptions.Timeout:
            # 处理请求超时
            status_dialog.done(0)  # 关闭状态对话框
            QMessageBox.warning(self, "检查更新", "检查更新超时，请稍后再试。", QMessageBox.Ok)
        except Exception as e:
            # 处理其他错误
            status_dialog.done(0)  # 关闭状态对话框
            QMessageBox.critical(self, "检查更新", f"检查更新时出错: {e}", QMessageBox.Ok)

    def create_desktop_shortcut(self):
        try:
            # 获取当前程序路径
            current_exe = sys.executable
            if getattr(sys, 'frozen', False):
                # 如果是打包后的程序
                application_path = os.path.dirname(current_exe)
            else:
                # 如果是源代码运行
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            # 启动器路径
            launcher_path = os.path.join(application_path, "launcher.bat")
            
            # 如果启动器不存在，创建它
            if not os.path.exists(launcher_path):
                with open(launcher_path, "w") as f:
                    f.write(f"""@echo off
start "" "{current_exe}"
exit
""")
            
            # 获取桌面路径
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            
            # 创建快捷方式
            shortcut_path = os.path.join(desktop_path, "POE2PriceAid.lnk")
            self.create_shortcut(launcher_path, shortcut_path, "POE2PriceAid", application_path)
            
            return True
        except Exception as e:
            return False

    def cancel_download(self):
        self.download_canceled = True
        self.is_updating = False

    def on_divine_amount_changed(self, text):
        """处理神圣石数量变化"""
        try:
            if not text:
                return
            
            # 计算价值
            amount = float(text)
            value = amount * self.prices["divine"]
            
            # 更新价值标签
            self.divine_value.setText(f"￥{value:.2f}")
            
            # 直接更新兑换比例
            self.update_exchange_rates()
        except ValueError as e:
            pass

    def on_exalted_amount_changed(self, text):
        """处理崇高石数量变化"""
        try:
            if not text:
                return
            
            # 计算价值
            amount = float(text)
            value = amount * self.prices["exalted"]
            
            # 更新价值标签
            self.exalted_value.setText(f"￥{value:.2f}")
            
            # 直接更新兑换比例
            self.update_exchange_rates()
        except ValueError as e:
            pass

    def on_chaos_amount_changed(self, text):
        """处理混沌石数量变化"""
        try:
            if not text:
                return
            
            # 计算价值
            amount = float(text)
            value = amount * self.prices["chaos"]
            
            # 更新价值标签
            self.chaos_value.setText(f"￥{value:.2f}")
            
            # 直接更新兑换比例
            self.update_exchange_rates()
        except ValueError as e:
            pass

    def closeEvent(self, event):
        # 停止所有线程
        if hasattr(self, 'price_thread') and self.price_thread.isRunning():
            self.price_thread.terminate()
            self.price_thread.wait()
        
        # 停止所有定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        # 调用父类方法
        super().closeEvent(event)

    def clear_app_cache(self):
        """清理应用程序缓存，确保字体大小一致"""
        try:
            # 获取应用程序缓存目录
            cache_dir = None
            
            # 根据操作系统确定缓存目录
            if os.name == 'nt':  # Windows
                cache_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'POE2PriceAid', 'cache')
            else:  # Linux/Mac
                cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'POE2PriceAid')
            
            # 如果缓存目录存在，尝试清理
            if cache_dir and os.path.exists(cache_dir):
                # 遍历缓存目录中的所有文件和子目录
                for root, dirs, files in os.walk(cache_dir, topdown=False):
                    # 删除所有文件
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                    
                    # 删除所有子目录
                    for dir in dirs:
                        try:
                            shutil.rmtree(os.path.join(root, dir), ignore_errors=True)
                        except:
                            pass
            
            # 设置统一的字体大小
            font = self.font()
            font.setPointSize(16)  # 将14px调整为16px，更适合大多数显示器
            self.setFont(font)
            
            # 设置应用程序级别的字体
            app = QApplication.instance()
            if app:
                app.setFont(font)
            
            # 强制应用DPI设置
            if hasattr(QApplication, 'setAttribute'):
                QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
                QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            
        except Exception as e:
            # 出错时不影响程序运行，只是记录错误
            print(f"清理缓存时出错: {e}")

if __name__ == "__main__":
    # 在创建QApplication之前设置环境变量
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"  # 禁用自动缩放
    os.environ["QT_FONT_DPI"] = "96"  # 设置固定DPI值，确保字体大小一致
    
    # 设置环境变量，确保PyInstaller能找到临时目录
    if getattr(sys, 'frozen', False):
        os.environ['PYI_APPLICATION_HOME_DIR'] = os.path.dirname(sys.executable)
    
    app = QApplication(sys.argv)
    
    # 检测屏幕DPI并调整字体大小
    screen = app.primaryScreen()
    dpi = screen.logicalDotsPerInch()
    
    # 根据DPI调整字体大小
    base_size = 16  # 基础字体大小
    if dpi > 120:
        # 高DPI屏幕
        font_size = base_size - 1  # 略小一点
    elif dpi < 96:
        # 低DPI屏幕
        font_size = base_size + 1  # 略大一点
    else:
        # 标准DPI屏幕
        font_size = base_size
    
    # 强制设置应用程序字体
    font = QFont("Microsoft YaHei")
    font.setPixelSize(font_size)
    app.setFont(font)
    
    # 同时设置环境变量
    os.environ["QT_FONT_DPI"] = str(int(dpi))
    
    # 在创建任何窗口前设置应用程序图标
    if getattr(sys, 'frozen', False):
        # 如果是打包后的程序
        base_path = sys._MEIPASS
    else:
        # 如果是源代码运行
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    icon_path = os.path.join(base_path, 'app.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 