"""Tema LeviathADM (PRODUCT.md): istituzionale, denso, movimento discreto."""
from nicegui import app, ui

STATO_COLORS = {
    'Da Avviare': 'grey-8', 'Bozza': 'grey-8', 'Startup': 'indigo-8',
    'In corso': 'blue-9', 'Analisi': 'blue-9', 'In Verifica': 'orange-9',
    'Collaudo': 'deep-orange-9', 'Concluso': 'green-8', 'Rinominato': 'grey-6',
}

# ordine del ciclo di vita (SCHEMA.md): usato per ordinare/filtrare per stato invece dell'alfabetico
STATI_ORDINE = ['Da Avviare', 'Bozza', 'Startup', 'Analisi', 'In corso', 'In Verifica', 'Collaudo', 'Concluso', 'Rinominato']


def rango_stato(stato: str) -> int:
    """Posizione nel ciclo di vita; stati sconosciuti in coda."""
    return STATI_ORDINE.index(stato) if stato in STATI_ORDINE else len(STATI_ORDINE)


_CSS = '''
.lv-row { transition: background-color .15s ease-out; }
.lv-row:hover { background-color: #f1f5f9; }
.lv-card { border: 1px solid #e2e8f0; border-radius: 6px; background-color: #ffffff; }
a:focus-visible { outline: 2px solid #1e40af; outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { .lv-row { transition: none; } }

/* barra laterale: velo del colore dell'header (slate-800) ben visibile, bordo verticale pieno dello stesso colore */
.lv-drawer { background-color: rgba(30, 41, 59, 0.16) !important; border-right: 4px solid #1e293b !important; }
.lv-drawer a { border-radius: 4px; }
.lv-drawer a:hover { background-color: rgba(30, 41, 59, 0.22); }

/* righe alternate: tabelle Quasar, tabelle HTML, elenchi a righe (lv-riga) */
.q-table tbody tr:nth-child(even) > td { background-color: #e2e8f0; }
.q-table tbody tr:hover > td { background-color: #cbd5e1; }
.q-table thead th { background-color: #cbd5e1; font-weight: 600; }
table.lv-card tbody tr:nth-child(even) { background-color: #e2e8f0; }
table.lv-card tbody tr:hover { background-color: #cbd5e1; }
table.lv-card thead th { background-color: #cbd5e1; }
.lv-riga { padding: 6px 8px; border-radius: 4px; }
.lv-riga:nth-child(even) { background-color: #e2e8f0; }
.lv-riga:hover { background-color: #cbd5e1; }

/* tabella dei rilasci: carattere più grande, colonne a larghezza fissa, testo troncato con tooltip */
.lv-tabella-grande .q-table { table-layout: fixed; width: 100%; }
.lv-tabella-grande .q-table td, .lv-tabella-grande .q-table th { font-size: 1.05rem; padding-top: 10px; padding-bottom: 10px; }
.lv-tabella-grande .q-table td.lv-ellissi, .lv-tabella-grande .q-table th { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* tema scuro (body--dark di Quasar): stesse gerarchie, palette slate invertita */
.body--dark { background-color: #0f172a; color: #e2e8f0; }
/* il primario (pulsanti a contorno) in tema scuro è più chiaro: lo imposta ui.colors in apply_theme/cambia_tema,
   perché le utility Tailwind (.text-primary) stanno in un layer CSS e battono qualunque override con !important */
.body--dark .lv-card { border-color: #334155; background-color: #1e293b; }
.body--dark .q-card, .body--dark .q-dialog .q-card, .body--dark .q-expansion-item, .body--dark .q-stepper { background-color: #1e293b; color: #e2e8f0; }
.body--dark .lv-drawer { background-color: #1e293b !important; border-right-color: #475569 !important; }
.body--dark .lv-drawer a:hover { background-color: rgba(255, 255, 255, 0.08); }
.body--dark .text-slate-800, .body--dark .text-slate-700 { color: #e2e8f0 !important; }
.body--dark .text-slate-600, .body--dark .text-slate-500 { color: #94a3b8 !important; }
.body--dark .text-slate-400 { color: #64748b !important; }
.body--dark .text-blue-900 { color: #93c5fd !important; }
.body--dark .text-amber-800, .body--dark .text-amber-900 { color: #fcd34d !important; }
.body--dark .text-red-800 { color: #fca5a5 !important; }
.body--dark .text-green-800 { color: #86efac !important; }
.body--dark .bg-amber-100 { background-color: #78350f !important; }
.body--dark .bg-blue-100, .body--dark .bg-blue-50 { background-color: #1e3a8a !important; }
.body--dark .border-slate-200 { border-color: #334155 !important; }
.body--dark .border-amber-300 { border-color: #b45309 !important; }
.body--dark .lv-row:hover { background-color: #334155; }
.body--dark .q-table { background-color: #1e293b; color: #e2e8f0; }
.body--dark .q-table tbody tr:nth-child(even) > td { background-color: #273449; }
.body--dark .q-table tbody tr:hover > td { background-color: #334155; }
.body--dark .q-table thead th { background-color: #334155; color: #e2e8f0; }
.body--dark table.lv-card tbody tr:nth-child(even) { background-color: #273449; }
.body--dark table.lv-card tbody tr:hover { background-color: #334155; }
.body--dark table.lv-card thead th { background-color: #334155; }
.body--dark .lv-riga:nth-child(even) { background-color: #273449; }
.body--dark .lv-riga:hover { background-color: #334155; }
.body--dark .q-log, .body--dark pre { background-color: #0f172a; color: #e2e8f0; }
.body--dark .nicegui-markdown table td, .body--dark .nicegui-markdown table th { border-color: #475569; }
.body--dark .nicegui-markdown table th { background-color: #334155; }
.body--dark .nicegui-markdown table tr:nth-child(even) td { background-color: #273449; }
.body--dark .nicegui-markdown code { background-color: #0f172a; color: #e2e8f0; }
.body--dark .nicegui-markdown blockquote { border-left-color: #475569; color: #94a3b8; }
.body--dark .nicegui-markdown h1, .body--dark .nicegui-markdown h2, .body--dark .nicegui-markdown h3 { color: #f1f5f9; }
.body--dark a { color: #93c5fd; }
'''


def tema_scuro_salvato() -> bool:
    return bool(app.storage.general.get('tema_scuro', True))   # predefinito: scuro


PRIMARIO = {False: '#1e40af', True: '#3b82f6'}   # chiaro: blu istituzionale; scuro: più chiaro, leggibile sul fondo


def _colori(scuro: bool) -> None:
    ui.colors(primary=PRIMARIO[scuro], secondary='#0f766e', accent='#9333ea',
              positive='#16a34a', negative='#dc2626', info='#06b6d4', warning='#d97706')


def apply_theme() -> ui.dark_mode:
    """Colori, CSS e modalità scura (preferenza in app.storage.general: app mono-utente)."""
    scuro = tema_scuro_salvato()
    _colori(scuro)
    ui.add_css(_CSS)
    return ui.dark_mode(value=scuro)


def cambia_tema(dm: ui.dark_mode) -> None:
    dm.value = not dm.value
    app.storage.general['tema_scuro'] = dm.value
    _colori(dm.value)
