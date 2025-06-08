import os
import sys
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from gui import TranscriptionGUI
from openai_client import OpenAIClient
from audio_processor import AudioProcessor

# 載入 .env 檔案
load_dotenv()

# 設定 logging
def setup_logging():
    """設定日誌系統"""
    # 建立 logs 資料夾
    log_dir = "logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # 設定日誌檔案路徑
    log_file = os.path.join(log_dir, "transcription.log")
    
    # 設定根日誌記錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除現有的處理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 建立檔案處理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 建立控制台處理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 設定其他模組的日誌記錄器
    for logger_name in ['openai_client', 'audio_processor', 'gui']:
        module_logger = logging.getLogger(logger_name)
        module_logger.propagate = True  # 確保日誌傳播到根記錄器
    
    logging.info("日誌系統初始化完成，日誌檔案：%s", log_file)

# 初始化日誌系統
setup_logging()
logger = logging.getLogger(__name__)

# 設定資料夾路徑
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "transcripts")
SUMMARY_FOLDER = os.getenv("SUMMARY_FOLDER", "summaries")
TEMP_FOLDER = os.getenv("TEMP_FOLDER", "temp")
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "")  # 監控資料夾路徑
SUPPORTED_FORMATS = os.getenv("SUPPORTED_FORMATS", ".mp3,.wav,.m4a,.flac").split(",")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "25")) * 1024 * 1024  # 25MB
SUMMARY_PROMPT = os.getenv("SUMMARY_PROMPT", "請為以下會議逐字稿生成摘要，包含：\n1. 會議主題\n2. 主要討論內容\n3. 重要決議事項\n4. 後續行動項目")

class AudioFileHandler(FileSystemEventHandler):
    def __init__(self, process_file_func):
        self.process_file = process_file_func
        self.processing_files = set()
        self.logger = logging.getLogger(__name__)
        
    def on_created(self, event):
        if event.is_directory:
            return
            
        file_path = event.src_path
        if not any(file_path.lower().endswith(fmt) for fmt in SUPPORTED_FORMATS):
            return
            
        # 避免重複處理
        if file_path in self.processing_files:
            return
            
        try:
            # 等待檔案完全寫入
            time.sleep(1)
            
            # 檢查檔案大小
            if os.path.getsize(file_path) == 0:
                self.logger.warning("檔案大小為 0，跳過處理：%s", file_path)
                return
                
            # 標記檔案正在處理
            self.processing_files.add(file_path)
            self.logger.info("開始處理檔案：%s", file_path)
            
            # 處理檔案
            success = self.process_file(file_path)
            if success:
                self.logger.info("檔案處理完成：%s", file_path)
            else:
                self.logger.error("檔案處理失敗：%s", file_path)
                
        except Exception as e:
            self.logger.error("處理檔案時發生錯誤：%s - %s", file_path, str(e))
        finally:
            # 移除處理標記
            self.processing_files.discard(file_path)

def ensure_folders():
    """確保必要的資料夾存在"""
    for folder in [OUTPUT_FOLDER, SUMMARY_FOLDER, TEMP_FOLDER]:
        Path(folder).mkdir(parents=True, exist_ok=True)
    logger.info("資料夾初始化完成")

def process_file(file_path):
    """
    處理單一音訊檔案
    :param file_path: 音訊檔案路徑
    :return: 是否成功處理
    """
    try:
        logger.info("開始處理檔案：%s", file_path)
        
        # 檢查檔案大小
        file_size = os.path.getsize(file_path)
        logger.info("檔案大小：%.2f MB", file_size / (1024 * 1024))
        
        if file_size > MAX_FILE_SIZE:
            logger.error("檔案太大：%.2f MB，超過限制", file_size / (1024 * 1024))
            return False
            
        # 初始化客戶端
        openai_client = OpenAIClient()
        
        # 轉錄音訊
        transcript = openai_client.transcribe_audio(file_path)
        if not transcript:
            logger.error("轉錄失敗")
            return False
            
        # 儲存逐字稿
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        transcript_path = os.path.join(OUTPUT_FOLDER, f"{file_name}_transcript.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        logger.info("逐字稿已儲存至：%s", transcript_path)
        
        # 生成摘要
        logger.info("開始生成摘要，檔案：%s", file_path)
        summary = openai_client.generate_summary(transcript, SUMMARY_PROMPT)
        if not summary:
            logger.error("生成摘要失敗")
            return False
            
        # 儲存摘要
        summary_path = os.path.join(SUMMARY_FOLDER, f"{file_name}_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        logger.info("摘要已儲存至：%s", summary_path)
        
        logger.info("檔案處理完成")
        return True
        
    except Exception as e:
        logger.error("處理檔案時發生錯誤：%s", str(e))
        return False

def start_file_monitoring():
    """啟動檔案監控"""
    if not WATCH_FOLDER or not os.path.exists(WATCH_FOLDER):
        logger.warning("未設定監控資料夾或資料夾不存在")
        return None
        
    try:
        # 建立觀察者
        observer = Observer()
        event_handler = AudioFileHandler(process_file)
        observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
        observer.start()
        logger.info("開始監控資料夾：%s", WATCH_FOLDER)
        return observer
    except Exception as e:
        logger.error("啟動檔案監控時發生錯誤：%s", str(e))
        return None

def main():
    """主程式"""
    try:
        # 確保資料夾存在
        ensure_folders()
        
        # 初始化 OpenAI 客戶端
        openai_client = OpenAIClient()
        logger.info("OpenAI 客戶端初始化完成")
        
        # 初始化音訊處理器
        audio_processor = AudioProcessor()
        logger.info("音訊處理器初始化完成")
        
        # 啟動檔案監控
        observer = start_file_monitoring()
        
        # 啟動 GUI
        app = TranscriptionGUI(openai_client, audio_processor)
        
        try:
            app.mainloop()
        finally:
            # 停止檔案監控
            if observer:
                observer.stop()
                observer.join()
                logger.info("停止監控資料夾")
        
    except Exception as e:
        logger.error("程式執行時發生錯誤：%s", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main() 