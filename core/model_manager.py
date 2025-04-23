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
        # 确保执行初始检查
        self.check_all_models()
        # 添加调试输出
        for model, status in self.download_status.items():
            print(f"模型 {model} 状态: {status['status']}")
        
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
            # 转换模型名称为缓存路径格式
            model_path = os.path.join(
                cache_dir,
                "models--" + repo_id.replace("/", "--")
            )
            
            # 检查模型目录是否存在
            if not os.path.exists(model_path):
                print(f"模型路径不存在: {model_path}")
                return False
                
            # 检查快照目录
            snapshots_path = os.path.join(model_path, "snapshots")
            if not os.path.exists(snapshots_path):
                print(f"快照路径不存在: {snapshots_path}")
                return False
                
            # 查找快照目录下的子目录
            try:
                snapshot_dirs = [d for d in os.listdir(snapshots_path) if os.path.isdir(os.path.join(snapshots_path, d))]
                if not snapshot_dirs:
                    print(f"没有找到快照子目录: {snapshots_path}")
                    return False
                    
                # 尝试在最新的快照目录中查找重要文件
                # 按字母顺序排序,通常最新的在最后
                snapshot_dirs.sort()
                latest_snapshot = snapshot_dirs[-1]
                snapshot_dir = os.path.join(snapshots_path, latest_snapshot)
                
                # 检查下是否有配置文件
                config_file = os.path.join(snapshot_dir, "config.json")
                
                # 检查下是否有模型文件
                model_files_exist = False
                for root, _, files in os.walk(snapshot_dir):
                    for file in files:
                        if file.endswith(".safetensors") or file.endswith(".bin") or file == "pytorch_model.bin":
                            model_files_exist = True
                            break
                    if model_files_exist:
                        break
                
                is_downloaded = os.path.exists(config_file) and model_files_exist
                
                if is_downloaded:
                    print(f"模型 {model_name} 已下载，找到: {config_file} 和模型文件")
                else:
                    print(f"模型 {model_name} 未完全下载，缺少必要文件")
                    
                return is_downloaded
                
            except Exception as e:
                print(f"检查快照目录出错: {e}")
                return False
                
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
                
            processor = AutoProcessor.from_pretrained(model_name,  mirror="hf-mirror")
            
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
                use_safetensors=True,
                mirror="hf-mirror"
            )
            
            # 强制模型保存到磁盘以确保文件全部下载
            save_dir = os.path.join(self.get_cache_path(), "tmp_verify_save")
            os.makedirs(save_dir, exist_ok=True)
            model.save_pretrained(save_dir)
            
            # 下载完成，再次检查模型是否存在
            download_success = self.is_model_downloaded(model_name)
            
            if download_success:
                # 更新状态
                self.download_status[model_name]["status"] = "downloaded"
                self.download_status[model_name]["progress"] = 100
                
                if progress_callback:
                    progress_callback(model_name, 100, "下载完成")
            else:
                # 下载后检查失败，更新状态为失败
                self.download_status[model_name]["status"] = "failed"
                self.download_status[model_name]["progress"] = -1
                
                if progress_callback:
                    progress_callback(model_name, -1, "下载似乎完成但验证失败")
                    
            # 删除临时目录
            import shutil
            if os.path.exists(save_dir):
                shutil.rmtree(save_dir)
                
        except Exception as e:
            # 下载失败，更新状态
            self.download_status[model_name]["status"] = "failed"
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
                
            if progress_callback:
                progress_callback(model_name, -1, f"下载失败: {error_msg}")
                
            print(f"模型下载失败: {e}")
