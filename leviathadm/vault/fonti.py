"""Fonti di una riunione: upload in _fonti/AAAAMMGG <Fase>/, conversione trascritti, presenze → Anagrafica."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from leviathadm.vault import cruscotto as _c  # noqa: F401  (allinea la radice degli script)
from parse_presenze import parse_presenze_csv
from update_anagrafica import update_from_presenze
import vtt2md

ESTENSIONI = {".docx", ".md", ".vtt", ".csv", ".pdf"}
MAX_BYTES = 200 * 1024 * 1024


@dataclass
class Esito:
    stato: Literal["salvato", "identico", "conflitto", "rifiutato"]
    path: Path | None = None
    messaggio: str = ""


def cartella_fonti(rilascio_dir: Path, data_iso: str, fase_tab: str) -> Path:
    return rilascio_dir / "_fonti" / f"{data_iso.replace('-', '')} {fase_tab}"


def salva_fonte(rilascio_dir: Path, data_iso: str, fase_tab: str, nome: str, dati: bytes, *, sovrascrivi: bool = False) -> Esito:
    from leviathadm.vault.writers import _libero
    _libero()                                     # nessuna scrittura durante un'esecuzione (sync)
    nome = Path(nome).name                        # mai percorsi dal browser
    if Path(nome).suffix.lower() not in ESTENSIONI:
        return Esito("rifiutato", None, f"estensione non ammessa: {nome}")
    if len(dati) > MAX_BYTES:
        return Esito("rifiutato", None, f"file troppo grande (> {MAX_BYTES // 2**20} MB): {nome}")
    dest = cartella_fonti(rilascio_dir, data_iso, fase_tab) / nome
    if not dest.resolve().is_relative_to((rilascio_dir / "_fonti").resolve()):
        return Esito("rifiutato", None, f"destinazione fuori da _fonti/: {data_iso} {fase_tab}")
    if dest.exists():
        if dest.read_bytes() == dati:
            return Esito("identico", dest)
        if not sovrascrivi:
            return Esito("conflitto", dest, f"{nome} esiste già con contenuto diverso")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(dati)
    return Esito("salvato", dest)


def converti_trascritto(path: Path, *, deps: set[str]) -> Path | None:
    """.vtt → .md (stdlib); .docx → .md via convert.docx_to_md (pandoc: se manca, None); .md → se stesso."""
    suf = path.suffix.lower()
    if suf == ".md":
        return path
    if suf == ".vtt":
        return vtt2md.vtt2md(path)
    if suf == ".docx":
        if "pandoc" not in deps:
            return None
        try:
            import convert            # importa pypandoc: solo qui, e solo se pandoc c'è
        except ImportError:
            return None
        return convert.docx_to_md(path)
    return None


def importa_presenze(csv: Path) -> dict:
    presenze = parse_presenze_csv(csv)
    esito = update_from_presenze(presenze)
    return {**presenze, "created": esito.get("created", [])}
