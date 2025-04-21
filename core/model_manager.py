import os
import threading
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
from huggingface_hub import hf_hub_download
from huggingface_hub.constants import HUGGINGFACE_HUB_CACHE
import torch

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
        self.check_all_models()
        
    def get_cache_path(self):
        """获取Hugging Face缓存目录"""
        return HUGGINGFACE_HUB_CACHE
        
    def is_model_downloaded(self, model_name):
        """检查模型是否已经下载"""
        try:
            # 解析模型名称
            repo_id = model_name  # 例如 "openai/whisper-tiny"
            
            # 检查模型文件是否存在
            cache_dir = self.get_cache_path()
            
            # 使用更可靠的方法检查缓存
            # 检查模型配置文件
            config_path = os.path.join(
                cache_dir,
                "models--" + repo_id.replace("/", "--"),
                "snapshots"
            )
            
            if not os.path.exists(config_path):
                return False
                
            # 查找快照目录
            snapshot_dirs = os.listdir(config_path)
            if not snapshot_dirs:
                return False
                
            # 检查快照目录中的配置文件
            latest_snapshot = snapshot_dirs[0]
            config_file = os.path.join(config_path, latest_snapshot, "config.json")
            
            # 如果找到配置文件，则认为模型已下载
            return os.path.exists(config_file)
            
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
        
    def download_model(self, model_name, progress_callback=None):
        """
        下载指定的模型
        
        Args:
            model_name: 要下载的模型名称
            progress_callback: 进度回调函数，接收模型名和进度值(0-100)
        """
        if model_name not in self.available_models:
            if progress_callback:
                progress_callback(model_name, -1, "错误：未知模型")
            return
            
        # 如果已下载，则无需重复下载
        if self.download_status[model_name]["status"] == "downloaded":
            if progress_callback:
                progress_callback(model_name, 100, "已下载")
            return
            
        # 更新状态为下载中
        self.download_status[model_name]["status"] = "downloading"
        
        # 创建后台线程下载模型
        thread = threading.Thread(
            target=self._download_model_thread, 
            args=(model_name, progress_callback)
        )
        thread.daemon = True
        thread.start()
        
    def _download_model_thread(self, model_name, progress_callback=None):
        """后台下载模型的线程"""
        try:
            # 分阶段下载并更新进度
            # 1. 下载配置文件 (10%)
            if progress_callback:
                progress_callback(model_name, 5, "开始下载...")
                
            processor = AutoProcessor.from_pretrained(model_name)
            
            if progress_callback:
                progress_callback(model_name, 30, "下载配置完成，正在下载模型...")
                
            # 2. 下载模型文件 (90%)
            # 根据可用设备决定使用的精度
            device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True
            )
            
            # 下载完成，更新状态
            self.download_status[model_name]["status"] = "downloaded"
            self.download_status[model_name]["progress"] = 100
            
            if progress_callback:
                progress_callback(model_name, 100, "下载完成")
                
        except Exception as e:
            # 下载失败，更新状态
            self.download_status[model_name]["status"] = "failed"
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
                
            if progress_callback:
                progress_callback(model_name, -1, f"下载失败: {error_msg}")
                
            print(f"模型下载失败: {e}")
