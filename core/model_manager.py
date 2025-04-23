import os
import threading
import sys
import subprocess
import logging
import shutil
import time
from pathlib import Path
import queue

from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, AutoTokenizer, AutoConfig
import torch

# OSS相关配置
OSS_BUCKET_NAME = "demo-1743258598-71"  # 默认OSS桶名称
OSS_ENDPOINT = "oss-cn-hangzhou.aliyuncs.com"  # OSS endpoint，请根据实际情况修改
MODEL_BASE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "whisper_models")  # 本地模型缓存目录
if not os.path.exists(MODEL_BASE_DIR):
    os.makedirs(MODEL_BASE_DIR, exist_ok=True)

try:
    import oss2  # 导入阿里云OSS SDK
except ImportError:
    print("警告: 未安装oss2库，无法使用OSS下载功能。请使用pip安装: pip install oss2")

class ModelManager:
    """Whisper模型管理类，用于检查和下载模型"""
    
    def __init__(self):
        self.available_models = [
            "openai/whisper-tiny",
            "openai/whisper-base",
            "openai/whisper-small", 
            "openai/whisper-medium",
            "openai/whisper-large"
        ]
        # 存储下载状态的字典
        self.download_status = {model: {"status": "unchecked", "progress": 0} for model in self.available_models}
        
        # 保存对象引用，防止垃圾回收
        self.download_threads = {}
        
        # 进度更新队列 - 用于避免直接从线程中更新UI
        self.progress_queue = queue.Queue()
        
        # 确保执行初始检查
        self.check_all_models()
        # 添加调试输出
        for model, status in self.download_status.items():
            print(f"模型 {model} 状态: {status['status']}")
        
    def get_cache_path(self):
        """获取模型缓存目录"""
        return MODEL_BASE_DIR
        
    def get_model_path(self, model_name):
        """
        获取模型的本地路径
        
        Args:
            model_name: 模型名称，如'openai/whisper-tiny'
            
        Returns:
            str: 模型的本地路径
        """
        # 提取模型名称部分，去掉组织名
        model_id = model_name.split("/")[-1] if "/" in model_name else model_name
        
        # 首先检查默认缓存目录
        cache_path = os.path.join(self.get_cache_path(), model_id)
        if os.path.exists(cache_path):
            return cache_path
            
        # 然后检查用户可能放置模型的本地路径
        local_paths = [
            # openai目录下的模型路径
            os.path.join("openai", model_id),
            # 当前目录下的openai目录
            os.path.join(os.getcwd(), "openai", model_id),
            # 上级目录的openai目录
            os.path.join(os.path.dirname(os.getcwd()), "openai", model_id),
        ]
        
        # 检查是否存在任一路径
        for path in local_paths:
            if os.path.exists(path):
                print(f"在本地找到模型: {path}")
                return path
                
        # 默认返回缓存目录的路径
        return cache_path
        
    def is_model_downloaded(self, model_name):
        """检查模型是否已经下载"""
        try:
            # 获取模型的本地路径
            model_path = self.get_model_path(model_name)
            
            # 检查模型目录是否存在
            if not os.path.exists(model_path):
                print(f"模型路径不存在: {model_path}")
                return False
            
            # 检查必要的模型文件
            required_files = ["config.json", "tokenizer.json", "preprocessor_config.json"]
            missing_files = []
            for file in required_files:
                if not os.path.exists(os.path.join(model_path, file)):
                    print(f"模型缺少必要文件: {file}")
                    missing_files.append(file)
            
            if missing_files:
                print(f"模型目录存在但缺少文件: {', '.join(missing_files)}")
                return False
            
            # 检查模型权重文件（.bin或.safetensors）
            model_files_exist = False
            for root, _, files in os.walk(model_path):
                for file in files:
                    if file.endswith(".safetensors") or file.endswith(".bin") or file == "pytorch_model.bin":
                        model_files_exist = True
                        break
                if model_files_exist:
                    break
            
            if not model_files_exist:
                print(f"模型缺少权重文件")
                return False
            
            print(f"模型 {model_name} 已下载到: {model_path}")
            return True
                
        except Exception as e:
            print(f"检查模型下载状态出错: {e}")
            return False
            
    def check_all_models(self):
        """检查所有可用模型的下载状态"""
        for model in self.available_models:
            downloaded = self.is_model_downloaded(model)
            self.download_status[model]["status"] = "downloaded" if downloaded else "not_downloaded"
            self.download_status[model]["progress"] = 100 if downloaded else 0
            
    def get_model_status(self, model_name):
        """获取模型下载状态"""
        if model_name in self.download_status:
            return self.download_status[model_name]
        return {"status": "unknown", "progress": 0}
    
    def process_progress_updates(self):
        """处理队列中的进度更新，应在主线程中调用"""
        try:
            while not self.progress_queue.empty():
                # 非阻塞方式获取队列项
                model_name, progress, message, callback = self.progress_queue.get_nowait()
                if callback:
                    try:
                        callback(model_name, progress, message)
                    except Exception as e:
                        print(f"主线程回调错误: {e}")
                self.progress_queue.task_done()
        except Exception as e:
            print(f"处理进度更新错误: {e}")
    
    def download_model(self, model_name, progress_callback=None):
        """
        下载指定的模型
        
        Args:
            model_name: 要下载的模型名称
            progress_callback: 进度回调函数，接收模型名和进度值(0-100)
        """
        if model_name not in self.available_models:
            # 将更新放入队列，而不是直接调用
            if progress_callback:
                self.progress_queue.put((model_name, -1, "错误：未知模型", progress_callback))
            return
            
        # 如果已下载，则无需重复下载
        if self.download_status[model_name]["status"] == "downloaded":
            # 将更新放入队列，而不是直接调用
            if progress_callback:
                self.progress_queue.put((model_name, 100, "已下载", progress_callback))
            return
            
        # 更新状态为下载中
        self.download_status[model_name]["status"] = "downloading"
        
        # 创建后台线程下载模型
        thread = threading.Thread(
            target=self._download_model_thread, 
            args=(model_name, progress_callback)
        )
        thread.daemon = True
        
        # 保存线程引用以防止垃圾回收
        self.download_threads[model_name] = thread
        
        thread.start()
        
    def _safe_callback(self, callback, model_name, progress, message):
        """安全地调用回调函数，将回调放入队列，而不是直接调用"""
        if callback:
            try:
                # 将更新添加到队列，而不是直接调用回调函数
                self.progress_queue.put((model_name, progress, message, callback))
            except Exception as e:
                print(f"添加到进度队列失败: {e}")
        
    def _download_model_thread(self, model_name, progress_callback=None):
        """后台下载模型的线程"""
        try:
            # 更新进度状态
            self._safe_callback(progress_callback, model_name, 5, "开始下载...")
            
            # 获取模型ID（去掉前缀）
            model_id = model_name.split("/")[-1] if "/" in model_name else model_name
            
            # 目标模型目录
            output_dir = os.path.join(self.get_cache_path(), model_id)
            os.makedirs(output_dir, exist_ok=True)
            
            print(f"开始从OSS下载模型: {model_id}")
            
            # 尝试导入OSS2库
            try:
                import oss2
            except ImportError:
                raise ImportError("未安装oss2库，无法使用OSS下载功能。请使用pip安装: pip install oss2")
            
            # 初始化OSS客户端
            # 注意：这里使用了环境变量或配置文件中的访问凭证
            # 在实际应用中，应从安全的位置读取这些凭证
            access_key_id = ""
            access_key_secret = ""
            
            if not access_key_id or not access_key_secret:
                # 尝试从配置文件读取
                config_file = os.path.join(os.path.expanduser("~"), ".ossconfig")
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        config_lines = f.readlines()
                        for line in config_lines:
                            if "access_key_id" in line:
                                access_key_id = line.split("=")[1].strip()
                            if "access_key_secret" in line:
                                access_key_secret = line.split("=")[1].strip()
                
            if not access_key_id or not access_key_secret:
                raise ValueError("未找到OSS访问凭证，请设置OSS_ACCESS_KEY_ID和OSS_ACCESS_KEY_SECRET环境变量或创建~/.ossconfig配置文件")
            
            # 设置下载进度
            self._safe_callback(progress_callback, model_name, 10, "连接到OSS服务器...")
            
            # 创建认证对象
            auth = oss2.Auth(access_key_id, access_key_secret)
            
            # 创建存储桶对象
            bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
            
            # 模型在OSS上的前缀
            prefix = f"models/{model_id}/"
            
            # 列出所有需要下载的文件
            objects = []
            for obj in oss2.ObjectIterator(bucket, prefix=prefix):
                if not obj.key.endswith('/'):  # 跳过目录
                    objects.append(obj.key)
            
            if not objects:
                raise FileNotFoundError(f"服务器OSS未找到模型文件: {prefix}")
            
            file_count = len(objects)
            print(f"共找到{file_count}个模型文件")
            
            self._safe_callback(progress_callback, model_name, 15, f"开始下载({file_count}个文件)...")
            
            # 下载每个文件
            files_downloaded = 0
            for obj_key in objects:
                # 提取相对路径
                rel_path = obj_key[len(prefix):]
                local_file_path = os.path.join(output_dir, rel_path)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                
                # 获取文件大小
                object_meta = bucket.head_object(obj_key)
                file_size = object_meta.content_length
                
                # 创建进度回调
                def percentage(consumed_bytes, total_bytes):
                    if total_bytes:
                        rate = int(100 * (consumed_bytes / total_bytes))
                        sys.stdout.write(f'\r{rel_path} 下载进度: {rate}%')
                        sys.stdout.flush()
                
                # 下载文件
                print(f"下载: {obj_key} -> {local_file_path}")
                bucket.get_object_to_file(obj_key, local_file_path, progress_callback=percentage)
                print(f"\n文件下载完成: {rel_path}")
                
                files_downloaded += 1
                if file_count > 0:
                    # 计算当前进度（15% - 90%范围内）
                    progress = 15 + int(75 * files_downloaded / file_count)
                    
                    # 每处理3个文件或最后一个文件时更新进度，避免频繁更新UI
                    if files_downloaded % 3 == 0 or files_downloaded == file_count:
                        self._safe_callback(progress_callback, model_name, 
                                           progress, 
                                           f"下载中...{files_downloaded}/{file_count}")
            
            print("模型下载成功")
            
            # 下载完成前先发送进度更新
            self._safe_callback(progress_callback, model_name, 95, "完成下载，检查模型...")
            
            # 睡眠一小段时间确保进度队列被处理
            time.sleep(0.1)
            
            # 下载完成，验证模型文件
            download_success = self.is_model_downloaded(model_name)
            
            if download_success:
                # 更新状态
                self.download_status[model_name]["status"] = "downloaded"
                self.download_status[model_name]["progress"] = 100
                
                # 睡眠一小段时间确保进度队列被处理
                time.sleep(0.1)
                
                self._safe_callback(progress_callback, model_name, 100, "下载完成")
                    
                print(f"模型 {model_name} 下载成功")
            else:
                # 下载后验证失败
                self.download_status[model_name]["status"] = "failed"
                error_msg = "模型下载成功但验证失败，文件可能不完整"
                print(error_msg)
                
                # 睡眠一小段时间确保进度队列被处理
                time.sleep(0.1)
                
                self._safe_callback(progress_callback, model_name, -1, error_msg)
                
        except Exception as e:
            # 下载失败，更新状态
            self.download_status[model_name]["status"] = "failed"
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            
            # 睡眠一小段时间确保进度队列被处理
            time.sleep(0.1)  
                
            self._safe_callback(progress_callback, model_name, -1, f"下载失败: {error_msg}")
                
            print(f"模型下载失败: {e}")
            
        finally:
            # 删除线程引用
            if model_name in self.download_threads:
                del self.download_threads[model_name]
