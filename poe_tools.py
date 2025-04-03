import sys
import requests
from bs4 import BeautifulSoup
import re
import webbrowser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox,
                            QGridLayout, QFrame, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
                            QMessageBox, QProgressDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette
import json
import os
import time
from datetime import datetime
import subprocess
import tempfile
import urllib.request
import shutil

class PriceScraper(QThread):
    price_updated = pyqtSignal(str, float)
    
    def __init__(self):
        super().__init__()
        self.urls = {
            "divine": "https://www.dd373.com/s-3hcpqw-c-8rknmp-bwgvrk-nxspw7.html",
            "exalted": "https://www.dd373.com/s-3hcpqw-c-tqcbc6-bwgvrk-nxspw7.html",
            "chaos": "https://www.dd373.com/s-3hcpqw-c-henjrw-bwgvrk-nxspw7.html"
        }
        
    def run(self):
        for currency, url in self.urls.items():
            price = self.get_price(url)
            self.price_updated.emit(currency, price)
    
    def get_price(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种选择器
            price_element = soup.select_one('p.font12.color666.m-t5')
            if not price_element:
                price_element = soup.select_one('.good-list-box div:first-child .p-r66 p.font12')
            
            if price_element:
                price_text = price_element.text.strip()
                match = re.search(r'(\d+\.\d+)', price_text)
                if match:
                    return float(match.group(1))
        except Exception as e:
            print(f"Error: {e}")
        
        # 价格获取失败时返回0
        return 0.0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 版本信息
        self.current_version = "1.0.0"  # 确保在使用之前初始化
        self.update_url = "https://raw.githubusercontent.com/mexiaow/poe_tools/refs/heads/main/update.json"
        
        # 在窗口标题中添加版本号
        self.setWindowTitle(f"POE2PriceAid v{self.current_version}")
        self.setMinimumSize(900, 350)  # 调整宽度到900
        
        # 设置深色主题
        self.setup_dark_theme()
        
        # 价格数据
        self.prices = {"divine": 0.00, "exalted": 0.00, "chaos": 0.00}
        self.currency_names = {"divine": "神圣石", "exalted": "崇高石", "chaos": "混沌石"}
        self.currency_colors = {"divine": "#FFD700", "exalted": "#00BFFF", "chaos": "#FF6347"}
        
        
        
        # 创建UI
        self.init_ui()
        
        # 启动价格更新线程
        self.price_thread = PriceScraper()
        self.price_thread.price_updated.connect(self.update_price)
        self.price_thread.start()
        
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
            }
            QTabWidget::pane {
                border: none;
                background-color: #1E1E1E;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #2D2D2D;
                color: #CCCCCC;
                padding: 10px 20px;
                margin-right: 2px;
                border: none;
                border-radius: 5px 5px 0 0;
            }
            QTabBar::tab:selected {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border-bottom: 2px solid #0078D7;
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
        
        # 顶部标题和按钮
        header_layout = QHBoxLayout()
        
        # 左侧标题
        title_label = QLabel("POE2PriceAid")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # 添加弹性空间，将按钮推到右侧
        header_layout.addStretch()
        
        # 右侧按钮组 - 使用水平布局将按钮放在一起
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)  # 设置按钮之间的间距
        
        # 刷新价格按钮
        refresh_button = QPushButton("刷新价格")
        refresh_button.clicked.connect(self.refresh_prices)
        buttons_layout.addWidget(refresh_button)
        
        # 检查更新按钮
        check_update_button = QPushButton("检查更新")
        check_update_button.clicked.connect(self.check_updates_manually)
        buttons_layout.addWidget(check_update_button)
        
        # 将按钮组添加到标题栏
        header_layout.addLayout(buttons_layout)
        
        main_layout.addLayout(header_layout)
        
        # 选项卡
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("QTabBar::tab { padding: 10px 20px; }")
        
        # 价格监控选项卡
        price_tab = QWidget()
        price_layout = QVBoxLayout(price_tab)
        price_layout.setContentsMargins(0, 10, 0, 0)
        
        # 价值计算面板（整合实时价格和兑换比例）
        value_group = QGroupBox("价格与兑换")
        value_layout = QGridLayout(value_group)
        value_layout.setColumnStretch(2, 1)  # 让价值列有更多空间
        
        # 神圣石输入 - 修改标签格式
        divine_label = QLabel("神圣石/个:")
        divine_label.setStyleSheet(f"color: {self.currency_colors['divine']}; font-weight: bold;")
        value_layout.addWidget(divine_label, 0, 0)
        
        # 神圣石实时价格 - 添加颜色
        self.divine_price_label = QLabel("加载中...")
        self.divine_price_label.setStyleSheet(f"color: {self.currency_colors['divine']};")
        value_layout.addWidget(self.divine_price_label, 0, 1)
        
        self.divine_amount = QLineEdit("100")
        self.divine_amount.textChanged.connect(self.calculate_value)
        self.divine_amount.setFocusPolicy(Qt.ClickFocus)
        value_layout.addWidget(self.divine_amount, 0, 2)
        
        self.divine_value = QLabel(f"￥{100 * self.prices['divine']:.2f}")
        self.divine_value.setStyleSheet("color: #00FF00; font-weight: bold;")
        value_layout.addWidget(self.divine_value, 0, 3)
        
        # 神圣石兑换比例
        self.divine_to_exalted = QLabel()
        self.divine_to_chaos = QLabel()
        self.divine_to_exalted.setText(f"<span style='color:{self.currency_colors['divine']}'>100D</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>0E</span>")
        self.divine_to_chaos.setText(f"<span style='color:{self.currency_colors['divine']}'>100D</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>0C</span>")
        value_layout.addWidget(self.divine_to_exalted, 0, 4)
        value_layout.addWidget(self.divine_to_chaos, 0, 5)
        
        # 崇高石输入 - 修改标签格式
        exalted_label = QLabel("崇高石/个:")
        exalted_label.setStyleSheet(f"color: {self.currency_colors['exalted']}; font-weight: bold;")
        value_layout.addWidget(exalted_label, 1, 0)
        
        # 崇高石实时价格 - 添加颜色
        self.exalted_price_label = QLabel("加载中...")
        self.exalted_price_label.setStyleSheet(f"color: {self.currency_colors['exalted']};")
        value_layout.addWidget(self.exalted_price_label, 1, 1)
        
        self.exalted_amount = QLineEdit("100")
        self.exalted_amount.textChanged.connect(self.calculate_value)
        self.exalted_amount.setFocusPolicy(Qt.ClickFocus)
        value_layout.addWidget(self.exalted_amount, 1, 2)
        
        self.exalted_value = QLabel(f"￥{100 * self.prices['exalted']:.2f}")
        self.exalted_value.setStyleSheet("color: #00FF00; font-weight: bold;")
        value_layout.addWidget(self.exalted_value, 1, 3)
        
        # 崇高石兑换比例
        self.exalted_to_divine = QLabel()
        self.exalted_to_chaos = QLabel()
        self.exalted_to_divine.setText(f"<span style='color:{self.currency_colors['exalted']}'>100E</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>0D</span>")
        self.exalted_to_chaos.setText(f"<span style='color:{self.currency_colors['exalted']}'>100E</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>0C</span>")
        value_layout.addWidget(self.exalted_to_divine, 1, 4)
        value_layout.addWidget(self.exalted_to_chaos, 1, 5)
        
        # 混沌石输入 - 修改标签格式
        chaos_label = QLabel("混沌石/个:")
        chaos_label.setStyleSheet(f"color: {self.currency_colors['chaos']}; font-weight: bold;")
        value_layout.addWidget(chaos_label, 2, 0)
        
        # 混沌石实时价格 - 添加颜色
        self.chaos_price_label = QLabel("加载中...")
        self.chaos_price_label.setStyleSheet(f"color: {self.currency_colors['chaos']};")
        value_layout.addWidget(self.chaos_price_label, 2, 1)
        
        self.chaos_amount = QLineEdit("100")
        self.chaos_amount.textChanged.connect(self.calculate_value)
        self.chaos_amount.setFocusPolicy(Qt.ClickFocus)
        value_layout.addWidget(self.chaos_amount, 2, 2)
        
        self.chaos_value = QLabel(f"￥{100 * self.prices['chaos']:.2f}")
        self.chaos_value.setStyleSheet("color: #00FF00; font-weight: bold;")
        value_layout.addWidget(self.chaos_value, 2, 3)
        
        # 混沌石兑换比例
        self.chaos_to_divine = QLabel()
        self.chaos_to_exalted = QLabel()
        self.chaos_to_divine.setText(f"<span style='color:{self.currency_colors['chaos']}'>100C</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>0D</span>")
        self.chaos_to_exalted.setText(f"<span style='color:{self.currency_colors['chaos']}'>100C</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>0E</span>")
        value_layout.addWidget(self.chaos_to_divine, 2, 4)
        value_layout.addWidget(self.chaos_to_exalted, 2, 5)
        
        price_layout.addWidget(value_group)
        
        # 快捷功能选项卡
        tools_tab = QWidget()
        tools_layout = QVBoxLayout(tools_tab)
        tools_layout.setContentsMargins(0, 10, 0, 0)
        
        tools_group = QGroupBox("常用工具")
        tools_group_layout = QVBoxLayout(tools_group)
        
        # 使用更好看的按钮
        ad_patch_button = QPushButton("A大补丁")
        ad_patch_button.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        ad_patch_button.clicked.connect(lambda: webbrowser.open("https://www.caimogu.cc/post/1615417.html"))
        
        easy_refresh_button = QPushButton("易刷")
        easy_refresh_button.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        easy_refresh_button.clicked.connect(lambda: webbrowser.open("https://www.caimogu.cc/post/1621584.html"))
        
        tools_group_layout.addWidget(ad_patch_button)
        tools_group_layout.addWidget(easy_refresh_button)
        tools_group_layout.addStretch()
        
        tools_layout.addWidget(tools_group)
        tools_layout.addStretch()
        
        # 添加选项卡
        tab_widget.addTab(price_tab, "价格监控")
        tab_widget.addTab(tools_tab, "快捷功能")
        
        main_layout.addWidget(tab_widget)
        
        self.setCentralWidget(main_widget)
        
        # 添加事件过滤器，处理点击其他区域时清除焦点
        main_widget.installEventFilter(self)
        
        # 初始计算
        self.calculate_value()
    
    def update_price(self, currency, price):
        self.prices[currency] = price
        
        # 更新实时价格标签 - 保持颜色与货币一致
        if currency == "divine":
            self.divine_price_label.setText(f"￥{price:.4f}")
            self.divine_price_label.setStyleSheet(f"color: {self.currency_colors['divine']};")
        elif currency == "exalted":
            self.exalted_price_label.setText(f"￥{price:.4f}")
            self.exalted_price_label.setStyleSheet(f"color: {self.currency_colors['exalted']};")
        elif currency == "chaos":
            self.chaos_price_label.setText(f"￥{price:.4f}")
            self.chaos_price_label.setStyleSheet(f"color: {self.currency_colors['chaos']};")
        
        # 更新价值计算
        self.calculate_value()
    
    def refresh_prices(self):
        # 重置为加载状态 - 保持颜色与货币一致但透明度降低
        self.divine_price_label.setText("加载中...")
        self.divine_price_label.setStyleSheet(f"color: {self.currency_colors['divine']}; opacity: 0.5;")
        self.exalted_price_label.setText("加载中...")
        self.exalted_price_label.setStyleSheet(f"color: {self.currency_colors['exalted']}; opacity: 0.5;")
        self.chaos_price_label.setText("加载中...")
        self.chaos_price_label.setStyleSheet(f"color: {self.currency_colors['chaos']}; opacity: 0.5;")
        
        if not self.price_thread.isRunning():
            self.price_thread = PriceScraper()
            self.price_thread.price_updated.connect(self.update_price)
            self.price_thread.start()
    
    def calculate_value(self):
        try:
            divine_amount = int(self.divine_amount.text() or "0")
            exalted_amount = int(self.exalted_amount.text() or "0")
            chaos_amount = int(self.chaos_amount.text() or "0")
            
            divine_value = divine_amount * self.prices["divine"]
            exalted_value = exalted_amount * self.prices["exalted"]
            chaos_value = chaos_amount * self.prices["chaos"]
            
            # 更新各个价值标签
            self.divine_value.setText(f"￥{divine_value:.2f}")
            self.exalted_value.setText(f"￥{exalted_value:.2f}")
            self.chaos_value.setText(f"￥{chaos_value:.2f}")
            
            # 同时更新兑换比例
            self.update_exchange_ratios()
        except ValueError:
            pass

    def update_exchange_ratios(self):
        try:
            # 获取各货币数量
            divine_amount = int(self.divine_amount.text() or "0")
            exalted_amount = int(self.exalted_amount.text() or "0")
            chaos_amount = int(self.chaos_amount.text() or "0")
            
            # 计算兑换比例
            # 神圣石兑换比例
            divine_to_exalted_ratio = self.prices["divine"] / self.prices["exalted"] if self.prices["exalted"] > 0 else 0
            divine_to_chaos_ratio = self.prices["divine"] / self.prices["chaos"] if self.prices["chaos"] > 0 else 0
            
            # 崇高石兑换比例
            exalted_to_divine_ratio = self.prices["exalted"] / self.prices["divine"] if self.prices["divine"] > 0 else 0
            exalted_to_chaos_ratio = self.prices["exalted"] / self.prices["chaos"] if self.prices["chaos"] > 0 else 0
            
            # 混沌石兑换比例
            chaos_to_divine_ratio = self.prices["chaos"] / self.prices["divine"] if self.prices["divine"] > 0 else 0
            chaos_to_exalted_ratio = self.prices["chaos"] / self.prices["exalted"] if self.prices["exalted"] > 0 else 0
            
            # 更新兑换比例标签 - 使用HTML格式和颜色
            self.divine_to_exalted.setText(f"<span style='color:{self.currency_colors['divine']}'>{divine_amount}D</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>{int(divine_amount * divine_to_exalted_ratio)}E</span>")
            self.divine_to_chaos.setText(f"<span style='color:{self.currency_colors['divine']}'>{divine_amount}D</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>{int(divine_amount * divine_to_chaos_ratio)}C</span>")
            
            self.exalted_to_divine.setText(f"<span style='color:{self.currency_colors['exalted']}'>{exalted_amount}E</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>{int(exalted_amount * exalted_to_divine_ratio)}D</span>")
            self.exalted_to_chaos.setText(f"<span style='color:{self.currency_colors['exalted']}'>{exalted_amount}E</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['chaos']}'>{int(exalted_amount * exalted_to_chaos_ratio)}C</span>")
            
            self.chaos_to_divine.setText(f"<span style='color:{self.currency_colors['chaos']}'>{chaos_amount}C</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['divine']}'>{int(chaos_amount * chaos_to_divine_ratio)}D</span>")
            self.chaos_to_exalted.setText(f"<span style='color:{self.currency_colors['chaos']}'>{chaos_amount}C</span><span style='color:white'>≈</span><span style='color:{self.currency_colors['exalted']}'>{int(chaos_amount * chaos_to_exalted_ratio)}E</span>")
            
        except ValueError:
            pass
        except ZeroDivisionError:
            pass

    def eventFilter(self, obj, event):
        # 当点击主窗口其他区域时，清除所有输入框的焦点
        if event.type() == event.MouseButtonPress:
            focused_widget = QApplication.focusWidget()
            if focused_widget in [self.divine_amount, self.exalted_amount, self.chaos_amount]:
                focused_widget.clearFocus()
        
        return super().eventFilter(obj, event)

    def check_for_updates(self):
        try:
            # 显示检查更新的状态
            status_dialog = QMessageBox(self)
            status_dialog.setWindowTitle("检查更新")
            status_dialog.setText("正在检查更新，请稍候...")
            status_dialog.setStandardButtons(QMessageBox.NoButton)
            status_dialog.setIcon(QMessageBox.Information)
            
            # 使用QTimer延迟显示状态对话框，避免闪烁
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(status_dialog.show)
            timer.start(500)  # 如果500毫秒内完成检查，则不显示对话框
            
            # 直接获取最新版本信息
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 使用超时参数，避免长时间等待
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            
            # 关闭状态对话框
            timer.stop()
            status_dialog.close()
            
            latest_version = update_info.get("version")
            download_url = update_info.get("download_url")
            
            # 比较版本号
            if self.compare_versions(latest_version, self.current_version) > 0:
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
        
        except requests.exceptions.Timeout:
            # 处理请求超时
            print("检查更新超时")
        except Exception as e:
            print(f"检查更新时出错: {e}")
    
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
            # 创建进度对话框
            progress_dialog = QProgressDialog("准备下载更新...", "取消", 0, 100, self)
            progress_dialog.setWindowTitle("下载更新")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setAutoClose(True)
            progress_dialog.setMinimumDuration(0)  # 立即显示，不等待
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()  # 确保对话框立即显示
            
            # 获取当前程序路径
            current_exe = sys.executable
            if getattr(sys, 'frozen', False):
                # 如果是打包后的程序
                application_path = os.path.dirname(current_exe)
            else:
                # 如果是源代码运行
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            # 创建临时目录 - 避免路径中有空格
            temp_dir = tempfile.mkdtemp(prefix="poe2update_")
            temp_file = os.path.join(temp_dir, "POE2PriceAid_new.exe")
            
            # 更新进度对话框文本
            progress_dialog.setLabelText("正在下载更新...")
            QApplication.processEvents()
            
            # 下载新版本
            def update_progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                progress_dialog.setValue(min(percent, 100))
                QApplication.processEvents()
                if progress_dialog.wasCanceled():
                    raise Exception("下载被取消")
            
            # 下载可执行文件
            urllib.request.urlretrieve(download_url, temp_file, reporthook=update_progress)
            
            # 下载完成后关闭进度对话框
            progress_dialog.close()
            
            # 创建更新批处理文件 - 简化版本，直接替换可执行文件
            update_script = os.path.join(temp_dir, "update.bat")
            with open(update_script, "w") as f:
                f.write(f"""@echo off
echo 正在更新，请稍候...
timeout /t 2 /nobreak > nul
taskkill /F /IM POE2PriceAid.exe > nul 2>&1

REM 替换可执行文件
copy /Y "{temp_file}" "{current_exe}" >nul

REM 启动新版本
start "" "{current_exe}"

REM 清理临时文件
rmdir /S /Q "{temp_dir}" >nul

exit
""")
            
            # 确认更新
            reply = QMessageBox.question(self, "确认更新", 
                                        "程序将关闭并安装更新，完成后会自动重启。是否继续？",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                # 执行更新脚本
                subprocess.Popen([update_script], shell=True)
                self.close()
                sys.exit(0)
        
        except Exception as e:
            QMessageBox.critical(self, "更新失败", f"更新过程中出错: {e}")

    def check_updates_manually(self):
        try:
            # 显示检查更新的状态
            status_dialog = QMessageBox(self)
            status_dialog.setWindowTitle("检查更新")
            status_dialog.setText("正在检查更新，请稍候...")
            status_dialog.setStandardButtons(QMessageBox.NoButton)
            status_dialog.setIcon(QMessageBox.Information)
            status_dialog.show()
            QApplication.processEvents()  # 确保对话框立即显示
            
            # 发送请求获取最新版本信息
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 使用超时参数，避免长时间等待
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            
            # 关闭状态对话框
            status_dialog.close()
            
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
            QMessageBox.warning(self, "检查更新", "检查更新超时，请稍后再试。", QMessageBox.Ok)
        except Exception as e:
            # 处理其他错误
            QMessageBox.critical(self, "检查更新", f"检查更新时出错: {e}", QMessageBox.Ok)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 