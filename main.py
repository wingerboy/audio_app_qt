import sys
import os
import time
import json
import logging
import shutil
import platform
import traceback
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QComboBox, QFileDialog, QMessageBox, QProgressBar, QRadioButton,
    QButtonGroup, QSpinBox, QGroupBox, QStyle, QAction, QStatusBar, QMenu,
    QToolButton, QDoubleSpinBox, QSizePolicy, QFrame, QSlider
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QUrl, QSize, QSettings, QPoint, QRect, QTimer,
    QLocale, QTranslator, QLibraryInfo, QCoreApplication
)
from PyQt5.QtGui import QIcon, QColor, QFont, QDesktopServices, QPalette, QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

from ui.main_window import Ui_MainWindow
from ui.model_selector import ModelSelector
from ui.system_info_dialog import SystemInfoDialog
from ui.login_dialog import LoginDialog
from ui.device_list_dialog import DeviceListDialog
from core.audio_analyzer import AudioAnalyzer
from core.audio_processor import AudioProcessor
from core.model_manager import ModelManager
from core.system_info import SystemInfo
from core.session_manager import SessionManager
from ui.range_slider import RangeSlider
from ui.theme_manager import ThemeManager

class TranscriptionThread(QThread):
    """Thread for running transcription in background"""
    progress_signal = pyqtSignal(str, int)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, file_path, model_name, language, chunk_length, analyzer=None, min_sentence_length=1, max_sentence_length=30):
        super().__init__()
        self.file_path = file_path
        self.model_name = model_name
        self.language = language
        self.chunk_length = chunk_length
        self.analyzer = analyzer
        self.min_sentence_length = min_sentence_length
        self.max_sentence_length = max_sentence_length
        
    def run(self):
        try:
            if self.analyzer is None:
                self.progress_signal.emit("初始化转录模型...", 0)
                analyzer = AudioAnalyzer(model_name=self.model_name)
            else:
                analyzer = self.analyzer
                self.progress_signal.emit("使用已加载的模型...", 10)
            
            self.progress_signal.emit("开始转录音频...", 20)
            
            result = analyzer.transcribe(
                self.file_path, 
                chunk_length=self.chunk_length, 
                language=self.language,
                min_sentence_length=self.min_sentence_length,
                max_sentence_length=self.max_sentence_length
            )
            
            self.progress_signal.emit("转录完成", 100)
            self.result_signal.emit(result)
            
        except Exception as e:
            self.error_signal.emit(f"转录失败: {str(e)}")

class ExportThread(QThread):
    """Thread for exporting audio segments"""
    progress_signal = pyqtSignal(str, int)
    result_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    
    def __init__(self, audio_path, segments, output_dir, file_prefix, output_format, bitrate):
        super().__init__()
        self.audio_path = audio_path
        self.segments = segments
        self.output_dir = output_dir
        self.file_prefix = file_prefix
        self.output_format = output_format
        self.bitrate = bitrate
        
    def run(self):
        try:
            self.progress_signal.emit("准备导出音频片段...", 0)
            processor = AudioProcessor()
            
            self.progress_signal.emit("开始分割音频...", 20)
            output_files = processor.split_audio(
                self.audio_path,
                self.segments,
                output_dir=self.output_dir,
                file_prefix=self.file_prefix,
                output_format=self.output_format,
                bitrate=self.bitrate,
                progress_callback=lambda msg, progress: self.progress_signal.emit(msg, 20 + int(progress * 0.8))
            )
            
            self.progress_signal.emit("导出完成", 100)
            self.result_signal.emit(output_files)
            
        except Exception as e:
            self.error_signal.emit(f"导出失败: {str(e)}")

class AudioExtractThread(QThread):
    """Thread for extracting audio from video"""
    progress_signal = pyqtSignal(str, int)
    result_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        
    def run(self):
        try:
            self.progress_signal.emit("准备处理音频...", 0)
            processor = AudioProcessor()
            
            result = processor.extract_audio(
                self.file_path,
                progress_callback=lambda msg, progress: self.progress_signal.emit(msg, progress)
            )
            
            self.progress_signal.emit("处理完成", 100)
            self.result_signal.emit(result)
            
        except Exception as e:
            self.error_signal.emit(f"处理失败: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        
        # 设置UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # 应用深色主题
        self.apply_dark_stylesheet()
        
        # 设置窗口最小尺寸 - 缩小到3/4
        self.setMinimumSize(750, 450)  # 原来是1000, 600
        
        # 初始化系统信息
        self.system_info = SystemInfo()
        
        # 初始化会话管理器
        self.init_session_manager()
        
        # 初始化模型管理器
        self.model_manager = ModelManager()
        
        # 创建处理模型下载进度队列的定时器
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.process_model_progress)
        self.progress_timer.start(100)  # 每100毫秒处理一次队列
        
        # 创建模型选择器
        self.model_selector = ModelSelector(self.model_manager)
        
        # 添加模型选择器到UI
        # 检查并设置TranscribeLayout中的modelSelector
        transcribe_layout = self.ui.transcribe_group.layout()
        if transcribe_layout:
            # 查找lblModelName后面的位置
            for i in range(transcribe_layout.count()):
                if transcribe_layout.itemAt(i).widget() == self.ui.lblModelName:
                    # 创建一个容器来持有模型选择器
                    container = QWidget()
                    container_layout = QHBoxLayout(container)
                    container_layout.setContentsMargins(0, 0, 0, 0)
                    container_layout.addWidget(self.model_selector)
                    
                    # 在标签后插入容器
                    transcribe_layout.insertWidget(i + 1, container)
                    self.ui.modelSelector = self.model_selector
                    break
        
        # 连接模型选择器信号
        self.model_selector.modelSelected.connect(self.on_model_selected)
        self.model_selector.requestDownload.connect(self.download_model)
        
        # 添加句子长度范围控制组件 - 直接在转录布局中添加
        self.add_sentence_range_controls()
        
        # 初始化音频处理类
        self.audio_processor = AudioProcessor()
        
        # 初始化音频分析类
        self.audio_analyzer = AudioAnalyzer()
        
        # 初始化多语言支持
        self.translator = QTranslator()
        
        # 初始化状态变量
        self.audio_file = None  # 当前音频文件
        self.segments = []  # 转录段落
        self.selected_segments = []  # 已选择的段落
        self.filtered_segments = None  # 过滤后的段落
        
        # 初始化统计数据
        self.total_segments = 0
        self.selected_count = 0
        self.filtered_count = 0
        
        # 设置表格
        self.setup_table()
        
        # 设置播放器
        self.setup_audio_player()
        
        # 连接信号和槽
        self.connect_signals()
        
        # 初始化UI状态
        self.update_ui_state()
        
        # 更新系统状态
        self.update_system_status()
        
        # 尝试加载之前的会话
        self.try_load_session()
        
        # 显示登录对话框
        QTimer.singleShot(100, self.show_login_dialog)
        
    def apply_dark_stylesheet(self):
        """应用深色模式样式表"""
        # 使用 ThemeManager 应用统一的深色主题
        ThemeManager.apply_dark_theme()
        
    # 新方法：处理模型进度队列
    def process_model_progress(self):
        """定时处理模型下载进度队列"""
        self.model_manager.process_progress_updates()
        
    def init_session_manager(self):
        """初始化会话管理器"""
        self.session_manager = SessionManager()
        self.session_manager.sessionChanged.connect(self.on_session_changed)
        
        # 添加登录状态显示
        self.login_status_layout = QHBoxLayout()
        self.login_status_label = QLabel("未登录")
        self.login_status_label.setStyleSheet("color: #e74c3c;")
        self.login_button = QPushButton("登录")
        self.login_button.setFixedWidth(60)
        self.login_button.clicked.connect(self.show_login_dialog)
        
        # 添加设备列表按钮
        self.btn_device_list = QPushButton("设备列表")
        self.btn_device_list.setFixedWidth(80)
        self.btn_device_list.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: white;
                border-radius: 3px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:pressed {
                background-color: #1c2e40;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btn_device_list.clicked.connect(self.show_device_list)
        self.btn_device_list.setEnabled(False)
        
        self.login_status_layout.addWidget(self.login_status_label)
        self.login_status_layout.addWidget(self.login_button)
        self.login_status_layout.addWidget(self.btn_device_list)
        
        # 将登录状态添加到状态栏区域
        status_layout = self.ui.lblStatus.parentWidget().layout()
        if status_layout:
            status_layout.insertLayout(0, self.login_status_layout)
        
    def try_load_session(self):
        """尝试从文件加载会话信息"""
        success = self.session_manager.load_session()
        if success:
            print("成功加载会话")
            
            # 更新会话状态
            self.on_session_changed(True, f"已登录: {self.session_manager.card_id}（卡密过期时间：{self.session_manager.expiry_date}）")
            
            # 更新UI状态
            self.update_ui_state()
            
            # 启用设备列表按钮
            self.btn_device_list.setEnabled(True)
            
            return True
        return False
        
    def on_session_changed(self, is_logged_in, status_message):
        """当会话状态改变时更新UI"""
        if is_logged_in:
            self.login_status_label.setText(status_message)
            self.login_status_label.setStyleSheet("color: #27ae60;")
            self.login_button.setText("注销")
            self.login_button.clicked.disconnect()
            self.login_button.clicked.connect(self.logout)
            self.btn_device_list.setEnabled(True)
            
            # 保存会话信息
            self.session_manager.save_session()
        else:
            self.login_status_label.setText("未登录")
            self.login_status_label.setStyleSheet("color: #e74c3c;")
            self.login_button.setText("登录")
            self.btn_device_list.setEnabled(False)
            try:
                self.login_button.clicked.disconnect()
            except:
                pass
            self.login_button.clicked.connect(self.show_login_dialog)
        
        # 更新UI启用状态
        self.update_ui_state()
        
    def show_login_dialog(self):
        """显示登录对话框"""
        # 如果已经登录，则不显示登录对话框
        if self.session_manager.is_logged_in:
            return
            
        dialog = LoginDialog(self)
        
        # 设置对话框为模态
        dialog.setModal(True)
        
        # 连接登录按钮点击事件
        dialog.btnLogin.clicked.connect(lambda: self.handle_login(dialog))
        
        # 连接登录成功信号
        dialog.loginSuccess.connect(self.on_login_success)
        
        # 显示对话框并确保它在所有窗口之上
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        dialog.exec_()
    
    def handle_login(self, dialog):
        """处理登录请求"""
        card_id = dialog.editCardId.text().strip()
        card_key = dialog.editCardKey.text().strip()
        
        success, message = self.session_manager.login(card_id, card_key)
        dialog.show_login_result(success, message)
        
        if success:
            # 登录成功，发出信号
            dialog.loginSuccess.emit(
                self.session_manager.session_token,
                self.session_manager.user_type,
                self.session_manager.expiry_date
            )
            dialog.accept()
    
    def on_login_success(self, session_token, user_type, expiry_date):
        """登录成功后的处理"""
        # 更新UI状态
        self.update_ui_state()
        
        # 启用设备列表按钮
        self.btn_device_list.setEnabled(True)
        
        # 保存会话信息到本地文件
        self.session_manager.save_session()
        
        # 更新登录状态显示
        self.on_session_changed(True, f"已登录: {self.session_manager.card_id}")
    
    def logout(self):
        """用户注销"""
        self.session_manager.logout()
        # 更新UI状态将通过sessionChanged信号触发
    
    def show_device_list(self):
        """显示设备列表对话框"""
        if not self.session_manager.is_logged_in:
            QMessageBox.warning(self, "未登录", "请先登录再查看设备列表")
            return
            
        # 使用DeviceListDialog代替自定义对话框实现
        dialog = DeviceListDialog(self.session_manager, self)
        dialog.exec_()
    
    # 新方法：设置表格
    def setup_table(self):
        """设置分段结果表格"""
        # 设置表格列名
        self.ui.tableSegments.setColumnCount(5)
        self.ui.tableSegments.setHorizontalHeaderLabels(["选择", "时间", "时长", "内容", "播放"])
        
        # 设置表格样式
        self.ui.tableSegments.setStyleSheet("""
            QTableWidget {
                background-color: #222;
                color: #ddd;
                gridline-color: #444;
                border: 1px solid #555;
                alternate-background-color: #2a2a2a;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #345;
            }
            QHeaderView::section {
                background-color: #333;
                color: #ddd;
                padding: 5px;
                border: 1px solid #555;
                font-weight: bold;
            }
            QTableWidget QCheckBox {
                color: #ddd;
            }
        """)
        
        # 设置列宽
        header = self.ui.tableSegments.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 选择列
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # 时间列
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # 时长列
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # 内容列
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # 操作列
        
        # 设置固定列宽
        table_width = self.ui.tableSegments.width()
        self.ui.tableSegments.setColumnWidth(0, 50)  # 选择列
        self.ui.tableSegments.setColumnWidth(1, 50)  # 时间列
        self.ui.tableSegments.setColumnWidth(2, 80)   # 时长列
        self.ui.tableSegments.setColumnWidth(4, 50)   # 操作列固定为50，与选择列相同
        
        # 启用自动换行和自动调整行高
        self.ui.tableSegments.setWordWrap(True)
        self.ui.tableSegments.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # 启用交替行颜色
        self.ui.tableSegments.setAlternatingRowColors(True)
        
        # 添加全选按钮和提示标签
        if not hasattr(self, 'selection_control_widget'):
            # 创建一个水平布局的Widget来容纳全选按钮和提示
            self.selection_control_widget = QWidget()
            selection_layout = QHBoxLayout(self.selection_control_widget)
            selection_layout.setContentsMargins(5, 5, 5, 5)
            
            # 添加全选按钮
            self.btn_select_all = QPushButton("全选")
            self.btn_select_all.setFixedWidth(80)
            self.btn_select_all.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1f6aa5;
                }
            """)
            self.btn_select_all.clicked.connect(self.toggle_select_all)
            selection_layout.addWidget(self.btn_select_all)
            
            # 添加帮助提示文本
            help_label = QLabel("点击可一键选择/取消选择所有行")
            help_label.setStyleSheet("color: #999; padding-left: 10px;")
            selection_layout.addWidget(help_label)
            
            # 添加弹性空间
            selection_layout.addStretch(1)
            
            # 将控件添加到界面布局
            segments_layout = self.ui.segments_group.layout()
            segments_layout.insertWidget(1, self.selection_control_widget)
    
    # 新方法：设置播放器
    def setup_audio_player(self):
        """设置音频播放器"""
        # 初始化播放器状态，实际上这里可以为空，
        # 因为我们使用系统默认播放器播放
        pass
        
    # 新方法：连接信号和槽
    def connect_signals(self):
        """连接信号和槽"""
        # 文件选择
        self.ui.btnSelectFile.clicked.connect(self.select_file)
        
        # 转录
        self.ui.btnTranscribe.clicked.connect(self.start_transcription)
        
        # 过滤和选择
        if hasattr(self.ui, 'editFilterKeyword'):
            self.ui.editFilterKeyword.textChanged.connect(self.apply_filter)
        
        if hasattr(self.ui, 'comboFilterType'):
            self.ui.comboFilterType.currentIndexChanged.connect(self.apply_filter)
        
        if hasattr(self.ui, 'spinMinDuration'):
            self.ui.spinMinDuration.valueChanged.connect(self.on_duration_filter_changed)
            
        if hasattr(self.ui, 'spinMaxDuration'):
            self.ui.spinMaxDuration.valueChanged.connect(self.on_duration_filter_changed)
        
        if hasattr(self.ui, 'btnApplyFilter'):
            self.ui.btnApplyFilter.clicked.connect(self.apply_all_filters)
        
        # 标签状态切换
        if hasattr(self.ui, 'radioAll'):
            self.ui.radioAll.clicked.connect(lambda: self.show_segments_by_status("all"))
            
        if hasattr(self.ui, 'radioSelected'):
            self.ui.radioSelected.clicked.connect(lambda: self.show_segments_by_status("selected"))
            
        if hasattr(self.ui, 'radioUnselected'):
            self.ui.radioUnselected.clicked.connect(lambda: self.show_segments_by_status("unselected"))
        
        # 导出
        if hasattr(self.ui, 'btnExport'):
            self.ui.btnExport.clicked.connect(self.export_selected_segments)
            
        if hasattr(self.ui, 'btnBatchExport'):
            self.ui.btnBatchExport.clicked.connect(self.batch_export_segments)
        
        # 系统信息
        if hasattr(self.ui, 'btnSystemInfo'):
            self.ui.btnSystemInfo.clicked.connect(self.show_system_info)
    
    def setup_ui_state(self):
        """初始化UI状态"""
        # 步骤1：选择文件
        self.ui.step1Label.setStyleSheet("background-color: #6360f5; color: white; border-radius: 10px;")
        
        # 后续步骤初始为灰色
        for step in [self.ui.step2Label, self.ui.step3Label, self.ui.step4Label]:
            step.setStyleSheet("background-color: #444; color: #999; border-radius: 10px;")
        
        # 禁用转录相关功能
        transcription_done = False
        self.ui.btnTranscribe.setEnabled(False)
        
        # 禁用导出功能
        self.ui.btnExport.setEnabled(False)
        self.ui.btnBatchExport.setEnabled(False)
        
        # 设置表格表头
        header = self.ui.tableSegments.horizontalHeader()
        header.setSectionsClickable(True)
        
        # 修改表格样式，确保行高适应内容
        self.ui.tableSegments.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # 确保表格字体和行高适应更小的窗口
        self.ui.tableSegments.setStyleSheet("""
            QTableWidget {
                background-color: #222;
                color: #ddd;
                gridline-color: #444;
                border: 1px solid #555;
                alternate-background-color: #2a2a2a;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #345;
            }
            QHeaderView::section {
                background-color: #333;
                color: #ddd;
                padding: 4px;
                border: 1px solid #555;
                font-weight: bold;
                font-size: 10pt;
            }
            QTableWidget QCheckBox {
                color: #ddd;
            }
        """)
        
        # 启用交替行颜色
        self.ui.tableSegments.setAlternatingRowColors(True)
        
        # 设置固定行高
        self.ui.tableSegments.verticalHeader().setDefaultSectionSize(40)
        self.ui.tableSegments.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
            
        # 初始化列宽
        table_width = self.ui.tableSegments.width()
        self.ui.tableSegments.setColumnWidth(0, int(table_width * 0.15))
        self.ui.tableSegments.setColumnWidth(1, int(table_width * 0.15))
        self.ui.tableSegments.setColumnWidth(2, int(table_width * 0.10))
        self.ui.tableSegments.setColumnWidth(4, int(table_width * 0.10))
        self.ui.tableSegments.setColumnWidth(3, int(table_width * 0.50))
        
    def toggle_select_all(self):
        """切换全选/取消全选状态"""
        if not self.segments or self.ui.tableSegments.rowCount() == 0:
            return
            
        # 判断当前是否所有可见行都已选中
        all_selected = True
        visible_segments = []
        
        # 收集当前表格中显示的所有段落
        for i in range(self.ui.tableSegments.rowCount()):
            checkbox_widget = self.ui.tableSegments.cellWidget(i, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    if not checkbox.isChecked():
                        all_selected = False
                    # 获取段落数据
                    segment = None
                    if self.ui.tableSegments.item(i, 3):
                        segment = self.ui.tableSegments.item(i, 3).data(Qt.UserRole)
                    if segment:
                        visible_segments.append(segment)
        
        # 根据当前状态决定是全选还是取消全选
        new_state = not all_selected
        
        # 批量更新选择状态
        if new_state:
            # 全选：添加所有可见段落
            for segment in visible_segments:
                if segment not in self.selected_segments:
                    self.selected_segments.append(segment)
            self.selected_count = len(self.selected_segments)
            self.btn_select_all.setText("取消全选")
        else:
            # 取消全选：移除所有可见段落
            for segment in visible_segments:
                if segment in self.selected_segments:
                    self.selected_segments.remove(segment)
            self.selected_count = len(self.selected_segments)
            self.btn_select_all.setText("全选")
            
        # 更新计数显示
        self.update_count_display()
        
        # 更新UI显示
        current_tab = "all"
        if self.ui.radioSelected.isChecked():
            current_tab = "selected"
        elif self.ui.radioUnselected.isChecked():
            current_tab = "unselected"
        
        # 暂时断开事件连接，避免触发大量单独事件
        self.update_ui_state()
        
        # 重新显示分段，使复选框状态与实际选择状态同步
        self.show_segments_by_status(current_tab)
        
    def update_step_indicator(self, step):
        """更新步骤指示器状态"""
        # 步骤列表
        step_labels = [
            self.ui.step1Label,  # 上传文件
            self.ui.step2Label,  # 分析内容/转录
            self.ui.step3Label,  # 筛选片段
            self.ui.step4Label   # 下载文件
        ]
        
        active_style = "background-color: #6360f5; color: white; border-radius: 10px;"
        inactive_style = "background-color: #555; color: white; border-radius: 10px;"
        completed_style = "background-color: #27ae60; color: white; border-radius: 10px;"
        
        for i, label in enumerate(step_labels):
            if i + 1 < step:
                # 已完成的步骤
                label.setStyleSheet(completed_style)
            elif i + 1 == step:
                # 当前步骤
                label.setStyleSheet(active_style)
            else:
                # 未开始的步骤
                label.setStyleSheet(inactive_style)
    
    def update_ui_state(self):
        """根据当前状态更新UI元素的启用/禁用状态"""
        # 如果未登录，禁用所有功能
        if not self.session_manager.is_logged_in:
            # 不能直接访问centralwidget，需要禁用主要功能组件
            self.ui.transcribe_group.setEnabled(False)
            self.ui.segments_group.setEnabled(False)
            self.ui.export_group.setEnabled(False)
            self.ui.tableSegments.setEnabled(False)
            self.ui.btnSelectFile.setEnabled(False)
            return
        else:
            self.ui.transcribe_group.setEnabled(True)
            self.ui.btnSelectFile.setEnabled(True)
        
        # 文件选择状态
        file_selected = bool(self.audio_file)
        self.ui.btnTranscribe.setEnabled(file_selected)
        
        # 转录设置状态
        self.ui.transcribe_group.setEnabled(file_selected)
        
        # 转录完成状态
        transcription_done = self.segments is not None
        self.ui.segments_group.setEnabled(transcription_done)
        self.ui.export_group.setEnabled(transcription_done and len(self.selected_segments) > 0)
        
        # 更新过滤器状态
        self.ui.filter_group.setEnabled(transcription_done)
        
        # 更新分段表格状态
        self.ui.tableSegments.setEnabled(transcription_done)
        
        # 更新导出状态
        if transcription_done:
            has_selected = len(self.selected_segments) > 0
            self.ui.btnExport.setEnabled(has_selected)
            
            # 仅允许高级用户进行批量导出
            allowed, _ = self.session_manager.validate_action("batch_process")
            self.ui.btnBatchExport.setEnabled(has_selected and allowed)
        else:
            self.ui.btnExport.setEnabled(False)
            self.ui.btnBatchExport.setEnabled(False)
    
    def select_file(self):
        """选择音频或视频文件"""
        # 验证用户是否有权限执行此操作
        allowed, reason = self.session_manager.validate_action("select_file")
        if not allowed:
            QMessageBox.warning(self, "操作受限", f"无法继续: {reason}")
            return
            
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("媒体文件 (*.mp3 *.wav *.m4a *.mp4 *.mkv *.avi *.flac *.ogg *.aac *.wma *.mov)")
        
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                self.ui.lblFilePath.setText(file_path)
                
                # 如果是视频文件，先提取音频
                if file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    self.extract_audio(file_path)
                else:
                    # 对于音频文件，直接设置路径
                    self.audio_file = file_path
                    self.update_step_indicator(2)
                    self.update_ui_state()
                    print(f"已选择音频文件: {file_path}")
    
    def extract_audio(self, file_path):
        # 禁用UI
        self.setEnabled(False)
        
        # 创建并启动提取线程
        self.extract_thread = AudioExtractThread(file_path)
        self.extract_thread.progress_signal.connect(self.update_progress)
        self.extract_thread.result_signal.connect(self.on_audio_extracted)
        self.extract_thread.error_signal.connect(self.show_error)
        self.extract_thread.start()
    
    def on_audio_extracted(self, audio_path):
        self.audio_file = audio_path
        self.update_ui_state()
        self.setEnabled(True)
    
    def start_transcription(self):
        """开始转录音频"""
        # 验证用户是否有权限执行此操作
        allowed, reason = self.session_manager.validate_action("transcribe")
        if not allowed:
            QMessageBox.warning(self, "操作受限", f"无法继续: {reason}")
            return
        
        # 获取转录参数
        file_path = self.audio_file
        model_name = self.model_selector.get_current_model()
        language = self.ui.comboLanguage.currentText()
        chunk_length = self.ui.spinChunkLength.value()
        
        # 获取句子长度范围
        min_sentence_length = self.spinMinLength.value()
        max_sentence_length = self.spinMaxLength.value()
        
        # 确保最小值不大于最大值
        if min_sentence_length > max_sentence_length:
            min_sentence_length = max_sentence_length
            self.spinMinLength.setValue(min_sentence_length)
        
        if not file_path:
            QMessageBox.warning(self, "错误", "请先选择音频文件")
            return
        
        # 检查是否需要初始化或更新analyzer
        if self.audio_analyzer is None or self.model_selector.get_current_model() != model_name:
            try:
                # 显示初始化进度
                self.update_progress("初始化转录模型...", 0)
                
                # 更新当前使用的模型名称
                self.model_selector.set_current_model(model_name)
                
                # 创建新的分析器
                self.audio_analyzer = AudioAnalyzer(model_name=model_name)
                
                # 确保加载模型
                self.audio_analyzer._ensure_model_loaded(chunk_length_s=chunk_length)
                
                self.update_progress("模型加载完成", 10)
                # 继续执行转录流程，而不是返回
            except Exception as e:
                self.show_error(f"模型初始化失败: {str(e)}")
                return  # 只有在初始化失败时才返回
        
        # 禁用UI
        self.ui.btnTranscribe.setEnabled(False)
        self.ui.progressBar.setValue(0)
        self.ui.progressBar.show()
        
        # 清除旧数据
        self.segments = None
        self.selected_segments = []
        self.ui.tableSegments.clearContents()
        self.ui.tableSegments.setRowCount(0)
        
        # 创建并启动转录线程
        self.transcription_thread = TranscriptionThread(
            file_path, 
            model_name, 
            language, 
            chunk_length, 
            self.audio_analyzer,
            min_sentence_length,
            max_sentence_length
        )
        self.transcription_thread.progress_signal.connect(self.update_progress)
        self.transcription_thread.result_signal.connect(self.on_transcription_completed)
        self.transcription_thread.error_signal.connect(self.show_error)
        self.transcription_thread.start()
    
    def on_transcription_completed(self, result):
        """转录完成时的回调"""
        self.segments = self.extract_segments(result)
        self.selected_segments = []
        
        # 初始化计数
        self.total_segments = len(self.segments) if self.segments else 0
        self.selected_count = 0
        
        # 显示转录结果
        self.update_duration_range()
        self.display_segments(self.segments)
        
        # 更新步骤指示器到"分割音频"步骤
        self.update_step_indicator(3)
        
        # 启用UI
        self.setEnabled(True)
        self.update_ui_state()
    
    def extract_segments(self, transcription):
        """从转录结果中提取分段"""
        if not transcription or "segments" not in transcription:
            return []
            
        # 从转录结果中提取分段
        segments = []
        for segment in transcription["segments"]:
            segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "duration": segment["end"] - segment["start"]
            })
        return segments
    
    def apply_filter(self):
        """应用关键词过滤器"""
        # 应用所有过滤条件
        pass
    
    def on_duration_filter_changed(self):
        """应用时长过滤器"""
        self.update_duration_filter_label()
        
    def update_duration_range(self):
        """根据片段时长更新双滑动条的范围"""
        if not self.segments:
            return
            
        # 找出所有片段的最短和最长时长
        min_duration = float('inf')
        max_duration = 0
        
        for segment in self.segments:
            duration = segment.get("end", 0) - segment.get("start", 0)
            min_duration = min(min_duration, duration)
            max_duration = max(max_duration, duration)
            
        # 确保有有效值
        min_duration = int(min_duration)
        max_duration = int(max_duration) + 1  # 加1确保最长的片段也能被包含
        
        # 设置时长输入范围
        self.ui.spinMinDuration.setMinimum(min_duration)
        self.ui.spinMinDuration.setMaximum(max_duration)
        self.ui.spinMinDuration.setValue(min_duration)
        
        self.ui.spinMaxDuration.setMinimum(min_duration)
        self.ui.spinMaxDuration.setMaximum(max_duration)
        self.ui.spinMaxDuration.setValue(max_duration)
        
        # 更新标签
        self.update_duration_filter_label()
    
    def update_duration_filter_label(self):
        """更新时长过滤器标签"""
        min_val = self.ui.spinMinDuration.value()
        max_val = self.ui.spinMaxDuration.value()
        in_range_count = 0
        
        if self.segments:
            for segment in self.segments:
                duration = segment.get("end", 0) - segment.get("start", 0)
                if min_val <= duration <= max_val:
                    in_range_count += 1
        
        total_count = len(self.segments) if self.segments else 0
        # 更新统计信息
        self.ui.lblDurationCount.setText(f"({in_range_count}/{total_count})")
    
    def display_segments(self, segments, show_mode="all"):
        """显示分段结果到表格中"""
        if not segments:
            return
            
        # 更新统计信息
        self.total_segments = len(self.segments) if self.segments else 0
        self.selected_count = len(self.selected_segments)
        
        # 更新UI中的计数显示
        self.update_count_display()
        
        # 清空并设置表格行数
        self.ui.tableSegments.setRowCount(len(segments))
        
        # 确定当前显示的段落中有多少被选中
        displayed_selected_count = 0
        
        # 设置基础行高
        base_row_height = 30
        self.ui.tableSegments.verticalHeader().setDefaultSectionSize(base_row_height)
        
        # 启用行高调整
        self.ui.tableSegments.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        for i, segment in enumerate(segments):
            # 创建操作列（复选框）
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            # 缩小内边距使复选框更小
            checkbox_layout.setContentsMargins(3, 3, 3, 3)  # 从原来的5,5,5,5缩小
            checkbox_layout.setAlignment(Qt.AlignCenter)
            
            checkbox = QCheckBox()
            # 缩小复选框大小为原来的3/5
            checkbox_size = int(18 * 3/5)  # 原来是18px
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    spacing: 3px;  /* 缩小间距 */
                }}
                QCheckBox::indicator {{
                    width: {checkbox_size}px;
                    height: {checkbox_size}px;
                    border: 1px solid #999;
                    border-radius: 3px;
                }}
                QCheckBox::indicator:unchecked {{
                    background-color: #444;
                }}
                QCheckBox::indicator:checked {{
                    background-color: #3498db;
                    border-color: #2980b9;
                }}
            """)
            
            # 根据显示模式设置复选框状态
            is_checked = False
            if show_mode == "selected":
                is_checked = True
            elif show_mode == "unselected":
                is_checked = False
            else:  # "all" 模式
                is_checked = segment in self.selected_segments
                
            if is_checked:
                displayed_selected_count += 1
                
            checkbox.setChecked(is_checked)
            checkbox.stateChanged.connect(lambda state, row=i, seg=segment: self.on_segment_selected(row, state, seg))
            
            checkbox_layout.addWidget(checkbox)
            
            # 添加到表格
            self.ui.tableSegments.setCellWidget(i, 0, checkbox_widget)
            
            # 添加时间（开始 - 结束）
            start_time = self.format_time(segment.get("start", 0))
            end_time = self.format_time(segment.get("end", 0))
            time_text = f"{start_time} - {end_time}"
            self.ui.tableSegments.setItem(i, 1, self.create_table_item(time_text))
            
            # 添加持续时间
            duration = segment.get("end", 0) - segment.get("start", 0)
            duration_text = f"{duration:.1f}s"
            self.ui.tableSegments.setItem(i, 2, self.create_table_item(duration_text))
            
            # 添加文本内容 - 设置为自动换行
            text = segment.get("text", "").strip()
            content_item = self.create_table_item(text)
            # 强制启用自动换行
            content_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            content_item.setFlags(content_item.flags() | Qt.TextWordWrap)
            # 明确设置文本格式，确保换行生效
            self.ui.tableSegments.setWordWrap(True)
            self.ui.tableSegments.setItem(i, 3, content_item)
            
            # 添加操作按钮（播放）
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            # 缩小内边距
            button_layout.setContentsMargins(2, 2, 2, 2)  # 从原来的3,3,3,3缩小
            button_layout.setAlignment(Qt.AlignCenter)
            
            play_button = QPushButton()
            play_button.setToolTip("播放此片段")
            # 按钮尺寸缩小为原来的2/3
            button_size = int((base_row_height - 10) * 2/3)  # 原来是base_row_height - 10
            play_button.setFixedSize(button_size, button_size)
            play_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3498db;
                    border-radius: {button_size // 2}px;
                    color: white;
                    font-weight: bold;
                    font-size: {button_size // 2}px;
                }}
                QPushButton:hover {{
                    background-color: #2980b9;
                }}
                QPushButton:pressed {{
                    background-color: #1f6aa5;
                }}
            """)
            # 使用三角形符号表示播放
            play_button.setText("▶")
            play_button.clicked.connect(lambda _, row=i: self.play_segment(row))
            
            button_layout.addWidget(play_button)
            
            self.ui.tableSegments.setCellWidget(i, 4, button_widget)
            
            # 保存segment对象到表格项中
            self.ui.tableSegments.item(i, 3).setData(Qt.UserRole, segment)
        
        # 设置列宽
        table_width = self.ui.tableSegments.width()
        # 选择列 - 紧凑
        self.ui.tableSegments.setColumnWidth(0, int(table_width * 0.05))
        # 时间范围 - 固定宽度，足够显示时间
        self.ui.tableSegments.setColumnWidth(1, int(table_width * 0.15))
        # 持续时间 - 较窄，只需显示几个数字
        self.ui.tableSegments.setColumnWidth(2, int(table_width * 0.08))
        # 播放按钮 - 设置与选择列相同宽度
        self.ui.tableSegments.setColumnWidth(4, int(table_width * 0.05))
        # 内容列 - 占据剩余空间
        # 增加内容列宽度，确保它有足够空间显示换行文本
        self.ui.tableSegments.setColumnWidth(3, int(table_width * 0.67))
        
        # 强制表格更新布局以正确处理换行
        self.ui.tableSegments.resizeRowsToContents()
        
        # 更新全选按钮文本
        if hasattr(self, 'btn_select_all'):
            if len(segments) > 0 and displayed_selected_count == len(segments):
                self.btn_select_all.setText("取消全选")
            else:
                self.btn_select_all.setText("全选")
        
        # 根据当前模式设置单选按钮状态
        if show_mode == "selected":
            self.ui.radioSelected.setChecked(True)
        elif show_mode == "unselected":
            self.ui.radioUnselected.setChecked(True)
        else:
            self.ui.radioAll.setChecked(True)
        
        # 更新UI状态
        self.update_ui_state()
    
    def create_table_item(self, text):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设为不可编辑
        return item
    
    def format_time(self, seconds):
        """将秒数格式化为 分:秒 格式"""
        minutes = int(seconds / 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"
    
    def on_segment_selected(self, row, state, segment=None):
        """当用户选择/取消选择片段时调用"""
        if not segment and (not self.segments or row >= len(self.segments)):
            return
            
        if not segment:
            segment = self.segments[row]
        
        current_tab = "all"
        if self.ui.radioSelected.isChecked():
            current_tab = "selected"
        elif self.ui.radioUnselected.isChecked():
            current_tab = "unselected"
        
        if state == Qt.Checked:
            if segment not in self.selected_segments:
                self.selected_segments.append(segment)
                self.selected_count += 1
        else:
            if segment in self.selected_segments:
                self.selected_segments.remove(segment)
                self.selected_count -= 1
        
        # 更新计数显示
        self.update_count_display()
        
        # 如果当前正在"已选择"或"未选择"标签，需要刷新显示
        if current_tab in ["selected", "unselected"]:
            self.show_segments_by_status(current_tab)
        
        # 更新UI状态
        self.update_ui_state()
    
    def play_segment(self, row):
        """播放指定行的音频片段"""
        if not self.segments or row >= len(self.segments):
            self.show_error("无法播放：段落不存在")
            return
            
        # 检查音频文件是否存在
        file_path = self.audio_file
        if not file_path or not os.path.exists(file_path):
            self.show_error(f"音频文件不存在: {file_path}")
            return
            
        segment = self.segments[row]
        start_time = segment.get("start", 0)
        end_time = segment.get("end", 0)
        
        # 使用临时文件保存片段
        try:
            processor = AudioProcessor()
            
            self.update_progress("正在准备播放...", 0)
            # 获取临时目录，确保存在
            temp_dir = os.path.join(os.path.dirname(file_path), "temp_audio")
            os.makedirs(temp_dir, exist_ok=True)
            
            # 使用绝对路径
            output_file = os.path.join(temp_dir, f"temp_play_{start_time:.2f}_{end_time:.2f}.mp3")
            
            # 使用ffmpeg直接裁剪音频文件（简化播放逻辑）
            import subprocess
            cmd = [
                "ffmpeg", "-y", 
                "-i", file_path,
                "-ss", str(start_time),
                "-to", str(end_time),
                "-c:a", "mp3", 
                output_file
            ]
            
            self.update_progress(f"正在剪切音频片段: {start_time:.2f}s - {end_time:.2f}s", 20)
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(output_file):
                self.update_progress("准备播放...", 90)
                # 使用系统默认播放器播放
                import platform
                
                if platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", output_file])
                    self.update_progress("已发送播放指令 (macOS)", 100)
                elif platform.system() == "Windows":
                    os.startfile(output_file)
                    self.update_progress("已发送播放指令 (Windows)", 100)
                else:  # Linux
                    subprocess.Popen(["xdg-open", output_file])
                    self.update_progress("已发送播放指令 (Linux)", 100)
            else:
                self.show_error(f"剪切音频失败，临时文件未生成: {output_file}")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.show_error(f"播放失败: {str(e)}\n详细错误: {error_details}")
    
    def apply_all_filters(self):
        """应用所有过滤条件（关键词和时长）"""
        if not self.segments:
            return
            
        # 获取关键词过滤条件
        filter_type = self.ui.comboFilterType.currentText()
        filter_text = self.ui.editFilterKeyword.text().strip()
        
        # 获取时长过滤条件
        min_duration = self.ui.spinMinDuration.value()
        max_duration = self.ui.spinMaxDuration.value()
        
        # 如果没有任何过滤条件（没有关键词且时长范围包含所有片段）
        # 则清除过滤状态，显示所有片段
        has_keyword_filter = filter_type != "过滤模式" and filter_text.strip()
        
        # 检查时长是否覆盖了所有片段
        min_possible = float('inf')
        max_possible = 0
        for segment in self.segments:
            duration = segment.get("end", 0) - segment.get("start", 0)
            min_possible = min(min_possible, duration)
            max_possible = max(max_possible, duration)
        
        has_duration_filter = (min_duration > min_possible) or (max_duration < max_possible)
        
        if not has_keyword_filter and not has_duration_filter:
            self.filtered_segments = None
            current_tab = "all"
            if self.ui.radioSelected.isChecked():
                current_tab = "selected"
            elif self.ui.radioUnselected.isChecked():
                current_tab = "unselected"
            
            # 重新显示当前选择的视图，但不应用过滤器
            self.show_segments_by_status(current_tab)
            return
        
        # 应用过滤
        filtered_segments = []
        
        for segment in self.segments:
            # 检查时长
            duration = segment.get("end", 0) - segment.get("start", 0)
            if duration < min_duration or duration > max_duration:
                continue
                
            # 检查关键词（如果有）
            if filter_type != "过滤模式" and filter_text:
                text = segment.get("text", "").lower()
                # 同时支持中文逗号和英文逗号作为分隔符
                keywords = [k.strip() for k in filter_text.replace("，", ",").split(",") if k.strip()]
                
                if not keywords:
                    # 没有有效关键词，保留此段
                    filtered_segments.append(segment)
                    continue
                    
                keyword_matches = any(keyword.lower() in text for keyword in keywords)
                
                if (filter_type == "包含关键词" and not keyword_matches) or \
                   (filter_type == "不包含关键词" and keyword_matches):
                    continue
            
            # 通过所有过滤条件，添加到结果中
            filtered_segments.append(segment)
        
        # 更新段落并显示
        self.filtered_segments = filtered_segments
        
        # 计算筛选结果数量
        self.filtered_count = len(filtered_segments)
        
        current_tab = "all"
        if self.ui.radioSelected.isChecked():
            current_tab = "selected"
        elif self.ui.radioUnselected.isChecked():
            current_tab = "unselected"
        
        # 重新显示当前选择的视图
        self.show_segments_by_status(current_tab)
    
    def show_segments_by_status(self, status):
        """根据状态显示片段"""
        if not self.segments:
            return
            
        # 更新单选按钮状态 - 确保UI正确反映当前选择
        if status == "all":
            self.ui.radioAll.setChecked(True)
        elif status == "selected":
            self.ui.radioSelected.setChecked(True)
        elif status == "unselected":
            self.ui.radioUnselected.setChecked(True)
            
        if status == "all":
            # 显示全部 - 如果有过滤结果，则显示过滤后的结果
            if self.filtered_segments is not None:
                self.display_segments(self.filtered_segments, "all")
            else:
                self.display_segments(self.segments, "all")
        elif status == "selected":
            # 只显示已选择的，并且要符合过滤条件
            if self.selected_segments:
                if self.filtered_segments is not None:
                    # 筛选出既在selected中又在filtered中的片段
                    filtered_selected = [s for s in self.selected_segments if s in self.filtered_segments]
                    self.display_segments(filtered_selected, "selected")
                else:
                    self.display_segments(self.selected_segments, "selected")
            else:
                # 如果没有选择任何片段，显示空表格
                self.ui.tableSegments.setRowCount(0)
                # 更新计数显示
                self.update_count_display()
        elif status == "unselected":
            # 显示未选择的，并且要符合过滤条件
            if self.filtered_segments is not None:
                # 筛选出在filtered中但不在selected中的片段
                filtered_unselected = [s for s in self.filtered_segments if s not in self.selected_segments]
                if filtered_unselected:
                    self.display_segments(filtered_unselected, "unselected")
                else:
                    # 没有未选择的片段，显示空表格
                    self.ui.tableSegments.setRowCount(0)
                    self.update_count_display()
            else:
                unselected_segments = [s for s in self.segments if s not in self.selected_segments]
                if unselected_segments:
                    self.display_segments(unselected_segments, "unselected")
                else:
                    # 没有未选择的片段，显示空表格
                    self.ui.tableSegments.setRowCount(0)
                    self.update_count_display()
    
    def export_selected_segments(self):
        """导出选中的音频片段"""
        # 验证用户是否有权限执行此操作
        allowed, reason = self.session_manager.validate_action("export")
        if not allowed:
            QMessageBox.warning(self, "操作受限", f"无法继续: {reason}")
            return
        
        # 检查是否有选中的片段
        if not self.selected_segments:
            QMessageBox.warning(self, "警告", "请先选择要导出的音频片段")
            return
            
        # 获取导出参数
        source_path = self.audio_file
        output_format = self.ui.comboFormat.currentText()
        output_bitrate = self.ui.comboBitrate.currentText()
        
        # 选择输出目录
        output_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not output_dir:
            return
            
        # 获取文件前缀
        file_prefix = os.path.splitext(os.path.basename(source_path))[0] + "_segment"
        
        # 显示进度条
        self.ui.progressBar.setValue(0)
        self.ui.progressBar.show()
        
        # 创建并启动导出线程
        self.export_thread = ExportThread(
            source_path,
            self.selected_segments,
            output_dir,
            file_prefix,
            output_format,
            output_bitrate
        )
        self.export_thread.progress_signal.connect(self.update_progress)
        self.export_thread.result_signal.connect(self.on_export_completed)
        self.export_thread.error_signal.connect(self.show_error)
        self.export_thread.start()
    
    def batch_export_segments(self):
        """批量导出音频片段"""
        # 验证用户是否有权限执行此操作
        allowed, reason = self.session_manager.validate_action("batch_process")
        if not allowed:
            QMessageBox.warning(self, "操作受限", f"无法继续: {reason}")
            return
        
        # 检查是否有选中的片段
        if not self.selected_segments:
            QMessageBox.warning(self, "警告", "请先选择要导出的音频片段")
            return
        
        # 获取导出参数
        source_path = self.audio_file
        output_format = self.ui.comboFormat.currentText()
        output_bitrate = self.ui.comboBitrate.currentText()
        
        # 选择输出目录
        output_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not output_dir:
            return
            
        # 获取文件前缀
        file_prefix = os.path.splitext(os.path.basename(source_path))[0] + "_segment"
        
        # 显示进度条
        self.ui.progressBar.setValue(0)
        self.ui.progressBar.show()
        
        # 创建并启动导出线程
        self.export_thread = ExportThread(
            source_path,
            self.selected_segments,
            output_dir,
            file_prefix,
            output_format,
            output_bitrate
        )
        self.export_thread.progress_signal.connect(self.update_progress)
        self.export_thread.result_signal.connect(self.on_export_completed)
        self.export_thread.error_signal.connect(self.show_error)
        self.export_thread.start()
    
    def on_export_completed(self, output_files):
        # 显示成功消息
        QMessageBox.information(
            self,
            "导出成功",
            f"成功导出 {len(output_files)} 个音频片段到选定目录"
        )
        
        # 启用UI
        self.setEnabled(True)
    
    def update_progress(self, message, value):
        self.ui.progressBar.setValue(value)
        self.ui.lblStatus.setText(message)
    
    def show_error(self, message):
        self.setEnabled(True)
        QMessageBox.critical(self, "错误", message)
        self.ui.lblStatus.setText("出错: " + message)
    
    def on_model_selected(self, model_name):
        """当用户选择不同的模型时调用"""
        # 每次选择模型时重新检查模型状态
        self.model_manager.check_all_models()
        
        # 获取最新的模型状态
        status = self.model_manager.get_model_status(model_name)
        print(f"当前选择的模型: {model_name}, 状态: {status['status']}")
        
        if status["status"] == "downloaded":
            self.update_ui_state()  # 更新UI状态，允许开始转录
        else:
            # 如果模型未下载，转录按钮应该禁用
            self.ui.btnTranscribe.setEnabled(False)
    
    def download_model(self, model_name):
        """下载指定的模型"""
        # 验证用户是否有权限执行此操作
        allowed, reason = self.session_manager.validate_action("download_large_model")
        if not allowed and model_name in ["whisper-medium", "whisper-large"]:
            QMessageBox.warning(self, "操作受限", f"无法下载大型模型: {reason}")
            return
            
        # 开始下载模型
        self.model_manager.download_model(model_name, self.on_model_download_progress)
    
    def on_model_download_progress(self, model_name, progress, status_text):
        """模型下载进度更新"""
        # 更新模型选择器中的下载进度
        self.model_selector.update_download_progress(model_name, progress, status_text)
        
        # 打印进度信息以便调试
        print(f"模型{model_name}下载进度: {progress}%, 状态: {status_text}")
        
        # 下载完成后，更新UI状态
        if progress == 100:
            print(f"模型{model_name}下载完成")
            # 确保模型状态更新
            self.model_manager.check_all_models()
            # 更新UI状态
            self.update_ui_state()
            
            # 使用友好的模型显示名称
            display_name = self.model_selector.get_display_name(model_name)
            
            # 使用延迟显示消息框，避免阻塞UI线程
            QTimer.singleShot(500, lambda: QMessageBox.information(self, "下载完成", 
                                                             f"模型 {display_name} 已成功下载完成！"))
    
    def show_system_info(self):
        """显示系统信息对话框"""
        dialog = SystemInfoDialog(self.system_info, self)
        dialog.exec_()
        # 对话框关闭后刷新状态显示
        self.update_system_status()
        
    def update_system_status(self):
        """更新系统状态显示"""
        # 获取关键状态
        cuda_available = self.system_info.info['dependencies']['cuda_available']
        ffmpeg_available = self.system_info.info['ffmpeg']['available']
        
        # 构建状态文本
        status_text = "GPU: "
        if cuda_available:
            gpu_name = self.system_info.info['dependencies']['gpu_name']
            status_text += f"<span style='color:#27ae60;'>✓</span> {gpu_name}"
        else:
            status_text += "<span style='color:#e74c3c;'>✗</span> 使用CPU"
            
        status_text += " | FFmpeg: "
        if ffmpeg_available:
            status_text += "<span style='color:#27ae60;'>✓</span> 已安装"
        else:
            status_text += "<span style='color:#e74c3c;'>✗</span> 未安装"
        
        # 更新状态标签
        self.ui.lblSystemStatus.setText(status_text)
        self.ui.lblSystemStatus.setTextFormat(Qt.RichText)
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 如果未登录，直接关闭
        if not self.session_manager.is_logged_in:
            event.accept()
            return
            
        # 如果已登录，询问用户是否确认关闭
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出应用程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
    
    def update_count_display(self):
        """更新界面上的计数显示"""
        total = self.total_segments
        selected = self.selected_count
        unselected = total - selected
        
        # 更新单选按钮上的计数
        self.ui.radioAll.setText(f"全部")
        self.ui.radioSelected.setText(f"已选择")
        self.ui.radioUnselected.setText(f"未选择")
        
        # 更新标签上的统计数据
        self.ui.lblStatTotal.setText(f"总计: {total}")
        self.ui.lblStatSelected.setText(f"已选择: {selected}")
        self.ui.lblStatUnselected.setText(f"未选择: {unselected}")
    
    def on_sentence_range_changed(self):
        """当句子长度范围发生变化时调用"""
        # 获取新的最小值和最大值
        min_length = self.spinMinLength.value()
        max_length = self.spinMaxLength.value()
        
        # 更新UI状态
        self.update_ui_state()
    
    def add_sentence_range_controls(self):
        """添加句子长度范围控制组件到转录面板"""
        transcribe_layout = self.ui.transcribe_group.layout()
        if not transcribe_layout:
            return
            
        # 创建带标签的控件组
        sentence_range_widget = QWidget()
        sentence_range_layout = QHBoxLayout(sentence_range_widget)
        sentence_range_layout.setContentsMargins(0, 5, 0, 5)  # 上下添加一点间距
        
        # 添加标签
        sentence_range_label = QLabel("句子长度范围:")
        sentence_range_label.setStyleSheet("color: #ddd;")
        sentence_range_layout.addWidget(sentence_range_label)
        
        # 添加最小值控件
        self.spinMinLength = QSpinBox()
        self.spinMinLength.setMinimum(1)
        self.spinMinLength.setMaximum(30)
        self.spinMinLength.setValue(3)  # 默认最小值3秒
        self.spinMinLength.setSuffix(" 秒")
        self.spinMinLength.setFixedWidth(60)
        self.spinMinLength.setStyleSheet("""
            QSpinBox {
                background-color: #444;
                color: #ddd;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        sentence_range_layout.addWidget(self.spinMinLength)
        
        # 添加分隔标签
        range_separator = QLabel("至")
        range_separator.setStyleSheet("color: #ddd;")
        sentence_range_layout.addWidget(range_separator)
        
        # 添加最大值控件
        self.spinMaxLength = QSpinBox()
        self.spinMaxLength.setMinimum(2)
        self.spinMaxLength.setMaximum(60)
        self.spinMaxLength.setValue(10)  # 默认最大值10秒
        self.spinMaxLength.setSuffix(" 秒")
        self.spinMaxLength.setFixedWidth(60)
        self.spinMaxLength.setStyleSheet("""
            QSpinBox {
                background-color: #444;
                color: #ddd;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        sentence_range_layout.addWidget(self.spinMaxLength)
        
        # 添加弹性空间，确保控件紧凑对齐
        sentence_range_layout.addStretch(1)
        
        # 插入到布局中合适的位置 - 查找分段长度控件的位置
        for i in range(transcribe_layout.count()):
            widget = transcribe_layout.itemAt(i).widget()
            if widget and widget == self.ui.spinChunkLength:
                # 在分段长度控件后添加
                transcribe_layout.insertWidget(i + 1, sentence_range_widget)
                break
        else:
            # 如果没找到，就加到布局最后（但在转录按钮前）
            btnTranscribe_index = -1
            for i in range(transcribe_layout.count()):
                widget = transcribe_layout.itemAt(i).widget()
                if widget and widget == self.ui.btnTranscribe:
                    btnTranscribe_index = i
                    break
            
            if btnTranscribe_index != -1:
                transcribe_layout.insertWidget(btnTranscribe_index, sentence_range_widget)
            else:
                # 实在找不到位置，就直接添加到布局最后
                transcribe_layout.addWidget(sentence_range_widget)
        
        # 连接最小值变化信号
        self.spinMinLength.valueChanged.connect(self.on_sentence_range_changed)
        # 连接最大值变化信号
        self.spinMaxLength.valueChanged.connect(self.on_sentence_range_changed)

def main():
    app = QApplication(sys.argv)
    
    # 设置样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = MainWindow()
    
    # 应用深色主题
    window.apply_dark_stylesheet()
    
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
