@echo off

:: 1. 프로젝트 폴더로 확실하게 이동 (중요)
cd /d "C:\Users\CORE\Downloads\kogongjang-print"

:: 2. 가상환경의 python.exe를 직접 지정하여 app.py 실행
::    이것이 activate를 대체하는 가장 확실한 방법입니다.
.\venv\Scripts\python.exe app.py
