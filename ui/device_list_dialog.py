from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                          QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                          QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QIcon, QFont, QColor

import json
from datetime import datetime

class DeviceListDialog(QDialog):
    """设备列表对话框"""
    
    def __init__(self, session_manager, parent=None):
        super(DeviceListDialog, self).__init__(parent)
        self.session_manager = session_manager
        self.setWindowTitle("设备绑定列表")
        self.setMinimumSize(800, 500)
        self.setWindowModality(Qt.ApplicationModal)
        self.setup_ui()
        self.devices_loaded = False
    
    def setup_ui(self):
        """设置对话框UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 状态信息
        info_layout = QHBoxLayout()
        
        self.status_label = QLabel("正在加载设备信息...")
        self.status_label.setStyleSheet("color: #3498db; font-weight: bold;")
        info_layout.addWidget(self.status_label)
        
        self.limit_label = QLabel("")
        self.limit_label.setAlignment(Qt.AlignRight)
        self.limit_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.limit_label)
        
        layout.addLayout(info_layout)
        
        # 加载进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度模式
        self.progress_bar.setMinimumHeight(5)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 设备表格
        self.devices_table = QTableWidget(0, 5)
        self.devices_table.setHorizontalHeaderLabels([
            "设备名称", "硬件信息", "首次登录时间", "最近登录时间", "状态"
        ])
        
        # 设置列宽
        header = self.devices_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 设备名称列自适应
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 硬件信息列自适应
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 首次登录时间列
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 最近登录时间列
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 状态列
        
        # 设置样式 - 使用深色主题
        self.devices_table.setStyleSheet("""
            QTableWidget {
                background-color: #222;
                color: #ddd;
                gridline-color: #444;
                border: 1px solid #555;
                alternate-background-color: #2a2a2a;
            }
            QHeaderView::section {
                background-color: #333;
                color: #ddd;
                padding: 5px;
                border: 1px solid #555;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #345;
            }
        """)
        
        # 启用交替行颜色
        self.devices_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.devices_table)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.clicked.connect(self.load_devices)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
        """)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        close_button.setMinimumWidth(100)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #7f8c8d;
                color: white;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #95a5a6;
            }
            QPushButton:pressed {
                background-color: #6d7b7c;
            }
        """)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def showEvent(self, event):
        """对话框显示事件"""
        super(DeviceListDialog, self).showEvent(event)
        if not self.devices_loaded:
            self.load_devices()
    
    def load_devices(self):
        """加载设备列表"""
        # 清空表格
        self.devices_table.setRowCount(0)
        
        # 显示加载状态
        self.status_label.setText("正在加载设备信息...")
        self.status_label.setStyleSheet("color: #3498db; font-weight: bold;")
        self.limit_label.setText("")
        self.progress_bar.show()
        self.refresh_button.setEnabled(False)
        
        # 获取设备列表
        success, message, data = self.session_manager.get_device_list()
        
        # 隐藏加载状态
        self.progress_bar.hide()
        self.refresh_button.setEnabled(True)
        
        if not success:
            self.status_label.setText(f"加载失败: {message}")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            return
        
        # 更新设备计数信息
        devices_count = data.get("device_count", 0)
        max_devices = data.get("max_device_count", 1)
        self.status_label.setText(f"设备列表加载成功")
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        
        # 设置设备数量限制信息
        if devices_count >= max_devices:
            self.limit_label.setText(f"设备数: {devices_count}/{max_devices} (已达上限)")
            self.limit_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            self.limit_label.setText(f"设备数: {devices_count}/{max_devices}")
            self.limit_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        
        # 填充设备数据
        devices = data.get("devices", [])
        self.devices_table.setRowCount(len(devices))
        
        current_fingerprint = self.session_manager.device_fingerprint
        
        for row, device in enumerate(devices):
            # 设备名称
            name_item = QTableWidgetItem(device.get("device_name", "未知设备"))
            self.devices_table.setItem(row, 0, name_item)
            
            # 设备指纹，如果是当前设备则高亮显示
            is_current_device = device.get("device_fingerprint") == current_fingerprint
            if is_current_device:
                name_item.setBackground(QColor(0, 80, 0))  # 深绿色背景，更适合暗色主题
                name_item.setForeground(QColor(255, 255, 255))  # 白色文字
                name_item.setToolTip("当前设备")
            
            # 硬件信息
            hardware_info = device.get("hardware_info", {})
            hardware_text = self._format_hardware_info(hardware_info)
            hardware_item = QTableWidgetItem(hardware_text)
            hardware_item.setToolTip(json.dumps(hardware_info, indent=2, ensure_ascii=False))
            self.devices_table.setItem(row, 1, hardware_item)
            
            # 首次登录时间
            first_login = device.get("first_login_at", "")
            first_login_text = self._format_datetime(first_login)
            self.devices_table.setItem(row, 2, QTableWidgetItem(first_login_text))
            
            # 最近登录时间
            last_login = device.get("last_login_at", "")
            last_login_text = self._format_datetime(last_login)
            self.devices_table.setItem(row, 3, QTableWidgetItem(last_login_text))
            
            # 状态
            is_active = device.get("is_active", False)
            status_text = "在线" if is_active else "离线"
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            
            if is_active:
                status_item.setForeground(QColor("#2ecc71"))  # 亮绿色
                if is_current_device:
                    status_item.setText("当前设备")
            else:
                status_item.setForeground(QColor("#95a5a6"))  # 浅灰色
            
            self.devices_table.setItem(row, 4, status_item)
            
            # 如果是当前设备，设置整行的背景色
            if is_current_device:
                for col in range(self.devices_table.columnCount()):
                    item = self.devices_table.item(row, col)
                    if item:
                        item.setBackground(QColor(0, 80, 0))  # 深绿色背景
                        item.setForeground(QColor(255, 255, 255))  # 白色文字，增加对比度
        
        self.devices_loaded = True
    
    def _format_hardware_info(self, hardware_info):
        """格式化硬件信息显示"""
        result = []
        
        # 系统信息
        os_name = hardware_info.get("system", "未知系统")
        os_version = hardware_info.get("version", "")
        if os_name:
            result.append(f"{os_name} {os_version}")
        
        # CPU信息
        cpu_info = hardware_info.get("cpu", {})
        if "brand" in cpu_info:
            result.append(f"CPU: {cpu_info['brand']}")
        elif "processor" in cpu_info:
            result.append(f"CPU: {cpu_info['processor']}")
        
        # 内存信息
        memory_info = hardware_info.get("memory", {})
        if "total" in memory_info:
            total_gb = memory_info["total"] / (1024 * 1024 * 1024)
            result.append(f"内存: {total_gb:.1f} GB")
        
        return " | ".join(result)
    
    def _format_datetime(self, datetime_str):
        """格式化日期时间字符串"""
        if not datetime_str:
            return "未知"
            
        try:
            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime_str 