# CREADO POR IAs "Gemini 2.5 Pro", "v0-1.5-md", "DeepSeek R1" Y "ChatGPT o-4-mini" CON SUPERVISIÓN DE KEISEV
# EL CÓDIGO v3.6 FUE TESTEADO, REVISADO Y MEJORADO POR LA IA "v0-1.5-md" CON SUPERVISIÓN DE KEISEV PARA CREAR LA v3.7
# VERSIÓN v3.7 - MEJORAS EN LA SELECCIÓN DE PISTAS DE AUDIO Y LIMPIEZA DE LOGS

import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess
import os
import json
import glob
import re
from urllib.parse import urlparse
import shutil
import threading
import signal
import logging
from datetime import datetime
from contextlib import contextmanager

class YT_DLP_GUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.local_srt_path = None
        self.current_process = None

        # --- CONFIGURACIÓN DE LA VENTANA PRINCIPAL ---
        self.title("Simple YT-DLP GUI v3.7")
        self.geometry("1100x720") # Aumentado el alto para los nuevos widgets
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")

        # --- Colores de la interfaz ---
        self.COLOR_MAIN_BG = "#2e2345"
        self.COLOR_FRAME_BG = "#3a2d58"
        self.COLOR_BORDER = "#6a4c9c"
        self.COLOR_ENTRY_BG = "#2e2345"
        self.COLOR_BUTTON_GREEN = "#26A65B"
        self.COLOR_BUTTON_RED = "#E74C3C"
        self.COLOR_LOG_BG = "#2e2345"
        
        # --- Colores para el texto del registro ---
        self.COLOR_LOG_INFO = "#ADD8E6"
        self.COLOR_LOG_ERROR = "#FF6347"
        self.COLOR_LOG_WARNING = "#FFD700"
        self.COLOR_LOG_SUCCESS = "#32CD32"
        self.COLOR_LOG_DEFAULT = "lightgray"
        self.configure(fg_color=self.COLOR_MAIN_BG)

        # --- VARIABLES DE ESTADO ---
        self.video_info = None
        self.audio_source_type = ctk.StringVar(value="original") # 'original' o 'external'
        self.subtitle_type = ctk.StringVar(value="none")
        self.is_downloading = False
        self.original_audio_tracks = {} # {'label': 'format_id'}
        self.external_audio_tracks = {}

        # --- VARIABLES PARA OPCIONES DE SUBTÍTULOS ---
        self.burn_subtitles = ctk.BooleanVar(value=True)
        self.embed_subtitles = ctk.BooleanVar(value=False)
        
        # Lista de idiomas para la generación de subtítulos automáticos.
        self.AUTOMATIC_SUB_LANGUAGES = ['es', 'en', 'ja', 'pt', 'fr', 'de', 'it', 'ko', 'ru', 'zh-Hans']

        # --- CONFIGURAR LOGGING MEJORADO ---
        self.setup_logging()

        # --- VERIFICAR DEPENDENCIAS AL INICIO ---
        self.dependencies_ok = False

        # --- INICIALIZAR LA INTERFAZ DE USUARIO ---
        self._create_widgets()

        # --- Variable para manejar el archivo de configuración y guardar la ruta ---
        self.config_file = "simpleytdlp_config.json"
        self.last_output_dir = ""
        self._load_config()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- VERIFICAR DEPENDENCIAS DESPUÉS DE CREAR LA UI ---
        self.after(500, self.check_dependencies_delayed)

    def setup_logging(self):
        """Configura logging estructurado"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        self.log_file_path = 'yt_dlp_gui.log'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(self.log_file_path, mode='a', encoding='utf-8'), # 'a' para append durante la sesión
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def validate_youtube_url(self, url):
        """Valida si la URL es de YouTube válida"""
        if not url:
            return False
            
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+',
        ]
        
        return any(re.match(pattern, url, re.IGNORECASE) for pattern in youtube_patterns)

    def sanitize_filename(self, filename):
        """Sanitiza nombres de archivo para múltiples plataformas"""
        if not filename:
            return "video_sin_titulo"
            
        forbidden_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(forbidden_chars, '_', filename)
        sanitized = sanitized.strip()
        sanitized = sanitized.rstrip('.')
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        if not sanitized:
            sanitized = "video_sin_titulo"
        return sanitized

    @contextmanager
    def managed_process(self, command):
        """Context manager para manejo seguro de procesos"""
        process = None
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=self._get_startup_info()
            )
            self.current_process = process
            yield process
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.log_message("Proceso forzado a terminar", "warning")
            self.current_process = None

    def check_dependencies_delayed(self):
        """Verifica dependencias después de que la UI esté lista"""
        thread = threading.Thread(target=self.check_dependencies, daemon=True)
        thread.start()

    def check_dependencies(self):
        """Verifica que las dependencias estén instaladas"""
        self.log_message("Verificando dependencias...", "info")
        
        dependencies = {
            'yt-dlp': ['yt-dlp', '--version'],
            'ffmpeg': ['ffmpeg', '-version']
        }
        
        missing_deps = []
        for name, command in dependencies.items():
            try:
                subprocess.run(
                    command, 
                    capture_output=True, 
                    check=True, 
                    timeout=10,
                    startupinfo=self._get_startup_info()
                )
                self.log_message(f"✓ {name} encontrado", "success")
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                missing_deps.append(name)
                self.log_message(f"✗ {name} no encontrado", "error")
        
        if missing_deps:
            error_msg = f"Dependencias faltantes: {', '.join(missing_deps)}"
            self.log_message(error_msg, "error")
            self.log_message("Por favor instala las dependencias antes de continuar.", "error")
            
            def show_error():
                messagebox.showerror(
                    "Dependencias faltantes", 
                    f"{error_msg}\n\nPor favor instala las dependencias antes de continuar.\n\n"
                    f"yt-dlp: pip install yt-dlp\n"
                    f"ffmpeg: Descarga desde https://ffmpeg.org/"
                )
            
            if self.winfo_exists():
                self.after(0, show_error)
            
            self.dependencies_ok = False
        else:
            self.log_message("Todas las dependencias están disponibles", "success")
            self.dependencies_ok = True

    def log_message(self, message, level="info"):
        """Versión mejorada del logging con timestamps y archivo"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        if hasattr(self, 'logger'):
            log_method = getattr(self.logger, level.lower(), self.logger.info)
            log_method(message)
        
        def _log():
            if hasattr(self, 'activity_log') and self.activity_log.winfo_exists():
                tag = level.lower() if level.lower() in ["info", "error", "warning", "success"] else None
                self.activity_log.insert("end", formatted_message + "\n", tag)
                self.activity_log.see("end")
        
        if self.winfo_exists():
            self.after(0, _log)

    def _create_widgets(self):
        main_container = ctk.CTkFrame(self, fg_color=self.COLOR_MAIN_BG, corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        main_container.grid_columnconfigure(0, weight=2)
        main_container.grid_columnconfigure(1, weight=3)
        main_container.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        right_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")

        self._create_title_section(left_panel)
        self._create_video_section(left_panel)
        self._create_audio_section(left_panel)
        self._create_subtitles_section(left_panel)
        self._create_output_section(left_panel)
        self._create_action_buttons(left_panel)
        self._create_log_section(right_panel)
        
        self.update_audio_source_ui()
        self.update_subtitle_type_ui()
        self.log_message("Aplicación iniciada. Verificando dependencias...", "info")

    def _create_title_section(self, parent):
        title_frame = ctk.CTkFrame(parent, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(title_frame, text="Simple YT-DLP GUI v3.7", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Descargas avanzadas de YouTube con selección de pista de audio y subtítulos. Salida en .mp4", font=ctk.CTkFont(size=12)).pack(anchor="w")

    def _create_video_section(self, parent):
        video_frame = self._create_section_frame(parent, "Video Principal")
        ctk.CTkLabel(video_frame, text="URL del video de YouTube para la imagen").pack(anchor="w", padx=10, pady=(10, 0))
        
        self.url_entry = ctk.CTkEntry(video_frame, placeholder_text="https://youtu.be/...", fg_color=self.COLOR_ENTRY_BG, height=35)
        self.url_entry.pack(fill="x", padx=10, pady=(5, 10), expand=True)
        self.info_button = ctk.CTkButton(video_frame, text="Obtener Info", command=self.fetch_video_info_thread)
        self.info_button.pack(anchor="e", padx=10, pady=(0, 10))

    def _create_audio_section(self, parent):
        """Crea la nueva sección de fuente de audio"""
        audio_frame = self._create_section_frame(parent, "Fuente de Audio")
        audio_frame.grid_columnconfigure((0, 1), weight=1)

        # Botones de tipo de audio
        self.audio_orig_btn = self._create_toggle_button(audio_frame, text="Usar audio del video original", value="original", command=lambda v="original": self.select_audio_source(v))
        self.audio_orig_btn.grid(row=0, column=0, padx=5, pady=10, sticky="ew")
        
        self.audio_ext_btn = self._create_toggle_button(audio_frame, text="Usar audio de otro video", value="external", command=lambda v="external": self.select_audio_source(v))
        self.audio_ext_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        # Contenedor para opciones de audio
        self.audio_options_container = ctk.CTkFrame(audio_frame, fg_color="transparent")
        self.audio_options_container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)

        # --- Widgets para audio original ---
        self.audio_track_menu_original = ctk.CTkOptionMenu(self.audio_options_container, values=["-Sin Info-"], state="disabled")

        # --- Widgets para audio externo ---
        self.audio_external_frame = ctk.CTkFrame(self.audio_options_container, fg_color="transparent")
        self.audio_external_frame.grid_columnconfigure(0, weight=1)
        
        self.audio_url_entry = ctk.CTkEntry(self.audio_external_frame, placeholder_text="URL del video para el audio", fg_color=self.COLOR_ENTRY_BG)
        
        self.audio_external_controls_frame = ctk.CTkFrame(self.audio_external_frame, fg_color="transparent")
        self.audio_external_controls_frame.grid_columnconfigure(0, weight=1)
        
        self.audio_track_menu_external = ctk.CTkOptionMenu(self.audio_external_controls_frame, values=["-Pulsa Info-"], state="disabled")
        self.audio_fetch_button = ctk.CTkButton(self.audio_external_controls_frame, text="Info", width=60, command=self.fetch_external_audio_info_thread)

    def _create_subtitles_section(self, parent):
        subs_frame = self._create_section_frame(parent, "Subtítulos")
        subs_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.sub_none_btn = self._create_toggle_button(subs_frame, text="Sin subtítulos", value="none", command=lambda v="none": self.select_subtitle_type(v))
        self.sub_none_btn.grid(row=0, column=0, padx=5, pady=10, sticky="ew")
        self.sub_internal_btn = self._create_toggle_button(subs_frame, text="Internos", value="internal", command=lambda v="internal": self.select_subtitle_type(v))
        self.sub_internal_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.sub_external_btn = self._create_toggle_button(subs_frame, text="Externos", value="external", command=lambda v="external": self.select_subtitle_type(v))
        self.sub_external_btn.grid(row=0, column=2, padx=5, pady=10, sticky="ew")
        self.sub_auto_btn = self._create_toggle_button(subs_frame, text="Automáticos", value="automatic", command=lambda v="automatic": self.select_subtitle_type(v))
        self.sub_auto_btn.grid(row=0, column=3, padx=5, pady=10, sticky="ew")

        self.sub_options_container = ctk.CTkFrame(subs_frame, fg_color="transparent")
        self.sub_processing_frame = ctk.CTkFrame(self.sub_options_container, fg_color="transparent")
        self.sub_processing_frame.grid_columnconfigure((0, 1), weight=1)
        self.burn_subs_checkbox = ctk.CTkCheckBox(self.sub_processing_frame, text="Quemar Subtítulos", variable=self.burn_subtitles, command=self._on_subtitle_option_change)
        self.embed_subs_checkbox = ctk.CTkCheckBox(self.sub_processing_frame, text="Insertar Subtítulos", variable=self.embed_subtitles, command=self._on_subtitle_option_change)
        self.sub_lang_menu_standalone = ctk.CTkOptionMenu(self.sub_options_container, values=["-"], state="disabled")
        self.sub_external_url_entry = ctk.CTkEntry(self.sub_options_container, placeholder_text="URL para subtítulos", fg_color=self.COLOR_ENTRY_BG)
        self.sub_menu_button_frame = ctk.CTkFrame(self.sub_options_container, fg_color="transparent")
        self.sub_menu_button_frame.grid_columnconfigure(0, weight=50)
        self.sub_menu_button_frame.grid_columnconfigure(1, weight=2)
        self.sub_menu_button_frame.grid_columnconfigure(2, weight=1)
        self.sub_lang_menu_external = ctk.CTkOptionMenu(self.sub_menu_button_frame, values=["-"], state="disabled")
        self.sub_file_button = ctk.CTkButton(self.sub_menu_button_frame, text="Desde archivo", command=self.toggle_subtitle_file)
        self.sub_fetch_button = ctk.CTkButton(self.sub_menu_button_frame, text="Info", width=60, command=self.fetch_external_sub_info_thread)

    def _create_output_section(self, parent):
        output_dir_frame = self._create_section_frame(parent, "Directorio de Salida")
        output_dir_frame.grid_columnconfigure(0, weight=1)
        
        self.dir_entry = ctk.CTkEntry(output_dir_frame, fg_color=self.COLOR_ENTRY_BG, height=35)
        self.dir_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")

        def set_initial_dir():
            if self.last_output_dir and os.path.isdir(self.last_output_dir):
                self.dir_entry.insert(0, self.last_output_dir)
            else:
                default_path = os.path.join(os.path.expanduser("~"), "Videos", "YT-DLP")
                os.makedirs(default_path, exist_ok=True)
                self.dir_entry.insert(0, default_path)
        
        self.after(100, set_initial_dir)
        self.browse_button = ctk.CTkButton(output_dir_frame, text="Cambiar", width=80, command=self.browse_directory)
        self.browse_button.grid(row=0, column=1, padx=(0, 10), pady=10)

    def _create_action_buttons(self, parent):
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.pack(fill="x", pady=(20, 0))
        
        self.download_button = ctk.CTkButton(action_frame, text="Iniciar Descarga", height=45, font=ctk.CTkFont(size=14, weight="bold"),
                                             fg_color=self.COLOR_BUTTON_GREEN, hover_color="#1E8449", command=self.start_download_thread)
        self.download_button.pack(fill="x", expand=True)

    def _create_log_section(self, parent):
        log_frame = self._create_section_frame(parent, "Registro de Actividad")
        log_frame.pack(fill="both", expand=True)
        log_frame.grid_propagate(False)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        self.stop_button = ctk.CTkButton(log_frame, text="Parar", width=80, 
                                         fg_color=self.COLOR_BUTTON_RED, hover_color="#C0392B",
                                         command=self.stop_current_process)
        self.stop_button.place(relx=0.98, y=635, anchor="ne")

        self.activity_log = ctk.CTkTextbox(log_frame, wrap="word", font=("Consolas", 12), border_width=0, 
                                           fg_color=self.COLOR_LOG_BG, text_color=self.COLOR_LOG_DEFAULT)
        self.activity_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(40, 40))
        
        for tag, color in [("info", self.COLOR_LOG_INFO), ("error", self.COLOR_LOG_ERROR), 
                           ("warning", self.COLOR_LOG_WARNING), ("success", self.COLOR_LOG_SUCCESS)]:
            self.activity_log.tag_config(tag, foreground=color)

    def _create_section_frame(self, parent, title, **kwargs):
        frame = ctk.CTkFrame(parent, fg_color=self.COLOR_FRAME_BG, border_width=1, border_color=self.COLOR_BORDER, corner_radius=8, **kwargs)
        frame.pack(fill="x", pady=(10, 0), expand=True)
        title_label = ctk.CTkLabel(frame, text=f" {title} ", font=ctk.CTkFont(size=12, weight="bold"), 
                                   fg_color=self.COLOR_FRAME_BG, bg_color=self.COLOR_MAIN_BG)
        title_label.place(x=10, y=-9)
        return frame

    def _create_toggle_button(self, parent, text, value, command):
        return ctk.CTkButton(parent, text=text, command=command,
                             fg_color="transparent", border_width=1, border_color=self.COLOR_BORDER, hover_color=self.COLOR_BORDER)

    def _on_subtitle_option_change(self):
        if not self.burn_subtitles.get() and not self.embed_subtitles.get():
            self.burn_subtitles.set(True)
        
        self.burn_subs_checkbox.configure(text="Quemar Subtítulos" if self.burn_subtitles.get() else "Quemar Subtítulos")
        self.embed_subs_checkbox.configure(text="Insertar Subtítulos" if self.embed_subtitles.get() else "Insertar Subtítulos")

    def toggle_subtitle_file(self):
        if self.local_srt_path is None:
            self.select_subtitle_file()
        else:
            self.remove_subtitle_file()

    def select_subtitle_file(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo de subtítulos",
            filetypes=[("Archivos de Subtítulos", "*.srt"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            self.local_srt_path = filepath
            self.sub_file_button.configure(text="Quitar archivo")
            self.sub_external_url_entry.delete(0, "end")
            self.sub_external_url_entry.configure(state="disabled")
            self.sub_lang_menu_external.configure(values=[os.path.basename(filepath)], state="disabled")
            self.sub_fetch_button.configure(state="disabled")
            self.log_message(f"Subtítulo local seleccionado: {os.path.basename(filepath)}", "success")

    def remove_subtitle_file(self):
        if self.local_srt_path:
            filename = os.path.basename(self.local_srt_path)
            self.local_srt_path = None
            self.sub_file_button.configure(text="Desde archivo")
            self.sub_external_url_entry.configure(state="normal")
            self.sub_lang_menu_external.configure(values=["-Pulsa Info-"], state="disabled")
            self.sub_fetch_button.configure(state="normal")
            self.log_message(f"Archivo de subtítulos removido: {filename}", "info")

    def stop_current_process(self):
        if self.current_process and self.current_process.poll() is None:
            try:
                if os.name == 'nt':
                    self.current_process.terminate()
                else:
                    self.current_process.send_signal(signal.SIGTERM)
                self.log_message("Proceso interrumpido por el usuario", "warning")
            except Exception as e:
                self.log_message(f"Error al interrumpir el proceso: {e}", "error")
        else:
            self.log_message("No hay proceso activo para interrumpir", "info")
        
        if self.is_downloading:
            self.set_ui_state(False)

    def browse_directory(self):
        dir_path = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if dir_path:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, dir_path)

    def select_audio_source(self, value):
        """Selecciona el tipo de fuente de audio"""
        self.audio_source_type.set(value)
        self.update_audio_source_ui()

    def update_audio_source_ui(self):
        """Actualiza la UI de la sección de audio"""
        # Actualizar apariencia de botones
        buttons = {"original": self.audio_orig_btn, "external": self.audio_ext_btn}
        for value, button in buttons.items():
            color = self.COLOR_BORDER if self.audio_source_type.get() == value else "transparent"
            button.configure(fg_color=color)

        # Limpiar contenedor de opciones
        for widget in self.audio_options_container.winfo_children():
            widget.pack_forget()
            widget.grid_forget()

        source_type = self.audio_source_type.get()
        if source_type == "original":
            self.audio_track_menu_original.pack(fill="x", pady=(5, 10), expand=True)
        elif source_type == "external":
            self.audio_external_frame.pack(fill="x", expand=True)
            self.audio_url_entry.pack(fill="x", pady=(0, 10), expand=True)
            self.audio_external_controls_frame.pack(fill="x", expand=True)
            self.audio_track_menu_external.grid(row=0, column=0, sticky="ew", padx=(0, 5))
            self.audio_fetch_button.grid(row=0, column=1, sticky="e")

    def select_subtitle_type(self, value):
        self.subtitle_type.set(value)
        self.update_subtitle_type_ui()

    def update_subtitle_type_ui(self):
        self.sub_options_container.grid_forget()
        for widget in self.sub_options_container.winfo_children():
            widget.pack_forget()
            widget.grid_forget()

        buttons = {"none": self.sub_none_btn, "internal": self.sub_internal_btn,
                   "external": self.sub_external_btn, "automatic": self.sub_auto_btn}
        for value, button in buttons.items():
            color = self.COLOR_BORDER if self.subtitle_type.get() == value else "transparent"
            button.configure(fg_color=color)
        
        sub_type = self.subtitle_type.get()
        if sub_type != "none":
            self.sub_options_container.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))
            self.sub_processing_frame.pack(fill="x", pady=(10, 10))
            self.burn_subs_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.embed_subs_checkbox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            
            if sub_type in ["internal", "automatic"]:
                self.sub_lang_menu_standalone.pack(fill="x", pady=(0, 10))
                if sub_type == "internal":
                    self.update_internal_subs_menu()
                else:
                    self.sub_lang_menu_standalone.configure(values=self.AUTOMATIC_SUB_LANGUAGES, state="normal")
                    if self.AUTOMATIC_SUB_LANGUAGES: 
                        self.sub_lang_menu_standalone.set(self.AUTOMATIC_SUB_LANGUAGES[0])
            elif sub_type == "external":
                self.sub_external_url_entry.pack(fill="x", pady=(0, 10))
                self.sub_menu_button_frame.pack(fill="x", expand=True, pady=(0, 10))
                self.sub_lang_menu_external.grid(row=0, column=0, padx=(0, 5), sticky="ew")
                self.sub_file_button.grid(row=0, column=1, padx=5)
                self.sub_fetch_button.grid(row=0, column=2, padx=0)
                
                if self.local_srt_path:
                    self.sub_lang_menu_external.configure(values=[os.path.basename(self.local_srt_path)], state="disabled")
                    self.sub_file_button.configure(text="Quitar archivo")
                    self.sub_external_url_entry.configure(state="disabled")
                    self.sub_fetch_button.configure(state="disabled")
                else:
                    self.sub_lang_menu_external.configure(values=["-Pulsa Info-"], state="disabled")
                    self.sub_file_button.configure(text="Desde archivo")
                    self.sub_external_url_entry.configure(state="normal")
                    self.sub_fetch_button.configure(state="normal")

    def update_internal_subs_menu(self):
        if not self.video_info:
            self.log_message("ERROR: Primero obtén la información del video principal.", "error")
            self.sub_lang_menu_standalone.configure(values=["-Sin Info-"], state="disabled")
            return
        
        subs = self.video_info.get("subtitles")
        if subs:
            langs = list(subs.keys())
            self.sub_lang_menu_standalone.configure(values=langs, state="normal")
            if langs: self.sub_lang_menu_standalone.set(langs[0])
        else:
            self.log_message("INFO: El video principal no tiene subtítulos internos.", "info")
            self.sub_lang_menu_standalone.configure(values=["-No disponibles-"], state="disabled")

    def set_ui_state(self, is_busy):
        self.is_downloading = is_busy
        state = "disabled" if is_busy else "normal"
        
        widgets_to_toggle = [
            self.download_button, self.info_button, self.browse_button, self.url_entry,
            self.audio_orig_btn, self.audio_ext_btn, self.audio_url_entry, self.audio_fetch_button,
            self.sub_none_btn, self.sub_internal_btn, self.sub_external_btn,
            self.sub_auto_btn, self.sub_lang_menu_standalone, self.sub_lang_menu_external, 
            self.sub_external_url_entry, self.dir_entry, self.burn_subs_checkbox, 
            self.embed_subs_checkbox, self.audio_track_menu_original, self.audio_track_menu_external,
            self.sub_fetch_button, self.sub_file_button
        ]
        
        for widget in widgets_to_toggle:
            if widget.winfo_exists(): 
                widget.configure(state=state)
        
        if self.download_button.winfo_exists():
            self.download_button.configure(text="Descargando..." if is_busy else "Iniciar Descarga")

    def fetch_video_info_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            self.log_message("ERROR: Por favor, introduce una URL de video.", "error")
            return
        if not self.validate_youtube_url(url):
            self.log_message("ERROR: La URL no parece ser de YouTube válida.", "error")
            return
        if not self.dependencies_ok:
            self.log_message("ERROR: Las dependencias no están disponibles.", "error")
            return
            
        self.log_message(f"Obteniendo información de: {url}...", "info")
        self.set_ui_state(True)
        thread = threading.Thread(target=self.get_video_info, args=(url,), daemon=True)
        thread.start()

    def start_download_thread(self):
        if self.is_downloading:
            self.log_message("ERROR: Ya hay una descarga en progreso.", "error")
            return
        if not self.dependencies_ok:
            self.log_message("ERROR: Las dependencias no están disponibles.", "error")
            return
            
        try:
            params = self._gather_download_parameters()
        except ValueError as e:
            self.log_message(f"ERROR: {e}", "error")
            return
        
        self.log_message("--- INICIANDO DESCARGA ---", "info")
        self.set_ui_state(True)
        thread = threading.Thread(target=self.download_and_process_video, args=params, daemon=True)
        thread.start()

    def _gather_download_parameters(self):
        video_url = self.url_entry.get().strip()
        if not video_url or not self.video_info: 
            raise ValueError("Obtén la información del video principal antes de descargar.")
        if not self.validate_youtube_url(video_url):
            raise ValueError("La URL del video principal no es válida.")
        
        # Audio
        audio_type = self.audio_source_type.get()
        audio_url = video_url
        selected_track_label = ""
        audio_tracks_dict = {}

        if audio_type == "original":
            audio_tracks_dict = self.original_audio_tracks
            selected_track_label = self.audio_track_menu_original.get()
        else: # external
            audio_url = self.audio_url_entry.get().strip()
            if not audio_url or not self.validate_youtube_url(audio_url):
                raise ValueError("URL de audio externo no es válida.")
            audio_tracks_dict = self.external_audio_tracks
            selected_track_label = self.audio_track_menu_external.get()
        
        invalid_options = ["-Sin Info-", "-Pulsa Info-", "-No disponibles-"]
        if not selected_track_label or selected_track_label in invalid_options:
            raise ValueError("No se ha seleccionado una pista de audio válida.")
        
        audio_format_id = audio_tracks_dict.get(selected_track_label)
        if not audio_format_id:
            raise ValueError(f"No se encontró el ID para la pista de audio '{selected_track_label}'.")
        
        audio_info = (audio_url, audio_format_id)

        # Subtítulos
        sub_type = "NONE"
        sub_lang = None
        sub_url_source = video_url
        if self.subtitle_type.get() != "none":
            sub_type = self.subtitle_type.get().upper()
            
            if self.subtitle_type.get() == "external" and self.local_srt_path:
                sub_lang = os.path.basename(self.local_srt_path)
                sub_url_source = None
            else:
                if self.subtitle_type.get() in ["internal", "automatic"]:
                    sub_lang = self.sub_lang_menu_standalone.get()
                else: # external por URL
                    sub_lang = self.sub_lang_menu_external.get()
                
                if not sub_lang or "-" in sub_lang: 
                    raise ValueError("No se ha seleccionado un idioma válido para los subtítulos.")
                
                if self.subtitle_type.get() == "external":
                    sub_url_source = self.sub_external_url_entry.get().strip()
                    if not sub_url_source or not self.validate_youtube_url(sub_url_source):
                        raise ValueError("La URL de subtítulos externos no es válida.")
        
        sub_info = (sub_type, sub_lang, sub_url_source)
        subtitle_options = {'burn': self.burn_subtitles.get(), 'embed': self.embed_subtitles.get()}
        
        # Salida
        output_dir = self.dir_entry.get().strip()
        if not output_dir: raise ValueError("El directorio de salida no puede estar vacío.")
        os.makedirs(output_dir, exist_ok=True)
        
        video_title = self.video_info.get("title", "video_sin_titulo")
        sanitized_title = self.sanitize_filename(video_title) + ".mp4"
        final_filename = os.path.join(output_dir, sanitized_title)
        
        font = self.select_font(video_title)
        
        return video_url, audio_info, sub_info, subtitle_options, font, final_filename

    def get_video_info(self, url, is_external_audio=False):
        """Obtiene información del video y extrae pistas de audio."""
        try:
            command = ["yt-dlp", "--dump-json", url]
            result = subprocess.run(
                command, capture_output=True, text=True, check=True,
                encoding='utf-8', startupinfo=self._get_startup_info(), timeout=30
            )
            info = json.loads(result.stdout)
            
            if is_external_audio:
                self.after(0, self._update_audio_tracks, info, True)
            else:
                self.video_info = info
                self.log_message(f"Información obtenida para: {self.video_info.get('title', 'N/A')}", "success")
                self.after(0, self.update_internal_subs_menu)
                self.after(0, self._update_audio_tracks, info, False)

        except subprocess.TimeoutExpired:
            self.log_message("Error: Tiempo de espera agotado", "error")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Error en yt-dlp: {e.stderr or str(e)}", "error")
        except json.JSONDecodeError as e:
            self.log_message(f"Error al parsear JSON: {e}", "error")
        except Exception as e:
            self.log_message(f"Error inesperado: {e}", "error")
        finally:
            if self.winfo_exists(): self.after(0, self.set_ui_state, False)
            
    def _update_audio_tracks(self, info, is_external):
        """Extrae y actualiza los menús de pistas de audio."""
        tracks = {}
        if "formats" in info:
            for f in info["formats"]:
                # Filtra por pistas que solo contienen audio
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    label = f.get('format_note', f.get('format_id', 'unknown'))
                    if 'abr' in f: label += f" (~{f['abr']}k)"
                    # Evitar duplicados de etiquetas
                    if label in tracks:
                        label = f"{label} ({f.get('format_id')})"
                    tracks[label] = f.get('format_id')

        if not tracks:
            self.log_message("No se encontraron pistas de solo audio.", "warning")
            tracks = {"-No disponibles-": None}
        else:
            self.log_message(f"Detectadas pistas de audio: {list(tracks.keys())}", "success")

        if is_external:
            self.external_audio_tracks = tracks
            self.audio_track_menu_external.configure(values=list(tracks.keys()), state="normal")
            if tracks and "-No disponibles-" not in tracks:
                self.audio_track_menu_external.set(list(tracks.keys())[0])
        else:
            self.original_audio_tracks = tracks
            self.audio_track_menu_original.configure(values=list(tracks.keys()), state="normal")
            if tracks and "-No disponibles-" not in tracks:
                self.audio_track_menu_original.set(list(tracks.keys())[0])

    def select_font(self, title):
        font_config = {
            "SDK_ES_Web": ["Zenless Zone Zero", "ゼンレスゾーンゼロ", "絕區零"],
            "SDK_SC_Web": ["Honkai Star Rail", "崩壊：スターレイル", "Honkai: Star Rail"],
            "HYWenHei-85W": ["Genshin Impact", "原神"]
        }
        self.log_message(f"Buscando fuente para el título: '{title}'", "info")
        for font, keywords in font_config.items():
            if any(keyword in title for keyword in keywords):
                self.log_message(f"Fuente encontrada: {font}", "info")
                return font
        self.log_message("No se detectó un juego específico. Se usará fuente por defecto.", "warning")
        return None

    def fetch_external_audio_info_thread(self):
        """Inicia un hilo para obtener info de audio externo."""
        url = self.audio_url_entry.get().strip()
        if not url or not self.validate_youtube_url(url):
            self.log_message("ERROR: URL de audio externo no es válida.", "error")
            return
        
        self.log_message(f"Obteniendo pistas de audio de: {url}", "info")
        self.set_ui_state(True)
        thread = threading.Thread(target=self.get_video_info, args=(url, True), daemon=True)
        thread.start()

    def fetch_external_sub_info_thread(self):
        url = self.sub_external_url_entry.get().strip()
        if not url or not self.validate_youtube_url(url):
            self.log_message("ERROR: URL de subtítulos externos no es válida.", "error")
            return
            
        self.log_message(f"Buscando subtítulos en: {url}", "info")
        self.set_ui_state(True)
        thread = threading.Thread(target=self._get_and_update_external_subs, args=(url,), daemon=True)
        thread.start()

    def _get_and_update_external_subs(self, url):
        try:
            command = ["yt-dlp", "--dump-json", "--no-warnings", url]
            result = subprocess.run(
                command, capture_output=True, text=True, check=True, encoding='utf-8', 
                startupinfo=self._get_startup_info(), timeout=30
            )
            sub_info = json.loads(result.stdout)
            self.after(0, self._update_external_subs_menu, sub_info)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
            self.log_message(f"Error al obtener info de subtítulos: {e}", "error")
        finally:
            self.current_process = None
            if self.winfo_exists(): self.after(0, self.set_ui_state, False)

    def _update_external_subs_menu(self, sub_info):
        if not sub_info or "subtitles" not in sub_info or not sub_info["subtitles"]:
            self.log_message("ADVERTENCIA: El video externo no tiene subtítulos.", "warning")
            self.sub_lang_menu_external.configure(values=["-No encontrados-"], state="disabled")
            return
        
        langs = list(sub_info["subtitles"].keys())
        self.log_message(f"Subtítulos externos encontrados: {', '.join(langs)}", "success")
        self.sub_lang_menu_external.configure(values=langs, state="normal")
        if langs: self.sub_lang_menu_external.set(langs[0])

    def _get_startup_info(self):
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return startupinfo
        return None

    def _run_command(self, command):
        with self.managed_process(command) as process:
            for line in iter(process.stdout.readline, ''):
                if line:
                    level = "error" if "error" in line.lower() else "warning" if "warning" in line.lower() else "info"
                    self.log_message(line.strip(), level)
            
            return_code = process.wait()
            if return_code != 0: 
                raise subprocess.CalledProcessError(return_code, command)

    def download_and_process_video(self, video_url, audio_info, sub_info, subtitle_options, font_name, final_video_name):
        original_dir = os.getcwd()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        try:
            temp_files = {'video': "temp_video.mp4", 'audio': "temp_audio.m4a", 'srt': "temp_subs.srt"}
            self._download_video_audio(video_url, audio_info, temp_files)
            
            srt_file_to_use = None
            if sub_info[0] != "NONE":
                srt_file_to_use = self._process_subtitles(sub_info[0], sub_info[1], sub_info[2], temp_files['srt'])
            
            self._combine_files(temp_files, srt_file_to_use, subtitle_options, font_name, final_video_name)
            self.log_message(f"\n¡PROCESO COMPLETADO! Video guardado en:\n'{final_video_name}'", "success")
        except Exception as e:
            self.log_message(f"\nERROR DURANTE EL PROCESO: {e}", "error")
        finally:
            self._cleanup_temp_files()
            os.chdir(original_dir)
            if self.winfo_exists(): self.after(0, self.set_ui_state, False)

    def _download_video_audio(self, video_url, audio_info, temp_files):
        audio_url, audio_format_id = audio_info
        self.log_message(f"\n--- Descargando video ---", "info")
        self._run_command(["yt-dlp", "-f", "bestvideo[vcodec^=avc][ext=mp4]", "-o", temp_files['video'], video_url])
        self.log_message(f"\n--- Descargando audio (Pista: {audio_format_id}) ---", "info")
        self._run_command(["yt-dlp", "-f", audio_format_id, "-o", temp_files['audio'], audio_url])

    def _process_subtitles(self, sub_type, sub_lang, sub_url_source, temp_srt_file):
        if sub_type == "EXTERNAL" and self.local_srt_path and os.path.exists(self.local_srt_path):
            self.log_message(f"\n--- Usando subtítulo local ---", "info")
            try:
                shutil.copy(self.local_srt_path, temp_srt_file)
                self.log_message(f"Archivo '{os.path.basename(self.local_srt_path)}' copiado.", "success")
                return temp_srt_file
            except Exception as e:
                self.log_message(f"Error al copiar subtítulo local: {e}", "error")
                return None
        elif sub_lang:
            self.log_message(f"\n--- Descargando subtítulos ({sub_type}: {sub_lang}) ---", "info")
            cmd = ["yt-dlp", "--skip-download", "--convert-subs", "srt", "--sub-langs", sub_lang]
            cmd.append("--write-auto-subs" if sub_type == "AUTOMATIC" else "--write-subs")
            cmd.append(sub_url_source)
            
            try:
                os.makedirs("temp_subs_dir", exist_ok=True)
                self._run_command(cmd + ["-P", "temp_subs_dir"])
                return self._find_and_rename_srt_file(sub_lang, temp_srt_file, "temp_subs_dir")
            except Exception as e:
                self.log_message(f"Fallo en descarga de subtítulos: {e}", "error")
                return None
        return None

    def _find_and_rename_srt_file(self, sub_lang, temp_srt_file, search_dir="."):
        patterns = [f"*.{sub_lang}*.srt", f"*.{sub_lang.split('-')[0]}*.srt", "*.srt"]
        for pattern in patterns:
            full_pattern = os.path.join(search_dir, pattern)
            possible_srt_files = glob.glob(full_pattern)
            
            if possible_srt_files:
                possible_srt_files.sort(key=os.path.getmtime, reverse=True)
                selected_srt = possible_srt_files[0]
                shutil.move(selected_srt, temp_srt_file)
                if search_dir != ".": shutil.rmtree(search_dir, ignore_errors=True)
                self.log_message(f"Subtítulos procesados: {os.path.basename(selected_srt)}", "success")
                return temp_srt_file
        
        self.log_message(f"ADVERTENCIA: No se encontraron subtítulos para '{sub_lang}'", "warning")
        if search_dir != ".": shutil.rmtree(search_dir, ignore_errors=True)
        return None

    def _combine_files(self, temp_files, srt_file_to_use, subtitle_options, font_name, final_video_name):
        self.log_message(f"\n--- Combinando archivos ---", "info")
        if os.path.exists(final_video_name): os.remove(final_video_name)
        
        ffmpeg_cmd = ["ffmpeg", "-i", temp_files['video'], "-i", temp_files['audio']]
        
        if srt_file_to_use and os.path.exists(srt_file_to_use):
            if subtitle_options['embed']:
                ffmpeg_cmd.extend(["-i", srt_file_to_use])
                if subtitle_options['burn']: # Quemar y insertar
                    escaped_path = srt_file_to_use.replace('\\', '/').replace(':', '\\:')
                    style = f":force_style='Fontname={font_name},FontSize=20'" if font_name else ""
                    ffmpeg_cmd.extend(["-vf", f"subtitles='{escaped_path}'{style}", "-c:a", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=spa"])
                    self.log_message("Aplicando subtítulos quemados E insertados", "info")
                else: # Solo insertar
                    ffmpeg_cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=spa"])
                    self.log_message("Insertando subtítulos como pista separada", "info")
            elif subtitle_options['burn']: # Solo quemar
                escaped_path = srt_file_to_use.replace('\\', '/').replace(':', '\\:')
                style = f":force_style='Fontname={font_name},FontSize=20'" if font_name else ""
                ffmpeg_cmd.extend(["-vf", f"subtitles='{escaped_path}'{style}", "-c:a", "copy"])
                self.log_message("Quemando subtítulos en el video", "info")
        else:
            ffmpeg_cmd.extend(["-c:v", "copy", "-c:a", "copy"])
        
        ffmpeg_cmd.append(final_video_name)
        self._run_command(ffmpeg_cmd)

    def _cleanup_temp_files(self):
        self.log_message("\nLimpiando archivos temporales...", "info")
        temp_files_pattern = "temp_*.*"
        files_to_delete = glob.glob(temp_files_pattern)
        for f in files_to_delete:
            try:
                os.remove(f)
                self.log_message(f"  Eliminado archivo: {f}", "info")
            except OSError as e:
                self.log_message(f"Error al eliminar archivo {f}: {e}", "warning")

        temp_dir = "temp_subs_dir"
        if os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                self.log_message(f"  Eliminado directorio: {temp_dir}", "info")
            except OSError as e:
                self.log_message(f"Error al eliminar directorio {temp_dir}: {e}", "warning")

        if not files_to_delete and not os.path.isdir(temp_dir):
            self.log_message("No se encontraron elementos temporales para limpiar.", "info")

    def _load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.last_output_dir = config.get("last_output_dir", "")
                    self.log_message("Configuración anterior cargada.", "info")
        except (json.JSONDecodeError, IOError) as e:
            self.log_message(f"No se pudo leer el archivo de configuración: {e}", "warning")
            self.last_output_dir = ""

    def _save_config(self):
        try:
            current_path = self.dir_entry.get()
            if current_path:
                config = {"last_output_dir": current_path}
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                self.log_message("Configuración guardada.", "info")
        except IOError as e:
            self.log_message(f"No se pudo guardar la configuración: {e}", "error")
            
    def _clear_log_file(self):
        """Borra el contenido del archivo de log."""
        try:
            # Cierra cualquier manejador de archivo existente
            for handler in self.logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
            # Trunca el archivo
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                pass # Simplemente abrir en modo 'w' y cerrar lo vacía
            self.log_message("Archivo de registro limpiado al cerrar.", "info")
        except Exception as e:
            # No podemos usar log_message aquí si el logger está cerrado, imprimimos a consola
            print(f"Error al limpiar el archivo de log: {e}")

    def on_closing(self):
        self._save_config()
        self._clear_log_file() # Limpiar el log antes de destruir la ventana
        self.destroy()

if __name__ == "__main__":
    app = YT_DLP_GUI()
    app.mainloop()
