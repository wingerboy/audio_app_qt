from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

class ThemeManager:
    """主题管理器，用于应用统一的深色主题样式到所有UI组件"""
    
    @staticmethod
    def apply_dark_theme():
        """应用深色主题到整个应用程序"""
        # 设置调色板
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
        
        QApplication.setPalette(dark_palette)
        
        # 设置应用程序的全局样式表
        ThemeManager._set_global_stylesheet()
    
    @staticmethod
    def _set_global_stylesheet():
        """设置全局样式表"""
        style = """
        QMainWindow, QDialog {
            background-color: #353535;
            color: white;
        }
        QWidget {
            color: white;
            background-color: #353535;
        }
        QHeaderView::section {
            background-color: #3A3A3A;
            color: white;
            padding: 5px;
            border: 1px solid #5A5A5A;
        }
        QTableWidget {
            gridline-color: #5A5A5A;
            color: white;
            background-color: #2D2D2D;
            selection-background-color: #3D8EC9;
            selection-color: #FFFFFF;
            border: 1px solid #5A5A5A;
        }
        QTableWidget QTableCornerButton::section {
            background-color: #3A3A3A;
            border: 1px solid #5A5A5A;
        }
        QTableWidget::item {
            padding: 4px;
            border-bottom: 1px solid #5A5A5A;
        }
        QPushButton {
            background-color: #3A3A3A;
            color: white;
            border: 1px solid #5A5A5A;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #4A4A4A;
        }
        QPushButton:pressed {
            background-color: #2A2A2A;
        }
        QPushButton:disabled {
            background-color: #2A2A2A;
            color: #808080;
        }
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            border: 1px solid #5A5A5A;
            background-color: #2D2D2D;
            color: white;
            padding: 2px;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid #3D8EC9;
        }
        QComboBox {
            border: 1px solid #5A5A5A;
            border-radius: 3px;
            padding: 5px;
            background-color: #3A3A3A;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left: 1px solid #5A5A5A;
        }
        QComboBox::down-arrow {
            image: url(:/icons/arrow_down.png);
        }
        QComboBox QAbstractItemView {
            border: 1px solid #5A5A5A;
            background-color: #2D2D2D;
            color: white;
            selection-background-color: #3D8EC9;
        }
        QSlider::groove:horizontal {
            height: 8px;
            background: #3A3A3A;
            margin: 2px 0;
        }
        QSlider::handle:horizontal {
            background: #3D8EC9;
            border: 1px solid #5A5A5A;
            width: 18px;
            margin: -2px 0;
            border-radius: 9px;
        }
        QRadioButton, QCheckBox {
            color: white;
            spacing: 5px;
        }
        QRadioButton::indicator, QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        QGroupBox {
            border: 1px solid #5A5A5A;
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
            color: white;
        }
        QScrollBar:vertical {
            border: none;
            background: #2D2D2D;
            width: 14px;
            margin: 15px 0 15px 0;
        }
        QScrollBar::handle:vertical {
            background: #5A5A5A;
            min-height: 30px;
            border-radius: 7px;
        }
        QScrollBar::handle:vertical:hover {
            background: #6A6A6A;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
            height: 15px;
        }
        QScrollBar:horizontal {
            border: none;
            background: #2D2D2D;
            height: 14px;
            margin: 0 15px 0 15px;
        }
        QScrollBar::handle:horizontal {
            background: #5A5A5A;
            min-width: 30px;
            border-radius: 7px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #6A6A6A;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
            width: 15px;
        }
        QProgressBar {
            border: 1px solid #5A5A5A;
            border-radius: 3px;
            background-color: #2D2D2D;
            color: white;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #3D8EC9;
            width: 20px;
        }
        QToolTip {
            border: 1px solid #5A5A5A;
            background-color: #2D2D2D;
            color: white;
            padding: 3px;
        }
        QTabWidget::pane {
            border: 1px solid #5A5A5A;
        }
        QTabBar::tab {
            background: #3A3A3A;
            border: 1px solid #5A5A5A;
            padding: 5px 10px;
        }
        QTabBar::tab:selected {
            background: #4A4A4A;
        }
        QTabBar::tab:!selected {
            margin-top: 2px;
        }
        QMenu {
            background-color: #2D2D2D;
            color: white;
            border: 1px solid #5A5A5A;
        }
        QMenu::item {
            padding: 5px 30px 5px 20px;
        }
        QMenu::item:selected {
            background-color: #3D8EC9;
        }
        QMenu::separator {
            height: 1px;
            background-color: #5A5A5A;
            margin: 5px 10px;
        }
        QMessageBox {
            background-color: #353535;
            color: white;
        }
        QLabel {
            color: white;
        }
        QStatusBar {
            background-color: #2D2D2D;
            color: white;
            border-top: 1px solid #5A5A5A;
        }
        """
        
        # 获取当前应用实例，然后设置样式表
        app = QApplication.instance()
        if app:
            app.setStyleSheet(style)
    
    @staticmethod
    def get_primary_button_style():
        """获取主按钮样式"""
        return """
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
        """
    
    @staticmethod
    def get_secondary_button_style():
        """获取次要按钮样式"""
        return """
            QPushButton {
                background-color: #7f8c8d;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #95a5a6;
            }
            QPushButton:pressed {
                background-color: #6d7b7c;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """ 