"""Stato condiviso del processo: un solo VaultIndex per tutti i client."""
from __future__ import annotations
from leviathadm.vault.index import VaultIndex

INDEX: VaultIndex | None = None
ESECUZIONE = None          # esecutore.Esecuzione in corso: una sola per processo
DEPS: set[str] = set()     # {"outlook","word","pandoc"} rilevate all'avvio
MASTER: bool = False       # machine_config.is_master() all'avvio
PORTA: int = 8080          # porta del server (RUN_KWARGS), usata dal riavvio


def get_index() -> VaultIndex:
    assert INDEX is not None, "INDEX non inizializzato: chiamare app.main()"
    return INDEX
