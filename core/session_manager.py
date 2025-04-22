import json
import requests
import os
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from core.device_fingerprint import DeviceFingerprint

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
        self.max_device_count = 1
        self.current_device_count = 0
        self._is_logged_in = False
        self.device_fingerprint = None
        self.card_id = None
    
    @property
    def is_logged_in(self):
        return self._is_logged_in
    
    def login(self, card_id, card_key):
        """使用卡密登录"""
        try:
            # 获取设备信息
            if not self.device_fingerprint:
                self.device_fingerprint = DeviceFingerprint.get_device_fingerprint()
                
            device_info = {
                "device_fingerprint": self.device_fingerprint,
                "device_name": DeviceFingerprint.get_device_name(),
                "hardware_info": json.dumps(DeviceFingerprint.get_hardware_info())
            }
            
            url = f"{self.api_base_url}/api/login"
            payload = {
                "card_id": card_id,
                "card_key": card_key,
                "device_info": device_info
            }
            
            print(f"发送登录请求到: {url}")
            print(f"请求数据: {payload}")
            
            response = requests.post(url, json=payload, timeout=10)
            print(f"响应状态码: {response.status_code}")
            
            # 检查响应内容是否为空
            if not response.text.strip():
                raise ValueError("服务器返回了空响应")
                
            data = response.json()
            print(f"响应内容: {data}")
            
            if response.status_code == 200 and data.get("success"):
                # 登录成功
                result_data = data.get("data", {})
                self.session_token = result_data.get("session_token")
                self.user_type = result_data.get("user_type")
                self.expiry_date = result_data.get("expiry_date")
                self.max_device_count = result_data.get("max_device_count", 1)
                self.current_device_count = result_data.get("current_device_count", 0)
                self._is_logged_in = True
                self.card_id = card_id
                
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
        if self.session_token:
            try:
                url = f"{self.api_base_url}/api/logout"
                payload = {"session_token": self.session_token}
                
                response = requests.post(url, json=payload, timeout=10)
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    print("成功登出服务器")
                else:
                    print(f"登出时服务器返回错误: {data.get('message', '未知错误')}")
            except Exception as e:
                print(f"发送登出请求失败: {str(e)}")
        
        self.session_token = None
        self.user_type = None
        self.expiry_date = None
        self.max_device_count = 1
        self.current_device_count = 0
        self.card_id = None
        self._is_logged_in = False
        self.sessionChanged.emit(False, "未登录")
    
    def validate_action(self, action_id):
        """验证当前会话是否可以执行特定操作"""
        if not self.is_logged_in or not self.session_token:
            return False, "未登录"
        
        try:
            url = f"{self.api_base_url}/api/validate"
            payload = {"session_token": self.session_token}
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                if data.get("success"):
                    # 会话有效，根据操作类型检查权限
                    if action_id in ["transcribe", "batch_process", "select_file", "export"] and self.user_type in ["standard", "premium"]:
                        return True, "允许操作"
                    else:
                        return False, f"当前账户类型({self.user_type})不支持此操作"
                else:
                    reason = data.get("message", "会话无效")
                    
                    # 会话已失效，注销
                    self.logout()
                    return False, reason
            else:
                # API调用失败
                return False, data.get("message", "服务器错误")
                
        except Exception as e:
            return False, f"验证操作失败: {str(e)}"
    
    def get_device_list(self):
        """获取当前卡密绑定的设备列表"""
        if not self.is_logged_in or not self.session_token:
            return False, "未登录", None
        
        try:
            url = f"{self.api_base_url}/api/devices"
            payload = {"session_token": self.session_token}
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and data.get("success"):
                return True, "获取成功", data.get("data", {})
            else:
                error_msg = data.get("message", "获取设备列表失败")
                if "无效的会话" in error_msg:
                    self.logout()
                return False, error_msg, None
                
        except Exception as e:
            print(f"获取设备列表失败: {str(e)}")
            return False, f"获取设备列表失败: {str(e)}", None
    
    def save_session(self, session_file="session.json"):
        """保存会话信息到文件"""
        if not self.is_logged_in:
            return False
            
        session_data = {
            "session_token": self.session_token,
            "user_type": self.user_type,
            "expiry_date": self.expiry_date,
            "device_fingerprint": self.device_fingerprint,
            "card_id": self.card_id
        }
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f)
            return True
        except Exception as e:
            print(f"保存会话失败: {str(e)}")
            return False
    
    def load_session(self, session_file="session.json"):
        """从文件加载会话信息"""
        if not os.path.exists(session_file):
            return False
            
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
                
            # 验证会话有效性前先设置设备指纹
            loaded_fingerprint = session_data.get("device_fingerprint")
            current_fingerprint = DeviceFingerprint.get_device_fingerprint()
            
            # 设备指纹必须匹配
            if loaded_fingerprint != current_fingerprint:
                print("加载的会话与当前设备不匹配")
                return False
                
            self.session_token = session_data.get("session_token")
            self.device_fingerprint = loaded_fingerprint
            self.card_id = session_data.get("card_id")
            
            # 验证会话有效性
            url = f"{self.api_base_url}/api/validate"
            payload = {"session_token": self.session_token}
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and data.get("success"):
                # 会话有效
                result_data = data.get("data", {})
                self.user_type = result_data.get("user_type")
                self.expiry_date = result_data.get("expiry_date")
                self.max_device_count = result_data.get("max_device_count", 1)
                self.current_device_count = result_data.get("current_device_count", 0)
                self._is_logged_in = True
                
                # 发送信号
                self.sessionChanged.emit(True, f"已登录 ({self.user_type})")
                return True
            else:
                # 会话无效
                return False
                
        except Exception as e:
            print(f"加载会话失败: {str(e)}")
            return False
    
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