#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: release.py

import os
import re
import json
import subprocess
from datetime import datetime

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
        # 使用subprocess.run执行pyinstaller命令
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

def main():
    """主函数，协调整个发布流程"""
    print("\n===================================")
    print("      POE2PriceAid 发布工具")
    print("===================================\n")
    
    # 提示用户输入版本号
    while True:
        new_version = input("请输入新版本号 (例如 1.0.3): ").strip()
        if new_version and re.match(r'^\d+\.\d+\.\d+$', new_version):
            break
        print("❌ 无效的版本号格式，请使用 x.y.z 格式 (例如 1.0.3)")
    
    # 确认操作
    print(f"\n您输入的版本号是: {new_version}")
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
    
    print("\n✨ 发布流程完成! ✨")
    print(f"版本号: {new_version}")
    print("\n📋 后续步骤:")
    print(f"1. 在dist文件夹中找到打包好的程序")
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
