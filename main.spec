# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import codecs  # 添加 codecs 模块用于处理编码
import re  # 用于正则表达式匹配版本号
import subprocess  # 用于检测UPX

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

# 检测UPX是否安装及其路径
upx_executable = None
upx_dir = None

# 首先检查本地upx目录
local_upx_path = os.path.join(os.getcwd(), 'upx', 'upx.exe')
if os.path.exists(local_upx_path):
    upx_executable = local_upx_path
    upx_dir = os.path.dirname(upx_executable)
    print(f"找到本地UPX: {upx_executable}")
    print(f"UPX目录: {upx_dir}")
else:
    # 如果本地没有找到，再尝试在系统PATH中查找
    try:
        # 先尝试直接运行upx命令
        result = subprocess.run(['upx', '--version'], 
                             capture_output=True, text=True, 
                             timeout=5)  # 添加超时以防止挂起
        if result.returncode == 0:
            upx_version = result.stdout.strip().split('\n')[0]
            print(f"找到系统UPX: {upx_version}")
            
            # 尝试获取upx可执行文件的完整路径
            if sys.platform == 'win32':
                # Windows系统使用where命令
                try:
                    where_result = subprocess.run(['where', 'upx'], 
                                                capture_output=True, text=True)
                    if where_result.returncode == 0:
                        upx_executable = where_result.stdout.strip().split('\n')[0]
                        upx_dir = os.path.dirname(upx_executable)
                        print(f"系统UPX可执行文件位置: {upx_executable}")
                        print(f"系统UPX目录: {upx_dir}")
                except Exception as e:
                    print(f"获取系统UPX路径失败: {e}")
            else:
                # Linux/Mac系统使用which命令
                try:
                    which_result = subprocess.run(['which', 'upx'], 
                                                capture_output=True, text=True)
                    if which_result.returncode == 0:
                        upx_executable = which_result.stdout.strip()
                        upx_dir = os.path.dirname(upx_executable)
                        print(f"系统UPX可执行文件位置: {upx_executable}")
                        print(f"系统UPX目录: {upx_dir}")
                except Exception as e:
                    print(f"获取系统UPX路径失败: {e}")
    except Exception as e:
        print(f"系统中未安装UPX或未在PATH中: {e}")

# 如果没有找到UPX，显示提示
if not upx_executable:
    print("未找到UPX可执行文件")
    print("如需使用UPX压缩减小文件体积，请安装UPX: https://upx.github.io/")
    print("或将UPX添加到系统PATH中")
    print("或将UPX放在项目根目录的upx文件夹中")

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

# 定义UPX压缩排除的文件类型
# - Python DLL必须排除以避免兼容性问题
# - 系统关键DLL应该排除以避免潜在问题
# - 其他类型的文件可以安全地压缩以减小体积
upx_exclude_patterns = [
    python_version,            # 当前Python版本DLL
    'python3*.dll',            # 所有Python 3.x DLL
    'vcruntime*.dll',          # Visual C++ Runtime DLL
    'VCRUNTIME*.dll',
    'api-ms-win-*.dll',        # Windows API DLL
    'KERNEL*.dll',             # 核心系统DLL
    'msvcr*.dll',              # Microsoft Visual C Runtime
    'msvcp*.dll',
]

# 配置UPX选项
# 使用'--best'和'--lzma'获得更好的压缩率
upx_options = ['--best', '--lzma']
if upx_executable:
    print(f"将使用UPX压缩，选项: {' '.join(upx_options)}")
else:
    print("未找到UPX，将使用默认系统搜索路径")

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
