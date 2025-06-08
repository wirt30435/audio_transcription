# config.py 僅保留設定參數，不包含業務邏輯或 GUI 相關程式碼

import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

# OpenAI API 設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 資料夾設定
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "")  # 監控的資料夾路徑
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "transcripts")
SUMMARY_FOLDER = os.getenv("SUMMARY_FOLDER", "summaries")
TEMP_FOLDER = os.getenv("TEMP_FOLDER", "temp_chunks")

# 檔案處理設定
SUPPORTED_FORMATS = os.getenv("SUPPORTED_FORMATS", ".mp3,.wav,.m4a,.flac").split(",")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "25"))  # 檔案大小限制（MB）
CHUNK_DURATION = int(os.getenv("CHUNK_DURATION", "10"))  # 切割片段長度（分鐘）

# 摘要生成設定
SUMMARY_PROMPT = os.getenv("SUMMARY_PROMPT", """請根據以下逐字稿生成一份結構化的會議記錄，包含：
1. 會議重點
2. 討論議題
3. 決議事項
4. 後續行動項目

請確保摘要清晰、簡潔，並突出重要資訊。""") 