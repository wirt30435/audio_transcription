import os
import logging
import time
from openai import OpenAI
from openai.types.audio import Transcription

# 使用 root logger
logger = logging.getLogger(__name__)
logger.propagate = True

class OpenAIClient:
    def __init__(self):
        """初始化 OpenAI 客戶端"""
        try:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not self.client.api_key:
                raise ValueError("OpenAI API Key 未設定")
            logger.info("(openai_client) OpenAI 客戶端初始化成功")
        except Exception as e:
            logger.error("(openai_client) OpenAI 客戶端初始化失敗：%s", str(e))
            raise
        
    def transcribe_audio(self, file_path):
        """
        使用 OpenAI Whisper API 進行語音轉錄。
        :param file_path: 音訊檔案路徑
        :return: 逐字稿文字（str），失敗時回傳 None
        """
        try:
            t_start = time.time()
            logger.info("(openai_client) 開始呼叫 OpenAI Whisper API 轉錄檔案：%s (時間戳: %s)", file_path, t_start)
            
            # 檢查檔案是否存在
            if not os.path.exists(file_path):
                logger.error("(openai_client) 檔案不存在：%s", file_path)
                return None
                
            # 檢查檔案大小
            file_size = os.path.getsize(file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB
                logger.error("(openai_client) 檔案太大：%.2f MB，超過 25MB 限制", file_size / (1024 * 1024))
                return None
            
            # 檢查 API Key
            if not self.client.api_key:
                logger.error("(openai_client) OpenAI API Key 未設定")
                return None
                
            # 設定超時時間（秒）
            timeout = 300  # 5分鐘
            
            try:
                with open(file_path, "rb") as f:
                    logger.info("(openai_client) 開始上傳檔案到 OpenAI API...")
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="zh",
                        response_format="text",  # 直接返回文字格式
                        timeout=timeout  # 設定超時時間
                    )
                    
                if not transcript:
                    logger.error("(openai_client) API 返回空結果")
                    return None
                    
                t_end = time.time()
                duration = t_end - t_start
                logger.info("(openai_client) OpenAI Whisper API 轉錄完成，耗時：%.2f 秒", duration)
                logger.info("(openai_client) 逐字稿內容：%s", transcript)
                return transcript
                
            except Exception as api_error:
                logger.error("(openai_client) API 呼叫失敗：%s", str(api_error))
                if "timeout" in str(api_error).lower():
                    logger.error("(openai_client) API 呼叫超時（超過 %d 秒）", timeout)
                return None
                
        except Exception as e:
            logger.error("(openai_client) 轉錄過程發生錯誤：%s", str(e))
            return None
            
    def generate_summary(self, transcript, prompt=None):
        """使用 OpenAI GPT API 生成摘要
        :param transcript: 轉錄內容
        :param prompt: 摘要提示詞（可選）
        :return: 摘要文字，失敗時回傳 None
        """
        if not transcript or not transcript.strip():
            logger.error("(openai_client) 無效的轉錄內容")
            return None
            
        try:
            logger.info("(openai_client) 開始呼叫 OpenAI GPT-4 API 生成摘要")
            start_time = time.time()
            
            # 使用預設提示詞或自定義提示詞
            system_prompt = "你是一位專業的會議記錄員，負責將會議內容整理成摘要。請保持專業、客觀的態度。"
            user_prompt = prompt or "請將以下會議內容整理成摘要，重點包含：\n1. 會議主題\n2. 重要討論事項\n3. 決議事項\n4. 後續行動項目"
            
            # 如果轉錄內容太長，先進行分段
            if len(transcript) > 2000:  # 降低分段閾值
                logger.info("(openai_client) 轉錄內容較長，進行分段處理")
                # 將轉錄內容分成多段，每段約1000字
                segments = []
                current_segment = ""
                current_length = 0
                
                for line in transcript.split('\n'):
                    if current_length + len(line) > 1000:  # 降低每段長度
                        segments.append(current_segment)
                        current_segment = line + '\n'
                        current_length = len(line)
                    else:
                        current_segment += line + '\n'
                        current_length += len(line)
                
                if current_segment:
                    segments.append(current_segment)
                
                logger.info(f"(openai_client) 將內容分成 {len(segments)} 段進行處理")
                
                # 對每個段落生成摘要
                segment_summaries = []
                for i, segment in enumerate(segments, 1):
                    logger.info(f"(openai_client) 處理第 {i}/{len(segments)} 段")
                    try:
                        response = self.client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"{user_prompt}\n\n會議內容：\n{segment}"}
                            ],
                            temperature=0.7,
                            max_tokens=300  # 減少每段摘要的 token 數量
                        )
                        if response.choices[0].message.content:
                            segment_summaries.append(response.choices[0].message.content)
                            logger.info(f"(openai_client) 第 {i} 段摘要生成成功")
                        else:
                            logger.warning(f"(openai_client) 第 {i} 段摘要生成為空")
                    except Exception as e:
                        logger.error(f"(openai_client) 第 {i} 段摘要生成失敗：{str(e)}")
                        continue
                
                # 如果有分段摘要，再生成最終摘要
                if segment_summaries:
                    combined_summaries = "\n\n".join(segment_summaries)
                    logger.info("(openai_client) 開始生成最終摘要")
                    try:
                        response = self.client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "你是一位專業的會議記錄員，負責將多個會議摘要整合成一個完整的摘要。"},
                                {"role": "user", "content": f"{user_prompt}\n\n摘要內容：\n{combined_summaries}"}
                            ],
                            temperature=0.7,
                            max_tokens=800  # 減少最終摘要的 token 數量
                        )
                        end_time = time.time()
                        logger.info(f"(openai_client) 摘要生成完成，耗時 {end_time - start_time:.2f} 秒")
                        return response.choices[0].message.content
                    except Exception as e:
                        logger.error(f"(openai_client) 最終摘要生成失敗：{str(e)}")
                        return None
                else:
                    logger.error("(openai_client) 所有段落摘要生成失敗")
                    return None
            else:
                # 如果內容不長，直接生成摘要
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"{user_prompt}\n\n會議內容：\n{transcript}"}
                        ],
                        temperature=0.7,
                        max_tokens=800  # 減少摘要的 token 數量
                    )
                    end_time = time.time()
                    logger.info(f"(openai_client) 摘要生成完成，耗時 {end_time - start_time:.2f} 秒")
                    return response.choices[0].message.content
                except Exception as e:
                    logger.error(f"(openai_client) 摘要生成失敗：{str(e)}")
                    return None
                
        except Exception as e:
            logger.error(f"(openai_client) API 呼叫失敗：{str(e)}")
            return None 