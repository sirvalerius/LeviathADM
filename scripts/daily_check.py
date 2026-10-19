"""
daily_check.py — Check giornaliero PO 2026.

Eseguito ogni mattina da Windows Task Scheduler. In sequenza:
  1. build_scadenze      — aggiorna Scadenze.md (milestones, azioni, approvazioni)
  2. build_stato_invii   — aggiorna Stato invii.md (matrice punti di piano × fase)
  3. build_rilasci / build_riunioni — aggiornano Rilasci.md / Riunioni.md dalle schede
  4. chiudi_approvazione — chiude i resoconti con scadenza tacita scaduta
                           (genera PDF + mail definitiva + aggiorna Scadenze.md)
  5. sync_bozze_folder   — allinea "Bozze da inviare/" con le bozze correnti

I passi 1-4 mutano file versionati: girano solo sul PC master
(vedi machines.json / machine_config.py). Sugli slave viene eseguito solo
sync_bozze_folder, che ricostruisce la cartella locale "Bozze da inviare/"
(hardlink, non versionata) a partire dallo stato sincronizzato via git.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Console Windows in cp1252: evita il crash UnicodeEncodeError sui print che
# contengono frecce/emoji (→ ❌ ✅ 🚨). errors="replace" degrada a "?".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import archivia_inviati
import build_bozze
import build_scadenze
import build_stato_invii
import build_rilasci
import build_riunioni
import chiudi_approvazione
import machine_config
import sync_bozze_folder


def main() -> None:
    print("=== PO 2026 — Check giornaliero ===\n")

    if not machine_config.is_master():
        print(f"Ruolo '{machine_config.get_role()}': eseguo solo il sync "
              "(pull/push + cartella bozze locale); i passi che mutano file "
              "versionati sono in carico al master.\n")
        import sync
        sync.main()
        return

    print("1. Archivio resoconti marcati come inviati...")
    archivia_inviati.main()
    print()

    print("2. Aggiorno pagina Bozze da inviare.md...")
    build_bozze.build()
    print()

    print("3. Aggiorno Scadenze.md...")
    build_scadenze.build()
    print()

    print("4. Aggiorno Stato invii.md...")
    build_stato_invii.build()
    print()

    print("4b. Aggiorno Rilasci.md e Riunioni.md...")
    build_rilasci.build()
    build_riunioni.build()
    print()

    print("5. Verifico scadenze approvazione...")
    chiudi_approvazione.main()
    print()

    print("6. Sincronizzo Bozze da inviare/...")
    sync_bozze_folder.sync()
    print()

    print("=== Completato ===")


if __name__ == "__main__":
    main()
