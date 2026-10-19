"""rigenera_resoconto.py — rigenera il .docx di un resoconto a partire dal .md.

Parsa il resoconto markdown (frontmatter, tabelle OBIETTIVO/PARTECIPANTI,
sezioni testuali) e riempie il template Word con fill_template.fill_resoconto,
salvando il .docx accanto al .md con lo stesso nome.

La DATA COMPILAZIONE è sempre la data di esecuzione di questa routine (oggi):
viene forzata a oggi nel .docx e riallineata nel .md (frontmatter + tabella).

Uso:
    python scripts/rigenera_resoconto.py "<percorso resoconto.md>" [...]
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fill_template import fill_resoconto


def _split_sections(text: str) -> dict[str, str]:
    """Mappa nome sezione H2 -> contenuto grezzo."""
    parts = re.split(r"^## +(.+?) *$", text, flags=re.M)
    sections = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip()] = parts[i + 1]
    return sections


def _kv_table(section: str) -> dict[str, str]:
    """Tabella a due colonne | **CHIAVE** | valore | -> dict."""
    out = {}
    for m in re.finditer(r"^\| +\*\*(.+?)\*\* +\| *(.*?) *\|", section, flags=re.M):
        out[m.group(1).strip().upper()] = m.group(2).strip()
    return out


def parse_resoconto_md(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")

    title_m = re.search(r"^# +(.+)$", text, flags=re.M)
    if not title_m:
        raise ValueError(f"Titolo H1 non trovato in {md_path}")

    sec = _split_sections(text)
    riunione = _kv_table(sec.get("RIUNIONE", ""))
    resoconto = _kv_table(sec.get("RESOCONTO", ""))
    obiettivo = _kv_table(sec.get("OBIETTIVO", ""))

    # LISTA PARTECIPANTI: blocco ADM (3 colonne) e blocco SOGEI (1 colonna)
    part = sec.get("LISTA PARTECIPANTI", "")
    adm_block = part.split("**SOGEI**")[0]
    sogei_block = part.split("**SOGEI**")[1] if "**SOGEI**" in part else ""

    adm_participants = []
    for m in re.finditer(r"^\|(.+)\|$", adm_block, flags=re.M):
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) == 3:
            ruolo, ufficio, nome = cells
        elif len(cells) == 2:
            # Riga senza colonna Ufficio esplicita (es. ruolo già concatenato
            # con "-" alla direzione/ufficio): trattata come ufficio vuoto.
            ruolo, ufficio, nome = cells[0], "", cells[1]
        else:
            continue
        if ruolo.lower().startswith(("ruolo", "---", ":--")) or set(ruolo) <= set("-: "):
            continue
        adm_participants.append((ruolo, ufficio, nome))

    sogei_participants = []
    for m in re.finditer(r"^\| *([^|]+?) *\|$", sogei_block, flags=re.M):
        nome = m.group(1).strip()
        if nome.lower() == "nome" or set(nome) <= set("-: "):
            continue
        sogei_participants.append(nome)

    def _clean_paragraphs(body: str) -> list[str]:
        body = body.split("\n---")[0]
        return [p.strip().replace("\n", " ") for p in re.split(r"\n\s*\n", body) if p.strip()]

    def paragraphs(name: str) -> list[str]:
        return _clean_paragraphs(sec.get(name, ""))

    def paragraphs_bullets(name: str) -> list[tuple[str, bool]]:
        """Come paragraphs(), ma ogni bullet '- ...' diventa un paragrafo a sé:
        serve per ARGOMENTI/ESITO del collaudo, che mescolano prosa ed elenchi.
        Ogni elemento è (testo, is_bullet) — fill_template.py usa is_bullet per
        scegliere la formattazione giusta (punto o testo semplice), non più la
        posizione: il numero di righe può quindi variare liberamente da
        resoconto a resoconto senza rompere l'elenco puntato."""
        body = sec.get(name, "").split("\n---")[0]
        out: list[tuple[str, bool]] = []
        buf: list[str] = []
        buf_bullet = False

        def _flush():
            if buf:
                text = re.sub(r"\s+", " ", " ".join(buf).replace("**", "")).strip()
                out.append((text, buf_bullet))

        bullet_marker = re.compile(r"^[-*]\s+")
        for line in body.splitlines():
            s = line.strip()
            if not s:
                _flush(); buf.clear(); buf_bullet = False
            elif bullet_marker.match(s):
                _flush(); buf.clear()
                buf_bullet = True
                buf.append(bullet_marker.sub("", s))
            else:
                buf.append(s)  # continuazione: eredita lo stato (bullet o prosa) del buf corrente
        _flush()
        return out

    azioni = [
        m.group(1).strip()
        for m in re.finditer(r"^- +(.+(?:\n {2,}.+)*)", sec.get("AZIONI CONCORDATE", ""), flags=re.M)
    ]
    azioni = [re.sub(r"\s+", " ", a) for a in azioni]

    obiettivo_paras = paragraphs("OBIETTIVO DELLA RIUNIONE")
    is_collaudo = "ESITO" in sec and "AZIONI CONCORDATE" not in sec

    KNOWN_SECTIONS = {
        "RIUNIONE", "RESOCONTO", "OBIETTIVO", "LISTA PARTECIPANTI",
        "OBIETTIVO DELLA RIUNIONE", "ARGOMENTI TRATTATI", "ESITO",
        "AZIONI CONCORDATE",
    }
    # Sezioni "## ..." extra non previste dal template (es. un addendum
    # aggiunto a un resoconto già inviato, tipo "AGGIORNAMENTO DEL ..."):
    # non hanno un posto fisso nel .docx, quindi vengono accodate dopo
    # ESITO/AZIONI CONCORDATE — vedi fill_template._append_extra_sections.
    extra_sections = [
        (heading, _clean_paragraphs(raw))
        for heading, raw in sec.items()
        if heading not in KNOWN_SECTIONS
    ]

    return {
        "tipo_riunione": "Collaudo" if is_collaudo else "",
        "esito_testi": paragraphs_bullets("ESITO") if is_collaudo else [],
        "extra_sections": extra_sections,
        # "approvazione telematicamente" nel testo ESITO (vedi Template/markdown/
        # resoconto_collaudo_telematico.md) → template Word senza sezione FIRME
        "approvazione_telematica": is_collaudo and "telematicamente" in sec.get("ESITO", ""),
        "title": title_m.group(1).strip(),
        "data_riunione": riunione.get("DATA", ""),
        "canale": riunione.get("CANALE", "MICROSOFT TEAMS"),
        "compilato_da": resoconto.get("COMPILATO DA", ""),
        "data_compilazione": resoconto.get("DATA COMPILAZIONE", ""),
        "codice_progetto": obiettivo.get("CODICE PROGETTO", ""),
        "descrizione_progetto": obiettivo.get("DESCRIZIONE PROGETTO", ""),
        "codice_sottoprogetto": obiettivo.get("CODICE SOTTOPROGETTO", ""),
        "descrizione_sottoprogetto": obiettivo.get("DESCRIZIONE SOTTOPROGETTO", ""),
        "codice_rilascio": obiettivo.get("CODICE RILASCIO", ""),
        "descrizione_rilascio": obiettivo.get("DESCRIZIONE RILASCIO", ""),
        "vincoli_normativi": obiettivo.get("VINCOLI NORMATIVI", "NO"),
        "variazione_date": obiettivo.get("VARIAZIONE DATE PREVISTE", "NO"),
        "variazione_effort": obiettivo.get("VARIAZIONE EFFORT", "NO"),
        "privacy": obiettivo.get("PRIVACY", "DA VERIFICARE"),
        "adm_participants": adm_participants,
        "sogei_participants": sogei_participants,
        "obiettivo_testo": " ".join(obiettivo_paras),
        "argomenti_testi": paragraphs_bullets("ARGOMENTI TRATTATI") if is_collaudo else paragraphs("ARGOMENTI TRATTATI"),
        "azioni_testi": azioni,
    }


def _forza_data_compilazione_oggi(md_path: Path, data: dict) -> None:
    """La data di compilazione è la data di esecuzione della routine: la forza a
    oggi nel dict (per il .docx) e nel .md (frontmatter ISO + tabella RESOCONTO)."""
    oggi_it = date.today().strftime("%d/%m/%Y")
    data["data_compilazione"] = oggi_it
    text = md_path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^data_compilazione:.*$",
                  f"data_compilazione: {date.today().isoformat()}", text)
    text = re.sub(r"(\|\s*\*\*DATA COMPILAZIONE\*\*\s*\|\s*).*?(\s*\|)",
                  lambda m: m.group(1) + oggi_it + m.group(2), text)
    md_path.write_text(text, encoding="utf-8")


def rigenera(md_path: Path) -> Path:
    """Rigenera il .docx dal .md (DATA COMPILAZIONE = oggi) e rimuove il .msg obsoleto, che il sync rigenera.
    Usata dalla CLI, da LeviathADM e dal sync del master per i .docx superati (md modificato dopo il docx)."""
    data = parse_resoconto_md(md_path)
    _forza_data_compilazione_oggi(md_path, data)
    out = fill_resoconto(data, md_path.with_suffix(".docx"))
    eml = md_path.with_suffix(".msg")
    if eml.exists():
        eml.unlink()
        print("  .msg rimosso (sync lo rigenererà con il .docx aggiornato)")
    return Path(out)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for arg in sys.argv[1:]:
        md_path = Path(arg)
        if not md_path.is_file():
            sys.exit(f"File non trovato: {md_path}")
        data = parse_resoconto_md(md_path)
        out = rigenera(md_path)
        print(f"Generato: {out}")
        coda = (f"esito: {len(data['esito_testi'])} ¶" if data.get("esito_testi")
                else f"azioni: {len(data['azioni_testi'])}")
        extra = f" · extra: {len(data['extra_sections'])}" if data.get("extra_sections") else ""
        print(f"  ADM: {len(data['adm_participants'])} · SOGEI: {len(data['sogei_participants'])}"
              f" · argomenti: {len(data['argomenti_testi'])} ¶ · {coda}{extra}")


if __name__ == "__main__":
    main()
