"""
Lazy boot helpers to speed up initial app startup.

We install lightweight stub modules for heavy submodules so that importing
modules.ui_core does not pull in requests/bs4/lxml immediately.

Stubs lazily import and swap in the real implementations on first use,
or shortly after the main window is shown.
"""

from __future__ import annotations

import os
import sys
import threading
import importlib
import importlib.util
from types import ModuleType
from typing import Optional, Callable

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import QTimer, QObject, QMetaObject, Qt, pyqtSlot


class _CollectingSignal:
    def __init__(self, collector: list):
        self._collector = collector

    def connect(self, handler):
        # Store the handler to attach to the real signal after upgrade
        if callable(handler):
            self._collector.append(handler)

    def emit(self, *args, **kwargs):
        # No-op; only the real signal should emit
        pass


class _LazyTabBase(QWidget):
    """Lightweight placeholder tab that upgrades to the real tab.

    Subclasses must set _module and _class_name.
    """

    _module: str = ""
    _class_name: str = ""

    def __init__(self):
        super().__init__()
        self._real: Optional[QWidget] = None
        self._pending_actions: set[str] = set()
        # Ensure the placeholder expands to fill the tab page
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("正在加载...")
        layout.addWidget(self._label)

        # Kick off background import to avoid blocking UI
        threading.Thread(target=self._import_and_prepare, daemon=True).start()

    # Public API methods can delegate after upgrade
    def refresh_prices(self):
        pass

    def refresh_websites(self):
        pass

    def show_refreshing_status(self):
        pass

    def detect_game_path(self):
        pass

    # Optional API called early by MainWindow
    def add_hidden_websites(self):
        real = self._real
        if real is not None and hasattr(real, 'add_hidden_websites'):
            try:
                real.add_hidden_websites()
            except Exception:
                pass
        else:
            # Record the intent and replay after upgrade
            self._pending_actions.add('add_hidden_websites')

    def _import_and_prepare(self):
        try:
            # Load the real module directly from file, bypassing stub
            mod = _load_real_module(self._module)
            cls = getattr(mod, self._class_name)
        except Exception:
            cls = None
        if cls is None:
            return

        # Marshal creation to the GUI thread using invokeMethod
        self._pending_cls = cls  # type: ignore[attr-defined]
        QMetaObject.invokeMethod(self, "_create_and_swap_on_gui", Qt.QueuedConnection)

    @pyqtSlot()
    def _create_and_swap_on_gui(self):
        try:
            cls = getattr(self, "_pending_cls", None)
            if cls is None:
                return
            real = cls()
            # Ensure the real widget expands properly inside the tab page
            try:
                real.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            except Exception:
                pass
            self._real = real
            # Replace placeholder content with the real widget
            lay = self.layout()
            while lay.count():
                item = lay.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            lay.addWidget(real)
            try:
                self.updateGeometry()
            except Exception:
                pass
            # Replay pending actions
            if 'add_hidden_websites' in self._pending_actions and hasattr(real, 'add_hidden_websites'):
                try:
                    real.add_hidden_websites()
                except Exception:
                    pass
            self._pending_actions.clear()
            # Cleanup
            try:
                delattr(self, "_pending_cls")
            except Exception:
                pass
        except Exception:
            pass

    # Delegation helpers
    def __getattr__(self, item):
        real = object.__getattribute__(self, "_real")
        if real is not None:
            return getattr(real, item)
        raise AttributeError(item)


def _make_stub_module(name: str, attrs: dict) -> ModuleType:
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _load_real_module(name: str) -> Optional[ModuleType]:
    """Load the real module from file, bypassing the stub in sys.modules.

    Only supports submodules under the 'modules' package in this app.
    """
    try:
        parts = name.split('.')
        if len(parts) != 2 or parts[0] != 'modules':
            return None
        mod_file = parts[1] + '.py'
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, mod_file)
        if not os.path.exists(file_path):
            return None
        unique_name = f"_real__{name}"
        spec = importlib.util.spec_from_file_location(unique_name, file_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        # Make relative imports like 'from .config import Config' work
        try:
            module.__package__ = 'modules'
            if getattr(spec, 'parent', None) is not None:
                spec.parent = 'modules'
        except Exception:
            pass
        spec.loader.exec_module(module)
        sys.modules[unique_name] = module
        return module
    except Exception:
        return None


def install_stubs():
    """Install stub modules under the 'modules.' package for heavy imports.

    Stubs: price_monitor, web_monitor, apatch, filter, update_checker,
           auto_flask, notice_manager
    """

    # Tabs
    class PriceMonitorTab(_LazyTabBase):
        _module = 'modules.price_monitor'
        _class_name = 'PriceMonitorTab'

    class WebMonitorTab(_LazyTabBase):
        _module = 'modules.web_monitor'
        _class_name = 'WebMonitorTab'

    class APatchTab(_LazyTabBase):
        _module = 'modules.apatch'
        _class_name = 'APatchTab'

    class FilterTab(_LazyTabBase):
        _module = 'modules.filter'
        _class_name = 'FilterTab'

    class AutoFlaskTab(_LazyTabBase):
        _module = 'modules.auto_flask'
        _class_name = 'AutoFlaskTab'

    # Non-UI helpers
    class UpdateChecker(QObject):
        def __init__(self, parent=None, current_version: str = ""):
            super().__init__(parent)
            self._parent = parent
            self._version = current_version
            self._real: Optional[QObject] = None

        def _ensure_real(self):
            if self._real is None:
                try:
                    mod = _load_real_module('modules.update_checker')
                    cls = getattr(mod, 'UpdateChecker') if mod else None
                    if cls is not None:
                        self._real = cls(self._parent, self._version)
                        # Attach back to parent for consistency
                        try:
                            if hasattr(self._parent, 'update_checker'):
                                self._parent.update_checker = self._real
                        except Exception:
                            pass
                except Exception:
                    self._real = None
            return self._real

        def check_for_updates(self):
            real = self._ensure_real()
            if real is not None:
                try:
                    real.check_for_updates()
                except Exception:
                    pass

        def check_updates_manually(self):
            real = self._ensure_real()
            if real is not None:
                try:
                    real.check_updates_manually()
                except Exception:
                    pass

    class NoticeManager(QObject):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._parent = parent
            self._real: Optional[QObject] = None
            self._pending_notice_handlers: list[Callable] = []
            self.notice_updated = _CollectingSignal(self._pending_notice_handlers)
            self.notice_error = _CollectingSignal([])

        def _ensure_real(self):
            if self._real is None:
                try:
                    mod = _load_real_module('modules.notice_manager')
                    cls = getattr(mod, 'NoticeManager') if mod else None
                    if cls is not None:
                        real = cls(self._parent)
                        self._real = real
                        # Reconnect stored handlers
                        try:
                            if hasattr(real, 'notice_updated'):
                                for h in self._pending_notice_handlers:
                                    try:
                                        real.notice_updated.connect(h)
                                    except Exception:
                                        pass
                                self._pending_notice_handlers.clear()
                            if hasattr(self._parent, 'notice_manager'):
                                self._parent.notice_manager = real
                        except Exception:
                            pass
                except Exception:
                    self._real = None
            return self._real

        def start(self):
            # Ensure creation and start happen on the GUI thread
            QMetaObject.invokeMethod(self, "_start_on_gui", Qt.QueuedConnection)

        @pyqtSlot()
        @pyqtSlot()
        def _start_on_gui(self):
            self._ensure_real()
            try:
                real = self._real
                if real is None:
                    return

                # 使 refresh_timer 的调用在后台线程执行，避免阻塞 GUI
                try:
                    try:
                        real.refresh_timer.timeout.disconnect()
                    except Exception:
                        pass

                    def _bg_fetch():
                        try:
                            real.fetch_notices()
                        except Exception:
                            pass

                    def _trigger_fetch():
                        try:
                            threading.Thread(target=_bg_fetch, daemon=True).start()
                        except Exception:
                            pass

                    real.refresh_timer.timeout.connect(_trigger_fetch)

                    # 启动轮播和刷新定时器（轮播在无数据时也会安全 no-op）
                    try:
                        real.rotation_timer.start(real.rotation_interval)
                    except Exception:
                        pass
                    try:
                        real.refresh_timer.start(real.refresh_interval)
                    except Exception:
                        pass

                    # 执行一次初始抓取（后台）
                    _trigger_fetch()
                except Exception:
                    pass
            except Exception:
                pass

        def show_status(self, text: str):
            real = self._ensure_real()
            try:
                if real is not None and hasattr(real, 'show_status'):
                    real.show_status(text)
                    return
            except Exception:
                pass
            # Fallback: update parent's notice label if available
            try:
                if hasattr(self._parent, 'update_notice_label'):
                    self._parent.update_notice_label(text, "#FFA500")
            except Exception:
                pass

        def stop(self):
            # Ensure stop happens on GUI thread even if real not yet created
            QMetaObject.invokeMethod(self, "_stop_on_gui", Qt.QueuedConnection)

        @pyqtSlot()
        def _stop_on_gui(self):
            try:
                if self._real is not None and hasattr(self._real, 'stop'):
                    self._real.stop()
            except Exception:
                pass

        # Back-compat helper (not used by ui_core, but available)
        def connect_notice_updated(self, handler: Callable):
            self._pending_notice_handlers.append(handler)

    # Install stub modules
    sys.modules['modules.price_monitor'] = _make_stub_module(
        'modules.price_monitor', {'PriceMonitorTab': PriceMonitorTab})
    sys.modules['modules.web_monitor'] = _make_stub_module(
        'modules.web_monitor', {'WebMonitorTab': WebMonitorTab})
    sys.modules['modules.apatch'] = _make_stub_module(
        'modules.apatch', {'APatchTab': APatchTab})
    sys.modules['modules.filter'] = _make_stub_module(
        'modules.filter', {'FilterTab': FilterTab})
    sys.modules['modules.auto_flask'] = _make_stub_module(
        'modules.auto_flask', {'AutoFlaskTab': AutoFlaskTab})
    sys.modules['modules.update_checker'] = _make_stub_module(
        'modules.update_checker', {'UpdateChecker': UpdateChecker})
    sys.modules['modules.notice_manager'] = _make_stub_module(
        'modules.notice_manager', {'NoticeManager': NoticeManager})
