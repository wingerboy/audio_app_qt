import os
import subprocess
import tempfile
from pydub import AudioSegment
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

class AudioProcessor:
    def __init__(self, use_disk_processing=True, chunk_size_mb=200, max_workers=2):
        """
        初始化音频处理器
        
        Args:
            use_disk_processing (bool): 是否使用硬盘处理大文件
            chunk_size_mb (int): 处理大文件时的分块大小(MB)
            max_workers (int): 并行处理的最大线程数
        """
        self.temp_dir = tempfile.mkdtemp()
        self.use_disk_processing = use_disk_processing
        self.chunk_size_mb = chunk_size_mb
        self.max_workers = max_workers
        self._check_ffmpeg()
        
        # 记录大文件处理配置
        print(f"AudioProcessor初始化: 硬盘处理={use_disk_processing}, 分块大小={chunk_size_mb}MB, 最大线程数={max_workers}")
    
    def _check_ffmpeg(self):
        """Check if FFmpeg is installed and accessible by pydub"""
        # 尝试设置ffmpeg路径
        self.has_ffmpeg = False
        try:
            # 尝试使用subprocess检测ffmpeg
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=False)
            self.has_ffmpeg = True
        except (FileNotFoundError, subprocess.SubprocessError):
            # 尝试为pydub设置ffmpeg路径
            try:
                # 查找可能的ffmpeg路径
                possible_paths = [
                    "ffmpeg",
                    r"C:\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
                    os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe"),
                    os.path.join(os.path.expanduser("~"), "ffmpeg", "ffmpeg.exe"),
                    # 添加更多可能的路径
                    os.path.join(os.path.expanduser("~"), "ffmpeg", "bin", "ffmpeg.exe"),
                    r"C:\Users\Administrator\ffmpeg\ffmpeg.exe",
                    r"C:\Users\Administrator\ffmpeg\bin\ffmpeg.exe"
                ]
                
                for path in possible_paths:
                    try:
                        if os.path.exists(path):
                            AudioSegment.converter = path
                            self.has_ffmpeg = True
                            break
                    except:
                        continue
            except:
                pass

    def extract_audio(self, file_path, progress_callback=None):
        """
        Extract audio from video file or copy audio file
        
        Args:
            file_path (str): Path to the input file
            progress_callback (function): Optional callback function to report progress
        
        Returns:
            str: Path to the extracted audio file
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        output_path = os.path.join(self.temp_dir, f"extracted_audio.mp3")
        
        # 更新支持的扩展名列表
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.3gp', '.m4v', '.ts', '.mts', '.vob']
        audio_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus']
        
        # 报告进度
        if progress_callback:
            progress_callback("开始提取音频...", 5)
        
        try:
            if file_ext in video_extensions:
                # 视频文件需要ffmpeg
                if not self.has_ffmpeg:
                    raise Exception("处理视频需要安装FFmpeg，请安装后重试")
                
                # 对于大文件，直接使用subprocess调用ffmpeg更高效
                try:
                    if progress_callback:
                        progress_callback("正在从视频中提取音频...", 10)
                    
                    # 使用更高效的ffmpeg命令处理大文件
                    cmd = [
                        "ffmpeg", "-i", file_path, 
                        "-vn",  # 去除视频流
                        "-acodec", "libmp3lame",  # 使用MP3编码器
                        "-ab", "192k",  # 比特率
                        "-ar", "44100",  # 采样率
                        "-ac", "2",  # 双声道
                        "-f", "mp3",  # 强制输出格式
                        "-y",  # 覆盖现有文件
                        output_path
                    ]
                    
                    # 对于大文件，使用subprocess.Popen来监控进度
                    process = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        universal_newlines=True
                    )
                    
                    # 每秒检查进度并报告
                    while process.poll() is None:
                        if progress_callback:
                            progress_callback("正在从视频中提取音频...", 15)
                        time.sleep(1)
                    
                    # 检查进程是否成功
                    if process.returncode != 0:
                        _, stderr = process.communicate()
                        raise Exception(f"FFmpeg执行失败: {stderr}")
                    
                    if progress_callback:
                        progress_callback("音频提取完成", 20)
                
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    # 如果subprocess调用失败，报告错误并尝试使用pydub
                    print(f"FFmpeg子进程失败: {str(e)}，尝试使用pydub...")
                    
                    if progress_callback:
                        progress_callback("正在使用备用方法提取音频...", 15)
                    
                    # 尝试使用pydub作为备选
                    try:
                        audio = AudioSegment.from_file(file_path)
                        audio.export(output_path, format="mp3")
                    except Exception as pydub_error:
                        raise Exception(f"音频提取失败: FFmpeg失败，Pydub也失败 - {str(pydub_error)}")
            
            elif file_ext in audio_extensions:
                # 对于音频文件，尝试直接复制或转换
                if progress_callback:
                    progress_callback("处理音频文件...", 10)
                
                if file_ext == '.mp3':
                    # 如果已经是mp3，直接复制
                    shutil.copy(file_path, output_path)
                    if progress_callback:
                        progress_callback("音频文件复制完成", 20)
                else:
                    # 否则转换为mp3
                    try:
                        if progress_callback:
                            progress_callback("转换音频格式...", 15)
                        
                        # 对于大文件，尝试使用ffmpeg命令行
                        if self.has_ffmpeg:
                            cmd = [
                                "ffmpeg", "-i", file_path, 
                                "-acodec", "libmp3lame", 
                                "-ab", "192k", "-ar", "44100",
                                "-y", output_path
                            ]
                            subprocess.run(cmd, check=True, capture_output=True)
                        else:
                            # 使用pydub
                            audio = AudioSegment.from_file(file_path)
                            audio.export(output_path, format="mp3")
                        
                        if progress_callback:
                            progress_callback("音频转换完成", 20)
                    except Exception as e:
                        raise Exception(f"音频转换失败: {str(e)}")
            else:
                raise Exception(f"不支持的文件格式: {file_ext}")
            
            return output_path
        except Exception as e:
            raise Exception(f"音频处理失败: {str(e)}")
    
    def split_audio(self, audio_path, segments, output_dir=None, file_prefix="segment", output_format="mp3", bitrate="192k", progress_callback=None):
        """
        Split audio based on segments and output format preferences
        
        Args:
            audio_path (str): Path to the audio file
            segments (list): List of segment dictionaries with start and end times
            output_dir (str): Directory to output files (optional)
            file_prefix (str): Prefix for output files
            output_format (str): Output audio format
            bitrate (str): Output audio bitrate
            progress_callback (function): Optional callback function to report progress
        
        Returns:
            list: Paths to the output files
        """
        try:
            # 确定输出目录
            if output_dir and os.path.isdir(output_dir):
                # 使用用户指定的输出目录
                output_folder = output_dir
            else:
                # 使用临时目录作为默认输出
                output_folder = os.path.join(self.temp_dir, "output")
                os.makedirs(output_folder, exist_ok=True)
            
            # 如果没有片段，返回空列表
            if not segments:
                return []
                
            # 验证输出格式
            valid_formats = ["mp3", "wav", "ogg", "flac", "m4a"]
            if output_format not in valid_formats:
                output_format = "mp3"  # 默认为mp3
            
            # 验证比特率
            valid_bitrates = ["96k", "128k", "192k", "256k", "320k"]
            if not any(bitrate in valid_bit for valid_bit in valid_bitrates):
                bitrate = "192k"  # 默认为192k
            
            # 报告进度
            if progress_callback:
                progress_callback("准备分割音频...", 70)
            
            # 检查文件大小
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            is_large_file = file_size_mb > self.chunk_size_mb
            
            # 对于大文件，根据设置决定处理方式
            if is_large_file:
                if progress_callback:
                    progress_callback(f"检测到大文件 ({file_size_mb:.2f} MB)", 71)
                
                # 如果启用硬盘处理或者文件非常大，使用ffmpeg直接处理
                if self.use_disk_processing or file_size_mb > 500:
                    if self.has_ffmpeg:
                        if progress_callback:
                            progress_callback("使用硬盘处理大文件...", 72)
                        return self._split_large_audio_with_ffmpeg(
                            audio_path, segments, output_folder, file_prefix, 
                            output_format, bitrate, progress_callback
                        )
                    else:
                        if progress_callback:
                            progress_callback("未检测到FFmpeg，尝试使用内存处理...", 72)
            
            # 对于较小的文件或未启用硬盘处理，使用pydub加载到内存
            try:
                if progress_callback:
                    progress_callback("加载音频文件...", 75)
                
                audio = AudioSegment.from_file(audio_path)
                
                if progress_callback:
                    progress_callback("音频加载完成，开始分割...", 80)
            except Exception as e:
                # 如果内存加载失败，尝试使用ffmpeg
                if self.has_ffmpeg:
                    if progress_callback:
                        progress_callback(f"内存加载失败: {str(e)}，尝试使用硬盘处理...", 75)
                    return self._split_large_audio_with_ffmpeg(
                        audio_path, segments, output_folder, file_prefix, 
                        output_format, bitrate, progress_callback
                    )
                else:
                    raise Exception(f"无法加载音频文件: {str(e)}，且未安装FFmpeg")
            
            # 是否使用并行处理
            use_parallel = self.max_workers > 1 and len(segments) > 4
            
            if use_parallel and progress_callback:
                progress_callback(f"使用{self.max_workers}个线程并行处理{len(segments)}个片段...", 80)
            
            output_files = []
            
            if use_parallel:
                # 并行处理片段
                segment_results = []
                
                def process_segment(idx_segment):
                    idx, segment = idx_segment
                    try:
                        start_ms = int(segment.get('start', 0) * 1000)
                        end_ms = int(segment.get('end', 0) * 1000)
                        
                        # 确保时间范围有效
                        if start_ms >= end_ms or start_ms < 0:
                            return None
                        
                        if end_ms > len(audio):
                            end_ms = len(audio)
                        
                        # Extract segment
                        audio_segment = audio[start_ms:end_ms]
                        
                        # 确保片段至少有100毫秒
                        if len(audio_segment) < 100:
                            return None
                        
                        # 根据输出格式设置输出参数
                        output_params = {
                            "format": output_format,
                        }
                        
                        # 根据格式设置编码器和比特率
                        if output_format == "mp3":
                            output_params["bitrate"] = bitrate
                            output_params["codec"] = "libmp3lame"
                        elif output_format == "ogg":
                            output_params["bitrate"] = bitrate
                            output_params["codec"] = "libvorbis"
                        elif output_format == "m4a":
                            output_params["bitrate"] = bitrate
                            output_params["codec"] = "aac"
                        
                        # Save segment
                        output_file = os.path.join(output_folder, f"{file_prefix}_{idx+1}.{output_format}")
                        audio_segment.export(output_file, **output_params)
                        
                        return output_file
                    except Exception as e:
                        print(f"警告：并行处理片段 {idx+1} 失败: {str(e)}")
                        return None
                
                # 创建线程池
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # 提交所有任务
                    futures = list(executor.map(process_segment, enumerate(segments)))
                    
                    # 收集结果
                    for i, result in enumerate(futures):
                        if result:
                            output_files.append(result)
                        
                        if progress_callback:
                            progress_percent = 80 + int((i / len(segments)) * 20)
                            progress_callback(f"已处理 {i+1}/{len(segments)} 个片段...", progress_percent)
            
            else:
                # 串行处理片段
                total_segments = len(segments)
                
                # Split audio based on segments
                for i, segment in enumerate(segments):
                    try:
                        # 更新进度
                        if progress_callback:
                            progress_percent = 80 + int((i / total_segments) * 20)
                            progress_callback(f"正在处理片段 {i+1}/{total_segments}...", progress_percent)
                        
                        start_ms = int(segment.get('start', 0) * 1000)
                        end_ms = int(segment.get('end', 0) * 1000)
                        
                        # 确保时间范围有效
                        if start_ms >= end_ms or start_ms < 0:
                            continue
                        
                        if end_ms > len(audio):
                            end_ms = len(audio)
                        
                        # Extract segment
                        audio_segment = audio[start_ms:end_ms]
                        
                        # 确保片段至少有100毫秒
                        if len(audio_segment) < 100:
                            continue
                        
                        # 根据输出格式设置输出参数
                        output_params = {
                            "format": output_format,
                        }
                        
                        # 根据格式设置编码器和比特率
                        if output_format == "mp3":
                            output_params["bitrate"] = bitrate
                            output_params["codec"] = "libmp3lame"
                        elif output_format == "ogg":
                            output_params["bitrate"] = bitrate
                            output_params["codec"] = "libvorbis"
                        elif output_format == "m4a":
                            output_params["bitrate"] = bitrate
                            output_params["codec"] = "aac"
                        
                        # Save segment
                        output_file = os.path.join(output_folder, f"{file_prefix}_{i+1}.{output_format}")
                        audio_segment.export(output_file, **output_params)
                        
                        output_files.append(output_file)
                    except Exception as e:
                        # 跳过有问题的片段，继续处理其他片段
                        print(f"警告：片段 {i+1} 处理失败: {str(e)}")
                        continue
            
            if progress_callback:
                progress_callback("音频分割完成", 100)
                
            return output_files
        
        except Exception as e:
            raise Exception(f"音频分割失败: {str(e)}")
    
    def _split_large_audio_with_ffmpeg(self, audio_path, segments, output_folder, file_prefix, output_format, bitrate, progress_callback=None):
        """使用ffmpeg直接分割大音频文件，不加载到内存"""
        if progress_callback:
            progress_callback("使用FFmpeg直接分割大文件...", 75)
        
        output_files = []
        total_segments = len(segments)
        
        # 获取更好的编码器映射
        codec_map = {
            "mp3": "libmp3lame",
            "ogg": "libvorbis",
            "wav": "pcm_s16le",
            "flac": "flac",
            "m4a": "aac"
        }
        
        codec = codec_map.get(output_format, "libmp3lame")
        
        # 是否使用并行处理
        use_parallel = self.max_workers > 1 and total_segments > 4
        
        if use_parallel:
            if progress_callback:
                progress_callback(f"使用{self.max_workers}个线程并行处理{total_segments}个片段...", 76)
            
            def process_segment_with_ffmpeg(idx_segment):
                idx, segment = idx_segment
                try:
                    start_seconds = segment.get('start', 0)
                    end_seconds = segment.get('end', 0)
                    
                    # 确保时间范围有效
                    if start_seconds >= end_seconds or start_seconds < 0:
                        return None
                    
                    duration = end_seconds - start_seconds
                    
                    # 确保片段至少有0.1秒
                    if duration < 0.1:
                        return None
                    
                    output_file = os.path.join(output_folder, f"{file_prefix}_{idx+1}.{output_format}")
                    
                    # 使用ffmpeg直接分割
                    cmd = [
                        "ffmpeg", 
                        "-i", audio_path,
                        "-ss", str(start_seconds),
                        "-t", str(duration),
                        "-acodec", codec,
                        "-ab", bitrate,
                        "-ar", "44100",
                        "-y", output_file
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        return output_file
                    else:
                        print(f"警告：并行处理片段 {idx+1} FFmpeg执行失败: {result.stderr}")
                        return None
                except Exception as e:
                    print(f"警告：并行处理片段 {idx+1} 异常: {str(e)}")
                    return None
            
            # 创建线程池
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                futures = list(executor.map(process_segment_with_ffmpeg, enumerate(segments)))
                
                # 收集结果
                for i, result in enumerate(futures):
                    if result:
                        output_files.append(result)
                    
                    if progress_callback and i % max(1, total_segments // 10) == 0:
                        progress_percent = 80 + int((i / total_segments) * 20)
                        progress_callback(f"已处理 {i+1}/{total_segments} 个片段...", progress_percent)
        
        else:
            # 串行处理片段
            for i, segment in enumerate(segments):
                try:
                    # 更新进度
                    if progress_callback:
                        progress_percent = 80 + int((i / total_segments) * 20)
                        progress_callback(f"正在处理片段 {i+1}/{total_segments}...", progress_percent)
                    
                    start_seconds = segment.get('start', 0)
                    end_seconds = segment.get('end', 0)
                    
                    # 确保时间范围有效
                    if start_seconds >= end_seconds or start_seconds < 0:
                        continue
                    
                    duration = end_seconds - start_seconds
                    
                    # 确保片段至少有0.1秒
                    if duration < 0.1:
                        continue
                    
                    output_file = os.path.join(output_folder, f"{file_prefix}_{i+1}.{output_format}")
                    
                    # 使用ffmpeg直接分割
                    cmd = [
                        "ffmpeg", 
                        "-i", audio_path,
                        "-ss", str(start_seconds),
                        "-t", str(duration),
                        "-acodec", codec,
                        "-ab", bitrate,
                        "-ar", "44100",
                        "-y", output_file
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        output_files.append(output_file)
                    else:
                        print(f"警告：片段 {i+1} FFmpeg处理失败: {result.stderr}")
                except Exception as e:
                    # 跳过有问题的片段，继续处理其他片段
                    print(f"警告：片段 {i+1} 处理失败: {str(e)}")
                    continue
        
        if progress_callback:
            progress_callback("音频分割完成", 100)
            
        return output_files
    
    def clean_up(self):
        """Clean up temporary files"""
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
