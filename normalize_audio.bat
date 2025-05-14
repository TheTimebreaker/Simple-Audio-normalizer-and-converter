@echo off
call "%~dp0.venv\Scripts\activate.bat"
py "%~dp0normalize_audio.py" %*