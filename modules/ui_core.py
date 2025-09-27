"""
UI核心模块
实现主窗口和基本UI框架
"""

import sys
import os
import webbrowser
import importlib
from typing import Dict, Callable, Optional
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QTabWidget, QApplication, 
                            QSpacerItem, QSizePolicy, QScrollArea, QFrame,
                            QGridLayout, QSplitter, QListWidget, QListWidgetItem,
                            QTextEdit, QDialog, QDialogButtonBox, QLineEdit, QFileDialog,
                            QMessageBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
                            QComboBox, QMenu, QAction, QProgressBar, QGroupBox, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont
from PyQt5.Qt import QDesktopServices

from modules.config import Config
from modules.filter import FilterTab  # 导入新的FilterTab类
from modules.update_checker import UpdateChecker
from modules.notice_manager import NoticeManager  # 导入公告管理器

# 明确导入跨平台标签页
from modules.price_monitor import PriceMonitorTab
from modules.web_monitor import WebMonitorTab

import platform


class PasswordDialog(QDialog):
    """密码输入对话框类"""
    
    def __init__(self, parent=None):
        """初始化密码输入对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        # 设置对话框属性
        self.setWindowTitle("输入密码")
        self.setFixedSize(300, 120)
        self.setModal(True)  # 设置为模态对话框
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 10)
        
        # 添加说明标签
        label = QLabel("请输入密码以启用隐藏功能:")
        layout.addWidget(label)
        
        # 添加密码输入框
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)  # 设置为密码模式
        layout.addWidget(self.password_edit)
        
        # 添加按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_password(self):
        """获取输入的密码
        
        Returns:
            str: 输入的密码
        """
        return self.password_edit.text()


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 从配置获取版本
        self.current_version = Config.CURRENT_VERSION
        # 设置默认窗口大小
        self.default_window_size = QSize(*Config.DEFAULT_WINDOW_SIZE)
        
        # 初始化货币颜色和名称
        self.currency_colors = Config.CURRENCY_COLORS
        self.currency_names = Config.CURRENCY_NAMES
        
        # 初始化网站数据
        self.website_data = Config.WEBSITE_DATA
        self.website_names = Config.WEBSITE_NAMES
        
        # 加载隐藏功能状态
        Config.load_hidden_features_state()
        
        # 初始化更新检查器
        self.update_checker = UpdateChecker(self, Config.CURRENT_VERSION)
        
        # 心跳客户端功能已移除
        # self.heartbeat_client = None
        
        # 初始化公告管理器
        self.notice_manager = NoticeManager(self)
        
        # 初始化UI
        self.init_ui()
        
        # 启动延迟自动检查更新（5秒后执行）- 程序仅在启动时检测一次，不会周期性检测
        QTimer.singleShot(5000, self.update_checker.check_for_updates)
        
        # 心跳客户端功能已移除
        
        # 显示正在加载公告状态
        self.update_notice_label("正在加载公告...", "#FFA500")
        
        # 在事件循环启动后再启动公告管理器，避免阻塞首帧绘制
        QTimer.singleShot(0, self.notice_manager.start)
        
        # 如果隐藏功能已启用，在UI初始化后激活隐藏功能
        if Config.HIDDEN_FEATURES["enabled"]:
            QTimer.singleShot(1000, self.apply_hidden_features)
    
    def init_ui(self):
        """初始化UI组件"""
        # 设置标题和大小
        self.setWindowTitle(f"POE2PriceAid 国服 v{self.current_version} • 请勿分享到公共平台 • by WANG")
        self.setMinimumSize(900, 350)  # 设置最小尺寸
        
        # 尝试恢复上次的窗口位置和大小
        if not Config.load_window_geometry(self):
            # 如果没有保存的几何信息，使用默认大小
            self.resize(self.default_window_size)  # 设置默认窗口大小
        
        # 应用深色主题
        self.setup_dark_theme()
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)  # 设置适当的边距
        
        # 添加页眉导航
        self.create_header(main_layout)
        
        # 添加选项卡
        self.create_tabs(main_layout)
        
        # 创建主窗口部件并设置布局
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # 设置应用图标
        self.set_app_icon()

    def setup_dark_theme(self):
        """设置深色主题"""
        dark_palette = QPalette()
        
        # 设置基础颜色
        dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.WindowText, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.Base, QColor(36, 36, 36))
        dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(36, 36, 36))
        dark_palette.setColor(QPalette.ToolTipText, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.Text, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ButtonText, QColor(212, 212, 212))
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(36, 36, 36))
        
        # 设置禁用状态颜色
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(122, 122, 122))
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(122, 122, 122))
        dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(122, 122, 122))
        
        # 应用调色板
        self.setPalette(dark_palette)
        
        # 设置全局样式
        QApplication.setStyle("Fusion")
        
        # 设置字体
        font = QFont()
        # 设置字体族，按优先级顺序指定多个备用字体，包括微软雅黑的所有可能名称
        font.setFamilies(["Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", 
                         "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体",
                         "SimSun", "宋体", "NSimSun", "新宋体",
                         "Arial", "Helvetica", "sans-serif"])
        font.setPointSize(9)  # 设置统一的字体大小
        QApplication.setFont(font)
        
        # 设置全局样式表
        qss = """
        QMainWindow {
            background-color: #2D2D2D;
        }
        QWidget {
            background-color: #2D2D2D;
            color: #D4D4D4;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QLineEdit {
            background-color: #363636;
            color: #D4D4D4;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 2px;
            selection-background-color: #0078D7;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QComboBox {
            background-color: #363636;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 2px 5px;
            color: #D4D4D4;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QComboBox:drop-down {
            subcontrol-origin: padding;
            subcontrol-position: right;
            width: 20px;
            border-left: 1px solid #555555;
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #555555;
            background-color: #363636;
            selection-background-color: #0078D7;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QPushButton {
            background-color: #363636;
            color: #D4D4D4;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px 8px;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QPushButton:hover {
            background-color: #404040;
        }
        QPushButton:pressed {
            background-color: #0078D7;
        }
        QLabel {
            color: #D4D4D4;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QTabWidget::pane {
            border: 1px solid #555555;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QTabBar::tab {
            background-color: #363636;
            border: 1px solid #555555;
            padding: 5px 10px;
            margin-right: 2px;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QTabBar::tab:selected {
            background-color: #0078D7;
        }
        QTabBar::tab:hover {
            background-color: #444444;
            cursor: pointer;    /* 保留鼠标指针为手型 */
        }
        QTableWidget {
            background-color: #363636;
            alternate-background-color: #404040;
            gridline-color: #555555;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QTableWidget QHeaderView::section {
            background-color: #2D2D2D;
            color: #D4D4D4;
            padding: 4px;
            border: 1px solid #555555;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QCheckBox {
            spacing: 5px;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QCheckBox::indicator {
            width: 13px;
            height: 13px;
        }
        QCheckBox::indicator:unchecked {
            background-color: #363636;
            border: 1px solid #555555;
        }
        QCheckBox::indicator:checked {
            background-color: #0078D7;
            border: 1px solid #0078D7;
        }
        QListWidget {
            background-color: #363636;
            border: 1px solid #555555;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QListWidget::item:hover {
            background-color: #404040;
        }
        QListWidget::item:selected {
            background-color: #0078D7;
        }
        QScrollBar:vertical {
            background-color: #2D2D2D;
            width: 12px;
            margin: 12px 0px 12px 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #555555;
            min-height: 30px;
            border-radius: 3px;
        }
        QScrollBar:horizontal {
            background-color: #2D2D2D;
            height: 12px;
            margin: 0px 12px 0px 12px;
        }
        QScrollBar::handle:horizontal {
            background-color: #555555;
            min-width: 30px;
            border-radius: 3px;
        }
        QGroupBox {
            border: 1px solid #555555;
            border-radius: 3px;
            margin-top: 10px;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: #D4D4D4;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QProgressBar {
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #363636;
            text-align: center;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        QProgressBar::chunk {
            background-color: #0078D7;
            width: 5px;
        }
        QTextEdit {
            background-color: #363636;
            color: #D4D4D4;
            border: 1px solid #555555;
            selection-background-color: #0078D7;
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 9pt;
        }
        """
        
        self.setStyleSheet(qss)

    def create_header(self, parent_layout):
        """创建标题和按钮"""
        # 顶部标题和按钮
        header_layout = QHBoxLayout()  # 使用水平布局，所有元素在同一行
        
        # 左侧标题
        title_label = QLabel("POE2PriceAid")
        title_label.setStyleSheet("font-family: \"Microsoft YaHei\", \"微软雅黑\", \"Microsoft YaHei UI\", \"Microsoft JhengHei\", \"微软正黑体\", \"SimHei\", \"黑体\", \"SimSun\", \"宋体\", \"NSimSun\", \"新宋体\", \"Arial\", \"Helvetica\", sans-serif; font-size: 20px; font-weight: bold;")
        title_label.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时显示为手型
        title_label.mouseDoubleClickEvent = self.on_title_double_clicked  # 设置双击事件处理函数
        self.title_label = title_label  # 保存引用，以便后续访问
        header_layout.addWidget(title_label)
        
        # 添加导航按钮 - 放在标题右侧，功能按钮左侧
        # 导航按钮样式 - 更大的字体和统一的颜色
        nav_button_style = """
            QPushButton {
                background-color: transparent;
                color: #0078D7;
                border: none;
                padding: 4px 12px;
                font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
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
            button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            button.setFixedHeight(30)  # 增加高度，使按钮更大
            return button
        
        # 添加导航按钮
        nav_buttons = Config.NAVIGATION_LINKS
        
        # 添加一个小的分隔符
        header_layout.addSpacing(15)
        
        # 添加导航按钮
        for text, url in nav_buttons:
            header_layout.addWidget(create_nav_button(text, url))
        
        # 添加新的公告区占位 (后续会由notice_manager模块填充)
        self.notice_label = QLabel(Config.NOTICE_CONFIG["default_notice"])
        self.notice_label.setStyleSheet("""
            color: #FFA500; 
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 14px; 
            font-weight: bold; 
            background-color: rgba(40, 40, 40, 0.7);
            border-radius: 4px;
            padding: 2px 10px;
        """)
        self.notice_label.setFixedWidth(320)  # 设置固定宽度
        self.notice_label.setFixedHeight(28)  # 匹配导航按钮高度
        self.notice_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 左对齐并垂直居中
        
        # 使公告标签可点击
        self.notice_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.notice_label.setCursor(Qt.PointingHandCursor)  # 设置鼠标指针为手型
        self.notice_label.mouseReleaseEvent = self.on_notice_clicked  # 设置点击事件处理函数
        
        # 连接公告更新信号
        self.notice_manager.notice_updated.connect(self.update_notice_label)
        
        # 在布局中添加公告标签
        header_layout.addSpacing(15)    # 添加一些间距
        header_layout.addWidget(self.notice_label)
        
        # 添加弹性空间，将功能按钮推到右侧
        header_layout.addStretch()
        
        # 右侧按钮组 - 使用水平布局将按钮放在一起
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)  # 设置按钮之间的间距
        
        # 检查更新按钮
        check_update_button = QPushButton("检查更新")
        check_update_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        check_update_button.clicked.connect(self.update_checker.check_updates_manually)
        buttons_layout.addWidget(check_update_button)
        
        # 将按钮组添加到标题栏
        header_layout.addLayout(buttons_layout)
        
        # 将整个头部布局添加到主布局
        parent_layout.addLayout(header_layout)

    def create_tabs(self, parent_layout):
        """创建选项卡"""
        # 选项卡
        self.tab_widget = QTabWidget()
        
        # 设置标签页样式
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 12px;
                margin-right: 3px;  /* 标签页右边距 */
                margin-left: 1px;   /* 标签页左边距 */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 100px;   /* 设置最小宽度确保有足够点击区域 */
                text-align: center; /* 文本居中 */
            }
            QTabBar::tab:selected {
                background-color: #333333;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #444444;
                cursor: pointer;    /* 保留鼠标指针为手型 */
            }
        """)
        
        # 创建各个功能模块标签页
        
        # 1. 价格监控选项卡 - 动态导入，避免某些环境下名称未解析
        try:
            from modules.price_monitor import PriceMonitorTab as _PMT
        except Exception:
            import importlib
            _PMT = getattr(importlib.import_module('modules.price_monitor'), 'PriceMonitorTab')
        self.price_tab = _PMT()

        # 2. 帖子监控选项卡 - 动态导入
        try:
            from modules.web_monitor import WebMonitorTab as _WMT
        except Exception:
            import importlib
            _WMT = getattr(importlib.import_module('modules.web_monitor'), 'WebMonitorTab')
        self.web_monitor_tab = _WMT()
        
        # 3. A大补丁（Windows 专用）
        self.apatch_tab = None
        if platform.system() == 'Windows':
            try:
                from modules.apatch import APatchTab  # 仅在 Windows 导入，避免 winreg 导入失败
                self.apatch_tab = APatchTab()
            except Exception:
                self.apatch_tab = self._build_placeholder_tab("A大补丁仅支持 Windows")
        else:
            self.apatch_tab = self._build_placeholder_tab("A大补丁仅支持 Windows")
        
        # 4. 过滤器安装选项卡 - 使用FilterTab
        self.filter_tab = FilterTab()
        
        # 5. 自动喝药（Windows 专用）
        self.auto_flask_tab = None
        if platform.system() == 'Windows':
            try:
                from modules.auto_flask import AutoFlaskTab
                self.auto_flask_tab = AutoFlaskTab()
            except Exception:
                self.auto_flask_tab = self._build_placeholder_tab("自动喝药仅支持 Windows")
        else:
            self.auto_flask_tab = self._build_placeholder_tab("自动喝药仅支持 Windows")
        
        # 添加主选项卡
        self.tab_widget.clear()  # 清除所有现有标签
        self.tab_widget.addTab(self.price_tab, "价格监控")
        self.tab_widget.addTab(self.web_monitor_tab, "帖子监控")
        self.tab_widget.addTab(self.apatch_tab, "A大补丁")
        self.tab_widget.addTab(self.filter_tab, "过滤器安装")
        self.tab_widget.addTab(self.auto_flask_tab, "自动喝药")
        
        # 连接双击事件
        self.tab_widget.tabBarDoubleClicked.connect(self.on_tab_double_clicked)
        
        parent_layout.addWidget(self.tab_widget)
        
        return self.tab_widget

    def _build_placeholder_tab(self, message: str) -> QWidget:
        """构建占位标签页（用于不支持的平台）"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #888888; font-size: 16px;")
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addStretch(1)
        return w
    
    def on_tab_double_clicked(self, index):
        """处理选项卡双击事件"""
        # 如果是价格监控标签页
        if index == 0:
            # 显示刷新状态信息
            self.notice_manager.show_status("正在刷新价格数据...")
            
            # 调用价格标签页的刷新方法
            if hasattr(self.price_tab, 'refresh_prices'):
                self.price_tab.refresh_prices()
            else:
                self.notice_manager.show_status("刷新功能未实现")
        
        # 如果是帖子监控标签页
        elif index == 1:
            # 显示刷新状态信息
            self.notice_manager.show_status("正在刷新帖子数据...")
            
            # 调用帖子监控标签页的刷新方法
            if hasattr(self.web_monitor_tab, 'refresh_websites'):
                # 先显示刷新状态
                if hasattr(self.web_monitor_tab, 'show_refreshing_status'):
                    self.web_monitor_tab.show_refreshing_status()
                
                # 然后进行实际刷新
                self.web_monitor_tab.refresh_websites()
            else:
                self.notice_manager.show_status("刷新功能未实现")
        
        # 如果是A大补丁标签页
        elif index == 2:
            # 显示刷新状态信息
            self.notice_manager.show_status("正在重新检测游戏路径...")
            
            # 调用A大补丁标签页的检测游戏路径方法
            if hasattr(self.apatch_tab, 'detect_game_path'):
                self.apatch_tab.detect_game_path()
            else:
                self.notice_manager.show_status("刷新功能未实现")

        # 如果是过滤器标签页
        elif index == 3:
            # 显示刷新状态信息
            self.notice_manager.show_status("正在获取过滤器更新信息...")
            
            # 调用过滤器标签页的获取更新时间方法
            if hasattr(self.filter_tab, 'get_filter_update_time'):
                self.filter_tab.get_filter_update_time()
            else:
                self.notice_manager.show_status("刷新功能未实现")
                
        # 如果是自动喝药标签页
        elif index == 4:
            # 显示刷新状态信息
            self.notice_manager.show_status("正在检测脚本状态...")
            
            # 调用自动喝药标签页的检查状态方法
            if hasattr(self.auto_flask_tab, 'check_status'):
                self.auto_flask_tab.check_status()
            else:
                self.notice_manager.show_status("刷新功能未实现")
    
    def set_app_icon(self):
        """设置应用图标"""
        icon_path = Config.get_app_icon_path()
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # 设置应用程序图标，影响任务栏
            if hasattr(QApplication.instance(), 'setWindowIcon'):
                QApplication.instance().setWindowIcon(QIcon(icon_path)) 

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 保存窗口位置和大小
        Config.save_window_geometry(self)
        
        # 心跳客户端功能已移除
        
        # 停止公告管理器
        self.notice_manager.stop()
        
        # 继续默认的关闭事件处理
        super().closeEvent(event)
    
    # 心跳功能已移除
    # def on_heartbeat_sent(self, success, message):

    def update_notice_label(self, text, color):
        """更新公告标签
        
        Args:
            text: 公告文本
            color: 文本颜色
        """
        self.notice_label.setText(text)
        self.notice_label.setStyleSheet(f"""
            color: {color}; 
            font-family: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "Microsoft JhengHei", "微软正黑体", "SimHei", "黑体", "SimSun", "宋体", "NSimSun", "新宋体", "Arial", "Helvetica", sans-serif;
            font-size: 14px; 
            font-weight: bold; 
            background-color: rgba(40, 40, 40, 0.7);
            border-radius: 4px;
            padding: 2px 10px;
        """)
    
    def on_notice_clicked(self, event):
        """处理公告点击事件
        
        Args:
            event: 鼠标事件
        """
        # 调用公告管理器的点击处理方法
        self.notice_manager.handle_click()
        
        # 继续传递事件
        super(QLabel, self.notice_label).mouseReleaseEvent(event) 

    def on_title_double_clicked(self, event):
        """处理标题双击事件
        
        Args:
            event: 鼠标事件
        """
        # 显示密码输入对话框
        dialog = PasswordDialog(self)
        
        # 如果用户点击了确定按钮
        if dialog.exec_() == QDialog.Accepted:
            # 获取输入的密码
            password = dialog.get_password()
            
            # 验证密码
            if password == Config.HIDDEN_FEATURES["password"]:
                # 更新隐藏功能状态
                self.enable_hidden_features()
                # 显示成功消息
                QMessageBox.information(self, "成功", "隐藏功能已启用")
            else:
                # 显示错误消息
                QMessageBox.warning(self, "错误", "密码错误")
        
        # 继续传递事件
        super(QLabel, self.title_label).mouseDoubleClickEvent(event)
    
    def enable_hidden_features(self):
        """启用隐藏功能"""
        # 更新配置
        Config.HIDDEN_FEATURES["enabled"] = True
        
        # 保存隐藏功能状态到配置文件
        Config.save_hidden_features_state()
        
        # 应用隐藏功能
        self.apply_hidden_features()
    
    def apply_hidden_features(self):
        """应用隐藏功能，添加隐藏的监控网站"""
        # 仅在GUI线程中执行，避免跨线程创建UI对象
        try:
            from PyQt5.QtCore import QThread
            if QThread.currentThread() is not self.thread():
                return
        except Exception:
            pass
        # 为WebMonitorTab添加隐藏的监控网站（安全检查 + 延迟重试）
        try:
            if hasattr(self, 'web_monitor_tab') and hasattr(self.web_monitor_tab, 'add_hidden_websites'):
                # 使用0延迟在GUI事件循环中执行，避免潜在线程问题
                QTimer.singleShot(0, self.web_monitor_tab.add_hidden_websites)
            else:
                # 如果方法尚未可用（懒加载尚未完成），稍后重试，最多重试5次
                tries = getattr(self, '_hidden_feature_apply_tries', 0)
                if tries < 5:
                    setattr(self, '_hidden_feature_apply_tries', tries + 1)
                    QTimer.singleShot(500, self.apply_hidden_features)
        except Exception:
            # 忽略异常，避免影响主流程
            pass
        
        # 为AutoFlaskTab添加POE2助手管理功能
        if hasattr(self, 'auto_flask_tab') and hasattr(self.auto_flask_tab, 'apply_hidden_features'):
            self.auto_flask_tab.apply_hidden_features() 
