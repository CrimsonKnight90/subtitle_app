# app\gui\extract\workers.py
from PySide6.QtCore import QObject, Signal
from pathlib import Path
from app.core.batch import process_one

# ------------------ Worker de procesamiento por lotes ------------------
class BatchWorker(QObject):
    # Señales para comunicar progreso y finalización
    progress = Signal(int, int, str)   # (hechos, total, mensaje)
    finished = Signal(dict)           # estadísticas finales

    def __init__(self, folder: Path, selected_tracks: dict):
        """
        folder: carpeta base de salida
        selected_tracks: {video_path: [track_index, ...]}
        """
        super().__init__()
        self.folder = folder
        self.selected_tracks = selected_tracks
        self._stop = False  # 🔹 bandera de cancelación

    def stop(self):
        """Solicita detener el procesamiento."""
        self._stop = True

    # ------------------ Ejecución del procesamiento ------------------
    def run(self):
        """
        Procesa cada pista seleccionada de cada video.
        Evita sobrescribir archivos cuando hay varias pistas con el mismo idioma
        añadiendo el índice de pista al nombre de salida.
        """
        total = sum(len(tracks) for tracks in self.selected_tracks.values())
        done = 0
        stats = {"ok": 0, "skip": 0, "error": 0, "total": total}

        for video, track_indexes in self.selected_tracks.items():
            for idx in track_indexes:
                # 🔹 Comprobación de cancelación
                if self._stop:
                    self.finished.emit(stats)
                    return

                # 🔹 Llamada a process_one con sufijo único
                ok, msg, outp = process_one(
                    video,
                    self.folder,
                    sel_index=idx,
                    suffix=f"_track{idx}"  # evita sobrescrituras
                )

                done += 1
                if ok:
                    stats["ok"] += 1
                elif "Saltado" in msg:
                    stats["skip"] += 1
                else:
                    stats["error"] += 1

                # Emitir progreso
                self.progress.emit(done, total, f"{video.name} | {msg}")

        # Emitir estadísticas finales
        self.finished.emit(stats)
