"""Cruscotto PO: letture per le viste native, sopra i collect_* degli script del vault."""
from __future__ import annotations
import importlib
from pathlib import Path

from . import paths as _paths

MODULI_SCRIPT = ("mail_utils", "build_scadenze", "build_bozze", "build_da_collaudare", "build_da_firmare",
                 "build_stato_invii", "chiudi_approvazione", "archivia_inviati", "prepara_firma", "update_anagrafica",
                 "parse_presenze", "genera_convocazione", "build_project_pages", "build_rilasci", "build_riunioni", "sync_bozze_folder")
_ROOT_ATTUALE: Path = _paths._REPO_ROOT


def allinea_root(root: Path) -> None:
    """Ri-punta ogni costante Path dei moduli script (VAULT, LAVORI, OUT, BOZZE, ANAGRAFICA…) da
    _ROOT_ATTUALE a `root`. No-op nell'uso normale (root == repo); serve a LEVIATHADM_ROOT e ai test.
    ponytail: alternativa = parametro vault= in dieci firme degli script; da fare se diventano un pacchetto."""
    global _ROOT_ATTUALE
    root = Path(root).resolve()
    vecchia = _ROOT_ATTUALE
    scripts = _paths.SCRIPTS_DIR
    for nome in MODULI_SCRIPT:
        m = importlib.import_module(nome)
        for attr, val in list(vars(m).items()):
            if (isinstance(val, Path) and not attr.startswith("__") and val.is_relative_to(vecchia)
                    and not val.is_relative_to(scripts)):      # codice e template degli script restano dove sono
                setattr(m, attr, root / val.relative_to(vecchia))
    _ROOT_ATTUALE = root
    lavori = importlib.import_module("build_bozze").LAVORI
    assert lavori.is_relative_to(root), f"radice script non allineata: {lavori}"   # fail-closed


allinea_root(_paths.VAULT_ROOT)

from datetime import date  # noqa: E402
import build_bozze, build_da_collaudare, build_da_firmare, build_scadenze, build_stato_invii, chiudi_approvazione  # noqa: E402,E401
from mail_utils import parse_frontmatter  # noqa: E402

ETICHETTE_SCADENZE = {"tassative": "🚨 Tassative — convocazione collaudo", "scadute": "🔴 Scadute",
                      "settimana": "🟡 Questa settimana", "prossime": "⚪ Prossime"}


def _lavori() -> Path:
    return build_bozze.LAVORI


def _trova(nome: str, sotto: str = "") -> Path | None:
    """Primo `<rilascio>/[sotto/]<nome>` esistente: niente glob, uno stem con `[` o `*` non è un pattern."""
    for d in _lavori().iterdir():
        p = d / sotto / nome if sotto else d / nome
        if p.is_file():
            return p
    return None


def scadenze(today: date | None = None) -> dict[str, list[dict]]:
    """Le quattro sezioni di Scadenze.md (stessa partizione di build_scadenze.build)."""
    today = today or date.today()
    sun = build_scadenze.week_end(today)
    entries = build_scadenze.collect(today)
    for e in entries:
        e["delta"] = build_scadenze.delta_label(e["data"], today)
        e["data_fmt"] = build_scadenze.fmt_date(e["data"])
    resto = [e for e in entries if not e["tassativo"]]

    def ordina(xs):
        return sorted(xs, key=lambda e: e["data"])
    return {"tassative": ordina([e for e in entries if e["tassativo"]]),
            "scadute": ordina([e for e in resto if e["data"] < today]),
            "settimana": ordina([e for e in resto if today <= e["data"] <= sun]),
            "prossime": ordina([e for e in resto if e["data"] > sun])}


def bozze() -> tuple[list[dict], list[dict], list[dict]]:
    """(bozze iniziali, convocazioni, definitivi) con il Path del file: cercato per stem, non per
    codice_rilascio (una cartella rinominata non coincide col frontmatter)."""
    b = build_bozze.collect_bozze()
    for x in b:
        x["path"] = _trova(f"{x['stem']}.md")
        x["mtime_ns"] = _mtime(x["path"])
    conv = build_bozze.collect_convocazioni()
    for x in conv:
        x["path"] = _trova(f"{x['stem']}.eml")
    d = build_bozze.collect_definitivi()
    for x in d:
        x["path"] = _trova(f"{x['stem']}.md", "inviati")
        x["mtime_ns"] = _mtime(x["path"])
    return b, conv, d


def _mtime(p: Path | None) -> int:
    """mtime catturato alla lettura: è ciò che la guardia dei writer confronta al momento del clic."""
    return p.stat().st_mtime_ns if p is not None and p.exists() else 0


def da_collaudare() -> list[dict]:
    items = build_da_collaudare._collect()
    for x in items:
        x["scheda"] = _lavori() / x["codice"] / f"{x['codice']}.md"
        x["mtime_ns"] = _mtime(x["scheda"])
    return items


def da_firmare() -> tuple[list[dict], list[dict]]:
    campi = {label: fb for label, fb, _ in build_da_firmare.LETTERE}
    da_mandare, in_firma = build_da_firmare._collect(prepara=False)
    for x in da_mandare + in_firma:
        x["scheda"] = _lavori() / x["codice"] / f"{x['codice']}.md"
        x["mtime_ns"] = _mtime(x["scheda"])
        x["field_base"] = campi[x["label"]]
        cartella = _lavori() / x["codice"] / "da mandare in firma" / x["label"]
        x["cartella_pronta"] = cartella.is_dir() and any(cartella.iterdir())
    return da_mandare, in_firma


def stato_invii() -> tuple[dict, list[str]]:
    return build_stato_invii.collect()


def approvazioni_scadute() -> list[dict]:
    """Resoconti che chiudi_approvazione chiuderebbe oggi (find_pending usa date.today())."""
    out = []
    for md in sorted(chiudi_approvazione.find_pending()):
        fm = parse_frontmatter(md)
        out.append({"path": md, "mtime_ns": _mtime(md), "stem": md.stem,
                    "codice": fm.get("codice_rilascio", md.parent.parent.name),
                    "tipo": fm.get("tipo_riunione", ""), "data": fm.get("data_riunione", ""),
                    "scadenza": fm.get("data_scadenza_approvazione", "")})
    return out
