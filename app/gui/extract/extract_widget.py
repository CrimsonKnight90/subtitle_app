from pathlib import Path
from datetime import datetime
import winsound

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QProgressBar,
    QTextEdit, QLabel, QFileDialog, QMessageBox, QHBoxLayout,
    QSplitter, QSizePolicy, QDialog, QInputDialog
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize, QThread, Signal

from app.gui.extract.video_tree_widget import VideoTreeWidget
from app.gui.extract.workers import BatchWorker
from app.services.settings import get_settings, save_config
from app.services.translations import TRANSLATIONS


def get_translator():
    S = get_settings()
    lang = S.config.get("ui_language", "es")
    return lambda key: TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


class ExtractWidget(QWidget):
    # Señales para que MainWindow gestione cosas globales
    request_menu_rebuild = Signal()
    request_title_change = Signal(str)

    processing_started = Signal()
    processing_finished = Signal()


    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)

        # Ruta base de iconos
        self.icon_path = Path("app/assets/icons")
        self.t = get_translator()
        self.selected_folder: Path | None = None

        # Estado inicial
        self.status_label = QLabel(self.t("ready_to_start"))
        main_layout.addWidget(self.status_label)

        # Botones superiores
        row = QHBoxLayout()

        self.btn_pick = QPushButton(QIcon(str(self.icon_path / "folder.svg")), self.t("select_folder"))
        self.btn_pick.setObjectName("PrimaryButton")
        self.btn_pick.setIconSize(QSize(20, 20))
        self.btn_pick.clicked.connect(self.pick_folder)
        row.addWidget(self.btn_pick)

        self.btn_extract = QPushButton(QIcon(str(self.icon_path / "extract.svg")), self.t("extract_selected"))
        self.btn_extract.setObjectName("PrimaryButton")
        self.btn_extract.setIconSize(QSize(20, 20))
        self.btn_extract.setEnabled(True)
        self.btn_extract.clicked.connect(self.start_batch)
        row.addWidget(self.btn_extract)

        self.btn_stop = QPushButton(QIcon(str(self.icon_path / "stop.svg")), self.t("stop"))
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setIconSize(QSize(20, 20))
        self.btn_stop.setEnabled(False)  # 🔹 deshabilitado por defecto
        self.btn_stop.clicked.connect(self.stop_batch)
        row.addWidget(self.btn_stop)

        main_layout.addLayout(row)

        # Botón de configuración
        self.btn_config = QPushButton(QIcon(str(self.icon_path / "settings.svg")), self.t("settings"))
        self.btn_config.setObjectName("PrimaryButton")
        self.btn_config.setIconSize(QSize(20, 20))
        self.btn_config.clicked.connect(self.open_settings_dialog)
        main_layout.addWidget(self.btn_config)

        # Mensaje de ayuda
        info_row = QHBoxLayout()
        self.info_icon_label = QLabel()
        self.info_icon_label.setPixmap(QIcon(str(self.icon_path / "idea.svg")).pixmap(20, 20))
        self.info_text_label = QLabel(self.t("videos_drag_hint"))
        info_row.addWidget(self.info_icon_label)
        info_row.addWidget(self.info_text_label)
        info_row.addStretch()
        main_layout.addLayout(info_row)

        # Árbol de videos/subtítulos
        self.tree = VideoTreeWidget(self)
        self.tree.status.connect(self._status_msg)
        self.tree.status.connect(self._on_status)

        # Idioma preferido
        S = get_settings()
        if S.config.get("preferred_lang"):
            VideoTreeWidget.last_selected_lang = S.config["preferred_lang"]
        self.tree.last_lang_changed.connect(self._on_lang_changed)

        # Conectar atajo Ctrl+Shift+E a start_batch
        for a in self.tree.actions():
            if hasattr(a, "shortcut") and a.shortcut().toString() == "Ctrl+Shift+E":
                a.triggered.connect(self.start_batch)

        # Área de log
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Splitter para árbol y log
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.log_area)
        splitter.setSizes([500, 120])
        main_layout.addWidget(splitter)

        # Barra de progreso
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress.setObjectName("MainProgressBar")
        main_layout.addWidget(self.progress)

        # 🔹 Traducciones iniciales
        self._apply_translations()

    # ------------------ Eventos UI ------------------
    def _status_msg(self, s: str):
        self.status_label.setText(s)
        self.log_area.append(s)

    def _on_status(self, msg: str):
        if msg == "add_files":
            S = get_settings()
            last_dir = S.config.get("last_extract_dir", "")

            files, _ = QFileDialog.getOpenFileNames(
                self,
                self.t("select_video_files"),
                last_dir,
                self.t("video_files_filter")
            )
            if files:
                paths = [Path(f) for f in files]
                # Guardar carpeta del primer archivo
                S.config["last_extract_dir"] = str(paths[0].parent)
                S.save()

                if self.selected_folder is None and paths:
                    self.selected_folder = paths[0].parent
                    self.status_label.setText(f"{self.t('folder')}: {self.selected_folder}")
                self.tree.add_videos(paths)
        else:
            self._status_msg(msg)

    def pick_folder(self):
        S = get_settings()
        last_dir = S.config.get("last_extract_dir", "")

        folder = QFileDialog.getExistingDirectory(
            self,
            self.t("select_root_folder"),
            last_dir
        )
        if folder:
            self.selected_folder = Path(folder)
            # Guardar última carpeta
            S.config["last_extract_dir"] = str(self.selected_folder)
            S.save()

            self.status_label.setText(f"{self.t('folder')}: {self.selected_folder}")
            videos = []
            for ext in (".mkv", ".mp4", ".avi", ".mov"):
                videos.extend(self.selected_folder.glob(f"*{ext}"))
            if videos:
                self.tree.add_videos(videos)
            else:
                self.status_label.setText(self.t("no_videos_found"))

    def _progress_gui(self, done: int, total: int, message: str):
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        self.log_area.append(message)
        self.status_label.setText(f"[{done}/{total}] {message}")

        if "✅" in message:
            color = "#4CAF50"
        elif "⚠️" in message:
            color = "#FFC107"
        elif "❌" in message:
            color = "#F44336"
        else:
            color = "#2196F3"

        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #555;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                font-size: 14px;
                color: #fff;
                background-color: #2b2b2b;
            }}
            QProgressBar::chunk {{
                border-radius: 8px;
                background-color: {color};
            }}
        """)

    # ------------------ Método para parar el proceso ------------------
    def stop_batch(self):
        if hasattr(self, "worker") and self.worker:
            self.worker.stop()
            self.log_area.append("⏹ " + self.t("process_stopped"))
            self.status_label.setText("⏹ " + self.t("process_stopped"))

    def _on_finished(self, stats: dict):
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        resumen = (
            f"{self.t('processed')}: {stats['total']}\n"
            f"✅ {self.t('success')}: {stats['ok']}\n"
            f"⚠️ {self.t('skipped')}: {stats['skip']}\n"
            f"❌ {self.t('errors')}: {stats['error']}"
        )
        QMessageBox.information(self, self.t("final_summary"), resumen)
        self.log_area.append("🎉 " + self.t("processing_completed") + "\n" + resumen)
        self.status_label.setText("✅ " + self.t("ready_to_start"))
        self._progress_gui(stats['total'], stats['total'], "✅ " + self.t("completed"))

        # Guardar log
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"extraccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"{self.t('date')}: {datetime.now()}\n")
            f.write(resumen + "\n\n")
            f.write(self.log_area.toPlainText())
        self.log_area.append(f"📝 {self.t('log_saved_to')}: {log_file}")

        # 🔹 Rehabilitar botones
        self.btn_pick.setEnabled(True)
        self.btn_extract.setEnabled(True)
        self.btn_config.setEnabled(True)
        self.btn_stop.setEnabled(False)  # 🔹 deshabilitar botón de parada

        # 🔹 Emitir señal de fin
        self.processing_finished.emit()

    def start_batch(self):
        selected_tracks = self.tree.collect_selection()
        if not selected_tracks:
            QMessageBox.information(self, self.t("no_selection"), self.t("no_tracks_marked"))
            return

        # 🔹 Emitir señal de inicio
        self.processing_started.emit()
        # 🔹 Deshabilitar botones mientras trabaja
        self.btn_pick.setEnabled(False)
        self.btn_extract.setEnabled(False)
        self.btn_config.setEnabled(False)
        self.btn_stop.setEnabled(True)  # 🔹 habilitar botón de parada

        self.thread = QThread()
        self.worker = BatchWorker(self.selected_folder or Path.cwd(), selected_tracks=selected_tracks)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress_gui)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _mostrar_manual(self):
        QMessageBox.information(
            self,
            self.t("manual_title"),
            self.t("manual_message")
        )

    def _cambiar_idioma(self, lang_code):
        S = get_settings()
        S.config["ui_language"] = lang_code
        save_config(S.config)

        self.t = get_translator()
        self.tree.set_ui_language(lang_code)
        self._apply_translations()

        # Avisamos a MainWindow para que reconstruya el menú y cambie título
        self.request_menu_rebuild.emit()
        self.request_title_change.emit(self.t("app_title"))

        QMessageBox.information(
            self,
            self.t("interface_language"),
            f"{self.t('interface_language')} → "
            f"{self.t({'es': 'spanish', 'en': 'english', 'fr': 'french'}[lang_code])}"
        )

    def _apply_translations(self):
        # Actualiza textos de la UI
        self.status_label.setText(self.t("ready_to_start"))

        self.btn_pick.setIcon(QIcon(str(self.icon_path / "folder.svg")))
        self.btn_pick.setText(self.t("select_folder"))

        self.btn_extract.setIcon(QIcon(str(self.icon_path / "extract.svg")))
        self.btn_extract.setText(self.t("extract_selected"))

        # 🔹 Nuevo: traducir botón Parar
        self.btn_stop.setIcon(QIcon(str(self.icon_path / "stop.svg")))
        self.btn_stop.setText(self.t("stop"))

        self.btn_config.setIcon(QIcon(str(self.icon_path / "settings.svg")))
        self.btn_config.setText(self.t("settings"))

        self.info_icon_label.setPixmap(QIcon(str(self.icon_path / "idea.svg")).pixmap(20, 20))
        self.info_text_label.setText(self.t("videos_drag_hint"))

        self.tree.apply_translations()

    def _on_lang_changed(self, lang: str):
        S = get_settings()
        S.config["preferred_lang"] = lang
        save_config(S.config)
        self.log_area.append(f"🌐 {self.t('preferred_language_saved')}: {lang}")

        # ------------------ Configuración ------------------

    def open_settings_dialog(self):
        S = get_settings()
        dlg = QDialog(self)
        dlg.setWindowTitle(self.t("output_settings"))
        dlg.setWindowIcon(QIcon(str(self.icon_path / "settings.svg")))

        layout = QVBoxLayout(dlg)

        btn_style = """
                    QPushButton {
                        padding: 8px;
                        text-align: left;
                        font-size: 14px;
                        border: 1px solid #444;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: rgba(30, 136, 229, 0.15);
                    }
                """

        btn_default = QPushButton(QIcon(str(self.icon_path / "folder-subtitles.svg")), self.t("output_default"))
        btn_same = QPushButton(QIcon(str(self.icon_path / "folder-video.svg")), self.t("output_same"))
        btn_same_sub = QPushButton(QIcon(str(self.icon_path / "folder-subdir.svg")), self.t("output_same_sub"))
        btn_custom = QPushButton(QIcon(str(self.icon_path / "folder-custom.svg")), self.t("output_custom"))

        for btn in (btn_default, btn_same, btn_same_sub, btn_custom):
            btn.setStyleSheet(btn_style)
            btn.setIconSize(QSize(20, 20))
            layout.addWidget(btn)

        btn_default.clicked.connect(lambda: self._set_output_mode(S, "default", dlg))
        btn_same.clicked.connect(lambda: self._set_output_mode(S, "same", dlg))
        btn_same_sub.clicked.connect(lambda: self._set_same_subdir(S, dlg))
        btn_custom.clicked.connect(lambda: self._set_custom_folder(S, dlg))

        dlg.exec()

    def _set_output_mode(self, S, mode, dlg):
        S.config["output_mode"] = mode
        save_config(S.config)
        dlg.accept()

    def _set_same_subdir(self, S, dlg):
        name, ok = QInputDialog.getText(
            self,
            self.t("subfolder_name_title"),
            self.t("subfolder_name_prompt"),
            text=self.t("subfolder_name_default")
        )
        if ok and name.strip():
            S.config["output_mode"] = "same_subdir"
            S.config["same_subdir_name"] = name.strip()
            save_config(S.config)
            dlg.accept()

    def _set_custom_folder(self, S, dlg):
        folder = QFileDialog.getExistingDirectory(self, self.t("select_output_folder"))
        if folder:
            S.config["output_mode"] = "custom"
            S.config["custom_output_base"] = folder
            save_config(S.config)
            dlg.accept()

    def retranslate_ui(self):
        self.t = get_translator()
        self.table.setHorizontalHeaderLabels([
            self.t("title") if "title" in dir(self.t) else "Archivo",
            "Formato", self.t("completed"), self.t("menu_translate"),
            self.t("source_lang"), self.t("target_lang"), "%"
        ])
        self.btn_add.setText(self.t("add_subtitles"))
        self.btn_translate.setText(self.t("start"))
        self.btn_cancel.setText(self.t("cancel"))

