import os
import logging
import time
import tempfile
from pydub import AudioSegment
from config import (
    OUTPUT_FOLDER,
    SUMMARY_FOLDER,
    TEMP_FOLDER,
    SUPPORTED_FORMATS,
    MAX_FILE_SIZE,
    CHUNK_DURATION,
    SUMMARY_PROMPT
)
from openai_client import OpenAIClient

# 使用 root logger
logger = logging.getLogger(__name__)
logger.propagate = True

class AudioProcessor:
    def __init__(self, supported_formats=None, max_file_size=None):
        """初始化音訊處理器"""
        self.supported_formats = supported_formats or SUPPORTED_FORMATS
        self.max_file_size = max_file_size or MAX_FILE_SIZE
        self.chunk_duration = CHUNK_DURATION
        self.output_folder = OUTPUT_FOLDER
        self.summary_folder = SUMMARY_FOLDER
        self.temp_folder = TEMP_FOLDER
        self.openai_client = OpenAIClient()
        
        # 建立必要的資料夾
        os.makedirs(self.temp_folder, exist_ok=True)
        os.makedirs(self.output_folder, exist_ok=True)
        os.makedirs(self.summary_folder, exist_ok=True)

        logger.info("(audio_processor) 音訊處理器初始化成功")

    def process_audio_file(self, file_path):
        """處理音訊檔案的主要方法"""
        try:
            logger.info("開始處理檔案：%s", file_path)
            
            # 檢查檔案是否存在且可讀取
            if not os.path.exists(file_path):
                logger.error("檔案不存在：%s", file_path)
                return False
                
            # 檢查檔案格式
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.supported_formats:
                logger.error("不支援的檔案格式：%s", file_ext)
                return False
                
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            logger.info("檔案大小：%.2f MB", file_size_mb)
            
            if file_size_mb > self.max_file_size:
                logger.info("檔案大小超過限制 (%.2f MB)，開始切割", self.max_file_size)
                chunk_paths = self.split_audio_file(file_path)
                
                if not chunk_paths:
                    logger.error("切割檔案失敗")
                    return False
                    
                transcripts = []
                for i, chunk_path in enumerate(chunk_paths):
                    try:
                        logger.info("處理第 %d/%d 個片段", i+1, len(chunk_paths))
                        chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                        logger.info("片段大小：%.2f MB", chunk_size_mb)
                        
                        t_start = time.time()
                        transcript = self.openai_client.transcribe_audio(chunk_path)
                        t_end = time.time()
                        
                        if transcript:
                            logger.info("片段轉錄成功，耗時：%.2f 秒", t_end - t_start)
                            transcripts.append(transcript)
                        else:
                            logger.error("片段轉錄失敗")
                    except Exception as e:
                        logger.error("處理片段時發生錯誤：%s", e)
                        continue
                    finally:
                        # 清理暫存檔案
                        try:
                            if os.path.exists(chunk_path):
                                os.remove(chunk_path)
                        except Exception as e:
                            logger.error("清理暫存檔案失敗：%s", e)
                        
                if transcripts:
                    merged_transcript = " ".join(transcripts)
                    self.save_transcript(file_path, merged_transcript)
                    self.generate_summary(merged_transcript, file_path)
                    logger.info("檔案處理完成")
                    return True
                else:
                    logger.error("所有片段轉錄均失敗")
                    return False
            else:
                # 直接處理小檔案
                t_start = time.time()
                transcript = self.openai_client.transcribe_audio(file_path)
                t_end = time.time()
                
                if transcript:
                    logger.info("檔案轉錄成功，耗時：%.2f 秒", t_end - t_start)
                    self.save_transcript(file_path, transcript)
                    self.generate_summary(transcript, file_path)
                    logger.info("檔案處理完成")
                    return True
                else:
                    logger.error("檔案轉錄失敗")
                    return False
                    
        except Exception as e:
            logger.error("處理檔案時發生錯誤：%s", e)
            return False

    def split_audio_file(self, file_path):
        """切割音訊檔案為較小的片段"""
        try:
            logger.info("開始切割檔案：%s", file_path)
            
            # 載入音訊檔案
            try:
                audio = AudioSegment.from_file(file_path)
            except Exception as e:
                logger.error("載入音訊檔案失敗：%s", e)
                return []
                
            # 計算切割參數
            duration_ms = len(audio)
            chunk_ms = self.chunk_duration * 60 * 1000  # 轉換為毫秒
            n_chunks = (duration_ms + chunk_ms - 1) // chunk_ms
            logger.info("音訊長度：%.2f 秒，將切割為 %d 個片段", duration_ms/1000, n_chunks)
            
            # 使用原始檔案名稱作為前綴
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # 根據檔案大小動態調整位元率
            target_chunk_size_mb = self.max_file_size * 0.8  # 預留 20% 的緩衝空間
            estimated_chunk_duration_min = self.chunk_duration
            bitrate = int((target_chunk_size_mb * 1024 * 8) / (estimated_chunk_duration_min * 60))  # kbps
            bitrate = max(32, min(192, bitrate))  # 限制在 32k-192k 之間
            logger.info("使用位元率：%d kbps", bitrate)
            
            chunk_paths = []
            for i in range(n_chunks):
                try:
                    # 計算當前片段的起止時間
                    start = i * chunk_ms
                    end = min((i + 1) * chunk_ms, duration_ms)
                    
                    # 切割音訊
                    chunk = audio[start:end]
                    
                    # 設定輸出路徑
                    chunk_path = os.path.join(self.temp_folder, f"{base_name}_part{i+1}.mp3")
                    
                    # 導出為 mp3 格式
                    chunk.export(
                        chunk_path,
                        format="mp3",
                        bitrate=f"{bitrate}k",
                        parameters=["-ac", "1"]  # 轉換為單聲道
                    )
                    
                    # 檢查輸出檔案
                    if os.path.exists(chunk_path):
                        chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                        logger.info("片段 %d 已輸出：%s (%.2f MB)", i+1, chunk_path, chunk_size_mb)
                        
                        # 如果檔案仍然太大，嘗試降低位元率
                        if chunk_size_mb > self.max_file_size:
                            logger.warning("片段 %d 仍然超過大小限制，嘗試降低位元率", i+1)
                            os.remove(chunk_path)
                            chunk.export(
                                chunk_path,
                                format="mp3",
                                bitrate="32k",  # 使用最低位元率
                                parameters=["-ac", "1"]
                            )
                            chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                            logger.info("重新輸出片段 %d：%s (%.2f MB)", i+1, chunk_path, chunk_size_mb)
                            
                            if chunk_size_mb > self.max_file_size:
                                logger.error("片段 %d 無法壓縮至符合大小限制", i+1)
                                os.remove(chunk_path)
                                continue
                        
                        chunk_paths.append(chunk_path)
                    else:
                        logger.error("片段 %d 輸出失敗", i+1)
                        
                except Exception as e:
                    logger.error("處理片段 %d 時發生錯誤：%s", i+1, e)
                    # 清理失敗的檔案
                    if os.path.exists(chunk_path):
                        try:
                            os.remove(chunk_path)
                        except:
                            pass
                    continue
                    
            if chunk_paths:
                logger.info("檔案切割完成，共 %d 個片段", len(chunk_paths))
                return chunk_paths
            else:
                logger.error("檔案切割失敗")
                return []
                
        except Exception as e:
            logger.error("切割檔案時發生錯誤：%s", e)
            return []

    def save_transcript(self, file_path, transcript):
        """儲存轉錄結果"""
        try:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(self.output_folder, f"{base_name}_transcript.txt")
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcript)
                
            logger.info("逐字稿已儲存至：%s", output_path)
            return True
        except Exception as e:
            logger.error("儲存逐字稿時發生錯誤：%s", e)
            return False

    def generate_summary(self, transcript, file_path):
        """生成並儲存摘要"""
        try:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(self.summary_folder, f"{base_name}_summary.txt")
            
            # 只傳遞 transcript 參數
            summary = self.openai_client.generate_summary(transcript)
            if summary:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(summary)
                logger.info("摘要已儲存至：%s", output_path)
                return True
            else:
                logger.error("生成摘要失敗")
                return False
        except Exception as e:
            logger.error("生成摘要時發生錯誤：%s", e)
            return False

    def split_audio(self, file_path, chunk_duration=600):
        """
        將音訊檔案分割成較小的片段
        :param file_path: 音訊檔案路徑
        :param chunk_duration: 每個片段的長度（秒）
        :return: 分割後的檔案路徑列表
        """
        try:
            logger.info("(audio_processor) 開始分割音訊檔案：%s", file_path)
            
            # 檢查檔案是否存在
            if not os.path.exists(file_path):
                logger.error("(audio_processor) 檔案不存在：%s", file_path)
                return []
                
            # 載入音訊檔案
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000  # 轉換為秒
            
            # 如果檔案長度小於 chunk_duration，直接返回原檔案
            if duration <= chunk_duration:
                logger.info("(audio_processor) 檔案長度小於 %d 秒，無需分割", chunk_duration)
                return [file_path]
                
            # 分割音訊
            chunks = []
            for i in range(0, len(audio), chunk_duration * 1000):
                chunk = audio[i:i + chunk_duration * 1000]
                chunk_path = os.path.join(tempfile.gettempdir(), f"chunk_{i}.mp3")
                chunk.export(chunk_path, format="mp3")
                chunks.append(chunk_path)
                
            logger.info("(audio_processor) 音訊檔案分割完成，共 %d 個片段", len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("(audio_processor) 分割音訊檔案時發生錯誤：%s", str(e))
            return []
            
    def cleanup_chunks(self, chunk_paths):
        """
        清理分割後的音訊片段
        :param chunk_paths: 音訊片段路徑列表
        """
        try:
            for path in chunk_paths:
                if os.path.exists(path):
                    os.remove(path)
            logger.info("(audio_processor) 清理完成，共清理 %d 個檔案", len(chunk_paths))
        except Exception as e:
            logger.error("(audio_processor) 清理檔案時發生錯誤：%s", str(e)) 