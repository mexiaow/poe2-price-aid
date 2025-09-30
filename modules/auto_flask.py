"""
自动喝药模块
实现自动喝药功能选项卡和AHK脚本管理
"""

import os
import sys
import subprocess
import time
import webbrowser
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QApplication, 
                            QSpacerItem, QSizePolicy, QProgressBar,
                            QMessageBox, QGroupBox, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess

from modules.config import Config

try:
    import requests
    import psutil  # 导入psutil用于进程检测
except ImportError:
    pass


class DownloadThread(QThread):
    """下载线程类"""
    progress_updated = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    download_error = pyqtSignal(str)
    
    def __init__(self, url, save_path):
        """初始化下载线程
        
        Args:
            url: 下载URL
            save_path: 保存路径
        """
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.canceled = False
    
    def run(self):
        """运行下载线程"""
        try:
            # 发送请求获取内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 使用stream=True启用流式下载
            response = requests.get(self.url, headers=headers, stream=True, timeout=30)
            
            # 检查状态码
            if response.status_code != 200:
                self.download_error.emit(f"服务器返回错误状态码: {response.status_code}")
                return
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                self.download_error.emit("无法获取文件大小信息，可能是下载链接无效")
                return
            
            # 下载文件
            downloaded_size = 0
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.canceled:
                        return
                        
                    if chunk:  # 过滤掉保持连接活跃的空块
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # 更新进度
                        progress = int(downloaded_size * 100 / total_size)
                        self.progress_updated.emit(progress)
            
            # 检查下载是否完成
            if os.path.exists(self.save_path) and os.path.getsize(self.save_path) > 0:
                self.download_complete.emit(self.save_path)
            else:
                self.download_error.emit("下载的文件为空或不存在")
                if os.path.exists(self.save_path):
                    os.remove(self.save_path)
        
        except requests.exceptions.Timeout:
            self.download_error.emit("下载超时，请检查网络连接并重试")
        except Exception as e:
            self.download_error.emit(f"下载过程中出错: {str(e)}")


class AutoFlaskTab(QWidget):
    """自动喝药选项卡类"""
    
    def __init__(self):
        """初始化自动喝药选项卡"""
        super().__init__()
        
        # 从配置中获取AHK相关路径
        self.ahk_path = Config.AUTO_FLASK["ahk_path"]
        self.ahk_install_url = Config.AUTO_FLASK["ahk_install_url"]
        self.script_url = Config.AUTO_FLASK["script_url"]
        self.script_name = Config.AUTO_FLASK["script_name"]
        
        # 应用数据目录
        self.app_data_dir = Config.get_app_data_dir()
        self.script_path = os.path.join(self.app_data_dir, self.script_name)
        
        # 内置脚本资源路径
        self.script_resource_path = os.path.join('scripts', self.script_name)
        
        # POE2助手相关属性
        self.poe2_assistant_dir = r"D:\Game\POE2\assistant_donwloader_china\assistant_current"
        self.poe2_assistant_process = None
        
        # 下载线程
        self.download_thread = None
        self.ahk_process = None
        
        # 初始化UI
        self.init_ui()
        
        # 检查AHK和脚本状态
        QTimer.singleShot(500, self.check_status)
        
        # 创建定时器，定期检测脚本进程状态
        self.process_check_timer = QTimer()
        self.process_check_timer.timeout.connect(self.check_ahk_process)
        self.process_check_timer.start(2000)  # 每2秒检测一次
        
        # 初始检测脚本进程状态
        self.check_ahk_process()
    
    def init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        
        # ===== 状态组 =====
        status_group = QGroupBox()  # 移除标题
        status_layout = QVBoxLayout(status_group)
        
        # 状态信息在同一行显示
        status_row_layout = QHBoxLayout()
        
        # AHK状态
        self.ahk_label = QLabel("AutoHotkey:")
        self.ahk_label.setStyleSheet("font-weight: bold;")
        self.ahk_status_value = QLabel("检测中...")
        self.ahk_status_value.setStyleSheet("font-weight: bold;")
        status_row_layout.addWidget(self.ahk_label)
        status_row_layout.addWidget(self.ahk_status_value)
        
        # 添加间距
        status_row_layout.addSpacing(20)
        
        # 脚本运行状态
        self.process_label = QLabel("自动喝药:")
        self.process_label.setStyleSheet("font-weight: bold;")
        self.process_status_value = QLabel("检测中...")
        self.process_status_value.setStyleSheet("font-weight: bold;")
        status_row_layout.addWidget(self.process_label)
        status_row_layout.addWidget(self.process_status_value)
        
        # 添加间距
        status_row_layout.addSpacing(20)
        
        # POE2助手状态 (初始隐藏)
        self.poe2_info_label = QLabel("POE助手:")
        self.poe2_info_label.setStyleSheet("font-weight: bold;")
        self.poe2_info_label.setVisible(False)
        self.poe2_info_value = QLabel("未检测")
        self.poe2_info_value.setStyleSheet("font-weight: bold; background-color: #333333; border-radius: 3px; padding: 2px;")
        self.poe2_info_value.setVisible(False)
        status_row_layout.addWidget(self.poe2_info_label)
        status_row_layout.addWidget(self.poe2_info_value)
        
        # 添加弹性空间
        status_row_layout.addStretch()
        
        # 下载AHK按钮 (初始隐藏)
        self.download_ahk_btn = QPushButton("下载AHK")
        self.download_ahk_btn.setFixedWidth(120)
        self.download_ahk_btn.clicked.connect(self.download_ahk)
        self.download_ahk_btn.setEnabled(False)  # 暂时禁用
        self.download_ahk_btn.setStyleSheet("QPushButton { color: gray; }")
        self.download_ahk_btn.hide()
        status_row_layout.addWidget(self.download_ahk_btn)
        
        # 从资源提取脚本按钮 (初始隐藏)
        self.extract_script_btn = QPushButton("使用内置脚本")
        self.extract_script_btn.setFixedWidth(120)
        self.extract_script_btn.clicked.connect(self.extract_script)
        self.extract_script_btn.setEnabled(False)  # 暂时禁用
        self.extract_script_btn.setStyleSheet("QPushButton { color: gray; }")
        self.extract_script_btn.hide()
        status_row_layout.addWidget(self.extract_script_btn)
        
        # 下载脚本按钮 (初始隐藏)
        self.download_script_btn = QPushButton("下载脚本")
        self.download_script_btn.setFixedWidth(120)
        self.download_script_btn.clicked.connect(self.download_script)
        self.download_script_btn.setEnabled(False)  # 暂时禁用
        self.download_script_btn.setStyleSheet("QPushButton { color: gray; }")
        self.download_script_btn.hide()
        status_row_layout.addWidget(self.download_script_btn)
        
        status_layout.addLayout(status_row_layout)
        
        # 下载进度条 (初始隐藏)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.hide()
        status_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(status_group)
        
        # ===== 控制组 =====
        control_group = QGroupBox()  # 移除标题
        control_layout = QVBoxLayout(control_group)
        
        # 按钮布局
        self.buttons_layout = QHBoxLayout()
        
        # 启动按钮
        self.start_btn = QPushButton("打开脚本")
        self.start_btn.setFixedWidth(120)
        self.start_btn.clicked.connect(self.start_script)
        self.start_btn.setEnabled(False)  # 暂时禁用
        self.start_btn.setStyleSheet("QPushButton { color: gray; }")

        # 关闭按钮
        self.stop_btn = QPushButton("关闭脚本")
        self.stop_btn.setFixedWidth(120)
        self.stop_btn.clicked.connect(self.stop_script)
        self.stop_btn.setEnabled(False)  # 暂时禁用
        self.stop_btn.setStyleSheet("QPushButton { color: gray; }")

        # 打开配置目录按钮，宽度设为135
        self.open_config_dir_btn = QPushButton("打开配置目录")
        self.open_config_dir_btn.setFixedWidth(135)
        self.open_config_dir_btn.clicked.connect(self.open_config_directory)
        self.open_config_dir_btn.setEnabled(False)  # 暂时禁用
        self.open_config_dir_btn.setStyleSheet("QPushButton { color: gray; }")

        # POE2助手切换按钮 (初始隐藏)
        self.poe2_toggle_btn = QPushButton("启动助手")
        self.poe2_toggle_btn.setFixedWidth(120)
        self.poe2_toggle_btn.clicked.connect(self.toggle_poe2_assistant)
        self.poe2_toggle_btn.setEnabled(False)  # 暂时禁用
        self.poe2_toggle_btn.setStyleSheet("QPushButton { color: gray; }")
        self.poe2_toggle_btn.setVisible(False)  # 初始隐藏

        # 打开POE2助手目录按钮 (初始隐藏)
        self.open_poe2_dir_btn = QPushButton("打开助手目录")
        self.open_poe2_dir_btn.setFixedWidth(135)
        self.open_poe2_dir_btn.clicked.connect(self.open_poe2_directory)
        self.open_poe2_dir_btn.setEnabled(False)  # 暂时禁用
        self.open_poe2_dir_btn.setStyleSheet("QPushButton { color: gray; }")
        self.open_poe2_dir_btn.setVisible(False)  # 初始隐藏
        
        self.buttons_layout.addWidget(self.start_btn)
        self.buttons_layout.addWidget(self.stop_btn)
        self.buttons_layout.addWidget(self.open_config_dir_btn)
        self.buttons_layout.addWidget(self.poe2_toggle_btn)
        self.buttons_layout.addWidget(self.open_poe2_dir_btn)
        self.buttons_layout.addStretch()
        
        control_layout.addLayout(self.buttons_layout)
        
        main_layout.addWidget(control_group)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        # 创建POE2助手状态检查定时器，但不启动
        self.poe2_check_timer = QTimer()
        self.poe2_check_timer.timeout.connect(self.check_poe2_assistant_status)
        
        # 创建POE2助手状态标签（用于内部保持状态）
        self.poe2_assistant_status = QLabel("未检测")
        self.poe2_assistant_status.setVisible(False)
        self.poe2_assistant_path = QLabel("未找到")
        self.poe2_assistant_path.setVisible(False)
        
        # 如果隐藏功能已启用，立即应用
        if Config.HIDDEN_FEATURES.get("enabled", False):
            QTimer.singleShot(1000, self.apply_hidden_features)
    
    def check_status(self):
        """检查AHK和脚本状态"""
        # 检查AHK安装
        self.check_ahk_installation()
        
        # 检查脚本是否存在
        self.check_script_exists()
        
        # 检查脚本进程状态
        self.check_ahk_process()
    
    def check_ahk_installation(self):
        """检查AHK是否已安装"""
        if os.path.exists(self.ahk_path):
            # AHK已安装
            self.ahk_status_value.setText("已安装")
            self.ahk_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.download_ahk_btn.hide()
        else:
            # AHK未安装
            self.ahk_status_value.setText("未安装")
            self.ahk_status_value.setStyleSheet("color: #F44336; font-weight: bold;")
            self.download_ahk_btn.show()
    
    def check_script_exists(self):
        """检查自动喝药脚本是否存在"""
        if os.path.exists(self.script_path):
            # 脚本已存在
            self.process_status_value.setText("已存在")
            self.process_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.download_script_btn.hide()
            self.extract_script_btn.hide()
            
            # 如果AHK也已安装，保持按钮禁用状态（暂时禁用功能）
            # self.start_btn.setEnabled(os.path.exists(self.ahk_path))
        else:
            # 脚本不存在，检查是否有内置脚本资源
            has_embedded_script = Config.get_resource_path(self.script_resource_path) is not None
            
            if has_embedded_script:
                # 自动从内置资源提取脚本，无需用户干预
                self.auto_extract_script()
            else:
                # 如果没有内置资源，显示下载按钮
                self.process_status_value.setText("未找到")
                self.process_status_value.setStyleSheet("color: #F44336; font-weight: bold;")
                self.download_script_btn.show()
                self.extract_script_btn.hide()
                
                # 保持按钮禁用状态（暂时禁用功能）
                # self.start_btn.setEnabled(False)
    
    def open_config_directory(self):
        """打开脚本所在的配置目录"""
        if not os.path.exists(self.app_data_dir):
            # 如果目录不存在，先创建
            try:
                os.makedirs(self.app_data_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(
                    self, "打开失败",
                    f"无法创建配置目录: {str(e)}"
                )
                return
        
        try:
            # 使用操作系统默认的文件管理器打开目录
            if sys.platform == 'win32':
                os.startfile(self.app_data_dir)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', self.app_data_dir])
            else:  # Linux
                subprocess.run(['xdg-open', self.app_data_dir])
        except Exception as e:
            QMessageBox.critical(
                self, "打开失败",
                f"无法打开配置目录: {str(e)}\n\n请手动打开以下路径:\n{self.app_data_dir}"
            )
    
    def auto_extract_script(self):
        """自动从内置资源中提取脚本，不显示提示信息"""
        try:
            # 使用配置类的方法提取资源
            extracted_path = Config.extract_resource_to_app_data(self.script_resource_path)
            
            if extracted_path and os.path.exists(extracted_path):
                # 更新界面状态
                self.process_status_value.setText("已存在")
                self.process_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
                self.extract_script_btn.hide()
                self.download_script_btn.hide()
                
                # 保持按钮禁用状态（暂时禁用功能）
                # self.start_btn.setEnabled(os.path.exists(self.ahk_path))
            else:
                # 提取失败，显示手动提取按钮
                self.process_status_value.setText("提取失败")
                self.process_status_value.setStyleSheet("color: #F44336; font-weight: bold;")
                self.extract_script_btn.show()
                self.download_script_btn.show()
        except Exception as e:
            print(f"自动提取脚本失败: {str(e)}")
            # 提取失败，显示手动操作按钮
            self.process_status_value.setText("提取失败")
            self.process_status_value.setStyleSheet("color: #F44336; font-weight: bold;")
            self.extract_script_btn.show()
            self.download_script_btn.show()
    
    def extract_script(self):
        """从内置资源中提取脚本（用户手动触发）"""
        try:
            # 使用配置类的方法提取资源
            extracted_path = Config.extract_resource_to_app_data(self.script_resource_path)
            
            if extracted_path and os.path.exists(extracted_path):
                # 更新界面状态
                self.process_status_value.setText("已存在")
                self.process_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
                self.extract_script_btn.hide()
                self.download_script_btn.hide()
                
                # 保持按钮禁用状态（暂时禁用功能）
                # self.start_btn.setEnabled(os.path.exists(self.ahk_path))
                
                QMessageBox.information(
                    self, "提取完成", 
                    "自动喝药脚本已成功从程序中提取。\n如果已安装AutoHotkey，您现在可以点击「打开脚本」按钮启动脚本。"
                )
            else:
                raise Exception("无法从资源中提取脚本")
                
        except Exception as e:
            QMessageBox.critical(
                self, "提取失败", 
                f"从程序资源中提取脚本失败：\n{str(e)}\n\n请尝试使用「下载脚本」按钮从网络下载。"
            )
            # 如果提取失败，显示下载按钮作为备选
            self.download_script_btn.show()
    
    def download_ahk(self):
        """下载AHK安装程序"""
        # 询问用户是否确认下载
        reply = QMessageBox.question(
            self, "下载确认", 
            "将下载AutoHotkey安装程序。下载完成后需要手动安装。是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        
        if reply == QMessageBox.No:
            return
        
        # 创建临时文件夹保存安装程序
        temp_dir = os.path.join(self.app_data_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        save_path = os.path.join(temp_dir, "AutoHotkey_setup.exe")
        
        # 开始下载
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.download_ahk_btn.setEnabled(False)
        
        # 创建下载线程
        self.download_thread = DownloadThread(self.ahk_install_url, save_path)
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.download_complete.connect(self.on_ahk_download_complete)
        self.download_thread.download_error.connect(self.on_download_error)
        self.download_thread.start()
    
    def download_script(self):
        """下载自动喝药脚本"""
        # 开始下载
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.download_script_btn.setEnabled(False)
        
        # 创建下载线程
        self.download_thread = DownloadThread(self.script_url, self.script_path)
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.download_complete.connect(self.on_script_download_complete)
        self.download_thread.download_error.connect(self.on_download_error)
        self.download_thread.start()
    
    def update_progress(self, value):
        """更新进度条
        
        Args:
            value: 进度值 (0-100)
        """
        self.progress_bar.setValue(value)
    
    def on_ahk_download_complete(self, file_path):
        """AHK下载完成处理
        
        Args:
            file_path: 下载的文件路径
        """
        self.progress_bar.hide()
        # 保持按钮禁用状态（暂时禁用功能）
        # self.download_ahk_btn.setEnabled(True)
        
        # 弹出安装向导
        try:
            os.startfile(file_path)
            QMessageBox.information(
                self, "下载完成", 
                "AutoHotkey安装程序已下载并启动，请按照安装向导完成安装。\n安装完成后，请返回程序点击「刷新」按钮。"
            )
            
            # 添加刷新按钮
            if not hasattr(self, 'refresh_btn'):
                self.refresh_btn = QPushButton("刷新")
                self.refresh_btn.setFixedWidth(80)
                self.refresh_btn.clicked.connect(self.check_status)
                status_row_layout = self.ahk_status_value.parent().layout()
                if status_row_layout:
                    status_row_layout.addWidget(self.refresh_btn)
        except Exception as e:
            QMessageBox.warning(
                self, "启动失败", 
                f"无法自动启动安装程序，请手动运行：\n{file_path}\n\n错误信息: {str(e)}"
            )
    
    def on_script_download_complete(self, file_path):
        """脚本下载完成处理
        
        Args:
            file_path: 下载的文件路径
        """
        self.progress_bar.hide()
        # 保持按钮禁用状态（暂时禁用功能）
        # self.download_script_btn.setEnabled(True)
        
        # 更新状态
        self.process_status_value.setText("已存在")
        self.process_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.download_script_btn.hide()
        self.extract_script_btn.hide()
        
        # 保持按钮禁用状态（暂时禁用功能）
        # self.start_btn.setEnabled(os.path.exists(self.ahk_path))
        
        QMessageBox.information(
            self, "下载完成", 
            "自动喝药脚本已下载成功。\n如果已安装AutoHotkey，您现在可以点击「打开脚本」按钮启动脚本。"
        )
    
    def on_download_error(self, error_msg):
        """下载错误处理
        
        Args:
            error_msg: 错误信息
        """
        self.progress_bar.hide()
        # 保持按钮禁用状态（暂时禁用功能）
        # self.download_ahk_btn.setEnabled(True)
        # 保持按钮禁用状态（暂时禁用功能）
        # self.download_script_btn.setEnabled(True)
        
        QMessageBox.critical(
            self, "下载错误", 
            f"下载过程中发生错误：\n{error_msg}\n\n请检查网络连接并重试。"
        )
    
    def start_script(self):
        """启动自动喝药脚本"""
        if not os.path.exists(self.ahk_path):
            QMessageBox.warning(self, "无法启动", "AutoHotkey未安装，请先安装AutoHotkey。")
            return
        
        if not os.path.exists(self.script_path):
            QMessageBox.warning(self, "无法启动", "自动喝药脚本不存在，请先下载或提取脚本。")
            return
        
        # 先检查AutoHotkey是否已经在运行
        self.check_ahk_process()
        if self.process_status_value.text() == "已启动":
            QMessageBox.information(self, "已在运行", "AutoHotkey脚本已经在运行中。")
            return
        
        try:
            # 使用subprocess启动脚本
            self.ahk_process = QProcess()
            self.ahk_process.finished.connect(self.on_script_stopped)
            self.ahk_process.start(self.ahk_path, [self.script_path])
            
            # 延迟一点时间后检查进程状态，确保UI更新
            QTimer.singleShot(500, self.check_ahk_process)
            
        except Exception as e:
            QMessageBox.critical(
                self, "启动失败", 
                f"启动脚本时出错：\n{str(e)}\n\n请检查AutoHotkey安装是否正确。"
            )
    
    def stop_script(self):
        """停止自动喝药脚本"""
        # 先检查AutoHotkey是否真的在运行
        self.check_ahk_process()
        if self.process_status_value.text() != "已启动":
            QMessageBox.information(self, "未在运行", "AutoHotkey脚本当前未运行。")
            return
            
        try:
            # 尝试终止所有AutoHotkey进程
            if 'psutil' in sys.modules:
                for proc in psutil.process_iter(['name']):
                    if proc.info['name'] and 'autohotkey' in proc.info['name'].lower():
                        try:
                            proc.terminate()
                        except:
                            pass
                            
            # 如果通过QProcess启动的进程仍在运行，也尝试终止它
            if self.ahk_process and self.ahk_process.state() != QProcess.NotRunning:
                self.ahk_process.terminate()
                # 给进程一些时间来终止
                if not self.ahk_process.waitForFinished(3000):
                    self.ahk_process.kill()
            
            # 延迟一点时间后检查进程状态，确保UI更新
            QTimer.singleShot(500, self.check_ahk_process)
            
        except Exception as e:
            QMessageBox.critical(
                self, "停止失败", 
                f"停止脚本时出错：\n{str(e)}"
            )
    
    def on_script_stopped(self, exit_code, exit_status):
        """脚本停止处理
        
        Args:
            exit_code: 退出代码
            exit_status: 退出状态
        """
        # 更新进程状态
        QTimer.singleShot(500, self.check_ahk_process)
    
    def check_ahk_process(self):
        """检测AutoHotkey.exe进程是否正在运行"""
        try:
            if 'psutil' not in sys.modules:
                self.process_status_value.setText("无法检测")
                self.process_status_value.setStyleSheet("color: #FFC107; font-weight: bold;")
                return
                
            # 检测是否有AutoHotkey.exe进程正在运行
            is_running = False
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'autohotkey' in proc.info['name'].lower():
                    is_running = True
                    break
            
            if is_running:
                # 脚本进程正在运行
                self.process_status_value.setText("已启动")
                self.process_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
                
                # 保持按钮禁用状态（暂时禁用功能）
                # if os.path.exists(self.ahk_path) and os.path.exists(self.script_path):
                #     self.start_btn.setEnabled(False)
                #     self.stop_btn.setEnabled(True)
            else:
                # 脚本进程未运行
                self.process_status_value.setText("已关闭")
                self.process_status_value.setStyleSheet("color: #F44336; font-weight: bold;")
                
                # 保持按钮禁用状态（暂时禁用功能）
                # if os.path.exists(self.ahk_path) and os.path.exists(self.script_path):
                #     self.start_btn.setEnabled(True)
                #     self.stop_btn.setEnabled(False)
                    
        except Exception as e:
            print(f"检测AutoHotkey进程出错: {str(e)}")
            self.process_status_value.setText("检测错误")
            self.process_status_value.setStyleSheet("color: #FFC107; font-weight: bold;")

    def hideEvent(self, event):
        """当窗口隐藏时停止定时器"""
        # 暂停定时器，但不要停止，因为窗口可能会再次显示
        self.process_check_timer.stop()
        super().hideEvent(event)
        
    def showEvent(self, event):
        """当窗口显示时恢复定时器"""
        # 重新启动定时器并立即检查一次
        self.process_check_timer.start()
        self.check_ahk_process()
        super().showEvent(event)

    def closeEvent(self, event):
        """当窗口关闭时停止定时器"""
        self.process_check_timer.stop()
        if hasattr(self, 'poe2_check_timer') and self.poe2_check_timer.isActive():
            self.poe2_check_timer.stop()
        super().closeEvent(event)

    def apply_hidden_features(self):
        """应用隐藏功能"""
        # 仅当隐藏功能已启用时才显示POE2助手管理功能
        if Config.HIDDEN_FEATURES.get("enabled", False):
            # 显示POE2助手状态在顶部状态栏
            self.poe2_info_label.setVisible(True)
            self.poe2_info_value.setVisible(True)
            
            # 显示POE2助手相关按钮
            self.poe2_toggle_btn.setVisible(True)
            self.open_poe2_dir_btn.setVisible(True)
            
            # 检查POE2助手当前状态
            self.check_poe2_assistant()
            
            # 启动定时器，定期检查POE2助手状态
            if not self.poe2_check_timer.isActive():
                self.poe2_check_timer.start(3000)  # 每3秒检查一次
    
    def check_poe2_assistant(self):
        """检查POE2助手的安装状态"""
        # 查找POE2助手可执行文件
        poe2_exe = self.find_poe2_assistant_exe()
        
        if poe2_exe:
            # 保持按钮禁用状态（暂时禁用功能）
            # self.poe2_toggle_btn.setEnabled(True)
            
            # 检查进程状态
            self.check_poe2_assistant_status()
        else:
            # 未找到可执行文件
            error_html = "<span style='color: #F44336;'>未找到助手程序</span>"
            self.poe2_info_value.setText(error_html)
            self.poe2_info_value.setStyleSheet("font-weight: bold; background-color: #333333; border-radius: 3px; padding: 2px;")
            self.poe2_toggle_btn.setEnabled(False)
    
    def find_poe2_assistant_exe(self):
        """查找POE2助手可执行文件
        
        Returns:
            str: 可执行文件路径，未找到则返回None
        """
        try:
            # 检查目录是否存在
            if not os.path.exists(self.poe2_assistant_dir):
                return None
            
            # 寻找目录中的所有exe文件（排除cports.exe）
            for file in os.listdir(self.poe2_assistant_dir):
                if file.lower().endswith('.exe') and file.lower() != 'cports.exe':
                    return os.path.join(self.poe2_assistant_dir, file)
            
            return None
        except Exception as e:
            print(f"查找POE2助手失败: {str(e)}")
            return None
    
    def check_poe2_assistant_status(self):
        """检查POE2助手进程状态"""
        try:
            if 'psutil' not in sys.modules:
                error_html = "<span style='color: #FFC107;'>无法检测</span>"
                self.poe2_info_value.setText(error_html)
                self.poe2_info_value.setStyleSheet("font-weight: bold; background-color: #333333; border-radius: 3px; padding: 2px;")
                return
            
            # 获取POE2助手可执行文件名
            poe2_exe = self.find_poe2_assistant_exe()
            if not poe2_exe:
                return
                
            exe_name = os.path.basename(poe2_exe)
            
            # 检查进程是否在运行
            is_running = False
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
                        is_running = True
                        self.poe2_assistant_process = proc
                        break
                except:
                    pass
            
            if is_running:
                # 助手进程在运行
                status_text = "已启动"
                status_color = "#4CAF50"  # 绿色
                self.poe2_toggle_btn.setText("关闭助手")
                # 保持按钮禁用状态（暂时禁用功能）
                # self.poe2_toggle_btn.setEnabled(True)
            else:
                # 助手进程未运行
                status_text = "已关闭"
                status_color = "#F44336"  # 红色
                self.poe2_toggle_btn.setText("启动助手")
                # 保持按钮禁用状态（暂时禁用功能）
                # self.poe2_toggle_btn.setEnabled(poe2_exe is not None)
                self.poe2_assistant_process = None
            
            # 更新顶部信息栏的状态显示 - 使用HTML格式化不同颜色
            # 程序名为蓝色，状态词为白色，状态值保持原有的红/绿色
            status_html = f"<span style='color: #0078D7;'>{exe_name}</span> <span style='color: white;'>状态:</span> <span style='color: {status_color};'>{status_text}</span>"
            self.poe2_info_value.setText(status_html)
            self.poe2_info_value.setStyleSheet("font-weight: bold;")
            
        except Exception as e:
            print(f"检查POE2助手状态出错: {str(e)}")
            error_html = "<span style='color: #FFC107;'>检测错误</span>"
            self.poe2_info_value.setText(error_html)
            self.poe2_info_value.setStyleSheet("font-weight: bold; background-color: #333333; border-radius: 3px; padding: 2px;")
    
    def start_poe2_assistant(self):
        """启动POE2助手"""
        try:
            # 获取POE2助手可执行文件路径
            poe2_exe = self.find_poe2_assistant_exe()
            if not poe2_exe:
                # 静默处理，不再显示弹窗
                print("无法找到POE2助手可执行文件")
                return
            
            # 尝试启动进程
            subprocess.Popen(poe2_exe)
            
            # 延迟一点时间后检查进程状态
            QTimer.singleShot(1000, self.check_poe2_assistant_status)
            
            # 移除成功提示弹窗
        except Exception as e:
            # 仅保留失败的弹窗，因为这是真正的错误
            QMessageBox.critical(
                self, "启动失败", 
                f"启动POE2助手时出错：\n{str(e)}"
            )
    
    def stop_poe2_assistant(self):
        """停止POE2助手"""
        try:
            # 检查进程是否存在
            if not self.poe2_assistant_process:
                self.check_poe2_assistant_status()
                if not self.poe2_assistant_process:
                    # 静默处理，不再显示弹窗
                    print("POE2助手未运行")
                    return
            
            # 尝试关闭进程
            self.poe2_assistant_process.terminate()
            
            # 等待一会儿确认进程已关闭
            try:
                self.poe2_assistant_process.wait(timeout=5)
            except:
                # 如果等待超时，强制结束进程
                try:
                    self.poe2_assistant_process.kill()
                except:
                    pass
            
            # 更新状态
            QTimer.singleShot(1000, self.check_poe2_assistant_status)
            
            # 移除成功提示弹窗
        except Exception as e:
            # 仅保留失败的弹窗，因为这是真正的错误
            QMessageBox.critical(
                self, "停止失败", 
                f"停止POE2助手时出错：\n{str(e)}"
            )
    
    def open_poe2_directory(self):
        """打开POE2助手目录"""
        try:
            # 检查目录是否存在
            if not os.path.exists(self.poe2_assistant_dir):
                QMessageBox.warning(self, "打开失败", "POE2助手目录不存在")
                return
            
            # 打开目录
            os.startfile(self.poe2_assistant_dir)
        except Exception as e:
            QMessageBox.critical(
                self, "打开失败",
                f"无法打开POE2助手目录: {str(e)}\n\n请手动打开以下路径:\n{self.poe2_assistant_dir}"
            )
    
    # 添加新的切换函数，用于替代分开的启动和停止函数
    def toggle_poe2_assistant(self):
        """切换POE2助手的启动/停止状态"""
        # 先检测当前状态
        if self.poe2_toggle_btn.text() == "启动助手":
            # 当前是停止状态，需要启动
            self.start_poe2_assistant()
        else:
            # 当前是启动状态，需要停止
            self.stop_poe2_assistant() 