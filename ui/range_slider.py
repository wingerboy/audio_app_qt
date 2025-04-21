from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtWidgets import QWidget, QSlider, QHBoxLayout, QLabel
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient


class RangeSlider(QWidget):
    """自定义的范围滑动条控件，允许同时选择最小值和最大值"""
    
    # 自定义信号，当范围改变时发出
    rangeChanged = pyqtSignal(int, int)
    
    def __init__(self, parent=None):
        super(RangeSlider, self).__init__(parent)
        
        # 最小最大范围
        self.minimum = 0
        self.maximum = 100
        
        # 当前选择的最小最大值
        self.min_value = 0
        self.max_value = 100
        
        # 滑块状态
        self._active_slider = None  # 'min' 或 'max'
        
        # 滑块属性
        self.slider_width = 12  # 增加滑块宽度
        self.slider_height = 24  # 增加滑块高度
        
        # 布局和样式
        self.setMinimumHeight(40)  # 增加控件高度
        self.setMinimumWidth(150)  # 设置最小宽度
        self.setMouseTracking(True)
        
    def setRange(self, min_value, max_value):
        """设置滑动条的范围"""
        self.minimum = min_value
        self.maximum = max_value
        self.min_value = min_value
        self.max_value = max_value
        self.update()
        
    def setRangeValues(self, min_value, max_value):
        """设置当前选择的范围值"""
        if min_value >= self.minimum and min_value <= self.maximum:
            self.min_value = min_value
        
        if max_value >= self.minimum and max_value <= self.maximum:
            self.max_value = max_value
            
        if self.min_value > self.max_value:
            self.min_value = self.max_value
            
        self.update()
        self.rangeChanged.emit(self.min_value, self.max_value)
        
    def getRangeValues(self):
        """获取当前选择的范围值"""
        return self.min_value, self.max_value
        
    def paintEvent(self, event):
        """绘制控件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景轨道
        pen = QPen(Qt.gray, 1)
        painter.setPen(pen)
        
        track_rect = self._get_track_rect()
        
        # 使用渐变背景
        gradient = QLinearGradient(track_rect.left(), 0, track_rect.right(), 0)
        gradient.setColorAt(0, QColor(220, 220, 220))
        gradient.setColorAt(1, QColor(180, 180, 180))
        painter.fillRect(track_rect, gradient)
        
        # 绘制轨道边框
        painter.drawRect(track_rect)
        
        # 绘制选中范围
        selected_rect = self._get_selected_rect()
        # 使用蓝色渐变
        sel_gradient = QLinearGradient(selected_rect.left(), 0, selected_rect.right(), 0)
        sel_gradient.setColorAt(0, QColor(100, 150, 255))
        sel_gradient.setColorAt(1, QColor(70, 120, 230))
        painter.fillRect(selected_rect, sel_gradient)
        
        # 绘制左右滑块
        min_slider_rect = self._get_min_slider_rect()
        max_slider_rect = self._get_max_slider_rect()
        
        # 设置滑块颜色和渐变
        min_gradient = QLinearGradient(0, min_slider_rect.top(), 0, min_slider_rect.bottom())
        min_gradient.setColorAt(0, QColor(100, 150, 255))
        min_gradient.setColorAt(1, QColor(70, 100, 230))
        
        max_gradient = QLinearGradient(0, max_slider_rect.top(), 0, max_slider_rect.bottom())
        max_gradient.setColorAt(0, QColor(100, 150, 255))
        max_gradient.setColorAt(1, QColor(70, 100, 230))
        
        # 绘制滑块
        painter.fillRect(min_slider_rect, min_gradient)
        painter.fillRect(max_slider_rect, max_gradient)
        
        # 给滑块添加3D效果
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
        painter.drawLine(min_slider_rect.topLeft(), min_slider_rect.topRight())
        painter.drawLine(min_slider_rect.topLeft(), min_slider_rect.bottomLeft())
        
        painter.drawLine(max_slider_rect.topLeft(), max_slider_rect.topRight())
        painter.drawLine(max_slider_rect.topLeft(), max_slider_rect.bottomLeft())
        
        # 绘制滑块边框
        painter.setPen(QPen(QColor(40, 70, 180), 1))
        painter.drawRect(min_slider_rect)
        painter.drawRect(max_slider_rect)
        
    def _get_track_rect(self):
        """获取轨道矩形"""
        return QRect(
            self.slider_width // 2,
            (self.height() - 8) // 2, # 增加轨道高度
            self.width() - self.slider_width,
            8
        )
        
    def _get_selected_rect(self):
        """获取选中范围矩形"""
        track_rect = self._get_track_rect()
        
        if self.maximum == self.minimum:
            return QRect(0, 0, 0, 0)
            
        min_pos = int(self._value_to_position(self.min_value))
        max_pos = int(self._value_to_position(self.max_value))
        
        return QRect(
            min_pos,
            track_rect.top(),
            max_pos - min_pos,
            track_rect.height()
        )
        
    def _get_min_slider_rect(self):
        """获取最小值滑块的矩形"""
        x = int(self._value_to_position(self.min_value))
        y = (self.height() - self.slider_height) // 2
        return QRect(x - self.slider_width // 2, y, self.slider_width, self.slider_height)
        
    def _get_max_slider_rect(self):
        """获取最大值滑块的矩形"""
        x = int(self._value_to_position(self.max_value))
        y = (self.height() - self.slider_height) // 2
        return QRect(x - self.slider_width // 2, y, self.slider_width, self.slider_height)
        
    def _position_to_value(self, pos):
        """将位置转换为值"""
        span = self.width() - self.slider_width
        delta = pos - self.slider_width // 2
        return int(self.minimum + (self.maximum - self.minimum) * delta / span)
        
    def _value_to_position(self, value):
        """将值转换为位置"""
        if self.maximum == self.minimum:
            return self.slider_width // 2
            
        span = self.width() - self.slider_width
        normalized = (value - self.minimum) / (self.maximum - self.minimum)
        return self.slider_width // 2 + int(normalized * span)
        
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        if event.button() == Qt.LeftButton:
            min_slider_rect = self._get_min_slider_rect()
            max_slider_rect = self._get_max_slider_rect()
            track_rect = self._get_track_rect()
            
            # 判断是否点击在最小值滑块上
            if min_slider_rect.contains(event.pos()):
                self._active_slider = 'min'
                self.setCursor(Qt.SizeHorCursor)  # 设置水平调整光标
                event.accept()
                return
                
            # 判断是否点击在最大值滑块上
            if max_slider_rect.contains(event.pos()):
                self._active_slider = 'max'
                self.setCursor(Qt.SizeHorCursor)  # 设置水平调整光标
                event.accept()
                return
                
            # 判断是否点击在轨道上（且不在滑块上）
            if track_rect.contains(event.pos()):
                # 找到点击位置更近的滑块并激活
                min_distance = abs(min_slider_rect.center().x() - event.pos().x())
                max_distance = abs(max_slider_rect.center().x() - event.pos().x())
                
                # 如果点击位置在最小滑块左边，直接选择最小滑块
                if event.pos().x() < min_slider_rect.center().x():
                    self._active_slider = 'min'
                # 如果点击位置在最大滑块右边，直接选择最大滑块
                elif event.pos().x() > max_slider_rect.center().x():
                    self._active_slider = 'max'
                # 否则选择最近的滑块
                else:
                    self._active_slider = 'min' if min_distance < max_distance else 'max'
                
                # 直接将滑块移动到点击位置
                click_value = self._position_to_value(event.pos().x())
                
                if self._active_slider == 'min':
                    self.min_value = max(min(click_value, self.max_value), self.minimum)
                else:
                    self.max_value = min(max(click_value, self.min_value), self.maximum)
                
                self.update()
                self.rangeChanged.emit(self.min_value, self.max_value)
                
                self.setCursor(Qt.SizeHorCursor)  # 设置水平调整光标
                event.accept()
                return
        
        super(RangeSlider, self).mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """鼠标移动事件处理"""
        # 检查是否在滑块上，更新鼠标形状
        min_slider_rect = self._get_min_slider_rect()
        max_slider_rect = self._get_max_slider_rect()
        
        if min_slider_rect.contains(event.pos()) or max_slider_rect.contains(event.pos()):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        # 如果有活动滑块，处理拖动
        if event.buttons() & Qt.LeftButton and self._active_slider:
            new_value = self._position_to_value(event.pos().x())
            
            if self._active_slider == 'min':
                # 最小值滑块不能超过最大值
                self.min_value = max(min(new_value, self.max_value), self.minimum)
            else:
                # 最大值滑块不能小于最小值
                self.max_value = min(max(new_value, self.min_value), self.maximum)
            
            self.update()
            self.rangeChanged.emit(self.min_value, self.max_value)
            event.accept()
            return
            
        super(RangeSlider, self).mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        """鼠标释放事件处理"""
        if event.button() == Qt.LeftButton and self._active_slider:
            # 释放活动滑块
            self._active_slider = None
            # 恢复默认光标
            self.unsetCursor()
            event.accept()
            return
            
        super(RangeSlider, self).mouseReleaseEvent(event)
        
    def enterEvent(self, event):
        """鼠标进入控件事件"""
        super(RangeSlider, self).enterEvent(event)
        
    def leaveEvent(self, event):
        """鼠标离开控件事件"""
        # 恢复默认光标
        self.unsetCursor()
        super(RangeSlider, self).leaveEvent(event)
