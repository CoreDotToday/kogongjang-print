# 실행할 파이썬 실행 파일과 스크립트 경로 정의
$ProjectDir = "C:\Users\CORE\Downloads\kogongjang-print"
$PythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"
$PythonScript = Join-Path $ProjectDir "app.py"

# 파이썬 스크립트를 창 없이 백그라운드에서 실행
Start-Process -FilePath $PythonExe -ArgumentList $PythonScript -WorkingDirectory $ProjectDir -WindowStyle Hidden
