# app\gui\translate\translation_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QProgressBar, QGroupBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QAbstractItemView, QMenu,
    QToolBar, QHeaderView
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon
from app.services.i18n import get_translator
import os
from pathlib import Path
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # resultados consistentes
class TranslationWidget(QWidget):
    request_translation = Signal(list, str, str, str)  # paths, src, dst, engine
    cancel_translation = Signal()

    processing_started = Signal()
    processing_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.t = get_translator()
        self.icon_path = Path("app/assets/icons")  # 🔹 define la ruta base de iconos
        self._files = []  # list of dict: {path, fmt, status, engine, src, dst, progress}
        self._setup_ui()
        self._wire()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(15, 15, 15, 15)
        main.setSpacing(12)

        # --- Barra de herramientas superior para configuración ---
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self.cmb_source = QComboBox()
        self.cmb_target = QComboBox()

        self.langs = {
            "Auto (detectar)": "auto",
            "Inglés": "en",
            "Español": "es",
            "Francés": "fr",
            "Alemán": "de",
            "Coreano": "ko",
            "Chino (Simplificado)": "zh-CN",
            "Japonés": "ja",
            "Tailandés": "th",
            "Ruso": "ru",
            "Portugués": "pt",
            "Italiano": "it",
            "Turco": "tr"
        }
        self.lang_codes = {v: k for k, v in self.langs.items()}

        # Poblar combos con nombres legibles y guardar código en itemData
        for name, code in self.langs.items():
            self.cmb_source.addItem(name, code)
            if code != "auto":  # en destino no tiene sentido "auto"
                self.cmb_target.addItem(name, code)

        self.cmb_engine = QComboBox()

        self.cmb_engine.addItems(["google_v1", "google_free", "mymemory"])

        self.lbl_source = QLabel(self.t("source_lang"))
        self.lbl_target = QLabel(self.t("target_lang"))
        self.lbl_engine = QLabel(self.t("menu_translate"))

        toolbar.addWidget(self.lbl_source)
        toolbar.addWidget(self.cmb_source)
        toolbar.addSeparator()
        toolbar.addWidget(self.lbl_target)
        toolbar.addWidget(self.cmb_target)
        toolbar.addSeparator()
        toolbar.addWidget(self.lbl_engine)
        toolbar.addWidget(self.cmb_engine)

        main.addWidget(toolbar)

        # --- Mensaje de ayuda arriba a la izquierda ---
        info_widget = QWidget()
        info_row = QHBoxLayout(info_widget)
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.info_icon_label = QLabel()
        icon_path = self.icon_path / "idea.svg"
        if icon_path.exists():
            self.info_icon_label.setPixmap(QIcon(str(icon_path)).pixmap(20, 20))
        self.info_icon_label.setFixedSize(20, 20)

        self.info_text_label = QLabel(self.t("videos_drag_hint"))

        info_row.addWidget(self.info_icon_label)
        info_row.addWidget(self.info_text_label)

        # 🔹 Insertamos el widget de ayuda justo después del toolbar
        main.addWidget(info_widget, alignment=Qt.AlignLeft)

        # --- Tabla de archivos ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([self.t("index"), self.t("title"), self.t("format"), self.t("source_lang"), self.t("target_lang"), self.t("progress")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAcceptDrops(True)
        self.table.dragEnterEvent = self._drag_enter
        self.table.dragMoveEvent = self.dragMoveEvent
        self.table.dropEvent = self._drop
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.verticalHeader().setVisible(False)  # 🔹 Oculta numeración de filas
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 🔹 Bloquear edición

        hdr = self.table.horizontalHeader()

        # Tamaños inciales ajustados de headerview
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)  # Índice fijo
        hdr.resizeSection(0, 10)  # ancho razonable
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)  # Archivo expande
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)  # Formato fijo
        hdr.resizeSection(2, 60)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)  # Origen fijo (idioma)
        hdr.resizeSection(3, 100)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)  # Destino expande
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)  # % fijo
        hdr.resizeSection(5, 20)  # ancho razonable

        main.addWidget(self.table)

        # --- Vista dividida original ↔ traducción ---
        split = QHBoxLayout()

        self.table_original = QTableWidget(0, 2)
        self.table_original.setHorizontalHeaderLabels([self.t("index"), self.t("original")])
        self.table_original.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_original.setEditTriggers(QAbstractItemView.NoEditTriggers)   # 🔹 Bloquear edición
        self.table_original.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_original.verticalHeader().setVisible(False)  # 🔹 Oculta numeración de filas
        # # Ocultar la columna de índice
        # self.table_original.setColumnHidden(0, True)

        # Para la tabla de originales
        header_orig = self.table_original.horizontalHeader()
        header_orig.setSectionResizeMode(0, QHeaderView.Fixed)  # Índice fijo
        header_orig.resizeSection(0, 40)  # ancho fijo 60px
        header_orig.setSectionResizeMode(1, QHeaderView.Stretch)  # Texto se expande

        self.table_translated = QTableWidget(0, 2)
        self.table_translated.setHorizontalHeaderLabels([self.t("index"),self.t("translation_completed")])
        self.table_translated.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_translated.setEditTriggers(QAbstractItemView.NoEditTriggers)   # 🔹 Bloquear edición
        self.table_translated.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_translated.verticalHeader().setVisible(False)  # 🔹 Oculta numeración de filas
        # # Ocultar la columna de índice
        # self.table_translated.setColumnHidden(0, True)

        # Para la tabla de traducciones
        header_trans = self.table_translated.horizontalHeader()
        header_trans.setSectionResizeMode(0, QHeaderView.Fixed)  # Índice fijo
        header_trans.resizeSection(0, 40)  # ancho fijo 60px
        header_trans.setSectionResizeMode(1, QHeaderView.Stretch)  # Texto se expande

        split.addWidget(self.table_original)
        split.addWidget(self.table_translated)
        main.addLayout(split)

        # --- Progreso global y estado ---
        self.progress = QProgressBar();
        self.progress.setValue(0)
        self.lbl_status = QLabel(self.t("ready_to_start"))
        main.addWidget(self.progress)
        main.addWidget(self.lbl_status)

        # --- Botones ---
        btns = QHBoxLayout()
        self.btn_add = QPushButton(self.t("add_subtitles"))
        self.btn_translate = QPushButton(self.t("start"));
        self.btn_translate.setObjectName("PrimaryButton")
        self.btn_cancel = QPushButton(self.t("cancel"));
        self.btn_cancel.setObjectName("DangerButton")
        self.btn_cancel.setEnabled(False)

        btns.addWidget(self.btn_add)
        btns.addStretch()
        btns.addWidget(self.btn_translate)
        btns.addWidget(self.btn_cancel)
        main.addLayout(btns)

    def _wire(self):
        self.btn_add.clicked.connect(self._select_files)
        self.btn_translate.clicked.connect(self._start_all)
        self.btn_cancel.clicked.connect(self.cancel_translation.emit)

    # --- DnD ---
    def _drag_enter(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def _drop(self, e):
        paths = []
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if not p.exists():
                continue
            if p.is_file() and p.suffix.lower() in (".srt", ".vtt"):
                paths.append(str(p))
            elif p.is_dir():
                # 🔹 Buscar recursivamente subtítulos dentro de la carpeta
                for sub in p.rglob("*"):
                    if sub.suffix.lower() in (".srt", ".vtt"):
                        paths.append(str(sub))

        if paths:
            self._add_files(paths)

    # --- selección de archivos ---
    def _select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, self.t("add_subtitles"), "", "Subtítulos (*.srt *.vtt)")
        if paths:
            self._add_files(paths)

    def _add_files(self, paths):
        for p in paths:
            if any(row["path"] == p for row in self._files):
                continue
            fmt = os.path.splitext(p)[1].lower().lstrip(".")
            row = {
                "path": p,
                "fmt": fmt,
                "status": "No",
                "engine": self.cmb_engine.currentText(),
                "src": self.cmb_source.currentData(),  # código ISO real
                "dst": self.cmb_target.currentData(),  # código ISO real
                "progress": 0
            }

            self._files.append(row)
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self._files))
        for r, row in enumerate(self._files):
            # 0: Índice (número de fila, empezando en 1)
            self.table.setItem(r, 0, QTableWidgetItem(str(r + 1)))

            # 1: Archivo (basename)
            self.table.setItem(r, 1, QTableWidgetItem(os.path.basename(row["path"])))

            # 2: Formato (upper)
            self.table.setItem(r, 2, QTableWidgetItem(row["fmt"].upper()))

            # 3: Origen (idioma detectado del archivo)
            detected = row.get("detected") or self._detect_language(row["path"])
            row["detected"] = detected

            # Mostrar nombre legible si existe en self.lang_codes
            display_name = self.lang_codes.get(detected, detected)
            self.table.setItem(r, 3, QTableWidgetItem(display_name))

            # 4: Destino (nombre final esperado)
            p = Path(row["path"])
            final_name = f"{p.stem}_{row['dst']}{p.suffix}"
            self.table.setItem(r, 4, QTableWidgetItem(final_name))

            # 5: % progreso
            self.table.setItem(r, 5, QTableWidgetItem(str(row["progress"])))

        # 👇 importante: no uses resizeColumnsToContents() porque te rompe los anchos
        # mejor reaplicar tus modos de redimensionamiento aquí
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed);
        hdr.resizeSection(0, 10)  # Índice
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)  # Archivo
        hdr.setSectionResizeMode(2, QHeaderView.Fixed);
        hdr.resizeSection(2, 60)  # Formato
        hdr.setSectionResizeMode(3, QHeaderView.Fixed);
        hdr.resizeSection(3, 100)  # Origen
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)  # Destino
        hdr.setSectionResizeMode(5, QHeaderView.Fixed);
        hdr.resizeSection(5, 20)  # %

    def _detect_language(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                sample = f.read(2000)  # leer un fragmento
            return detect(sample)
        except Exception:
            return "auto"

    # --- menú contextual ---
    def _context_menu(self, pos):
        menu = QMenu(self)
        a_add = menu.addAction(self.t("add_input_files"))
        a_select = menu.addAction(self.t("select_video_files"))  # renombrar en i18n si quieres “Seleccionar subtítulos...”
        a_all = menu.addAction("Seleccionar todos")
        a_rm_sel = menu.addAction("Eliminar seleccionado")
        a_rm_all = menu.addAction("Eliminar todos")
        menu.addSeparator()
        a_tr_sel = menu.addAction("Traducir seleccionado")
        a_tr_all = menu.addAction("Traducir todos")
        act = menu.exec(self.table.mapToGlobal(pos))
        if act == a_add:
            self._select_files()
        elif act == a_select:
            self._select_files()
        elif act == a_all:
            self.table.selectAll()
        elif act == a_rm_sel:
            self._remove_selected()
        elif act == a_rm_all:
            self._remove_all()
        elif act == a_tr_sel:
            self._start_selected()
        elif act == a_tr_all:
            self._start_all()

    def _remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self._files):
                self._files.pop(r)
        self._refresh_table()

    def _remove_all(self):
        self._files.clear()
        self._refresh_table()

    # --- iniciar traducciones ---
    def _start_selected(self):
        idxs = sorted({i.row() for i in self.table.selectedIndexes()})
        paths = [self._files[i]["path"] for i in idxs if 0 <= i < len(self._files)]
        self._start(paths)

    def _start_all(self):
        paths = [row["path"] for row in self._files]
        self._start(paths)

    def _start(self, paths):
        if not paths:
            return
        # fijar motor y lenguajes actuales para la corrida
        src = self.cmb_source.currentData()
        dst = self.cmb_target.currentData()
        engine = self.cmb_engine.currentText()

        # bloquear UI sensible
        self.btn_cancel.setEnabled(True)  # 🔹 habilitar
        self._set_busy(True)
        self.progress.setValue(0)
        self.lbl_status.setText(self.t("analyzing_files").format(count=len(paths)))
        self.processing_started.emit()
        self.request_translation.emit(paths, src, dst, engine)

    # --- hooks desde controller ---
    def on_file_progress(self, path, value):
        for r, row in enumerate(self._files):
            if row["path"] == path:
                if value >= 99:
                    value = 100
                row["progress"] = value
                # actualizar solo la celda de progreso (columna 5)
                item = self.table.item(r, 5)
                if item is None:
                    item = QTableWidgetItem(str(value))
                    self.table.setItem(r, 5, item)
                else:
                    item.setText(str(value))
                break

        # progreso global: media
        if self._files:
            self.progress.setValue(sum(r["progress"] for r in self._files) // len(self._files))

    def on_file_finished(self, out_path):
        out_stem = Path(out_path).stem
        for r, row in enumerate(self._files):
            orig_stem = Path(row["path"]).stem
            if out_stem.startswith(orig_stem):
                row["status"] = "Sí"
                row["progress"] = 100
                item = self.table.item(r, 5)
                if item is None:
                    item = QTableWidgetItem("100")
                    self.table.setItem(r, 5, item)
                else:
                    item.setText("100")
                break

    def on_all_finished(self, canceled=False):
        print(f"[WIDGET] on_all_finished recibido, canceled={canceled}")
        try:
            self._set_busy(False)
            self.btn_cancel.setEnabled(False)
            self.processing_finished.emit()

            if canceled:
                self.lbl_status.setText(self.t("processing_canceled"))
                self.progress.setValue(0)  # Resetear progreso global

                # 🔹 Resetear progreso de cada fila
                for r, row in enumerate(self._files):
                    row["progress"] = 0
                    item = self.table.item(r, 5)
                    if item is None:
                        item = QTableWidgetItem("0")
                        self.table.setItem(r, 5, item)
                    else:
                        item.setText("0")

            else:
                self.lbl_status.setText(self.t("processing_completed"))
                self.progress.setValue(100)  # Asegurar 100% en completado
        except Exception as e:
            print(f"[ERROR] Error en on_all_finished: {e}")

    def _set_busy(self, busy: bool):
        for w in (self.btn_add, self.btn_translate, self.cmb_source, self.cmb_target, self.cmb_engine):
            w.setEnabled(not busy)
        # 🔹 Deshabilitar menú contextual de la tabla
        if busy:
            self.table.setContextMenuPolicy(Qt.NoContextMenu)
        else:
            self.table.setContextMenuPolicy(Qt.CustomContextMenu)

    def retranslate_ui(self):
        self.t = get_translator()

        # Grupo de configuración
        if self.parent():
            self.parent().setWindowTitle(self.t("app_title"))

        # Etiquetas del formulario
        self.cmb_source.setToolTip(self.t("source_lang"))
        self.cmb_target.setToolTip(self.t("target_lang"))
        self.cmb_engine.setToolTip(self.t("menu_translate"))

        # Grupo
        group = self.findChild(QGroupBox)
        if group:
            group.setTitle(self.t("translate_subtitles"))

        # Cabeceras de la tabla principal
        self.table.setHorizontalHeaderLabels([
            self.t("index"),
            self.t("title"),
            self.t("format"),
            self.t("source_lang"),
            self.t("target_lang"),
            self.t("progress")
        ])

        # Actualizar headers de las tablas de preview si existen
        if hasattr(self, "table_original"):
            self.table_original.setHorizontalHeaderLabels([
                self.t("index"),
                self.t("original")
            ])
            header_orig = self.table_original.horizontalHeader()
            header_orig.setSectionResizeMode(0, QHeaderView.Fixed)
            header_orig.resizeSection(0, 40)
            header_orig.setSectionResizeMode(1, QHeaderView.Stretch)

        if hasattr(self, "table_translated"):
            self.table_translated.setHorizontalHeaderLabels([
                self.t("index"),
                self.t("translation_completed")
            ])
            header_trans = self.table_translated.horizontalHeader()
            header_trans.setSectionResizeMode(0, QHeaderView.Fixed)
            header_trans.resizeSection(0,40)
            header_trans.setSectionResizeMode(1, QHeaderView.Stretch)

        # Botones y labels
        self.btn_add.setText(self.t("add_subtitles"))
        self.btn_translate.setText(self.t("start"))
        self.btn_cancel.setText(self.t("cancel"))
        self.lbl_status.setText(self.t("ready_to_start"))

    def load_file_preview(self, entries):
        """Carga líneas originales preservando estructura multi-línea."""
        count = len(entries)
        self.table_original.setRowCount(count)
        self.table_translated.setRowCount(count)

        print(f"[WIDGET] Cargando preview: {count} entradas")

        for i, entry in enumerate(entries):
            # CRÍTICO: No alterar la estructura del texto original
            # Mostrar el texto completo tal como está, incluyendo saltos de línea
            original_text = entry.original

            # Para visualización en la tabla, reemplazar \n con espacio para que sea legible
            # pero NO alterar el contenido real
            display_text = original_text.replace('\n', ' | ')  # Usar separador visual

            self.table_original.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table_original.setItem(i, 1, QTableWidgetItem(display_text))

            self.table_translated.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table_translated.setItem(i, 1, QTableWidgetItem(""))

            # Debug para primeras 3 entradas
            if i < 3:
                print(f"[WIDGET] Preview {i + 1}: '{original_text[:50]}...'")
                print(f"[WIDGET] Líneas en texto: {original_text.count(chr(10)) + 1}")

        # Reaplizar modos de header sin alterar contenido
        header_orig = self.table_original.horizontalHeader()
        header_orig.setSectionResizeMode(0, QHeaderView.Fixed)
        header_orig.resizeSection(0, 40)
        header_orig.setSectionResizeMode(1, QHeaderView.Stretch)

        header_trans = self.table_translated.horizontalHeader()
        header_trans.setSectionResizeMode(0, QHeaderView.Fixed)
        header_trans.resizeSection(0, 40)
        header_trans.setSectionResizeMode(1, QHeaderView.Stretch)

    def clear_preview(self):
        """Limpia ambas tablas."""
        self.table_original.setRowCount(0)
        self.table_translated.setRowCount(0)

    def on_line_translated(self, index, original, translated):
        """Actualiza en tiempo real la columna de traducción preservando estructura."""
        try:
            # Para mostrar en la tabla, convertir saltos de línea a separador visual
            display_translated = translated.replace('\n', ' | ')

            self.table_translated.setItem(index, 1, QTableWidgetItem(display_translated))

            # Debug para primeras 3
            if index < 3:
                print(f"[WIDGET] Traducción {index}: '{translated[:50]}...'")
                print(f"[WIDGET] Líneas en traducción: {translated.count(chr(10)) + 1}")

        except Exception as e:
            print(f"[WIDGET] Error actualizando línea {index}: {e}")

