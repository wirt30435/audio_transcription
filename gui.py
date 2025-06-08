import tkinter as tk
from tkinter import filedialog, scrolledtext
import logging
import os
import threading
from audio_processor import AudioProcessor

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        self.text_widget.after(0, append)

class TranscriptionGUI:
    def __init__(self, openai_client, audio_processor):
        self.root = tk.Tk()
        self.root.title("音訊轉錄工具")
        self.root.geometry("800x600")
        
        # 初始化處理器
        self.openai_client = openai_client
        self.audio_processor = audio_processor
        
        # 建立 GUI
        self.setup_gui()
        
        # 設定日誌處理器
        self.logger = logging.getLogger(__name__)
        self.logger.propagate = True  # 確保日誌傳播到根記錄器
        
        # 設定 GUI 文字處理器
        self.text_handler = TextHandler(self.log_text)
        self.text_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(self.text_handler)
        
    def setup_gui(self):
        # 選擇檔案按鈕
        self.select_btn = tk.Button(
            self.root, 
            text="選擇音訊檔案",
            command=self.select_file
        )
        self.select_btn.pack(pady=10)
        
        # 檔案路徑顯示
        self.file_label = tk.Label(self.root, text="尚未選擇檔案")
        self.file_label.pack(pady=5)
        
        # 轉錄按鈕
        self.transcribe_btn = tk.Button(
            self.root,
            text="開始轉錄",
            command=self.start_transcription,
            state=tk.DISABLED
        )
        self.transcribe_btn.pack(pady=10)
        
        # 日誌顯示區域
        self.log_text = scrolledtext.ScrolledText(
            self.root,
            height=20,
            width=80
        )
        self.log_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.log_text.configure(state='disabled')
        
    def select_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("音訊檔案", "*.mp3 *.wav *.m4a *.flac"),
                ("所有檔案", "*.*")
            ]
        )
        if file_path:
            self.file_path = file_path
            self.file_label.config(text=file_path)
            self.transcribe_btn.config(state=tk.NORMAL)
            self.logger.info("(GUI) 手動選擇檔案製作逐字稿：%s", file_path)
            
    def process_file_in_thread(self):
        """在背景執行緒中處理檔案"""
        try:
            from transcribe import process_file
            self.logger.info("(GUI) 已啟動背景執行緒，開始處理檔案")
            success = process_file(self.file_path)
            if success:
                self.logger.info("檔案處理完成")
            else:
                self.logger.error("檔案處理失敗")
        except Exception as e:
            self.logger.error("處理過程發生錯誤：%s", str(e))
        finally:
            # 重新啟用按鈕
            self.root.after(0, lambda: self.transcribe_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
            
    def start_transcription(self):
        if not hasattr(self, 'file_path'):
            self.logger.error("請先選擇檔案")
            return
            
        try:
            # 禁用按鈕，避免重複操作
            self.transcribe_btn.config(state=tk.DISABLED)
            self.select_btn.config(state=tk.DISABLED)
            
            # 在背景執行緒中處理檔案
            thread = threading.Thread(target=self.process_file_in_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.logger.error("啟動處理執行緒時發生錯誤：%s", str(e))
            # 重新啟用按鈕
            self.transcribe_btn.config(state=tk.NORMAL)
            self.select_btn.config(state=tk.NORMAL)
            
    def mainloop(self):
        self.root.mainloop() 