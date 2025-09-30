"""
帖子监控模块
实现帖子信息爬取和显示功能
"""

import webbrowser
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QGridLayout, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QFont
from PyQt5.Qt import QDesktopServices

from modules.config import Config


class WebMonitor(QThread):
    """帖子监控线程类"""
    content_updated = pyqtSignal(str, str, str)  # 网站ID, 标题, 更新时间
    
    def __init__(self, include_hidden=False):
        super().__init__()
        self.websites = Config.WEBSITE_DATA.copy()
        
        # 如果需要包含隐藏网站且隐藏功能已启用
        if include_hidden and Config.HIDDEN_FEATURES.get("enabled", False):
            # 将隐藏网站数据添加到网站列表中
            self.websites.update(Config.HIDDEN_WEBSITE_DATA)
        
    def run(self):
        # 网站顺序
        site_order = list(self.websites.keys())
        
        for site_id in site_order:
            try:
                site_info = self.websites.get(site_id)
                if not site_info:
                    continue
                
                # 获取网站信息
                title, update_time = self.get_website_info(site_info["url"], site_info["title_selector"], site_info["time_selector"])
                if title and update_time:
                    self.content_updated.emit(site_id, title, update_time)
                
                # 添加较长的延迟，避免被反爬机制拦截
                self.msleep(3000)  # 每个请求间隔3秒
            except Exception as e:
                print(f"获取网站信息时出错 ({site_id}): {e}")
    
    def get_website_info(self, url, title_selector, time_selector):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.caimogu.cc/',
                'Cache-Control': 'max-age=0',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # 创建会话，启用重试机制
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            
            response = session.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title_element = soup.select_one(title_selector)
            title = title_element.text.strip() if title_element else "获取失败"
            
            # 提取更新时间
            time_element = soup.select_one(time_selector)
            update_time = time_element.text.strip() if time_element else "获取失败"
            
            return title, update_time
            
        except Exception as e:
            print(f"抓取网页内容时出错: {e}")
            return "获取失败", "获取失败"


class WebMonitorTab(QWidget):
    """帖子监控标签页类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化属性
        self.website_data = {
            site_id: {"title": "加载中...", "update_time": "加载中...", "url": site_info["url"]}
            for site_id, site_info in Config.WEBSITE_DATA.items()
        }
        self.website_names = Config.WEBSITE_NAMES.copy()
        self.web_countdown_seconds = 1800  # 30分钟倒计时
        self.web_start_time = datetime.now()  # 记录网站监控开始时间
        
        # 追踪隐藏网站状态
        self.hidden_websites_added = False
        
        # 存储监控线程
        self.web_monitor_thread = None
        self.hidden_web_monitor_thread = None
        
        # 初始化UI
        self.init_ui()
        
        # 启动倒计时定时器
        self.web_countdown_timer = QTimer(self)
        self.web_countdown_timer.timeout.connect(self.update_web_countdown_display)
        self.web_countdown_timer.start(1000)  # 每秒更新倒计时
        
        # 启动网站监控线程
        self.refresh_websites()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(10)
        
        # 创建网址监控UI - 使用网格布局
        self.web_monitor_grid = QGridLayout()
        self.web_monitor_grid.setSpacing(10)  # 设置网格间距
        
        # 添加网站内容
        self.create_website_grid()
        
        # 设置列的拉伸因子，使标题列获得更多空间
        self.web_monitor_grid.setColumnStretch(0, 1)  # 网站名称列
        self.web_monitor_grid.setColumnStretch(1, 5)  # 标题列获得更多空间
        self.web_monitor_grid.setColumnStretch(2, 2)  # 更新时间列
        self.web_monitor_grid.setColumnStretch(3, 0)  # 按钮列不拉伸
        
        # 添加网格布局到主布局
        self.layout.addLayout(self.web_monitor_grid)
        
        # 底部布局 - 说明和倒计时
        web_bottom_layout = QHBoxLayout()
        
        # 添加说明文本
        web_note = QLabel("说明：数据每60分钟自动更新一次。")
        web_note.setStyleSheet("color: #888888; margin-top: 10px; font-size: 16px;")
        web_bottom_layout.addWidget(web_note)
        
        # 添加弹性空间，将倒计时推到右侧
        web_bottom_layout.addStretch(1)
        
        # 添加倒计时标签
        self.web_countdown_label = QLabel("下次刷新: 60:00")
        self.web_countdown_label.setStyleSheet("color: #888888; margin-top: 10px; font-size: 14px;")
        web_bottom_layout.addWidget(self.web_countdown_label)
        
        # 将底部布局添加到主布局
        self.layout.addLayout(web_bottom_layout)
        
        # 添加弹性空间
        self.layout.addStretch(1)
    
    def create_website_grid(self):
        """创建网站监控网格"""
        row = 0
        for site_id, site_name in self.website_names.items():
            # 网站名称
            site_label = QLabel(site_name + ":")
            site_label.setStyleSheet("color: #0078D7; font-weight: bold; font-size: 16px;")
            self.web_monitor_grid.addWidget(site_label, row, 0)
            
            # 标题
            title_label = QLabel("加载中...")
            title_label.setStyleSheet("color: #888888; font-size: 16px;")
            title_label.setMinimumWidth(300)  # 设置最小宽度
            setattr(self, f"{site_id}_title_label", title_label)
            self.web_monitor_grid.addWidget(title_label, row, 1)
            
            # 更新时间
            time_label = QLabel("加载中...")
            time_label.setStyleSheet("color: #888888; font-size: 14px;")
            setattr(self, f"{site_id}_time_label", time_label)
            self.web_monitor_grid.addWidget(time_label, row, 2)
            
            # 跳转按钮
            jump_button = QPushButton("跳转")
            jump_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #1C86E0;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
            """)
            jump_button.clicked.connect(lambda checked, url=self.website_data[site_id]["url"]: QDesktopServices.openUrl(QUrl(url)))
            jump_button.setFixedWidth(60)  # 设置按钮宽度
            self.web_monitor_grid.addWidget(jump_button, row, 3)
            
            row += 1
    
    def add_hidden_websites(self):
        """添加隐藏的网站到监控列表"""
        # 如果隐藏功能未启用或隐藏网站已添加，则返回
        if not Config.HIDDEN_FEATURES.get("enabled", False) or self.hidden_websites_added:
            return
        
        # 更新网站数据和名称
        for site_id, site_info in Config.HIDDEN_WEBSITE_DATA.items():
            # 如果网站已经在列表中，则跳过
            if site_id in self.website_data:
                continue
            
            # 添加到网站数据和名称
            self.website_data[site_id] = {
                "title": "加载中...", 
                "update_time": "加载中...", 
                "url": site_info["url"]
            }
            self.website_names[site_id] = site_info["name"]
            
            # 获取当前行号
            row = self.web_monitor_grid.rowCount()
            
            # 网站名称
            site_label = QLabel(site_info["name"] + ":")
            site_label.setStyleSheet("color: #0078D7; font-weight: bold; font-size: 16px;")
            self.web_monitor_grid.addWidget(site_label, row, 0)
            
            # 标题
            title_label = QLabel("加载中...")
            title_label.setStyleSheet("color: #888888; font-size: 16px;")
            title_label.setMinimumWidth(300)  # 设置最小宽度
            setattr(self, f"{site_id}_title_label", title_label)
            self.web_monitor_grid.addWidget(title_label, row, 1)
            
            # 更新时间
            time_label = QLabel("加载中...")
            time_label.setStyleSheet("color: #888888; font-size: 14px;")
            setattr(self, f"{site_id}_time_label", time_label)
            self.web_monitor_grid.addWidget(time_label, row, 2)
            
            # 跳转按钮
            jump_button = QPushButton("跳转")
            jump_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #1C86E0;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
            """)
            jump_button.clicked.connect(lambda checked, url=site_info["url"]: QDesktopServices.openUrl(QUrl(url)))
            jump_button.setFixedWidth(60)  # 设置按钮宽度
            self.web_monitor_grid.addWidget(jump_button, row, 3)
        
        # 标记隐藏网站已添加
        self.hidden_websites_added = True
        
        # 刷新网站信息
        self.refresh_hidden_websites()
    
    def refresh_hidden_websites(self):
        """仅刷新隐藏的网站信息"""
        # 如果隐藏功能未启用或隐藏网站未添加，则返回
        if not Config.HIDDEN_FEATURES.get("enabled", False) or not self.hidden_websites_added:
            return
        
        # 如果已有隐藏监控线程在运行，先终止它
        if self.hidden_web_monitor_thread and self.hidden_web_monitor_thread.isRunning():
            self.hidden_web_monitor_thread.quit()
            self.hidden_web_monitor_thread.wait()
            
        # 启动网站监控线程，包含隐藏网站
        self.hidden_web_monitor_thread = WebMonitor(include_hidden=True)
        self.hidden_web_monitor_thread.content_updated.connect(self.update_website_info)
        self.hidden_web_monitor_thread.finished.connect(self.on_hidden_web_monitor_finished)
        self.hidden_web_monitor_thread.start()
    
    def on_hidden_web_monitor_finished(self):
        """隐藏网站监控线程完成处理"""
        print("隐藏网站监控刷新已完成")
    
    def refresh_websites(self):
        """刷新所有网站信息"""
        # 重置倒计时
        self.web_start_time = datetime.now()
        
        # 更新倒计时显示
        self.update_web_countdown_display()
        
        # 如果已有监控线程在运行，先终止它
        if self.web_monitor_thread and self.web_monitor_thread.isRunning():
            self.web_monitor_thread.quit()
            self.web_monitor_thread.wait()
        
        # 启动网站监控线程，根据隐藏功能状态决定是否包含隐藏网站
        include_hidden = Config.HIDDEN_FEATURES.get("enabled", False) and self.hidden_websites_added
        self.web_monitor_thread = WebMonitor(include_hidden=include_hidden)
        self.web_monitor_thread.content_updated.connect(self.update_website_info)
        self.web_monitor_thread.finished.connect(self.on_web_monitor_finished)
        self.web_monitor_thread.start()
    
    def update_web_countdown_display(self):
        """更新倒计时显示"""
        # 计算经过的时间
        elapsed = datetime.now() - self.web_start_time
        elapsed_seconds = int(elapsed.total_seconds())
        
        # 计算剩余时间
        remaining = max(0, self.web_countdown_seconds - elapsed_seconds)
        minutes = remaining // 60
        seconds = remaining % 60
        
        # 更新倒计时标签
        self.web_countdown_label.setText(f"下次刷新: {minutes:02d}:{seconds:02d}")
        
        # 如果倒计时结束，自动刷新
        if remaining == 0 and (not hasattr(self, 'web_monitor_thread') or 
                               (hasattr(self, 'web_monitor_thread') and not self.web_monitor_thread.isRunning())):
            self.refresh_websites()
    
    def on_web_monitor_finished(self):
        """网站监控线程完成处理"""
        # 打印一条调试信息，实际使用时可以移除
        print("网站监控刷新已完成")
        
        # 恢复倒计时标签的默认样式（灰色）
        if hasattr(self, 'web_countdown_label'):
            # 保持文本内容为当前倒计时，但恢复原始灰色样式
            self.web_countdown_label.setStyleSheet("color: #888888; margin-top: 10px; font-size: 14px;")
            
            # 立即更新倒计时显示，确保显示正确的时间
            self.update_web_countdown_display()
    
    def update_website_info(self, site_id, title, update_time):
        """更新网站信息"""
        if site_id in self.website_data:
            # 更新数据
            self.website_data[site_id]["title"] = title
            self.website_data[site_id]["update_time"] = update_time
            
            # 更新UI
            title_label = getattr(self, f"{site_id}_title_label", None)
            time_label = getattr(self, f"{site_id}_time_label", None)
            
            if title_label:
                title_label.setText(title)
                title_label.setStyleSheet("color: #D4D4D4; font-size: 16px;")
            
            if time_label:
                time_label.setText(update_time)
                time_label.setStyleSheet("color: #888888; font-size: 14px;")
    
    def show_refreshing_status(self):
        """显示正在刷新的状态"""
        # 更新所有网站的标题和时间标签
        for site_id in self.website_data:
            title_label = getattr(self, f"{site_id}_title_label", None)
            time_label = getattr(self, f"{site_id}_time_label", None)
            
            if title_label:
                title_label.setText("正在刷新...")
                title_label.setStyleSheet("color: #888888; font-size: 16px;")
            
            if time_label:
                time_label.setText("请稍候...")
                time_label.setStyleSheet("color: #888888; font-size: 14px;")
                
        # 仅修改倒计时标签的文本，但保持其灰色样式
        if hasattr(self, 'web_countdown_label'):
            self.web_countdown_label.setText("正在刷新...")
    
    def __del__(self):
        """析构函数，确保线程在对象销毁时被正确终止"""
        try:
            # 停止倒计时定时器
            if hasattr(self, 'web_countdown_timer') and self.web_countdown_timer.isActive():
                self.web_countdown_timer.stop()
            
            # 停止主网站监控线程
            if hasattr(self, 'web_monitor_thread') and self.web_monitor_thread and self.web_monitor_thread.isRunning():
                self.web_monitor_thread.quit()
                self.web_monitor_thread.wait(1000)  # 等待最多1秒
            
            # 停止隐藏网站监控线程
            if hasattr(self, 'hidden_web_monitor_thread') and self.hidden_web_monitor_thread and self.hidden_web_monitor_thread.isRunning():
                self.hidden_web_monitor_thread.quit()
                self.hidden_web_monitor_thread.wait(1000)  # 等待最多1秒
        except:
            # 忽略销毁过程中的异常
            pass 