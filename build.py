"""Nuitka 빌드 스크립트 — 단일 exe 생성"""
import subprocess
import sys

cmd = [
    sys.executable, "-m", "nuitka",
    "--mode=onefile",
    "--zig",
    "--windows-console-mode=disable",
    "--output-filename=감사장인쇄.exe",
    "--output-dir=dist",

    # 패키지 포함
    "--include-package=flask",
    "--include-package=werkzeug",
    "--include-package=jinja2",
    "--include-package=markupsafe",
    "--include-package=flask_cors",
    "--include-package=fitz",
    "--include-package=PIL",
    "--include-package=requests",
    "--include-package=pystray",
    "--include-package=customtkinter",
    "--include-package-data=customtkinter",

    # tkinter 플러그인
    "--enable-plugin=tk-inter",

    # 정적 파일 포함
    "--include-data-dir=static=static",
    "--include-data-dir=templates=templates",

    # 빌드 후 중간 파일 정리
    "--remove-output",

    # 메인 스크립트
    "gui.py",
]

print("빌드 시작...")
print(" ".join(cmd))
result = subprocess.run(cmd)
if result.returncode == 0:
    print("\n빌드 완료! dist/감사장인쇄.exe")
else:
    print(f"\n빌드 실패 (exit code: {result.returncode})")
    sys.exit(1)
