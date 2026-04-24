import os
import sys
import traceback

# --- 작업 디렉토리를 exe 위치로 설정 (자동실행 시 System32 방지) ---
IS_COMPILED = "__compiled__" in dir()
if IS_COMPILED:
    os.chdir(__nuitka_binary_dir)  # noqa: F821
else:
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

# --- data/ 폴더(설정/배경/폰트/PDF/로그를 한 곳에) 위치 계산 ---
# config.py와 동일한 규칙. 임포트 전에도 쓰려고 인라인.
_APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
_DATA_DIR = os.path.join(_APP_DIR, "data")
try:
    os.makedirs(_DATA_DIR, exist_ok=True)
except Exception:
    pass


# --- 에러 처리 유틸리티 (GUI 초기화 전에도 동작) ---
def show_startup_error(title, message):
    """시작 시 에러를 사용자에게 보여주는 함수"""
    try:
        error_log = os.path.join(_DATA_DIR, "error.log")
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
_error_log_path = os.path.join(_DATA_DIR, "error.log")
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
    import time
    import winreg
    import logging
    import queue
    import shutil
    import requests
    from PIL import Image, ImageDraw, ImageFont
    from config import (
        load_config, save_config, find_sumatra,
        find_background, find_font,
        get_backgrounds_dir, get_fonts_dir, get_output_dir,
    )
    from version import (
        __version__, __release_date__, __app_name__,
        __description__, __copyright__,
    )
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

# 미리보기 캔버스: A4(595x842pt) 기준으로 합성 후 썸네일로 축소.
PREVIEW_PT_W = 595
PREVIEW_PT_H = 842
PREVIEW_DISPLAY_W = 280
PREVIEW_DISPLAY_H = int(PREVIEW_DISPLAY_W * PREVIEW_PT_H / PREVIEW_PT_W)  # ~396


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
        self.root.title(f"{__app_name__}  v{__version__}")
        self.root.geometry("880x900")
        self.root.resizable(False, True)

        self.config = load_config()
        self.server_thread = None
        self.http_server = None
        self.server_running = False
        self.log_queue = queue.Queue()
        self.kiosk_process = None  # Chrome 키오스크 프로세스

        # 미리보기 상태
        self._preview_after_id = None
        self._preview_ctk_image = None

        self._build_ui()
        self._load_config_to_ui()
        self._bind_preview_traces()
        self._update_preview()  # 초기 렌더

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.tray_icon = None
        self.root.bind("<Unmap>", self._on_minimize)

    def _build_ui(self):
        # 하단 상태바 (먼저 BOTTOM 으로 packing — 그래야 콘텐츠가 위로 expand)
        self._build_status_bar(self.root)

        # 좌(컨트롤) + 우(미리보기) 2단 레이아웃
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))

        frame = ctk.CTkFrame(container)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_preview_panel(container)

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
                                           width=220, command=lambda _: self._save_ui_to_config())
        self.font_combo.grid(row=row, column=1, sticky=tk.W, padx=10, pady=8)
        ctk.CTkButton(frame, text="추가", command=self._add_font, width=60).grid(
            row=row, column=2, sticky=tk.W, padx=5)
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
        names = set()
        # 사용자 추가 폰트(data/fonts/)
        for ext in ('*.ttf', '*.otf'):
            for f in glob.glob(os.path.join(get_fonts_dir(), ext)):
                names.add(os.path.basename(f))
        # 번들 폰트(static/fonts/)
        for ext in ('*.ttf', '*.otf'):
            for f in glob.glob(os.path.join(BASE_DIR, 'static', 'fonts', ext)):
                names.add(os.path.basename(f))
        return sorted(names)

    def _add_font(self):
        """파일 선택 다이얼로그로 TTF/OTF를 data/fonts/ 폴더에 복사"""
        paths = filedialog.askopenfilenames(
            title="폰트 파일 선택",
            filetypes=[("폰트 파일", "*.ttf *.otf"), ("All files", "*.*")]
        )
        if not paths:
            return
        dest_dir = get_fonts_dir()
        for path in paths:
            filename = os.path.basename(path)
            dest = os.path.join(dest_dir, filename)
            if os.path.abspath(path) != os.path.abspath(dest):
                shutil.copy2(path, dest)
        new_values = self._get_fonts()
        self.font_combo.configure(values=new_values)
        last = os.path.basename(paths[-1])
        self.font_var.set(last)
        self._save_ui_to_config()

    # --- 미리보기 ----------------------------------------------------------

    def _build_preview_panel(self, parent):
        panel = ctk.CTkFrame(parent, width=PREVIEW_DISPLAY_W + 40)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        panel.pack_propagate(False)

        ctk.CTkLabel(panel, text="미리보기",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        # 샘플 이름 입력
        name_frame = ctk.CTkFrame(panel, fg_color="transparent")
        name_frame.pack(pady=4)
        ctk.CTkLabel(name_frame, text="샘플 이름:").pack(side=tk.LEFT, padx=(0, 6))
        self.sample_name_var = tk.StringVar(value="홍길동")
        ctk.CTkEntry(name_frame, textvariable=self.sample_name_var, width=140).pack(side=tk.LEFT)

        # 텍스트 영역 가이드 표시 토글
        self.show_text_box_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(panel, text="텍스트 영역 표시",
                        variable=self.show_text_box_var,
                        command=self._schedule_preview_update).pack(pady=4)

        # 미리보기 이미지
        self.preview_label = ctk.CTkLabel(
            panel, text="(렌더링 중...)",
            width=PREVIEW_DISPLAY_W, height=PREVIEW_DISPLAY_H,
            fg_color="gray20",
        )
        self.preview_label.pack(pady=10, padx=10)

        self.preview_status = ctk.CTkLabel(panel, text="", text_color="gray", font=ctk.CTkFont(size=10))
        self.preview_status.pack(pady=(0, 10))

    def _bind_preview_traces(self):
        """설정 UI 변수가 바뀔 때마다 미리보기 갱신을 예약."""
        for var in (
            self.bg_var, self.font_var, self.fontsize_var,
            self.name_x_var, self.name_y_var, self.name_w_var, self.name_h_var,
            self.sample_name_var,
        ):
            var.trace_add("write", lambda *_: self._schedule_preview_update())

    def _schedule_preview_update(self):
        """디바운싱: 짧은 시간 내 연속 변경은 마지막 한 번만 렌더."""
        if self._preview_after_id is not None:
            try:
                self.root.after_cancel(self._preview_after_id)
            except Exception:
                pass
        self._preview_after_id = self.root.after(300, self._update_preview)

    def _update_preview(self):
        self._preview_after_id = None
        try:
            img = self._render_preview()
        except Exception as e:
            # 직전 미리보기는 그대로 두고 status에만 경고 표시.
            # (image=None으로 라벨을 비우면 customtkinter가 이후 이미지 갱신을
            # 안정적으로 못 받아서 영구히 빈 상태가 되는 케이스가 있음.)
            self.preview_status.configure(
                text=f"입력값 확인 필요: {e}", text_color="#FFB454",
            )
            return
        self._preview_ctk_image = ctk.CTkImage(
            light_image=img, dark_image=img,
            size=(PREVIEW_DISPLAY_W, PREVIEW_DISPLAY_H),
        )
        self.preview_label.configure(image=self._preview_ctk_image, text="")
        self.preview_status.configure(
            text="A4 비율 · 실제 인쇄 결과와 미세 차이 가능", text_color="gray",
        )

    def _render_preview(self):
        """현재 UI 값(저장 전 포함)으로 합성 이미지를 만들어 반환."""
        # UI 값 읽기 (잘못된 숫자 입력 중에는 그냥 예외 던져서 호출측이 메시지 표시)
        font_size = int(self.fontsize_var.get())
        nx = int(self.name_x_var.get())
        ny = int(self.name_y_var.get())
        nw = int(self.name_w_var.get())
        nh = int(self.name_h_var.get())
        bg_name = self.bg_var.get()
        font_name = self.font_var.get()
        name = self.sample_name_var.get() or "홍길동"

        canvas = Image.new("RGB", (PREVIEW_PT_W, PREVIEW_PT_H), "white")

        bg_path = find_background(bg_name)
        if bg_path and os.path.exists(bg_path):
            bg = Image.open(bg_path).convert("RGB")
            bg = bg.resize((PREVIEW_PT_W, PREVIEW_PT_H), Image.LANCZOS)
            canvas.paste(bg, (0, 0))

        draw = ImageDraw.Draw(canvas)

        # 텍스트 영역 가이드 (얇은 실선)
        # PIL은 x1>=x0, y1>=y0 요구하므로 좌표가 거꾸로 들어와도
        # 그려서 사용자가 어디에 있는지 보이게 한다.
        if self.show_text_box_var.get():
            rx0, rx1 = sorted((nx, nw))
            ry0, ry1 = sorted((ny, nh))
            if rx1 > rx0 and ry1 > ry0:
                draw.rectangle([rx0, ry0, rx1, ry1], outline=(220, 60, 60), width=1)

        # 폰트 로딩: 사용자→번들 순으로 탐색
        font_path = find_font(font_name)
        try:
            pil_font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        except Exception:
            pil_font = ImageFont.load_default()

        # 텍스트 중앙 정렬 (rect 안에 가로/세로 중앙)
        rect_w = max(1, nw - nx)
        rect_h = max(1, nh - ny)
        try:
            bbox = draw.textbbox((0, 0), name, font=pil_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            tx = nx + (rect_w - text_w) / 2 - bbox[0]
            ty = ny + (rect_h - text_h) / 2 - bbox[1]
        except Exception:
            tx, ty = nx, ny
        draw.text((tx, ty), name, fill="black", font=pil_font)

        # 화면 표시용 썸네일로 축소
        return canvas.resize((PREVIEW_DISPLAY_W, PREVIEW_DISPLAY_H), Image.LANCZOS)

    # --- 상태바 / About 다이얼로그 -----------------------------------------

    def _build_status_bar(self, parent):
        """창 하단의 얇은 상태바 — 버전·릴리즈 날짜와 '정보' 버튼."""
        bar = ctk.CTkFrame(parent, height=34, fg_color="gray14", corner_radius=0)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        version_text = f"v{__version__}  ·  {__release_date__}"
        ctk.CTkLabel(
            bar, text=version_text,
            text_color="gray55", font=ctk.CTkFont(size=11),
        ).pack(side=tk.LEFT, padx=14)

        ctk.CTkButton(
            bar, text="정보", command=self._show_about_dialog,
            width=64, height=24,
            fg_color="transparent",
            border_width=1, border_color="gray35",
            text_color="gray70", hover_color="gray22",
            font=ctk.CTkFont(size=11),
        ).pack(side=tk.RIGHT, padx=14, pady=5)

    def _show_about_dialog(self):
        """About 다이얼로그 — 헤더 + 정보/릴리즈노트 탭 + 닫기 버튼."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("정보")
        dialog.geometry("560x560")
        dialog.resizable(False, False)
        dialog.transient(self.root)

        # 부모 창 중앙에 위치
        self.root.update_idletasks()
        try:
            px = self.root.winfo_x()
            py = self.root.winfo_y()
            pw = self.root.winfo_width()
            ph = self.root.winfo_height()
            x = px + (pw - 560) // 2
            y = py + (ph - 560) // 2
            dialog.geometry(f"560x560+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # 헤더 — 앱명(굵게 큰), 버전(회색 중간), 릴리즈 날짜(작게)
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(pady=(28, 8), padx=24, fill=tk.X)
        ctk.CTkLabel(
            header, text=__app_name__,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            header, text=f"버전 {__version__}",
            font=ctk.CTkFont(size=13), text_color="gray60",
        ).pack(pady=(6, 0))
        ctk.CTkLabel(
            header, text=f"릴리즈 일자 · {__release_date__}",
            font=ctk.CTkFont(size=11), text_color="gray50",
        ).pack()

        # 얇은 구분선
        ctk.CTkFrame(dialog, height=1, fg_color="gray25").pack(
            fill=tk.X, padx=24, pady=(16, 8))

        # 탭
        tabs = ctk.CTkTabview(dialog, height=340)
        tabs.pack(padx=20, pady=(4, 8), fill=tk.BOTH, expand=True)
        tabs.add("정보")
        tabs.add("릴리즈 노트")

        # --- 정보 탭 ---
        info_box = ctk.CTkTextbox(
            tabs.tab("정보"), wrap="word",
            font=ctk.CTkFont(size=12),
            fg_color="gray16", border_width=0,
        )
        info_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        info_lines = [
            __description__,
            "",
            "주요 기능",
            "  • Flask 기반 인쇄 서버 + customtkinter 설정 GUI",
            "  • 라이브 미리보기 패널 (배경·폰트·위치·글자크기 즉시 반영)",
            "  • 외부 폰트/배경 추가 지원 (data/ 폴더 기반)",
            "  • Chrome 키오스크 모드 자동 실행",
            "  • Windows 자동 시작 등록 / 트레이 최소화",
            "",
            "─" * 36,
            "",
            "시스템 정보",
            f"  • Python      : {sys.version.split()[0]}",
            f"  • 플랫폼      : {sys.platform}",
            f"  • 실행 모드   : {'빌드된 exe (Nuitka onefile)' if IS_COMPILED else '소스 (개발 모드)'}",
            "",
            __copyright__,
        ]
        info_box.insert("1.0", "\n".join(info_lines))
        info_box.configure(state=tk.DISABLED)

        # --- 릴리즈 노트 탭 ---
        notes_box = ctk.CTkTextbox(
            tabs.tab("릴리즈 노트"), wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="gray16", border_width=0,
        )
        notes_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        notes_box.insert("1.0", self._load_changelog())
        notes_box.configure(state=tk.DISABLED)

        # 닫기 버튼
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(side=tk.BOTTOM, pady=(0, 18), padx=24, fill=tk.X)
        ctk.CTkButton(
            btn_row, text="닫기", command=dialog.destroy,
            width=100, height=32,
        ).pack(side=tk.RIGHT)

        # 모달화는 창이 보인 뒤에 (Windows에서 grab_set 타이밍 이슈 회피)
        dialog.after(120, dialog.grab_set)
        dialog.focus_set()

    def _load_changelog(self):
        """CHANGELOG.md 본문 로드. 빌드된 exe에서는 번들된 파일을 읽음."""
        candidates = [
            os.path.join(BASE_DIR, "CHANGELOG.md"),
        ]
        for path in candidates:
            try:
                with open(path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                continue
        return "릴리즈 노트를 불러올 수 없습니다."

    # ----------------------------------------------------------------------

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
                if "__compiled__" in dir():
                    # Nuitka 빌드: onefile은 임시폴더에서 실행되므로 원본 경로 사용
                    nuitka_dir = __nuitka_binary_dir  # noqa: F821
                    exe_path = f'"{os.path.join(nuitka_dir, "감사장인쇄.exe")}"'
                elif sys.argv[0].endswith('.exe'):
                    exe_path = f'"{os.path.abspath(sys.argv[0])}"'
                else:
                    exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                winreg.SetValueEx(key, "감사장인쇄", 0, winreg.REG_SZ, exe_path)
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

        from app import app as flask_app, shutdown_callback_holder
        from werkzeug.serving import make_server

        port = int(self.port_var.get())
        try:
            self.http_server = make_server('0.0.0.0', port, flask_app)
        except OSError as e:
            messagebox.showerror("오류", f"서버 시작 실패: {e}")
            return

        # /quit 라우트가 호출할 콜백 등록 — Flask 워커 스레드에서 와도
        # Tk는 메인스레드에서만 안전하므로 root.after로 스케줄링.
        shutdown_callback_holder["callback"] = lambda: self.root.after(0, self._on_close)

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


def _port_in_use(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            return sock.connect_ex(('localhost', port)) == 0
    except Exception:
        return False


def _wait_port_free(port, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        if not _port_in_use(port):
            return True
        time.sleep(0.3)
    return False


def _find_pid_on_port(port):
    """netstat -ano로 해당 포트를 LISTENING 중인 PID 탐색.
    상태 컬럼이 한글 윈도우에서 '수신 대기 중'으로 나오는 것 때문에
    상태 문자열 대신 remote address가 0.0.0.0:0 / [::]:0 인 줄로 판단."""
    try:
        result = subprocess.run(
            ['netstat', '-ano', '-p', 'TCP'],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            local, remote = parts[1], parts[2]
            if not local.endswith(f':{port}'):
                continue
            if remote not in ('0.0.0.0:0', '[::]:0', '*:*'):
                continue
            try:
                return int(parts[-1])
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _get_process_name(pid):
    """tasklist로 PID의 실행파일명 조회."""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        if lines:
            parts = lines[0].split(',')
            if parts:
                return parts[0].strip('"')
    except Exception:
        pass
    return None


def _is_our_process(name):
    if not name:
        return False
    return name.lower() in ('감사장인쇄.exe', 'python.exe', 'pythonw.exe')


def _request_graceful_quit(port, timeout=2.0):
    try:
        r = requests.post(f'http://localhost:{port}/quit', timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _force_kill_port(port):
    """포트 점유 PID를 안전 검증 후 taskkill /F /T. 성공 시 True."""
    pid = _find_pid_on_port(port)
    if not pid:
        messagebox.showerror("오류", f"포트 {port}을(를) 점유한 프로세스를 찾을 수 없습니다.")
        return False
    name = _get_process_name(pid)
    if not _is_our_process(name):
        messagebox.showwarning(
            "강제 종료 불가",
            f"포트 {port}을(를) 사용 중인 프로세스가 감사장 인쇄 프로그램이 아닙니다.\n"
            f"프로세스: {name or '알 수 없음'} (PID: {pid})\n\n"
            f"안전을 위해 자동 종료하지 않습니다. 작업관리자에서 직접 확인해주세요."
        )
        return False
    try:
        subprocess.run(
            ['taskkill', '/F', '/T', '/PID', str(pid)],
            shell=False,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            timeout=5,
        )
        return True
    except Exception as e:
        messagebox.showerror("오류", f"강제 종료 실패: {e}")
        return False


def _show_duplicate_dialog(port):
    """3-버튼 다이얼로그. 'graceful' / 'force' / 'cancel' 반환."""
    root = tk.Tk()
    root.withdraw()

    dialog = tk.Toplevel(root)
    dialog.title("감사장 인쇄 서버 실행 중")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    w, h = 460, 200
    x = (dialog.winfo_screenwidth() - w) // 2
    y = (dialog.winfo_screenheight() - h) // 2
    dialog.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(
        dialog,
        text=f"감사장 인쇄 서버가 이미 실행 중입니다.\n(포트 {port} 사용 중)\n\n어떻게 하시겠습니까?",
        justify='center',
    ).pack(pady=(20, 10), padx=20)

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=10)

    result = {'value': 'cancel'}

    def choose(v):
        result['value'] = v
        dialog.destroy()

    tk.Button(btn_frame, text="정상 종료 후 시작", width=18,
              command=lambda: choose('graceful')).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="강제 종료 후 시작", width=18,
              command=lambda: choose('force')).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="취소", width=10,
              command=lambda: choose('cancel')).pack(side=tk.LEFT, padx=4)

    dialog.protocol("WM_DELETE_WINDOW", lambda: choose('cancel'))

    root.wait_window(dialog)
    root.destroy()
    return result['value']


def check_duplicate(port):
    """포트 점유 시 사용자에게 정상/강제 종료 옵션을 제시한다.
    정상 종료가 실패하면 강제 종료로 escalate 가능."""
    if not _port_in_use(port):
        return

    choice = _show_duplicate_dialog(port)

    if choice == 'cancel':
        sys.exit(0)

    if choice == 'graceful':
        if _request_graceful_quit(port) and _wait_port_free(port, timeout=5):
            return
        if not messagebox.askyesno(
            "정상 종료 실패",
            "이전 프로세스가 응답하지 않거나 포트가 해제되지 않았습니다.\n"
            "강제 종료할까요?"
        ):
            sys.exit(0)
        choice = 'force'

    if choice == 'force':
        if not _force_kill_port(port):
            sys.exit(1)
        if not _wait_port_free(port, timeout=5):
            messagebox.showerror("오류", "포트가 해제되지 않았습니다.\n잠시 후 다시 시도해주세요.")
            sys.exit(1)


if __name__ == '__main__':
    get_output_dir()  # data/output/ 보장 생성

    config = load_config()
    check_duplicate(config['port'])

    root = ctk.CTk()
    app = CertificateApp(root)

    root.after(500, app._start_server)
    root.mainloop()
