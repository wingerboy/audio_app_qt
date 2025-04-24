#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSS模型下载工具

功能：从阿里云OSS下载Whisper模型文件到本地目录

使用方法：
    python model_download.py --model whisper-base --output-dir ./models

环境变量:
    ALIYUN_ACCESS_KEY_ID: 阿里云访问密钥ID
    ALIYUN_ACCESS_KEY_SECRET: 阿里云访问密钥Secret
"""

import os
import sys
import argparse
import logging
import shutil
import time
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ModelDownloader")

def get_oss_bucket(bucket_name="demo-1743258598-71", access_key_id=None, access_key_secret=None):
    """
    获取OSS存储桶对象
    
    Args:
        bucket_name: OSS桶名称
        access_key_id: 阿里云访问密钥ID
        access_key_secret: 阿里云访问密钥Secret
        
    Returns:
        Bucket: OSS存储桶对象
    """
    try:
        import oss2
        from oss2.credentials import StaticCredentialsProvider
        
        # 获取访问密钥
        access_key_id = access_key_id or os.environ.get("ALIYUN_ACCESS_KEY_ID")
        access_key_secret = access_key_secret or os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
        
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
        
        # 还原代理设置
        if original_http_proxy:
            os.environ['http_proxy'] = original_http_proxy
        if original_https_proxy:
            os.environ['https_proxy'] = original_https_proxy
        
        return bucket
    
    except Exception as e:
        logger.error(f"获取OSS存储桶失败: {str(e)}")
        raise e

def download_file(bucket, object_name, local_path, chunk_size=8192):
    """
    从OSS下载文件到本地
    
    Args:
        bucket: OSS存储桶对象
        object_name: OSS对象名称
        local_path: 本地文件路径
        chunk_size: 分块下载大小

    Returns:
        bool: 下载是否成功
    """
    import oss2
    
    try:
        # 确保目标目录存在
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # 获取文件元信息，主要是获取文件大小
        file_info = bucket.get_object_meta(object_name)
        total_size = file_info.content_length
        
        # 记录开始时间，用于计算下载速度
        start_time = time.time()
        
        # 创建进度条
        logger.info(f"开始下载: {object_name} -> {local_path}")
        logger.info(f"文件大小: {total_size / 1024 / 1024:.2f} MB")
        
        # 通过分块读取来下载大文件
        with open(local_path, 'wb') as local_file:
            # 使用get_object获取OSS对象
            object_stream = bucket.get_object(object_name)
            
            # 记录已下载的字节数
            downloaded = 0
            last_log_time = start_time
            
            # 读取数据
            while True:
                chunk = object_stream.read(chunk_size)
                if not chunk:
                    break
                
                local_file.write(chunk)
                downloaded += len(chunk)
                
                # 计算下载进度和速度，每秒更新一次
                now = time.time()
                if now - last_log_time >= 1:
                    percent = 100.0 * downloaded / total_size if total_size > 0 else 0
                    speed = downloaded / (now - start_time) / 1024  # KB/s
                    
                    logger.info(f"下载进度: {percent:.1f}% ({downloaded}/{total_size} 字节), 速度: {speed:.1f} KB/s")
                    last_log_time = now
        
        # 计算总下载时间和平均速度
        download_time = time.time() - start_time
        avg_speed = total_size / download_time / 1024 if download_time > 0 else 0
        
        logger.info(f"文件下载完成: {object_name}")
        logger.info(f"总时间: {download_time:.1f} 秒, 平均速度: {avg_speed:.1f} KB/s")
        
        return True
    
    except oss2.exceptions.NoSuchKey:
        logger.error(f"OSS对象不存在: {object_name}")
        return False
    except oss2.exceptions.OssError as e:
        logger.error(f"OSS下载错误: {e}")
        return False
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        return False

def list_model_files(bucket, model_name):
    """
    列出OSS上模型的所有文件
    
    Args:
        bucket: OSS存储桶对象
        model_name: 模型名称，如whisper-base
        
    Returns:
        list: 模型文件列表
    """
    prefix = f"models/{model_name}/"
    
    try:
        # 列出符合前缀的所有文件
        logger.info(f"正在列出模型文件: {prefix}")
        
        all_files = []
        next_marker = ""
        
        while True:
            result = bucket.list_objects(prefix=prefix, marker=next_marker, max_keys=100)
            
            for obj in result.object_list:
                if obj.key != prefix:  # 排除目录本身
                    all_files.append(obj.key)
            
            # 如果列举完毕，则退出循环
            if result.is_truncated:
                next_marker = result.next_marker
            else:
                break
        
        logger.info(f"共找到 {len(all_files)} 个模型文件")
        return all_files
    
    except Exception as e:
        logger.error(f"列出模型文件失败: {str(e)}")
        raise e

def download_model_from_oss(model_name, output_dir, bucket_name="demo-1743258598-71"):
    """
    从OSS下载整个模型
    
    Args:
        model_name: 模型名称，如whisper-base
        output_dir: 输出目录
        bucket_name: OSS桶名称
        
    Returns:
        str: 模型下载路径
    """
    try:
        # 获取OSS存储桶
        bucket = get_oss_bucket(bucket_name)
        
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 列出模型文件
        model_files = list_model_files(bucket, model_name)
        
        if not model_files:
            logger.error(f"未找到模型文件: {model_name}")
            return None
        
        # 创建模型目录
        model_dir = os.path.join(output_dir, model_name)
        os.makedirs(model_dir, exist_ok=True)
        
        # 下载文件
        success_count = 0
        for file_path in model_files:
            # 计算本地文件路径，需要移除前缀
            rel_path = file_path.replace(f"models/{model_name}/", "")
            local_path = os.path.join(model_dir, rel_path)
            
            # 下载文件
            if download_file(bucket, file_path, local_path):
                success_count += 1
        
        logger.info(f"模型下载完成: {model_name}")
        logger.info(f"成功下载 {success_count}/{len(model_files)} 个文件")
        
        return model_dir
    
    except Exception as e:
        logger.error(f"从OSS下载模型失败: {str(e)}")
        raise e

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='从OSS下载Whisper模型工具')
    parser.add_argument('--model', type=str, default='whisper-base', help='模型名称，默认为whisper-base')
    parser.add_argument('--output-dir', type=str, default='./openai', help='输出目录，默认为./openai')
    parser.add_argument('--bucket', type=str, default='demo-1743258598-71', help='OSS存储桶名称')
    
    args = parser.parse_args()
    
    try:
        # 下载模型
        model_dir = download_model_from_oss(
            model_name=args.model,
            output_dir=args.output_dir,
            bucket_name=args.bucket
        )
        
        if model_dir:
            logger.info(f"模型已下载到: {model_dir}")
            # 将模型目录移动到openai/whisper-base/
            target_dir = os.path.join(args.output_dir, args.model)
            if os.path.exists(target_dir) and target_dir != model_dir:
                shutil.rmtree(target_dir)
            
            logger.info(f"模型下载成功: {target_dir}")
        else:
            logger.error("模型下载失败")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
