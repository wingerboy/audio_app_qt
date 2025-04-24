from PyQt5.QtWidgets import (
    QMainWindow, QHeaderView, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QSpinBox, QTextEdit, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar, QListWidget, QLineEdit,
    QGridLayout, QHBoxLayout, QVBoxLayout, QGroupBox, QWidget, QCheckBox,
    QRadioButton, QSlider, QButtonGroup, QFrame
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        # 设置窗口基本属性
        MainWindow.setWindowTitle("音频内容分析与处理")
        MainWindow.resize(1000, 750)
        
        # 中央窗口部件
        central_widget = QWidget()
        MainWindow.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        
        # 步骤指示器
        steps_layout = QHBoxLayout()
        
        # 创建步骤指示器
        self.step1Label = QLabel("1\n上传文件")
        self.step1Label.setAlignment(Qt.AlignCenter)
        self.step1Label.setFixedSize(80, 50)
        self.step1Label.setStyleSheet("background-color: #555; color: white; border-radius: 10px;")
        
        self.step2Label = QLabel("2\n分析内容")
        self.step2Label.setAlignment(Qt.AlignCenter)
        self.step2Label.setFixedSize(80, 50)
        self.step2Label.setStyleSheet("background-color: #555; color: white; border-radius: 10px;")
        
        self.step3Label = QLabel("3\n分割音频")
        self.step3Label.setAlignment(Qt.AlignCenter)
        self.step3Label.setFixedSize(80, 50)
        self.step3Label.setStyleSheet("background-color: #6360f5; color: white; border-radius: 10px;")
        
        self.step4Label = QLabel("4\n下载文件")
        self.step4Label.setAlignment(Qt.AlignCenter)
        self.step4Label.setFixedSize(80, 50)
        self.step4Label.setStyleSheet("background-color: #555; color: white; border-radius: 10px;")
        
        steps_layout.addWidget(self.step1Label)
        steps_layout.addStretch(1)
        steps_layout.addWidget(self.step2Label)
        steps_layout.addStretch(1)
        steps_layout.addWidget(self.step3Label)
        steps_layout.addStretch(1)
        steps_layout.addWidget(self.step4Label)
        
        main_layout.addLayout(steps_layout)
        
        # 文件选择区域
        file_group = QGroupBox("选择音频或视频文件")
        file_layout = QHBoxLayout()
        
        self.lblFilePath = QLabel("未选择文件")
        self.lblFilePath.setStyleSheet("""
            color: #ddd;
            padding: 5px;
            background-color: #333;
            border: 1px solid #555;
        """)
        
        self.btnSelectFile = QPushButton("选择文件")
        self.btnSelectFile.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        
        file_layout.addWidget(self.lblFilePath, 1)
        file_layout.addWidget(self.btnSelectFile)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # 转录区域
        transcribe_group = QGroupBox("转录设置")
        transcribe_layout = QHBoxLayout()
        
        # 保存为类属性以便外部访问
        self.transcribe_group = transcribe_group
        
        self.lblModelName = QLabel("模型:")
        self.lblModelName.setStyleSheet("color: #ddd;")
        
        # 将comboModelName替换为自定义的ModelSelector控件
        # (ModelSelector会在主程序中实例化和配置)
        self.modelSelector = None  # 会在主程序中设置
        
        self.lblLanguage = QLabel("语言:")
        self.lblLanguage.setStyleSheet("color: #ddd;")
        
        self.comboLanguage = QComboBox()
        self.comboLanguage.addItems(["中文"])
        self.comboLanguage.setFixedWidth(150)
        self.comboLanguage.setStyleSheet("""
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
        
        self.lblChunkLength = QLabel("分段长度:")
        self.lblChunkLength.setStyleSheet("color: #ddd;")
        
        self.spinChunkLength = QSpinBox()
        self.spinChunkLength.setRange(5, 30)
        self.spinChunkLength.setValue(30)
        self.spinChunkLength.setSuffix(" 秒")
        self.spinChunkLength.setFixedWidth(80)
        self.spinChunkLength.setStyleSheet("""
            QSpinBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                background-color: #444;
                color: #ddd;
            }
            QSpinBox:focus {
                border: 1px solid #6af;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #555;
                border: none;
            }
        """)
        
        self.btnTranscribe = QPushButton("开始转录")
        self.btnTranscribe.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        
        transcribe_layout.addWidget(self.lblModelName)
        transcribe_layout.addWidget(self.modelSelector)  # 使用modelSelector替换comboModelName
        transcribe_layout.addWidget(self.lblLanguage)
        transcribe_layout.addWidget(self.comboLanguage)
        transcribe_layout.addWidget(self.lblChunkLength)
        transcribe_layout.addWidget(self.spinChunkLength)
        transcribe_layout.addStretch(1)
        transcribe_layout.addWidget(self.btnTranscribe)
        
        transcribe_group.setLayout(transcribe_layout)
        main_layout.addWidget(transcribe_group)
        
        # 音频内容分段区域
        segments_group = QGroupBox("音频内容分段")
        segments_layout = QVBoxLayout()
        
        # 保存为类属性
        self.segments_group = segments_group
        
        # 过滤区域
        filter_frame = QFrame()
        filter_frame.setFrameShape(QFrame.StyledPanel)
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #333333;
                border: 1px solid #505050;
                border-radius: 8px;
            }
        """)
        
        # 保存为类属性
        self.filter_group = filter_frame
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(15, 10, 15, 10)
        filter_layout.setSpacing(10)
        
        # 过滤模式下拉菜单
        self.comboFilterType = QComboBox()
        self.comboFilterType.setMinimumWidth(120)
        self.comboFilterType.addItems(["过滤模式", "包含关键词", "不包含关键词"])
        self.comboFilterType.setStyleSheet("""
            QComboBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #444;
                color: #ddd;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555;
            }
            QComboBox QAbstractItemView {
                background-color: #444;
                color: #ddd;
                selection-background-color: #666;
            }
        """)
        
        # 关键词过滤输入框
        self.editFilterKeyword = QLineEdit()
        self.editFilterKeyword.setMinimumWidth(200)
        self.editFilterKeyword.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #444;
                color: #ddd;
            }
            QLineEdit:focus {
                border: 1px solid #6af;
            }
        """)
        self.editFilterKeyword.setPlaceholderText("过滤内容(多个关键词用逗号分隔)...")
        
        # 时长范围输入区域
        duration_frame = QFrame()
        duration_frame.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #505050;
                border-radius: 4px;
            }
        """)
        
        duration_layout = QHBoxLayout(duration_frame)
        duration_layout.setContentsMargins(10, 5, 10, 5)
        duration_layout.setSpacing(8)
        
        self.lblDurationTitle = QLabel("时长:")
        self.lblDurationTitle.setStyleSheet("color: #ddd; font-weight: bold;")
        
        self.spinMinDuration = QSpinBox()
        self.spinMinDuration.setRange(0, 9999)
        self.spinMinDuration.setFixedWidth(80)
        self.spinMinDuration.setSuffix(" 秒")
        self.spinMinDuration.setStyleSheet("""
            QSpinBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                background-color: #444;
                color: #ddd;
            }
            QSpinBox:focus {
                border: 1px solid #6af;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #555;
                border: none;
            }
        """)
        
        self.lblDurationTo = QLabel("至")
        self.lblDurationTo.setAlignment(Qt.AlignCenter)
        self.lblDurationTo.setStyleSheet("color: #ddd;")
        
        self.spinMaxDuration = QSpinBox()
        self.spinMaxDuration.setRange(0, 9999)
        self.spinMaxDuration.setFixedWidth(80)
        self.spinMaxDuration.setSuffix(" 秒")
        self.spinMaxDuration.setStyleSheet("""
            QSpinBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                background-color: #444;
                color: #ddd;
            }
            QSpinBox:focus {
                border: 1px solid #6af;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #555;
                border: none;
            }
        """)
        
        self.lblDurationCount = QLabel("(0/0)")
        self.lblDurationCount.setStyleSheet("color: #ddd;")
        
        duration_layout.addWidget(self.lblDurationTitle)
        duration_layout.addWidget(self.spinMinDuration)
        duration_layout.addWidget(self.lblDurationTo)
        duration_layout.addWidget(self.spinMaxDuration)
        duration_layout.addWidget(self.lblDurationCount)
        
        # 应用筛选按钮
        self.btnApplyFilter = QPushButton("应用筛选")
        self.btnApplyFilter.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btnApplyFilter.setFixedWidth(100)
        
        filter_layout.addWidget(self.comboFilterType)
        filter_layout.addWidget(self.editFilterKeyword)
        filter_layout.addWidget(duration_frame)
        filter_layout.addWidget(self.btnApplyFilter)
        
        segments_layout.addWidget(filter_frame)
        
        # 标签按钮组和导出按钮
        tab_layout = QHBoxLayout()
        
        self.radioAll = QRadioButton("全部")
        self.radioAll.setChecked(True)
        self.radioAll.setStyleSheet("""
            QRadioButton {
                color: #ddd;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
                border-radius: 7px;
                border: 1px solid #777;
            }
            QRadioButton::indicator:checked {
                background-color: #3498db;
            }
        """)
        
        self.radioSelected = QRadioButton("已选择")
        self.radioSelected.setStyleSheet("""
            QRadioButton {
                color: #ddd;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
                border-radius: 7px;
                border: 1px solid #777;
            }
            QRadioButton::indicator:checked {
                background-color: #3498db;
            }
        """)
        
        self.radioUnselected = QRadioButton("未选择")
        self.radioUnselected.setStyleSheet("""
            QRadioButton {
                color: #ddd;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
                border-radius: 7px;
                border: 1px solid #777;
            }
            QRadioButton::indicator:checked {
                background-color: #3498db;
            }
        """)
        
        # 状态标签
        self.lblStatSelected = QLabel("已选择: 0")
        self.lblStatSelected.setStyleSheet("color: #ddd;")
        
        self.lblStatUnselected = QLabel("未选择: 0")
        self.lblStatUnselected.setStyleSheet("color: #ddd;")
        
        self.lblStatTotal = QLabel("总计: 0")
        self.lblStatTotal.setStyleSheet("color: #ddd;")
        
        # 导出按钮
        self.btnExport = QPushButton("导出选中")
        self.btnExport.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #219653;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btnExport.setFixedWidth(100)
        
        tab_layout.addWidget(self.radioAll)
        tab_layout.addWidget(self.radioSelected)
        tab_layout.addWidget(self.radioUnselected)
        tab_layout.addWidget(self.lblStatTotal)
        tab_layout.addWidget(self.lblStatSelected)
        tab_layout.addWidget(self.lblStatUnselected)
        tab_layout.addStretch(1)
        tab_layout.addWidget(self.btnExport)
        
        segments_layout.addLayout(tab_layout)
        
        # 分段表格
        self.tableSegments = QTableWidget()
        self.tableSegments.setColumnCount(5)  # 选择、起始时间、结束时间、时长、文本
        self.tableSegments.setHorizontalHeaderLabels(["选择", "时间范围", "时长", "内容", "播放"])
        self.tableSegments.horizontalHeader().setStretchLastSection(True)
        self.tableSegments.setStyleSheet("""
            QTableWidget {
                background-color: #222;
                color: #ddd;
                gridline-color: #444;
                border: 1px solid #555;
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
            }
            QTableWidget QCheckBox {
                color: #ddd;
            }
        """)
        
        segments_layout.addWidget(self.tableSegments)
        segments_group.setLayout(segments_layout)
        main_layout.addWidget(segments_group)
        
        # 导出设置
        export_group = QGroupBox("导出设置")
        export_layout = QGridLayout()
        
        # 保存为类属性
        self.export_group = export_group
        
        self.lblFilePrefix = QLabel("文件名前缀:")
        self.lblFilePrefix.setStyleSheet("color: #ddd;")
        
        self.editFilePrefix = QLineEdit("segment")
        self.editFilePrefix.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #444;
                color: #ddd;
            }
            QLineEdit:focus {
                border: 1px solid #6af;
            }
        """)
        
        self.lblFormat = QLabel("输出格式:")
        self.lblFormat.setStyleSheet("color: #ddd;")
        
        self.comboFormat = QComboBox()
        self.comboFormat.addItems(["MP3"])
        self.comboFormat.setStyleSheet("""
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
        
        self.lblBitrate = QLabel("比特率:")
        self.lblBitrate.setStyleSheet("color: #ddd;")
        
        self.comboBitrate = QComboBox()
        self.comboBitrate.addItems(["192k"])
        self.comboBitrate.setCurrentText("192k")
        self.comboBitrate.setStyleSheet("""
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
        
        self.btnBatchExport = QPushButton("批量导出")
        self.btnBatchExport.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #219653;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        
        export_layout.addWidget(self.lblFilePrefix, 0, 0)
        export_layout.addWidget(self.editFilePrefix, 0, 1)
        export_layout.addWidget(self.lblFormat, 0, 2)
        export_layout.addWidget(self.comboFormat, 0, 3)
        export_layout.addWidget(self.lblBitrate, 0, 4)
        export_layout.addWidget(self.comboBitrate, 0, 5)
        export_layout.addWidget(self.btnBatchExport, 0, 6)
        
        export_group.setLayout(export_layout)
        main_layout.addWidget(export_group)
        
        # 进度条
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(False)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #333;
                height: 10px;
            }
            QProgressBar::chunk {
                background-color: #2980b9;
                width: 1px;
            }
        """)
        
        # 状态标签
        self.lblStatus = QLabel("就绪")
        self.lblStatus.setStyleSheet("color: #ddd;")
        
        # 系统信息按钮
        self.btnSystemInfo = QPushButton("查看系统环境")
        self.btnSystemInfo.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #ddd;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        self.btnSystemInfo.setFixedWidth(120)
        
        # 系统状态指示器
        self.lblSystemStatus = QLabel()
        self.lblSystemStatus.setStyleSheet("color: #aaa; font-size: 12px;")
        self.lblSystemStatus.setText("系统状态: 加载中...")
        
        # 状态栏
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.lblStatus, 1)
        status_layout.addWidget(self.lblSystemStatus)
        status_layout.addWidget(self.btnSystemInfo)
        status_layout.addWidget(self.progressBar)
        
        main_layout.addLayout(status_layout)
