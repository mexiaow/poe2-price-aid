import os
import sys
import time
import shutil
import subprocess
from PyQt5.QtWidgets import QApplication, QProgressDialog, QMessageBox
from PyQt5.QtCore import Qt
import urllib.request

def update_app(download_url, app_path):
    app = QApplication(sys.argv)
    
    # 创建进度对话框
    progress_dialog = QProgressDialog("正在下载更新...", "取消", 0, 100)
    progress_dialog.setWindowTitle("更新程序")
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setAutoClose(True)
    progress_dialog.setMinimumDuration(0)
    progress_dialog.setValue(0)
    progress_dialog.show()
    
    # 下载新版本
    temp_file = "POE2PriceAid_new.exe"
    
    def update_progress(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        progress_dialog.setValue(min(percent, 100))
        QApplication.processEvents()
        if progress_dialog.wasCanceled():
            sys.exit(0)
    
    try:
        # 下载新版本
        urllib.request.urlretrieve(download_url, temp_file, reporthook=update_progress)
        progress_dialog.close()
        
        # 替换旧版本
        progress_dialog = QProgressDialog("正在安装更新...", None, 0, 0)
        progress_dialog.setWindowTitle("更新程序")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        # 等待一段时间，确保主程序已经完全退出
        time.sleep(2)
        
        # 替换可执行文件
        shutil.copy2(temp_file, app_path)
        os.remove(temp_file)
        
        progress_dialog.close()
        
        # 启动新版本
        subprocess.Popen([app_path])
        
        # 显示成功消息
        QMessageBox.information(None, "更新完成", "更新已成功安装，程序将重新启动。")
        
    except Exception as e:
        progress_dialog.close()
        QMessageBox.critical(None, "更新失败", f"更新过程中出错: {e}")
    
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: updater.py <下载URL> <应用程序路径>")
        sys.exit(1)
    
    download_url = sys.argv[1]
    app_path = sys.argv[2]
    update_app(download_url, app_path) 