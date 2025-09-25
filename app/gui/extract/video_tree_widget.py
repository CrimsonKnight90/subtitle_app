# app\gui\extract\video_tree_widget.py
# 📄 Archivo: video_tree_widget.py

from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QAction, QKeySequence
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QHeaderView
)

from app.core.ffmpeg_utils import ffprobe_subs, BITMAP_CODECS
import pycountry
import os
import subprocess
import sys
from app.services.translations import TRANSLATIONS
from app.services.settings import get_settings

def get_translator():
    S = get_settings()
    lang = S.config.get("ui_language", "es")
    return lambda key: TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)

# ------------------ Worker para análisis con ffprobe ------------------
class ProbeWorker(QThread):
    probed = Signal(Path, list)   # Señal: (video_path, supported_tracks)
    failed = Signal(Path, str)    # Señal: (video_path, error)
    finished_all = Signal()       # Señal: análisis terminado

    def __init__(self, videos: List[Path], parent=None):
        super().__init__(parent)
        self.videos = videos
        self._stop = False

    def run(self):
        for v in self.videos:
            if self._stop:
                break
            try:
                tracks = ffprobe_subs(v)
                supported = [t for t in tracks if t["codec_name"] not in BITMAP_CODECS]
                self.probed.emit(v, supported)
            except Exception as e:
                self.failed.emit(v, str(e))
        self.finished_all.emit()

    def stop(self):
        self._stop = True


# ------------------ Widget principal de árbol de videos/subtítulos ------------------
class VideoTreeWidget(QTreeWidget):
    # Señales hacia MainWindow
    status = Signal(str)              # Mensajes de estado
    last_lang_changed = Signal(str)   # Cambio de idioma preferido

    # Idioma preferido recordado en la sesión
    last_selected_lang: str | None = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DropOnly)
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.setUniformRowHeights(True)
        self.setAnimated(True)
        self.setIndentation(24)

        # Estilos de fuente
        self._video_font = QFont()
        self._video_font.setBold(True)
        self._video_font.setPointSize(11)

        self._sub_font = QFont()
        self._sub_font.setPointSize(9)

        # Atajos de teclado
        self._shortcut_select_all = QAction(self)
        self._shortcut_select_all.setShortcut(QKeySequence("Ctrl+A"))
        self._shortcut_select_all.triggered.connect(self._select_all_videos)
        self.addAction(self._shortcut_select_all)

        self._shortcut_extract = QAction(self)
        self._shortcut_extract.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.addAction(self._shortcut_extract)

        self._shortcut_delete = QAction(self)
        self._shortcut_delete.setShortcut(QKeySequence("Delete"))
        self._shortcut_delete.triggered.connect(self._delete_selected)
        self.addAction(self._shortcut_delete)

        # Iconos (opcional)
        self.icon_video = None
        self.icon_sub = None

        # Hilo de análisis
        self._probe_thread: ProbeWorker | None = None

        # Traductor y cabeceras iniciales
        self.t = get_translator()
        self.apply_translations()

    def set_ui_language(self, lang_code: str):
        # Recarga el traductor y reaplica cabeceras
        self.t = get_translator()
        self.apply_translations()

    def apply_translations(self):
        # Cabeceras del árbol traducibles
        self.setHeaderLabels([
            self.t("header_element"),
            self.t("header_language"),
            self.t("header_codec"),
            self.t("header_flags")
        ])

        # Ajustar automáticamente la primera columna (Elemento) al contenido
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)

        # Opcional: que las demás columnas se ajusten o estiren
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

    # ------------------ Drag & Drop ------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                for ext in (".mkv", ".mp4", ".avi", ".mov"):
                    paths.extend(p.rglob(f"*{ext}"))
            elif p.is_file() and p.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov"}:
                paths.append(p)
        if not paths:
            self.status.emit(self.t("no_valid_videos_drag"))
            return
        self._probe_and_insert(paths)

    # ------------------ Añadir videos programáticamente ------------------
    def add_videos(self, videos: List[Path]):
        valid = [v for v in videos if v.is_file() and v.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov"}]
        if not valid:
            self.status.emit(self.t("no_valid_videos_add"))
            return

        # Evitar duplicados
        existentes = {
            (self.topLevelItem(i).data(0, Qt.UserRole) or {}).get("path")
            for i in range(self.topLevelItemCount())
        }
        nuevos = [v for v in valid if v not in existentes]

        if not nuevos:
            self.status.emit(self.t("all_videos_listed"))
            return

        self._probe_and_insert(nuevos)

    # ------------------ Lanzar análisis con ffprobe ------------------
    def _probe_and_insert(self, videos: List[Path]):
        if self._probe_thread and self._probe_thread.isRunning():
            self._probe_thread.stop()
        self._probe_thread = ProbeWorker(videos, self)
        self._probe_thread.probed.connect(self._on_probed)
        self._probe_thread.failed.connect(self._on_failed)
        self._probe_thread.finished_all.connect(lambda: self.status.emit(self.t("list_updated")))
        self._probe_thread.start()
        self.status.emit(self.t("analyzing_files").format(count=len(videos)))

    # ------------------ Callbacks de análisis ------------------
    def _on_probed(self, video: Path, tracks: List[Dict[str, Any]]):
        root = self._add_video_item(video)
        if not tracks:
            no_item = QTreeWidgetItem(root, [self.t("no_extractable_subs"), "", "", ""])
            no_item.setFont(0, self._sub_font)
            root.setExpanded(True)
            return
        for i, t in enumerate(tracks, start=1):
            self._add_subtitle_item(root, i, t)
        root.setExpanded(True)

    def _on_failed(self, video: Path, err: str):
        root = self._add_video_item(video)
        fail = QTreeWidgetItem(root, [self.t("ffprobe_failed").format(error=err), "", "", ""])
        fail.setFont(0, self._sub_font)
        root.setExpanded(True)

    # ------------------ Creación de items ------------------
    def _add_video_item(self, video: Path) -> QTreeWidgetItem:
        root = QTreeWidgetItem([video.name, "", "", ""])
        root.setData(0, Qt.UserRole, {"type": "video", "path": video})
        root.setFont(0, self._video_font)
        if self.icon_video:
            root.setIcon(0, self.icon_video)
        self.addTopLevelItem(root)
        return root

    def _add_subtitle_item(self, root: QTreeWidgetItem, num: int, track: Dict[str, Any]) -> QTreeWidgetItem:
        lang = track.get("language") or "und"
        codec = track.get("codec_name", "?").upper()
        flags = []
        if track.get("default"):
            flags.append("default")
        if track.get("forced"):
            flags.append("forced")
        flags_txt = ", ".join(flags) if flags else "-"
        title = track.get("title") or ""
        label = f"{self.t('subtitle_label')} #{num}: {lang} {f'({title})' if title else ''}".strip()

        child = QTreeWidgetItem([label, lang, codec, flags_txt])
        child.setData(0, Qt.UserRole, {"type": "subtitle", "track": track})
        child.setFlags(child.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        child.setCheckState(0, Qt.Checked if (
                    self.last_selected_lang and self.last_selected_lang == lang) else Qt.Unchecked)
        child.setFont(0, self._sub_font)
        if self.icon_sub:
            child.setIcon(0, self.icon_sub)
        root.addChild(child)
        return child

    # ------------------ Menú contextual ------------------
    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        menu = QMenu(self)

        # Estado global
        has_files = self.topLevelItemCount() > 0
        has_subs = any(self._iter_sub_items(v) for v in self._iter_video_items())
        checked_tracks = sum(1 for v in self._iter_video_items()
                             for s in self._iter_sub_items(v)
                             if s.checkState(0) == Qt.Checked)
        unchecked_tracks = sum(1 for v in self._iter_video_items()
                               for s in self._iter_sub_items(v)
                               if s.checkState(0) == Qt.Unchecked)

        # Listas globales
        langs = self._collect_languages_global()
        codecs = self._collect_codecs_global()
        ids = self._collect_track_ids_global()

        # Siempre activa
        act_add = menu.addAction(self.t("add_input_files"), lambda: self.status.emit("add_files"))

        menu.addSeparator()
        act_check_all = menu.addAction(self.t("check_all_tracks"), lambda: self._mark_all_tracks(True))
        act_check_all.setEnabled(has_files and unchecked_tracks > 0)
        act_check_all.setToolTip("" if act_check_all.isEnabled() else self.t("no_tracks_to_check"))

        subs_check_menu = menu.addMenu(self.t("check_subtitle_tracks"))
        subs_check_menu.setEnabled(has_subs and unchecked_tracks > 0)
        subs_check_menu.setToolTip("" if subs_check_menu.isEnabled() else self.t("no_subs_to_check"))
        subs_check_menu.addAction(self.t("all_subtitle_tracks"), lambda: self._mark_all_subs(True))

        lang_menu = subs_check_menu.addMenu(self.t("by_language"))
        for code, name in langs:
            lang_menu.addAction(f"{name} ({code})", lambda c=code: self._mark_subs_by_lang(c, True))

        codec_menu = subs_check_menu.addMenu(self.t("by_codec"))
        for codec in codecs:
            codec_menu.addAction(codec.upper(), lambda c=codec: self._mark_subs_by_codec(c, True))

        id_menu = subs_check_menu.addMenu(self.t("by_track_id"))
        for tid, desc in ids:
            id_menu.addAction(desc, lambda t=tid: self._mark_sub_by_id(t, True))

        menu.addSeparator()
        act_uncheck_all = menu.addAction(self.t("uncheck_all_tracks"), lambda: self._mark_all_tracks(False))
        act_uncheck_all.setEnabled(has_files and checked_tracks > 0)

        subs_uncheck_menu = menu.addMenu(self.t("uncheck_subtitle_tracks"))
        subs_uncheck_menu.setEnabled(has_subs and checked_tracks > 0)
        subs_uncheck_menu.addAction(self.t("all_subtitle_tracks"), lambda: self._mark_all_subs(False))

        lang_menu_u = subs_uncheck_menu.addMenu(self.t("by_language"))
        for code, name in langs:
            lang_menu_u.addAction(f"{name} ({code})", lambda c=code: self._mark_subs_by_lang(c, False))

        codec_menu_u = subs_uncheck_menu.addMenu(self.t("by_codec"))
        for codec in codecs:
            codec_menu_u.addAction(codec.upper(), lambda c=codec: self._mark_subs_by_codec(c, False))

        id_menu_u = subs_uncheck_menu.addMenu(self.t("by_track_id"))
        for tid, desc in ids:
            id_menu_u.addAction(desc, lambda t=tid: self._mark_sub_by_id(t, False))

        menu.addSeparator()
        # Globales
        act_remove_all = menu.addAction(self.t("remove_all"), self.clear)
        act_remove_all.setEnabled(has_files)
        act_remove_all.setToolTip("" if has_files else self.t("no_files_loaded"))
        act_remove_selected = menu.addAction(self.t("remove_selected_file"), lambda: self._remove_video_item(item))
        act_open_file = menu.addAction(self.t("open_selected_file"), lambda: self._open_file(item))
        act_open_folder = menu.addAction(self.t("open_selected_file_folder"), lambda: self._open_file_folder(item))

        if not item:
            act_remove_selected.setEnabled(False)
            act_open_file.setEnabled(False)
            act_open_folder.setEnabled(False)

        # Expandir/Colapsar al final
        menu.addSeparator()
        act_expand = menu.addAction(self.t("expand_all"), self.expandAll)
        act_collapse = menu.addAction(self.t("collapse_all"), self.collapseAll)

        menu.exec(event.globalPos())

    # ------------------ Arrastrar y soltar ------------------
    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                for ext in (".mkv", ".mp4", ".avi", ".mov"):
                    paths.extend(p.rglob(f"*{ext}"))
            elif p.is_file() and p.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov"}:
                paths.append(p)

        if not paths:
            self.status.emit(self.t("no_valid_videos_drag"))
            return

        # Evitar duplicados
        existentes = {
            (self.topLevelItem(i).data(0, Qt.UserRole) or {}).get("path")
            for i in range(self.topLevelItemCount())
        }
        nuevos = [v for v in paths if v not in existentes]

        if not nuevos:
            self.status.emit(self.t("all_videos_listed"))
            return

        self._probe_and_insert(nuevos)

    # ------------------ Auxiliares para recolección ------------------
    def _iter_video_items(self, scope_item=None):
        if scope_item and (scope_item.data(0, Qt.UserRole) or {}).get("type") == "video":
            yield scope_item
        elif scope_item and (scope_item.data(0, Qt.UserRole) or {}).get("type") == "subtitle":
            yield scope_item.parent()
        else:
            for i in range(self.topLevelItemCount()):
                yield self.topLevelItem(i)

    def _iter_sub_items(self, video_item):
        for i in range(video_item.childCount()):
            ch = video_item.child(i)
            if (ch.data(0, Qt.UserRole) or {}).get("type") == "subtitle":
                yield ch

    def _collect_languages(self, scope_item=None):
        langs = set()
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                code = sub_item.text(1) or "und"
                try:
                    name = pycountry.languages.get(alpha_3=code) or pycountry.languages.get(alpha_2=code)
                    langs.add((code, name.name if name else self.t("unknown_language")))
                except:
                    langs.add((code, self.t("unknown_language")))
        return sorted(langs)

    def _collect_codecs(self, scope_item=None):
        codecs = set()
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                codecs.add(sub_item.text(2).lower())
        return sorted(codecs)

    def _collect_track_ids(self, scope_item=None):
        ids = []
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                t = (sub_item.data(0, Qt.UserRole) or {}).get("track", {})
                desc = self.t("track_desc").format(
                    index=t.get('index'),
                    lang=t.get('language', 'und').upper(),
                    codec=t.get('codec_name', '?').upper()
                )
                ids.append((t.get("index"), desc))
        return ids

    # ------------------ Recolección global ------------------
    def _nombre_idioma(self, code):
        traducciones = {
            "English": self.t("english"),
            "Spanish": self.t("spanish"),
            "French": self.t("french")
        }
        try:
            lang = pycountry.languages.get(alpha_3=code) or pycountry.languages.get(alpha_2=code)
            if lang:
                return traducciones.get(lang.name, lang.name)
        except:
            pass
        return code

    def _collect_languages_global(self):
        langs = set()
        for v in self._iter_video_items():
            for s in self._iter_sub_items(v):
                code = s.text(1) or "und"
                langs.add((code, self._nombre_idioma(code)))
        return sorted(langs)

    def _collect_codecs_global(self):
        codecs = set()
        for v in self._iter_video_items():
            for s in self._iter_sub_items(v):
                codecs.add(s.text(2).lower())
        return sorted(codecs)

    def _collect_track_ids_global(self):
        ids = []
        for v in self._iter_video_items():
            for s in self._iter_sub_items(v):
                t = (s.data(0, Qt.UserRole) or {}).get("track", {})
                desc = self.t("track_desc").format(
                    index=t.get('index'),
                    lang=t.get('language', 'und').upper(),
                    codec=t.get('codec_name', '?').upper()
                )
                ids.append((t.get("index"), desc))
        return ids

    # ------------------ Auxiliares para marcado ------------------
    def _mark_all_tracks(self, mark):
        for i in range(self.topLevelItemCount()):
            video_item = self.topLevelItem(i)
            for sub_item in self._iter_sub_items(video_item):
                sub_item.setCheckState(0, Qt.Checked if mark else Qt.Unchecked)

    def _mark_all_subs(self, mark, scope_item=None):
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                sub_item.setCheckState(0, Qt.Checked if mark else Qt.Unchecked)

    def _mark_subs_by_lang(self, code, mark, scope_item=None):
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                if sub_item.text(1) == code:
                    sub_item.setCheckState(0, Qt.Checked if mark else Qt.Unchecked)

    def _mark_subs_by_codec(self, codec, mark, scope_item=None):
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                if sub_item.text(2).lower() == codec.lower():
                    sub_item.setCheckState(0, Qt.Checked if mark else Qt.Unchecked)

    def _mark_sub_by_id(self, track_id, mark, scope_item=None):
        for video_item in self._iter_video_items(scope_item):
            for sub_item in self._iter_sub_items(video_item):
                t = (sub_item.data(0, Qt.UserRole) or {}).get("track", {})
                if t.get("index") == track_id:
                    sub_item.setCheckState(0, Qt.Checked if mark else Qt.Unchecked)

    # ------------------ Acciones sobre videos ------------------
    def _video_mark_all(self, video_item, mark):
        """Marca o desmarca todos los subtítulos de un video."""
        for i in range(video_item.childCount()):
            ch = video_item.child(i)
            data = ch.data(0, Qt.UserRole) or {}
            if data.get("type") == "subtitle":
                ch.setCheckState(0, Qt.Checked if mark else Qt.Unchecked)

    def _video_mark_default_only(self, video_item):
        """Marca solo la pista default de un video."""
        any_default = False
        for i in range(video_item.childCount()):
            ch = video_item.child(i)
            data = ch.data(0, Qt.UserRole) or {}
            if data.get("type") != "subtitle":
                continue
            track = data.get("track", {})
            if track.get("default"):
                ch.setCheckState(0, Qt.Checked)
                any_default = True
            else:
                ch.setCheckState(0, Qt.Unchecked)
        if not any_default:
            QMessageBox.information(self, self.t("no_default_track"), self.t("no_default_track_msg"))

    def _video_show_tracks_info(self, video_item):
        """Muestra información detallada de todas las pistas de un video."""
        lines = []
        for i in range(video_item.childCount()):
            ch = video_item.child(i)
            data = ch.data(0, Qt.UserRole) or {}
            if data.get("type") == "subtitle":
                t = data["track"]
                lines.append(
                    f"idx={t['index']} lang={t.get('language', 'und')} codec={t.get('codec_name', '?')} "
                    f"default={t.get('default', False)} forced={t.get('forced', False)} title={t.get('title', '')}"
                )
        msg = "\n".join(lines) if lines else self.t("no_tracks")
        QMessageBox.information(self, self.t("subtitle_tracks"), msg)

    # ------------------ Acciones sobre subtítulos ------------------
    def _sub_toggle(self, sub_item):
        """Alterna el estado de marcado de un subtítulo."""
        st = sub_item.checkState(0)
        sub_item.setCheckState(0, Qt.Unchecked if st == Qt.Checked else Qt.Checked)
        lang = sub_item.text(1)
        if sub_item.checkState(0) == Qt.Checked and lang:
            VideoTreeWidget.last_selected_lang = lang
            self.last_lang_changed.emit(lang)

    def _sub_force_default(self, sub_item):
        """Marca solo este subtítulo y desmarca los demás del mismo video."""
        parent = sub_item.parent()
        if not parent:
            return
        for i in range(parent.childCount()):
            ch = parent.child(i)
            data = ch.data(0, Qt.UserRole) or {}
            if data.get("type") == "subtitle":
                ch.setCheckState(0, Qt.Unchecked)
        sub_item.setCheckState(0, Qt.Checked)
        lang = sub_item.text(1)
        if lang:
            VideoTreeWidget.last_selected_lang = lang
            self.last_lang_changed.emit(lang)

    def _sub_show_info(self, sub_item):
        """Muestra información detallada de una pista de subtítulo."""
        t = (sub_item.data(0, Qt.UserRole) or {}).get("track", {})
        QMessageBox.information(
            self,
            self.t("track_info"),
            f"Index: {t.get('index')}\n"
            f"{self.t('header_language')}: {t.get('language', 'und')}\n"
            f"{self.t('header_codec')}: {t.get('codec_name', '?')}\n"
            f"Default: {t.get('default', False)}\n"
            f"Forced: {t.get('forced', False)}\n"
            f"{self.t('title')}: {t.get('title', '')}"
        )

    # ------------------ Atajos de teclado ------------------
    def _select_all_videos(self):
        """Selecciona todos los nodos raíz (videos)."""
        for i in range(self.topLevelItemCount()):
            it = self.topLevelItem(i)
            it.setSelected(True)

    def _delete_selected(self):
        """Elimina los elementos seleccionados (subtítulos o videos)."""
        selected = self.selectedItems()
        # Borrar hijos primero
        for it in selected:
            data = it.data(0, Qt.UserRole) or {}
            if data.get("type") == "subtitle":
                parent = it.parent()
                if parent:
                    parent.removeChild(it)
        # Luego borrar raíces
        roots = [it for it in selected if (it.data(0, Qt.UserRole) or {}).get("type") == "video"]
        for r in roots:
            idx = self.indexOfTopLevelItem(r)
            self.takeTopLevelItem(idx)

    # ------------------ Auxiliares para gestión y apertura de vídeos ------------------
    def _remove_video_item(self, item):
        """Elimina un vídeo del árbol."""
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("type") == "video":
            idx = self.indexOfTopLevelItem(item)
            if idx >= 0:
                self.takeTopLevelItem(idx)
                self.status.emit(self.t("video_removed").format(path=data.get('path')))
        elif data.get("type") == "subtitle":
            parent = item.parent()
            if parent:
                parent.removeChild(item)
                self.status.emit(self.t("track_removed_from").format(video=parent.text(0)))

    def _open_file(self, item):
        """Abre el archivo de vídeo con el reproductor predeterminado."""
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("type") == "subtitle":
            data = item.parent().data(0, Qt.UserRole) or {}
        path = data.get("path")
        if path and Path(path).exists():
            try:
                if sys.platform.startswith("win"):
                    os.startfile(path)
                elif sys.platform.startswith("darwin"):
                    subprocess.run(["open", path])
                else:
                    subprocess.run(["xdg-open", path])
            except Exception as e:
                self.status.emit(self.t("cannot_open_file").format(error=e))

    def _open_file_folder(self, item):
        """Abre la carpeta que contiene el archivo y lo selecciona."""
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("type") == "subtitle":
            data = item.parent().data(0, Qt.UserRole) or {}
        path = data.get("path")
        if path and Path(path).exists():
            try:
                if sys.platform.startswith("win"):
                    subprocess.run(["explorer", "/select,", str(path)])
                elif sys.platform.startswith("darwin"):
                    subprocess.run(["open", "-R", str(path)])
                else:
                    subprocess.run(["xdg-open", str(Path(path).parent)])
            except Exception as e:
                self.status.emit(self.t("cannot_open_folder").format(error=e))

    # ------------------ Recolección de selección ------------------
    def collect_selection(self) -> Dict[Path, List[int]]:
        """
        Devuelve un diccionario {video_path: [track_indexes]} con las pistas marcadas.
        """
        mapping: Dict[Path, List[int]] = {}
        for i in range(self.topLevelItemCount()):
            root = self.topLevelItem(i)
            data = root.data(0, Qt.UserRole) or {}
            if data.get("type") != "video":
                continue
            vpath: Path = data["path"]
            indexes: List[int] = []
            for j in range(root.childCount()):
                ch = root.child(j)
                cdata = ch.data(0, Qt.UserRole) or {}
                if cdata.get("type") != "subtitle":
                    continue
                if ch.checkState(0) == Qt.Checked:
                    idx = int(cdata["track"]["index"])
                    indexes.append(idx)
            if indexes:
                mapping[vpath] = indexes
        return mapping
