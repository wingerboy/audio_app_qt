#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型下载与OSS上传工具

功能：下载Whisper tiny模型并上传到阿里云OSS存储，方便中国用户快速访问

使用方法：
    python model_upload.py --model openai/whisper-tiny

    python backend/model_upload.py --model openai/whisper-base --output-dir /Users/wingerliu/Downloads/windsurf/audio_app_qt/whisper-base --keep-local

环境变量:
    ALIYUN_ACCESS_KEY_ID: 阿里云访问密钥ID
    ALIYUN_ACCESS_KEY_SECRET: 阿里云访问密钥Secret
    DASHSCOPE_API_KEY: 灵积模型API密钥(可选)
"""

import os
import sys
import argparse
import logging
import uuid
import shutil
import tempfile
import time
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ModelDownloader")

def setup_mirror(use_mirror=False):
    """设置国内镜像加速（可选）
    
    Args:
        use_mirror: 是否启用镜像，默认为False
    """
    if use_mirror:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        logger.info("已设置HuggingFace镜像: https://hf-mirror.com")
    else:
        # 清除可能存在的镜像设置
        if "HF_ENDPOINT" in os.environ:
            del os.environ["HF_ENDPOINT"]
        logger.info("直接连接HuggingFace官方服务器")

def download_model(model_name, output_dir=None):
    """
    下载HuggingFace模型
    
    Args:
        model_name: 模型名称，如openai/whisper-tiny
        output_dir: 输出目录，默认使用临时目录
        
    Returns:
        str: 模型下载路径
    """
    try:
        from transformers import AutoConfig, AutoProcessor, AutoModelForSpeechSeq2Seq, AutoTokenizer
        import torch
        
        # 设置输出目录
        if not output_dir:
            output_dir = tempfile.mkdtemp(prefix="model_")
        else:
            output_dir = os.path.join(output_dir, f"{model_name.split('/')[-1]}")
            os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"开始下载模型: {model_name}")
        logger.info(f"模型将保存到: {output_dir}")
        
        # 下载配置
        logger.info("下载模型配置...")
        config = AutoConfig.from_pretrained(model_name)
        config.save_pretrained(output_dir)
        
        # 下载分词器
        logger.info("下载模型分词器...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        tokenizer.save_pretrained(output_dir)
        
        # 下载处理器
        logger.info("下载模型处理器...")
        processor = AutoProcessor.from_pretrained(model_name)
        processor.save_pretrained(output_dir)
        
        # 基于可用设备确定使用的精度
        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        
        # 下载模型
        logger.info(f"下载模型权重...（使用{device}，精度{torch_dtype}）")
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            use_safetensors=True,
            low_cpu_mem_usage=True,
        )
        model.save_pretrained(output_dir)
        
        # 验证所有必要的文件是否存在
        required_files = ["config.json", "tokenizer.json", "preprocessor_config.json"]
        missing_files = [file for file in required_files if not os.path.exists(os.path.join(output_dir, file))]
        
        if missing_files:
            logger.warning(f"警告：模型下载后缺少以下文件: {', '.join(missing_files)}")
            
            # 如果缺少tokenizer.json，尝试从tokenizer_config.json创建
            if "tokenizer.json" in missing_files and os.path.exists(os.path.join(output_dir, "tokenizer_config.json")):
                logger.info("检测到tokenizer_config.json，尝试重新下载tokenizer...")
                try:
                    # 指定特殊参数强制创建tokenizer.json
                    special_tokenizer = AutoTokenizer.from_pretrained(model_name, legacy=False)
                    special_tokenizer.save_pretrained(output_dir)
                    logger.info("成功创建tokenizer.json文件")
                except Exception as tokenizer_err:
                    logger.error(f"创建tokenizer.json失败: {tokenizer_err}")
        
        # 验证模型文件完整性
        model_files = [f for f in os.listdir(output_dir) if f.endswith('.safetensors') or f.endswith('.bin')]
        if not model_files:
            logger.warning("警告: 未检测到模型权重文件，下载可能不完整")
        else:
            logger.info(f"检测到{len(model_files)}个模型权重文件")
            
        logger.info(f"模型下载完成: {model_name}")
        return output_dir
    
    except Exception as e:
        logger.error(f"模型下载失败: {str(e)}")
        raise e

def upload_to_oss(local_path, bucket_name, access_key_id=None, access_key_secret=None):
    """
    将本地模型文件上传到OSS
    
    Args:
        local_path: 本地模型路径
        bucket_name: OSS桶名称
        access_key_id: 阿里云访问密钥ID
        access_key_secret: 阿里云访问密钥Secret
        
    Returns:
        dict: 上传的文件和它们的URL
    """
    try:
        import oss2
        from oss2.credentials import StaticCredentialsProvider
        
        # 获取访问密钥
        access_key_id = "" or os.environ.get("ALIYUN_ACCESS_KEY_ID")
        access_key_secret = "" or os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
        
        if not access_key_id or not access_key_secret:
            raise ValueError("未设置OSS访问密钥，请在环境变量或参数中设置ALIYUN_ACCESS_KEY_ID和ALIYUN_ACCESS_KEY_SECRET")
        
        # 禁用系统代理设置
        original_http_proxy = os.environ.get('http_proxy')
        original_https_proxy = os.environ.get('https_proxy')
        
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        
        endpoint = "https://oss-cn-hangzhou.aliyuncs.com"
        region = "cn-hangzhou"
        
        # 创建凭证提供者
        creds = StaticCredentialsProvider(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret
        )
        
        # 创建认证对象
        auth = oss2.ProviderAuthV4(creds)
        
        # 创建Bucket对象
        bucket = oss2.Bucket(auth, endpoint, bucket_name, connect_timeout=60, region=region)
        
        # 模型目录的基本名称
        model_name = os.path.basename(local_path)
        base_object_name = f"models/{model_name}"
        
        # 上传模型文件
        uploaded_files = {}
        
        logger.info(f"开始上传模型到OSS: {base_object_name}")
        
        # 遍历模型目录中的所有文件
        for root, _, files in os.walk(local_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                # 计算相对路径
                rel_path = os.path.relpath(local_file_path, local_path)
                # 构造OSS对象名
                object_name = f"{base_object_name}/{rel_path}"
                
                # 上传文件
                logger.info(f"上传文件: {rel_path} -> {object_name}")
                result = bucket.put_object_from_file(object_name, local_file_path)
                
                if result.status != 200:
                    logger.error(f"上传失败，状态码: {result.status}")
                    continue
                
                # 生成签名URL，有效期7天
                download_url = bucket.sign_url('GET', object_name, 60 * 60 * 24 * 7)
                
                uploaded_files[rel_path] = download_url
                logger.info(f"文件 {rel_path} 上传成功")
        
        # 还原代理设置
        if original_http_proxy:
            os.environ['http_proxy'] = original_http_proxy
        if original_https_proxy:
            os.environ['https_proxy'] = original_https_proxy
        
        logger.info(f"模型上传完成，共上传 {len(uploaded_files)} 个文件")
        
        return uploaded_files
    
    except Exception as e:
        logger.error(f"上传到OSS失败: {str(e)}")
        raise e

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Whisper模型下载与OSS上传工具')
    parser.add_argument('--model', type=str, default='openai/whisper-tiny', help='模型名称，默认为openai/whisper-tiny')
    parser.add_argument('--output-dir', type=str, help='模型下载的本地输出目录，默认使用临时目录')
    parser.add_argument('--bucket', type=str, default='demo-1743258598-71', help='OSS存储桶名称')
    parser.add_argument('--keep-local', action='store_true', help='保留本地模型文件，默认下载后删除')
    parser.add_argument('--use-mirror', action='store_true', help='使用镜像加速下载，外网服务器无需开启')
    
    args = parser.parse_args()
    
    try:
        # 设置镜像(可选)
        setup_mirror(args.use_mirror)
        
        # 下载模型
        local_model_path = download_model(args.model, args.output_dir)
        
        # 上传到OSS
        uploaded_files = upload_to_oss(local_model_path, args.bucket)
        
        # 输出模型配置文件的URL
        if 'config.json' in uploaded_files:
            logger.info(f"模型配置文件URL: {uploaded_files['config.json']}")

        # 输出所有文件的URL到日志文件
        url_log_path = os.path.join(os.path.dirname(local_model_path), f"{args.model.split('/')[-1]}_urls.txt")
        with open(url_log_path, 'w') as f:
            for file_name, url in uploaded_files.items():
                f.write(f"{file_name}: {url}\n")
        
        logger.info(f"所有文件的URL已保存到: {url_log_path}")
        
        # 清理本地文件（除非指定了保留）
        if not args.keep_local and not args.output_dir:
            logger.info(f"清理临时目录: {local_model_path}")
            shutil.rmtree(local_model_path)
        
        logger.info("模型下载与上传完成")
    
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()