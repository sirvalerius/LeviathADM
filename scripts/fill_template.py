"""
fill_template.py — fills the Word Resoconto template programmatically.

Usage (standalone test):
  python fill_template.py

Or import and call fill_resoconto(data, output_path).
"""
from __future__ import annotations

import copy
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TEMPLATE = Path(__file__).parent.parent / "Template" / "Template - ADMXXX-XX-XX 2026MMGG Resoconto Startup.docx"
TEMPLATE_COLLAUDO = Path(__file__).parent.parent / "Template" / "Template - ADMXXX-XX-XX 2026MMGG Resoconto Collaudo.docx"
TEMPLATE_COLLAUDO_TELEMATICO = Path(__file__).parent.parent / "Template" / "Template - ADMXXX-XX-XX 2026MMGG Resoconto Collaudo (approvazione telematica).docx"

_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _set_para_text(para, text: str) -> None:
    """Replace paragraph text, preserving the rPr of the first run exactly as-is.
    Removes surplus runs so only one run remains (avoids mixed-font paragraphs).
    Also strips spurious w:ind from pPr so placeholder indentation doesn't leak."""
    runs = para.runs
    # Remove all runs except the first
    for run in runs[1:]:
        run._r.getparent().remove(run._r)
    if runs:
        runs[0].text = text
    elif text:
        # Fallback: no runs in template paragraph — create one inheriting style font
        para.add_run(text)
    # Remove any paragraph-level indentation left over from template placeholders
    pPr = para._p.find(qn("w:pPr"))
    if pPr is not None:
        for ind in pPr.findall(qn("w:ind")):
            pPr.remove(ind)


def _set_cell_text(cell, text: str) -> None:
    """Replace cell text, preserving run formatting of the first run."""
    for para in cell.paragraphs:
        for run in para.runs:
            run.text = ""
    first_para = cell.paragraphs[0] if cell.paragraphs else None
    if first_para:
        if first_para.runs:
            first_para.runs[0].text = text
        elif text:
            first_para.add_run(text)


def _add_table_row(table, values: list[str]):
    """Append a row to a table by deep-copying the last row's XML."""
    src_tr = table.rows[-1]._tr
    new_tr = copy.deepcopy(src_tr)
    table._tbl.append(new_tr)
    new_row = table.rows[-1]
    for i, val in enumerate(values):
        if i < len(new_row.cells):
            _set_cell_text(new_row.cells[i], str(val))
    return new_row


def _has_numpr(p) -> bool:
    pPr = p._p.find(qn("w:pPr"))
    return pPr is not None and pPr.find(qn("w:numPr")) is not None


def _clone_paragraph_with_text(template_p, text: str):
    """Deep-copies template_p's XML (keeps its formatting/numPr) and sets its
    text, collapsing it to a single run."""
    new_elem = copy.deepcopy(template_p)
    for t in new_elem.findall(".//" + qn("w:t")):
        t.text = ""
    runs = new_elem.findall(".//" + qn("w:r"))
    if runs:
        for r in runs[1:]:
            r.getparent().remove(r)
        t_elem = runs[0].find(qn("w:t"))
        if t_elem is None:
            t_elem = OxmlElement("w:t")
            runs[0].append(t_elem)
        t_elem.text = text
        t_elem.set(_XML_SPACE, "preserve")
    return new_elem


def _replace_section_paragraphs(doc, section_header: str, new_items: list) -> None:
    """
    Replace all consecutive Body Text paragraphs that follow a List Paragraph
    with the given section_header, with exactly len(new_items) paragraphs.

    Each item is either a plain string (rendered as a normal paragraph) or a
    (text, is_bullet) tuple. Formatting is picked explicitly by is_bullet —
    from the template's own bulleted/plain Body Text paragraphs under this
    section — never by position. This keeps bullet lists intact (and plain
    sentences plain) regardless of how many lines new_items has compared to
    the template's original fixed paragraph count (e.g. ARGOMENTI/ESITO del
    collaudo, dove prosa ed elenchi si mescolano e il numero di righe varia
    da resoconto a resoconto).

    Returns (header_elem, trailing_elem, plain_ref_elem) — None, None, None
    if the section wasn't found — so the caller can append further ad-hoc
    content (see _append_extra_sections) right after it.
    """
    items = [it if isinstance(it, tuple) else (it, False) for it in new_items]

    paras = doc.paragraphs
    header_idx = None
    for i, p in enumerate(paras):
        if p.style.name == "List Paragraph" and p.text.strip() == section_header:
            header_idx = i
            break
    if header_idx is None:
        return None, None, None

    body_paras = []
    for p in paras[header_idx + 1:]:
        if p.style.name == "Body Text":
            body_paras.append(p)
        else:
            break
    if not body_paras:
        return None, None, None

    bullet_ref = next((p._p for p in body_paras if _has_numpr(p)), None)
    plain_ref = next((p._p for p in body_paras if not _has_numpr(p)), body_paras[0]._p)

    header_elem = paras[header_idx]._p
    anchor = body_paras[-1]._p
    for text, is_bullet in items:
        template_elem = bullet_ref if (is_bullet and bullet_ref is not None) else plain_ref
        new_elem = _clone_paragraph_with_text(template_elem, text)
        anchor.addnext(new_elem)
        anchor = new_elem

    # Trailing empty (plain, no indent) paragraph to close the section
    trailing = _clone_paragraph_with_text(plain_ref, "")
    pPr = trailing.find(qn("w:pPr"))
    if pPr is not None:
        for ind in pPr.findall(qn("w:ind")):
            pPr.remove(ind)
    anchor.addnext(trailing)
    anchor = trailing

    # Drop the original template paragraphs now that the fresh sequence is in place
    for p in body_paras:
        p._p.getparent().remove(p._p)

    return header_elem, anchor, plain_ref


def _append_extra_sections(header_ref, anchor, plain_ref, extra_sections: list) -> None:
    """Appends ad-hoc '## Heading' sections found in the markdown that have
    no counterpart in the Word template (e.g. a dated addendum added to a
    resoconto that was already sent) right after ESITO/AZIONI CONCORDATE.
    Reuses the section header's own formatting for the new heading, and
    plain Body Text for its paragraphs."""
    if not extra_sections or header_ref is None or anchor is None:
        return
    for heading, body_paragraphs in extra_sections:
        new_header = _clone_paragraph_with_text(header_ref, heading)
        anchor.addnext(new_header)
        anchor = new_header
        for text in body_paragraphs:
            new_para = _clone_paragraph_with_text(plain_ref, text)
            anchor.addnext(new_para)
            anchor = new_para


# ---------------------------------------------------------------------------
# Main fill function
# ---------------------------------------------------------------------------

def fill_resoconto(data: dict, output_path: Path | str | None = None) -> Path:
    """
    Fill the Word template and save the result.

    Required keys in data:
      title                  — full document title line
      data_riunione          — date string, e.g. "12/05/2026"
      compilato_da           — name of compiler
      data_compilazione      — compilation date string
      codice_progetto
      descrizione_progetto
      codice_sottoprogetto
      descrizione_sottoprogetto
      codice_rilascio
      descrizione_rilascio

    Optional keys (default shown):
      canale                 — "MICROSOFT TEAMS"
      vincoli_normativi      — "NO"
      variazione_date        — "NO"
      variazione_effort      — "NO"
      privacy                — "DA VERIFICARE"
      adm_participants       — list of (ruolo, ufficio, nome); roles starting
                               with "(PM)", "(RA)", "(RP)", "(RB)" map to the
                               four template rows; extras are appended
      sogei_participants     — list of name strings
      obiettivo_testo        — single string for OBIETTIVO DELLA RIUNIONE
      argomenti_testi        — list of strings for ARGOMENTI TRATTATI
      azioni_testi           — list of strings for AZIONI CONCORDATE (startup/analisi/SAL)
      esito_testi            — list of strings for ESITO (solo collaudo). Se
                               valorizzato (o tipo_riunione contiene "collaudo")
                               si usa il template Collaudo e la sezione ESITO
                               sostituisce AZIONI CONCORDATE.
      approvazione_telematica — bool (solo collaudo): se True usa la variante
                               di template senza sezione FIRME, che chiude con
                               "I partecipanti forniscono la propria
                               approvazione telematicamente."
    """
    is_collaudo = bool(data.get("esito_testi")) or "collaudo" in str(data.get("tipo_riunione", "")).lower()
    if is_collaudo:
        template_path = TEMPLATE_COLLAUDO_TELEMATICO if data.get("approvazione_telematica") else TEMPLATE_COLLAUDO
    else:
        template_path = TEMPLATE
    doc = Document(template_path)

    # --- Title paragraph ---
    _set_para_text(doc.paragraphs[0], data["title"])

    # --- Table 0: RIUNIONE ---
    t0 = doc.tables[0]
    _set_cell_text(t0.rows[1].cells[1], data["data_riunione"])
    _set_cell_text(t0.rows[2].cells[1], data.get("canale", "MICROSOFT TEAMS"))

    # --- Table 1: RESOCONTO ---
    t1 = doc.tables[1]
    _set_cell_text(t1.rows[1].cells[1], data["compilato_da"])
    _set_cell_text(t1.rows[2].cells[1], data["data_compilazione"])
    _set_cell_text(t1.rows[4].cells[1], data.get("data_approvazione", ""))

    # --- Table 2: OBIETTIVO ---
    t2 = doc.tables[2]
    _set_cell_text(t2.rows[1].cells[1],  data["codice_progetto"])
    _set_cell_text(t2.rows[2].cells[1],  data["descrizione_progetto"])
    _set_cell_text(t2.rows[3].cells[1],  data["codice_sottoprogetto"])
    _set_cell_text(t2.rows[4].cells[1],  data["descrizione_sottoprogetto"])
    _set_cell_text(t2.rows[5].cells[1],  data["codice_rilascio"])
    _set_cell_text(t2.rows[6].cells[1],  data["descrizione_rilascio"])
    _set_cell_text(t2.rows[7].cells[1],  data.get("vincoli_normativi", "NO"))
    _set_cell_text(t2.rows[8].cells[1],  data.get("variazione_date",   "NO"))
    _set_cell_text(t2.rows[9].cells[1],  data.get("variazione_effort", "NO"))
    _set_cell_text(t2.rows[10].cells[1], data.get("privacy", "DA VERIFICARE"))

    # --- Table 3: ADM participants ---
    # Enforce fixed order: PM, RA, RP (any number), RB, then other roles.
    # Template has 4 data rows (1-4); extra rows are appended by deep-copying the last.
    t3 = doc.tables[3]
    ROLE_ORDER = ["PM", "RA", "RP", "RB"]
    buckets: dict[str, list] = {r: [] for r in ROLE_ORDER}
    buckets["OTHER"] = []

    for ruolo, ufficio, nome in data.get("adm_participants", []):
        matched = next((r for r in ROLE_ORDER if ruolo.startswith(f"({r})")), None)
        buckets[matched if matched else "OTHER"].append((ruolo, ufficio, nome))

    ordered = []
    for role in ROLE_ORDER:
        ordered.extend(buckets[role])
    ordered.extend(buckets["OTHER"])

    for i, (ruolo, ufficio, nome) in enumerate(ordered):
        # Col. 0 e col. 1 sono unite nel template: l'ufficio va concatenato al
        # ruolo con "-" e la col. 1 resta sempre vuota. Scrivere testo in
        # entrambe rompe il merge della cella nel .docx.
        if ufficio.strip():
            ruolo = f"{ruolo} - {ufficio.strip()}"
            ufficio = ""
        if i < 4:                          # fill the 4 template rows
            row = t3.rows[i + 1]
            _set_cell_text(row.cells[0], ruolo)
            _set_cell_text(row.cells[1], ufficio)
            _set_cell_text(row.cells[2], nome)
        else:                              # append extra rows after the last
            _add_table_row(t3, [ruolo, ufficio, nome])

    # --- Table 4: SOGEI participants ---
    # Col 0 empty, col 1 empty, col 2 = nome (same position as ADM "Nome" column)
    t4 = doc.tables[4]
    sogei = data.get("sogei_participants", [])
    for i in range(min(len(sogei), 3)):
        _set_cell_text(t4.rows[i + 1].cells[0], "")
        _set_cell_text(t4.rows[i + 1].cells[1], "")
        _set_cell_text(t4.rows[i + 1].cells[2], sogei[i])
    for i in range(len(sogei), 3):          # clear unused template rows
        _set_cell_text(t4.rows[i + 1].cells[2], "")
    for nome in sogei[3:]:                  # add rows beyond the 3 in the template
        _add_table_row(t4, ["", "", nome])

    # --- Text sections ---
    _replace_section_paragraphs(
        doc, "OBIETTIVO DELLA RIUNIONE",
        [data.get("obiettivo_testo", "")]
    )
    _replace_section_paragraphs(
        doc, "ARGOMENTI TRATTATI",
        data.get("argomenti_testi", [])
    )
    if is_collaudo:
        last = _replace_section_paragraphs(doc, "ESITO", data.get("esito_testi", []))
    else:
        last = _replace_section_paragraphs(doc, "AZIONI CONCORDATE", data.get("azioni_testi", []))
    _append_extra_sections(*last, data.get("extra_sections", []))

    # --- Save ---
    if output_path is None:
        output_path = Path("output_resoconto.docx")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


def set_data_approvazione(docx_path: Path | str, data_str: str) -> None:
    """Compila il campo 'Data approvazione' in un resoconto .docx già generato.

    Alcuni .docx storici hanno il run di questa cella privo di `<w:rPr>`
    (nessuna formattazione esplicita): in quel caso Word applica il font/
    dimensione di default (es. 12pt) invece del 10pt usato in tutta la
    tabella, producendo una data visibilmente più grande delle altre. Per
    essere robusti a questo stato, la formattazione viene sempre allineata
    a quella della cella "Data compilazione" (riga 2), popolata fin dalla
    generazione iniziale e quindi affidabile."""
    docx_path = Path(docx_path)
    doc = Document(str(docx_path))
    t1 = doc.tables[1]
    target_cell = t1.rows[4].cells[1]
    _set_cell_text(target_cell, data_str)

    ref_runs = t1.rows[2].cells[1].paragraphs[0].runs
    target_runs = target_cell.paragraphs[0].runs
    if ref_runs and target_runs:
        ref_rPr = ref_runs[0]._r.find(qn("w:rPr"))
        target_r = target_runs[0]._r
        old_rPr = target_r.find(qn("w:rPr"))
        if old_rPr is not None:
            target_r.remove(old_rPr)
        if ref_rPr is not None:
            target_r.insert(0, copy.deepcopy(ref_rPr))

    doc.save(str(docx_path))


# ---------------------------------------------------------------------------
# Standalone test — ADM953-01-0L Prima Analisi 12/05/2026
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data = {
        "title": "ADM953-01-0L - RESOCONTO PRIMA RIUNIONE DI ANALISI DEL 12/05/2026",
        "data_riunione": "12/05/2026",
        "canale": "MICROSOFT TEAMS",
        "compilato_da": "Astolfo Lunardi",
        "data_compilazione": "14/05/2026",
        "codice_progetto": "ADM953",
        "descrizione_progetto": "SISTEMA DEI CONTROLLI DEI GIOCHI",
        "codice_sottoprogetto": "ADM953-01",
        "descrizione_sottoprogetto": "Evoluzione del Sistema Integrato dei Controlli",
        "codice_rilascio": "ADM953-01-0L",
        "descrizione_rilascio": "Interoperabilita GDF",
        "vincoli_normativi": "NO",
        "variazione_date": "NO",
        "variazione_effort": "NO",
        "privacy": "DA VERIFICARE",
        "adm_participants": [
            ("(PM) DOTD - ATTUAZIONE PROGETTI E SICUREZZA INFORMATICA", "", "Astolfo Lunardi"),
            ("(RA) DOTD - GOVERNO E TRANSIZIONE DIGITALE",              "", "Tramontana Urbano"),
            ("(RP) DODT - ANALISI E PROCESSI",                          "", "Maestrale Cassiopea"),
            ("(RP) DODT - ANALISI E PROCESSI",                          "", "Isolotto Tiberio"),
            ("(RB) DGIO",                                               "", "Ciclone Nicodemo"),
            ("DGIO - Ufficio Territoriale",                             "", "Tramontana Brunilde"),
            ("DGIO - Ufficio Antifrode",                                "", "Aquilone Amerigo"),
            ("DGIO - Ufficio Territoriale",                             "", "Ortensia Amerigo"),
        ],
        "sogei_participants": [
            "Ciclone Gelsomina",
            "Alveare Fulgenzio",
            "Scirocco Ersilia",
        ],
        "obiettivo_testo": (
            "In data 12 maggio 2026 si e svolta la prima riunione di analisi, tenutasi a distanza, "
            "tra ADM e Sogei sul tema riguardante \"Evoluzione del Sistema Integrato dei Controlli\", "
            "con l'obiettivo di avviare l'analisi dei requisiti per il rilascio \"Interoperabilita GDF\"."
        ),
        "argomenti_testi": [
            "Il progetto si inquadra nel programma di interoperabilita tra il Sistema Integrato dei "
            "Controlli (SIC) e la Guardia di Finanza, limitatamente all'ambito giochi. Sogei ha "
            "illustrato la struttura dell'obiettivo, articolato in tre punti distinti.",

            "Il primo punto riguarda la visualizzazione, da parte degli uffici ADM, dei dati di "
            "controllo trasmessi dalla Guardia di Finanza tramite il sistema MUV (area tributaria). "
            "L'integrazione tecnica con MUV e gia completata e pronta per la messa in produzione; "
            "i dati arrivano sul SIC ma al momento risultano fini a se stessi, in quanto non collegati "
            "al flusso sanzionatorio. E emersa la necessita di definire quale tipo di visualizzazione "
            "rendere disponibile agli uffici e quale lavorazione, se prevista, essi debbano effettuare "
            "a fronte dei dati ricevuti. La progettazione dell'interfaccia sara curata da Anna Virginia "
            "Scirocco (SOGEI) nell'ambito della reingegnerizzazione del SIC.",

            "Il secondo punto riguarda lo scambio reciproco delle date di controllo tra ADM e Guardia "
            "di Finanza, al fine di evitare che lo stesso esercizio venga sottoposto a verifiche "
            "sovrapposte da parte di organi distinti nel corso dell'anno.",

            "Il terzo punto riguarda il completamento dell'integrazione con il sistema ARES, controparte "
            "extratributaria del MUV per la parte amministrativa. A differenza del MUV, il servizio con "
            "ARES e ancora da definire nel flusso di scambio dati. La dottoressa Ciclone ha rappresentato "
            "la necessita di affidare la gestione di ARES a un unico referente per garantire continuita, "
            "e ha comunicato che si coordinera con il dottor Ortensia e con Gianluca Ciaravola per definire "
            "l'assegnazione.",

            "Nel corso del confronto con gli uffici territoriali e emerso che il flusso tributario su "
            "STAMPS non viene attualmente utilizzato, in quanto storicamente giudicato poco praticabile; "
            "le violazioni amministrative vengono invece regolarmente inserite sul SIC e transitate su "
            "STAMPS. Il dottor Tramontana ha segnalato che l'anello mancante nel ciclo tributario e la "
            "redazione del Processo Verbale di Constatazione (PVC), di competenza dell'ufficio controlli, "
            "che dovrebbe transitare su STAMPS per completare l'iter fino all'atto di accertamento. "
            "Tale criticita, pur non rientrando nell'ambito diretto del presente obiettivo, e stata "
            "rilevata come priorita da affrontare in parallelo.",
        ],
        "azioni_testi": [
            "Scirocco Ersilia (SOGEI) predisporra una proposta di prototipo per la visualizzazione "
            "dei dati GDF sul SIC entro fine maggio / primi di giugno 2026, previo allineamento interno "
            "con Alveare Stefano.",

            "Ciclone Nicodemo (ADM) si coordinera con il dottor Ortensia e Gianluca Ciaravola per "
            "definire il referente responsabile del sistema ARES e del collegamento SIC-STAMPS per il "
            "flusso tributario.",

            "Seconda riunione di analisi fissata per lunedi 8 giugno 2026 (prima settimana disponibile "
            "dopo le ferie di inizio giugno).",

            "Data di fine analisi concordata: 1 luglio 2026.",
        ],
    }

    # Demo eseguibile a mano (`python fill_template.py`): scrive un .docx di
    # prova nella cartella corrente, senza dipendere dalla posizione del vault.
    out = fill_resoconto(data, Path("_demo Resoconto.docx"))
    print(f"Generato: {out}")
