# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import codecs  # 添加 codecs 模块用于处理编码
import re  # 用于正则表达式匹配版本号

# 从modules/config.py中提取版本号
version = "1.0.0"  # 默认版本号
try:
    with open(os.path.join('modules', 'config.py'), 'r', encoding='utf-8') as f:
        content = f.read()
        version_match = re.search(r'CURRENT_VERSION\s*=\s*["\']([0-9.]+)["\']', content)
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

# 确定Python主版本号，用于后续DLL处理
python_version = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
print(f"使用Python版本: {python_version}")

# 已移除所有UPX检测与提示，打包始终不使用UPX

block_cipher = None

a = Analysis(
    ['main.py'],  # 使用main.py作为入口点
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.Qt',
        'requests',
        'bs4',
        'chardet',
        'urllib3',
        'lxml',
        'py7zr',
        'psutil',
        'json',
        'datetime',
        'modules.config',
        'modules.ui_core',
        'modules.price_monitor',
        'modules.web_monitor',
        'modules.apatch',
        'modules.filter',
        'modules.update_checker',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],  # 添加运行时钩子
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy',
        'pandas',
        'PIL',
    ],  # 排除不需要的包减小体积
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 检测并添加Python DLL文件
# 首先尝试使用主Python版本的DLL
python_dll = os.path.join(os.path.dirname(sys.executable), python_version)
if os.path.exists(python_dll):
    print(f"Found Python DLL at: {python_dll}")
    a.binaries += [(python_version, python_dll, 'BINARY')]
    # 也添加到datas确保可以找到
    a.datas += [(python_version, python_dll, 'DATA')]
else:
    print(f"Warning: {python_version} not found at {python_dll}")
    # 尝试几个常见的Python版本作为后备
    backup_versions = ["python310.dll", "python311.dll", "python312.dll"]
    for backup_dll in backup_versions:
        backup_path = os.path.join(os.path.dirname(sys.executable), backup_dll)
        if os.path.exists(backup_path):
            print(f"Using backup Python DLL: {backup_path}")
            a.binaries += [(backup_dll, backup_path, 'BINARY')]
            a.datas += [(backup_dll, backup_path, 'DATA')]
            break

# 确保app.ico作为数据文件包含
if os.path.exists('app.ico'):
    a.datas += [('app.ico', 'app.ico', 'DATA')]
    print("添加图标文件: app.ico")
else:
    print("警告: 未找到图标文件 app.ico")

# 添加自动喝药脚本文件
ahk_script_path = os.path.join('scripts', 'auto_HPES.ahk')
if os.path.exists(ahk_script_path):
    a.datas += [(ahk_script_path, ahk_script_path, 'DATA')]
    print(f"添加自动喝药脚本: {ahk_script_path}")
else:
    print(f"警告: 未找到自动喝药脚本 {ahk_script_path}")

# 添加其他版本文件
version_files = [
    'version.txt', 
    'version_过滤器.txt', 
    'version_A大补丁.json', 
    'version_Notice.txt',
    'update.json'
]
for file in version_files:
    if os.path.exists(file):
        a.datas += [(file, file, 'DATA')]
        print(f"添加数据文件: {file}")
    else:
        print(f"警告: 未找到文件 {file}")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 使用带版本号的文件名
exe_name = f'POE2PriceAid_v{version}'

# 无UPX选项或排除设置

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
    upx=False,                  # 禁用UPX压缩
    # 以下UPX相关参数在upx=False时不起作用
    # upx_exclude=upx_exclude_patterns,  # 排除模式不再需要
    # upx_dir=upx_dir,           # UPX目录不再需要
    # upx_options=upx_options,   # UPX选项不再需要
    runtime_tmpdir=None,
    onefile_tempdir='_poe2priceaid_temp',
    console=False,  # 设为False以隐藏控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',  # 确保此行正确设置了图标
)

print(f"打包完成，输出文件: dist/{exe_name}.exe") 
