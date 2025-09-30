"""
POE2PriceAid 使用统计收集模块
独立模块，静默运行，不干扰主程序功能
"""

import requests
import threading
import hashlib
import platform
from datetime import datetime
from modules.config import Config


class StatsCollector:
    """统计信息收集器"""
    
    def __init__(self):
        # WebDAV统计服务器配置
        self.webdav_url = "https://poe2.1232323.xyz/dav/stats"
        self.username = "POE2PriceAid"
        self.password = "POE2PriceAid"
        
        # 生成用户唯一标识
        self.user_id = self._generate_user_id()
        self.computer_name = platform.node()
        self.user_file = f"user_{self.computer_name}_{self.user_id}.txt"  # 计算机名+ID格式
    
    def _generate_user_id(self):
        """生成基于MachineGuid的用户唯一标识"""
        try:
            import subprocess

            # 获取Windows机器GUID
            machine_guid = ""
            try:
                result = subprocess.run([
                    'reg', 'query',
                    'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography',
                    '/v', 'MachineGuid'
                ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if 'MachineGuid' in line:
                            machine_guid = line.split()[-1]
                            break
            except:
                pass

            # 只使用MachineGuid生成ID，更稳定
            if machine_guid:
                return hashlib.sha256(machine_guid.encode()).hexdigest()[:16]
            else:
                # 获取失败时使用固定ID，避免不稳定的备用方案
                return "default_user"

        except:
            return "default_user"
    
    def _get_public_ip(self):
        """获取公网IP地址"""
        # IP获取API列表，优先使用带地区信息的
        ip_apis = [
            "https://myip.ipip.net/",  # 带地区信息，优先使用
            "http://v4.66666.host:66/ip",
            "https://4.ipw.cn",
            "https://v4.66666.host:66/ip",
            "https://ip.3322.net"
        ]

        for api_url in ip_apis:
            try:
                response = requests.get(api_url, timeout=3)
                if response.status_code == 200:
                    ip_text = response.text.strip()

                    # 针对ipip.net的特殊解析（带地区信息）
                    if "myip.ipip.net" in api_url:
                        # 返回完整的地区信息
                        return ip_text if ip_text else "unknown"
                    else:
                        # 其他API只返回IP，提取纯IP地址
                        import re
                        ip_match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', ip_text)
                        if ip_match:
                            return ip_match.group()
                        return ip_text if ip_text else "unknown"
            except:
                continue

        return "unknown"
    
    def _download_user_file(self):
        """下载用户统计文件"""
        try:
            response = requests.get(
                f"{self.webdav_url}/{self.user_file}",
                auth=(self.username, self.password),
                timeout=5
            )
            
            if response.status_code == 200:
                # 返回文本内容，按行分割
                return response.text.strip().split('\n') if response.text.strip() else []
            else:
                # 文件不存在，返回空列表
                return []
        except:
            return []
    
    def _upload_user_file(self, lines):
        """上传用户统计文件"""
        try:
            # 将行列表转换为文本内容
            text_content = '\n'.join(lines)
            
            response = requests.put(
                f"{self.webdav_url}/{self.user_file}",
                data=text_content.encode('utf-8'),
                auth=(self.username, self.password),
                headers={'Content-Type': 'text/plain; charset=utf-8'},
                timeout=10
            )
            
            # 静默处理结果，不输出任何信息
            return response.status_code in (200, 201, 204)
        except:
            return False
    
    def record_startup(self):
        """记录启动信息（异步执行）"""
        # 使用独立线程执行，避免影响主程序启动速度
        threading.Thread(target=self._record_startup_async, daemon=True).start()
    
    def _record_startup_async(self):
        """异步记录启动信息"""
        try:
            # 1. 获取公网IP
            public_ip = self._get_public_ip()
            
            # 2. 下载现有用户数据（文本行列表）
            lines = self._download_user_file()
            
            # 3. 创建新的启动记录行
            # 格式：时间|版本|IP
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_line = f"{timestamp}|{Config.CURRENT_VERSION}|{public_ip}"
            
            # 将新记录插入到最前面（倒序存储）
            lines.insert(0, new_line)
            
            # 4. 限制记录数量，只保留最近100行（从前面开始计算）
            if len(lines) > 100:
                lines = lines[:100]
            
            # 5. 上传更新后的数据
            self._upload_user_file(lines)
            
        except:
            # 静默处理所有异常，不影响主程序
            pass
    
    def get_user_id(self):
        """获取用户ID（供调试使用）"""
        return self.user_id


# 全局实例
_stats_collector = None


def initialize_stats():
    """初始化统计收集器"""
    global _stats_collector
    try:
        if _stats_collector is None:
            _stats_collector = StatsCollector()
    except:
        pass


def record_startup():
    """记录程序启动（主程序调用接口）"""
    try:
        global _stats_collector
        if _stats_collector is None:
            initialize_stats()
        
        if _stats_collector is not None:
            _stats_collector.record_startup()
    except:
        # 静默处理所有异常
        pass


def get_user_id():
    """获取用户ID（调试接口）"""
    try:
        global _stats_collector
        if _stats_collector is None:
            initialize_stats()
        
        if _stats_collector is not None:
            return _stats_collector.get_user_id()
    except:
        pass
    return "unknown"