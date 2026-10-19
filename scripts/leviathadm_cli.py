"""Entry point a riga di comando per le funzioni-libreria del vault, usato da LeviathADM (e dalla console).
Nessun prompt; exit 0/1; output UTF-8.

  leviathadm_cli.py convocazione-startup CODICE --data AAAA-MM-GG [--ora 10:00] [--durata 30] [--alternativa TESTO]...
  leviathadm_cli.py convocazione-collaudo CODICE [--data AAAA-MM-GG] [--ora 10:00] [--durata 60] --pdf FILE --documento TESTO --verifica TESTO...
  leviathadm_cli.py prepara-firma CODICE --lettera {trasmissione,estensione}
  leviathadm_cli.py schede [--dry-run]
  leviathadm_cli.py build-pagine
  leviathadm_cli.py proponi-data-collaudo CODICE
  (--vault PATH: solo verifiche, ri-punta gli script su un altro vault)
"""
from __future__ import annotations
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

LETTERE = {"trasmissione": "Trasmissione copia verbale di collaudo", "estensione": "Richiesta estensione in esercizio"}


def _allinea(vault: str | None) -> None:
    if vault:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from leviathadm.vault import cruscotto
        cruscotto.allinea_root(Path(vault))


def cmd_startup(a) -> int:
    from genera_convocazione import genera_convocazione_startup
    r = genera_convocazione_startup(a.codice, date.fromisoformat(a.data), alternative=a.alternativa or None,
                                    ora=a.ora, durata_min=a.durata)
    print(f"Convocazione: {r['eml']}\nA: {r['to']}\nCc: {', '.join(r['cc'])}")
    return 0


def cmd_collaudo(a) -> int:
    from genera_convocazione import genera_convocazione_collaudo
    r = genera_convocazione_collaudo(a.codice, a.verifica, a.documento, Path(a.pdf),
                                     data=date.fromisoformat(a.data) if a.data else None, ora=a.ora, durata_min=a.durata)
    print(f"Convocazione: {r['eml']}\nVerbale: {r['verbale']}\nData: {r['data']}\nA: {r['to']}\nCc: {', '.join(r['cc'])}")
    return 0


def cmd_proponi(a) -> int:
    from genera_convocazione import _parse_date, propose_collaudo_date
    from mail_utils import read_release
    fm, _ = read_release(a.codice)
    disp = _parse_date(fm.get("data_disponibilita_collaudo", ""))
    if disp is None:
        print("data_disponibilita_collaudo assente o 'DA COMPLETARE': indica la data a mano")
        return 1
    print(propose_collaudo_date(disp + timedelta(days=20), date.today()).isoformat())
    return 0


def cmd_firma(a) -> int:
    import prepara_firma
    ok = prepara_firma.prepara_cartella(a.codice, LETTERE[a.lettera])
    print("Cartella pronta." if ok else "Cartella non preparata (lettera .docx mancante?)")
    return 0 if ok else 1


def cmd_schede(a) -> int:
    import build_project_pages as bpp
    if not bpp.EXCEL.exists():
        print(f"Excel PO non trovato: {bpp.EXCEL}")
        return 1
    if a.dry_run:
        rel = bpp.load_releases()
        nuove = [r["cod_rilascio"] for r in rel if not (bpp.LAVORI / r["cod_rilascio"] / f"{r['cod_rilascio']}.md").exists()]
        print(f"{len(rel)} rilasci nell'Excel; schede da creare: {len(nuove)}")
        for c in nuove:
            print(f"  {c}")
        return 0
    bpp.run()
    return 0


def cmd_build(a) -> int:
    import importlib
    falliti = []
    for n in ("build_bozze", "build_scadenze", "build_stato_invii", "build_rilasci", "build_riunioni",
              "build_da_collaudare", "build_da_firmare"):
        try:
            importlib.import_module(n).build()
        except Exception as e:  # noqa: BLE001 — una pagina rotta non blocca le altre
            print(f"ERRORE {n}: {e}")
            falliti.append(n)
    print("Rigenerazione completata." if not falliti else f"Falliti: {', '.join(falliti)}")
    return 1 if falliti else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="leviathadm_cli.py")
    p.add_argument("--vault")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("convocazione-startup")
    s.add_argument("codice"); s.add_argument("--data", required=True)
    s.add_argument("--ora", default="10:00"); s.add_argument("--durata", type=int, default=30)
    s.add_argument("--alternativa", action="append"); s.set_defaults(fn=cmd_startup)
    s = sub.add_parser("convocazione-collaudo")
    s.add_argument("codice"); s.add_argument("--data")
    s.add_argument("--ora", default="10:00"); s.add_argument("--durata", type=int, default=60)
    s.add_argument("--pdf", required=True); s.add_argument("--documento", required=True)
    s.add_argument("--verifica", action="append", required=True); s.set_defaults(fn=cmd_collaudo)
    s = sub.add_parser("proponi-data-collaudo")
    s.add_argument("codice"); s.set_defaults(fn=cmd_proponi)
    s = sub.add_parser("prepara-firma")
    s.add_argument("codice"); s.add_argument("--lettera", choices=list(LETTERE), required=True); s.set_defaults(fn=cmd_firma)
    s = sub.add_parser("schede")
    s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_schede)
    s = sub.add_parser("build-pagine")
    s.set_defaults(fn=cmd_build)
    a = p.parse_args(argv)
    _allinea(a.vault)
    try:
        return a.fn(a)
    except ValueError as e:          # ora in pausa pranzo, data non proponibile, scheda assente
        print(f"ERRORE: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
