import os
import numpy as np
import torch
from transformers import pipeline
import re

class AudioAnalyzer:
    def __init__(self, model_name="openai/whisper-tiny"):
        """Initialize with specified Whisper model from transformers"""
        # 确保只有在实际需要时才加载模型
        self.model_name = model_name
        
        # 详细检查GPU状态
        print("\n===== GPU状态检查 =====")
        print(f"CUDA是否可用: {torch.cuda.is_available()}")
        print(f"PyTorch版本: {torch.__version__}")
        
        if torch.cuda.is_available():
            self.device = "cuda"
            print(f"GPU数量: {torch.cuda.device_count()}")
            print(f"GPU型号: {torch.cuda.get_device_name(0)}")
            print(f"当前选择的GPU: {torch.cuda.current_device()}")
            try:
                print(f"GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024 / 1024 / 1024:.2f} GB")
            except Exception as e:
                print(f"获取GPU内存信息失败: {e}")
        else:
            self.device = "cpu"
            print("警告: 未检测到可用的GPU。转录将使用CPU，这可能会很慢。")
            print("如果您有NVIDIA GPU，请确保正确安装了CUDA和相应版本的PyTorch。")
            
            # 尝试诊断CUDA问题
            try:
                import subprocess
                print("\n尝试运行nvidia-smi检查GPU状态...")
                result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
                if result.returncode == 0:
                    print("nvidia-smi输出:")
                    print(result.stdout)
                else:
                    print(f"nvidia-smi错误: {result.stderr}")
            except Exception as e:
                print(f"无法执行nvidia-smi: {e}")
        
        print(f"使用设备: {self.device}")
        print("======================\n")
        
        # 繁简体转换器
        try:
            import opencc
            self.converter = opencc.OpenCC('t2s')  # 繁体转简体
            self.use_converter = True
        except ImportError:
            print("警告: 未安装opencc库，无法进行繁简体转换。请使用pip安装: pip install opencc-python-reimplemented")
            self.use_converter = False
        
        self.pipe = None
    
    def _get_model_path(self, model_name):
        """
        获取模型的本地路径
        
        Args:
            model_name: 模型名称，如'openai/whisper-tiny'
            
        Returns:
            str: 模型的本地路径
        """
        # 提取模型名称部分，去掉组织名
        model_id = model_name.split("/")[-1] if "/" in model_name else model_name
        
        # 首先检查用户指定的本地目录
        local_paths = [
            # 标准缓存目录（与ModelManager一致）
            os.path.join(os.path.expanduser("~"), ".cache", "whisper_models", model_id),
        ]
        
        # 检查是否存在任一路径
        for path in local_paths:
            if os.path.exists(path):
                print(f"在本地找到模型: {path}")
                return path
        
        # 默认返回缓存目录
        return os.path.join(os.path.expanduser("~"), ".cache", "whisper_models", model_id)
    
    def _ensure_model_loaded(self, chunk_length_s=10):
        """确保模型已加载"""
        if self.pipe is None:
            try:
                # 获取模型的本地路径
                model_path = self._get_model_path(self.model_name)
                
                # 检查模型是否存在
                if not os.path.exists(model_path):
                    # 如果本地不存在，尝试使用ModelManager下载
                    try:
                        from core.model_manager import ModelManager
                        print(f"模型文件不存在: {model_path}，尝试从OSS下载...")
                        model_manager = ModelManager()
                        # 检查模型是否可下载
                        if not model_manager.is_model_downloaded(self.model_name):
                            # 使用同步方式下载模型
                            model_manager.download_model(self.model_name)
                            # 等待下载完成
                            max_wait = 600  # 最多等待10分钟
                            wait_time = 0
                            check_interval = 5  # 每5秒检查一次
                            while wait_time < max_wait:
                                status = model_manager.get_model_status(self.model_name)
                                if status["status"] == "downloaded":
                                    print(f"模型下载完成: {self.model_name}")
                                    break
                                elif status["status"] == "failed":
                                    raise Exception(f"模型下载失败: {self.model_name}")
                                print(f"等待模型下载完成... {status.get('progress', 0)}%")
                                import time
                                time.sleep(check_interval)
                                wait_time += check_interval
                            
                            # 重新获取模型路径
                            model_path = self._get_model_path(self.model_name)
                            if not os.path.exists(model_path):
                                raise FileNotFoundError(f"下载模型后路径仍不存在: {model_path}")
                        else:
                            model_path = model_manager.get_model_path(self.model_name)
                    except ImportError:
                        raise FileNotFoundError(f"模型文件不存在: {model_path}，请先下载模型")
                
                print(f"从本地加载模型: {model_path}")
                
                # 使用本地模型路径
                self.pipe = pipeline(
                    "automatic-speech-recognition",
                    model=model_path,
                    generate_kwargs={"task": "transcribe"},
                    device=self.device,
                    chunk_length_s=chunk_length_s,
                    return_timestamps=True
                )
            except Exception as e:
                # 提供更详细的错误信息
                raise Exception(f"模型加载失败({self.model_name}): {str(e)}")
    
    def transcribe(self, audio_path, chunk_length=10, language=None):
        """
        Transcribe audio file using Whisper
        
        Args:
            audio_path: Path to audio file
            chunk_length: Length of audio chunks to process in seconds
            language: Language of the audio (optional)
        
        Returns:
            Transcription with segments
        """
        # 使用提供的chunk_length参数加载模型
        self._ensure_model_loaded(chunk_length_s=chunk_length)
        
        try:
            # 检查文件是否存在
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"文件不存在: {audio_path}")
                
            # 加载模型（如果尚未加载）
            self._ensure_model_loaded(chunk_length_s=chunk_length)
            
            # 准备转录参数
            transcribe_params = {
                "chunk_length_s": chunk_length,  # 切片长度
                "return_timestamps": True,  # 返回时间戳
            }
            
            # 配置生成参数
            generate_kwargs = {}
            
            # 将界面语言转换为模型支持的标准语言代码
            language_mapping = {
                "中文": "chinese",
                "英文": "english",
                "日文": "japanese",
                "韩文": "korean",
                "自动检测": None  # 自动检测时不指定语言
            }
            
            if language and language != "自动检测":
                # 检查是否需要转换语言代码
                if language in language_mapping:
                    standard_lang = language_mapping[language]
                    print(f"将界面语言 '{language}' 转换为标准语言代码 '{standard_lang}'")
                    language = standard_lang
                
                # 在新版本的transformers中，language需要通过generate_kwargs参数传递
                if language:  # 确保语言不为None
                    generate_kwargs["language"] = language
                    print(f"使用指定语言进行转录: {language}")
                    transcribe_params["generate_kwargs"] = generate_kwargs
            else:
                print("使用自动语言检测")
            
            print(f"Device set to use {self.device}")
            
            # 尝试转录
            result = self.pipe(audio_path, **transcribe_params)
            print(f"Transcription result: {result}")
            
            # 处理繁体转简体
            if self.use_converter and (language == "chinese" or (language is None and "chunks" in result)):
                if "text" in result:
                    result["text"] = self._process_text_with_punctuation(result["text"])
                if "chunks" in result:
                    for chunk in result["chunks"]:
                        if "text" in chunk:
                            chunk["text"] = self._process_text_with_punctuation(chunk["text"])
                print("已将繁体文字转换为简体")
            
            # 转换为标准格式
            segments = []
            
            # 处理pipeline返回的不同格式
            if "chunks" in result:
                # 较新版本的transformers可能以chunks形式返回
                # 合并过短的片段并添加标点符号
                merged_segments = self._merge_short_segments(result["chunks"])
                for segment in merged_segments:
                    segments.append({
                        "start": segment["timestamp"][0],
                        "end": segment["timestamp"][1],
                        "text": segment["text"]
                    })
            elif "text" in result and isinstance(result.get("timestamps"), list):
                # 处理带时间戳的文本
                for i, timestamp in enumerate(result["timestamps"]):
                    if len(timestamp) >= 2:
                        segments.append({
                            "start": timestamp[0],
                            "end": timestamp[1],
                            "text": timestamp[2] if len(timestamp) > 2 else ""
                        })
            else:
                # 如果没有时间戳，创建一个大片段
                segments.append({
                    "start": 0.0,
                    "end": 30.0,  # 假设默认长度
                    "text": result.get("text", "")
                })
            
            return {"segments": segments}
        except Exception as e:
            raise Exception(f"转录失败: {str(e)}")

    def _merge_short_segments(self, chunks, min_duration=2.0, min_chars=15):
        """合并过短的音频片段，并尝试添加标点符号"""
        if not chunks:
            return []
            
        merged_chunks = []
        current_chunk = None
        
        for chunk in chunks:
            # 确保数据格式正确
            if "timestamp" not in chunk or len(chunk["timestamp"]) < 2:
                continue
                
            duration = chunk["timestamp"][1] - chunk["timestamp"][0]
            text = chunk["text"].strip()
            
            # 跳过空文本
            if not text:
                continue
                
            # 如果是第一个片段或当前片段足够长/字符数足够多，直接作为新片段
            if current_chunk is None or duration >= min_duration or len(text) >= min_chars:
                # 如果当前已有积累的片段，先处理它
                if current_chunk is not None:
                    # 尝试添加合适的标点符号
                    current_chunk["text"] = self._add_punctuation(current_chunk["text"])
                    merged_chunks.append(current_chunk)
                
                # 创建新的当前片段
                current_chunk = {
                    "timestamp": list(chunk["timestamp"]),
                    "text": text
                }
            else:
                # 合并到当前片段
                current_chunk["timestamp"][1] = chunk["timestamp"][1]
                
                # 判断是否需要添加空格
                if not current_chunk["text"].endswith(("，", "。", "？", "！", " ")):
                    current_chunk["text"] += " "
                    
                current_chunk["text"] += text
        
        # 处理最后一个片段
        if current_chunk is not None:
            current_chunk["text"] = self._add_punctuation(current_chunk["text"])
            merged_chunks.append(current_chunk)
            
        return merged_chunks
        
    def _add_punctuation(self, text):
        """添加标点符号，提高可读性
        
        Args:
            text: 需要处理的文本
            
        Returns:
            添加或修正标点后的文本
        """
        import re
        
        # 如果文本为空，直接返回
        if not text:
            return text
            
        # 替换常见的错误标点形式
        text = re.sub(r'([，。？！；：,.?!;:])\s+', r'\1', text)  # 移除标点后的空格
        
        # 检查文本末尾是否有标点，如果没有则添加
        if not re.search(r'[，。？！；：,.?!;:]$', text):
            # 根据文本句式决定添加的标点
            if re.search(r'(什么|为何|怎么样|吗|呢|会不会)$', text):
                text += '？'
            elif re.search(r'(多好|太棒了|真是|太|好极了|真棒)$', text):
                text += '！'
            else:
                text += '。'
                
        return text
        
    def _process_text_with_punctuation(self, text):
        """处理文本，确保有正确的标点并进行繁简体转换
        
        Args:
            text: 原始文本
            
        Returns:
            处理后的文本
        """
        # 首先进行繁简体转换
        if self.use_converter:
            text = self.converter.convert(text)
            
        # 添加/修正标点
        text = self._add_punctuation(text)
        
        return text
    
    def find_sentence_breaks(self, transcription, max_interval=60, min_interval=10, preserve_sentences=True):
        """
        Find logical sentence breaks between min and max interval while preserving sentence integrity
        
        Args:
            transcription: The transcription result from Whisper
            max_interval: Maximum length of each segment in seconds
            min_interval: Minimum length of each segment in seconds
            preserve_sentences: If True, try to preserve sentence integrity within ±3秒
            
        Returns:
            List of segments with start, end times and text
        """
        segments = []
        
        try:
            # 获取所有转录片段
            whisper_segments = transcription.get("segments", [])
            
            # 如果没有片段，返回空列表
            if not whisper_segments:
                print("警告: 没有找到有效的转录片段")
                return []
            
            # 确保最小区间不大于最大区间
            if min_interval > max_interval:
                min_interval = max_interval / 2
                print(f"警告: 最小区间大于最大区间，已调整为 {min_interval}s")
                
            # 清理无效的片段，去除有None值或异常数据的片段
            valid_whisper_segments = []
            for segment in whisper_segments:
                # 确保所有必要的键都存在且不为None
                if not all(k in segment and segment[k] is not None for k in ["start", "end", "text"]):
                    continue
                # 确保时间值是有效的数字    
                if not isinstance(segment["start"], (int, float)) or not isinstance(segment["end"], (int, float)):
                    continue
                # 确保结束时间大于开始时间
                if segment["end"] <= segment["start"]:
                    continue
                # 确保有文本内容
                if not segment["text"].strip():
                    continue
                    
                valid_whisper_segments.append(segment)
            
            if not valid_whisper_segments:
                print("警告: 清理后没有有效的转录片段")
                return []
                
            # 按时间排序
            valid_whisper_segments.sort(key=lambda x: x["start"])
            
            # 合并所有文本片段为完整的音频流
            total_duration = valid_whisper_segments[-1]["end"] - valid_whisper_segments[0]["start"]
            
            if total_duration < min_interval:
                # 如果总长度小于最小区间，则作为一个片段返回
                print(f"警告: 总音频长度({total_duration:.2f}s)小于最小区间({min_interval}s)，将作为单个片段返回")
                return [{
                    "start": valid_whisper_segments[0]["start"],
                    "end": valid_whisper_segments[-1]["end"],
                    "text": " ".join([s["text"] for s in valid_whisper_segments])
                }]
                
            # 开始按区间分割
            current_pos = valid_whisper_segments[0]["start"]
            end_pos = valid_whisper_segments[-1]["end"]
            
            print(f"开始分割音频: 总长度 {total_duration:.2f}s, 区间设置: {min_interval}s - {max_interval}s")
            
            # 当前正在处理的片段
            current_segment_texts = []
            current_segment_start = current_pos
            current_segment_end = current_pos
            
            for segment in valid_whisper_segments:
                # 如果当前片段结束时间小于current_pos，跳过这个片段
                if segment["end"] <= current_pos:
                    continue
                    
                # 如果当前片段开始时间大于current_pos，可能有时间间隙，调整current_pos
                if segment["start"] > current_pos:
                    current_pos = segment["start"]
                    
                # 计算这个片段加入后的总长度
                potential_end = segment["end"]
                potential_length = potential_end - current_segment_start
                
                # 如果加入后长度仍小于最小区间，或者未达到最大区间，继续加入
                if potential_length < min_interval or (len(current_segment_texts) > 0 and potential_length <= max_interval):
                    current_segment_texts.append(segment["text"])
                    current_segment_end = segment["end"]
                    current_pos = segment["end"]
                else:
                    # 如果已经有内容且长度超过最大区间，完成当前片段
                    if len(current_segment_texts) > 0:
                        segment_length = current_segment_end - current_segment_start
                        if segment_length >= min_interval:
                            segments.append({
                                "start": current_segment_start,
                                "end": current_segment_end,
                                "text": " ".join(current_segment_texts)
                            })
                            print(f"创建片段: {current_segment_start:.2f}s - {current_segment_end:.2f}s，长度: {segment_length:.2f}s")
                    
                    # 开始新片段
                    current_segment_texts = [segment["text"]]
                    current_segment_start = segment["start"]
                    current_segment_end = segment["end"]
                    current_pos = segment["end"]
            
            # 添加最后一个片段（如果有）
            if len(current_segment_texts) > 0:
                segment_length = current_segment_end - current_segment_start
                if segment_length >= min_interval:
                    segments.append({
                        "start": current_segment_start,
                        "end": current_segment_end,
                        "text": " ".join(current_segment_texts)
                    })
                    print(f"创建最后片段: {current_segment_start:.2f}s - {current_segment_end:.2f}s，长度: {segment_length:.2f}s")
            
            # 如果分段结果为空但有有效转录，则将整个音频作为一个片段
            if not segments and valid_whisper_segments:
                print(f"警告: 分段算法未生成有效片段，返回整个音频作为单个片段")
                return [{
                    "start": valid_whisper_segments[0]["start"],
                    "end": valid_whisper_segments[-1]["end"],
                    "text": " ".join([s["text"] for s in valid_whisper_segments])
                }]
            
            # 最终验证所有片段，确保长度符合要求
            valid_segments = []
            for segment in segments:
                length = segment["end"] - segment["start"]
                if length >= min_interval and length <= max_interval * 1.5:  # 允许50%的超出
                    valid_segments.append(segment)
                    
            # 如果没有有效片段，返回原始片段
            if not valid_segments and valid_whisper_segments:
                print(f"警告: 验证后没有有效片段，返回原始片段")
                return valid_whisper_segments
                
            print(f"生成片段总数: {len(valid_segments)}，总持续时间：{sum(seg['end']-seg['start'] for seg in valid_segments):.2f}s")
            
            return valid_segments
        except Exception as e:
            # 如果处理失败，返回原始片段或空列表
            print(f"查找句子中断点失败: {str(e)}")
            print(f"错误详情: {e.__class__.__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 尝试返回原始片段作为备选方案
            try:
                # 清理无效的片段，去除有None值或异常数据的片段
                valid_segments = []
                for segment in whisper_segments:
                    if all(k in segment and segment[k] is not None for k in ["start", "end", "text"]):
                        if segment["end"] > segment["start"] and segment["end"] - segment["start"] >= min_interval:
                            valid_segments.append(segment)
                return valid_segments
            except:
                return []
    
    def _find_last_sentence_break(self, text):
        """Find the position of the last sentence break in text"""
        try:
            sentence_end_markers = [".", "?", "!", "。", "？", "！"]
            
            last_break_pos = None
            for marker in sentence_end_markers:
                pos = text.rfind(marker)
                if pos != -1 and (last_break_pos is None or pos > last_break_pos):
                    last_break_pos = pos + 1  # 包含标记
            
            return last_break_pos
        except:
            return None
    
    def filter_segments_with_keywords(self, segments, keywords):
        """
        Filter out segments containing any of the specified keywords
        
        Args:
            segments: 要过滤的片段列表
            keywords: 要过滤的关键词列表
            
        Returns:
            不含有任何关键词的片段列表
        """
        if not keywords or not segments:
            return segments
            
        filtered_segments = []
        filtered_out = []
        
        try:
            import re
            
            # 处理关键词，不再忽略短关键词
            processed_keywords = []
            for keyword in keywords:
                keyword = keyword.lower().strip()
                if not keyword:
                    continue
                # 保留所有非空关键词，不再过滤短关键词
                processed_keywords.append(keyword)
            
            # 如果处理后没有有效关键词，直接返回原始片段
            if not processed_keywords:
                print("没有有效的关键词，跳过过滤")
                return segments
            
            print(f"有效关键词: {processed_keywords}")
                
            for segment in segments:
                # 检查片段是否包含任何关键词
                segment_text = segment.get("text", "").lower()
                contains_keyword = False
                matched_keywords = []
                match_positions = []
                
                for keyword in processed_keywords:
                    # 检查纯文本匹配
                    if keyword in segment_text:
                        # 收集所有匹配位置
                        start_pos = 0
                        while True:
                            pos = segment_text.find(keyword, start_pos)
                            if pos == -1:
                                break
                            
                            # 对于短关键词(1-2个字符)，我们需要更严格的匹配规则
                            is_valid_match = True
                            if len(keyword) <= 2:
                                # 验证匹配位置的上下文，确保是独立词汇而非词汇的一部分
                                
                                # 检查前一个字符（如果有）
                                if pos > 0:
                                    prev_char = segment_text[pos-1]
                                    # 如果前一个字符是字母或数字，可能是更大词汇的一部分
                                    if prev_char.isalnum() and prev_char not in [' ', ',', '.', '?', '!', ';', '，', '。', '？', '！', '；', '：']:
                                        # 对于拉丁文，这可能是错误匹配
                                        if re.match(r'[a-zA-Z0-9]', prev_char):
                                            is_valid_match = False
                                
                                # 检查后一个字符（如果有）
                                if pos + len(keyword) < len(segment_text) and is_valid_match:
                                    next_char = segment_text[pos + len(keyword)]
                                    # 如果后一个字符是字母或数字，可能是更大词汇的一部分
                                    if next_char.isalnum() and next_char not in [' ', ',', '.', '?', '!', ';', '，', '。', '？', '！', '；', '：']:
                                        # 对于拉丁文，这可能是错误匹配
                                        if re.match(r'[a-zA-Z0-9]', next_char):
                                            is_valid_match = False
                            
                            if is_valid_match:
                                # 这是有效匹配
                                contains_keyword = True
                                if keyword not in matched_keywords:
                                    matched_keywords.append(keyword)
                                match_info = {
                                    "keyword": keyword,
                                    "position": pos,
                                    "context": segment_text[max(0, pos-10):min(len(segment_text), pos+len(keyword)+10)]
                                }
                                match_positions.append(match_info)
                            
                            start_pos = pos + len(keyword)
                
                if contains_keyword and matched_keywords:
                    # 保存被过滤的片段和匹配的关键词，用于调试
                    segment_copy = segment.copy()
                    segment_copy["matched_keywords"] = matched_keywords
                    segment_copy["match_positions"] = match_positions
                    filtered_out.append(segment_copy)
                else:
                    filtered_segments.append(segment)
            
            # 打印过滤结果，方便调试
            print(f"过滤前片段数: {len(segments)}, 过滤后片段数: {len(filtered_segments)}")
            print(f"过滤掉的片段数: {len(filtered_out)}")
            
            # 打印被过滤片段的前3个，帮助确认过滤是否正确
            for i, seg in enumerate(filtered_out[:3]):
                print(f"被过滤片段 {i+1}: {seg.get('text', '')[:100]}...")
                matches = seg.get("match_positions", [])
                for m in matches:
                    print(f"  匹配关键词 '{m['keyword']}' 在位置 {m['position']}，上下文: '{m['context']}'")
            
            return filtered_segments
        except Exception as e:
            print(f"过滤关键词错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return segments
