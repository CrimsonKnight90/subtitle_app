# app\core\subtitles.py
# app/core/subtitles.py
import pysrt
from dataclasses import dataclass

@dataclass
class SubtitleEntry:
    id: int
    start: float
    end: float
    original: str
    translated: str = ""

def load_srt(path: str) -> list[SubtitleEntry]:
    subs = pysrt.open(path, encoding="utf-8")
    out=[]
    for s in subs:
        start = s.start.ordinal/1000.0
        end = s.end.ordinal/1000.0
        out.append(SubtitleEntry(id=s.index, start=start, end=end, original=s.text))
    return out

def save_srt(entries: list[SubtitleEntry], path: str):
    from pysrt import SubRipFile, SubRipItem, SubRipTime
    sr = SubRipFile()
    for i,e in enumerate(entries, start=1):
        s = SubRipItem(
            index=i,
            start=SubRipTime(milliseconds=int(e.start*1000)),
            end=SubRipTime(milliseconds=int(e.end*1000)),
            text=e.translated or e.original
        )
        sr.append(s)
    sr.save(path, encoding="utf-8")
