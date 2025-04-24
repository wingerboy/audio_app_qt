from PyQt5.QtWidgets import (
    QWidget, QComboBox, QPushButton, QHBoxLayout, QVBoxLayout, 
    QLabel, QProgressBar, QMenu, QAction, QDialog, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont
from ui.theme_manager import ThemeManager

class ModelDownloadDialog(QDialog):
    """显示模型下载进度的对话框"""
    
    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"下载模型 - {model_name}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # 模型名称
        self.lblModel = QLabel(f"模型: {model_name}")
        self.lblModel.setStyleSheet("font-weight: bold; color: #ddd;")
        layout.addWidget(self.lblModel)
        
        # 状态标签
        self.lblStatus = QLabel("准备下载...")
        self.lblStatus.setStyleSheet("color: #ddd;")
        layout.addWidget(self.lblStatus)
        
        # 进度条
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(True)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #333;
                height: 20px;
                text-align: center;
                color: white;
            }
            
            QProgressBar::chunk {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(self.progressBar)
        
        # 提示
        self.lblInfo = QLabel("下载可能需要较长时间，请耐心等待...")
        self.lblInfo.setStyleSheet("color: #aaa; font-style: italic;")
        layout.addWidget(self.lblInfo)
        
        # 关闭按钮
        self.btnClose = QPushButton("关闭")
        self.btnClose.setEnabled(False)
        self.btnClose.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #999;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:enabled {
                background-color: #2980b9;
                color: white;
            }
            QPushButton:enabled:hover {
                background-color: #3498db;
            }
        """)
        self.btnClose.clicked.connect(self.close)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btnClose)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def update_progress(self, progress, status_text):
        """更新进度条和状态文本"""
        if progress >= 0:
            self.progressBar.setValue(progress)
            
        if status_text:
            self.lblStatus.setText(status_text)
            
        # 下载完成或失败时，启用关闭按钮
        if progress == 100 or progress == -1:
            self.btnClose.setEnabled(True)
            if progress == 100:
                self.lblInfo.setText("下载完成！可以关闭此窗口。")
            else:
                self.lblInfo.setText("下载失败，请检查网络连接后重试。")
                
        # 强制UI更新
        self.repaint()
        QApplication.processEvents()

class ModelSelector(QWidget):
    """自定义的模型选择控件，显示模型下载状态"""
    
    # 当选择的模型改变时发出的信号
    modelSelected = pyqtSignal(str)
    
    # 当请求下载模型时发出的信号
    requestDownload = pyqtSignal(str)
    
    def __init__(self, model_manager, parent=None):
        super(ModelSelector, self).__init__(parent)
        
        self.model_manager = model_manager
        self.current_model = None
        self.download_dialog = None
        
        # 布局
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 模型下拉框
        self.comboModels = QComboBox()
        self.comboModels.setMinimumWidth(200)
        self.comboModels.setStyleSheet("""
            QComboBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #444;
                color: #ddd;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
            }
            QComboBox QAbstractItemView {
                background-color: #444;
                color: #ddd;
                selection-background-color: #666;
            }
        """)
        
        # 更新模型选项
        self.update_model_list()
        
        # 下载按钮
        self.btnDownload = QPushButton("下载")
        self.btnDownload.setFixedWidth(80)
        self.btnDownload.setStyleSheet(ThemeManager.get_primary_button_style())
        self.btnDownload.setEnabled(False)
        self.btnDownload.clicked.connect(self.download_current_model)
        
        # 添加到布局
        layout.addWidget(self.comboModels, 1)
        layout.addWidget(self.btnDownload)
        
        self.setLayout(layout)
        
        # 连接信号
        self.comboModels.currentIndexChanged.connect(self.on_model_changed)
    
    def update_model_list(self):
        """更新模型列表，显示下载状态"""
        self.comboModels.clear()
        
        for model in self.model_manager.available_models:
            status = self.model_manager.get_model_status(model)
            
            # 根据下载状态显示不同文本
            if status["status"] == "downloaded":
                display_text = f"✓ {model}"
            elif status["status"] == "downloading":
                display_text = f"⏳ {model} ({status['progress']}%)"
            else:
                display_text = f"⬇ {model} (未下载)"
                
            self.comboModels.addItem(display_text, model)
    
    def get_current_model(self):
        """获取当前选择的模型名称（不含状态标记）"""
        if self.current_model:
            return self.current_model
        return ""
    
    def on_model_changed(self):
        """当选择的模型改变时调用"""
        index = self.comboModels.currentIndex()
        if index >= 0:
            # 获取实际的模型名称（保存在userData中）
            model_name = self.comboModels.itemData(index)
            self.current_model = model_name
            
            # 检查模型是否需要下载
            status = self.model_manager.get_model_status(model_name)
            self.btnDownload.setEnabled(status["status"] != "downloaded" and status["status"] != "downloading")
            
            # 发出信号
            self.modelSelected.emit(model_name)
    
    def download_current_model(self):
        """下载当前选择的模型"""
        if not self.current_model:
            return
            
        # 禁用下载按钮
        self.btnDownload.setEnabled(False)
        
        # 创建并显示下载对话框
        self.download_dialog = ModelDownloadDialog(self.current_model, self)
        
        # 发出下载请求信号
        self.requestDownload.emit(self.current_model)
        
        # 显示对话框
        self.download_dialog.show()
    
    def update_download_progress(self, model_name, progress, status_text):
        """更新下载进度"""
        # 更新下载对话框
        if self.download_dialog and model_name == self.current_model:
            # 确保对话框仍然存在且可见
            if self.download_dialog.isVisible():
                self.download_dialog.update_progress(progress, status_text)
            else:
                # 如果对话框已关闭但下载完成，显示提示
                if progress == 100:
                    QMessageBox.information(self, "下载完成", f"模型 {model_name} 已成功下载完成")
                elif progress == -1:
                    QMessageBox.warning(self, "下载失败", f"模型 {model_name} 下载失败: {status_text}")
            
        # 更新模型列表
        self.update_model_list()
        
        # 如果下载完成，启用按钮
        if progress == 100 or progress == -1:
            # 重新检查当前模型状态
            status = self.model_manager.get_model_status(self.current_model)
            self.btnDownload.setEnabled(status["status"] != "downloaded" and status["status"] != "downloading")
            
    def set_selected_model(self, model_name):
        """设置当前选择的模型"""
        for i in range(self.comboModels.count()):
            if self.comboModels.itemData(i) == model_name:
                self.comboModels.setCurrentIndex(i)
                break
