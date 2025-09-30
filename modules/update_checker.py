"""
更新检查器模块
提供自动更新和手动更新检查功能
"""

import os
import sys
import json
import re
import shutil
import subprocess
import tempfile
import time
from PyQt5.QtWidgets import (QMessageBox, QProgressDialog, QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal

try:
    import requests
except ImportError:
    pass


class CountdownUpdateDialog(QDialog):
    """带倒计时的更新确认对话框"""

    def __init__(self, parent=None, latest_version="", current_version="", countdown_seconds=5):
        super().__init__(parent)
        self.setWindowTitle("发现新版本")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(350, 150)

        self.result = None
        self.countdown_seconds = countdown_seconds
        self.original_countdown = countdown_seconds

        # 创建布局
        layout = QVBoxLayout()

        # 版本信息标签
        version_label = QLabel(f"发现新版本 {latest_version}，当前版本 {current_version}")
        layout.addWidget(version_label)

        # 询问标签
        self.question_label = QLabel("是否立即更新？")
        layout.addWidget(self.question_label)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 是按钮（带倒计时）
        self.yes_button = QPushButton(f"是 ({self.countdown_seconds})")
        self.yes_button.clicked.connect(self.accept_update)
        self.yes_button.setDefault(True)
        button_layout.addWidget(self.yes_button)

        # 否按钮
        self.no_button = QPushButton("否")
        self.no_button.clicked.connect(self.reject_update)
        button_layout.addWidget(self.no_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # 创建倒计时定时器
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # 每秒更新一次

    def update_countdown(self):
        """更新倒计时"""
        self.countdown_seconds -= 1
        if self.countdown_seconds > 0:
            # 更新按钮文本
            self.yes_button.setText(f"是 ({self.countdown_seconds})")
        else:
            # 倒计时结束，自动选择"是"
            self.countdown_timer.stop()
            self.accept_update()

    def accept_update(self):
        """用户选择更新"""
        self.countdown_timer.stop()
        self.result = True
        self.accept()

    def reject_update(self):
        """用户拒绝更新"""
        self.countdown_timer.stop()
        self.result = False
        self.reject()

    def get_result(self):
        """获取用户选择结果"""
        return self.result


class UpdateChecker(QObject):
    """更新检查器类"""
    
    # 信号定义
    update_available = pyqtSignal(str, str)  # 发现新版本时发送信号 (版本号, 下载URL)
    update_not_available = pyqtSignal()  # 没有新版本时发送信号
    update_error = pyqtSignal(str)  # 更新检查出错时发送信号
    
    def __init__(self, parent=None, current_version=None, update_url=None):
        """初始化更新检查器
        
        Args:
            parent: 父窗口对象
            current_version: 当前程序版本号
            update_url: 更新信息URL
        """
        super().__init__(parent)
        
        # 保存父窗口引用
        self.parent = parent
        
        # 当前版本和更新URL
        self.current_version = current_version
        self.update_url = update_url or "https://gitee.com/mexiaow/poe2-price-aid/raw/main/update.json"
        # 测试更新专用
        #self.update_url = update_url or "https://s4-share.xwat.cn/POE2PriceAid/update.json"
        
        # 更新状态标志
        self.is_updating = False
        self.download_canceled = False
        
        # 进度对话框
        self.progress_dialog = None
    
    def start_auto_check(self, delay_ms=5000):
        """启动延迟自动检查 (仅用于程序启动时的一次性检测，非周期性定时检测)
        
        本方法仅在程序启动后执行一次检测，不会设置周期性的定时检测。
        如需再次检测更新，请使用 check_updates_manually 方法。
        
        Args:
            delay_ms: 延迟毫秒数，默认5秒
        """
        QTimer.singleShot(delay_ms, self.check_for_updates)
    
    def check_for_updates(self):
        """静默检查更新，仅在有新版本时显示提示"""
        # 如果正在更新，则跳过
        if self.is_updating:
            return
        
        try:
            # 从本地文件读取更新信息
            # 自动检查不显示状态对话框，直接进行检查
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 发送请求获取更新信息
            response = requests.get(self.update_url, headers=headers, timeout=5, verify=True)
            update_info = json.loads(response.text)
            
            latest_version = update_info.get("version")
            download_url = update_info.get("download_url")
            
            # 比较版本号
            version_comparison = self.compare_versions(latest_version, self.current_version)

            if version_comparison > 0:
                # 有新版本可用，显示带倒计时的更新提示
                countdown_dialog = CountdownUpdateDialog(
                    parent=self.parent,
                    latest_version=latest_version,
                    current_version=self.current_version,
                    countdown_seconds=5
                )

                countdown_dialog.exec_()

                if countdown_dialog.get_result():
                    # 用户选择更新，下载并替换当前程序
                    self.download_and_replace(download_url)
            # 如果是最新版本，不显示任何提示
        
        except Exception as e:
            # 自动检查更新时出错，不显示提示，只记录日志
            print(f"自动检查更新时出错: {e}")
            self.update_error.emit(str(e))
    
    def check_updates_manually(self):
        """手动检查更新，显示所有结果"""
        # 如果正在更新，则跳过
        if self.is_updating:
            QMessageBox.information(self.parent, "正在更新", "更新已在进行中，请稍候...", QMessageBox.Ok)
            return
        
        try:
            # 创建可关闭的状态对话框
            status_dialog = QMessageBox(self.parent)
            status_dialog.setWindowTitle("检查更新")
            status_dialog.setText("正在检查更新，请稍候...")
            status_dialog.setStandardButtons(QMessageBox.Cancel)
            status_dialog.setIcon(QMessageBox.Information)
            
            # 创建一个定时器，如果检查时间过长，允许用户取消
            check_timer = QTimer(self.parent)
            check_timer.setSingleShot(True)
            check_timer.timeout.connect(lambda: self._perform_manual_update_check(status_dialog))
            check_timer.start(0)  # 立即开始检查
            
            # 显示对话框并等待用户响应
            result = status_dialog.exec_()
            
            # 如果用户取消，则停止检查
            if result == QMessageBox.Cancel:
                return
        
        except Exception as e:
            QMessageBox.critical(self.parent, "检查更新", f"检查更新时出错: {e}", QMessageBox.Ok)
            self.update_error.emit(str(e))
    
    def _perform_manual_update_check(self, status_dialog):
        """执行手动更新检查
        
        Args:
            status_dialog: 状态对话框
        """
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
                # 有新版本可用，显示带倒计时的更新提示
                countdown_dialog = CountdownUpdateDialog(
                    parent=self.parent,
                    latest_version=latest_version,
                    current_version=self.current_version,
                    countdown_seconds=5
                )

                countdown_dialog.exec_()

                if countdown_dialog.get_result():
                    # 用户选择更新，下载并替换当前程序
                    self.download_and_replace(download_url)
            else:
                # 已经是最新版本，显示提示
                # 使用静音消息框
                QMessageBox.information(self.parent, "检查更新", "当前已是最新版本。", QMessageBox.Ok)
                self.update_not_available.emit()
        
        except requests.exceptions.Timeout:
            # 处理请求超时
            status_dialog.done(0)  # 关闭状态对话框
            # 使用静音消息框
            QMessageBox.warning(self.parent, "检查更新", "检查更新超时，请稍后再试。", QMessageBox.Ok)
            self.update_error.emit("检查更新超时")
        except Exception as e:
            # 处理其他错误
            status_dialog.done(0)  # 关闭状态对话框
            QMessageBox.critical(self.parent, "检查更新", f"检查更新时出错: {e}", QMessageBox.Ok)
            self.update_error.emit(str(e))
    
    def compare_versions(self, version1, version2):
        """比较两个版本号
        
        Args:
            version1: 第一个版本号
            version2: 第二个版本号
            
        Returns:
            1 如果 version1 > version2
            -1 如果 version1 < version2
            0 如果相等
        """
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
        """下载并替换当前程序
        
        Args:
            download_url: 下载URL
        """
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
            self.progress_dialog = QProgressDialog("正在下载更新...", "取消", 0, 100, self.parent)
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
                QMessageBox.critical(self.parent, "下载失败", f"服务器返回错误状态码: {response.status_code}")
                self.is_updating = False
                return
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                self.progress_dialog.close()
                QMessageBox.critical(self.parent, "下载失败", "无法获取文件大小信息，可能是下载链接无效")
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
                QMessageBox.critical(self.parent, "更新失败", "下载的文件为空或者不存在")
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

echo 更新成功！正在启动新版本程序...

rem 启动新版本程序
start "" "{exe_dir}\\{new_exe_name}"

rem 延迟删除自身
ping 127.0.0.1 -n 2 > nul
del "%~f0"
exit
""")
            
            # 提示用户更新，使用新版本号
            countdown_seconds = 5
            msg_box = QMessageBox(self.parent)
            msg_box.setWindowTitle("下载完成")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(f"程序将在 {countdown_seconds} 秒后关闭并进行更新。\n更新完成后将自动启动新版本 {new_exe_name}。")
            msg_box.setStandardButtons(QMessageBox.NoButton)  # 不显示按钮
            msg_box.setModal(False)  # 设置为非模态对话框
            msg_box.show()
            
            # 创建倒计时定时器
            countdown_timer = QTimer(self.parent)
            
            def update_countdown():
                nonlocal countdown_seconds
                countdown_seconds -= 1
                if countdown_seconds > 0:
                    # 更新对话框文本，显示剩余时间
                    msg_box.setText(f"程序将在 {countdown_seconds} 秒后关闭并进行更新。\n更新完成后将自动启动新版本 {new_exe_name}。")
                else:
                    # 倒计时结束，关闭定时器和对话框
                    countdown_timer.stop()
                    msg_box.close()
                    
                    # 启动更新脚本并退出
                    subprocess.Popen([updater_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    QTimer.singleShot(500, self.parent.close)
                    QTimer.singleShot(1000, lambda: sys.exit(0))
            
            # 设置定时器每秒触发一次
            countdown_timer.timeout.connect(update_countdown)
            countdown_timer.start(1000)
        
        except Exception as e:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self.parent, "更新失败", f"更新过程中出错: {e}")
            self.update_error.emit(str(e))
    
    def cancel_download(self):
        """取消下载"""
        self.download_canceled = True
        self.is_updating = False 