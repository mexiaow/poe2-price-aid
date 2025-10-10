"""
过滤器模块
实现过滤器的更新和安装功能
"""

import os
import time
import tempfile
import shutil
import subprocess
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFileDialog, QMessageBox, QApplication,
                            QProgressBar, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices

try:
    import requests
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup
except ImportError:
    pass

try:
    import py7zr
except ImportError:
    pass

from .config import Config


class FilterTab(QWidget):
    """过滤器标签页类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化属性
        self.game_path = ""
        self.filter_check_time = None
        self.update_check_interval = 60 * 60  # 60分钟检查一次
        
        # 初始化UI
        self.init_ui()
        
        # 自动检测游戏路径
        self.detect_game_path()
        
        # 延迟首轮获取与定时器启动由主窗口统一调度（避免启动时并发网络请求）
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.auto_check_update)
    
    def auto_check_update(self):
        """自动检查更新"""
        # 只有当距离上次检查时间超过1小时才进行检查
        if self.filter_check_time is None or (datetime.now() - self.filter_check_time).total_seconds() > self.update_check_interval:
            print("自动检查过滤器更新...")
            # 标记为自动更新
            self._auto_update = True
            # 获取更新时间
            self.get_filter_update_time()
    
    def get_filter_update_time(self):
        """获取过滤器最后更新时间"""
        try:
            # 如果已经有线程在运行，先停止它
            if hasattr(self, 'update_time_thread') and self.update_time_thread.isRunning():
                # 标记为手动刷新，但不重复创建线程
                self._auto_update = False
                return
                
            # 判断是否为自动更新
            if not hasattr(self, '_auto_update'):
                self._auto_update = not hasattr(self, 'update_time_thread')
            
            # 重置显示状态
            self.filter_update_time_label.setText("最后更新时间: 获取中...")
            self.filter_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FFA500; font-weight: bold;")
            
            # 禁用刷新按钮，避免重复点击
            if hasattr(self, 'refresh_time_button'):
                self.refresh_time_button.setEnabled(False)
                self.refresh_time_button.setText("获取中...")
            
            # 在GUI线程中立即更新
            QApplication.processEvents()
            
            # 确保所需库已安装
            self.ensure_required_libs()
            
            # 创建线程获取更新时间
            class UpdateTimeThread(QThread):
                update_time_found = pyqtSignal(str)
                finished = pyqtSignal()  # 添加完成信号
                
                def run(self):
                    try:
                        import requests
                        from bs4 import BeautifulSoup
                        
                        # 设置请求头部，模拟浏览器访问
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        
                        # 获取网页内容
                        url = "https://gitee.com/mexiaow/poe2-price-aid/blob/main/version_%E8%BF%87%E6%BB%A4%E5%99%A8.txt"
                        response = requests.get(url, headers=headers, timeout=10)
                        
                        if response.status_code == 200:
                            # 解析HTML
                            soup = BeautifulSoup(response.text, 'html.parser')
                            
                            # 查找时间元素
                            time_element = soup.select_one("#tree-content-holder > div.file_holder > div.file_title > div.contributor-description > span > span.timeago.commit-date")
                            
                            if time_element:
                                # 直接获取显示的相对时间
                                display_time = time_element.text.strip()
                                # 发送结果信号 - 直接使用相对时间
                                self.update_time_found.emit(f"最后更新时间: {display_time}")
                            else:
                                # 未找到时间元素，尝试备用方法
                                time_element = soup.select_one(".timeago.commit-date")
                                if time_element:
                                    display_time = time_element.text.strip()
                                    self.update_time_found.emit(f"最后更新时间: {display_time}")
                                else:
                                    # 未找到时间元素
                                    self.update_time_found.emit("最后更新时间: 无法获取")
                        else:
                            # 请求失败，尝试获取本地过滤器时间
                            local_time = self.try_get_local_filter_time()
                            if local_time:
                                self.update_time_found.emit(local_time)
                            else:
                                # 无法获取本地时间
                                self.update_time_found.emit("最后更新时间: 无法连接到服务器")
                    
                    except ImportError:
                        # 如果缺少required库
                        self.update_time_found.emit("最后更新时间: 缺少必要库(requests/bs4)")
                    except Exception as e:
                        # 其他错误，尝试获取本地过滤器时间
                        print(f"获取更新时间出错: {e}")
                        try:
                            local_time = self.try_get_local_filter_time()
                            if local_time:
                                self.update_time_found.emit(local_time)
                            else:
                                self.update_time_found.emit("最后更新时间: 获取失败")
                        except:
                            self.update_time_found.emit("最后更新时间: 获取失败")
                    
                    # 无论成功或失败，发送完成信号
                    self.finished.emit()
                
                def try_get_local_filter_time(self):
                    """尝试获取本地过滤器文件时间"""
                    try:
                        # 获取当前用户名
                        username = os.environ.get('USERNAME', '')
                        game_path = os.path.join("C:\\Users", username, "Documents", "My Games", "Path of Exile 2")
                        
                        # 查找过滤器文件
                        filter_files = []
                        if os.path.exists(game_path):
                            for file in os.listdir(game_path):
                                if file.endswith('.filter') or file == 'filter.txt':
                                    filter_files.append(os.path.join(game_path, file))
                        
                        if filter_files:
                            # 找到了过滤器文件，获取最新的一个
                            newest_filter = max(filter_files, key=os.path.getmtime)
                            mod_time = os.path.getmtime(newest_filter)
                            mod_datetime = datetime.fromtimestamp(mod_time)
                            formatted_time = mod_datetime.strftime('%Y-%m-%d %H:%M:%S')
                            filter_name = os.path.basename(newest_filter)
                            return f"最后更新时间: {formatted_time} (本地文件: {filter_name})"
                        
                        return None
                    except Exception as e:
                        print(f"获取本地过滤器时间出错: {e}")
                        return None
            
            # 创建并启动线程
            self.update_time_thread = UpdateTimeThread()
            self.update_time_thread.update_time_found.connect(self.update_time_label)
            self.update_time_thread.finished.connect(self.on_update_time_finished)
            self.update_time_thread.start()
            
            # 更新检查时间
            self.filter_check_time = datetime.now()
            
        except Exception as e:
            print(f"启动更新时间线程时出错: {e}")
            self.filter_update_time_label.setText("最后更新时间: 获取失败")
            self.filter_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FF0000; font-weight: bold;")
            
            # 恢复刷新按钮状态
            if hasattr(self, 'refresh_time_button'):
                self.refresh_time_button.setEnabled(True)
                self.refresh_time_button.setText("刷新")
    
    def on_update_time_finished(self):
        """更新时间获取完成的处理"""
        # 恢复刷新按钮状态
        if hasattr(self, 'refresh_time_button'):
            self.refresh_time_button.setEnabled(True)
            self.refresh_time_button.setText("刷新")
    
    def ensure_required_libs(self):
        """确保所需库已安装"""
        try:
            # 检查requests库
            try:
                import requests
            except ImportError:
                print("正在安装requests库...")
                self.install_pip_package("requests")
            
            # 检查BeautifulSoup库
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                print("正在安装beautifulsoup4库...")
                self.install_pip_package("beautifulsoup4")
            
            # 检查py7zr库
            try:
                import py7zr
            except ImportError:
                print("正在安装py7zr库...")
                self.install_pip_package("py7zr")
                
            return True
        except Exception as e:
            print(f"确保所需库安装时出错: {e}")
            return False
    
    def install_pip_package(self, package_name):
        """安装指定的pip包"""
        try:
            import subprocess
            import sys
            
            # 获取python解释器路径
            python_exec = sys.executable
            
            # 使用子进程安装
            subprocess.check_call([python_exec, "-m", "pip", "install", package_name], 
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            
            print(f"成功安装 {package_name}")
            return True
        except Exception as e:
            print(f"安装{package_name}失败: {e}")
            return False
    
    def update_time_label(self, time_text):
        """更新时间标签内容"""
        self.filter_update_time_label.setText(time_text)
        
        # 根据获取结果设置不同的样式
        if "获取失败" in time_text or "无法" in time_text:
            self.filter_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FF0000; font-weight: bold;")
            # 提示获取失败的原因，但只在非自动获取时显示
            if (not hasattr(self, '_auto_update') or not self._auto_update) and not time_text.endswith('(本地文件)'):
                QMessageBox.warning(self, "获取失败", 
                                  f"无法获取过滤器更新时间信息：\n{time_text}\n\n可能的原因：\n1. 网络连接问题\n2. 网站结构变更\n3. 所需库安装失败",
                                  QMessageBox.Ok)
        elif "获取中" in time_text:
            self.filter_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FFA500; font-weight: bold;")
        else:
            # 成功获取时只改变颜色，不显示弹窗
            self.filter_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #0078D7; font-weight: bold;")
    
    def init_ui(self):
        """初始化UI"""
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 创建左侧垂直布局用于整体左对齐
        left_aligned_layout = QVBoxLayout()
        left_aligned_layout.setAlignment(Qt.AlignLeft)
        left_aligned_layout.setSpacing(15)
        left_aligned_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建过滤器更新时间行
        update_time_layout = QHBoxLayout()
        update_time_layout.setContentsMargins(0, 0, 0, 0)
        update_time_layout.setSpacing(10)
        
        # 添加过滤器更新时间显示
        self.filter_update_time_label = QLabel("最后更新时间: 获取中...")
        self.filter_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FFA500; font-weight: bold;")
        self.filter_update_time_label.setContentsMargins(0, 0, 0, 0)
        self.filter_update_time_label.setAlignment(Qt.AlignLeft)
        update_time_layout.addWidget(self.filter_update_time_label)
        
        # 添加刷新按钮
        self.refresh_time_button = QPushButton("刷新")
        self.refresh_time_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.refresh_time_button.clicked.connect(self.get_filter_update_time)
        update_time_layout.addWidget(self.refresh_time_button)
        
        # 添加音效包下载按钮
        self.sound_pack_button = QPushButton("音效包下载")
        self.sound_pack_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6B35;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FF7D4D;
            }
            QPushButton:pressed {
                background-color: #E55A2B;
            }
        """)
        self.sound_pack_button.clicked.connect(self.open_sound_pack_download)
        update_time_layout.addWidget(self.sound_pack_button)

        # 添加清理过滤文件按钮
        self.clear_filters_button = QPushButton("清理过滤文件")
        self.clear_filters_button.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FF5555;
            }
            QPushButton:pressed {
                background-color: #CC3333;
            }
        """)
        self.clear_filters_button.clicked.connect(self.clear_filter_files)
        update_time_layout.addWidget(self.clear_filters_button)
        
        # 添加弹性空间推动刷新按钮靠右
        update_time_layout.addStretch(1)
        
        # 将更新时间行添加到左对齐布局
        left_aligned_layout.addLayout(update_time_layout)
        
        # 创建按钮的水平布局
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(15)
        button_row.setAlignment(Qt.AlignLeft)
        
        # 安装按钮 - 增加宽度确保文字完全显示
        self.install_button = QPushButton("安装过滤器")
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 16px;
                min-width: 160px;
                max-width: 160px;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        self.install_button.clicked.connect(self.install_filter)
        self.install_button.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self.install_button, 0, Qt.AlignLeft)
        
        # 打开目录按钮 - 增加宽度确保文字完全显示
        self.open_dir_button = QPushButton("打开过滤器目录")
        self.open_dir_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 16px;
                min-width: 140px;
                max-width: 140px;
            }
            QPushButton:hover {
                background-color: #5DBE60;
            }
            QPushButton:pressed {
                background-color: #3A8C3D;
            }
        """)
        self.open_dir_button.clicked.connect(self.open_filter_directory)
        self.open_dir_button.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self.open_dir_button, 0, Qt.AlignLeft)
        
        # 游戏路径显示 - 移到打开目录按钮右侧
        self.game_path_label = QLabel("游戏路径: 自动检测中...")
        self.game_path_label.setStyleSheet("font-size: 16px; color: #6A5ACD; margin-left: 15px;")  # 添加左边距
        button_row.addWidget(self.game_path_label)

        # 添加弹性空间
        button_row.addStretch(1)
        
        # 将按钮行添加到左对齐布局
        left_aligned_layout.addLayout(button_row)
        
        # 将左对齐布局添加到主布局
        layout.addLayout(left_aligned_layout)
        
        # 状态显示
        self.filter_status_label = QLabel("")
        self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #30B4FF;")  # 使用淡蓝色作为安装提示颜色
        self.filter_status_label.setWordWrap(True)
        layout.addWidget(self.filter_status_label)
        
        # 进度条 (初始隐藏)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid grey;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0078D7;
                width: 1px;
            }
        """)
        self.progress_bar.setVisible(False)  # 初始隐藏
        layout.addWidget(self.progress_bar)
        
        # 添加弹性空间
        layout.addStretch(1)
        
        # 说明文本
        description_label = QLabel("下载最新过滤器并替换至最新版")
        description_label.setStyleSheet("font-size: 14px; margin-top: 10px; color: #888888;")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
    
    def open_filter_directory(self):
        """打开过滤器目录"""
        try:
            # 确保路径存在
            if not self.game_path:
                # 尝试检测游戏路径
                self.detect_game_path()
                
            if not self.game_path:
                QMessageBox.warning(self, "无法打开目录", "游戏路径未设置或无法检测。", QMessageBox.Ok)
                return
                
            # 如果目录不存在，询问是否创建
            if not os.path.exists(self.game_path):
                reply = QMessageBox.question(self, "目录不存在", 
                                          f"目录 {self.game_path} 不存在，是否创建？",
                                          QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    try:
                        os.makedirs(self.game_path, exist_ok=True)
                    except Exception as e:
                        QMessageBox.critical(self, "创建目录失败", f"无法创建目录: {str(e)}", QMessageBox.Ok)
                        return
                else:
                    return
            
            # 尝试使用系统默认的文件资源管理器打开目录
            try:
                # 针对Windows系统
                if os.name == 'nt':
                    os.startfile(self.game_path)
                # 针对Linux系统
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', self.game_path])
                # 针对macOS系统
                elif os.name == 'mac':
                    subprocess.Popen(['open', self.game_path])
                else:
                    QMessageBox.warning(self, "无法打开目录", "不支持的操作系统类型。", QMessageBox.Ok)
            except Exception as e:
                QMessageBox.warning(self, "无法打开目录", f"打开目录时出错: {str(e)}", QMessageBox.Ok)
        except Exception as e:
            QMessageBox.warning(self, "操作失败", f"执行操作时出错: {str(e)}", QMessageBox.Ok)
    
    def detect_game_path(self):
        """检测游戏路径"""
        try:
            # 获取当前用户名
            username = os.environ.get('USERNAME', '')
            game_path = os.path.join("C:\\Users", username, "Documents", "My Games", "Path of Exile 2")
            
            # 简化显示路径，使用"主目录"替代"C:\Users\用户名"
            display_path = os.path.join("主目录", "Documents", "My Games", "Path of Exile 2")
            
            if os.path.exists(game_path):
                self.game_path_label.setText(f"游戏路径: {display_path}")
                self.game_path_label.setStyleSheet("font-size: 16px; color: #6A5ACD;")  # 使用紫色调
                self.game_path = game_path
            else:
                self.game_path_label.setText(f"游戏路径: {display_path} (将在安装时创建)")
                self.game_path_label.setStyleSheet("font-size: 16px; color: #6A5ACD;")  # 使用紫色调
                self.game_path = game_path  # 仍然设置路径，稍后会创建目录
        except Exception as e:
            print(f"检测游戏路径时出错: {e}")
            self.game_path_label.setText("游戏路径: 检测失败")
            self.game_path_label.setStyleSheet("font-size: 16px; color: #FF0000;")
    
    def open_sound_pack_download(self):
        """打开音效包下载链接"""
        try:
            sound_pack_url = "https://cyurl.cn/0s1fu"
            QDesktopServices.openUrl(QUrl(sound_pack_url))
        except Exception as e:
            QMessageBox.warning(self, "打开链接失败", f"无法打开音效包下载链接: {str(e)}", QMessageBox.Ok)

    def clear_filter_files(self):
        """清理过滤文件"""
        try:
            # 确认对话框
            reply = QMessageBox.question(
                self,
                "清理过滤文件",
                "确定要删除游戏目录下所有的 .filter 文件吗？\n\n此操作不可撤销！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # 获取游戏目录
            username = os.environ.get('USERNAME', '')
            game_dir = os.path.join("C:\\Users", username, "Documents", "My Games", "Path of Exile 2")

            if not os.path.exists(game_dir):
                QMessageBox.warning(self, "警告", f"游戏目录不存在：\n{game_dir}")
                return

            # 查找并删除所有.filter文件（仅根目录）
            deleted_files = []
            try:
                for file in os.listdir(game_dir):
                    if file.endswith('.filter'):
                        file_path = os.path.join(game_dir, file)
                        # 确保只处理文件，不处理文件夹
                        if os.path.isfile(file_path):
                            try:
                                os.remove(file_path)
                                deleted_files.append(file)
                            except Exception as e:
                                print(f"删除文件 {file} 失败: {e}")

                # 显示结果
                if deleted_files:
                    file_list = "\n".join(deleted_files)
                    QMessageBox.information(
                        self,
                        "清理完成",
                        f"成功删除了 {len(deleted_files)} 个过滤文件：\n\n{file_list}"
                    )
                else:
                    QMessageBox.information(self, "清理完成", "未找到任何 .filter 文件")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"清理过滤文件时出错：\n{str(e)}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"清理过滤文件时出错：\n{str(e)}")
    
    def install_filter(self):
        """安装过滤器到游戏目录"""
        try:
            # 显示下载状态并准备进度条
            self.filter_status_label.setText("正在下载过滤器文件...")
            self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #30B4FF;")  # 使用淡蓝色
            self.progress_bar.setValue(10)
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # 更新UI
            
            # 确保所需库已安装
            if not self.ensure_required_libs():
                self.filter_status_label.setText("安装必要库失败，无法下载过滤器")
                self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #FF0000;")
                self.progress_bar.setVisible(False)
                return
            
            # 创建线程执行安装过程
            class FilterInstallThread(QThread):
                progress_update = pyqtSignal(int, str)
                install_finished = pyqtSignal(bool, str)
                
                def __init__(self, game_path, parent=None):
                    super().__init__(parent)
                    self.game_path = game_path

                def backup_existing_filters(self):
                    """不再备份现有的过滤器文件，按原来的替换方式"""
                    # 根据用户要求，不再删除所有.filter文件和生成备份
                    # 直接跳过备份步骤，按原来的替换方式进行
                    pass
                
                def run(self):
                    try:
                        import requests
                        import py7zr

                        # 更新进度 - 备份现有过滤器
                        self.progress_update.emit(10, "正在备份现有过滤器文件...")

                        # 执行备份逻辑
                        try:
                            self.backup_existing_filters()
                        except Exception as e:
                            print(f"备份过滤器时出错: {e}")
                            # 备份失败不阻止安装，只是记录错误

                        # 更新进度
                        self.progress_update.emit(20, "正在下载过滤器文件...")

                        # 下载过滤器文件 - 使用7z格式
                        filter_url = Config.DOWNLOAD_LINKS["filter"]
                        
                        response = requests.get(filter_url, stream=True)
                        
                        if response.status_code != 200:
                            self.install_finished.emit(False, f"下载失败: HTTP错误 {response.status_code}")
                            return
                        
                        # 获取文件总大小
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        # 保存压缩文件到临时文件
                        tmp_archive_path = os.path.join(tempfile.gettempdir(), "poe2_filter.7z")
                        
                        with open(tmp_archive_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    # 计算下载进度
                                    if total_size > 0:
                                        progress = 20 + min(30, int(30 * downloaded / total_size))
                                        self.progress_update.emit(progress, f"正在下载: {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB")
                        
                        # 确保目录存在
                        if not os.path.exists(self.game_path):
                            os.makedirs(self.game_path, exist_ok=True)
                            self.progress_update.emit(55, f"已创建游戏目录: {self.game_path}")
                        
                        # 解压文件到游戏目录
                        self.progress_update.emit(60, "正在解压过滤器文件到游戏目录...")
                        
                        # 使用py7zr库解压7z文件，可以正确处理中文文件名
                        with py7zr.SevenZipFile(tmp_archive_path, mode='r') as archive:
                            archive.extractall(path=self.game_path)
                        
                        # 删除临时压缩文件
                        os.remove(tmp_archive_path)
                        
                        # 安装成功
                        self.progress_update.emit(100, "过滤器安装成功！已替换过滤文件")
                        self.install_finished.emit(True, f"过滤器安装成功！文件已替换至: {self.game_path}")
                        
                    except Exception as e:
                        import traceback
                        print(f"安装过滤器时出错: {traceback.format_exc()}")
                        self.install_finished.emit(False, f"安装过滤器时出错: {str(e)}")
            
            # 创建并启动线程
            self.filter_install_thread = FilterInstallThread(self.game_path)
            self.filter_install_thread.progress_update.connect(self.update_install_progress)
            self.filter_install_thread.install_finished.connect(self.on_filter_install_finished)
            self.filter_install_thread.start()
            
        except Exception as e:
            import traceback
            print(f"启动安装过滤器线程时出错: {traceback.format_exc()}")
            self.filter_status_label.setText(f"安装过滤器时出错: {str(e)}")
            self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #FF0000;")
            self.progress_bar.setVisible(False)
    
    def update_install_progress(self, progress, message):
        """更新安装进度"""
        self.progress_bar.setValue(progress)
        self.filter_status_label.setText(message)
        
        # 根据进度更新颜色
        if progress >= 100:
            self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #00FF00; font-weight: bold;")
        else:
            self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #30B4FF;")  # 使用淡蓝色
    
    def on_filter_install_finished(self, success, message):
        """过滤器安装完成的处理"""
        if success:
            self.filter_status_label.setText(message)
            self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #00FF00; font-weight: bold;")
            
            # 更新过滤器时间显示 - 延迟一秒再刷新，确保文件系统已更新
            QTimer.singleShot(1000, self.get_filter_update_time)
        else:
            self.filter_status_label.setText(message)
            self.filter_status_label.setStyleSheet("font-size: 16px; margin-top: 20px; color: #FF0000; font-weight: bold;")
            
            # 提示错误消息
            QMessageBox.critical(self, "安装失败", 
                               f"过滤器安装失败！\n{message}",
                               QMessageBox.Ok)
        
        self.progress_bar.setVisible(False) 
