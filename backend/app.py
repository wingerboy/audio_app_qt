# backend/app.py
import os
import uuid
import json
import datetime
import time
import logging
import traceback
import pymysql
from pymysql.cursors import DictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps

# 配置日志
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 创建日志记录器
logger = logging.getLogger('api_service')
logger.setLevel(logging.INFO)

# 创建日志文件处理器
log_file = os.path.join(log_dir, f'api_{datetime.datetime.now().strftime("%Y%m%d")}.log')
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器到记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 日志装饰器
def log_api_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        request_id = uuid.uuid4().hex
        client_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        endpoint = request.path
        method = request.method
        request_data = request.json if request.is_json else {}
        # 敏感信息处理
        if 'card_key' in request_data:
            masked_data = request_data.copy()
            masked_data['card_key'] = '******'
        else:
            masked_data = request_data
            
        # 记录请求开始
        logger.info(f"[{request_id}] 开始 {method} {endpoint} - 客户端: {client_ip} - 请求: {masked_data}")
        
        start_time = time.time()
        try:
            # 执行原始函数
            result = func(*args, **kwargs)
            # 记录响应时间和状态
            response_time = round((time.time() - start_time) * 1000, 2)  # 毫秒
            
            # 捕获结果状态
            response_data = json.loads(result.get_data(as_text=True))
            is_success = response_data.get('success', False)
            message = response_data.get('message', '')
            
            log_level = logging.INFO if is_success else logging.WARNING
            logger.log(log_level, f"[{request_id}] 完成 {method} {endpoint} - 耗时: {response_time}ms - 状态: {'成功' if is_success else '失败'} - 消息: {message}")
            
            return result
        except Exception as e:
            # 记录异常
            response_time = round((time.time() - start_time) * 1000, 2)  # 毫秒
            logger.error(f"[{request_id}] 异常 {method} {endpoint} - 耗时: {response_time}ms - 错误: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # 返回错误响应
            return jsonify({"success": False, "message": f"服务器错误: {str(e)}"})
    return wrapper

# 数据库连接配置
DB_CONFIG = {
    'host': 'obmt6nn1aqdr2nb4-mi.aliyun-cn-hangzhou-internet.oceanbase.cloud',
    'port': 3306,
    'user': 'wingerboy',
    'password': 'LI',
    'db': 'audio_app_offline',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

class SessionManager:
    def __init__(self, db_config):
        """初始化会话管理器"""
        self.db_config = db_config
        
    def get_db_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.db_config)
        
    def init_db(self):
        """初始化数据库表结构"""
        logger.info("开始初始化数据库表结构")
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 创建卡密表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                card_id VARCHAR(32) NOT NULL UNIQUE,
                card_key VARCHAR(64) NOT NULL,
                user_type VARCHAR(32) NOT NULL,
                status VARCHAR(16) NOT NULL,
                max_device_count INT DEFAULT 1,
                device_count INT DEFAULT 0,
                validity_days INT DEFAULT 30,
                created_at DATETIME NOT NULL,
                activated_at DATETIME,
                expiry_date DATETIME,
                last_login_at DATETIME,
                INDEX (card_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 创建设备会话表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                card_id VARCHAR(32) NOT NULL,
                device_fingerprint VARCHAR(128) NOT NULL,
                device_name VARCHAR(128),
                hardware_info TEXT,
                session_token VARCHAR(64) NOT NULL,
                is_active BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                last_login_at DATETIME NOT NULL,
                last_ip VARCHAR(64),
                UNIQUE KEY card_device (card_id, device_fingerprint),
                INDEX (session_token),
                INDEX (card_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 创建登录记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                card_id VARCHAR(32) NOT NULL,
                device_fingerprint VARCHAR(128) NOT NULL,
                session_token VARCHAR(64) NOT NULL,
                login_at DATETIME NOT NULL,
                ip_address VARCHAR(64) NOT NULL,
                user_agent TEXT,
                hardware_info TEXT,
                status VARCHAR(16) NOT NULL,
                reason TEXT,
                INDEX (card_id),
                INDEX (login_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 创建API日志表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                request_id VARCHAR(64) NOT NULL,
                endpoint VARCHAR(128) NOT NULL,
                method VARCHAR(16) NOT NULL,
                request_data TEXT,
                response_data TEXT,
                client_ip VARCHAR(64),
                user_agent TEXT,
                status VARCHAR(16) NOT NULL,
                response_time INT,
                created_at DATETIME NOT NULL,
                session_token VARCHAR(64),
                card_id VARCHAR(32),
                INDEX (request_id),
                INDEX (endpoint),
                INDEX (created_at),
                INDEX (card_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 创建测试账号
            self.create_test_accounts(cursor)
            
            conn.commit()
            logger.info("数据库表结构初始化成功")
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库初始化失败: {str(e)}")
            logger.debug(traceback.format_exc())
            raise e
        finally:
            cursor.close()
            conn.close()
            
    def create_test_accounts(self, cursor):
        """创建测试账号"""
        now = datetime.datetime.now()
        expiry_date = now + datetime.timedelta(days=30)  # 30天后过期
        
        # 检查测试账号是否已存在
        cursor.execute("SELECT card_id FROM card_keys WHERE card_id IN ('TEST001', 'TEST002')")
        existing_accounts = [row['card_id'] for row in cursor.fetchall()]
        
        # 添加测试账号1（如果不存在）
        if 'TEST001' not in existing_accounts:
            cursor.execute('''
            INSERT INTO card_keys (card_id, card_key, user_type, status, max_device_count, 
                                  device_count, validity_days, created_at, expiry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                'TEST001', 
                'password123', 
                'premium', 
                'inactive',  # 未激活状态
                1,           # 最多允许1台设备
                0,
                30,          # 有效期30天
                now, 
                expiry_date
            ))
            print("创建测试账号1: TEST001/password123 (Premium, 最大1台设备, 有效期30天)")
        
        # 添加测试账号2（如果不存在）
        if 'TEST002' not in existing_accounts:
            cursor.execute('''
            INSERT INTO card_keys (card_id, card_key, user_type, status, max_device_count, 
                                  device_count, validity_days, created_at, expiry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                'TEST002', 
                'test456', 
                'standard', 
                'inactive',  # 未激活状态
                3,           # 最多允许3台设备
                0,
                60,          # 有效期60天
                now, 
                now + datetime.timedelta(days=60)
            ))
            print("创建测试账号2: TEST002/test456 (Standard, 最大3台设备, 有效期60天)")
    
    def login(self, card_id, card_key, device_info, request_info=None):
        """用户登录处理"""
        # 验证必要的设备信息
        if not device_info or 'device_fingerprint' not in device_info:
            logger.warning(f"登录失败: 设备信息不完整，卡密ID: {card_id}")
            return False, "设备信息不完整，缺少设备唯一标识", None
            
        # 提取设备信息
        device_fingerprint = device_info.get('device_fingerprint')
        device_name = device_info.get('device_name', '未知设备')
        hardware_info = device_info.get('hardware_info', '{}')
        
        # 获取请求信息
        ip_address = request_info.get('ip', '未知IP') if request_info else '未知IP'
        user_agent = request_info.get('user_agent', '未知设备') if request_info else '未知设备'
        
        logger.info(f"尝试登录 - 卡密ID: {card_id}, 设备: {device_name}, IP: {ip_address}")
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 1. 检查卡密是否有效
            cursor.execute(
                "SELECT * FROM card_keys WHERE card_id = %s AND card_key = %s", 
                (card_id, card_key)
            )
            card = cursor.fetchone()
            
            if not card:
                # 记录失败登录
                self._log_login(cursor, card_id, device_fingerprint, "", ip_address, 
                              user_agent, "failed", "卡密无效", hardware_info)
                conn.commit()
                logger.warning(f"登录失败: 卡密无效 - 卡密ID: {card_id}, IP: {ip_address}")
                return False, "卡密无效或密钥错误", None
            
            now = datetime.datetime.now()
            
            # 检查卡密状态
            if card['status'] == 'inactive':
                # 这是首次登录，激活卡密并设置过期时间
                validity_days = card['validity_days']
                expiry_date = now + datetime.timedelta(days=validity_days)
                
                cursor.execute(
                    "UPDATE card_keys SET status = 'active', activated_at = %s, expiry_date = %s WHERE card_id = %s", 
                    (now, expiry_date, card_id)
                )
                
                # 更新本地卡片信息以便后续使用
                card['expiry_date'] = expiry_date
                card['activated_at'] = now
                logger.info(f"卡密首次激活 - 卡密ID: {card_id}, 有效期: {validity_days}天, 过期时间: {expiry_date}")
            elif card['status'] != 'active':
                reason = "卡密已禁用或过期"
                self._log_login(cursor, card_id, device_fingerprint, "", ip_address, 
                              user_agent, "failed", reason, hardware_info)
                conn.commit()
                logger.warning(f"登录失败: {reason} - 卡密ID: {card_id}, 状态: {card['status']}")
                return False, reason, None
                
            # 检查卡密过期时间
            if card['expiry_date'] and card['expiry_date'] < now:
                reason = "卡密已过期"
                self._log_login(cursor, card_id, device_fingerprint, "", ip_address, 
                              user_agent, "failed", reason, hardware_info)
                # 更新卡密状态
                cursor.execute(
                    "UPDATE card_keys SET status = 'expired' WHERE card_id = %s", 
                    (card_id,)
                )
                conn.commit()
                logger.warning(f"登录失败: 卡密已过期 - 卡密ID: {card_id}, 过期时间: {card['expiry_date']}")
                return False, reason, None
            
            # 2. 检查设备绑定情况
            cursor.execute(
                "SELECT * FROM device_sessions WHERE card_id = %s AND device_fingerprint = %s", 
                (card_id, device_fingerprint)
            )
            device_session = cursor.fetchone()
            
            # 3. 检查历史设备数量限制
            max_devices = card['max_device_count']
            if not device_session and card['device_count'] >= max_devices:
                reason = f"该卡密已绑定{max_devices}台设备，已超出最大限制"
                self._log_login(cursor, card_id, device_fingerprint, "", ip_address, 
                              user_agent, "blocked", reason, hardware_info)
                conn.commit()
                logger.warning(f"登录失败: 设备数量限制 - 卡密ID: {card_id}, 当前设备数: {card['device_count']}, 最大限制: {max_devices}")
                return False, reason, None
            
            # 4. 处理登录会话
            session_token = str(uuid.uuid4())
            
            if device_session:
                # 已经绑定过的设备，更新会话
                cursor.execute(
                    """UPDATE device_sessions 
                       SET session_token = %s, is_active = 1, last_login_at = %s, last_ip = %s 
                       WHERE card_id = %s AND device_fingerprint = %s""", 
                    (session_token, now, ip_address, card_id, device_fingerprint)
                )
                logger.info(f"已绑定设备登录 - 卡密ID: {card_id}, 设备: {device_name}")
            else:
                # 新设备，添加会话
                cursor.execute(
                    """INSERT INTO device_sessions 
                       (card_id, device_fingerprint, device_name, hardware_info, 
                        session_token, is_active, created_at, last_login_at, last_ip) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                    (card_id, device_fingerprint, device_name, hardware_info, 
                     session_token, 1, now, now, ip_address)
                )
                
                # 更新卡密设备计数
                cursor.execute(
                    "UPDATE card_keys SET device_count = device_count + 1 WHERE card_id = %s", 
                    (card_id,)
                )
                logger.info(f"新设备绑定 - 卡密ID: {card_id}, 设备: {device_name}, 当前设备数: {card['device_count'] + 1}")
            
            # 使其他设备的会话失效（保证同一时间只有一台设备在线）
            cursor.execute(
                """UPDATE device_sessions 
                   SET is_active = 0 
                   WHERE card_id = %s AND device_fingerprint != %s""", 
                (card_id, device_fingerprint)
            )
            
            # 更新卡密最后登录时间
            cursor.execute(
                "UPDATE card_keys SET last_login_at = %s WHERE card_id = %s", 
                (now, card_id)
            )
            
            # 记录成功登录
            self._log_login(cursor, card_id, device_fingerprint, session_token, 
                          ip_address, user_agent, "success", "", hardware_info)
            
            conn.commit()
            
            # 返回登录结果
            expiry_date = card['expiry_date'].isoformat() if card['expiry_date'] else None
            logger.info(f"登录成功 - 卡密ID: {card_id}, 用户类型: {card['user_type']}, 设备: {device_name}")
            return True, "登录成功", {
                "session_token": session_token,
                "user_type": card['user_type'],
                "expiry_date": expiry_date,
                "max_device_count": max_devices,
                "current_device_count": card['device_count']
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"登录处理异常: {str(e)}")
            logger.debug(traceback.format_exc())
            return False, f"登录处理失败: {str(e)}", None
        finally:
            cursor.close()
            conn.close()
    
    def validate_session(self, session_token):
        """验证会话是否有效"""
        if not session_token:
            return False, "未提供会话令牌", None
            
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 查找会话
            cursor.execute(
                """SELECT ds.*, ck.user_type, ck.expiry_date, ck.status, 
                          ck.max_device_count, ck.device_count
                   FROM device_sessions ds
                   JOIN card_keys ck ON ds.card_id = ck.card_id
                   WHERE ds.session_token = %s AND ds.is_active = 1""", 
                (session_token,)
            )
            session = cursor.fetchone()
            
            if not session:
                return False, "会话无效或已过期", None
                
            # 检查卡密状态
            if session['status'] != 'active':
                return False, "卡密已禁用或过期", None
                
            # 检查过期时间
            now = datetime.datetime.now()
            if session['expiry_date'] and session['expiry_date'] < now:
                # 使会话和卡密失效
                cursor.execute(
                    "UPDATE device_sessions SET is_active = 0 WHERE session_token = %s", 
                    (session_token,)
                )
                cursor.execute(
                    "UPDATE card_keys SET status = 'expired' WHERE card_id = %s", 
                    (session['card_id'],)
                )
                conn.commit()
                return False, "卡密已过期", None
            
            expiry_date = session['expiry_date'].isoformat() if session['expiry_date'] else None
            return True, "会话有效", {
                "card_id": session['card_id'],
                "user_type": session['user_type'],
                "expiry_date": expiry_date,
                "max_device_count": session['max_device_count'],
                "current_device_count": session['device_count'],
                "device_fingerprint": session['device_fingerprint']
            }
            
        except Exception as e:
            print(f"会话验证异常: {str(e)}")
            return False, f"会话验证失败: {str(e)}", None
        finally:
            cursor.close()
            conn.close()
    
    def logout(self, session_token):
        """用户登出处理"""
        if not session_token:
            return False, "未提供会话令牌"
            
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 使会话失效
            cursor.execute(
                "UPDATE device_sessions SET is_active = 0 WHERE session_token = %s", 
                (session_token,)
            )
            
            affected_rows = cursor.rowcount
            conn.commit()
            
            if affected_rows > 0:
                return True, "登出成功"
            else:
                return False, "会话不存在或已失效"
        except Exception as e:
            conn.rollback()
            print(f"登出处理异常: {str(e)}")
            return False, f"登出处理失败: {str(e)}"
        finally:
            cursor.close()
            conn.close()
    
    def get_device_list(self, card_id):
        """获取卡密绑定的设备列表"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 首先获取卡密信息
            cursor.execute(
                "SELECT device_count, max_device_count FROM card_keys WHERE card_id = %s",
                (card_id,)
            )
            card_info = cursor.fetchone()
            
            if not card_info:
                return False, "卡密不存在", None
            
            # 获取设备列表
            cursor.execute(
                """SELECT device_fingerprint, device_name, hardware_info, is_active, 
                          created_at, last_login_at, last_ip 
                   FROM device_sessions 
                   WHERE card_id = %s 
                   ORDER BY last_login_at DESC""", 
                (card_id,)
            )
            devices = cursor.fetchall()
            
            result = []
            for device in devices:
                hardware = "{}"
                try:
                    if device['hardware_info']:
                        hardware = device['hardware_info']
                except:
                    pass
                    
                # 格式化日期时间字段
                created_at = device['created_at'].isoformat() if device['created_at'] else None
                last_login_at = device['last_login_at'].isoformat() if device['last_login_at'] else None
                
                result.append({
                    "device_fingerprint": device['device_fingerprint'],
                    "device_name": device['device_name'],
                    "hardware_info": json.loads(hardware),
                    "is_active": bool(device['is_active']),
                    "first_login_at": created_at,
                    "last_login_at": last_login_at,
                    "last_ip": device['last_ip']
                })
            
            return True, "获取成功", {
                "devices": result,
                "device_count": card_info['device_count'],
                "max_device_count": card_info['max_device_count']
            }
        except Exception as e:
            print(f"获取设备列表异常: {str(e)}")
            return False, f"获取设备列表失败: {str(e)}", None
        finally:
            cursor.close()
            conn.close()
    
    def _log_login(self, cursor, card_id, device_fingerprint, session_token, 
                  ip_address, user_agent, status, reason, hardware_info=None):
        """记录登录活动"""
        now = datetime.datetime.now()
        cursor.execute(
            """INSERT INTO login_history 
               (card_id, device_fingerprint, session_token, login_at, 
                ip_address, user_agent, hardware_info, status, reason) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
            (card_id, device_fingerprint, session_token, now, 
             ip_address, user_agent, hardware_info, status, reason)
        )

    def log_to_db(self, request_id, endpoint, method, request_data, response_data, 
                client_ip, user_agent, status, response_time, session_token=None, card_id=None):
        """将API调用记录到数据库"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            now = datetime.datetime.now()
            
            # 数据处理 - 敏感信息过滤
            if isinstance(request_data, dict) and 'card_key' in request_data:
                masked_request = request_data.copy()
                masked_request['card_key'] = '******'
                request_json = json.dumps(masked_request, ensure_ascii=False)
            else:
                request_json = json.dumps(request_data, ensure_ascii=False) if request_data else None
                
            response_json = json.dumps(response_data, ensure_ascii=False) if response_data else None
            
            # 插入日志记录
            cursor.execute('''
                INSERT INTO api_logs 
                (request_id, endpoint, method, request_data, response_data, 
                 client_ip, user_agent, status, response_time, created_at, 
                 session_token, card_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                request_id, endpoint, method, request_json, response_json,
                client_ip, user_agent, status, response_time, now,
                session_token, card_id
            ))
            
            conn.commit()
        except Exception as e:
            logger.error(f"数据库日志记录失败: {str(e)}")
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 初始化会话管理器
session_manager = SessionManager(DB_CONFIG)

# 日志中间件
@app.before_request
def before_request():
    # 为每个请求生成唯一ID
    request.request_id = uuid.uuid4().hex
    request.start_time = time.time()

@app.after_request
def after_request(response):
    # 计算响应时间
    response_time = round((time.time() - request.start_time) * 1000, 2)  # 毫秒
    
    # 获取请求信息
    request_id = getattr(request, 'request_id', uuid.uuid4().hex)
    endpoint = request.path
    method = request.method
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    # 获取会话信息
    session_token = None
    card_id = None
    if request.is_json:
        data = request.json
        session_token = data.get('session_token')
        card_id = data.get('card_id')
    
    # 获取响应状态
    try:
        response_data = json.loads(response.get_data(as_text=True))
        status = 'success' if response_data.get('success', False) else 'failure'
    except:
        status = 'error'
        response_data = {'message': 'Response parsing error'}
    
    # 记录到数据库
    try:
        request_data = request.json if request.is_json else {}
        session_manager.log_to_db(
            request_id, endpoint, method, request_data, response_data,
            client_ip, user_agent, status, response_time, session_token, card_id
        )
    except Exception as e:
        logger.error(f"日志记录失败: {str(e)}")
    
    return response

# API路由
@app.route('/api/login', methods=['POST'])
@log_api_call
def login():
    data = request.json
    card_id = data.get('card_id')
    card_key = data.get('card_key')
    
    if not card_id or not card_key:
        return jsonify({"success": False, "message": "卡密ID和密钥必须提供"})
    
    # 获取设备信息（从客户端发送）
    device_info = data.get('device_info')
    if not device_info or 'device_fingerprint' not in device_info:
        return jsonify({"success": False, "message": "设备信息不完整"})
    
    # 获取请求信息
    request_info = {
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent')
    }
    
    success, message, session_data = session_manager.login(card_id, card_key, device_info, request_info)
    
    return jsonify({
        "success": success,
        "message": message,
        "data": session_data
    })

@app.route('/api/validate', methods=['POST'])
@log_api_call
def validate_session():
    data = request.json
    session_token = data.get('session_token')
    
    success, message, session_data = session_manager.validate_session(session_token)
    
    return jsonify({
        "success": success,
        "message": message,
        "data": session_data
    })

@app.route('/api/logout', methods=['POST'])
@log_api_call
def logout():
    data = request.json
    session_token = data.get('session_token')
    
    success, message = session_manager.logout(session_token)
    
    return jsonify({
        "success": success,
        "message": message
    })

@app.route('/api/devices', methods=['POST'])
@log_api_call
def get_devices():
    data = request.json
    session_token = data.get('session_token')
    
    # 先验证会话
    success, message, session_data = session_manager.validate_session(session_token)
    
    if not success:
        return jsonify({
            "success": False,
            "message": "无效的会话",
            "data": None
        })
    
    # 获取设备列表
    card_id = session_data['card_id']
    success, message, devices = session_manager.get_device_list(card_id)
    
    return jsonify({
        "success": success,
        "message": message,
        "data": devices
    })

# 只用于测试，生产环境不应该公开此API
@app.route('/api/admin/init_db', methods=['POST'])
@log_api_call
def init_db():
    try:
        session_manager.init_db()
        return jsonify({
            "success": True,
            "message": "数据库初始化成功"
        })
    except Exception as e:
        logger.error(f"通过API初始化数据库失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"数据库初始化失败: {str(e)}"
        })

# 应用启动入口
if __name__ == '__main__':
    logger.info("===== 服务启动 =====")
    # 初始化数据库（可选，也可以通过API单独调用）
    try:
        session_manager.init_db()
    except Exception as e:
        logger.error(f"启动时数据库初始化失败: {str(e)}")
        
    # 启动Flask应用
    logger.info(f"启动Flask应用，监听端口: 5010")
    app.run(debug=True, host='0.0.0.0', port=5010)