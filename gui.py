import os
import sys
import traceback

# --- 에러 처리 유틸리티 (GUI 초기화 전에도 동작) ---
def show_startup_error(title, message):
    """시작 시 에러를 사용자에게 보여주는 함수"""
    try:
        error_log = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0])), "error.log"
        )
        with open(error_log, "w", encoding="utf-8") as f:
            f.write(f"{title}\n{message}\n")
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showerror(title, message)
        root.destroy()
    except Exception:
        pass


# --- 콘솔 창 숨기기 (Windows, Nuitka onefile 호환) ---
try:
    import ctypes
    _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if _hwnd:
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        style = ctypes.windll.user32.GetWindowLongW(_hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(_hwnd, GWL_EXSTYLE, style)
        ctypes.windll.user32.ShowWindow(_hwnd, 0)
except Exception:
    pass

# --- stderr를 파일로 리다이렉트 ---
_error_log_path = os.path.join(
    os.path.dirname(os.path.abspath(sys.argv[0])), "error.log"
)
try:
    sys.stderr = open(_error_log_path, 'w', encoding='utf-8')
except Exception:
    pass

# --- Import (try/except로 감싸기) ---
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import customtkinter as ctk
    import threading
    import glob
    import socket
    import subprocess
    import tempfile
    import winreg
    import logging
    import queue
    import shutil
    from config import load_config, save_config, find_sumatra, get_backgrounds_dir
except Exception as e:
    show_startup_error(
        "감사장 인쇄 시스템 시작 실패",
        f"필수 모듈을 로드할 수 없습니다.\n\n"
        f"오류: {type(e).__name__}: {e}\n\n"
        f"상세:\n{traceback.format_exc()}\n\n"
        f"이 오류가 계속되면 개발자에게 문의해주세요."
    )
    sys.exit(1)

# --- 테마 설정 ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class QueueLogHandler(logging.Handler):
    """logging 핸들러 — 로그를 큐로 전달"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg + "\n")
        except Exception:
            pass


class CertificateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("감사장 인쇄 시스템")
        self.root.geometry("520x900")
        self.root.resizable(False, True)

        self.config = load_config()
        self.server_thread = None
        self.http_server = None
        self.server_running = False
        self.log_queue = queue.Queue()
        self.kiosk_process = None  # Chrome 키오스크 프로세스

        self._build_ui()
        self._load_config_to_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.tray_icon = None
        self.root.bind("<Unmap>", self._on_minimize)

    def _build_ui(self):
        frame = ctk.CTkFrame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        row = 0

        # 배경 템플릿
        ctk.CTkLabel(frame, text="배경 템플릿:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        self.bg_var = tk.StringVar()
        self.bg_combo = ctk.CTkComboBox(frame, variable=self.bg_var, values=self._get_backgrounds(),
                                         width=220, command=lambda _: self._save_ui_to_config())
        self.bg_combo.grid(row=row, column=1, sticky=tk.W, padx=10, pady=8)
        ctk.CTkButton(frame, text="추가", command=self._add_background, width=60).grid(
            row=row, column=2, sticky=tk.W, padx=5)
        row += 1

        # 폰트
        ctk.CTkLabel(frame, text="폰트:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        self.font_var = tk.StringVar()
        self.font_combo = ctk.CTkComboBox(frame, variable=self.font_var, values=self._get_fonts(),
                                           width=280, command=lambda _: self._save_ui_to_config())
        self.font_combo.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=10, pady=8)
        row += 1

        # 글자 크기
        ctk.CTkLabel(frame, text="글자 크기:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        self.fontsize_var = tk.StringVar()
        self.fontsize_entry = ctk.CTkEntry(frame, textvariable=self.fontsize_var, width=80)
        self.fontsize_entry.grid(row=row, column=1, sticky=tk.W, padx=10, pady=8)
        row += 1

        # 이름 위치
        ctk.CTkLabel(frame, text="이름 위치:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        pos_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pos_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=10, pady=8)

        ctk.CTkLabel(pos_frame, text="X").pack(side=tk.LEFT)
        self.name_x_var = tk.StringVar()
        ctk.CTkEntry(pos_frame, textvariable=self.name_x_var, width=55).pack(side=tk.LEFT, padx=(2, 8))

        ctk.CTkLabel(pos_frame, text="Y").pack(side=tk.LEFT)
        self.name_y_var = tk.StringVar()
        ctk.CTkEntry(pos_frame, textvariable=self.name_y_var, width=55).pack(side=tk.LEFT, padx=(2, 8))

        ctk.CTkLabel(pos_frame, text="W").pack(side=tk.LEFT)
        self.name_w_var = tk.StringVar()
        ctk.CTkEntry(pos_frame, textvariable=self.name_w_var, width=55).pack(side=tk.LEFT, padx=(2, 8))

        ctk.CTkLabel(pos_frame, text="H").pack(side=tk.LEFT)
        self.name_h_var = tk.StringVar()
        ctk.CTkEntry(pos_frame, textvariable=self.name_h_var, width=55).pack(side=tk.LEFT, padx=(2, 0))
        row += 1

        # 위치 저장 버튼
        ctk.CTkButton(frame, text="설정 저장", command=self._save_ui_to_config, width=100,
                       fg_color="#FFC107", text_color="black", hover_color="#FFD54F").grid(
            row=row, column=1, sticky=tk.W, padx=10, pady=4)
        row += 1

        # 구분선 대체 (CTkFrame 얇은 라인)
        ctk.CTkFrame(frame, height=2, fg_color="gray40").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=10)
        row += 1

        # SumatraPDF 경로
        ctk.CTkLabel(frame, text="SumatraPDF:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        self.sumatra_var = tk.StringVar()
        ctk.CTkEntry(frame, textvariable=self.sumatra_var, width=240).grid(row=row, column=1, sticky=tk.W, padx=10, pady=8)
        ctk.CTkButton(frame, text="찾아보기", command=self._browse_sumatra, width=80).grid(
            row=row, column=2, sticky=tk.W, padx=5)
        row += 1

        # 서버 포트
        ctk.CTkLabel(frame, text="서버 포트:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        self.port_var = tk.StringVar()
        ctk.CTkEntry(frame, textvariable=self.port_var, width=100).grid(row=row, column=1, sticky=tk.W, padx=10, pady=8)
        row += 1

        # 윈도우 시작 시 자동 실행
        self.autostart_var = tk.BooleanVar()
        self.autostart_check = ctk.CTkCheckBox(
            frame, text="윈도우 시작 시 자동 실행",
            variable=self.autostart_var,
            command=self._toggle_autostart
        )
        self.autostart_check.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=8)
        row += 1

        # 구분선
        ctk.CTkFrame(frame, height=2, fg_color="gray40").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=10)
        row += 1

        # --- 키오스크 설정 ---
        ctk.CTkLabel(frame, text="키오스크 URL:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=8)
        self.kiosk_url_var = tk.StringVar()
        ctk.CTkEntry(frame, textvariable=self.kiosk_url_var, width=280,
                      placeholder_text="http://localhost:5000/preview?name=홍길동").grid(
            row=row, column=1, columnspan=2, sticky=tk.W, padx=10, pady=8)
        row += 1

        # 키오스크 옵션 행
        kiosk_opt_frame = ctk.CTkFrame(frame, fg_color="transparent")
        kiosk_opt_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=4)

        self.kiosk_auto_var = tk.BooleanVar()
        ctk.CTkCheckBox(kiosk_opt_frame, text="서버 시작 시 크롬 자동 열기 (풀스크린)",
                         variable=self.kiosk_auto_var,
                         command=self._save_kiosk_config).pack(side=tk.LEFT)

        ctk.CTkLabel(kiosk_opt_frame, text="  확대율:").pack(side=tk.LEFT, padx=(16, 0))
        self.kiosk_zoom_var = tk.StringVar()
        ctk.CTkEntry(kiosk_opt_frame, textvariable=self.kiosk_zoom_var, width=50).pack(side=tk.LEFT, padx=2)
        ctk.CTkLabel(kiosk_opt_frame, text="%").pack(side=tk.LEFT)
        row += 1

        # 키오스크 저장 버튼
        ctk.CTkButton(frame, text="키오스크 설정 저장", command=self._save_kiosk_config, width=140,
                       fg_color="#FFC107", text_color="black", hover_color="#FFD54F").grid(
            row=row, column=1, sticky=tk.W, padx=10, pady=4)
        row += 1

        # 구분선
        ctk.CTkFrame(frame, height=2, fg_color="gray40").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=10)
        row += 1

        # 서버 제어 버튼
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=3, pady=8)

        self.start_btn = ctk.CTkButton(btn_frame, text="서버 시작", command=self._start_server,
                                        fg_color="#4CAF50", hover_color="#66BB6A", width=120)
        self.start_btn.pack(side=tk.LEFT, padx=8)

        self.stop_btn = ctk.CTkButton(btn_frame, text="서버 중지", command=self._stop_server,
                                       fg_color="#f44336", hover_color="#EF5350", width=120,
                                       state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=8)
        row += 1

        # 상태 표시
        self.status_label = ctk.CTkLabel(frame, text="서버 중지됨", text_color="gray")
        self.status_label.grid(row=row, column=0, columnspan=3, pady=(10, 4))
        row += 1

        # 로그 텍스트박스
        ctk.CTkLabel(frame, text="서버 로그:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=(4, 0))
        row += 1

        self.log_text = ctk.CTkTextbox(frame, height=120, font=ctk.CTkFont(size=11))
        self.log_text.grid(row=row, column=0, columnspan=3, sticky=tk.NSEW, padx=10, pady=(0, 10))
        self.log_text.configure(state=tk.DISABLED)
        frame.grid_rowconfigure(row, weight=1)

    def _get_backgrounds(self):
        names = set()
        # 외부 backgrounds/ 폴더
        ext_pattern = os.path.join(get_backgrounds_dir(), '*.png')
        for f in glob.glob(ext_pattern):
            names.add(os.path.basename(f))
        # 내장 static/images/
        int_pattern = os.path.join(BASE_DIR, 'static', 'images', 'background_*.png')
        for f in glob.glob(int_pattern):
            names.add(os.path.basename(f))
        return sorted(names)

    def _add_background(self):
        """파일 선택 다이얼로그로 배경 이미지를 backgrounds/ 폴더에 복사"""
        paths = filedialog.askopenfilenames(
            title="배경 이미지 선택",
            filetypes=[("PNG 이미지", "*.png"), ("All files", "*.*")]
        )
        if not paths:
            return
        dest_dir = get_backgrounds_dir()
        for path in paths:
            filename = os.path.basename(path)
            dest = os.path.join(dest_dir, filename)
            if os.path.abspath(path) != os.path.abspath(dest):
                shutil.copy2(path, dest)
        # 드롭다운 갱신
        new_values = self._get_backgrounds()
        self.bg_combo.configure(values=new_values)
        # 마지막으로 추가한 파일 선택
        last = os.path.basename(paths[-1])
        self.bg_var.set(last)
        self._save_ui_to_config()

    def _get_fonts(self):
        pattern = os.path.join(BASE_DIR, 'static', 'fonts', '*.ttf')
        files = glob.glob(pattern)
        return [os.path.basename(f) for f in sorted(files)]

    def _load_config_to_ui(self):
        self.bg_var.set(self.config.get('background', ''))
        self.font_var.set(self.config.get('font', ''))
        self.fontsize_var.set(str(self.config.get('font_size', 24)))
        self.name_x_var.set(str(self.config.get('name_x', 20)))
        self.name_y_var.set(str(self.config.get('name_y', 300)))
        self.name_w_var.set(str(self.config.get('name_width', 500)))
        self.name_h_var.set(str(self.config.get('name_height', 350)))
        sumatra = self.config.get('sumatra_path', 'auto')
        if sumatra == 'auto':
            found = find_sumatra()
            self.sumatra_var.set(found if found else 'auto')
        else:
            self.sumatra_var.set(sumatra)
        self.port_var.set(str(self.config.get('port', 5000)))
        self.autostart_var.set(self._is_autostart_enabled())
        self.kiosk_url_var.set(self.config.get('kiosk_url', ''))
        self.kiosk_auto_var.set(self.config.get('kiosk_auto_open', False))
        self.kiosk_zoom_var.set(str(self.config.get('kiosk_zoom', 100)))

    def _is_autostart_enabled(self):
        """레지스트리에 자동 실행이 등록되어 있는지 확인"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "감사장인쇄")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _toggle_autostart(self):
        """체크박스 토글 시 레지스트리에 자동 실행 등록/해제"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_SET_VALUE)
            if self.autostart_var.get():
                exe_path = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, "감사장인쇄", 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, "감사장인쇄")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            messagebox.showerror("오류", f"자동 실행 설정 실패: {e}")
            self.autostart_var.set(not self.autostart_var.get())

    def _save_kiosk_config(self):
        """키오스크 설정을 config.json에 저장"""
        try:
            zoom = int(self.kiosk_zoom_var.get())
            if zoom < 50 or zoom > 300:
                messagebox.showwarning("경고", "확대율은 50~300 사이로 입력해주세요.")
                return
        except ValueError:
            messagebox.showwarning("경고", "확대율에 숫자를 입력해주세요.")
            return
        self.config['kiosk_url'] = self.kiosk_url_var.get().strip()
        self.config['kiosk_auto_open'] = self.kiosk_auto_var.get()
        self.config['kiosk_zoom'] = zoom
        save_config(self.config)

    def _open_kiosk_chrome(self):
        """Chrome을 키오스크(풀스크린) 모드로 실행"""
        url = self.kiosk_url_var.get().strip()
        if not url:
            return
        chrome = self._find_chrome()
        if not chrome:
            messagebox.showerror("오류", "Chrome을 찾을 수 없습니다.\nChrome이 설치되어 있는지 확인해주세요.")
            return
        try:
            kiosk_data_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
                "KogongjangKiosk", "ChromeData"
            )
            zoom = self.config.get('kiosk_zoom', 100)
            scale_factor = zoom / 100.0
            self.kiosk_process = subprocess.Popen([
                chrome,
                "--kiosk",
                "--new-window",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={kiosk_data_dir}",
                f"--force-device-scale-factor={scale_factor}",
                url,
            ])
            # app.py의 close-kiosk 엔드포인트에서 접근할 수 있도록 공유
            from app import kiosk_process_holder
            kiosk_process_holder["process"] = self.kiosk_process
        except Exception as e:
            messagebox.showerror("오류", f"Chrome 실행 실패: {e}")

    @staticmethod
    def _find_chrome():
        """Windows에서 Chrome 실행 파일 경로를 탐색"""
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _save_ui_to_config(self):
        try:
            self.config['background'] = self.bg_var.get()
            self.config['font'] = self.font_var.get()
            self.config['font_size'] = int(self.fontsize_var.get())
            self.config['name_x'] = int(self.name_x_var.get())
            self.config['name_y'] = int(self.name_y_var.get())
            self.config['name_width'] = int(self.name_w_var.get())
            self.config['name_height'] = int(self.name_h_var.get())
            self.config['sumatra_path'] = self.sumatra_var.get()
            self.config['port'] = int(self.port_var.get())
            save_config(self.config)
        except ValueError:
            pass  # 숫자 변환 실패 시 무시

    def _browse_sumatra(self):
        path = filedialog.askopenfilename(
            title="SumatraPDF 선택",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if path:
            self.sumatra_var.set(path)
            self._save_ui_to_config()

    def _start_server(self):
        if self.server_running:
            return
        self._save_ui_to_config()

        from app import app as flask_app
        from werkzeug.serving import make_server

        port = int(self.port_var.get())
        try:
            self.http_server = make_server('0.0.0.0', port, flask_app)
        except OSError as e:
            messagebox.showerror("오류", f"서버 시작 실패: {e}")
            return

        self._setup_log_redirect()
        self.server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.server_thread.start()
        self.server_running = True
        self._poll_log_queue()

        self._append_log(f"서버 시작됨 — http://0.0.0.0:{port}\n")
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_label.configure(text=f"● 서버 실행 중 (포트 {port})", text_color="#4CAF50")

        # 키오스크 자동 열기
        if self.kiosk_auto_var.get() and self.kiosk_url_var.get().strip():
            self.root.after(500, self._open_kiosk_chrome)

    def _stop_server(self):
        if not self.server_running:
            return
        self.http_server.shutdown()
        self.server_running = False

        self._append_log("서버 중지됨\n")
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.status_label.configure(text="서버 중지됨", text_color="gray")

    def _on_minimize(self, event):
        if self.root.state() == 'iconic':
            self._hide_to_tray()

    def _hide_to_tray(self):
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            return

        self.root.withdraw()
        icon_image = PILImage.new('RGB', (64, 64), color=(0, 102, 204))
        menu = pystray.Menu(
            pystray.MenuItem("열기", self._show_from_tray),
            pystray.MenuItem("종료", self._quit_from_tray)
        )
        self.tray_icon = pystray.Icon("certificate", icon_image, "감사장 인쇄", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_from_tray(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.deiconify)

    def _quit_from_tray(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self._on_close)

    def _append_log(self, msg):
        """로그 텍스트박스에 메시지 추가"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self):
        """큐에서 로그를 가져와 UI 업데이트 (100ms 간격)"""
        try:
            while True:
                line = self.log_queue.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _setup_log_redirect(self):
        """werkzeug 로거를 큐 핸들러로 리다이렉트"""
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(message)s", datefmt="%H:%M:%S"
        ))
        for name in ("werkzeug",):
            logger = logging.getLogger(name)
            logger.handlers = [handler]
            logger.setLevel(logging.INFO)
            logger.propagate = False

    def _on_close(self):
        if self.server_running:
            self._stop_server()
        self.root.destroy()


def check_duplicate(port):
    """소켓으로 포트 사용 여부 체크하여 중복 실행 방지"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(('localhost', port)) == 0:
                messagebox.showwarning(
                    "경고",
                    f"감사장 인쇄 서버가 이미 실행 중입니다.\n(포트 {port} 사용 중)"
                )
                sys.exit(0)
    except Exception:
        pass


if __name__ == '__main__':
    if not os.path.exists('output'):
        os.makedirs('output')

    config = load_config()
    check_duplicate(config['port'])

    root = ctk.CTk()
    app = CertificateApp(root)

    root.after(500, app._start_server)
    root.mainloop()
