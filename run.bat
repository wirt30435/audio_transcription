@echo off
echo 正在啟動音訊轉錄工具...

:: 設定 OpenAI API Key
set OPENAI_API_KEY=your-api-key-here

:: 安裝必要的套件（如果還沒安裝）
pip install openai

:: 執行程式
python transcribe.py

pause 