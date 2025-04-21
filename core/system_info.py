import os
import subprocess
import platform
import torch
import sys
from pathlib import Path

class SystemInfo:
    """系统环境信息检测类"""
    
    def __init__(self):
        """初始化系统信息检测"""
        self.info = {}
        self.collect_system_info()
    
    def collect_system_info(self):
        """收集系统环境信息"""
        # 操作系统信息
        self.info['os'] = {
            'name': platform.system(),
            'version': platform.version(),
            'architecture': platform.architecture()[0]
        }
        
        # Python信息
        self.info['python'] = {
            'version': platform.python_version(),
            'implementation': platform.python_implementation(),
            'path': sys.executable
        }
        
        # 依赖版本
        self.info['dependencies'] = {
            'pytorch': torch.__version__,
            'cuda_available': torch.cuda.is_available(),
        }
        
        if torch.cuda.is_available():
            self.info['dependencies']['cuda_version'] = torch.version.cuda
            self.info['dependencies']['gpu_count'] = torch.cuda.device_count()
            self.info['dependencies']['gpu_name'] = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "N/A"
        
        # FFmpeg检测
        self.check_ffmpeg()
    
    def check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               timeout=3)
            
            if result.returncode == 0:
                # 提取版本号
                output = result.stdout
                version_line = output.split('\n')[0]
                self.info['ffmpeg'] = {
                    'available': True,
                    'version': version_line,
                    'full_output': output[:200] + ('...' if len(output) > 200 else '')
                }
            else:
                self.info['ffmpeg'] = {
                    'available': False,
                    'error': result.stderr
                }
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.info['ffmpeg'] = {
                'available': False,
                'error': str(e)
            }
    
    def get_info_summary(self):
        """返回简洁的系统信息摘要"""
        summary = []
        
        # 添加操作系统信息
        summary.append(f"操作系统: {self.info['os']['name']} {self.info['os']['version']} {self.info['os']['architecture']}")
        
        # 添加Python信息
        summary.append(f"Python版本: {self.info['python']['version']}")
        
        # 添加PyTorch和CUDA信息
        cuda_status = "可用" if self.info['dependencies']['cuda_available'] else "不可用"
        summary.append(f"PyTorch: {self.info['dependencies']['pytorch']}, CUDA: {cuda_status}")
        
        if self.info['dependencies']['cuda_available']:
            summary.append(f"GPU: {self.info['dependencies']['gpu_name']} (CUDA {self.info['dependencies']['cuda_version']})")
        
        # 添加FFmpeg信息
        if self.info['ffmpeg']['available']:
            version = self.info['ffmpeg']['version'].split(' ')[2] if 'version' in self.info['ffmpeg'] else "未知版本"
            summary.append(f"FFmpeg: 已安装 ({version})")
        else:
            summary.append("FFmpeg: 未安装或无法访问")
        
        return summary
    
    def get_detailed_info(self):
        """返回详细的系统信息"""
        return self.info
    
    def get_status_html(self):
        """返回带有颜色标记的HTML格式的状态信息"""
        html = "<style>span.ok{color:#27ae60;} span.warning{color:#f39c12;} span.error{color:#e74c3c;}</style>"
        html += "<h3>系统环境信息</h3>"
        
        # CUDA状态
        if self.info['dependencies']['cuda_available']:
            cuda_text = f"<span class='ok'>可用</span> (CUDA {self.info['dependencies']['cuda_version']})"
            gpu_text = f"<span class='ok'>{self.info['dependencies']['gpu_name']}</span>"
        else:
            cuda_text = "<span class='warning'>不可用</span> (使用CPU转录将较慢)"
            gpu_text = "<span class='warning'>未检测到</span>"
        
        html += f"<p><b>GPU支持:</b> {cuda_text}</p>"
        html += f"<p><b>GPU型号:</b> {gpu_text}</p>"
        
        # FFmpeg状态
        if self.info['ffmpeg']['available']:
            version = self.info['ffmpeg']['version'].split(' ')[2] if 'version' in self.info['ffmpeg'] else "未知版本"
            ffmpeg_text = f"<span class='ok'>已安装</span> ({version})"
        else:
            ffmpeg_text = "<span class='error'>未安装或无法访问</span> (无法处理视频文件)"
        
        html += f"<p><b>FFmpeg:</b> {ffmpeg_text}</p>"
        
        # PyTorch状态
        html += f"<p><b>PyTorch:</b> {self.info['dependencies']['pytorch']}</p>"
        
        return html
