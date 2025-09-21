from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QProgressBar, QGroupBox, QFormLayout,
    QSizePolicy, QTableWidget, QTableWidgetItem, QAbstractItemView, QMenu
)
from PySide6.QtCore import Signal, Qt, QMimeData
from app.services.i18n import get_translator
import os

class TranslationWidget(QWidget):
    request_translation = Signal(list, str, str, str)  # paths, src, dst, engine
    cancel_translation = Signal()

    processing_started = Signal()
    processing_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.t = get_translator()
        self._files = []  # list of dict: {path, fmt, status, engine, src, dst, progress}
        self._setup_ui()
        self._wire()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(15, 15, 15, 15)
        main.setSpacing(12)

        # Configuración
        config = QGroupBox(self.t("translate_subtitles"))
        form = QFormLayout()
        self.cmb_source = QComboBox(); self.cmb_source.addItems(["auto", "en", "es", "fr", "de"])
        self.cmb_target = QComboBox(); self.cmb_target.addItems(["es", "en", "fr", "de"])
        self.cmb_engine = QComboBox(); self.cmb_engine.addItems(["google_free", "mymemory"])
        form.addRow(self.t("source_lang"), self.cmb_source)
        form.addRow(self.t("target_lang"), self.cmb_target)
        form.addRow(self.t("menu_translate"), self.cmb_engine)
        config.setLayout(form)

        # Tabla de archivos
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Archivo", "Formato", "Estado", "Motor", "Origen", "Destino", "%"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAcceptDrops(True)
        self.table.dragEnterEvent = self._drag_enter
        self.table.dropEvent = self._drop
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)

        # Progreso global
        self.progress = QProgressBar(); self.progress.setValue(0)
        self.lbl_status = QLabel(self.t("ready_to_start"))

        # Botones
        btns = QHBoxLayout()
        self.btn_add = QPushButton(self.t("add_subtitles"))
        self.btn_translate = QPushButton(self.t("start")); self.btn_translate.setObjectName("PrimaryButton")
        self.btn_cancel = QPushButton(self.t("cancel")); self.btn_cancel.setObjectName("DangerButton")
        btns.addWidget(self.btn_add); btns.addStretch(); btns.addWidget(self.btn_translate); btns.addWidget(self.btn_cancel)

        main.addWidget(config)
        main.addWidget(self.table)
        main.addWidget(self.progress)
        main.addWidget(self.lbl_status)
        main.addLayout(btns)

    def _wire(self):
        self.btn_add.clicked.connect(self._select_files)
        self.btn_translate.clicked.connect(self._start_all)
        self.btn_cancel.clicked.connect(self.cancel_translation.emit)

    # --- DnD ---
    def _drag_enter(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def _drop(self, e):
        paths = []
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p and p.lower().endswith((".srt", ".vtt")):
                paths.append(p)
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
            row = {"path": p, "fmt": fmt, "status": "No", "engine": self.cmb_engine.currentText(),
                   "src": self.cmb_source.currentText(), "dst": self.cmb_target.currentText(), "progress": 0}
            self._files.append(row)
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self._files))
        for r, row in enumerate(self._files):
            self.table.setItem(r, 0, QTableWidgetItem(os.path.basename(row["path"])))
            self.table.setItem(r, 1, QTableWidgetItem(row["fmt"].upper()))
            self.table.setItem(r, 2, QTableWidgetItem("Sí" if row["status"] == "Sí" else "No"))
            self.table.setItem(r, 3, QTableWidgetItem(row["engine"]))
            self.table.setItem(r, 4, QTableWidgetItem(row["src"]))
            self.table.setItem(r, 5, QTableWidgetItem(row["dst"]))
            self.table.setItem(r, 6, QTableWidgetItem(str(row["progress"])))
        self.table.resizeColumnsToContents()

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
        src = self.cmb_source.currentText()
        dst = self.cmb_target.currentText()
        engine = self.cmb_engine.currentText()
        # bloquear UI sensible
        self._set_busy(True)
        self.progress.setValue(0)
        self.lbl_status.setText(self.t("analyzing_files").format(count=len(paths)) if "analyzing_files" in dir(self.t) else "Traduciendo...")
        self.processing_started.emit()
        self.request_translation.emit(paths, src, dst, engine)

    # --- hooks desde controller ---
    def on_file_progress(self, path, value):
        for row in self._files:
            if row["path"] == path:
                row["progress"] = value
        self._refresh_table()
        # progreso global: media
        if self._files:
            self.progress.setValue(sum(r["progress"] for r in self._files) // len(self._files))

    def on_file_finished(self, out_path):
        for row in self._files:
            if os.path.basename(row["path"]).split(".")[0] == os.path.basename(out_path).split("_translated")[0]:
                row["status"] = "Sí"; row["progress"] = 100
        self._refresh_table()

    def on_all_finished(self):
        self._set_busy(False)
        self.processing_finished.emit()
        self.lbl_status.setText(self.t("processing_completed"))

    def _set_busy(self, busy: bool):
        for w in (self.btn_add, self.btn_translate, self.cmb_source, self.cmb_target, self.cmb_engine):
            w.setEnabled(not busy)
