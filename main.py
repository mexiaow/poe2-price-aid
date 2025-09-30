"""
POE2PriceAid 主程序入口
"""

import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer

from modules.config import Config
from modules import startup_profiler


def main():
    """主程序入口函数"""
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.xcb.debug=false'

    if os.environ.get('POE2_PROFILE_STARTUP'):
        startup_profiler.enable()
        startup_profiler.mark('main: start')

    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    startup_profiler.mark('main: Qt attributes set')

    try:
        from modules.stats_collector import record_startup
        record_startup()
        startup_profiler.mark('main: stats collector recorded')
    except Exception:
        startup_profiler.mark('main: stats collector skipped')

    if getattr(sys, 'frozen', False):
        os.environ['PATH'] = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)) + os.pathsep + os.environ['PATH']

        import ctypes
        try:
            dll_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'python312.dll')
            if os.path.exists(dll_path):
                ctypes.CDLL(dll_path)
        except Exception:
            pass
        startup_profiler.mark('main: frozen path prepared')

    # 直接加载真实模块，不使用懒加载占位（避免 UI 异常/功能缺失）
    startup_profiler.mark('main: stubs skipped')

    app = QApplication(sys.argv)
    app.setApplicationName("POE2PriceAid")
    app.setOrganizationName("POE2PriceAid")
    startup_profiler.mark('main: QApplication created')

    # Import UI after stubs are in place
    from modules.ui_core import MainWindow
    window = MainWindow()
    startup_profiler.mark('main: MainWindow constructed')

    window.show()
    startup_profiler.mark('main: MainWindow shown')

    # 在 profiling 模式下，可通过环境变量指定自动退出毫秒数，方便采集启动日志
    try:
        exit_after = int(os.environ.get('POE2_EXIT_AFTER_MS', '0'))
    except Exception:
        exit_after = 0
    if exit_after > 0:
        QTimer.singleShot(exit_after, app.quit)

    startup_profiler.mark('main: entering event loop')
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
