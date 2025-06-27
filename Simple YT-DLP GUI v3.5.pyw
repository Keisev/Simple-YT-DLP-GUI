# CREADO POR GEMINI Y v0 CON AYUDA DE KEISEV

import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess
import os
import json
import glob
import re
import shutil
import threading
import signal

# --- CHANGELOG ---
# v3.5

# - Corregido error al insertar subtítulos desde un archivo local: El programa ya no validará el idioma de los subtítulos si se selecciona un archivo local.
# - El programa ya no elimina todos los archivos .srt en el directorio del script
# - Eliminado código duplicado y redundante.

class YT_DLP_GUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.local_srt_path = None
        self.current_process = None

        # --- CONFIGURACIÓN DE LA VENTANA PRINCIPAL ---
        self.title("Simple YT-DLP GUI v3.5")
        self.geometry("1100x680")
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
        self.audio_source = ctk.StringVar(value="original")
        self.subtitle_type = ctk.StringVar(value="none")
        self.is_downloading = False

        # --- VARIABLES PARA OPCIONES DE SUBTÍTULOS ---
        self.burn_subtitles = ctk.BooleanVar(value=True)
        self.embed_subtitles = ctk.BooleanVar(value=False)

        # Lista de idiomas para la generación de subtítulos automáticos.
        self.AUTOMATIC_SUB_LANGUAGES = ['es', 'en', 'ja', 'pt', 'fr', 'de', 'it', 'ko', 'ru', 'zh-Hans']

        # --- INICIALIZAR LA INTERFAZ DE USUARIO ---
        self._create_widgets()

        # --- Variable para manejar el archivo de configuración y guardar la ruta ---
        self.config_file = "simpleytdlp_config.json"
        self.last_output_dir = "" # Guardará la ruta del config
        self._load_config()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        # --- Contenedor principal ---
        main_container = ctk.CTkFrame(self, fg_color=self.COLOR_MAIN_BG, corner_radius=0)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        main_container.grid_columnconfigure(0, weight=2)
        main_container.grid_columnconfigure(1, weight=3)
        main_container.grid_rowconfigure(0, weight=1)

        # --- PANEL IZQUIERDO ---
        left_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        # --- PANEL DERECHO (Registro de Actividad) ---
        right_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")

        # --- TÍTULO DE LA APLICACIÓN ---
        self._create_title_section(left_panel)

        # --- SECCIÓN: VIDEO PRINCIPAL ---
        self._create_video_section(left_panel)

        # --- SECCIÓN: FUENTE DE AUDIO ---
        self._create_audio_section(left_panel)
        
        # --- SECCIÓN: SUBTÍTULOS ---
        self._create_subtitles_section(left_panel)

        # --- SECCIÓN: DIRECTORIO DE SALIDA ---
        self._create_output_section(left_panel)

        # --- BOTONES DE ACCIÓN ---
        self._create_action_buttons(left_panel)

        # --- SECCIÓN: REGISTRO DE ACTIVIDAD (Panel derecho) ---
        self._create_log_section(right_panel)
        
        self.update_subtitle_type_ui()
        self.log_message("Listo para empezar. Introduce una URL y haz clic en 'Obtener Info'.", "info")

    def _create_title_section(self, parent):
        """Crea la sección del título de la aplicación"""
        title_frame = ctk.CTkFrame(parent, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(title_frame, text="Simple YT-DLP GUI", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Aplicación de escritorio para descargas avanzadas de YouTube con múltiples opciones para subtítulos. Salida siempre en .mp4", font=ctk.CTkFont(size=12)).pack(anchor="w")

    def _create_video_section(self, parent):
        """Crea la sección de video principal"""
        video_frame = self._create_section_frame(parent, "Video Principal")
        ctk.CTkLabel(video_frame, text="URL del video de YouTube para la imagen").pack(anchor="w", padx=10, pady=(10, 0))
        
        self.url_entry = ctk.CTkEntry(video_frame, placeholder_text="https://youtu.be/...", fg_color=self.COLOR_ENTRY_BG, height=35)
        self.url_entry.pack(fill="x", padx=10, pady=(5, 10), expand=True)

        self.info_button = ctk.CTkButton(video_frame, text="Obtener Info", command=self.fetch_video_info_thread)
        self.info_button.pack(anchor="e", padx=10, pady=(0, 10))

    def _create_audio_section(self, parent):
        """Crea la sección de fuente de audio"""
        audio_frame = self._create_section_frame(parent, "Fuente de Audio")
        audio_frame.grid_columnconfigure(0, weight=1)

        self.audio_orig_radio = ctk.CTkRadioButton(audio_frame, text="Usar audio del video original", variable=self.audio_source, value="original", command=self.on_audio_source_change)
        self.audio_orig_radio.grid(row=0, column=0, sticky="w", padx=10, pady=(10,5))
        
        self.audio_ext_radio = ctk.CTkRadioButton(audio_frame, text="Usar audio de otro video", variable=self.audio_source, value="external", command=self.on_audio_source_change)
        self.audio_ext_radio.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))
        
        self.audio_url_entry = ctk.CTkEntry(audio_frame, placeholder_text="URL del video para el audio", fg_color=self.COLOR_ENTRY_BG)

    def _create_subtitles_section(self, parent):
        """CORRECCIÓN DEFINITIVA: Crea la sección de subtítulos con separación clara de widgets"""
        subs_frame = self._create_section_frame(parent, "Subtítulos")
        subs_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Botones de tipo de subtítulo
        self.sub_none_btn = self._create_toggle_button(subs_frame, text="Sin subtítulos", value="none")
        self.sub_none_btn.grid(row=0, column=0, padx=5, pady=10, sticky="ew")

        self.sub_internal_btn = self._create_toggle_button(subs_frame, text="Internos", value="internal")
        self.sub_internal_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.sub_external_btn = self._create_toggle_button(subs_frame, text="Externos", value="external")
        self.sub_external_btn.grid(row=0, column=2, padx=5, pady=10, sticky="ew")
        
        self.sub_auto_btn = self._create_toggle_button(subs_frame, text="Automáticos", value="automatic")
        self.sub_auto_btn.grid(row=0, column=3, padx=5, pady=10, sticky="ew")

        # Contenedor de opciones que se oculta cuando no se necesita
        self.sub_options_container = ctk.CTkFrame(subs_frame, fg_color="transparent")

        # --- OPCIONES DE PROCESAMIENTO DE SUBTÍTULOS ---
        self.sub_processing_frame = ctk.CTkFrame(self.sub_options_container, fg_color="transparent")
        self.sub_processing_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.burn_subs_checkbox = ctk.CTkCheckBox(self.sub_processing_frame, text="Quemar Subtítulos", 
                                                  variable=self.burn_subtitles, command=self._on_subtitle_option_change)
        self.embed_subs_checkbox = ctk.CTkCheckBox(self.sub_processing_frame, text="Insertar Subtítulos", 
                                                   variable=self.embed_subtitles, command=self._on_subtitle_option_change)

        # CORRECCIÓN: Menú de idiomas INDEPENDIENTE para internos/automáticos
        self.sub_lang_menu_standalone = ctk.CTkOptionMenu(self.sub_options_container, values=["-"], state="disabled")

        # Campo de URL externa (solo para externos)
        self.sub_external_url_entry = ctk.CTkEntry(self.sub_options_container, placeholder_text="URL para subtítulos", fg_color=self.COLOR_ENTRY_BG)

        # CORRECCIÓN: Marco SOLO para externos con distribución original
        self.sub_menu_button_frame = ctk.CTkFrame(self.sub_options_container, fg_color="transparent")
        self.sub_menu_button_frame.grid_columnconfigure(0, weight=50)  # Menú más espacio (ORIGINAL)
        self.sub_menu_button_frame.grid_columnconfigure(1, weight=2)   # Botón archivo (ORIGINAL)
        self.sub_menu_button_frame.grid_columnconfigure(2, weight=1)   # Botón info (ORIGINAL)

        # Widgets SOLO para externos
        self.sub_lang_menu_external = ctk.CTkOptionMenu(self.sub_menu_button_frame, values=["-"], state="disabled")
        self.sub_file_button = ctk.CTkButton(self.sub_menu_button_frame, text="Desde archivo", command=self.toggle_subtitle_file)
        self.sub_fetch_button = ctk.CTkButton(self.sub_menu_button_frame, text="Info", width=60, command=self.fetch_external_sub_info_thread)

    def _create_output_section(self, parent):
        """Crea la sección de directorio de salida"""
        output_dir_frame = self._create_section_frame(parent, "Directorio de Salida")
        output_dir_frame.grid_columnconfigure(0, weight=1)
        
        self.dir_entry = ctk.CTkEntry(output_dir_frame, fg_color=self.COLOR_ENTRY_BG, height=35)
        self.dir_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        def set_initial_dir():
            # 1. Usar la ruta guardada si es válida
            if self.last_output_dir and os.path.isdir(self.last_output_dir):
                self.dir_entry.insert(0, self.last_output_dir)
            # 2. Si no, crear la nueva ruta por defecto
            else:
                default_path = os.path.join(os.path.expanduser("~"), "Videos", "YT-DLP")
                # Crear el directorio si no existe
                os.makedirs(default_path, exist_ok=True)
                self.dir_entry.insert(0, default_path)
        
        self.after(100, set_initial_dir)

        self.browse_button = ctk.CTkButton(output_dir_frame, text="Cambiar", width=80, command=self.browse_directory)
        self.browse_button.grid(row=0, column=1, padx=(0, 10), pady=10)

    def _create_action_buttons(self, parent):
        """Crea los botones de acción"""
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.pack(fill="x", pady=(20, 0))
        
        self.download_button = ctk.CTkButton(action_frame, text="Iniciar Descarga", height=45, font=ctk.CTkFont(size=14, weight="bold"),
                                             fg_color=self.COLOR_BUTTON_GREEN, hover_color="#1E8449", command=self.start_download_thread)
        self.download_button.pack(fill="x", expand=True)

    def _create_log_section(self, parent):
        """Crea la sección de registro de actividad"""
        log_frame = self._create_section_frame(parent, "Registro de Actividad")
        log_frame.pack(fill="both", expand=True)
        log_frame.grid_propagate(False)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        self.stop_button = ctk.CTkButton(log_frame, text="Parar", width=80, 
                                        fg_color=self.COLOR_BUTTON_RED, hover_color="#C0392B",
                                        command=self.stop_current_process)
        self.stop_button.place(relx=0.98, y=595, anchor="ne")

        self.activity_log = ctk.CTkTextbox(log_frame, wrap="word", font=("Consolas", 12), border_width=0, 
                                           fg_color=self.COLOR_LOG_BG, text_color=self.COLOR_LOG_DEFAULT)
        self.activity_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(40, 40))
        
        # Configuración de etiquetas para colores
        for tag, color in [("info", self.COLOR_LOG_INFO), ("error", self.COLOR_LOG_ERROR), 
                          ("warning", self.COLOR_LOG_WARNING), ("success", self.COLOR_LOG_SUCCESS)]:
            self.activity_log.tag_config(tag, foreground=color)

    def _create_section_frame(self, parent, title, **kwargs):
        """Crea un marco de sección con título"""
        frame = ctk.CTkFrame(parent, fg_color=self.COLOR_FRAME_BG, border_width=1, border_color=self.COLOR_BORDER, corner_radius=8, **kwargs)
        frame.pack(fill="x", pady=(10, 0), expand=True)
        title_label = ctk.CTkLabel(frame, text=f" {title} ", font=ctk.CTkFont(size=12, weight="bold"), 
                                   fg_color=self.COLOR_FRAME_BG, bg_color=self.COLOR_MAIN_BG)
        title_label.place(x=10, y=-9)
        return frame

    def _create_toggle_button(self, parent, text, value):
        """Crea un botón de alternancia para tipos de subtítulos"""
        return ctk.CTkButton(parent, text=text, command=lambda v=value: self.select_subtitle_type(v),
                             fg_color="transparent", border_width=1, border_color=self.COLOR_BORDER, hover_color=self.COLOR_BORDER)

    def _on_subtitle_option_change(self):
        """Maneja los cambios en las opciones de procesamiento de subtítulos"""
        # Asegurar que al menos una opción esté seleccionada
        if not self.burn_subtitles.get() and not self.embed_subtitles.get():
            self.burn_subtitles.set(True)
        
        burn_text = "Quemar Subtítulos" if self.burn_subtitles.get() else "Quemar Subtítulos"
        embed_text = "Insertar Subtítulos" if self.embed_subtitles.get() else "Insertar Subtítulos"
        
        self.burn_subs_checkbox.configure(text=burn_text)
        self.embed_subs_checkbox.configure(text=embed_text)

    def toggle_subtitle_file(self):
        """Alterna entre seleccionar un archivo de subtítulos y quitarlo"""
        if self.local_srt_path is None:
            self.select_subtitle_file()
        else:
            self.remove_subtitle_file()

    def select_subtitle_file(self):
        """Abre un diálogo para seleccionar un archivo de subtítulos .srt local"""
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
        """Quita el archivo de subtítulos seleccionado y restaura el estado original"""
        if self.local_srt_path:
            filename = os.path.basename(self.local_srt_path)
            self.local_srt_path = None
            self.sub_file_button.configure(text="Desde archivo")
            self.sub_external_url_entry.configure(state="normal")
            self.sub_lang_menu_external.configure(values=["-Pulsa Info-"], state="disabled")
            self.sub_fetch_button.configure(state="normal")
            self.log_message(f"Archivo de subtítulos removido: {filename}", "info")

    def stop_current_process(self):
        """Para el proceso actual en ejecución"""
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

    def log_message(self, message, level="default"):
        """Registra un mensaje en el log con el nivel especificado"""
        def _log():
            if self.activity_log.winfo_exists():
                tag = level.lower() if level.lower() in ["info", "error", "warning", "success"] else None
                self.activity_log.insert("end", message + "\n", tag)
                self.activity_log.see("end")
        if self.winfo_exists():
            self.after(0, _log)

    def browse_directory(self):
        """Abre el diálogo para seleccionar directorio de salida"""
        dir_path = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if dir_path:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, dir_path)

    def on_audio_source_change(self):
        """Maneja el cambio de fuente de audio"""
        if self.audio_source.get() == "external":
            self.audio_url_entry.grid(row=2, column=0, columnspan=1, sticky="ew", padx=10, pady=(0, 10))
        else:
            self.audio_url_entry.grid_forget()

    def select_subtitle_type(self, value):
        """Selecciona el tipo de subtítulo"""
        self.subtitle_type.set(value)
        self.update_subtitle_type_ui()

    def update_subtitle_type_ui(self):
        """CORRECCIÓN DEFINITIVA: Separación completa de widgets por tipo"""
        
        # PASO 1: Ocultar COMPLETAMENTE el contenedor de opciones
        self.sub_options_container.grid_forget()
        
        # PASO 2: Limpiar TODOS los widgets dentro del contenedor
        for widget in self.sub_options_container.winfo_children():
            widget.pack_forget()
            widget.grid_forget()

        # PASO 3: Actualizar apariencia de botones
        buttons = {"none": self.sub_none_btn, "internal": self.sub_internal_btn,
                   "external": self.sub_external_btn, "automatic": self.sub_auto_btn}
        for value, button in buttons.items():
            color = self.COLOR_BORDER if self.subtitle_type.get() == value else "transparent"
            button.configure(fg_color=color)
        
        sub_type = self.subtitle_type.get()
        
        # PASO 4: Solo mostrar opciones si NO es "none"
        if sub_type != "none":
            # Mostrar el contenedor de opciones
            self.sub_options_container.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))
            
            # Mostrar opciones de procesamiento SIEMPRE
            self.sub_processing_frame.pack(fill="x", pady=(10, 10))
            self.burn_subs_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.embed_subs_checkbox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            
            if sub_type in ["internal", "automatic"]:
                # CORRECCIÓN: Solo menú standalone, SIN frame de botones
                self.sub_lang_menu_standalone.pack(fill="x", pady=(0, 10))
                
                if sub_type == "internal":
                    self.update_internal_subs_menu()
                else:  # automatic
                    self.sub_lang_menu_standalone.configure(values=self.AUTOMATIC_SUB_LANGUAGES, state="normal")
                    if self.AUTOMATIC_SUB_LANGUAGES: 
                        self.sub_lang_menu_standalone.set(self.AUTOMATIC_SUB_LANGUAGES[0])
                        
            elif sub_type == "external":
                # CORRECCIÓN: Usar frame CON botones, distribución original
                self.sub_external_url_entry.pack(fill="x", pady=(0, 10))
                self.sub_menu_button_frame.pack(fill="x", expand=True, pady=(0, 10))
                
                # Posicionar widgets con distribución ORIGINAL
                self.sub_lang_menu_external.grid(row=0, column=0, padx=(0, 5), sticky="ew")
                self.sub_file_button.grid(row=0, column=1, padx=5)
                self.sub_fetch_button.grid(row=0, column=2, padx=0)
                
                # Configurar estado según archivo local
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
        """CORRECCIÓN: Actualiza el menú standalone para internos"""
        if not self.video_info:
            self.log_message("ERROR: Primero obtén la información del video principal.", "error")
            self.sub_lang_menu_standalone.configure(values=["-Sin Info-"], state="disabled")
            return
        
        subs = self.video_info.get("subtitles")
        if subs:
            langs = list(subs.keys())
            self.sub_lang_menu_standalone.configure(values=langs, state="normal")
            if langs: 
                self.sub_lang_menu_standalone.set(langs[0])
        else:
            self.log_message("INFO: El video principal no tiene subtítulos internos.", "info")
            self.sub_lang_menu_standalone.configure(values=["-No disponibles-"], state="disabled")

    def set_ui_state(self, is_busy):
        """Establece el estado de la interfaz (habilitada/deshabilitada)"""
        self.is_downloading = is_busy
        state = "disabled" if is_busy else "normal"
        
        widgets_to_toggle = [
            self.download_button, self.info_button, self.browse_button, self.url_entry,
            self.audio_orig_radio, self.audio_ext_radio, self.audio_url_entry,
            self.sub_none_btn, self.sub_internal_btn, self.sub_external_btn,
            self.sub_auto_btn, self.sub_lang_menu_standalone, self.sub_lang_menu_external, 
            self.sub_external_url_entry, self.dir_entry, self.burn_subs_checkbox, self.embed_subs_checkbox
        ]
        
        for widget in widgets_to_toggle:
            if widget.winfo_exists(): 
                widget.configure(state=state)
        
        if self.download_button.winfo_exists():
            self.download_button.configure(text="Descargando..." if is_busy else "Iniciar Descarga")

    def fetch_video_info_thread(self):
        """Inicia un hilo para obtener información del video"""
        url = self.url_entry.get()
        if not url:
            self.log_message("ERROR: Por favor, introduce una URL de video.", "error")
            return
        self.log_message(f"Obteniendo información de: {url}...", "info")
        self.set_ui_state(True)
        thread = threading.Thread(target=self.get_video_info, args=(url,), daemon=True)
        thread.start()

    def start_download_thread(self):
        """Inicia un hilo para la descarga"""
        if self.is_downloading:
            self.log_message("ERROR: Ya hay una descarga en progreso.", "error")
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
        """CORRECCIÓN: Recopila parámetros diferenciando entre archivo local y URL"""
        video_url = self.url_entry.get()
        if not video_url or not self.video_info: 
            raise ValueError("Obtén la información del video principal antes de descargar.")
        
        # Información de audio
        audio_type_val = self.audio_source.get()
        audio_url_val = self.audio_url_entry.get() if audio_type_val == "external" else video_url
        if audio_type_val == "external" and not audio_url_val: 
            raise ValueError("Debes proporcionar un URL para el audio externo.")
        audio_info = (audio_type_val.upper(), audio_url_val)
        
        # Información de subtítulos
        sub_type_val = "NONE"
        sub_lang_val = None
        sub_url_source_val = video_url # Por defecto es la URL principal

        if self.subtitle_type.get() != "none":
            sub_type_val = self.subtitle_type.get().upper()
            
            # CASO 1: Subtítulos externos DESDE ARCHIVO
            if self.subtitle_type.get() == "external" and self.local_srt_path:
                # Si hay un archivo local, el "idioma" es el nombre del archivo y no hay URL.
                # La validación de idioma no es necesaria.
                sub_lang_val = os.path.basename(self.local_srt_path)
                sub_url_source_val = None # No hay URL de origen
            
            # CASO 2: Subtítulos desde la web (Internos, Automáticos o Externos por URL)
            else:
                if self.subtitle_type.get() in ["internal", "automatic"]:
                    sub_lang_val = self.sub_lang_menu_standalone.get()
                else:  # external por URL
                    sub_lang_val = self.sub_lang_menu_external.get()
                
                # Validar que se haya seleccionado un idioma válido
                if not sub_lang_val or "-" in sub_lang_val: 
                    raise ValueError("No se ha seleccionado un idioma válido para los subtítulos.")
                
                # Validar que haya un URL si es externo
                if self.subtitle_type.get() == "external":
                    sub_url_source_val = self.sub_external_url_entry.get()
                    if not sub_url_source_val: 
                        raise ValueError("Debes proporcionar un URL para los subtítulos externos.")
        
        sub_info = (sub_type_val, sub_lang_val, sub_url_source_val)
        
        # Opciones de procesamiento de subtítulos
        subtitle_options = {
            'burn': self.burn_subtitles.get(),
            'embed': self.embed_subtitles.get()
        }
        
        # Directorio de salida y nombre de archivo
        output_dir = self.dir_entry.get()
        if not output_dir: 
            raise ValueError("El directorio de salida no puede estar vacío.")
        os.makedirs(output_dir, exist_ok=True)
        
        video_title = self.video_info.get("title", "video_sin_titulo")
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", video_title).strip() + ".mp4"
        final_filename = os.path.join(output_dir, sanitized_title)
        
        # Opciones de procesamiento de subtítulos
        subtitle_options = {
            'burn': self.burn_subtitles.get(),
            'embed': self.embed_subtitles.get()
        }
        
        # Directorio de salida y nombre de archivo
        output_dir = self.dir_entry.get()
        if not output_dir: 
            raise ValueError("El directorio de salida no puede estar vacío.")
        os.makedirs(output_dir, exist_ok=True)
        
        video_title = self.video_info.get("title", "video_sin_titulo")
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", video_title).strip() + ".mp4"
        final_filename = os.path.join(output_dir, sanitized_title)
        
        font = self.select_font(video_title)
        
        return video_url, audio_info, sub_info, subtitle_options, font, final_filename

    def get_video_info(self, url):
        """Obtiene información del video usando yt-dlp"""
        try:
            command = ["yt-dlp", "--dump-json", url]
            self.current_process = subprocess.run(command, capture_output=True, text=True, check=True, 
                                                encoding='utf-8', startupinfo=self._get_startup_info())
            self.video_info = json.loads(self.current_process.stdout)
            self.log_message(f"Información obtenida para: {self.video_info.get('title', 'Título desconocido')}", "success")
            if self.winfo_exists(): 
                self.after(0, self.update_internal_subs_menu)
        except Exception as e:
            self.log_message(f"Error al obtener información del video: {e}", "error")
            self.video_info = None
        finally:
            self.current_process = None
            if self.winfo_exists(): 
                self.after(0, self.set_ui_state, False)

    def select_font(self, title):
        """Selecciona la fuente basada en el título del video"""
        font_config = {
            "SDK_ES_Web": ["Zenless Zone Zero", "ゼンレスゾーンゼロ", "絕區零"],
            "SDK_SC_Web": ["Honkai Star Rail", "崩壊：スターレイル", "Honkai: Star Rail"],
            "HYWenHei-85W": ["Genshin Impact", "原神"]
        }
        
        self.log_message(f"\nBuscando fuente para el título: '{title}'", "info")
        for font, keywords in font_config.items():
            if any(keyword in title for keyword in keywords):
                self.log_message(f"Fuente encontrada: {font}", "info")
                return font
        self.log_message("No se detectó un juego específico. Se usará fuente por defecto.", "warning")
        return None
    
    def fetch_external_sub_info_thread(self):
        """Inicia un hilo para obtener información de subtítulos externos"""
        url = self.sub_external_url_entry.get()
        if not url:
            self.log_message("ERROR: Introduce un URL para los subtítulos externos.", "error")
            return
        self.log_message(f"Buscando subtítulos en: {url}", "info")
        self.set_ui_state(True)
        thread = threading.Thread(target=self._get_and_update_external_subs, args=(url,), daemon=True)
        thread.start()

    def _get_and_update_external_subs(self, url):
        """Obtiene y actualiza información de subtítulos externos"""
        try:
            command = ["yt-dlp", "--dump-json", "--no-warnings", url]
            self.current_process = subprocess.run(command, capture_output=True, text=True, check=True, 
                                                encoding='utf-8', startupinfo=self._get_startup_info())
            sub_info = json.loads(self.current_process.stdout)
            self.after(0, self._update_external_subs_menu, sub_info)
        except Exception as e:
            self.log_message(f"Error al obtener info de subtítulos: {e}", "error")
        finally:
            self.current_process = None
            if self.winfo_exists():
                self.after(0, self.set_ui_state, False)

    def _update_external_subs_menu(self, sub_info):
        """CORRECCIÓN: Actualiza el menú externo específico"""
        if not sub_info or "subtitles" not in sub_info or not sub_info["subtitles"]:
            self.log_message("ADVERTENCIA: El video externo no tiene subtítulos o el URL es inválido.", "warning")
            self.sub_lang_menu_external.configure(values=["-No encontrados-"], state="disabled")
            return
        
        langs = list(sub_info["subtitles"].keys())
        self.log_message(f"Subtítulos externos encontrados: {', '.join(langs)}", "success")
        self.sub_lang_menu_external.configure(values=langs, state="normal")
        if langs:
            self.sub_lang_menu_external.set(langs[0])

    def _get_startup_info(self):
        """Obtiene información de inicio para Windows"""
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return startupinfo
        return None

    def _run_command(self, command):
        """Ejecuta un comando y registra la salida, manteniendo referencia al proceso"""
        self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                              text=True, encoding='utf-8', errors='replace', 
                                              startupinfo=self._get_startup_info())
        for line in iter(self.current_process.stdout.readline, ''):
            level = "error" if "error" in line.lower() else "warning" if "warning" in line.lower() else "info"
            self.log_message(line.strip(), level)
        
        return_code = self.current_process.wait()
        self.current_process = None
        
        if return_code != 0: 
            raise subprocess.CalledProcessError(return_code, command)

    def download_and_process_video(self, video_url, audio_info, sub_info, subtitle_options, font_name, final_video_name):
        # Cambiar al directorio del script
        original_dir = os.getcwd()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        try:
            audio_type, audio_url = audio_info
            sub_type, sub_lang, sub_url_source = sub_info
            temp_files = {
                'video': "temp_video.mp4",
                'audio': "temp_audio.m4a", 
                'srt': "temp_subs.srt"
            }
            
            # Descargar video y audio
            self._download_video_audio(video_url, audio_url, temp_files)
            
            # Procesar subtítulos si es necesario
            srt_file_to_use = None
            if sub_type != "NONE":
                srt_file_to_use = self._process_subtitles(sub_type, sub_lang, sub_url_source, temp_files['srt'])
            
            # Combinar archivos con las opciones de subtítulos
            self._combine_files(temp_files, srt_file_to_use, subtitle_options, font_name, final_video_name)
            
            self.log_message(f"\n¡PROCESO COMPLETADO! Video guardado en:\n'{final_video_name}'", "success")

        except Exception as e:
            self.log_message(f"\nERROR DURANTE EL PROCESO: {e}", "error")
        finally:
            os.chdir(original_dir)
            self._cleanup_temp_files(script_dir)
            if self.winfo_exists(): 
                self.after(0, self.set_ui_state, False)

    def _download_video_audio(self, video_url, audio_url, temp_files):
        """Descarga video y audio por separado"""
        self.log_message(f"\n--- Descargando video ---", "info")
        self._run_command(["yt-dlp", "-f", "bestvideo[ext=mp4]", "-o", temp_files['video'], video_url])

        self.log_message(f"\n--- Descargando audio ---", "info")
        self._run_command(["yt-dlp", "-f", "bestaudio[ext=m4a]", "-o", temp_files['audio'], audio_url])

    def _process_subtitles(self, sub_type, sub_lang, sub_url_source, temp_srt_file):
        """Procesa los subtítulos según el tipo especificado"""
        if sub_type == "EXTERNAL" and self.local_srt_path and os.path.exists(self.local_srt_path):
            self.log_message(f"\n--- Usando subtítulo local ---", "info")
            try:
                shutil.copy(self.local_srt_path, temp_srt_file)
                self.log_message(f"Archivo '{os.path.basename(self.local_srt_path)}' copiado para procesar.", "success")
                return temp_srt_file
            except Exception as e:
                self.log_message(f"Error al copiar el archivo de subtítulos local: {e}", "error")
                return None
        
        elif sub_lang:
            self.log_message(f"\n--- Descargando subtítulos ({sub_type}: {sub_lang}) ---", "info")
            cmd = ["yt-dlp", "--skip-download", "--convert-subs", "srt", "--sub-langs", sub_lang]
            
            if sub_type == "AUTOMATIC":
                cmd.append("--write-auto-subs")
            else:
                cmd.append("--write-subs")
            cmd.append(sub_url_source)
            
            try:
                self._run_command(cmd)
                return self._find_and_rename_srt_file(sub_lang, temp_srt_file)
            except Exception as e:
                self.log_message(f"Fallo en la descarga de subtítulos: {e}", "error")
                return None
        
        return None

    def _find_and_rename_srt_file(self, sub_lang, temp_srt_file):
        """Busca y renombra el archivo SRT descargado"""
        possible_srt_files = []
        patterns = [f"*.{sub_lang}*.srt", f"*.{sub_lang.split('-')[0]}*.srt", "*.srt"]
        
        for pattern in patterns:
            possible_srt_files.extend(glob.glob(pattern))
        
        if possible_srt_files:
            possible_srt_files = sorted(set(possible_srt_files), key=len)
            selected_srt = possible_srt_files[0]
            shutil.move(selected_srt, temp_srt_file)
            self.log_message(f"Subtítulos encontrados: {selected_srt} -> {temp_srt_file}", "success")
            return temp_srt_file
        else:
            self.log_message(f"ADVERTENCIA: No se pudo encontrar el archivo de subtítulos '{sub_lang}'.", "warning")
            all_srt = glob.glob("*.srt")
            if all_srt:
                self.log_message(f"Archivos .srt encontrados: {', '.join(all_srt)}", "info")
            return None

    def _combine_files(self, temp_files, srt_file_to_use, subtitle_options, font_name, final_video_name):
        """Combina archivos de video, audio y subtítulos con las opciones especificadas"""
        self.log_message(f"\n--- Combinando archivos ---", "info")
        
        if os.path.exists(final_video_name): 
            os.remove(final_video_name)
        
        ffmpeg_cmd = ["ffmpeg", "-i", temp_files['video'], "-i", temp_files['audio']]
        
        # Procesar subtítulos según las opciones seleccionadas
        if srt_file_to_use and os.path.exists(srt_file_to_use):
            if subtitle_options['embed']:
                # Insertar subtítulos como pista separada
                ffmpeg_cmd.extend(["-i", srt_file_to_use])
                if subtitle_options['burn']:
                    # Tanto quemar como insertar
                    escaped_path = srt_file_to_use.replace('\\', '/').replace(':', '\\:')
                    style = f":force_style='Fontname={font_name},FontSize=20'" if font_name else ""
                    ffmpeg_cmd.extend(["-vf", f"subtitles='{escaped_path}'{style}", 
                                     "-c:a", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=spa"])
                    self.log_message("Aplicando subtítulos quemados E insertados", "info")
                else:
                    # Solo insertar
                    ffmpeg_cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", 
                                     "-metadata:s:s:0", "language=spa"])
                    self.log_message("Insertando subtítulos como pista separada", "info")
            elif subtitle_options['burn']:
                # Solo quemar subtítulos
                escaped_path = srt_file_to_use.replace('\\', '/').replace(':', '\\:')
                style = f":force_style='Fontname={font_name},FontSize=20'" if font_name else ""
                ffmpeg_cmd.extend(["-vf", f"subtitles='{escaped_path}'{style}", "-c:a", "copy"])
                self.log_message("Quemando subtítulos en el video", "info")
        else:
            # Sin subtítulos
            ffmpeg_cmd.extend(["-c:v", "copy", "-c:a", "copy"])
        
        ffmpeg_cmd.append(final_video_name)
        self._run_command(ffmpeg_cmd)
            
    def _cleanup_temp_files(self, script_dir):
        """Limpia archivos temporales en el directorio del script"""
        original_dir = os.getcwd()
        try:
            os.chdir(script_dir)
            self.log_message("\nLimpiando archivos temporales...", "info")
            patterns = ["temp_video.mp4", "temp_audio.m4a", "temp_subs.srt"]
            for pattern in patterns:
                for f in glob.glob(pattern):
                    try:
                        os.remove(f)
                        self.log_message(f"  Eliminado: {f}", "info")
                    except OSError as e:
                        self.log_message(f"Error al eliminar {f}: {e}", "warning")
        finally:
            os.chdir(original_dir)

    # --- Variables para Cargar, Guardar y Cerrar ruta de salida ---

    def _load_config(self):
        """Carga la configuración desde config.json si existe."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.last_output_dir = config.get("last_output_dir", "")
                    self.log_message("Configuración anterior cargada.", "info")
        except (json.JSONDecodeError, IOError) as e:
            self.log_message(f"No se pudo leer el archivo de configuración: {e}", "warning")
            self.last_output_dir = ""

    def _save_config(self):
        """Guarda el directorio de salida actual en config.json."""
        try:
            current_path = self.dir_entry.get()
            if current_path: # Solo guarda si hay algo en el campo
                config = {"last_output_dir": current_path}
                with open(self.config_file, 'w') as f:
                    json.dump(config, f, indent=4)
                self.log_message("Configuración guardada.", "info")
        except IOError as e:
            self.log_message(f"No se pudo guardar la configuración: {e}", "error")

    def on_closing(self):
        """Se ejecuta al cerrar la ventana para guardar la configuración."""
        self._save_config()
        self.destroy()

if __name__ == "__main__":
    app = YT_DLP_GUI()
    app.mainloop()