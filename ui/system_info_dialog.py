from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextBrowser, QTabWidget, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from ui.theme_manager import ThemeManager

class SystemInfoDialog(QDialog):
    """系统环境信息对话框"""
    
    def __init__(self, system_info, parent=None):
        super().__init__(parent)
        self.system_info = system_info
        self.setWindowTitle("系统环境信息")
        self.setMinimumSize(600, 400)
        self.setup_ui()
    
    def setup_ui(self):
        """设置对话框UI"""
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 摘要选项卡
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        
        # 添加HTML格式的摘要信息
        summary_browser = QTextBrowser()
        summary_browser.setOpenExternalLinks(True)
        summary_browser.setHtml(self.system_info.get_status_html())
        summary_layout.addWidget(summary_browser)
        
        # 如果CUDA不可用或FFmpeg不可用，显示安装建议
        if (not self.system_info.info['dependencies']['cuda_available'] or
            not self.system_info.info['ffmpeg']['available']):
            
            help_widget = QWidget()
            help_layout = QVBoxLayout(help_widget)
            
            help_label = QLabel("<b>环境安装建议</b>")
            help_label.setStyleSheet("color: #2980b9;")
            help_layout.addWidget(help_label)
            
            if not self.system_info.info['dependencies']['cuda_available']:
                cuda_help = QLabel(
                    "• GPU加速不可用，转录将使用CPU运行（较慢）。<br>"
                    "• 如果你有NVIDIA显卡，建议安装<a href='https://developer.nvidia.com/cuda-downloads'>CUDA</a>和兼容的PyTorch版本。"
                )
                cuda_help.setOpenExternalLinks(True)
                cuda_help.setWordWrap(True)
                help_layout.addWidget(cuda_help)
            
            if not self.system_info.info['ffmpeg']['available']:
                ffmpeg_help = QLabel(
                    "• FFmpeg未安装或无法访问，视频处理功能将不可用。<br>"
                    "• 请安装FFmpeg: <br>"
                    "  - Windows: <a href='https://ffmpeg.org/download.html'>下载链接</a><br>"
                    "  - macOS: 使用Homebrew安装 <code>brew install ffmpeg</code><br>"
                    "  - Linux: 使用包管理器安装，如 <code>apt install ffmpeg</code>"
                )
                ffmpeg_help.setOpenExternalLinks(True)
                ffmpeg_help.setWordWrap(True)
                help_layout.addWidget(ffmpeg_help)
            
            summary_layout.addWidget(help_widget)
        
        # 详细信息选项卡
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)
        
        details_browser = QTextBrowser()
        details_browser.setFont(QFont("Monospace", 10))
        
        # 将字典转换为可读格式
        detailed_text = self._format_detailed_info(self.system_info.get_detailed_info())
        details_browser.setText(detailed_text)
        
        details_layout.addWidget(details_browser)
        
        # 添加选项卡
        tab_widget.addTab(summary_tab, "摘要")
        tab_widget.addTab(details_tab, "详细信息")
        
        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("刷新信息")
        refresh_button.clicked.connect(self._refresh_info)
        refresh_button.setStyleSheet(ThemeManager.get_primary_button_style())
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet(ThemeManager.get_secondary_button_style())
        
        button_layout.addWidget(refresh_button)
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _refresh_info(self):
        """刷新系统信息"""
        self.system_info.collect_system_info()
        self.accept()  # 关闭当前对话框
        # 创建一个新的对话框并显示
        new_dialog = SystemInfoDialog(self.system_info, self.parent())
        new_dialog.exec_()
    
    def _format_detailed_info(self, info_dict, indent=0):
        """将嵌套字典格式化为可读文本"""
        result = ""
        indent_str = "  " * indent
        
        for key, value in info_dict.items():
            if isinstance(value, dict):
                result += f"{indent_str}{key}:\n"
                result += self._format_detailed_info(value, indent + 1)
            else:
                result += f"{indent_str}{key}: {value}\n"
        
        return result
