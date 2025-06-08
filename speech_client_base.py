from abc import ABC, abstractmethod

class SpeechClientBase(ABC):
    @abstractmethod
    def transcribe_audio(self, file_path):
        """
        使用語音轉錄 API 進行轉錄。
        :param file_path: 音訊檔案路徑
        :return: 逐字稿文字（str），失敗時回傳 None
        """
        pass

    @abstractmethod
    def generate_summary(self, transcript, prompt):
        """
        使用 AI 摘要 API 生成摘要。
        :param transcript: 逐字稿內容（str）
        :param prompt: 摘要提示詞（str）
        :return: 摘要文字（str），失敗時回傳 None
        """
        pass 