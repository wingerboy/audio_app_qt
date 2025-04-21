import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QTableWidgetItem, QCheckBox, QWidget, QHBoxLayout, QPushButton, QSlider, QSpinBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

from ui.main_window import Ui_MainWindow
from ui.model_selector import ModelSelector
from ui.system_info_dialog import SystemInfoDialog
from core.audio_analyzer import AudioAnalyzer
from core.audio_processor import AudioProcessor
from core.model_manager import ModelManager
from core.system_info import SystemInfo

class TranscriptionThread(QThread):
    """Thread for running transcription in background"""
    progress_signal = pyqtSignal(str, int)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, file_path, model_name, language, chunk_length):
        super().__init__()
        self.file_path = file_path
        self.model_name = model_name
        self.language = language
        self.chunk_length = chunk_length
        
    def run(self):
        try:
            self.progress_signal.emit("初始化转录模型...", 0)
            analyzer = AudioAnalyzer(model_name=self.model_name)
            self.progress_signal.emit("开始转录音频...", 20)
            
            result = analyzer.transcribe(
                self.file_path, 
                chunk_length=self.chunk_length, 
                language=self.language
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
        
        # 初始化系统信息检查器
        self.system_info = SystemInfo()
        
        # 初始化模型管理器
        self.model_manager = ModelManager()
        
        # 设置UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # 创建并设置模型选择器
        self.model_selector = ModelSelector(self.model_manager)
        
        # 将模型选择器添加到转录设置布局中
        transcribe_layout = self.ui.transcribe_group.layout()
        if transcribe_layout:
            transcribe_layout.insertWidget(1, self.model_selector)
            self.ui.modelSelector = self.model_selector
        else:
            print("警告: 无法找到转录设置布局")
        
        # 连接模型选择器信号
        self.model_selector.modelSelected.connect(self.on_model_selected)
        self.model_selector.requestDownload.connect(self.download_model)
        
        # 更新系统状态摘要
        self.update_system_status()
        
        # 初始状态
        self.audio_path = None
        self.extracted_audio_path = None
        self.transcription = None
        self.segments = None
        self.filtered_segments = None
        self.selected_segments = []
        
        # 统计计数
        self.total_segments = 0
        self.selected_count = 0
        self.filtered_count = 0
        
        # 设置信号和槽
        self.setup_connections()
        
        # 更新UI状态
        self.setup_ui_state()
        self.update_step_indicator(1)
        
    def setup_connections(self):
        # 文件选择
        self.ui.btnSelectFile.clicked.connect(self.select_file)
        
        # 转录
        self.ui.btnTranscribe.clicked.connect(self.start_transcription)
        
        # 过滤
        self.ui.editFilterKeyword.textChanged.connect(self.apply_filter)
        self.ui.comboFilterType.currentIndexChanged.connect(self.apply_filter)
        self.ui.spinMinDuration.valueChanged.connect(self.on_duration_filter_changed)
        self.ui.spinMaxDuration.valueChanged.connect(self.on_duration_filter_changed)
        
        # 标签状态切换
        self.ui.radioAll.clicked.connect(lambda: self.show_segments_by_status("all"))
        self.ui.radioSelected.clicked.connect(lambda: self.show_segments_by_status("selected"))
        self.ui.radioUnselected.clicked.connect(lambda: self.show_segments_by_status("unselected"))
        
        # 导出
        self.ui.btnExport.clicked.connect(self.export_selected_segments)
        self.ui.btnBatchExport.clicked.connect(self.batch_export_segments)
        
        # 系统信息
        self.ui.btnSystemInfo.clicked.connect(self.show_system_info)
        
    def setup_ui_state(self):
        """初始化UI状态"""
        # 步骤1：选择文件
        self.ui.step1Label.setStyleSheet("background-color: #6360f5; color: white; border-radius: 10px;")
        
        # 后续步骤初始为灰色
        for step in [self.ui.step2Label, self.ui.step3Label, self.ui.step4Label]:
            step.setStyleSheet("background-color: #444; color: #999; border-radius: 10px;")
        
        # 隐藏分段设置，直到转录完成
        # self.ui.segment_group.hide()
        
        # 禁用转录相关功能
        transcription_done = False
        self.ui.btnTranscribe.setEnabled(transcription_done)
        
        # 禁用分段相关功能
        segmentation_done = False
        # self.ui.btnApplyFilter.setEnabled(segmentation_done)
        
        # 禁用过滤器
        filter_enabled = segmentation_done
        self.ui.comboFilterType.setEnabled(filter_enabled)
        self.ui.editFilterKeyword.setEnabled(filter_enabled)
        self.ui.spinMinDuration.setEnabled(filter_enabled)
        self.ui.spinMaxDuration.setEnabled(filter_enabled)
        # self.ui.btnApplyFilter.setEnabled(filter_enabled)
        
        # 单选按钮
        self.ui.radioAll.setEnabled(filter_enabled)
        self.ui.radioSelected.setEnabled(filter_enabled)
        self.ui.radioUnselected.setEnabled(filter_enabled)
        
        # 默认选择"全部"
        self.ui.radioAll.setChecked(True)
        
        # 禁用导出功能
        self.ui.btnExport.setEnabled(False)
        self.ui.btnBatchExport.setEnabled(False)
        
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
        # 根据当前状态更新UI元素的启用/禁用状态
        
        # 文件选择状态
        file_selected = self.audio_path is not None
        
        # 转录状态
        transcription_done = self.transcription is not None
        
        # 分段状态（现在直接从转录后获取）
        segments_available = self.segments is not None and len(self.segments) > 0
        
        # 筛选后的分段状态
        filtered_segments_available = self.filtered_segments is not None and len(self.filtered_segments) > 0
        
        # 转录按钮
        self.ui.btnTranscribe.setEnabled(file_selected)
        
        # 导出按钮
        self.ui.btnExport.setEnabled(segments_available and len(self.selected_segments) > 0)
        self.ui.btnBatchExport.setEnabled(segments_available and (
            len(self.selected_segments) > 0 or 
            (filtered_segments_available and len(self.filtered_segments) > 0)
        ))
        
        # 过滤控件
        filter_enabled = segments_available
        self.ui.editFilterKeyword.setEnabled(filter_enabled)
        self.ui.comboFilterType.setEnabled(filter_enabled)
        self.ui.spinMinDuration.setEnabled(filter_enabled)
        self.ui.spinMaxDuration.setEnabled(filter_enabled)
        
        # 单选按钮
        self.ui.radioAll.setEnabled(filter_enabled)
        self.ui.radioSelected.setEnabled(filter_enabled)
        self.ui.radioUnselected.setEnabled(filter_enabled)
        
        # 更新统计信息
        if segments_available and self.segments:
            self.ui.radioAll.setText(f"全部 ({self.total_segments}/{self.total_segments})")
            self.ui.radioSelected.setText(f"已选择 ({self.selected_count}/{self.total_segments})")
            self.ui.radioUnselected.setText(f"未选择 ({self.total_segments - self.selected_count}/{self.total_segments})")
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频或视频文件",
            "",
            "媒体文件 (*.mp3 *.wav *.mp4 *.avi *.mov *.mkv *.flac *.ogg *.m4a *.webm)"
        )
        
        if file_path:
            self.audio_path = file_path
            self.ui.lblFilePath.setText(os.path.basename(file_path))
            self.update_step_indicator(1)
            
            # 如果是视频文件，需要提取音频
            if os.path.splitext(file_path)[1].lower() in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                self.extract_audio(file_path)
            else:
                self.extracted_audio_path = file_path
                self.update_ui_state()
    
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
        self.extracted_audio_path = audio_path
        self.update_ui_state()
        self.setEnabled(True)
    
    def start_transcription(self):
        if not self.extracted_audio_path:
            self.show_error("没有有效的音频文件")
            return
        
        # 获取转录设置
        model_name = self.model_selector.get_current_model()
        language = self.ui.comboLanguage.currentText()
        chunk_length = 10  # 使用默认值10秒
        
        # 检查模型是否已下载
        status = self.model_manager.get_model_status(model_name)
        if status["status"] != "downloaded":
            self.show_error(f"模型 {model_name} 尚未下载，请先下载模型")
            return
        
        # 禁用UI
        self.setEnabled(False)
        
        # 清除之前的结果
        self.transcription = None
        self.segments = None
        self.ui.tableSegments.setRowCount(0)
        
        # 更新状态
        self.ui.lblStatus.setText("正在转录...")
        self.ui.progressBar.setValue(0)
        
        # 更新步骤指示器
        self.update_step_indicator(2)
        
        # 创建并启动转录线程
        self.transcribe_thread = TranscriptionThread(
            self.extracted_audio_path, model_name, language, chunk_length
        )
        self.transcribe_thread.progress_signal.connect(self.update_progress)
        self.transcribe_thread.result_signal.connect(self.on_transcription_completed)
        self.transcribe_thread.error_signal.connect(self.show_error)
        self.transcribe_thread.start()
    
    def on_transcription_completed(self, result):
        """转录完成时的回调"""
        self.transcription = result
        
        # 直接将转录结果设为分段
        self.segments = self.extract_segments(result)
        self.filtered_segments = None
        self.selected_segments = []
        
        # 显示转录结果
        self.update_duration_range()
        self.display_segments(self.segments)
        
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
        
        # 清空并设置表格行数
        self.ui.tableSegments.setRowCount(len(segments))
        
        for i, segment in enumerate(segments):
            # 创建操作列（复选框）
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            
            checkbox = QCheckBox()
            # 根据显示模式设置复选框状态
            if show_mode == "selected":
                checkbox.setChecked(True)
            elif show_mode == "unselected":
                checkbox.setChecked(False)
            else:  # "all" 模式
                checkbox.setChecked(segment in self.selected_segments)
                
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
            
            # 添加文本内容
            text = segment.get("text", "").strip()
            self.ui.tableSegments.setItem(i, 3, self.create_table_item(text))
            
            # 添加操作按钮（播放、删除）
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            button_layout.setContentsMargins(3, 3, 3, 3)
            
            play_button = QPushButton("播放")
            play_button.setFixedWidth(50)
            play_button.clicked.connect(lambda _, row=i: self.play_segment(row))
            
            button_layout.addWidget(play_button)
            
            self.ui.tableSegments.setCellWidget(i, 4, button_widget)
            
            # 保存segment对象到表格项中
            self.ui.tableSegments.item(i, 3).setData(Qt.UserRole, segment)
        
        # 选中"全部"单选按钮
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
        
        # 如果当前正在"已选择"或"未选择"标签，需要刷新显示
        if current_tab in ["selected", "unselected"]:
            self.show_segments_by_status(current_tab)
        
        # 更新UI状态
        self.update_ui_state()
    
    def play_segment(self, row):
        """播放指定行的音频片段"""
        if not self.segments or row >= len(self.segments) or not self.extracted_audio_path:
            return
            
        segment = self.segments[row]
        start_time = segment.get("start", 0)
        end_time = segment.get("end", 0)
        
        # 使用临时文件保存片段
        try:
            processor = AudioProcessor()
            
            self.update_progress("正在准备播放...", 0)
            output_files = processor.split_audio(
                self.extracted_audio_path,
                [segment],
                file_prefix="temp_play",
                progress_callback=lambda msg, progress: self.update_progress(msg, progress)
            )
            
            if output_files and os.path.exists(output_files[0]):
                # 使用系统默认播放器播放
                import subprocess
                import platform
                
                if platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", output_files[0]])
                elif platform.system() == "Windows":
                    os.startfile(output_files[0])
                else:  # Linux
                    subprocess.Popen(["xdg-open", output_files[0]])
                    
                self.update_progress("播放中...", 100)
            
        except Exception as e:
            self.show_error(f"播放失败: {str(e)}")
    
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
                keywords = [k.strip() for k in filter_text.split(",") if k.strip()]
                
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
            
        if status == "all":
            # 显示全部 - 如果有过滤结果，则显示过滤后的结果
            if self.filtered_segments is not None:
                self.display_segments(self.filtered_segments)
            else:
                self.display_segments(self.segments)
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
        elif status == "unselected":
            # 显示未选择的，并且要符合过滤条件
            if self.filtered_segments is not None:
                # 筛选出在filtered中但不在selected中的片段
                filtered_unselected = [s for s in self.filtered_segments if s not in self.selected_segments]
                self.display_segments(filtered_unselected, "unselected")
            else:
                unselected_segments = [s for s in self.segments if s not in self.selected_segments]
                self.display_segments(unselected_segments, "unselected")
    
    def export_selected_segments(self):
        """导出选中的片段"""
        if not self.selected_segments or not self.extracted_audio_path:
            self.show_error("请先选择要导出的片段")
            return
        
        # 更新步骤指示器
        self.update_step_indicator(4)
        
        # 选择输出目录
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            ""
        )
        
        if not output_dir:
            return
            
        # 获取导出设置
        file_prefix = self.ui.editFilePrefix.text() or "segment"
        output_format = self.ui.comboFormat.currentText().lower()
        bitrate = self.ui.comboBitrate.currentText()
        
        # 禁用UI
        self.setEnabled(False)
        
        # 创建并启动导出线程
        self.export_thread = ExportThread(
            self.extracted_audio_path,
            self.selected_segments,
            output_dir,
            file_prefix,
            output_format,
            bitrate
        )
        self.export_thread.progress_signal.connect(self.update_progress)
        self.export_thread.result_signal.connect(self.on_export_completed)
        self.export_thread.error_signal.connect(self.show_error)
        self.export_thread.start()
    
    def batch_export_segments(self):
        """批量导出所有片段"""
        if not self.segments or not self.extracted_audio_path:
            self.show_error("没有可导出的片段")
            return
        
        # 更新步骤指示器
        self.update_step_indicator(4)
        
        # 根据当前显示状态决定导出哪些片段
        segments_to_export = []
        if self.ui.radioAll.isChecked():
            segments_to_export = self.segments
        elif self.ui.radioSelected.isChecked():
            segments_to_export = self.selected_segments
        elif self.ui.radioUnselected.isChecked():
            segments_to_export = [s for s in self.segments if s not in self.selected_segments]
        
        if not segments_to_export:
            self.show_error("当前没有可导出的片段")
            return
        
        # 选择输出目录
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            ""
        )
        
        if not output_dir:
            return
            
        # 获取导出设置
        file_prefix = self.ui.editFilePrefix.text() or "segment"
        output_format = self.ui.comboFormat.currentText().lower()
        bitrate = self.ui.comboBitrate.currentText()
        
        # 禁用UI
        self.setEnabled(False)
        
        # 创建并启动导出线程
        self.export_thread = ExportThread(
            self.extracted_audio_path,
            segments_to_export,
            output_dir,
            file_prefix,
            output_format,
            bitrate
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
        # 开始下载模型
        self.model_manager.download_model(model_name, self.on_model_download_progress)
    
    def on_model_download_progress(self, model_name, progress, status_text):
        """模型下载进度更新"""
        # 更新模型选择器中的下载进度
        self.model_selector.update_download_progress(model_name, progress, status_text)
        
        # 下载完成后，更新UI状态
        if progress == 100:
            self.update_ui_state()
    
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
    
def main():
    app = QApplication(sys.argv)
    
    # 设置样式
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
