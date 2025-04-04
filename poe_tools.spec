# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import codecs  # 添加 codecs 模块用于处理编码
import re  # 用于正则表达式匹配版本号

# 从poe_tools.py中提取版本号
version = "1.0.0"  # 默认版本号
try:
    with open('poe_tools.py', 'r', encoding='utf-8') as f:
        content = f.read()
        version_match = re.search(r'self\.current_version\s*=\s*["\']([0-9.]+)["\']', content)
        if version_match:
            version = version_match.group(1)
            print(f"检测到版本号: {version}")
except Exception as e:
    print(f"读取版本号时出错: {e}")

# 创建runtime_hook.py文件，确保使用UTF-8编码
with codecs.open('runtime_hook.py', 'w', encoding='utf-8') as f:
    f.write('''import os
import sys

# 将当前目录添加到DLL搜索路径
if hasattr(sys, '_MEIPASS'):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ['PATH']
''')

a = Analysis(
    ['poe_tools.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt5.QtNetwork'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],  # 添加运行时钩子
    excludes=[],
    noarchive=False,
)

# 显式添加 Python DLL 文件
python_dll = os.path.join(os.path.dirname(sys.executable), 'python310.dll')
if os.path.exists(python_dll):
    a.binaries += [('python310.dll', python_dll, 'BINARY')]
    # 也添加到datas确保可以找到
    a.datas += [('python310.dll', python_dll, 'DATA')]

# 确保app.ico作为数据文件包含
a.datas += [('app.ico', 'app.ico', 'DATA')]

pyz = PYZ(a.pure)

# 使用带版本号的文件名
exe_name = f'POE2PriceAid_v{version}'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,  # 使用带版本号的名称
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    onefile_tempdir='_poe2priceaid_temp',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',  # 确保此行正确设置了图标
)
