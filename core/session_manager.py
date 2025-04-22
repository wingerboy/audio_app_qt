import json
import requests
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

class SessionManager(QObject):
    """管理用户会话和身份验证"""
    
    # 信号
    sessionChanged = pyqtSignal(bool, str)  # 会话状态改变信号 (已登录, 会话状态消息)
    loginCompleted = pyqtSignal(bool, str)  # 登录完成信号 (成功, 消息)
    
    def __init__(self, api_base_url="http://localhost:5010"):
        super(SessionManager, self).__init__()
        self.api_base_url = api_base_url
        self.session_token = None
        self.user_type = None
        self.expiry_date = None
        self._is_logged_in = False
    
    @property
    def is_logged_in(self):
        return self._is_logged_in
    
    def login(self, card_id, card_key):
        """使用卡密登录"""
        try:
            url = f"{self.api_base_url}/login"
            payload = {
                "card_id": card_id,
                "card_key": card_key
            }
            
            print(f"发送登录请求到: {url}")
            print(f"请求数据: {payload}")
            
            response = requests.post(url, json=payload, timeout=10)
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
            # 检查响应内容是否为空
            if not response.text.strip():
                raise ValueError("服务器返回了空响应")
                
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "success":
                # 登录成功
                self.session_token = data.get("session_token")
                self.user_type = data.get("user_type")
                self.expiry_date = data.get("expires_at")
                self._is_logged_in = True
                
                # 发送信号
                self.sessionChanged.emit(True, f"已登录 ({self.user_type})")
                self.loginCompleted.emit(True, "登录成功")
                return True, "登录成功"
            else:
                # 登录失败
                error_msg = data.get("message", "未知错误")
                self.loginCompleted.emit(False, error_msg)
                return False, error_msg
        
        except requests.exceptions.ConnectionError:
            error_msg = f"连接服务器失败，请检查API端口和服务器是否运行 ({self.api_base_url})"
            print(error_msg)
            self.loginCompleted.emit(False, error_msg)
            return False, error_msg
        except json.JSONDecodeError as e:
            error_msg = f"解析JSON响应失败: {str(e)}, 响应内容: {response.text if 'response' in locals() else '无响应'}"
            print(error_msg)
            self.loginCompleted.emit(False, error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"登录失败: {str(e)}"
            print(f"登录异常: {str(e)}")
            self.loginCompleted.emit(False, error_msg)
            return False, error_msg
    
    def logout(self):
        """注销当前会话"""
        self.session_token = None
        self.user_type = None
        self.expiry_date = None
        self._is_logged_in = False
        self.sessionChanged.emit(False, "未登录")
    
    def validate_action(self, action_id):
        """验证当前会话是否可以执行特定操作"""
        if not self.is_logged_in or not self.session_token:
            return False, "未登录"
        
        try:
            url = f"{self.api_base_url}/validate_action"
            payload = {
                "session_token": self.session_token,
                "action_id": action_id
            }
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                allowed = data.get("allowed", False)
                reason = data.get("reason", "未知原因")
                
                if reason == "session_expired":
                    # 会话已过期，注销
                    self.logout()
                    return False, "会话已过期，请重新登录"
                elif reason == "expired":
                    # 卡密已过期，注销
                    self.logout()
                    return False, "卡密已过期"
                
                return allowed, reason
            else:
                # API调用失败
                return False, data.get("message", "服务器错误")
                
        except Exception as e:
            return False, f"验证操作失败: {str(e)}"
    
    def refresh_token(self):
        """刷新会话令牌"""
        if not self.is_logged_in or not self.session_token:
            return False, "未登录"
        
        try:
            url = f"{self.api_base_url}/refresh_token"
            payload = {"session_token": self.session_token}
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "success":
                # 刷新成功
                self.session_token = data.get("session_token")
                return True, "会话刷新成功"
            else:
                # 刷新失败
                error_msg = data.get("message", "会话刷新失败")
                if "会话无效" in error_msg or "会话已过期" in error_msg:
                    self.logout()
                return False, error_msg
                
        except Exception as e:
            return False, f"会话刷新失败: {str(e)}"
    
    def get_card_info(self):
        """获取当前卡密信息"""
        if not self.is_logged_in or not self.session_token:
            return None
        
        try:
            url = f"{self.api_base_url}/card_info"
            params = {"session_token": self.session_token}
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "success":
                return data.get("card_info")
            else:
                error_msg = data.get("message", "获取卡密信息失败")
                if "会话无效" in error_msg or "会话已过期" in error_msg:
                    self.logout()
                return None
                
        except Exception as e:
            print(f"获取卡密信息失败: {str(e)}")
            return None 