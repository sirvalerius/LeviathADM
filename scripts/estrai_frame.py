"""estrai_frame.py — estrae fotogrammi da una registrazione Teams a timestamp dati.

Complementare a vtt2md.py: il VTT dà il parlato, questo script estrae cosa
veniva mostrato a schermo nei momenti indicati (demo, condivisioni schermo).

Uso:
    python scripts/estrai_frame.py <video> <out_dir> <mm:ss> [mm:ss ...]

I frame vengono salvati come PNG `frame_MMSS.png` (larghezza max 1280px).
Richiede opencv-python(-headless).
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2


def estrai(video: Path, out_dir: Path, timestamps: list[str]) -> list[Path]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        sys.exit(f"Impossibile aprire il video: {video}")
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for ts in timestamps:
        m, s = ts.split(":")
        msec = (int(m) * 60 + int(s)) * 1000
        cap.set(cv2.CAP_PROP_POS_MSEC, msec)
        ok, frame = cap.read()
        if not ok:
            print(f"  SKIP {ts}: fuori durata o frame non leggibile")
            continue
        h, w = frame.shape[:2]
        if w > 1280:
            frame = cv2.resize(frame, (1280, int(h * 1280 / w)))
        out = out_dir / f"frame_{int(m):02d}{int(s):02d}.png"
        cv2.imwrite(str(out), frame)
        saved.append(out)
        print(f"  OK {ts} -> {out.name}")
    cap.release()
    return saved


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    estrai(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
