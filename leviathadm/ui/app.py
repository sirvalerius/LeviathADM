"""Entrypoint: costruisce l'indice, avvia il watcher, serve la UI. Mai reload=True.

Routing: una @ui.page per rotta (non ui.sub_pages: NiceGUI vieta header/drawer
dentro SubPages, e la shell li usa). Le viste restano funzioni render_*(...)
indipendenti dal meccanismo di routing.
"""
from __future__ import annotations
import asyncio
import logging

from nicegui import app, background_tasks, ui

from leviathadm.ui import state
from leviathadm.vault.index import VaultIndex
from leviathadm.vault.paths import VAULT_ROOT
from leviathadm.vault.watcher import avvia_watcher

_stop = asyncio.Event()

# host=127.0.0.1: app locale mono-utente con rotte di scrittura e senza autenticazione —
# senza host NiceGUI ascolterebbe su tutte le interfacce (rete d'ufficio, VPN).
# reload=False è OBBLIGATORIO: il reloader di uvicorn su Windows uccide la console che ha lanciato l'app.
RUN_KWARGS = dict(title='LeviathADM', host='127.0.0.1', port=8080, native=False, reload=False, show=False)


def _registra_rotte() -> None:
    from leviathadm.ui.pages import (anagrafica, azioni, bozze, da_collaudare, da_firmare, home, log_azioni, manuale, nota, nuovo, resoconto,
                                     resoconto_modifica, rilascio, rilascio_modifica, scadenze, stato_invii, verbale)

    @ui.page('/azioni')
    def _azioni():
        azioni.render_azioni()

    @ui.page('/anagrafica')
    def _anagrafica():
        anagrafica.render_anagrafica()

    @ui.page('/log')
    def _log():
        log_azioni.render_log()

    @ui.page('/bozze')
    def _bozze():
        bozze.render_bozze()

    @ui.page('/da-collaudare')
    def _da_collaudare():
        da_collaudare.render_da_collaudare()

    @ui.page('/da-firmare')
    def _da_firmare():
        da_firmare.render_da_firmare()

    @ui.page('/verbale/{id}')
    def _verbale(id: str):
        verbale.render_verbale(id)

    @ui.page('/scadenze')
    def _scadenze():
        scadenze.render_scadenze()

    @ui.page('/stato-invii')
    def _stato_invii():
        stato_invii.render_stato_invii()

    @ui.page('/')
    def _home(anno: str = ''):
        home.render_home(anno)

    @ui.page('/resoconto/{id}')
    def _resoconto(id: str):
        resoconto.render_resoconto(id)

    @ui.page('/resoconto/{id}/modifica')
    def _resoconto_modifica(id: str):
        resoconto_modifica.render_modifica(id)

    @ui.page('/rilascio/{codice}')
    def _rilascio(codice: str):
        rilascio.render_rilascio(codice)

    @ui.page('/rilascio/{codice}/modifica')
    def _modifica(codice: str):
        rilascio_modifica.render_modifica(codice)

    @ui.page('/nuovo')
    def _nuovo():
        nuovo.render_nuovo()

    @ui.page('/nota/{id}')
    def _nota(id: str):
        nota.render_nota(id)

    @ui.page('/manuale')
    def _manuale():
        manuale.render_manuale()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
    state.INDEX = VaultIndex(VAULT_ROOT)
    state.INDEX.load_all()
    from leviathadm.vault import esecutore
    import machine_config
    state.DEPS = esecutore.dipendenze_disponibili()
    state.MASTER = machine_config.is_master()
    state.PORTA = int(RUN_KWARGS['port'])
    logging.getLogger('leviathadm').info('ruolo: %s · dipendenze: %s', 'master' if state.MASTER else 'slave', sorted(state.DEPS))
    logging.getLogger('leviathadm').info('indice: %d note, piani %s', len(state.INDEX.note), state.INDEX.anni())
    _registra_rotte()

    @app.on_startup
    async def _avvia_watcher():
        background_tasks.create(avvia_watcher(state.INDEX, _stop), name='vault-watcher')

    @app.on_shutdown
    async def _ferma_watcher():
        _stop.set()

    ui.run(**RUN_KWARGS)


if __name__ in {'__main__', '__mp_main__'}:
    main()
