"""Modelli tipizzati del vault: vista senza perdita sul markdown (SCHEMA.md)."""
from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .parsers import Wikilink, parse_data


class _Base(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class Riunione(_Base):
    data: str
    fase: str
    trascritto: str = ""
    resoconto_link: str = ""
    inviato: bool = False
    raw_row: list[str] = Field(default_factory=list)


class Azione(_Base):
    chiusa: bool
    testo: str
    testo_pulito: str
    scadenza: date | None = None


class Decisione(_Base):
    data: date | None
    testo: str


class Protocollo(_Base):
    tipo: str
    documento: str
    numero_adm: str
    data_adm: str
    rif_sogei: str
    registro: str


class Resoconto(_Base):
    path: Path
    stem: str
    tipo_riunione: str
    data_riunione: date | None
    stato: Literal["bozza", "inviato", "definitivo"]
    in_inviati: bool
    ha_docx: bool
    ha_msg: bool
    ha_pdf: bool
    frontmatter: dict[str, str]


class Nota(_Base):
    path: Path
    id: str
    titolo: str
    frontmatter: dict[str, str]
    corpo: str
    wikilink: list[Wikilink]
    tag: list[str]
    tipo: str
    mtime_ns: int


class Rilascio(_Base):
    codice: str
    path: Path
    id: str
    mtime_ns: int
    frontmatter: dict[str, str]
    stato: str
    descrizione_rilascio: str
    riunioni: list[Riunione]
    azioni: list[Azione]
    decisioni: list[Decisione]
    protocolli: list[Protocollo]
    prossima_riunione: str
    team_raw: str
    resoconti: list[Resoconto]
    verbali: list[Path] = Field(default_factory=list)
    sezioni: dict[str, str]
    problemi: list[str]

    def data(self, campo: str) -> date | None:
        return parse_data(self.frontmatter.get(campo, ""))

    @property
    def attivo(self) -> bool:
        return self.stato.strip().lower() != "rinominato"


class Progetto(_Base):
    codice: str
    titolo: str
    area: str
    path: Path
    id: str


class Sottoprogetto(_Base):
    codice: str
    titolo: str
    codice_progetto: str
    path: Path
    id: str


class Piano(_Base):
    anno: int
    root: Path
    rilasci: dict[str, Rilascio] = Field(default_factory=dict)
    progetti: dict[str, Progetto] = Field(default_factory=dict)
    sottoprogetti: dict[str, Sottoprogetto] = Field(default_factory=dict)


class Risultato(_Base):
    tipo: str
    titolo: str
    id: str
    path: Path
    snippet: str
    score: float
