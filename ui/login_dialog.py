from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QMessageBox, QProgressBar, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QFont
from ui.theme_manager import ThemeManager

class LoginDialog(QDialog):
    """登录对话框"""
    loginSuccess = pyqtSignal(str, str, str) # session_token, user_type, expiry_date
    
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle("用户登录")
        self.setMinimumWidth(400)
        self.setMinimumHeight(250)
        # 设置为应用模态，阻止与其他窗口交互
        self.setWindowModality(Qt.ApplicationModal)
        # 移除帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # 设置为固定大小
        self.setFixedSize(400, 250)
        
        # 创建布局
        self.init_ui()
        
        # 连接信号
        self.btnLogin.clicked.connect(self.login)
        
        # 设置初始焦点到用户名输入框
        self.editCardId.setFocus()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        icon_label = QLabel()
        # 可以添加应用图标
        # icon_label.setPixmap(QPixmap("路径/到/图标").scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        title_label = QLabel("音频分割工具登录")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_layout.addWidget(icon_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)
        
        # 设备绑定提示
        self.device_info_label = QLabel("登录将绑定您的设备，请确保当前设备为个人常用设备")
        self.device_info_label.setStyleSheet("color: #e74c3c; font-style: italic;")
        self.device_info_label.setWordWrap(True)
        main_layout.addWidget(self.device_info_label)
        
        # 表单
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.editCardId = QLineEdit()
        self.editCardId.setPlaceholderText("请输入卡密ID")
        self.editCardId.setMinimumHeight(30)
        
        self.editCardKey = QLineEdit()
        self.editCardKey.setPlaceholderText("请输入卡密密钥")
        self.editCardKey.setEchoMode(QLineEdit.Password)
        self.editCardKey.setMinimumHeight(30)
        
        # 设置回车键触发登录按钮
        self.editCardId.returnPressed.connect(self.login)
        self.editCardKey.returnPressed.connect(self.login)
        
        form_layout.addRow("卡密ID:", self.editCardId)
        form_layout.addRow("卡密密钥:", self.editCardKey)
        
        main_layout.addLayout(form_layout)
        
        # 添加状态提示标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #e74c3c;")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.hide()
        main_layout.addWidget(self.status_label)
        
        # 进度条
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 0)  # 不确定进度模式
        self.progressBar.setMinimumHeight(5)
        self.progressBar.setTextVisible(False)
        self.progressBar.hide()
        main_layout.addWidget(self.progressBar)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btnLogin = QPushButton("登录")
        self.btnLogin.setMinimumHeight(35)
        self.btnLogin.setMinimumWidth(100)
        self.btnLogin.setStyleSheet(ThemeManager.get_primary_button_style())
        btn_layout.addWidget(self.btnLogin)
        btn_layout.addStretch()
        
        main_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
        
    def login(self):
        card_id = self.editCardId.text().strip()
        card_key = self.editCardKey.text().strip()
        
        if not card_id or not card_key:
            QMessageBox.warning(self, "警告", "请输入卡密ID和密钥")
            return
        
        # 显示进度条和状态
        self.status_label.setText("正在登录，请稍候...")
        self.status_label.setStyleSheet("color: #3498db;")
        self.status_label.show()
        self.progressBar.show()
        self.btnLogin.setEnabled(False)
        
        # 登录相关逻辑将在主应用程序中实现
        # 不直接发出信号，实际登录过程在MainWindow的handle_login方法中处理
        
    def show_login_result(self, success, message):
        self.progressBar.hide()
        
        if not success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #e74c3c;")
            self.btnLogin.setEnabled(True)
            return
        
        # 登录成功
        self.status_label.setText("登录成功，正在初始化...")
        self.status_label.setStyleSheet("color: #27ae60;")
        # 登录成功时发出信号
        # 此方法由MainWindow中的handle_login方法在登录成功后调用
        # 而实际的session_token等数据已经存储在SessionManager中
        
    def keyPressEvent(self, event):
        # 重写keyPressEvent，阻止Escape键关闭对话框
        if event.key() != Qt.Key_Escape:
            super(LoginDialog, self).keyPressEvent(event) 