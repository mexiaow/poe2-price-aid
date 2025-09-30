#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: release.py

import os
import re
import json
import subprocess
import shutil
import requests
from datetime import datetime
from urllib.parse import quote
import sys

VERSION_FILE = 'version.txt'  # 存储版本号的文件

# WebDAV配置 - 支持多个备用服务器
WEBDAV_CONFIGS = [
    {
        'name': '主服务器',
        'url': 'https://poe2.1232323.xyz/dav/release',
        'username': 'POE2PriceAid',
        'password': 'POE2PriceAid',
        'download_url_base': 'https://poe2.1232323.xyz/d/POE2PriceAid/release/',
        'timeout': (10, 120)  # (连接超时, 读取超时)
    },
    # 可以添加更多备用服务器
    # {
    #     'name': '备用服务器',
    #     'url': 'https://backup-server.com/dav',
    #     'username': 'POE2PriceAid',
    #     'password': 'backup_password',
    #     'download_url_base': 'https://backup-server.com/d/POE2PriceAid/release/',
    #     'timeout': (10, 120)
    # }
]

# 向后兼容的单一配置
WEBDAV_CONFIG = WEBDAV_CONFIGS[0]

def get_next_version():
    """从version.txt读取当前版本号并计算下一个版本号"""
    try:
        # 检查版本文件是否存在
        if not os.path.exists(VERSION_FILE):
            # 如果不存在，创建初始版本号1.0.0
            with open(VERSION_FILE, 'w', encoding='utf-8') as f:
                f.write('1.0.0')
            return '1.0.1'  # 返回第一个版本号
        
        # 读取当前版本号
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            current_version = f.read().strip()
        
        # 解析版本号
        major, minor, patch = map(int, current_version.split('.'))
        
        # 递增补丁版本号
        patch += 1
        
        # 构建新版本号
        new_version = f"{major}.{minor}.{patch}"
        
        # 保存新版本号到文件
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            f.write(new_version)
        
        return new_version
    except Exception as e:
        print(f"❌ 获取下一个版本号失败: {e}")
        # 如果出错，回退到手动输入
        return None

def detect_encoding(file_path):
    """检测文件编码"""
    try:
        # 尝试常见编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'ascii']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read()
                return encoding
            except UnicodeDecodeError:
                continue
        
        # 如果常见编码都失败，尝试使用二进制模式读取前几千字节来猜测
        import chardet
        with open(file_path, 'rb') as f:
            raw_data = f.read(4096)
        result = chardet.detect(raw_data)
        return result['encoding']
    except Exception as e:
        print(f"检测编码失败: {e}")
        return 'utf-8'  # 默认返回utf-8

def update_version_in_source(new_version):
    """更新modules/config.py中的版本号"""
    file_path = os.path.join('modules', 'config.py')
    version_pattern = r'(CURRENT_VERSION\s*=\s*["\'])([0-9.]+)(["\'])'
    
    try:
        # 检测文件编码
        encoding = detect_encoding(file_path)
        print(f"检测到文件编码: {encoding}")
        
        # 使用检测到的编码读取文件
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        # 替换版本号
        updated_content = re.sub(version_pattern, r'\g<1>' + new_version + r'\g<3>', content)
        
        # 使用相同的编码写回文件
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(updated_content)
        
        print(f"✅ 已将modules/config.py中的版本号更新为: {new_version}")
        return True
    except Exception as e:
        print(f"❌ 更新modules/config.py版本号失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_json_file(version):
    """更新update.json文件中的版本号和下载URL"""
    # 使用WebDAV下载URL
    download_url = f"{WEBDAV_CONFIG['download_url_base']}POE2PriceAid_v{version}.exe"
    
    try:
        # 创建新的update.json内容
        data = {
            'version': version,
            'download_url': download_url,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 写入update.json
        with open('update.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已更新update.json: 版本 {version}, 下载URL {download_url}")
        return True
    except Exception as e:
        print(f"❌ 更新update.json失败: {e}")
        return False

def upload_to_webdav(version):
    """将程序和update.json上传到WebDAV服务器，并只保留最新的5个版本"""
    print("📤 正在上传文件到WebDAV服务器...")
    
    # 输出WebDAV配置信息（不含密码）
    masked_password = '*' * len(WEBDAV_CONFIG['password']) if WEBDAV_CONFIG['password'] else ''
    print(f"📋 WebDAV配置信息:")
    print(f"  - URL: {WEBDAV_CONFIG['url']}")
    print(f"  - 用户名: {WEBDAV_CONFIG['username']}")
    print(f"  - 密码: {masked_password}")
    print(f"  - 下载基础URL: {WEBDAV_CONFIG['download_url_base']}")
    
    try:
        # 准备要上传的文件
        exe_file = os.path.join("dist", f"POE2PriceAid_v{version}.exe")
        json_file = "update.json"
        
        # 检查文件是否存在
        if not os.path.exists(exe_file):
            print(f"❌ 可执行文件不存在: {exe_file}")
            
            # 尝试在dist目录下查找匹配的文件
            dist_files = []
            for root, dirs, files in os.walk("dist"):
                for file in files:
                    if file.startswith("POE2PriceAid") and file.endswith(".exe"):
                        dist_files.append(os.path.join(root, file))
            
            if dist_files:
                # 使用找到的第一个文件
                exe_file = dist_files[0]
                print(f"找到打包文件: {exe_file}")
            else:
                print("❌ 在dist目录中未找到任何POE2PriceAid*.exe文件")
                return False
        
        if not os.path.exists(json_file):
            print(f"❌ update.json文件不存在")
            return False
        
        # 输出文件信息
        exe_size = os.path.getsize(exe_file) / (1024 * 1024)  # 转换为MB
        print(f"📂 准备上传文件:")
        print(f"  - 可执行文件: {exe_file} ({exe_size:.2f} MB)")
        print(f"  - JSON文件: {json_file} ({os.path.getsize(json_file)} 字节)")
        
        # 上传可执行文件
        print(f"🔄 正在上传可执行文件到 {WEBDAV_CONFIG['url']}/POE2PriceAid_v{version}.exe ...")
        with open(exe_file, 'rb') as f:
            exe_data = f.read()
        
        # 设置超时参数，大文件可能需要更长时间
        timeout = (30, 300)  # (连接超时, 读取超时)
        print(f"⏱️ 设置请求超时: 连接 {timeout[0]} 秒, 读取 {timeout[1]} 秒")
        
        # 测试服务器连接
        try:
            print("🔍 测试WebDAV服务器连接...")
            test_response = requests.options(
                WEBDAV_CONFIG['url'],
                auth=(WEBDAV_CONFIG['username'], WEBDAV_CONFIG['password']),
                timeout=10
            )
            print(f"✅ 服务器连接测试: HTTP {test_response.status_code}")
            print(f"  - 服务器headers: {dict(test_response.headers)}")
        except Exception as e:
            print(f"⚠️ 服务器连接测试失败: {e}")
            print("  但仍将尝试上传文件...")
        
        exe_response = requests.put(
            f"{WEBDAV_CONFIG['url']}/POE2PriceAid_v{version}.exe",
            data=exe_data,
            auth=(WEBDAV_CONFIG['username'], WEBDAV_CONFIG['password']),
            headers={'Content-Type': 'application/octet-stream'},
            timeout=timeout
        )
        
        print(f"📡 EXE上传响应状态码: HTTP {exe_response.status_code}")
        print(f"📡 EXE上传响应headers: {dict(exe_response.headers)}")
        
        if exe_response.status_code not in (200, 201, 204):
            print(f"❌ 上传可执行文件失败: HTTP {exe_response.status_code}")
            print(f"  - 响应内容: {exe_response.text[:500]}..." if len(exe_response.text) > 500 else exe_response.text)
            return False
        
        # 上传update.json文件
        print(f"🔄 正在上传update.json到 {WEBDAV_CONFIG['url']}/update.json ...")
        with open(json_file, 'rb') as f:
            json_data = f.read()
        
        json_response = requests.put(
            f"{WEBDAV_CONFIG['url']}/update.json",
            data=json_data,
            auth=(WEBDAV_CONFIG['username'], WEBDAV_CONFIG['password']),
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        
        print(f"📡 JSON上传响应状态码: HTTP {json_response.status_code}")
        print(f"📡 JSON上传响应headers: {dict(json_response.headers)}")
        
        if json_response.status_code not in (200, 201, 204):
            print(f"❌ 上传update.json文件失败: HTTP {json_response.status_code}")
            print(f"  - 响应内容: {json_response.text}")
            return False
        
        print(f"✅ 文件上传成功")
        print(f"  - 可执行文件: {WEBDAV_CONFIG['url']}/POE2PriceAid_v{version}.exe")
        print(f"  - update.json: {WEBDAV_CONFIG['url']}/update.json")
        print(f"  - 下载链接: {WEBDAV_CONFIG['download_url_base']}POE2PriceAid_v{version}.exe")
        
        # 清理旧版本，只保留最新的3个版本
        clean_old_versions()
        
        # 清理本地dist文件夹，只保留最新的3个版本
        clean_local_dist_folder()
        
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接WebDAV服务器失败: {e}")
        print(f"  - 请检查网络连接和WebDAV服务器地址是否正确")
        import traceback
        traceback.print_exc()
        return False
    except requests.exceptions.Timeout as e:
        print(f"❌ 上传文件超时: {e}")
        print(f"  - 文件可能太大或网络连接太慢，请尝试增加超时时间")
        import traceback
        traceback.print_exc()
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP请求错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ 上传到WebDAV失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def clean_old_versions():
    """清理WebDAV服务器上的旧版本，只保留最新的3个版本"""
    print("🧹 正在检查并清理旧版本...")
    try:
        # 使用PROPFIND方法获取WebDAV服务器上的文件列表
        headers = {
            'Depth': '1',  # 只获取当前目录的文件，不包括子目录
            'Content-Type': 'application/xml'
        }
        
        response = requests.request(
            'PROPFIND',
            WEBDAV_CONFIG['url'],
            auth=(WEBDAV_CONFIG['username'], WEBDAV_CONFIG['password']),
            headers=headers
        )
        
        if response.status_code != 207:  # 207是WebDAV的Multi-Status响应
            print(f"❌ 获取文件列表失败: HTTP {response.status_code}")
            return False
        
        # 解析XML响应，提取文件名
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        
        # 查找所有POE2PriceAid_v*.exe文件
        version_files = []
        for response_elem in root.findall('.//{DAV:}response'):
            href = response_elem.find('.//{DAV:}href').text
            filename = os.path.basename(href)
            
            # 匹配POE2PriceAid_v*.exe文件
            match = re.match(r'POE2PriceAid_v(\d+\.\d+\.\d+)\.exe', filename)
            if match:
                version = match.group(1)
                version_files.append((version, filename))
        
        # 按版本号排序（从新到旧）
        version_files.sort(key=lambda x: [int(n) for n in x[0].split('.')], reverse=True)
        
        # 如果版本数量超过3个，删除旧版本
        if len(version_files) > 3:
            print(f"发现 {len(version_files)} 个版本，将只保留最新的3个版本")
            
            # 保留最新的3个版本
            keep_versions = version_files[:3]
            delete_versions = version_files[3:]
            
            # 打印将保留的版本
            print("将保留以下版本:")
            for version, filename in keep_versions:
                print(f"  - {filename}")
            
            # 删除旧版本
            print("正在删除以下旧版本:")
            for version, filename in delete_versions:
                print(f"  - {filename}")
                
                # 发送DELETE请求删除文件
                delete_response = requests.delete(
                    f"{WEBDAV_CONFIG['url']}/{filename}",
                    auth=(WEBDAV_CONFIG['username'], WEBDAV_CONFIG['password'])
                )
                
                if delete_response.status_code not in (200, 204):
                    print(f"    ❌ 删除失败: HTTP {delete_response.status_code}")
                else:
                    print(f"    ✅ 删除成功")
            
            print("✅ 旧版本清理完成")
        else:
            print(f"当前共有 {len(version_files)} 个版本，不需要清理")
        
        return True
    except Exception as e:
        print(f"❌ 清理旧版本失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def clean_local_dist_folder():
    """清理本地dist文件夹中的旧版本，只保留最新的3个版本"""
    print("🧹 正在检查并清理本地dist文件夹中的旧版本...")
    try:
        dist_folder = "dist"
        if not os.path.exists(dist_folder) or not os.path.isdir(dist_folder):
            print(f"❌ dist文件夹不存在")
            return False
        
        # 获取dist文件夹中所有的POE2PriceAid_v*.exe文件
        version_files = []
        for filename in os.listdir(dist_folder):
            # 匹配POE2PriceAid_v*.exe文件
            match = re.match(r'POE2PriceAid_v(\d+\.\d+\.\d+)\.exe', filename)
            if match:
                version = match.group(1)
                version_files.append((version, filename))
        
        # 按版本号排序（从新到旧）
        version_files.sort(key=lambda x: [int(n) for n in x[0].split('.')], reverse=True)
        
        # 如果版本数量超过3个，删除旧版本
        if len(version_files) > 3:
            print(f"本地dist文件夹中发现 {len(version_files)} 个版本，将只保留最新的3个版本")
            
            # 保留最新的3个版本
            keep_versions = version_files[:3]
            delete_versions = version_files[3:]
            
            # 打印将保留的版本
            print("将保留以下版本:")
            for version, filename in keep_versions:
                print(f"  - {filename}")
            
            # 删除旧版本
            print("正在删除以下旧版本:")
            for version, filename in delete_versions:
                file_path = os.path.join(dist_folder, filename)
                print(f"  - {filename}")
                
                try:
                    os.remove(file_path)
                    print(f"    ✅ 删除成功")
                except Exception as e:
                    print(f"    ❌ 删除失败: {e}")
            
            print("✅ 本地dist文件夹清理完成")
        else:
            print(f"本地dist文件夹中当前共有 {len(version_files)} 个版本，不需要清理")
        
        return True
    except Exception as e:
        print(f"❌ 清理本地dist文件夹失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_syntax():
    """检查main.py的语法"""
    print("🔍 检查main.py语法...")
    try:
        result = subprocess.run(['python', '-m', 'py_compile', 'main.py'], 
                               capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ 语法检查失败！错误信息:")
            print(result.stderr)
            return False
        print("✅ 语法检查通过")
        return True
    except Exception as e:
        print(f"❌ 语法检查失败: {e}")
        return False

def clean_cache_before_packaging():
    """在打包前清理缓存目录，只清理必要的缓存，保护用户数据"""
    print("🧹 正在清理打包相关缓存...")
    try:
        # 定义只需要清理的项目级缓存目录
        project_cache_dirs = []
        
        # 定义保护的用户数据目录
        protected_dirs = []
        
        # 只清理当前项目目录的缓存
        current_dir = os.getcwd()
        project_cache_dirs = [
            os.path.join(current_dir, '__pycache__'),
            os.path.join(current_dir, 'build'),  # PyInstaller build目录
            os.path.join(current_dir, '.pytest_cache'),  # pytest缓存
            os.path.join(current_dir, 'modules', '__pycache__'),  # modules缓存
        ]
        
        # 只清理项目级缓存，保护所有用户数据
        cleaned = False
        for cache_dir in project_cache_dirs:
            if os.path.exists(cache_dir):
                print(f"  - 清理项目缓存: {cache_dir}")
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    cleaned = True
                except Exception as e:
                    print(f"    清理失败: {e}")
        
        # 只清理当前项目目录下的.pyc和.pyo文件
        pyc_count = 0
        
        # 只在当前项目目录中搜索
        for root, dirs, files in os.walk(current_dir):
            # 跳过虚拟环境目录和其他不相关目录
            dirs[:] = [d for d in dirs if d not in ['.venv', 'venv', 'env', '.git', 'node_modules', 'dist']]
            
            for file in files:
                if file.endswith(('.pyc', '.pyo')):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        pyc_count += 1
                    except Exception:
                        pass  # 忽略无法删除的文件
        
        if pyc_count > 0:
            print(f"  - 清理了 {pyc_count} 个项目编译文件")
        
        if cleaned or pyc_count > 0:
            print("✅ 项目缓存清理完成")
        else:
            print("ℹ️ 未找到需要清理的项目缓存")
        
        return True
    except Exception as e:
        print(f"❌ 清理缓存目录时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_pyinstaller():
    """运行PyInstaller打包应用（不处理任何UPX相关逻辑）"""
    print("🔧 正在打包应用程序...")
    try:
        command = ['pyinstaller', '--clean', '--noconfirm', 'main.spec']
        print(f"执行命令: {' '.join(command)}")
        result = subprocess.run(command)
        if result.returncode != 0:
            print("❌ 打包失败")
            return False
        print("✅ 应用程序打包成功")
        return True
    except Exception as e:
        print(f"❌ 执行pyinstaller命令失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def copy_to_desktop(version):
    """将打包好的程序复制到桌面"""
    print("📋 正在将程序复制到桌面...")
    try:
        # 获取桌面路径
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        
        # 打包后的文件路径（带版本号）
        source_file = os.path.join("dist", f"POE2PriceAid_v{version}.exe")
        
        # 如果以上路径不存在，尝试在dist目录下查找匹配的文件
        if not os.path.exists(source_file):
            print(f"在 {source_file} 路径未找到文件，正在搜索dist目录...")
            
            # 查找dist目录下所有可能的POE2PriceAid*.exe文件
            dist_files = []
            for root, dirs, files in os.walk("dist"):
                for file in files:
                    if file.startswith("POE2PriceAid") and file.endswith(".exe"):
                        dist_files.append(os.path.join(root, file))
            
            if dist_files:
                # 使用找到的第一个文件
                source_file = dist_files[0]
                print(f"找到打包文件: {source_file}")
            else:
                print("❌ 在dist目录中未找到任何POE2PriceAid*.exe文件")
                return False
        
        # 目标文件路径(带版本号)
        dest_file = os.path.join(desktop_path, f"POE2PriceAid_v{version}.exe")
        
        # 检查源文件是否存在
        if not os.path.exists(source_file):
            print(f"❌ 源文件不存在: {source_file}")
            return False
            
        # 复制文件到桌面
        shutil.copy2(source_file, dest_file)
        print(f"✅ 程序已复制到桌面: {dest_file}")
        return True
    except Exception as e:
        print(f"❌ 复制到桌面失败: {e}")
        import traceback
        traceback.print_exc()
    return False

def clean_build_directory():
    """清理build目录和__pycache__目录"""
    print("🧹 正在清理构建和缓存目录...")
    try:
        # 清理build目录
        build_path = "build"
        if os.path.exists(build_path) and os.path.isdir(build_path):
            shutil.rmtree(build_path)
            print("✅ build目录已清理")
        else:
            print("🔍 build目录不存在，无需清理")
        
        # 清理所有__pycache__目录
        cleaned_pycache = 0
        for root, dirs, files in os.walk('.'):
            for dir_name in dirs:
                if dir_name == "__pycache__":
                    pycache_path = os.path.join(root, dir_name)
                    try:
                        shutil.rmtree(pycache_path)
                        cleaned_pycache += 1
                    except Exception as e:
                        print(f"❌ 无法删除 {pycache_path}: {e}")
        
        if cleaned_pycache > 0:
            print(f"✅ 已清理 {cleaned_pycache} 个 __pycache__ 目录")
        else:
            print("🔍 未找到 __pycache__ 目录")
            
        return True
    except Exception as e:
        print(f"❌ 清理构建和缓存目录失败: {e}")
        return False

def commit_and_push(version):
    """提交所有更改并推送到Gitee和GitHub仓库"""
    print("\n🔄 正在准备提交和推送代码到远程仓库...")
    
    try:
        # 检查是否存在.git目录
        if not os.path.exists('.git') or not os.path.isdir('.git'):
            print("❌ 当前目录不是Git仓库，跳过提交和推送步骤")
            return False
        
        # 检查Git远程仓库配置
        print("🔍 检查Git远程仓库配置...")
        remotes_result = subprocess.run(['git', 'remote', '-v'], 
                                      capture_output=True, text=True)
        
        if remotes_result.returncode != 0:
            print(f"❌ 获取Git远程仓库信息失败: {remotes_result.stderr}")
            return False
        
        # 解析远程仓库信息
        remotes = remotes_result.stdout.strip()
        print(f"📋 已配置的Git远程仓库:")
        print(remotes)
        
        # 查找包含gitee.com和github.com的远程仓库（记录实际仓库名称）
        remote_configs = []
        
        remote_lines = remotes.split('\n')
        for line in remote_lines:
            if '(push)' in line:  # 只查找推送用的远程仓库配置
                parts = line.strip().split()
                if len(parts) >= 2:
                    remote_name = parts[0]
                    remote_url = parts[1]
                    
                    if 'gitee.com' in remote_url:
                        print(f"✅ 检测到Gitee远程仓库: {remote_name} -> {remote_url}")
                        remote_configs.append((remote_name, 'Gitee', remote_url))
                    
                    if 'github.com' in remote_url:
                        print(f"✅ 检测到GitHub远程仓库: {remote_name} -> {remote_url}")
                        remote_configs.append((remote_name, 'GitHub', remote_url))
        
        if not remote_configs:
            print("⚠️ 未检测到Gitee或GitHub远程仓库配置")
            confirm = input("是否仍要继续? (Y/N, 默认N): ").strip().upper()
            if confirm != 'Y':
                print("已取消Git操作")
                return False
        
        # 确认提交
        print("\n即将提交所有更改并推送到远程仓库")
        print(f"提交消息将包含版本号: v{version}")
        input("按Enter键继续提交和推送操作...")
        
        # 检查Git状态
        print("\n🔍 检查Git工作区状态...")
        status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                     capture_output=True, text=True)
        
        if status_result.returncode != 0:
            print(f"❌ 获取Git状态失败: {status_result.stderr}")
            return False
        
        # 如果没有更改，提示用户
        if not status_result.stdout.strip():
            print("ℹ️ 工作区没有需要提交的更改")
            confirm = input("是否继续推送操作? (Y/N, 默认Y): ").strip().upper()
            if confirm == 'N':
                print("已取消Git操作")
                return False
        else:
            # 显示更改的文件
            print("📝 工作区有以下更改:")
            print(status_result.stdout)
            
            # 添加所有更改到暂存区
            print("\n🔄 添加所有更改到Git暂存区...")
            add_result = subprocess.run(['git', 'add', '.'], 
                                      capture_output=True, text=True)
            
            if add_result.returncode != 0:
                print(f"❌ 添加更改到暂存区失败: {add_result.stderr}")
                return False
            
            # 提交更改
            commit_message = f"发布版本 v{version} ({datetime.now().strftime('%Y-%m-%d')})"
            print(f"\n🔄 提交更改: {commit_message}")
            
            commit_result = subprocess.run(
                ['git', 'commit', '-m', commit_message], 
                capture_output=True, text=True
            )
            
            if commit_result.returncode != 0:
                print(f"❌ 提交更改失败: {commit_result.stderr}")
                return False
            
            print(f"✅ 成功提交更改: {commit_message}")
        
        # 获取当前分支
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
            capture_output=True, text=True
        )
        
        if branch_result.returncode != 0:
            print(f"❌ 获取当前分支失败: {branch_result.stderr}")
            current_branch = 'master'  # 默认使用master
            print(f"   使用默认分支: {current_branch}")
        else:
            current_branch = branch_result.stdout.strip()
            print(f"   当前分支: {current_branch}")
        
        # 推送到远程仓库
        if not remote_configs:
            # 如果没有检测到gitee或github远程仓库，但用户选择继续，则尝试推送到origin
            print("⚠️ 未找到Gitee或GitHub远程仓库，将尝试推送到origin...")
            remote_configs.append(('origin', '默认', 'origin'))
        
        success_count = 0
        for remote_name, remote_type, remote_url in remote_configs:
            print(f"\n🔄 正在推送到 {remote_type} ({remote_name})...")
            
            # 推送到远程仓库
            push_result = subprocess.run(
                ['git', 'push', remote_name, current_branch], 
                capture_output=True, text=True
            )
            
            if push_result.returncode != 0:
                print(f"❌ 推送到 {remote_type} ({remote_name}) 失败: {push_result.stderr}")
                print("   将尝试下一个远程仓库")
            else:
                print(f"✅ 成功推送到 {remote_type} ({remote_name})")
                success_count += 1
        
        if success_count > 0:
            print(f"\n✨ Git操作完成，成功推送到 {success_count} 个远程仓库")
        else:
            print("\n⚠️ Git操作完成，但未能成功推送到任何远程仓库")
        
        return True
    except Exception as e:
        print(f"❌ 执行Git操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数，协调整个发布流程"""
    print("\n===================================")
    print("  POE2PriceAid 发布工具 (main.py版)")
    print("===================================\n")
    
    # 获取下一个版本号
    new_version = get_next_version()
    
    # 如果自动获取版本号失败，则回退到手动输入
    if not new_version:
        while True:
            new_version = input("自动获取版本号失败，请手动输入新版本号 (例如 1.0.3): ").strip()
            if new_version and re.match(r'^\d+\.\d+\.\d+$', new_version):
                break
            print("❌ 无效的版本号格式，请使用 x.y.z 格式 (例如 1.0.3)")
    else:
        print(f"自动递增版本号: {new_version}")
    
    # 确认操作
    print(f"\n您将发布的版本号是: {new_version}")
    confirm = input("确认继续? (Y/N, 默认Y): ").strip().upper()
    if confirm == 'N':
        print("已取消操作")
        return
    
    print("\n🚀 开始执行发布流程...\n")
    
    # 1. 更新modules/config.py中的版本号
    if not update_version_in_source(new_version):
        return
    
    # 2. 更新update.json
    if not update_json_file(new_version):
        return
    
    # 3. 检查语法
    if not check_syntax():
        print("\n⚠️ 警告: main.py存在语法错误，请修复后再继续")
        return
    
    # 4. 在打包前清理缓存
    if not clean_cache_before_packaging():
        print("\n⚠️ 警告: 清理缓存失败，可能会影响字体大小一致性")
        confirm = input("是否继续打包? (Y/N, 默认Y): ").strip().upper()
        if confirm == 'N':
            print("已取消操作")
            return
    
    # 5. 运行PyInstaller
    if not run_pyinstaller():
        return
    
    # 6. 复制到桌面
    # copy_to_desktop(new_version)
    
    # 7. 上传到WebDAV
    if not upload_to_webdav(new_version):
        print("\n⚠️ 警告: 上传到WebDAV失败，请手动上传文件")
    
    # 8. 清理build目录
    clean_build_directory()
    
    # 9. 提交和推送到Gitee和GitHub
    commit_and_push(new_version)
    
    print("\n✨ 发布流程完成! ✨")
    print(f"版本号: {new_version}")
    print("\n📋 后续步骤:")
    print(f"1. 程序已打包到dist文件夹")
    print(f"2. 程序和update.json已上传到WebDAV服务器")
    print(f"3. 下载链接: {WEBDAV_CONFIG['download_url_base']}POE2PriceAid_v{new_version}.exe")
    print(f"4. 代码更改已提交并推送到远程Git仓库")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    
    input("\n按Enter键退出...")
