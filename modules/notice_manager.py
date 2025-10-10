"""
公告管理模块
负责获取和显示公告信息
"""

import os
import sys
import json
import time
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextBrowser
from PyQt5.QtGui import QColor

from modules.config import Config

try:
    import requests
except ImportError:
    pass


class NoticeDialog(QDialog):
    """公告详情对话框"""
    
    def __init__(self, title, content, parent=None):
        """初始化公告详情对话框
        
        Args:
            title: 公告标题
            content: 公告内容
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 添加内容浏览器
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)  # 允许打开外部链接
        
        # 添加全局CSS样式，修改链接颜色
        styled_content = f"""
        <style type="text/css">
            a {{
                color: #00FFFF;  /* 亮青色，在灰色背景上非常显眼 */
                font-weight: bold;
                text-decoration: underline;
            }}
            a:hover {{
                color: #FFA500;  /* 悬停时变为橙色 */
            }}
            body {{
                color: #FFFFFF;  /* 文本颜色为白色 */
                font-family: "Microsoft YaHei", sans-serif;  /* 使用微软雅黑字体 */
                font-size: 14px;
            }}
            b, strong {{
                color: #FFFFFF;  /* 确保粗体文本也是白色 */
            }}
        </style>
        {content}
        """
        self.content_browser.setHtml(styled_content)
        
        # 添加关闭按钮
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        
        # 设置布局
        layout.addWidget(self.content_browser)
        layout.addWidget(self.close_button)


class NoticeManager(QObject):
    """公告管理器类"""
    
    # 信号定义
    notice_updated = pyqtSignal(str, str)  # 公告更新信号 (文本, 颜色)
    notice_error = pyqtSignal(str)  # 公告获取错误信号
    
    def __init__(self, parent=None):
        """初始化公告管理器
        
        Args:
            parent: 父窗口对象
        """
        super().__init__(parent)
        
        # 保存父窗口引用
        self.parent = parent
        
        # 从配置获取公告相关设置
        self.notice_url = Config.NOTICE_CONFIG["url"]
        self.local_file = Config.NOTICE_CONFIG["local_file"]
        self.rotation_interval = Config.NOTICE_CONFIG["rotation_interval"]
        self.default_notice = Config.NOTICE_CONFIG["default_notice"]
        self.max_notices = Config.NOTICE_CONFIG["max_notices"]
        self.refresh_interval = Config.NOTICE_CONFIG.get("refresh_interval", 30 * 60 * 1000)  # 使用配置中的刷新间隔，默认30分钟
        
        # 公告数据
        self.notices = []
        self.current_index = 0
        self.original_notice = self.default_notice  # 保存原始公告文本，用于临时状态显示后恢复
        
        # 轮播计时器
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_notice)
        
        # 公告刷新计时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.fetch_notices)
        
        # 状态标志
        self.rotation_paused = False
        self.showing_status = False
    
    def start(self):
        """启动公告管理器"""
        # 获取初始公告数据
        self.fetch_notices()
        
        # 启动轮播计时器
        if self.notices:
            self.rotation_timer.start(self.rotation_interval)
        
        # 启动公告刷新计时器
        self.refresh_timer.start(self.refresh_interval)
    
    def stop(self):
        """停止公告管理器"""
        self.rotation_timer.stop()
        self.refresh_timer.stop()
    
    def fetch_notices(self):
        """获取公告数据(JSON格式)"""
        try:
            # 从服务器获取
            print(f"正在从 {self.notice_url} 获取公告数据...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.notice_url, headers=headers, timeout=5)
            
            if response.status_code == 200 and response.text.strip():
                print(f"成功获取公告数据: {len(response.text)} 字节")
                # 输出获取到的前100个字符，帮助调试
                print(f"获取内容预览: {response.text[:100].replace('\n', '\\n')}")
                
                # 验证是否是JSON格式
                if response.text.strip().startswith('{') or response.text.strip().startswith('['):
                    print("内容疑似JSON格式，尝试解析...")
                else:
                    print("警告：内容可能不是JSON格式，解析可能会失败")
                
                self._parse_notices(response.text)
                
                # 如果解析后仍然没有公告，尝试加载本地文件
                if not self.notices:
                    print("解析远程公告失败，尝试加载本地文件...")
                    self._load_local_notices()
            else:
                # 如果服务器获取失败，尝试加载本地文件
                error_msg = f"获取公告失败，服务器返回: {response.status_code}，尝试加载本地文件..."
                print(error_msg)
                self._load_local_notices()
        
        except Exception as e:
            # 出错时，尝试加载本地文件
            error_msg = f"获取公告失败: {str(e)}，尝试加载本地文件..."
            print(error_msg)
            self._load_local_notices()
    
    def _load_local_notices(self):
        """从本地文件加载公告(JSON格式)"""
        try:
            # 确定本地文件路径
            if getattr(sys, 'frozen', False):
                # 如果是打包后的程序
                base_path = sys._MEIPASS
            else:
                # 如果是源代码运行
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            file_path = os.path.join(base_path, self.local_file)
            print(f"正在加载本地公告文件: {file_path}")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print("本地文件加载成功，尝试解析JSON格式...")
                    self._parse_notices(content)
                    
                # 如果本地文件解析后仍然没有公告，使用默认公告
                if not self.notices:
                    print("解析本地公告文件失败，使用默认公告")
                    self._use_default_notice()
            else:
                # 如果本地文件不存在，使用默认公告
                print(f"本地公告文件不存在: {file_path}，使用默认公告")
                self._use_default_notice()
        
        except Exception as e:
            print(f"加载本地公告失败: {e}")
            # 使用默认公告
            self._use_default_notice()
    
    def _use_default_notice(self):
        """使用默认公告"""
        print("使用默认公告...")
        self.notices = [{"text": self.default_notice, "color": "#FFA500", "html": self.default_notice}]
        self.show_current_notice()
    
    def _parse_notices(self, content):
        """解析公告内容
        
        Args:
            content: 公告内容文本(JSON格式)
        """
        try:
            # 检查内容是否有效
            if not content or not content.strip():
                print("警告：获取的内容为空")
                self.notices = []  # 清空公告列表，让调用者处理
                return
            
            print(f"尝试解析JSON格式公告数据，内容长度: {len(content)} 字节")
            
            # 解析JSON格式
            try:
                notices_data = json.loads(content)
                if isinstance(notices_data, list):
                    # 标准格式：[{"text": "...", "color": "...", "html": "..."}, ...]
                    self.notices = notices_data[:self.max_notices]  # 限制公告数量
                    print(f"成功解析JSON公告数据: {len(self.notices)} 条公告")
                else:
                    # 如果不是列表格式，创建单个公告项
                    print("JSON数据不是列表格式，处理为单条公告")
                    self.notices = [{"text": notices_data.get("text", self.default_notice), 
                                  "color": notices_data.get("color", "#FFA500"),
                                  "html": notices_data.get("html", "")}]
            except json.JSONDecodeError as e:
                error_line = int(str(e).split("line", 1)[1].split()[0]) if "line" in str(e) else "未知"
                error_pos = int(str(e).split("column", 1)[1].split()[0]) if "column" in str(e) else "未知"
                print(f"JSON解析错误: {e}，在行 {error_line} 列 {error_pos}")
                
                # 显示出错附近的内容
                lines = content.split("\n")
                if 0 <= error_line - 1 < len(lines):
                    error_context = lines[error_line - 1]
                    if isinstance(error_pos, int) and error_pos < len(error_context):
                        print(f"错误附近内容: ...{error_context[max(0, error_pos-20):error_pos]}[HERE]{error_context[error_pos:error_pos+20]}...")
                # JSON 失败时，尝试按“纯文本/Markdown”解析，降低编辑复杂度
                print("回退：尝试按纯文本/Markdown 风格解析公告...")
                self.notices = self._parse_plain_or_markdown_notices(content)
                if self.notices:
                    print(f"纯文本/Markdown 公告解析成功: {len(self.notices)} 条")
                else:
                    # 保持一致的异常路径，让外层按本地/默认回退
                    raise
                
        except Exception as e:
            error_msg = f"解析公告内容失败: {str(e)}"
            print(error_msg)
            import traceback
            print(traceback.format_exc())  # 打印完整的异常堆栈
            # 解析失败时清空公告列表，让调用方法处理
            self.notices = []
        
        # 只有当有公告时才显示，否则让调用者处理
        if self.notices:
            self.show_current_notice()

    def _parse_plain_or_markdown_notices(self, content):
        """将非 JSON 内容解析为公告列表（支持纯文本/简易 Markdown）。

        约定与示例：
        - 多条公告以单独一行的分隔符“---”分隔；无分隔符则视为单条。
        - 每条公告第一行作为标题/简述，用于顶部滚动条展示。
        - 可在标题末尾用“[#RRGGBB]”指定颜色，例如：标题文本 [#E91E63]
        - 正文任意多行，支持自动换行与链接自动识别（http/https）。

        Args:
            content: 原始文本
        Returns:
            list[dict]: [{"text": str, "color": str, "html": str}, ...]
        """
        try:
            import re

            # 标准化换行并按分隔符切块
            text = content.replace("\r\n", "\n").replace("\r", "\n")
            raw_blocks = []
            tmp = []
            for line in text.split("\n"):
                if line.strip() == '---':
                    # 遇到分隔符，结束当前块
                    raw_blocks.append("\n".join(tmp).strip())
                    tmp = []
                else:
                    tmp.append(line)
            if tmp:
                raw_blocks.append("\n".join(tmp).strip())

            # 若全部为空则返回空
            blocks = [b for b in raw_blocks if b]
            if not blocks:
                return []

            def extract_color_from_title(title):
                # 支持在标题末尾使用 [#RRGGBB] 指定颜色
                m = re.search(r"\[(#[0-9a-fA-F]{6})\]\s*$", title)
                if m:
                    color = m.group(1)
                    title = re.sub(r"\s*\[(#[0-9a-fA-F]{6})\]\s*$", "", title).strip()
                    return title, color
                return title.strip(), "#FFA500"

            def escape_html(s):
                return (s.replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;"))

            # 使用单引号包裹原始字符串，避免字符类中的双引号与字符串定界符冲突
            url_pattern = re.compile(r'(https?://[^\s<>"]+)', re.IGNORECASE)

            notices = []
            for block in blocks[: self.max_notices]:
                lines = [ln for ln in block.split("\n")]
                # 找到第一条非空行作为标题
                title_line = next((ln for ln in lines if ln.strip()), "").strip()
                if not title_line:
                    # 没有标题的块跳过
                    continue

                title, color = extract_color_from_title(title_line)

                # 构造 HTML：标题 + 正文（自动链接 + 换行）
                escaped_lines = []
                for ln in lines:
                    ln_esc = escape_html(ln)
                    ln_esc = url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', ln_esc)
                    escaped_lines.append(ln_esc)
                body_html = "<br>".join(escaped_lines)
                html = f"<h3 style=\"margin:0 0 8px 0;\">{escape_html(title)}</h3>" \
                       f"<div style=\"line-height:1.6;\">{body_html}</div>"

                notices.append({
                    "text": title,
                    "color": color,
                    "html": html
                })

            return notices
        except Exception as e:
            print(f"纯文本/Markdown 公告解析失败: {e}")
            return []
    
    def rotate_notice(self):
        """轮播下一条公告"""
        # 如果正在显示状态信息，不进行轮播
        if self.showing_status:
            return
        
        # 如果轮播暂停，不更新
        if self.rotation_paused:
            return
        
        # 如果没有公告数据，不更新
        if not self.notices:
            return
        
        # 切换到下一条公告
        self.current_index = (self.current_index + 1) % len(self.notices)
        
        # 更新显示
        self.show_current_notice()
    
    def show_current_notice(self):
        """显示当前公告"""
        if not self.notices:
            return
        
        # 获取当前公告
        notice = self.notices[self.current_index]
        
        # 发送更新信号
        self.notice_updated.emit(notice["text"], notice["color"])
        
        # 更新原始公告
        self.original_notice = notice["text"]
    
    def pause_rotation(self):
        """暂停轮播"""
        self.rotation_paused = True
    
    def resume_rotation(self):
        """恢复轮播"""
        self.rotation_paused = False
    
    def show_status(self, text, duration_ms=2000):
        """显示临时状态信息
        
        Args:
            text: 状态文本
            duration_ms: 显示持续时间（毫秒）
        """
        # 标记正在显示状态
        self.showing_status = True
        
        # 发送更新信号
        self.notice_updated.emit(text, "#FFA500")
        
        # 设置定时器，在指定时间后恢复原始公告
        QTimer.singleShot(duration_ms, self.restore_notice)
    
    def restore_notice(self):
        """恢复原始公告"""
        self.showing_status = False
        self.show_current_notice()
    
    def show_notice_detail(self):
        """显示当前公告详情"""
        if not self.notices:
            return
        
        # 获取当前公告
        notice = self.notices[self.current_index]
        
        # 创建并显示详情对话框
        dialog = NoticeDialog("公告详情", notice.get("html", notice["text"]), self.parent)
        dialog.exec_()
    
    def handle_click(self):
        """处理公告点击事件"""
        if not self.showing_status:
            self.show_notice_detail()
    
    def refresh_notices(self):
        """手动刷新公告
        在用户请求时刷新公告数据
        """
        # 暂停轮播
        old_paused_state = self.rotation_paused
        self.rotation_paused = True
        
        # 显示刷新状态
        self.notice_updated.emit("正在刷新公告...", "#FFA500")
        
        # 创建单独的QTimer，确保状态显示有足够时间
        QTimer.singleShot(500, lambda: self._do_refresh(old_paused_state))
    
    def _do_refresh(self, restore_pause_state):
        """执行实际的刷新操作
        
        Args:
            restore_pause_state: 刷新完成后是否恢复原来的暂停状态
        """
        # 获取公告数据
        self.fetch_notices()
        
        # 恢复原来的暂停状态
        self.rotation_paused = restore_pause_state 
