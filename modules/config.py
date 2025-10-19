"""
配置管理模块
用于存储和管理全局配置和共享数据
"""

import os
import sys
import json
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QSettings


class Config:
    """配置管理类"""
    
    # 程序版本
    CURRENT_VERSION = "3.0.25"
    
    # 默认窗口大小
    DEFAULT_WINDOW_SIZE = (930, 350)
    
    # 货币颜色
    CURRENCY_COLORS = {
        "divine": "#FFFF00",   # 神圣石 - 黄色
        "exalted": "#00BFFF",  # 崇高石 - 蓝色
        "chaos": "#FF6347",    # 混沌石 - 番茄红
        "chance": "#32CD32",   # 机会石 - 绿色
    }
    
    # 货币名称
    CURRENCY_NAMES = ["divine", "exalted", "chaos", "chance"]
    
    # 隐藏功能配置
    HIDDEN_FEATURES = {
        "enabled": False,      # 是否启用隐藏功能
        "password": "poe1126", # 默认密码
    }
    
    # 隐藏网站数据
    HIDDEN_WEBSITE_DATA = {
        "poehelper": {
            "name": "POE助手",
            "url": "https://www.caimogu.cc/post/2191352.html",
            "title_selector": "body > div.container.simple > div.content > div.post-content > div > div.title",
            "time_selector": "body > div.container.simple > div.content > div.post-content > div > div.post-action-container > div > span.publish-time"
        }
    }
    
    # 公告配置
    NOTICE_CONFIG = {
        "url": "https://gitee.com/mexiaow/poe2-price-aid/raw/main/version_Notice.txt",  # 公告数据URL
        "local_file": "version_Notice.txt",  # 本地公告文件名
        "rotation_interval": 15000,  # 公告轮播间隔（毫秒）→ 15秒
        "default_notice": "双击标签可刷新相应数据",  # 最终后备公告（当所有其他获取方式失败时使用）
        "max_notices": 5,  # 最多显示的公告数量
        "refresh_interval": 30 * 60 * 1000  # 公告刷新间隔（毫秒）→ 30分钟
    }
    
    # 网站数据
    WEBSITE_DATA = {
        "adabd": {
            "name": "A大补丁",
            "url": "https://www.caimogu.cc/post/2170680.html",
            "title_selector": "body > div.container.simple > div.content > div.post-content > div > div.title",
            "time_selector": "body > div.container.simple > div.content > div.post-content > div > div.post-action-container > div > span.publish-time"
        },
        "wenzi": {
            "name": "文子过滤",
            "url": "https://www.caimogu.cc/post/2154276.html",
            "title_selector": "body > div.container.simple > div.content > div.post-content > div > div.title",
            "time_selector": "body > div.container.simple > div.content > div.post-content > div > div.post-action-container > div > span.publish-time"
        },
        "yile": {
            "name": "一乐过滤",
            "url": "https://www.caimogu.cc/post/2156024.html",
            "title_selector": "body > div.container.simple > div.content > div.post-content > div > div.title",
            "time_selector": "body > div.container.simple > div.content > div.post-content > div > div.post-action-container > div > span.publish-time"
        },
        "eshua": {
            "name": "易刷查价",
            "url": "https://www.caimogu.cc/post/1621584.html",
            "title_selector": "body > div.container.simple > div.content > div.post-content > div > div.title",
            "time_selector": "body > div.container.simple > div.content > div.post-content > div > div.post-action-container > div > span.publish-time"
        }
    }
    
    # 网站名称
    WEBSITE_NAMES = {site_id: site_info["name"] for site_id, site_info in WEBSITE_DATA.items()}
    
    # 默认价格
    DEFAULT_PRICES = {
        "divine": 0.0,    # 神圣石默认价格
        "exalted": 0.0,   # 崇高石默认价格
        "chaos": 0.0,     # 混沌石默认价格
        "chance": 0.0,    # 机会石默认价格
    }
    
    # 自动喝药相关配置
    AUTO_FLASK = {
        "ahk_path": "C:\\Program Files\\AutoHotkey\\AutoHotkey.exe",       # AHK程序路径
        "ahk_install_url": "https://s.1232323.xyz/d/POE2/AHK/AutoHotkey_setup_1.1.exe",  # AHK安装程序下载URL
        "script_url": "https://s.1232323.xyz/d/POE2/AHK/auto_HPES.ahk",    # 自动喝药脚本下载URL
        "script_name": "auto_HPES.ahk"                                      # 脚本文件名
    }
    
    # 下载链接配置
    DOWNLOAD_LINKS = {
        "filter": "https://poe2.1232323.xyz/d/POE2PriceAid/filter/filter.7z",     # 过滤器下载链接
        "apatch": "https://poe2.1232323.xyz/d/POE2PriceAid/apatch/apatch.7z"      # A大补丁下载链接
    }
    
    # 导航链接配置
    NAVIGATION_LINKS = [
        ("编年史", "https://poe2db.tw/cn/"),
        ("官网", "https://poe2.qq.com/main.shtml"),
        ("忍者", "https://poe.ninja/poe2/builds"),
        ("市集", "https://poe.game.qq.com/trade2/search/poe2/"),
        ("易刷", "https://cyurl.cn/eshua")
    ]
    
    
    @staticmethod
    def get_app_icon_path():
        """获取应用图标路径"""
        if getattr(sys, 'frozen', False):
            # 如果是打包后的程序
            base_path = sys._MEIPASS
        else:
            # 如果是源代码运行
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        icon_path = os.path.join(base_path, 'app.ico')
        
        if os.path.exists(icon_path):
            return icon_path
        # 备用路径
        alt_path = os.path.join(os.path.dirname(base_path), 'app.ico')
        if os.path.exists(alt_path):
            return alt_path
        return None
    
    @staticmethod
    def get_app_data_dir():
        """获取应用数据目录"""
        app_data_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'POE2PriceAid')
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir 
        
    @staticmethod
    def get_resource_path(relative_path):
        """获取资源路径，支持打包后的资源访问
        
        Args:
            relative_path: 相对路径，例如 'scripts/auto_HPES.ahk'
            
        Returns:
            资源的完整路径
        """
        if getattr(sys, 'frozen', False):
            # 打包后的程序，使用_MEIPASS
            base_path = sys._MEIPASS
        else:
            # 源代码运行，使用项目根目录
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        resource_path = os.path.join(base_path, relative_path)
        return resource_path if os.path.exists(resource_path) else None
        
    @staticmethod
    def extract_resource_to_app_data(resource_path, dest_filename=None):
        """从资源中提取文件到AppData目录
        
        Args:
            resource_path: 相对于资源目录的路径
            dest_filename: 提取后的文件名（可选），默认使用源文件名
            
        Returns:
            提取后文件的完整路径，如果失败则返回None
        """
        # 获取资源路径
        src_path = Config.get_resource_path(resource_path)
        if not src_path:
            return None
            
        # 确定目标路径
        app_data_dir = Config.get_app_data_dir()
        if dest_filename is None:
            dest_filename = os.path.basename(resource_path)
            
        dest_path = os.path.join(app_data_dir, dest_filename)
        
        try:
            # 复制文件
            import shutil
            shutil.copy2(src_path, dest_path)
            return dest_path
        except Exception as e:
            print(f"提取资源文件失败: {str(e)}")
            return None
    
    @staticmethod
    def save_window_geometry(window):
        """保存窗口几何信息
        
        Args:
            window: 要保存几何信息的窗口对象
        """
        settings = QSettings()
        settings.setValue("MainWindow/geometry", window.saveGeometry())
        settings.setValue("MainWindow/state", window.saveState())
        settings.setValue("MainWindow/position", window.pos())
        settings.setValue("MainWindow/size", window.size())
    
    @staticmethod
    def load_window_geometry(window):
        """加载窗口几何信息
        
        Args:
            window: 要应用几何信息的窗口对象
            
        Returns:
            bool: 是否成功加载了几何信息
        """
        settings = QSettings()
        geometry = settings.value("MainWindow/geometry")
        if geometry:
            window.restoreGeometry(geometry)
            state = settings.value("MainWindow/state")
            if state:
                window.restoreState(state)
            return True
        return False
    
    @staticmethod
    def save_hidden_features_state():
        """保存隐藏功能状态到配置文件
        """
        settings = QSettings()
        settings.setValue("Features/hidden_enabled", Config.HIDDEN_FEATURES["enabled"])
    
    @staticmethod
    def load_hidden_features_state():
        """从配置文件加载隐藏功能状态
        
        Returns:
            bool: 隐藏功能是否已启用
        """
        settings = QSettings()
        enabled = settings.value("Features/hidden_enabled", False, type=bool)
        Config.HIDDEN_FEATURES["enabled"] = enabled
        return enabled 
