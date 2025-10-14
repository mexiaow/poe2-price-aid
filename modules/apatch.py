"""
A大补丁模块
实现补丁下载和安装功能
"""

import os
import time
import tempfile
import shutil
import glob
import winreg
import subprocess
import ctypes
import string
import json  # 添加 JSON 模块导入
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFileDialog, QMessageBox, QApplication,
                            QProgressBar, QSpacerItem, QSizePolicy, QDialog, QTextEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon
import re

try:
    import requests
except ImportError:
    pass

try:
    import psutil
except ImportError:
    pass

from .config import Config


class APatchInstallThread(QThread):
    """A大补丁安装线程类"""
    progress_update = pyqtSignal(int, str)
    install_finished = pyqtSignal(bool, str)

    def __init__(self, game_path, parent=None):
        super().__init__(parent)
        self.game_path = game_path
        # 从配置中获取下载链接
        self.patch_file_url = Config.DOWNLOAD_LINKS["apatch"]
        self.extracted_files = []  # 记录解压的文件列表
        self.replacement_failure = False  # 记录替换是否失败
        self.failed_files = []  # 记录替换失败的文件
        self.install_log = []  # 保存安装日志
    
    def add_log(self, message):
        """添加日志记录"""
        import time
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_entry = f"[{timestamp}] {message}"
        self.install_log.append(log_entry)
        print(log_entry)

    def run(self):
        try:
            self.add_log("开始安装A大补丁")

            # 1. 下载补丁文件
            self.progress_update.emit(5, "正在下载补丁文件...")
            self.add_log("正在下载补丁文件...")
            patch_file_path = self.download_patch(self.patch_file_url)
            if not patch_file_path:
                self.add_log("下载补丁文件失败")
                self.install_finished.emit(False, "下载补丁文件失败")
                return
            self.add_log(f"补丁文件下载成功: {patch_file_path}")

            # 2. 列出并记录压缩包内容
            self.progress_update.emit(40, "正在解析补丁文件...")
            self.add_log("正在解析补丁文件...")
            file_list = self.list_7z_contents(patch_file_path)
            if not file_list:
                self.add_log("无法读取补丁文件内容")
                self.install_finished.emit(False, "无法读取补丁文件内容")
                return
            self.add_log(f"补丁文件包含: {file_list}")

            # 3. 创建临时目录用于解压
            temp_extract_dir = os.path.join(tempfile.gettempdir(), f"apatch_temp_{int(time.time())}")
            os.makedirs(temp_extract_dir, exist_ok=True)
            self.progress_update.emit(45, f"已创建临时目录: {temp_extract_dir}")
            self.add_log(f"已创建临时目录: {temp_extract_dir}")

            # 4. 解压到临时目录
            self.progress_update.emit(50, "正在解压补丁文件到临时目录...")
            self.add_log("正在解压补丁文件到临时目录...")

            # 尝试解压到临时目录
            extract_success = self.extract_to_temp(patch_file_path, temp_extract_dir)
            if not extract_success:
                self.add_log("解压补丁文件到临时目录失败")
                self.install_finished.emit(False, "解压补丁文件到临时目录失败")
                # 清理临时目录
                self.clean_temp_dir(temp_extract_dir)
                return
            self.add_log("补丁文件解压成功")

            # 5. 获取解压后的文件列表
            extracted_files = self.get_extracted_files(temp_extract_dir)
            if not extracted_files:
                self.add_log("解压后未找到有效文件")
                self.install_finished.emit(False, "解压后未找到有效文件")
                # 清理临时目录
                self.clean_temp_dir(temp_extract_dir)
                return
            self.add_log(f"解压得到文件: {extracted_files}")

            # 6. 新的安装流程 - 直接替换Bundles2文件夹下的文件
            self.progress_update.emit(70, "正在备份原文件...")
            self.add_log("正在备份原文件...")
            if not self.backup_original_files():
                self.add_log("备份原文件失败")
                self.install_finished.emit(False, "备份原文件失败")
                # 清理临时目录
                self.clean_temp_dir(temp_extract_dir)
                return
            self.add_log("原文件备份完成")

            # 7. 替换目标文件
            self.progress_update.emit(80, "正在替换补丁文件...")
            self.add_log("正在替换补丁文件...")
            if not self.replace_patch_files(temp_extract_dir, extracted_files):
                self.add_log("替换补丁文件失败")
                self.install_finished.emit(False, "替换补丁文件失败")
                # 清理临时目录
                self.clean_temp_dir(temp_extract_dir)
                return
            self.add_log("补丁文件替换完成")

            # === 以下为旧的PatchGGPK.exe相关步骤，已注释掉 ===
            # # 6. 复制文件到游戏目录
            # self.progress_update.emit(70, "正在复制文件到游戏目录...")
            # if not self.copy_files_to_game_dir(temp_extract_dir, self.game_path, extracted_files):
            #     self.install_finished.emit(False, "复制文件到游戏目录失败")
            #     # 清理临时目录
            #     self.clean_temp_dir(temp_extract_dir)
            #     return
            #
            # # 7. 检查PatchGGPK.exe
            # self.progress_update.emit(80, "正在准备运行补丁程序...")
            # patch_exe = os.path.join(self.game_path, "PatchGGPK.exe")
            # if not os.path.exists(patch_exe):
            #     self.install_finished.emit(False, f"未找到PatchGGPK.exe文件: {patch_exe}")
            #     # 清理临时目录
            #     self.clean_temp_dir(temp_extract_dir)
            #     return
            #
            # # 8. 运行补丁程序
            # if not self.run_patch_program(patch_exe):
            #     self.install_finished.emit(False, "运行补丁程序失败")
            #     # 清理临时目录
            #     self.clean_temp_dir(temp_extract_dir)
            #     return
            #
            # # 等待较长时间确保补丁程序完成对文件的操作
            # max_wait_time = 60  # 最多等待60秒
            # wait_interval = 5   # 每5秒检查一次
            # start_wait_time = time.time()
            #
            # while self.is_process_running("PatchGGPK.exe") and time.time() - start_wait_time < max_wait_time:
            #     self.progress_update.emit(89, f"等待补丁程序完成... ({int(time.time() - start_wait_time)}秒)")
            #     time.sleep(wait_interval)
            #
            # # 再等待5秒确保文件释放
            # time.sleep(5)
            #
            # # 9. 清理游戏目录中的临时工具文件
            # self.progress_update.emit(90, "正在清理游戏目录中的临时文件...")
            #
            # # 保存要清理的文件列表
            # tool_files_to_clean = []
            #
            # # 需要清理的文件列表 - 常见的A大补丁工具文件
            # common_tool_files = [
            #     "A大补丁+原版字体.zip",
            #     "Ionic.Zip.dll",
            #     "LibDat.dll",
            #     "LibGGPK.dll",
            #     "Newtonsoft.Json.dll",
            #     "PatchGGPK.exe",
            #     "一键安装.bat"
            # ]
            #
            # # 首先添加我们已知的工具文件
            # for file in common_tool_files:
            #     tool_file_path = os.path.join(self.game_path, file)
            #     if os.path.exists(tool_file_path):
            #         tool_files_to_clean.append(tool_file_path)
            #
            # # 再添加从解压文件中检测到的文件（可能有未知的工具文件）
            # for file in extracted_files:
            #     # 排除可能是游戏文件的子目录，只清理根目录下的工具文件
            #     if "/" not in file and "\\" not in file:
            #         tool_file_path = os.path.join(self.game_path, file)
            #         if os.path.exists(tool_file_path) and tool_file_path not in tool_files_to_clean:
            #             tool_files_to_clean.append(tool_file_path)
            #
            # # 删除工具文件
            # self.cleanup_game_dir_files(tool_files_to_clean)
            
            # 8. 清理临时文件和目录
            self.progress_update.emit(95, "正在清理临时目录...")
            self.add_log("正在清理临时目录...")
            self.clean_temp_dir(temp_extract_dir)

            # 删除下载的补丁文件
            if os.path.exists(patch_file_path):
                try:
                    os.remove(patch_file_path)
                    self.add_log(f"已删除下载的补丁文件: {patch_file_path}")
                except Exception as e:
                    self.add_log(f"无法删除补丁文件: {e}")

            # 9. 完成
            self.progress_update.emit(100, "补丁安装成功！")
            self.add_log("A大补丁安装成功！")
            self.install_finished.emit(True, "A大补丁安装成功！")

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.add_log(f"安装A大补丁时出错: {error_details}")
            print(f"安装A大补丁时出错: {error_details}")
            self.install_finished.emit(False, f"安装过程出错: {str(e)}")
    
    def backup_original_files(self):
        """备份原始文件到“@A大补丁还原@/backup_YYYYMMDD_HHMMSS”，并保留最近3次历史"""
        try:
            import shutil
            from datetime import datetime

            # 指定要备份的文件和目录（Bundles2 目录中的文件和目录结构）
            items_to_backup = [
                "_.index.bin",
                "Tiny.V0.1.bundle.bin",
                "LibGGPK3"  # 整个 LibGGPK3 目录
            ]

            # 源文件目录（Bundles2 文件夹）
            bundles2_path = os.path.join(self.game_path, "Bundles2")
            if not os.path.exists(bundles2_path):
                self.add_log(f"Bundles2目录不存在: {bundles2_path}")
                return False

            # 备份根目录：<game_path>/@A大补丁还原@
            backup_root = os.path.join(self.game_path, "@A大补丁还原@")
            os.makedirs(backup_root, exist_ok=True)

            # 在备份根目录写入固定说明文件：还原方法.txt
            try:
                restore_tip_path = os.path.join(backup_root, "还原方法.txt")
                with open(restore_tip_path, "w", encoding="utf-8") as f:
                    f.write("选择你需要还原的备份文件夹'backup_YYYYMMDD_HHMMSS',将备份文件夹内所有文件覆盖到游戏目录Bundles2文件夹下")
            except Exception as e:
                # 写入失败不影响备份流程
                self.add_log(f"写入还原方法说明失败: {e}")

            # 时间戳目录：backup_YYYYMMDD_HHMMSS
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(backup_root, f"backup_{timestamp}")
            os.makedirs(backup_dir, exist_ok=True)
            self.add_log(f"已创建新的备份目录: {backup_dir}")

            # 备份指定的文件和目录
            backup_success_count = 0
            for item_path in items_to_backup:
                source_path = os.path.join(bundles2_path, item_path)

                if os.path.exists(source_path):
                    destination_path = os.path.join(backup_dir, item_path)
                    try:
                        if os.path.isfile(source_path):
                            # 备份文件
                            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                            shutil.copy2(source_path, destination_path)
                            self.add_log(f"已备份文件: {item_path}")
                        elif os.path.isdir(source_path):
                            # 备份目录
                            shutil.copytree(source_path, destination_path)
                            self.add_log(f"已备份目录: {item_path}")

                        backup_success_count += 1
                    except Exception as e:
                        self.add_log(f"备份失败 {item_path}: {e}")
                else:
                    self.add_log(f"源文件/目录不存在，跳过备份: {item_path}")

            # 清理只保留最近3次历史备份
            try:
                entries = []
                for name in os.listdir(backup_root):
                    path = os.path.join(backup_root, name)
                    if os.path.isdir(path) and name.startswith("backup_"):
                        try:
                            mtime = os.path.getmtime(path)
                        except Exception:
                            mtime = 0
                        entries.append((name, path, mtime))

                # 按修改时间从新到旧排序
                entries.sort(key=lambda x: x[2], reverse=True)

                # 多于3个则删除多余的旧备份
                if len(entries) > 3:
                    to_delete = entries[3:]
                    for name, path, _ in to_delete:
                        try:
                            shutil.rmtree(path, ignore_errors=True)
                            self.add_log(f"已删除过期备份: {path}")
                        except Exception as e:
                            self.add_log(f"删除过期备份失败 {path}: {e}")
                self.add_log("历史备份保留：最近3次")
            except Exception as e:
                # 清理失败不影响备份结果，但记录日志
                self.add_log(f"清理历史备份时出错: {e}")

            # 备份成功（即使某些文件不存在也算成功，因为首次安装时可能没有这些文件）
            self.add_log(f"备份完成，成功备份了 {backup_success_count} 个项目")
            return True

        except Exception as e:
            self.add_log(f"备份原文件时出错: {e}")
            return False

    def replace_patch_files(self, temp_extract_dir, extracted_files):
        """替换补丁文件到Bundles2目录"""
        try:
            import shutil

            # 目标目录（Bundles2文件夹）
            bundles2_path = os.path.join(self.game_path, "Bundles2")
            if not os.path.exists(bundles2_path):
                self.add_log(f"Bundles2目录不存在: {bundles2_path}")
                return False

            # 过滤出需要处理的文件（排除目录）
            files_to_process = []
            for extracted_file in extracted_files:
                source_file = os.path.join(temp_extract_dir, extracted_file)
                if os.path.exists(source_file) and os.path.isfile(source_file):
                    files_to_process.append(extracted_file)

            total_files = len(files_to_process)
            if total_files == 0:
                self.add_log("没有找到任何有效的补丁文件")
                return False

            self.add_log(f"准备替换 {total_files} 个文件到Bundles2目录")

            # 记录成功替换的文件，用于出错时回滚
            replaced_files = []
            failed_files = []

            # 遍历所有需要处理的文件
            for i, extracted_file in enumerate(files_to_process):
                try:
                    # 源文件路径
                    source_file = os.path.join(temp_extract_dir, extracted_file)

                    # 处理目标路径 - 保持原有的目录结构
                    destination_file = os.path.join(bundles2_path, extracted_file)

                    # 确保目标目录存在
                    target_dir = os.path.dirname(destination_file)
                    os.makedirs(target_dir, exist_ok=True)

                    # 复制文件
                    shutil.copy2(source_file, destination_file)
                    self.add_log(f"已替换: {extracted_file}")
                    replaced_files.append((extracted_file, destination_file))

                    # 更新进度
                    progress = 80 + int((i + 1) / total_files * 15)  # 80-95%之间
                    self.progress_update.emit(progress, f"正在替换文件 ({i+1}/{total_files})...")

                except Exception as e:
                    error_msg = f"替换文件失败 {extracted_file}: {e}"
                    self.add_log(error_msg)
                    failed_files.append((extracted_file, str(e)))

            # 检查是否所有文件都成功替换
            if failed_files:
                self.add_log(f"有 {len(failed_files)} 个文件替换失败，补丁安装不完整")
                for failed_file, error in failed_files:
                    self.add_log(f"失败文件: {failed_file} - {error}")

                # 由于补丁不完整，返回失败
                self.add_log("由于文件替换不完整，补丁安装失败")
                return False

            # 所有文件都成功替换
            self.add_log(f"成功替换了所有 {len(replaced_files)} 个补丁文件")
            return True

        except Exception as e:
            self.add_log(f"替换补丁文件时出错: {e}")
            return False

    def extract_to_temp(self, patch_file_path, temp_dir):
        """解压文件到临时目录"""
        try:
            self.progress_update.emit(55, "解压文件到临时目录...")
            
            # 尝试多种解压方法
            extraction_methods = [
                self._extract_with_py7zr,
                self._extract_with_zipfile,
                self._extract_with_7zip_cmd,
                self._extract_with_powershell
            ]
            
            for extract_method in extraction_methods:
                try:
                    self.progress_update.emit(58, f"尝试使用{extract_method.__name__}方法解压...")
                    if extract_method(patch_file_path, temp_dir):
                        # 检查是否解压出了任何文件（不再检查PatchGGPK.exe）
                        try:
                            if os.path.exists(temp_dir) and os.listdir(temp_dir):  # 如果临时目录存在且不为空
                                self.progress_update.emit(60, "补丁文件成功解压到临时目录！")
                                return True
                        except Exception as check_error:
                            print(f"检查解压结果时出错: {check_error}")
                            continue
                except Exception as method_error:
                    print(f"{extract_method.__name__}解压到临时目录失败: {method_error}")
            
            # 所有方法都失败
            return False
            
        except Exception as e:
            print(f"解压到临时目录失败: {e}")
            return False
            
    def get_extracted_files(self, temp_dir):
        """获取解压后的文件列表"""
        try:
            file_list = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, temp_dir)
                    file_list.append(rel_path)
            
            print(f"解压得到以下文件: {file_list}")
            return file_list
            
        except Exception as e:
            print(f"获取解压文件列表失败: {e}")
            return []
            
    def copy_files_to_game_dir(self, source_dir, target_dir, file_list):
        """复制文件到游戏目录"""
        try:
            import shutil
            
            # 创建目标目录(如果不存在)
            os.makedirs(target_dir, exist_ok=True)
            
            # 复制文件到游戏目录
            for file in file_list:
                source_file = os.path.join(source_dir, file)
                target_file = os.path.join(target_dir, file)
                
                # 创建目标文件所在的目录(如果不存在)
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                
                # 复制文件
                shutil.copy2(source_file, target_file)
                print(f"已复制: {source_file} -> {target_file}")
                
                # 更新进度
                progress = 70 + int(10 * file_list.index(file) / len(file_list))
                self.progress_update.emit(progress, f"正在复制: {file}")
            
            return True
            
        except Exception as e:
            print(f"复制文件到游戏目录失败: {e}")
            return False
            
    def clean_temp_dir(self, temp_dir):
        """清理临时目录"""
        try:
            import shutil
            
            # 检查目录是否存在
            if os.path.exists(temp_dir):
                # 删除整个目录
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"已清理临时目录: {temp_dir}")
            
            return True
            
        except Exception as e:
            print(f"清理临时目录失败: {e}")
            return False
    
    def is_game_running(self):
        """检查游戏是否正在运行"""
        try:
            import subprocess
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq PathOfExile.exe', '/NH'], 
                                   capture_output=True, text=True)
            return "PathOfExile.exe" in result.stdout
        except Exception as e:
            print(f"检查游戏进程时出错: {e}")
            return False  # 出错时默认假设游戏没在运行 
    
    def _extract_with_py7zr(self, patch_file_path, temp_dir):
        """使用py7zr库解压"""
        try:
            import py7zr
            if patch_file_path.lower().endswith('.7z'):
                with py7zr.SevenZipFile(patch_file_path, mode='r') as z:
                    z.extractall(path=temp_dir)
                return True
            return False
        except Exception as e:
            print(f"py7zr解压失败: {e}")
            return False
            
    def _extract_with_zipfile(self, patch_file_path, temp_dir):
        """使用zipfile库解压"""
        try:
            import zipfile
            if patch_file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(patch_file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                return True
            return False
        except Exception as e:
            print(f"zipfile解压失败: {e}")
            return False
            
    def _extract_with_7zip_cmd(self, patch_file_path, temp_dir):
        """使用系统7zip命令行解压"""
        try:
            sevenzip_path = "C:\\Program Files\\7-Zip\\7z.exe"
            if not os.path.exists(sevenzip_path):
                sevenzip_path = "C:\\Program Files (x86)\\7-Zip\\7z.exe"
            
            if os.path.exists(sevenzip_path):
                import subprocess
                cmd = f'"{sevenzip_path}" x -y "{patch_file_path}" -o"{temp_dir}"'
                print(f"执行命令: {cmd}")
                subprocess.run(cmd, shell=True, check=True, capture_output=True)
                return True
            return False
        except Exception as e:
            print(f"7zip命令行解压失败: {e}")
            return False
            
    def _extract_with_powershell(self, patch_file_path, temp_dir):
        """使用PowerShell解压"""
        try:
            import subprocess
            
            # 对于zip文件
            if patch_file_path.lower().endswith('.zip'):
                ps_command = f'Expand-Archive -LiteralPath "{patch_file_path}" -DestinationPath "{temp_dir}" -Force'
                subprocess.run(['powershell', '-Command', ps_command], check=True, capture_output=True)
                return True
            
            return False
        except Exception as e:
            print(f"PowerShell解压失败: {e}")
            return False
    
    def cleanup_game_dir_files(self, file_list):
        """清理游戏目录中的文件"""
        try:
            # 先检查PatchGGPK.exe是否还在运行
            if self.is_process_running("PatchGGPK.exe"):
                print("PatchGGPK.exe仍在运行，跳过文件清理")
                return False
                
            for file_path in file_list:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"已删除: {file_path}")
                except Exception as e:
                    print(f"删除文件失败 {file_path}: {e}")
            
            return True
        except Exception as e:
            print(f"清理游戏目录文件失败: {e}")
            return False
    
    def list_7z_contents(self, archive_path):
        """列出7z或zip文件内容"""
        try:
            # 根据文件扩展名选择不同的处理方法
            if archive_path.lower().endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    return zip_ref.namelist()
            elif archive_path.lower().endswith('.7z'):
                try:
                    import py7zr
                    with py7zr.SevenZipFile(archive_path, mode='r') as z:
                        return [f.filename for f in z.list()]
                except ImportError:
                    # 如果py7zr不可用，尝试使用7zip命令行
                    return self._list_7z_with_cmd(archive_path)
            else:
                # 未知格式
                print(f"未知压缩文件格式: {archive_path}")
                return []
        except Exception as e:
            print(f"列出压缩文件内容时出错: {e}")
            return []
    
    def _list_7z_with_cmd(self, archive_path):
        """使用7zip命令行列出内容"""
        try:
            # 查找7zip路径
            sevenzip_path = "C:\\Program Files\\7-Zip\\7z.exe"
            if not os.path.exists(sevenzip_path):
                sevenzip_path = "C:\\Program Files (x86)\\7-Zip\\7z.exe"
            
            if not os.path.exists(sevenzip_path):
                print("未找到7zip程序")
                return []
            
            # 执行7zip命令列出内容
            result = subprocess.run([sevenzip_path, 'l', archive_path], 
                                    capture_output=True, text=True)
            
            # 解析输出
            lines = result.stdout.splitlines()
            file_list = []
            
            # 找到文件列表开始的行
            start_idx = -1
            for i, line in enumerate(lines):
                if "----------" in line:
                    start_idx = i + 1
                    break
            
            if start_idx == -1:
                return []
            
            # 解析文件列表
            for i in range(start_idx, len(lines)):
                line = lines[i].strip()
                if not line or "----------" in line:
                    break
                
                parts = line.split()
                if len(parts) >= 5:
                    # 最后一列是文件名，可能包含空格
                    file_name = " ".join(parts[5:])
                    file_list.append(file_name)
            
            return file_list
            
        except Exception as e:
            print(f"使用7zip命令行列出内容时出错: {e}")
            return []
    
    def download_patch(self, patch_url):
        """下载补丁文件"""
        try:
            import requests
            from urllib.parse import urlparse
            
            self.progress_update.emit(10, "正在准备下载补丁文件...")
            
            # 解析URL获取文件名
            parsed_url = urlparse(patch_url)
            file_name = os.path.basename(parsed_url.path)
            
            # 如果文件名为空或无效，使用默认名称
            if not file_name or file_name == '':
                file_name = "apatch_download.7z"
                
            # 下载路径
            download_dir = tempfile.gettempdir()
            download_path = os.path.join(download_dir, file_name)
            
            # 清理可能存在的旧文件
            if os.path.exists(download_path):
                try:
                    os.remove(download_path)
                except Exception as e:
                    print(f"无法删除旧的下载文件: {e}")
                    # 使用新的文件名
                    download_path = os.path.join(download_dir, f"apatch_download_{int(time.time())}.7z")
            
            # 开始下载
            self.progress_update.emit(15, f"正在下载: {patch_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(patch_url, headers=headers, stream=True)
            
            # 获取文件大小（如果服务器提供）
            total_size = int(response.headers.get('content-length', 0))
            
            # 写入文件
            with open(download_path, 'wb') as f:
                if total_size > 0:
                    # 有文件大小信息时，显示下载进度
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 计算下载进度
                            progress = min(35, 15 + int(20 * downloaded / total_size))
                            self.progress_update.emit(progress, f"下载中: {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB")
                else:
                    # 没有文件大小信息时，只显示下载状态
                    for i, chunk in enumerate(response.iter_content(chunk_size=8192)):
                        if chunk:
                            f.write(chunk)
                        # 每100个区块更新一次状态
                        if i % 100 == 0:
                            self.progress_update.emit(20, f"下载中: {i*8192/1024/1024:.1f}MB")
            
            self.progress_update.emit(35, "补丁文件下载完成")
            
            # 检查下载文件
            if os.path.exists(download_path) and os.path.getsize(download_path) > 0:
                return download_path
            else:
                return None
                
        except Exception as e:
            print(f"下载补丁文件失败: {e}")
            return None
    
    def run_patch_program(self, patch_exe):
        """运行补丁程序"""
        try:
            # 检查文件是否存在
            if not os.path.exists(patch_exe):
                print(f"补丁程序不存在: {patch_exe}")
                return False
            
            # 获取当前工作目录
            cwd = os.path.dirname(patch_exe)
            
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            batch_file = os.path.join(temp_dir, "run_patch.bat")
            output_file = os.path.join(temp_dir, "patch_output.txt")
            
            # 清理可能存在的旧输出文件
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception as e:
                    print(f"无法删除旧输出文件: {e}")
            
            # 创建批处理文件，使用echo y模拟按键输入，并捕获输出
            batch_content = f"""@echo off
chcp 65001 > nul
cd /d "{cwd}"
echo 正在运行补丁程序: {patch_exe} > "{output_file}"
echo 时间: %date% %time% >> "{output_file}"

REM 使用echo y来模拟按键输入，将所有输出重定向到日志文件
(echo y | "{patch_exe}") >> "{output_file}" 2>&1

echo 补丁程序已完成执行 >> "{output_file}"
echo 完成时间: %date% %time% >> "{output_file}"
echo 退出代码: %errorlevel% >> "{output_file}"
exit
"""
            
            # 写入批处理文件
            with open(batch_file, 'w', encoding='gbk') as f:
                f.write(batch_content)
            
            self.progress_update.emit(85, "正在运行补丁程序，请稍候...")
            
            # 运行批处理文件
            process = subprocess.Popen(batch_file, 
                                      shell=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 不等待程序完成，只检查进程是否成功启动
            if process.poll() is not None:
                # 进程已结束（可能启动失败）
                print(f"补丁程序启动失败")
                return False
                
            # 进程成功启动，定期检查输出文件并更新UI
            self.progress_update.emit(87, "补丁程序已启动，正在处理中...")
            
            # 等待补丁程序完成执行
            start_time = time.time()
            max_wait_time = 300  # 最多等待5分钟
            check_interval = 1   # 每秒检查一次
            last_update_time = start_time
            
            # 循环等待程序完成或超时
            while time.time() - start_time < max_wait_time:
                time.sleep(check_interval)
                
                # 检查是否有输出文件
                if os.path.exists(output_file):
                    try:
                        output_content = self.read_file_with_encoding(output_file)
                        # 保存输出内容
                        self.patch_output = output_content
                        
                        # 检查是否有成功标志 - 只有检测到"成功替换"才认为成功
                        if "成功替换" in output_content:
                            # 提取包含成功标志的那一行作为状态消息
                            success_line = next((line for line in output_content.split('\n') 
                                            if "成功替换" in line 
                                            and line.strip()), "补丁已成功应用")
                            self.progress_update.emit(95, f"补丁状态: {success_line}")
                            success = True
                        elif "替换失败" in output_content:
                            # 检查是否有替换失败的情况
                            import re
                            replacement_failure_pattern = re.compile(r'替换失败\s+\S+')
                            matches = replacement_failure_pattern.findall(output_content)
                            if matches:
                                self.replacement_failure = True
                                self.failed_files = [m.split("替换失败", 1)[1].strip() for m in matches]
                                self.progress_update.emit(90, f"补丁部分失败: {len(self.failed_files)}个文件无法替换")
                            else:
                                self.progress_update.emit(90, "检测到替换失败")
                            self.replacement_failure = True
                            success = False
                        else:
                            # 其他情况，如果PatchGGPK.exe已退出，也视为成功
                            if not self.is_process_running("PatchGGPK.exe"):
                                self.progress_update.emit(95, "补丁程序已执行完毕")
                                success = True
                    except Exception as e:
                        print(f"读取输出文件时出错: {e}")
                
                # 检查补丁程序是否还在运行
                if not self.is_process_running("PatchGGPK.exe") and time.time() - start_time > 10:
                    # 程序已结束，检查输出文件最后修改时间
                    if os.path.exists(output_file):
                        file_mod_time = os.path.getmtime(output_file)
                        if time.time() - file_mod_time > 5:  # 文件超过5秒未修改
                            break
            
            # 读取最终输出并判断结果
            if success:
                self.progress_update.emit(95, "补丁已成功应用!")
            else:
                self.progress_update.emit(90, "补丁安装失败")
            
            # 将进程对象存储为类成员，以防止被垃圾回收
            self.patch_process = process
            
            return success
            
        except Exception as e:
            print(f"运行补丁程序时出错: {e}")
            return False

    def is_process_running(self, process_name):
        """检查指定进程是否正在运行"""
        try:
            import subprocess
            result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {process_name}', '/NH'], 
                                   capture_output=True, text=True)
            return process_name in result.stdout
        except Exception as e:
            print(f"检查进程时出错: {e}")
            return False  # 出错时默认假设进程没在运行
    
    def read_file_with_encoding(self, file_path):
        """尝试不同编码读取文件内容"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        content = ""
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
                    # 如果成功读取并且包含中文，说明编码正确
                    if any("\u4e00" <= c <= "\u9fff" for c in content):
                        print(f"成功使用编码 {encoding} 读取文件")
                        return content
            except Exception as e:
                print(f"使用编码 {encoding} 读取文件失败: {e}")
        
        # 所有编码都失败，返回最后一次尝试的结果
        return content

class APatchTab(QWidget):
    """A大补丁标签页类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_path = ""  # 游戏路径
        self.init_ui()  # 初始化界面
        self.detect_game_path()  # 自动检测游戏路径
        
        # 初始不拉取，等待首次打开标签页时再检查，降低启动时的网络负担
        # self.check_updates()
        
        # 确保需要的库已安装
        self.ensure_required_libs()
        
        # 设置定时器，定期检查更新（包括补丁状态和更新时间）
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_updates)
        # 延后到首次打开标签页后再启动：在 ui_core.on_tab_changed 中调用 start
        # self.update_timer.start(1800000)  # 30分钟 = 1800000毫秒
    
    def check_updates(self, force_refresh=False):
        """检查补丁更新状态和最后更新时间（合并函数）
        
        Args:
            force_refresh: 是否强制刷新（即使之前已经检查过）
        """
        try:
            # 移除缓存检查代码，每次都执行网络请求
            
            # 暂存原状态，以便在网络请求失败时恢复
            original_button_enabled = self.install_button.isEnabled() if hasattr(self, 'install_button') else True
            
            # 保存原始状态标签内容
            if hasattr(self, 'apatch_status_label'):
                original_status_text = self.apatch_status_label.text()
                original_status_style = self.apatch_status_label.styleSheet()
            
            # 设置刷新按钮状态
            if hasattr(self, 'refresh_time_button'):
                self.refresh_time_button.setEnabled(False)
                self.refresh_time_button.setText("获取中...")
                QApplication.processEvents()  # 更新UI
            
            # 从网络获取数据
            try:
                # 确保requests库已安装
                self.ensure_required_libs()
                
                import requests
                from bs4 import BeautifulSoup
                
                # 设置请求头部，模拟浏览器访问
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # 1. 获取补丁状态
                allow_install = True  # 默认允许安装
                version_url = "https://gitee.com/mexiaow/poe2-price-aid/raw/main/version_A%E5%A4%A7%E8%A1%A5%E4%B8%81.json"
                #version_url = "https://s4-share.xwat.cn/POE2PriceAid/version_A%E5%A4%A7%E8%A1%A5%E4%B8%81.json"
                
                response = requests.get(version_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # 成功获取数据
                    content = response.text.strip()
                    print(f"从网络获取补丁状态原始内容: {content}")
                    
                    try:
                        # 解析JSON数据
                        json_data = json.loads(content)
                        print(f"解析后的JSON数据: {json_data}, 类型: {type(json_data)}")
                        
                        # 使用辅助函数统一解析值
                        allow_install = self._parse_json_value(json_data)
                        print(f"解析结果: allow_install = {allow_install}")
                        
                    except json.JSONDecodeError as e:
                        print(f"JSON解析错误: {e}, 回退到简单文本匹配")
                        # JSON解析失败，回退到简单的文本匹配
                        allow_install = content.lower() not in ["false", "0"]
                
                # 2. 获取更新时间
                update_time_text = "最后更新时间: 获取中..."
                
                # 获取网页内容
                url = "https://gitee.com/mexiaow/poe2-price-aid/blob/main/version_A%E5%A4%A7%E8%A1%A5%E4%B8%81.json"
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # 解析HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找时间元素
                    time_element = soup.select_one("#tree-content-holder > div.file_holder > div.file_title > div.contributor-description > span > span.timeago.commit-date")
                    
                    if time_element:
                        # 直接获取显示的相对时间
                        display_time = time_element.text.strip()
                        # 设置结果
                        update_time_text = f"最后更新时间: {display_time}"
                    else:
                        # 未找到时间元素
                        update_time_text = "最后更新时间: 无法获取"
                else:
                    # 请求失败
                    update_time_text = "最后更新时间: 无法连接到服务器"
                
                # 3. 更新UI
                # 更新时间显示
                self.update_time_label(update_time_text)
                
                # 设置按钮状态
                self._set_button_status(allow_install)
                
            except Exception as e:
                print(f"检查更新出错: {e}")
                # 更新时间显示错误
                self.update_time_label("最后更新时间: 获取失败")
                # 保持按钮原状态
                if hasattr(self, 'install_button'):
                    self.install_button.setEnabled(original_button_enabled)
            
            # 恢复刷新按钮状态
            if hasattr(self, 'refresh_time_button'):
                self.refresh_time_button.setEnabled(True)
                self.refresh_time_button.setText("刷新")
                
        except Exception as e:
            print(f"check_updates 方法出错: {e}")
            # 恢复刷新按钮状态
            if hasattr(self, 'refresh_time_button'):
                self.refresh_time_button.setEnabled(True)
                self.refresh_time_button.setText("刷新")
    
    def _parse_json_value(self, value):
        """解析JSON值，统一转换为布尔值
        
        Args:
            value: 要解析的值，可以是字典、字符串、数字或布尔值
        
        Returns:
            bool: 解析后的布尔值结果
        """
        # 处理字典类型
        if isinstance(value, dict):
            # 按优先级查找不同的键
            for key in ["Status", "status", "enabled", "allow_install", "available"]:
                if key in value:
                    return self._parse_json_value(value[key])
            # 如果找不到任何已知键，默认为真
            return True
        
        # 处理字符串类型（不区分大小写）
        elif isinstance(value, str):
            # 将字符串标准化为小写并去除空白
            value_lower = value.lower().strip()
            # "true"或"1"视为真
            if value_lower in ["true", "1"]:
                return True
            # "false"或"0"视为假
            elif value_lower in ["false", "0"]:
                return False
            # 其他字符串视为真
            else:
                return True
        
        # 处理数字类型
        elif isinstance(value, (int, float)):
            # 非零值视为真，零视为假
            return bool(value)
        
        # 处理布尔类型
        elif isinstance(value, bool):
            return value
        
        # 处理其他类型（默认为真）
        else:
            print(f"未知的JSON值类型: {type(value)}")
            return True
    
    def _set_button_status(self, allow_install):
        """根据补丁状态设置按钮状态
        
        Args:
            allow_install: 是否允许安装补丁
        """
        if allow_install:
            # 启用按钮
            self.install_button.setEnabled(True)
            self.install_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 16px;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #1C86E0;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
            """)
            # 清空可能的提示
            if hasattr(self, "version_notice_label") and self.version_notice_label:
                self.version_notice_label.setVisible(False)
        else:
            # 禁用按钮
            self.install_button.setEnabled(False)
            self.install_button.setStyleSheet("""
                QPushButton {
                    background-color: #888888;
                    color: #CCCCCC;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 16px;
                    min-width: 120px;
                }
            """)
            
            # 添加提示文本（如果尚未添加）
            if not hasattr(self, "version_notice_label") or not self.version_notice_label:
                self.version_notice_label = QLabel("游戏已更新 请等待新补丁")
                self.version_notice_label.setStyleSheet("font-size: 16px; color: #FF0000; font-weight: bold;")
                # 将标签添加到按钮下方
                for i in range(self.layout().count()):
                    item = self.layout().itemAt(i)
                    if item and item.widget() == self.apatch_status_label:
                        # 在状态标签前插入提示
                        self.layout().insertWidget(i, self.version_notice_label)
                        break
            
            # 确保提示可见
            self.version_notice_label.setVisible(True)
    
    def check_version_status(self, force_refresh=False):
        """检查补丁可用状态并设置按钮状态（已合并到 check_updates 方法）
        
        Args:
            force_refresh: 是否强制刷新（即使之前已经检查过）
        """
        # 为保持兼容性，调用新方法
        self.check_updates(force_refresh)
    
    def get_apatch_update_time(self):
        """获取A大补丁最后更新时间（已合并到 check_updates 方法）"""
        # 为保持兼容性，调用新方法
        self.check_updates(force_refresh=True)
    
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
        self.apatch_update_time_label.setText(time_text)
        
        # 根据获取结果设置不同的样式
        if "获取失败" in time_text or "无法" in time_text:
            self.apatch_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FF0000; font-weight: bold;")
            # 提示获取失败的原因，但只在非自动获取时显示
            if not hasattr(self, '_auto_update') or not self._auto_update:
                QMessageBox.warning(self, "获取失败", 
                                  f"无法获取A大补丁更新时间信息：\n{time_text}\n\n可能的原因：\n1. 网络连接问题\n2. 网站结构变更\n3. 所需库安装失败",
                                  QMessageBox.Ok)
        elif "获取中" in time_text:
            self.apatch_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FFA500; font-weight: bold;")
        else:
            # 成功获取时只改变颜色，不显示弹窗
            self.apatch_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #0078D7; font-weight: bold;")
    
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
        
        # 创建A大补丁更新时间行
        update_time_layout = QHBoxLayout()
        update_time_layout.setContentsMargins(0, 0, 0, 0)
        update_time_layout.setSpacing(10)
        
        # 添加A大补丁更新时间显示
        self.apatch_update_time_label = QLabel("最后更新时间: 获取中...")
        self.apatch_update_time_label.setStyleSheet("font-size: 16px; margin-bottom: 10px; color: #FFA500; font-weight: bold;")
        self.apatch_update_time_label.setContentsMargins(0, 0, 0, 0)
        self.apatch_update_time_label.setAlignment(Qt.AlignLeft)
        update_time_layout.addWidget(self.apatch_update_time_label)
        
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
        self.refresh_time_button.clicked.connect(self.check_updates)
        update_time_layout.addWidget(self.refresh_time_button)
        
        # 添加弹性空间推动刷新按钮靠右
        update_time_layout.addStretch(1)
        
        # 将更新时间行添加到左对齐布局
        left_aligned_layout.addLayout(update_time_layout)
        
        # 创建按钮行的水平布局
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(15)
        button_row.setAlignment(Qt.AlignLeft)

        # 一键安装按钮
        self.install_button = QPushButton("一键安装补丁")
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 16px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        self.install_button.clicked.connect(self.install_apatch)
        self.install_button.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self.install_button, 0, Qt.AlignLeft)

        # 添加搜索按钮
        self.search_dir_button = QPushButton("搜索")
        self.search_dir_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.search_dir_button.clicked.connect(self.search_game_directory)
        button_row.addWidget(self.search_dir_button)

        # 选择游戏目录按钮
        self.select_dir_button = QPushButton("选择游戏目录")
        self.select_dir_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.select_dir_button.clicked.connect(self.select_game_directory)
        button_row.addWidget(self.select_dir_button)

        # 打开游戏目录按钮
        self.open_dir_button = QPushButton("打开游戏目录")
        self.open_dir_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.open_dir_button.clicked.connect(self.open_game_directory)
        button_row.addWidget(self.open_dir_button)

        # 将按钮行添加到左对齐布局
        left_aligned_layout.addLayout(button_row)

        # 游戏路径显示（单独一行）
        self.poe_game_path_label = QLabel("游戏根目录: 自动检测中...")
        self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #888888; margin-top: 10px;")
        left_aligned_layout.addWidget(self.poe_game_path_label)
        
        # 将左对齐布局添加到主布局
        layout.addLayout(left_aligned_layout)
        
        # 状态显示
        self.apatch_status_label = QLabel("")
        self.apatch_status_label.setStyleSheet("font-size: 16px; margin-top: 5px;")
        self.apatch_status_label.setWordWrap(True)
        layout.addWidget(self.apatch_status_label)
        
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
        description_label = QLabel("检测游戏目录并自动下载最新补丁直接替换Bundles2目录中的相关文件")
        description_label.setStyleSheet("font-size: 14px; margin-top: 10px; color: #888888;")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
    
    def detect_game_path(self):
        """检测POE2游戏路径"""
        try:
            # 显示检测中状态
            self.poe_game_path_label.setText("游戏根目录: 检测中...")
            self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #FFA500;")
            QApplication.processEvents()  # 更新UI
            
            # 创建线程查找游戏路径
            class GamePathThread(QThread):
                path_found = pyqtSignal(str)
                
                def run(self):
                    try:
                        # 优先从运行进程查找
                        path = self._find_poe2_from_running_process()
                        if path:
                            self.path_found.emit(path)
                            return
                            
                        # 尝试从注册表查找
                        path = self._find_poe2_from_registry()
                        if path:
                            self.path_found.emit(path)
                            return
                            
                        # 尝试WeGame路径搜索
                        path = self._find_poe2_common_locations()
                        if path:
                            self.path_found.emit(path)
                            return
                            
                        # 都找不到时
                        self.path_found.emit("")
                    except Exception as e:
                        print(f"查找游戏路径线程出错: {e}")
                        self.path_found.emit("")
                
                def _find_poe2_from_running_process(self):
                    """从运行中的PathOfExile.exe进程查找游戏路径"""
                    try:
                        if 'psutil' not in globals():
                            print("psutil模块不可用，无法从运行进程查找")
                            return ""
                            
                        for proc in psutil.process_iter(['pid', 'name', 'exe']):
                            if proc.info['name'] and proc.info['name'].lower() in ['pathofexile.exe', 'pathofexile_x64.exe']:
                                if proc.info['exe']:
                                    game_dir = os.path.dirname(proc.info['exe'])
                                    # 验证找到的目录是否包含必要的游戏文件
                                    if self._validate_game_directory(game_dir):
                                        print(f"从运行进程找到游戏目录: {game_dir}")
                                        return game_dir
                        return ""
                    except Exception as e:
                        print(f"从运行进程查找游戏路径时出错: {e}")
                        return ""
                
                def _validate_game_directory(self, directory):
                    """验证目录是否为有效的POE2游戏目录"""
                    try:
                        # 检查是否包含游戏主要可执行文件
                        exe_path = os.path.join(directory, "PathOfExile.exe")
                        exe_x64_path = os.path.join(directory, "PathOfExile_x64.exe")
                        
                        # 如果找到可执行文件，就认为是有效目录
                        if os.path.exists(exe_path) or os.path.exists(exe_x64_path):
                            return True
                            
                        # 对于WeGame路径，可能需要检查特定的目录结构
                        if any(keyword in directory for keyword in ["WeGameApps", "rail_apps", "流放之路"]):
                            return os.path.exists(exe_path) or os.path.exists(exe_x64_path)
                            
                        # 原有的目录名检查（兼容性保留）
                        if "Path of Exile 2" in directory:
                            return os.path.exists(exe_path) or os.path.exists(exe_x64_path)
                            
                        return False
                    except Exception as e:
                        print(f"验证游戏目录时出错: {e}")
                        return False
                
                def _find_poe2_from_registry(self):
                    """从注册表查找POE2游戏路径"""
                    try:
                        # 常见游戏路径注册表位置
                        registry_paths = [
                            # 优先查找WeGame版本的注册表路径
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\流放之路：降临"),
                            # Steam版本路径
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 2381970"),
                            # 原有GGG路径
                            (winreg.HKEY_CURRENT_USER, r"Software\GrindingGearGames\Path of Exile 2"),
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Grinding Gear Games\Path of Exile 2"),
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Grinding Gear Games\Path of Exile 2"),
                            # Installer文件夹
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\Folders")
                        ]
                        
                        for hkey, subkey in registry_paths:
                            try:
                                with winreg.OpenKey(hkey, subkey) as key:
                                    # 对于特殊的Installer\Folders键，需要遍历所有值
                                    if "Installer\\Folders" in subkey:
                                        index = 0
                                        while True:
                                            try:
                                                name, value, _ = winreg.EnumValue(key, index)
                                                # 检查值是否包含POE2相关路径
                                                if any(keyword in value for keyword in ["Path of Exile 2", "流放之路", "降临", "WeGameApps"]):
                                                    path = value
                                                    # 移除可能的尾部斜杠
                                                    if path.endswith('\\'):
                                                        path = path[:-1]
                                                    if os.path.exists(path) and self._validate_game_directory(path):
                                                        print(f"从Installer\\Folders找到游戏目录: {path}")
                                                        return path
                                                index += 1
                                            except OSError:  # 没有更多的值
                                                break
                                    else:
                                        # 常规路径尝试 - 优先查找InstallSource
                                        try:
                                            path, _ = winreg.QueryValueEx(key, "InstallSource")
                                            if os.path.exists(path) and self._validate_game_directory(path):
                                                print(f"从注册表InstallSource找到游戏目录: {path}")
                                                return path
                                        except:
                                            pass
                                        
                                        # 备用查找InstallLocation
                                        try:
                                            path, _ = winreg.QueryValueEx(key, "InstallLocation")
                                            if os.path.exists(path) and self._validate_game_directory(path):
                                                print(f"从注册表InstallLocation找到游戏目录: {path}")
                                                return path
                                        except:
                                            pass
                            except Exception as e:
                                print(f"尝试注册表路径 {subkey} 时出错: {e}")
                                continue
                        
                        return ""
                    except Exception as e:
                        print(f"从注册表查找游戏路径时出错: {e}")
                        return ""
                
                def _find_poe2_common_locations(self):
                    """在常见位置查找POE2游戏目录"""
                    # 搜索WeGame安装路径模式
                    potential_drives = ['C', 'D', 'E', 'F', 'G', 'H']
                    base_patterns = [
                        "Game\\WeGameApps\\rail_apps",
                        "WeGame\\WeGameApps\\rail_apps", 
                        "Program Files\\WeGame\\WeGameApps\\rail_apps",
                        "Program Files (x86)\\WeGame\\WeGameApps\\rail_apps"
                    ]
                    
                    for drive in potential_drives:
                        for pattern in base_patterns:
                            base_path = f"{drive}:\\{pattern}"
                            if os.path.exists(base_path):
                                try:
                                    # 在rail_apps目录下查找包含"流放之路"或"降临"的文件夹
                                    for item in os.listdir(base_path):
                                        if any(keyword in item for keyword in ["流放之路", "降临"]):
                                            game_path = os.path.join(base_path, item)
                                            if os.path.isdir(game_path) and self._validate_game_directory(game_path):
                                                print(f"从WeGame路径找到游戏目录: {game_path}")
                                                return game_path
                                except Exception as e:
                                    print(f"搜索路径 {base_path} 时出错: {e}")
                                    continue
                    
                    # 备用：传统Path of Exile 2路径（保持兼容性）
                    traditional_locations = [
                        "C:\\Program Files\\Path of Exile 2",
                        "D:\\Program Files\\Path of Exile 2"
                    ]
                    
                    for location in traditional_locations:
                        if os.path.exists(location) and self._validate_game_directory(location):
                            print(f"从传统路径找到游戏目录: {location}")
                            return location
                    
                    return ""
            
            # 创建并启动线程
            self.game_path_thread = GamePathThread()
            self.game_path_thread.path_found.connect(self.on_game_path_found)
            self.game_path_thread.start()
            
        except Exception as e:
            print(f"检测游戏路径过程中出错: {e}")
            self.poe_game_path_label.setText("游戏根目录: 检测失败")
            self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #FF0000;")
    
    def on_game_path_found(self, path):
        """游戏路径找到时的回调"""
        if path:
            self.poe_game_path_label.setText(f"游戏根目录: {path}")
            self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #00FF00;")
            self.game_path = path  # 保存找到的路径
        else:
            # 不再自动弹出选择对话框
            self.poe_game_path_label.setText("游戏根目录: 未找到 (点击\"选择游戏目录\"按钮手动选择)")
            self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #FF0000;")
            self.game_path = ""  # 清空路径
    
    def install_apatch(self):
        """安装A大补丁"""
        try:
            # 显示检测中状态
            self.apatch_status_label.setText("正在准备安装...")
            self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FFA500;")
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # 更新UI
            
            # 检查是否已经查找到游戏路径
            if not self.game_path:
                # 提示用户先选择游戏目录
                self.apatch_status_label.setText("请先选择游戏目录")
                self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FF0000;")
                self.progress_bar.setVisible(False)
                return
            
            # 检查游戏是否运行
            if self.is_game_running():
                # 提示用户是否关闭游戏
                reply = QMessageBox.question(self, 
                                           "游戏正在运行", 
                                           "检测到游戏客户端正在运行，是否关闭游戏后继续安装？",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
                
                if reply == QMessageBox.Yes:
                    # 关闭游戏
                    self.apatch_status_label.setText("正在关闭游戏进程...")
                    QApplication.processEvents()  # 更新UI
                    
                    if not self.close_game_process():
                        self.apatch_status_label.setText("无法关闭游戏进程，请手动关闭后重试")
                        self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FF0000;")
                        self.progress_bar.setVisible(False)
                        return
                else:
                    # 用户选择不关闭游戏，停止安装
                    self.apatch_status_label.setText("安装已取消")
                    self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FF0000;")
                    self.progress_bar.setVisible(False)
                    return
            
            # 创建安装进程
            self.apatch_status_label.setText("正在检查游戏进程...")
            self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FFA500;")
            QApplication.processEvents()  # 更新UI
            
            # 创建线程执行安装过程
            self.apatch_install_thread = APatchInstallThread(self.game_path)
            self.apatch_install_thread.progress_update.connect(self.update_apatch_progress)
            self.apatch_install_thread.install_finished.connect(self.on_apatch_install_finished)
            self.apatch_install_thread.start()
            
        except Exception as e:
            self.apatch_status_label.setText(f"安装A大补丁时出错: {str(e)}")
            self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FF0000;")
            self.progress_bar.setVisible(False)
    
    def close_game_process(self):
        """关闭游戏进程"""
        try:
            if 'psutil' not in globals():
                # 如果不能导入psutil，使用传统方式
                try:
                    subprocess.run(['taskkill', '/F', '/IM', 'PathOfExile.exe'], 
                                  capture_output=True, check=False)
                    subprocess.run(['taskkill', '/F', '/IM', 'PathOfExile_x64.exe'], 
                                  capture_output=True, check=False)
                    time.sleep(2)  # 等待进程完全关闭
                    return not self.is_game_running()
                except:
                    return False
            
            # 使用psutil关闭游戏进程
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() in ['pathofexile.exe', 'pathofexile_x64.exe']:
                    try:
                        proc.terminate()  # 尝试优雅终止
                    except:
                        pass
            
            # 等待进程终止
            time.sleep(2)
            
            # 如果进程仍然存在，强制终止
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() in ['pathofexile.exe', 'pathofexile_x64.exe']:
                    try:
                        proc.kill()  # 强制终止
                    except:
                        pass
            
            # 再次检查是否还有游戏进程
            time.sleep(1)  # 短暂等待确保进程状态更新
            return not self.is_game_running()
        
        except Exception as e:
            print(f"关闭游戏进程时出错: {e}")
            return False
            
    def is_game_running(self):
        """检查游戏是否正在运行"""
        try:
            if 'psutil' not in globals():
                # 如果不能导入psutil，使用传统方式
                try:
                    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq PathOfExile.exe', '/NH'], 
                                          capture_output=True, text=True)
                    if "PathOfExile.exe" in result.stdout:
                        return True
                    
                    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq PathOfExile_x64.exe', '/NH'], 
                                          capture_output=True, text=True)
                    return "PathOfExile_x64.exe" in result.stdout
                except:
                    return False
            
            # 使用psutil检查
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() in ['pathofexile.exe', 'pathofexile_x64.exe']:
                    return True
            return False
        except Exception as e:
            print(f"检查游戏进程时出错: {e}")
            return False  # 出错时默认假设游戏没在运行
    
    def update_apatch_progress(self, progress, message):
        """更新A大补丁安装进度"""
        self.progress_bar.setValue(progress)
        
        # 如果消息中包含"补丁状态"，提取并格式化状态信息
        if "补丁状态:" in message:
            status_info = message.split("补丁状态:", 1)[1].strip()
            # 根据状态信息类型设置不同样式
            if any(keyword in status_info for keyword in ["成功替换", "补丁完成", "已完成"]):
                # 成功信息用绿色显示
                self.apatch_status_label.setText(status_info)
                self.apatch_status_label.setStyleSheet("font-size: 16px; color: #00AA00;")
            elif "替换失败" in status_info:
                # 失败信息用红色显示
                self.apatch_status_label.setText(status_info)
                self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FF0000;")
            else:
                # 一般状态信息
                self.apatch_status_label.setText(status_info)
                self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FFA500;")
        else:
            # 其他类型的消息
            self.apatch_status_label.setText(message)
            if progress >= 100:
                self.apatch_status_label.setStyleSheet("font-size: 16px; color: #00FF00;")
            else:
                self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FFA500;")
    
    def on_apatch_install_finished(self, success, message):
        """补丁安装完成的处理"""
        # 检查是否有替换失败的情况（从安装线程中获取）
        replacement_failure = False
        failed_files = []
        
        if hasattr(self, 'apatch_install_thread'):
            if hasattr(self.apatch_install_thread, 'replacement_failure'):
                replacement_failure = self.apatch_install_thread.replacement_failure
            if hasattr(self.apatch_install_thread, 'failed_files'):
                failed_files = self.apatch_install_thread.failed_files
        
        # 如果检测到替换失败，强制标记为失败，覆盖可能错误的成功状态
        if replacement_failure:
            success = False
            if failed_files:
                message = f"补丁部分失败: {len(failed_files)}个文件无法替换"
            else:
                message = "补丁部分失败: 检测到文件替换失败"
        
        if success:
            self.apatch_status_label.setText("A大补丁安装成功!")
            self.apatch_status_label.setStyleSheet("font-size: 16px; color: #00FF00; font-weight: bold;")
            self.apatch_status_label.setAlignment(Qt.AlignLeft)  # 左对齐
            
            # 提示成功消息并添加查看按钮
            success_dialog = QMessageBox(self)
            success_dialog.setIcon(QMessageBox.Information)
            success_dialog.setWindowTitle("安装成功")
            success_dialog.setText(f"A大补丁安装成功！\n{message}")
            
            # 添加"查看"按钮
            view_button = success_dialog.addButton("查看", QMessageBox.ActionRole)
            ok_button = success_dialog.addButton(QMessageBox.Ok)
            success_dialog.setDefaultButton(QMessageBox.Ok)
            
            success_dialog.exec_()
            
            # 如果点击了"查看"按钮
            if success_dialog.clickedButton() == view_button:
                self.show_patch_output()
        else:
            self.apatch_status_label.setText(f"安装失败: {message}")
            self.apatch_status_label.setStyleSheet("font-size: 16px; color: #FF0000; font-weight: bold;")
            self.apatch_status_label.setAlignment(Qt.AlignLeft)  # 左对齐
            
            # 构建详细错误信息
            error_details = message
            if failed_files:
                error_details += "\n\n替换失败的文件:"
                for file in failed_files[:10]:  # 最多显示10个文件
                    error_details += f"\n- {file}"
                if len(failed_files) > 10:
                    error_details += f"\n...以及其他{len(failed_files)-10}个文件"
            
            # 弹出错误对话框
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("安装失败")
            error_dialog.setText("A大补丁安装失败！")
            error_dialog.setInformativeText(message)
            
            # 添加"查看"按钮
            view_button = error_dialog.addButton("查看", QMessageBox.ActionRole)
            ok_button = error_dialog.addButton(QMessageBox.Ok)
            error_dialog.setDefaultButton(QMessageBox.Ok)
            
            error_dialog.exec_()
            
            # 如果点击了"查看"按钮
            if error_dialog.clickedButton() == view_button:
                self.show_patch_output()
        
        self.progress_bar.setVisible(False)
    
    def select_game_directory(self):
        """手动选择游戏目录"""
        path = QFileDialog.getExistingDirectory(self, "选择Path of Exile 2游戏根目录")
        if path:
            self.poe_game_path_label.setText(f"游戏根目录: {path}")
            self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #00FF00;")
            self.game_path = path  # 保存选择的路径

    def open_game_directory(self):
        """打开游戏目录"""
        if not self.game_path or not os.path.exists(self.game_path):
            QMessageBox.warning(self, "警告", "游戏目录不存在或未设置！\n请先选择正确的游戏目录。")
            return

        try:
            # 在Windows上使用explorer打开目录
            os.startfile(self.game_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开游戏目录：\n{str(e)}") 
    
    def search_game_directory(self):
        """智能搜索游戏目录"""
        # 如果已经有搜索线程在运行，则忽略此次请求
        if hasattr(self, 'game_search_thread') and self.game_search_thread.isRunning():
            print("搜索已在进行中，忽略此次请求")
            return
            
        # 显示搜索中状态
        self.poe_game_path_label.setText("游戏根目录: 正在智能搜索...")
        self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #FFA500;")
        QApplication.processEvents()  # 更新UI
        
        # 创建搜索线程 - 使用与自动检测相同的逻辑
        class GameSearchThread(QThread):
            path_found = pyqtSignal(str)
            search_progress = pyqtSignal(str)
            
            def __init__(self, parent=None):
                super().__init__(parent)
                self.stopped = False
                
            def stop(self):
                """停止搜索"""
                self.stopped = True
                
            def run(self):
                try:
                    # 使用与自动检测相同的逻辑，但增加进度提示
                    
                    # 1. 先尝试运行进程检测
                    self.search_progress.emit("正在检查运行中的游戏进程...")
                    path = self._find_poe2_from_running_process()
                    if path and not self.stopped:
                        self.path_found.emit(path)
                        return
                    
                    # 2. 尝试从注册表查找
                    self.search_progress.emit("正在查找注册表信息...")
                    path = self._find_poe2_from_registry()
                    if path and not self.stopped:
                        self.path_found.emit(path)
                        return
                    
                    # 3. 尝试WeGame路径搜索
                    self.search_progress.emit("正在搜索WeGame安装路径...")
                    path = self._find_poe2_common_locations()
                    if path and not self.stopped:
                        self.path_found.emit(path)
                        return
                    
                    # 4. 如果以上都没找到，进行全盘搜索
                    self.search_progress.emit("正在进行全盘搜索，这可能需要几分钟...")
                    path = self._full_disk_search()
                    if path and not self.stopped:
                        self.path_found.emit(path)
                        return
                    
                    # 都找不到
                    self.path_found.emit("")
                    
                except Exception as e:
                    print(f"智能搜索游戏路径线程出错: {e}")
                    self.path_found.emit("")
            
            def _find_poe2_from_running_process(self):
                """从运行中的PathOfExile.exe进程查找游戏路径"""
                try:
                    if 'psutil' not in globals():
                        return ""
                        
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        if proc.info['name'] and proc.info['name'].lower() in ['pathofexile.exe', 'pathofexile_x64.exe']:
                            if proc.info['exe']:
                                game_dir = os.path.dirname(proc.info['exe'])
                                if self._validate_game_directory(game_dir):
                                    return game_dir
                    return ""
                except Exception as e:
                    print(f"从运行进程查找游戏路径时出错: {e}")
                    return ""
            
            def _find_poe2_from_registry(self):
                """从注册表查找POE2游戏路径"""
                try:
                    registry_paths = [
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\流放之路：降临"),
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 2381970"),
                        (winreg.HKEY_CURRENT_USER, r"Software\GrindingGearGames\Path of Exile 2"),
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Grinding Gear Games\Path of Exile 2"),
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Grinding Gear Games\Path of Exile 2"),
                    ]
                    
                    for hkey, subkey in registry_paths:
                        try:
                            with winreg.OpenKey(hkey, subkey) as key:
                                # 优先查找InstallSource
                                try:
                                    path, _ = winreg.QueryValueEx(key, "InstallSource")
                                    if os.path.exists(path) and self._validate_game_directory(path):
                                        return path
                                except:
                                    pass
                                
                                # 备用查找InstallLocation
                                try:
                                    path, _ = winreg.QueryValueEx(key, "InstallLocation")
                                    if os.path.exists(path) and self._validate_game_directory(path):
                                        return path
                                except:
                                    pass
                        except Exception as e:
                            continue
                    
                    return ""
                except Exception as e:
                    print(f"从注册表查找游戏路径时出错: {e}")
                    return ""
            
            def _find_poe2_common_locations(self):
                """在常见位置查找POE2游戏目录"""
                # 搜索WeGame安装路径模式
                potential_drives = ['C', 'D', 'E', 'F', 'G', 'H']
                base_patterns = [
                    "Game\\WeGameApps\\rail_apps",
                    "WeGame\\WeGameApps\\rail_apps", 
                    "Program Files\\WeGame\\WeGameApps\\rail_apps",
                    "Program Files (x86)\\WeGame\\WeGameApps\\rail_apps"
                ]
                
                for drive in potential_drives:
                    if self.stopped:
                        return ""
                    for pattern in base_patterns:
                        base_path = f"{drive}:\\{pattern}"
                        if os.path.exists(base_path):
                            try:
                                for item in os.listdir(base_path):
                                    if any(keyword in item for keyword in ["流放之路", "降临"]):
                                        game_path = os.path.join(base_path, item)
                                        if os.path.isdir(game_path) and self._validate_game_directory(game_path):
                                            return game_path
                            except Exception as e:
                                continue
                
                # 备用：传统Path of Exile 2路径
                traditional_locations = [
                    "C:\\Program Files\\Path of Exile 2",
                    "D:\\Program Files\\Path of Exile 2"
                ]
                
                for location in traditional_locations:
                    if self.stopped:
                        return ""
                    if os.path.exists(location) and self._validate_game_directory(location):
                        return location
                
                return ""
            
            def _validate_game_directory(self, directory):
                """验证目录是否为有效的POE2游戏目录"""
                try:
                    exe_path = os.path.join(directory, "PathOfExile.exe")
                    exe_x64_path = os.path.join(directory, "PathOfExile_x64.exe")
                    return os.path.exists(exe_path) or os.path.exists(exe_x64_path)
                except:
                    return False
            
            def _full_disk_search(self):
                """全盘搜索作为最后手段"""
                try:
                    potential_drives = ['C', 'D', 'E', 'F', 'G', 'H']
                    
                    for drive in potential_drives:
                        if self.stopped:
                            return ""
                        
                        self.search_progress.emit(f"正在全盘搜索驱动器 {drive}...")
                        
                        try:
                            # 跳过可移动设备
                            if self._is_removable_drive(f"{drive}:"):
                                continue
                                
                            # 搜索特定模式而不是全盘遍历
                            search_patterns = [
                                f"{drive}:\\*WeGameApps*",
                                f"{drive}:\\*rail_apps*", 
                                f"{drive}:\\*流放之路*",
                                f"{drive}:\\*Path of Exile 2*"
                            ]
                            
                            for pattern in search_patterns:
                                if self.stopped:
                                    return ""
                                try:
                                    import glob
                                    for path in glob.glob(pattern):
                                        if os.path.isdir(path) and self._validate_game_directory(path):
                                            return path
                                        # 如果是WeGameApps或rail_apps目录，搜索子目录
                                        if any(keyword in path.lower() for keyword in ["wegameapps", "rail_apps"]):
                                            for subdir in os.listdir(path):
                                                subpath = os.path.join(path, subdir)
                                                if os.path.isdir(subpath) and any(keyword in subdir for keyword in ["流放之路", "降临", "Path of Exile"]):
                                                    if self._validate_game_directory(subpath):
                                                        return subpath
                                except Exception as e:
                                    continue
                        except Exception as e:
                            print(f"搜索驱动器 {drive} 时出错: {e}")
                            continue
                    
                    return ""
                except Exception as e:
                    print(f"全盘搜索时出错: {e}")
                    return ""
            
            def _is_removable_drive(self, drive):
                """检查是否为可移动驱动器（简化版）"""
                try:
                    total, used, free = shutil.disk_usage(drive)
                    return total < 64 * 1024 * 1024 * 1024  # 小于64GB可能是可移动设备
                except:
                    return True  # 出错时认为是可移动设备，跳过
        
        # 创建并启动线程
        self.game_search_thread = GameSearchThread(self)
        self.game_search_thread.path_found.connect(self.on_game_path_found)
        self.game_search_thread.search_progress.connect(self.update_search_progress)
        
        # 设置超时定时器
        search_timeout = 300000  # 5分钟超时
        QTimer.singleShot(search_timeout, self._check_search_timeout)
        
        self.game_search_thread.start()
    
    def _check_search_timeout(self):
        """检查搜索是否已超时"""
        if hasattr(self, 'game_search_thread') and self.game_search_thread.isRunning():
            print("搜索超时，强制停止")
            self.game_search_thread.stop()
            self.poe_game_path_label.setText("游戏根目录: 搜索超时，未找到游戏")
            self.poe_game_path_label.setStyleSheet("font-size: 16px; color: #FF0000;")
    
    def update_search_progress(self, progress_text):
        """更新搜索进度显示"""
        self.poe_game_path_label.setText(f"游戏根目录: {progress_text}")
        # 减少UI更新频率，避免频繁调用processEvents
        # QApplication.processEvents()  # 移除此行
    
    def show_patch_output(self):
        """显示补丁安装的日志内容"""
        if hasattr(self, 'apatch_install_thread') and hasattr(self.apatch_install_thread, 'install_log'):
            log_content = self.apatch_install_thread.install_log
            if log_content:
                # 创建一个自定义对话框显示日志内容
                output_dialog = QDialog(self)
                output_dialog.setWindowTitle("A大补丁安装日志")
                output_dialog.resize(700, 500)  # 设置对话框大小

                layout = QVBoxLayout(output_dialog)

                # 创建文本编辑框显示日志内容
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                # 将日志列表转换为字符串
                log_text = "\n".join(log_content)
                text_edit.setText(log_text)
                text_edit.setLineWrapMode(QTextEdit.NoWrap)  # 不自动换行，保持日志格式

                # 使用等宽字体，更适合显示日志
                font = text_edit.font()
                font.setFamily("Courier New")
                text_edit.setFont(font)

                layout.addWidget(text_edit)

                # 添加"确定"按钮
                button_box = QDialogButtonBox(QDialogButtonBox.Ok)
                button_box.accepted.connect(output_dialog.accept)
                layout.addWidget(button_box)

                output_dialog.exec_()
            else:
                QMessageBox.information(self, "提示", "没有可用的安装日志信息")
        else:
            QMessageBox.information(self, "提示", "没有可用的安装日志信息") 
