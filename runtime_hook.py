import os
import sys

# 将当前目录添加到DLL搜索路径
if hasattr(sys, '_MEIPASS'):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ['PATH']
