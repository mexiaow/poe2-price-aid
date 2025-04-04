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
from PyQt5.QtGui import QFont, QColor, QPalette
import json
import os
import time
from datetime import datetime
import subprocess
import tempfile
import urllib.request
import shutil

# ???????????Python DLL
if getattr(sys, 'frozen', False):
    # ??????????DLL????
    os.environ['PATH'] = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)) + os.pathsep + os.environ['PATH']
    
    # ??ctypes???python DLL
    import ctypes
    try:
        dll_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'python310.dll')
        if os.path.exists(dll_path):
            ctypes.CDLL(dll_path)
            print(f"???? Python DLL: {dll_path}")
    except Exception as e:
        print(f"?? Python DLL ??: {e}")

    # ???????
    print(f"??????: {sys.executable}")
    print(f"????: {getattr(sys, '_MEIPASS', 'Not found')}")
    print(f"??????PATH: {os.environ['PATH']}")
    
    # ??_MEIPASS????
    if hasattr(sys, '_MEIPASS'):
        print("????????:")
        for root, dirs, files in os.walk(sys._MEIPASS):
            for file in files:
                if file.endswith('.dll'):
                    print(f" - {os.path.join(root, file)}")

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
            
            print(f"??URL: {url}")
            
            # ?????????CSS???
            css_selector = "div.good-list-box > div:nth-child(1) > div.width233.p-l30 > div.p-r66 > p.font12.color666.m-t5"
            price_element = soup.select_one(css_selector)
            
            # ?????????????????????
            if not price_element:
                price_element = soup.select_one('div.good-list-box div:first-child div.p-r66 p.font12.color666.m-t5')
            
            # ???????????????
            if not price_element:
            price_element = soup.select_one('p.font12.color666.m-t5')
            
            if not price_element:
                price_element = soup.select_one('.good-list-box div:first-child .p-r66 p.font12')
            
            # ???????????XPath?????
            if not price_element:
                price_element = soup.select_one('div.main div.goods-list-content div div.sell-goods div.good-list-box div:first-child div.width233.p-l30 div.p-r66 p.font12.color666.m-t5')
            
            if price_element:
                price_text = price_element.text.strip()
                print(f"??????: {price_text}")
                match = re.search(r'(\d+\.\d+)', price_text)
                if match:
                    price = float(match.group(1))
                    print(f"????: {price}")
                    return price
                else:
                    print(f"??????????: {price_text}")
            else:
                # ?????????????????????
                all_price_elements = soup.select('p.font12.color666')
                for element in all_price_elements:
                    price_text = element.text.strip()
                    print(f"????????: {price_text}")
                    match = re.search(r'(\d+\.\d+)', price_text)
                    if match:
                        price = float(match.group(1))
                        print(f"??????????: {price}")
                        return price
                
                print("????????????????")
                # ????????????????
                all_elements = soup.find_all(['p', 'div', 'span'])
                for element in all_elements:
                    if '?/?' in element.text or '?' in element.text:
                        price_text = element.text.strip()
                        match = re.search(r'(\d+\.\d+)', price_text)
                        if match:
                            price = float(match.group(1))
                            print(f"??????????: {price}")
                            return price
                            
                print("?????????")
        except Exception as e:
            print(f"??????: {e}")
            import traceback
            traceback.print_exc()
        
        # ?????????0
        print(f"???????URL: {url}")
        return 0.0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ????
        self.current_version = "1.0.2"  # ??????????
        self.update_url = "https://raw.githubusercontent.com/mexiaow/poe_tools/refs/heads/main/update.json"
        
        # ?????????????
        self.is_updating = False
        
        # ?????????????
        self.download_canceled = False
        
        # ???????????
        self.setWindowTitle(f"POE2PriceAid v{self.current_version}")
        self.setMinimumSize(900, 350)  # ?????900
        
        # ??????
        self.setup_dark_theme()
        
        # ????
        self.prices = {"divine": 0.00, "exalted": 0.00, "chaos": 0.00}
        self.currency_names = {"divine": "???", "exalted": "???", "chaos": "???"}
        self.currency_colors = {"divine": "#FFD700", "exalted": "#00BFFF", "chaos": "#FF6347"}
        
        # ??UI
        self.init_ui()
        
        # ????????
        self.price_thread = PriceScraper()
        self.price_thread.price_updated.connect(self.update_price)
        self.price_thread.start()
        
        # ????????
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start(3600000)  # ????????? (3600000??)
        
        # ???????
        QTimer.singleShot(5000, self.check_for_updates)  # ??5??????
    
    def setup_dark_theme(self):
        # ??????
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
        
        # ????? - ????????????????????
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: "Microsoft YaHei", "????", sans-serif;
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
        
        # ???????
        header_layout = QHBoxLayout()
        
        # ????
        title_label = QLabel("POE2PriceAid")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # ??????????????
        header_layout.addStretch()
        
        # ????? - ?????????????
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)  # ?????????
        
        # ??????
        refresh_button = QPushButton("????")
        refresh_button.clicked.connect(self.refresh_prices)
        buttons_layout.addWidget(refresh_button)
        
        # ??????
        check_update_button = QPushButton("????")
        check_update_button.clicked.connect(self.check_updates_manually)
        buttons_layout.addWidget(check_update_button)
        
        # ??????????
        header_layout.addLayout(buttons_layout)
        
        main_layout.addLayout(header_layout)
        
        # ???
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("QTabBar::tab { padding: 10px 20px; }")
        
        # ???????
        price_tab = QWidget()
        price_layout = QVBoxLayout(price_tab)
        price_layout.setContentsMargins(0, 10, 0, 0)
        
        # ???????????????????
        value_group = QGroupBox("?????")
        value_layout = QGridLayout(value_group)
        value_layout.setColumnStretch(2, 1)  # ?????????
        
        # ????? - ??????
        divine_label = QLabel("???/?:")
        divine_label.setStyleSheet(f"color: {self.currency_colors['divine']}; font-weight: bold;")
        value_layout.addWidget(divine_label, 0, 0)
        
        # ??????? - ????
        self.divine_price_label = QLabel("???...")
        self.divine_price_label.setStyleSheet(f"color: {self.currency_colors['divine']};")
        value_layout.addWidget(self.divine_price_label, 0, 1)
        
        self.divine_amount = QLineEdit("100")
        self.divine_amount.textChanged.connect(self.calculate_value)
        self.divine_amount.setFocusPolicy(Qt.ClickFocus)
        value_layout.addWidget(self.divine_amount, 0, 2)
        
        self.divine_value = QLabel(f"?{100 * self.prices['divine']:.2f}")
        self.divine_value.setStyleSheet("color: #00FF00; font-weight: bold;")
        value_layout.addWidget(self.divine_value, 0, 3)
        
        # ???????
        self.divine_to_exalted = QLabel()
        self.divine_to_chaos = QLabel()
        self.divine_to_exalted.setText(f"<span style='color:{self.currency_colors['divine']}'>100D</span><span style='color:white'>?</span><span style='color:{self.currency_colors['exalted']}'>0E</span>")
        self.divine_to_chaos.setText(f"<span style='color:{self.currency_colors['divine']}'>100D</span><span style='color:white'>?</span><span style='color:{self.currency_colors['chaos']}'>0C</span>")
        value_layout.addWidget(self.divine_to_exalted, 0, 4)
        value_layout.addWidget(self.divine_to_chaos, 0, 5)
        
        # ????? - ??????
        exalted_label = QLabel("???/?:")
        exalted_label.setStyleSheet(f"color: {self.currency_colors['exalted']}; font-weight: bold;")
        value_layout.addWidget(exalted_label, 1, 0)
        
        # ??????? - ????
        self.exalted_price_label = QLabel("???...")
        self.exalted_price_label.setStyleSheet(f"color: {self.currency_colors['exalted']};")
        value_layout.addWidget(self.exalted_price_label, 1, 1)
        
        self.exalted_amount = QLineEdit("100")
        self.exalted_amount.textChanged.connect(self.calculate_value)
        self.exalted_amount.setFocusPolicy(Qt.ClickFocus)
        value_layout.addWidget(self.exalted_amount, 1, 2)
        
        self.exalted_value = QLabel(f"?{100 * self.prices['exalted']:.2f}")
        self.exalted_value.setStyleSheet("color: #00FF00; font-weight: bold;")
        value_layout.addWidget(self.exalted_value, 1, 3)
        
        # ???????
        self.exalted_to_divine = QLabel()
        self.exalted_to_chaos = QLabel()
        self.exalted_to_divine.setText(f"<span style='color:{self.currency_colors['exalted']}'>100E</span><span style='color:white'>?</span><span style='color:{self.currency_colors['divine']}'>0D</span>")
        self.exalted_to_chaos.setText(f"<span style='color:{self.currency_colors['exalted']}'>100E</span><span style='color:white'>?</span><span style='color:{self.currency_colors['chaos']}'>0C</span>")
        value_layout.addWidget(self.exalted_to_divine, 1, 4)
        value_layout.addWidget(self.exalted_to_chaos, 1, 5)
        
        # ????? - ??????
        chaos_label = QLabel("???/?:")
        chaos_label.setStyleSheet(f"color: {self.currency_colors['chaos']}; font-weight: bold;")
        value_layout.addWidget(chaos_label, 2, 0)
        
        # ??????? - ????
        self.chaos_price_label = QLabel("???...")
        self.chaos_price_label.setStyleSheet(f"color: {self.currency_colors['chaos']};")
        value_layout.addWidget(self.chaos_price_label, 2, 1)
        
        self.chaos_amount = QLineEdit("100")
        self.chaos_amount.textChanged.connect(self.calculate_value)
        self.chaos_amount.setFocusPolicy(Qt.ClickFocus)
        value_layout.addWidget(self.chaos_amount, 2, 2)
        
        self.chaos_value = QLabel(f"?{100 * self.prices['chaos']:.2f}")
        self.chaos_value.setStyleSheet("color: #00FF00; font-weight: bold;")
        value_layout.addWidget(self.chaos_value, 2, 3)
        
        # ???????
        self.chaos_to_divine = QLabel()
        self.chaos_to_exalted = QLabel()
        self.chaos_to_divine.setText(f"<span style='color:{self.currency_colors['chaos']}'>100C</span><span style='color:white'>?</span><span style='color:{self.currency_colors['divine']}'>0D</span>")
        self.chaos_to_exalted.setText(f"<span style='color:{self.currency_colors['chaos']}'>100C</span><span style='color:white'>?</span><span style='color:{self.currency_colors['exalted']}'>0E</span>")
        value_layout.addWidget(self.chaos_to_divine, 2, 4)
        value_layout.addWidget(self.chaos_to_exalted, 2, 5)
        
        price_layout.addWidget(value_group)
        
        # ???????
        tools_tab = QWidget()
        tools_layout = QVBoxLayout(tools_tab)
        tools_layout.setContentsMargins(0, 10, 0, 0)
        
        tools_group = QGroupBox("????")
        tools_group_layout = QVBoxLayout(tools_group)
        
        # ????????
        ad_patch_button = QPushButton("A???")
        ad_patch_button.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        ad_patch_button.clicked.connect(lambda: webbrowser.open("https://www.caimogu.cc/post/1615417.html"))
        
        easy_refresh_button = QPushButton("??")
        easy_refresh_button.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        easy_refresh_button.clicked.connect(lambda: webbrowser.open("https://www.caimogu.cc/post/1621584.html"))
        
        tools_group_layout.addWidget(ad_patch_button)
        tools_group_layout.addWidget(easy_refresh_button)
        tools_group_layout.addStretch()
        
        tools_layout.addWidget(tools_group)
        tools_layout.addStretch()
        
        # ?????
        tab_widget.addTab(price_tab, "????")
        tab_widget.addTab(tools_tab, "????")
        
        main_layout.addWidget(tab_widget)
        
        self.setCentralWidget(main_widget)
        
        # ?????????????????????
        main_widget.installEventFilter(self)
        
        # ????
        self.calculate_value()
    
    def update_price(self, currency, price):
        """???????????????"""
        # ??????
        self.prices[currency] = price
        
        # ?????? - ??4???
        price_label = getattr(self, f"{currency}_price_label", None)
        if price_label:
            price_label.setText(f"?{price:.4f}/?")
        
        # ????
        self.calculate_value()
        
        # ??????????????????????
        self.calculate_exchange_rates()
        
        # ??????????
        print(f"??{self.currency_names[currency]}??: {price}")
        print(f"??????: {self.prices}")
    
    def refresh_prices(self):
        """????????"""
        # ???????????
        for currency in self.prices:
            price_label = getattr(self, f"{currency}_price_label", None)
            if price_label:
                price_label.setText("????...")
        
        # ???????(????)??????
        if hasattr(self, 'price_thread') and self.price_thread.isRunning():
            self.price_thread.terminate()
            self.price_thread.wait()
        
        # ??????????
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
            
            # ????????
            self.divine_value.setText(f"?{divine_value:.2f}")
            self.exalted_value.setText(f"?{exalted_value:.2f}")
            self.chaos_value.setText(f"?{chaos_value:.2f}")
            
            # ????????
            self.calculate_exchange_rates()
        except ValueError:
            pass
    
    def calculate_exchange_rates(self):
        """???????????????"""
        # ?????
        if self.prices['exalted'] > 0 and self.prices['divine'] > 0 and self.prices['chaos'] > 0:
            # ??100??????????????
            divine_100 = 100
            exalted_rate = round(divine_100 * (self.prices['divine'] / self.prices['exalted']))
            chaos_rate = round(divine_100 * (self.prices['divine'] / self.prices['chaos']))
            
            # ??????
            self.divine_to_exalted.setText(
                f"<span style='color:{self.currency_colors['divine']}'>100D</span>"
                f"<span style='color:white'>?</span>"
                f"<span style='color:{self.currency_colors['exalted']}'>{exalted_rate}E</span>"
            )
            self.divine_to_chaos.setText(
                f"<span style='color:{self.currency_colors['divine']}'>100D</span>"
                f"<span style='color:white'>?</span>"
                f"<span style='color:{self.currency_colors['chaos']}'>{chaos_rate}C</span>"
            )
            
            # ??100??????????????
            exalted_100 = 100
            divine_rate = round(exalted_100 * (self.prices['exalted'] / self.prices['divine']))
            chaos_rate = round(exalted_100 * (self.prices['exalted'] / self.prices['chaos']))
            
            # ??????
            self.exalted_to_divine.setText(
                f"<span style='color:{self.currency_colors['exalted']}'>100E</span>"
                f"<span style='color:white'>?</span>"
                f"<span style='color:{self.currency_colors['divine']}'>{divine_rate}D</span>"
            )
            self.exalted_to_chaos.setText(
                f"<span style='color:{self.currency_colors['exalted']}'>100E</span>"
                f"<span style='color:white'>?</span>"
                f"<span style='color:{self.currency_colors['chaos']}'>{chaos_rate}C</span>"
            )
            
            # ??100??????????????
            chaos_100 = 100
            divine_rate = round(chaos_100 * (self.prices['chaos'] / self.prices['divine']))
            exalted_rate = round(chaos_100 * (self.prices['chaos'] / self.prices['exalted']))
            
            # ??????
            self.chaos_to_divine.setText(
                f"<span style='color:{self.currency_colors['chaos']}'>100C</span>"
                f"<span style='color:white'>?</span>"
                f"<span style='color:{self.currency_colors['divine']}'>{divine_rate}D</span>"
            )
            self.chaos_to_exalted.setText(
                f"<span style='color:{self.currency_colors['chaos']}'>100C</span>"
                f"<span style='color:white'>?</span>"
                f"<span style='color:{self.currency_colors['exalted']}'>{exalted_rate}E</span>"
            )
            
            # ??????
            print(f"???????: 100D ? {exalted_rate}E ? {chaos_rate}C")

    def eventFilter(self, obj, event):
        # ??????????????????????
        if event.type() == event.MouseButtonPress:
            focused_widget = QApplication.focusWidget()
            if focused_widget in [self.divine_amount, self.exalted_amount, self.chaos_amount]:
                focused_widget.clearFocus()
        
        return super().eventFilter(obj, event)

    def check_for_updates(self):
        # ??????????
        if self.is_updating:
            return
        
        try:
            # ???????????????????
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # ??????????????
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            
            latest_version = update_info.get("version")
            download_url = update_info.get("download_url")
            
            # ?????
            version_comparison = self.compare_versions(latest_version, self.current_version)
            
            if version_comparison > 0:
                # ?????????????
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setWindowTitle("?????")
                msg_box.setText(f"????? {latest_version}????? {self.current_version}")
                msg_box.setInformativeText("???????")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.Yes)
                
                if msg_box.exec_() == QMessageBox.Yes:
                    # ????????????????
                    self.download_and_replace(download_url)
            # ???????????????
        
        except Exception as e:
            # ???????????????????
            print(f"?????????: {e}")

    def compare_versions(self, version1, version2):
        """?????????? 1 ?? version1 > version2??? -1 ?? version1 < version2??? 0 ????"""
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
            # ??????
            self.is_updating = True
            
            # ???????????
            current_exe = sys.executable
            exe_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            
            # ?update.json??????
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            new_version = update_info.get("version", "unknown")
            
            # ?????????????
            new_exe_name = f"POE2PriceAid_v{new_version}.exe"
            
            # ??????????
            if not re.search(r'_v[0-9.]+\.exe$', exe_name):
                # ??????????
                new_name = os.path.join(exe_dir, f"POE2PriceAid_v{self.current_version}.exe")
                
                # ??????????
                try:
                    shutil.copy2(current_exe, new_name)
                    # ?????
                    subprocess.Popen([new_name])
                    # ??????
                    sys.exit(0)
                except Exception as e:
                    print(f"?????: {e}")
            
            # ???????
            self.progress_dialog = QProgressDialog("??????...", "??", 0, 100, self)
            self.progress_dialog.setWindowTitle("??")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setAutoClose(True)
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
            QApplication.processEvents()
            
            # ?progress_dialog?????????
            self.progress_dialog.canceled.connect(self.cancel_download)
            
            # ??requests??
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # ??????
            print(f"??? {download_url} ????")
            
            # ??stream=True???????
            response = requests.get(download_url, headers=headers, stream=True, timeout=30)
            
            # ?????
            if response.status_code != 200:
                self.progress_dialog.close()
                QMessageBox.critical(self, "????", f"??????????: {response.status_code}")
                self.is_updating = False
                return
            
            # ??????
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                self.progress_dialog.close()
                QMessageBox.critical(self, "????", "????????????????????")
                self.is_updating = False
                return
            
            # ?????????????
            temp_file = os.path.join(exe_dir, "POE2PriceAid_new.exe")
            downloaded_size = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # ????????????
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # ????
                        progress = int(downloaded_size * 100 / total_size)
                        self.progress_dialog.setValue(progress)
                        QApplication.processEvents()
                        
                    # ??????
                    if self.progress_dialog.wasCanceled():
                        f.close()
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        self.progress_dialog.close()
                        self.is_updating = False
                        return
            
            # ???????????????
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                self.progress_dialog.close()
                QMessageBox.critical(self, "????", "????????????")
                self.is_updating = False
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return
            
            # ???????
            self.progress_dialog.close()
            
            # ?????????
            updater_script = os.path.join(exe_dir, "update.bat")
            with open(updater_script, "w", encoding="gbk") as f:  # ??GBK???????Windows
                f.write(f"""@echo off
chcp 936 > nul
echo ????POE2PriceAid...
echo ???????...

rem ???????
timeout /t 5 /nobreak > nul

rem ???? (??????)
echo ??????...
del /f /q "{current_exe}"
if exist "{current_exe}" (
  echo ?????????????
  echo ???: {temp_file}
  echo ????: {exe_dir}\\{new_exe_name}
  pause
  exit /b 1
)

rem ??????????????
move /y "{temp_file}" "{exe_dir}\\{new_exe_name}"
if errorlevel 1 (
  echo ????????????
  pause
  exit /b 1
)

echo ?????????????

rem ??????
ping 127.0.0.1 -n 2 > nul
del "%~f0"
exit
""")
            
            # ?????????????
            QMessageBox.information(self, "????", f"???????????????????\n?????????? {new_exe_name}?")

            # ?????????
            subprocess.Popen([updater_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
            QTimer.singleShot(500, self.close)
            QTimer.singleShot(1000, lambda: sys.exit(0))
        
        except Exception as e:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, "????", f"???????: {e}")
            print(f"??????: {str(e)}")
            self.is_updating = False

    def check_updates_manually(self):
        # ??????????
        if self.is_updating:
            QMessageBox.information(self, "????", "???????????...", QMessageBox.Ok)
            return
        
        try:
            # ???????????
            status_dialog = QMessageBox(self)
            status_dialog.setWindowTitle("????")
            status_dialog.setText("??????????...")
            status_dialog.setStandardButtons(QMessageBox.Cancel)
            status_dialog.setIcon(QMessageBox.Information)
            
            # ???????????????????????
            check_timer = QTimer(self)
            check_timer.setSingleShot(True)
            check_timer.timeout.connect(lambda: self._perform_manual_update_check(status_dialog))
            check_timer.start(0)  # ??????
            
            # ????????????
            result = status_dialog.exec_()
            
            # ????????????
            if result == QMessageBox.Cancel:
                return
        
        except Exception as e:
            QMessageBox.critical(self, "????", f"???????: {e}", QMessageBox.Ok)

    def _perform_manual_update_check(self, status_dialog):
        try:
            # ????????????
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # ??????????????
            response = requests.get(self.update_url, headers=headers, timeout=5)
            update_info = json.loads(response.text)
            
            # ???????
            status_dialog.done(0)
            
            latest_version = update_info.get("version")
            download_url = update_info.get("download_url")
            
            # ?????
            version_comparison = self.compare_versions(latest_version, self.current_version)
            
            if version_comparison > 0:
                # ?????????????
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setWindowTitle("?????")
                msg_box.setText(f"????? {latest_version}????? {self.current_version}")
                msg_box.setInformativeText("???????")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.Yes)
                
                if msg_box.exec_() == QMessageBox.Yes:
                    # ????????????????
                    self.download_and_replace(download_url)
            else:
                # ????????????
                QMessageBox.information(self, "????", "?????????", QMessageBox.Ok)
        
        except requests.exceptions.Timeout:
            # ??????
            status_dialog.done(0)  # ???????
            QMessageBox.warning(self, "????", "?????????????", QMessageBox.Ok)
        except Exception as e:
            # ??????
            status_dialog.done(0)  # ???????
            QMessageBox.critical(self, "????", f"???????: {e}", QMessageBox.Ok)

    def create_desktop_shortcut(self):
        try:
            # ????????
            current_exe = sys.executable
            if getattr(sys, 'frozen', False):
                # ?????????
                application_path = os.path.dirname(current_exe)
            else:
                # ????????
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            # ?????
            launcher_path = os.path.join(application_path, "launcher.bat")
            
            # ????????????
            if not os.path.exists(launcher_path):
                with open(launcher_path, "w") as f:
                    f.write(f"""@echo off
start "" "{current_exe}"
exit
""")
            
            # ??????
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            
            # ??????
            shortcut_path = os.path.join(desktop_path, "POE2PriceAid.lnk")
            self.create_shortcut(launcher_path, shortcut_path, "POE2PriceAid", application_path)
            
            return True
        except Exception as e:
            print(f"??????????: {e}")
            return False

    def cancel_download(self):
        self.download_canceled = True
        self.is_updating = False

if __name__ == "__main__":
    # ?????????PyInstaller???????
    if getattr(sys, 'frozen', False):
        os.environ['PYI_APPLICATION_HOME_DIR'] = os.path.dirname(sys.executable)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 