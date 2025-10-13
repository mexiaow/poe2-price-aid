"""
公告管理模块
负责获取和显示公告信息
"""

import os
import sys
import json
import time
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, QThread
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
        self._fetching = False
        self._fetch_thread = None

    def _ensure_rotation_started(self):
        """在公告可用时启动轮播计时器（若未启动）。"""
        try:
            if self.notices and not self.rotation_timer.isActive():
                self.rotation_timer.start(self.rotation_interval)
        except Exception:
            pass
    
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
        """获取公告数据（仅纯文本/Markdown），在后台线程执行网络请求，避免阻塞UI。"""
        if self._fetching:
            return
        self._fetching = True

        class NoticeFetchThread(QThread):
            fetched = pyqtSignal(str)
            failed = pyqtSignal(str)

            def __init__(self, url):
                super().__init__()
                self.url = url

            def run(self):
                try:
                    try:
                        import requests  # 确保在工作线程中导入，避免主线程阻塞
                    except ImportError:
                        self.failed.emit("缺少requests库")
                        return
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    resp = requests.get(self.url, headers=headers, timeout=5)
                    if resp.status_code == 200 and resp.text.strip():
                        self.fetched.emit(resp.text)
                    else:
                        self.failed.emit(f"HTTP {resp.status_code}")
                except Exception as e:
                    self.failed.emit(str(e))

        print(f"正在从 {self.notice_url} 获取公告数据(纯文本/Markdown, 异步)...")
        self._fetch_thread = NoticeFetchThread(self.notice_url)
        self._fetch_thread.fetched.connect(self._on_fetch_success)
        self._fetch_thread.failed.connect(self._on_fetch_failed)
        self._fetch_thread.finished.connect(self._on_fetch_finished)
        self._fetch_thread.start()

    def _on_fetch_success(self, text):
        try:
            print(f"成功获取公告数据: {len(text)} 字节")
            print(f"获取内容预览: {text[:100].replace('\n', '\\n')}")
            self._parse_notices(text)
            if not self.notices:
                print("解析远程公告失败，尝试加载本地文件...")
                self._load_local_notices()
        except Exception as e:
            print(f"处理公告获取结果失败: {e}")
            self._load_local_notices()

    def _on_fetch_failed(self, msg):
        print(f"获取公告失败({msg})，尝试加载本地文件...")
        self._load_local_notices()

    def _on_fetch_finished(self):
        self._fetching = False
        try:
            if self._fetch_thread:
                self._fetch_thread.deleteLater()
        except Exception:
            pass

    def _get_local_file_path(self):
        """获取本地公告文件路径（打包/源码两种模式）"""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, self.local_file)
    
    def _load_local_notices(self):
        """从本地文件加载公告（纯文本/Markdown）"""
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
                    print("本地文件加载成功，按纯文本/Markdown解析...")
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
        """解析公告内容（纯文本/Markdown）"""
        try:
            if not content or not content.strip():
                print("警告：获取的内容为空")
                self.notices = []
                return
            print(f"按纯文本/Markdown解析公告，长度: {len(content)} 字节")
            self.notices = self._parse_plain_or_markdown_notices(content)
        except Exception as e:
            print(f"解析公告内容失败: {e}")
            self.notices = []

        if self.notices:
            print(f"解析公告成功: {len(self.notices)} 条")
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
                first_idx = next((i for i, ln in enumerate(lines) if ln.strip()), None)
                title_line = lines[first_idx].strip() if first_idx is not None else ""
                if not title_line:
                    # 没有标题的块跳过
                    continue
                # 首行以注释开头则整块忽略
                if re.match(r"^(//|#)", title_line):
                    continue

                title, color = extract_color_from_title(title_line)

                # 构造 HTML：标题 + 正文（自动链接 + 换行）
                # 详情正文不重复标题，从标题下一行开始
                body_lines = lines[first_idx + 1:] if first_idx is not None else []
                escaped_lines = []
                for ln in body_lines:
                    # 跳过正文中的注释行
                    if ln.strip().startswith('#') or ln.strip().startswith('//'):
                        continue
                    ln_esc = escape_html(ln)
                    ln_esc = url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', ln_esc)
                    escaped_lines.append(ln_esc)
                body_html = "<br>".join(escaped_lines) if escaped_lines else ""
                html = f"<h3 style=\"margin:0 0 8px 0;\">{escape_html(title)}</h3>"
                if body_html:
                    html += f"<div style=\"line-height:1.6;\">{body_html}</div>"

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
        
        # 确保轮播定时器已启动
        self._ensure_rotation_started()
    
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
