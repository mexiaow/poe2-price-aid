#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: release.py

import os
import re
import json
import subprocess
import shutil
from datetime import datetime

VERSION_FILE = 'version.txt'  # 存储版本号的文件

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
    """更新poe_tools.py中的版本号"""
    file_path = 'poe_tools.py'
    version_pattern = r'(self\.current_version\s*=\s*["\'])([0-9.]+)(["\'])'
    
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
        
        print(f"✅ 已将poe_tools.py中的版本号更新为: {new_version}")
        return True
    except Exception as e:
        print(f"❌ 更新poe_tools.py版本号失败: {e}")
        return False

def update_json_file(version):
    """更新update.json文件中的版本号和下载URL"""
    # GitHub下载URL - 不带v前缀的路径，但文件名带v前缀
    download_url = f"https://github.com/mexiaow/poe_tools/releases/download/{version}/POE2PriceAid_v{version}.exe"
    
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

def check_syntax():
    """检查poe_tools.py的语法"""
    print("🔍 检查poe_tools.py语法...")
    try:
        result = subprocess.run(['python', '-m', 'py_compile', 'poe_tools.py'], 
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

def run_pyinstaller():
    """运行PyInstaller打包应用"""
    print("🔧 正在打包应用程序...")
    try:
        # 使用已有的spec文件进行打包，不添加额外选项
        result = subprocess.run(['pyinstaller', 'poe_tools.spec'], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("❌ 打包失败！错误信息:")
            print(result.stderr)
            return False
        
        print("✅ 应用程序打包成功")
        return True
    except Exception as e:
        print(f"❌ 执行pyinstaller命令失败: {e}")
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

def main():
    """主函数，协调整个发布流程"""
    print("\n===================================")
    print("      POE2PriceAid 发布工具")
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
    
    # 1. 更新poe_tools.py中的版本号
    if not update_version_in_source(new_version):
        return
    
    # 2. 更新update.json
    if not update_json_file(new_version):
        return
    
    # 3. 检查语法
    if not check_syntax():
        print("\n⚠️ 警告: poe_tools.py存在语法错误，请修复后再继续")
        print("提示: 检查第85-86行的缩进问题")
        return
    
    # 4. 运行PyInstaller
    if not run_pyinstaller():
        return
    
    # 5. 复制到桌面
    copy_to_desktop(new_version)
    
    print("\n✨ 发布流程完成! ✨")
    print(f"版本号: {new_version}")
    print("\n📋 后续步骤:")
    print(f"1. 程序已打包到dist文件夹，并复制到桌面")
    print(f"2. 创建新的GitHub Release，标签为 {new_version} (不带v前缀)")
    print(f"3. 上传程序并发布Release")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    
    input("\n按Enter键退出...")
