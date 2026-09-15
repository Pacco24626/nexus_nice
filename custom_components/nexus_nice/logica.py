"""Logica del cancello senza Home Assistant: si prova a tavolino.

Qui stanno le regole che contano e che si possono sbagliare in silenzio:
quali entita' del gateway sono di questo cancello, quali eventi finiscono nello
storico, e quando il cancello a due ante e' in apertura pedonale.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

# Chiave interna -> (dominio, suffisso dell'unique_id dopo "nexus_nice_N").
# Gli unique_id sono congelati dal gateway (banco tools/prova_identita_ha.js);
# gli entity_id no: li rinomina Home Assistant e li puo' cambiare l'utente.
ENTITA: dict[str, tuple[str, str]] = {
    "cancello": ("cover", ""),
    "passo_passo": ("button", "_sbs"),
    "parziale": ("button", "_partial"),
    "luce": ("button", "_luce"),
    "riavvia": ("button", "_riavvia"),
    "registro_leggi": ("button", "_registro_leggi"),
    "registro": ("sensor", "_registro"),
    "sorgente_posizione": ("sensor", "_sorgente_posizione"),
    # Nel gateway l'id dice "totali", ma sono le manovre dall'ultima accensione
    # della centrale: la chiave interna dice cosa sono davvero.
    "manovre_accensione": ("sensor", "_manovre_totali"),
    "manovre_manutenzione": ("sensor", "_manovre_manutenzione"),
    "manutenzione_dovuta": ("binary_sensor", "_manutenzione_dovuta"),
    "motivo_arresto": ("sensor", "_motivo_arresto"),
    "ostacolo": ("binary_sensor", "_ostacolo"),
    "eventi": ("event", "_eventi"),
}

_IDENTIFICATIVO = re.compile(r"nexus_nice_(\d+)")

# Attributi degli eventi che hanno un significato (paragrafo 4 della specifica).
# Tutto il resto, compresi eventuali identificativi, resta fuori dallo storico.
ATTRIBUTI_EVENTO = (
    "tipo",
    "stato",
    "ostruzione",
    "codice_base",
    "causa",
    "codice_avanzato",
    "errore_bluebus",
    "batteria",
    "batteria_dispositivo",
    "causa_reset",
    "manovre",
    "soglia_manovre",
    "corrente_media",
    "motivo",
    "esito",
)
LUNGHEZZA_MASSIMA = 40
GIORNI_STORICO = 30
VOCI_STORICO = 50

# Servizio chiamato -> azione, per le chiamate sulla cover del cancello.
AZIONI_COVER = {
    "open_cover": "apri",
    "close_cover": "chiudi",
    "stop_cover": "stop",
    "set_cover_position": "posizione",
    "toggle": "inverti",
}
# Pulsante premuto -> azione.
AZIONI_PULSANTI = {
    "parziale": "parziale",
    "passo_passo": "passo_passo",
    "luce": "luce",
    "riavvia": "riavvia",
    "registro_leggi": "registro",
}
# Le azioni dopo cui il gateway rifiuta il riavvio dell'interfaccia per 30 s.
AZIONI_MOVIMENTO = frozenset({"apri", "chiudi", "stop", "posizione", "inverti", "parziale", "passo_passo"})
# Le azioni che portano il cancello fuori dall'apertura pedonale.
AZIONI_FINE_PEDONALE = frozenset({"apri", "chiudi", "posizione", "inverti", "passo_passo"})


def unique_id(slot: int, chiave: str) -> str:
    return f"nexus_nice_{slot}{ENTITA[chiave][1]}"


def slot_da_identificativi(identificativi: Iterable[tuple[str, ...]]) -> int | None:
    """Lo slot del cancello (1-5) dal dispositivo MQTT del gateway, se lo e'.

    Non tutti gli identificativi sono coppie: il bridge HomeKit, per esempio, ne
    registra uno di tre elementi. Spacchettarli in due faceva fallire il config
    flow con un errore 500 su qualunque impianto che ne avesse uno.
    """
    for voce in identificativi:
        if not isinstance(voce, (tuple, list)) or len(voce) < 2 or voce[0] != "mqtt":
            continue
        trovato = _IDENTIFICATIVO.fullmatch(str(voce[1]))
        if trovato:
            return int(trovato.group(1))
    return None


def nome_predefinito(nome_dispositivo: str | None) -> str:
    """«Nexus-T Cancello» diventa «Cancello»: il prefisso lo sa gia' chi guarda."""
    nome = (nome_dispositivo or "").strip()
    if nome.lower().startswith("nexus-t "):
        nome = nome[8:].strip()
    return nome or "Cancello"


def cancelli_disponibili(
    dispositivi: Iterable[tuple[Iterable[tuple[str, str]], str | None]],
    gia_configurati: Iterable[int],
) -> list[tuple[int, str]]:
    """(slot, nome) dei cancelli del gateway non ancora configurati, per slot."""
    esclusi = set(gia_configurati)
    trovati: dict[int, str] = {}
    for identificativi, nome in dispositivi:
        slot = slot_da_identificativi(identificativi)
        if slot is None or slot in esclusi or slot in trovati:
            continue
        trovati[slot] = nome or f"Cancello {slot}"
    return sorted(trovati.items())


# -----------------------------------------------------------------------------
# Storico degli eventi
# -----------------------------------------------------------------------------
def _istante(ts: Any) -> datetime | None:
    try:
        istante = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return istante if istante.tzinfo is not None else None


def pulisci_evento(ts: Any, tipo: Any, attributi: dict[str, Any]) -> dict[str, Any] | None:
    """La voce di storico per uno stato dell'entita' eventi, o None se non e' un evento."""
    if _istante(ts) is None or not tipo:
        return None
    campi = {}
    for chiave in ATTRIBUTI_EVENTO:
        valore = attributi.get(chiave)
        if valore is None or valore == "":
            continue
        campi[chiave] = str(valore)[:LUNGHEZZA_MASSIMA]
    return {"ts": str(ts), "tipo": str(tipo)[:LUNGHEZZA_MASSIMA], "attributi": campi}


def potato(storico: Iterable[dict[str, Any]], adesso: datetime) -> list[dict[str, Any]]:
    """Solo gli ultimi 30 giorni, al massimo 50 voci, dalla piu' recente.

    Restituisce sempre oggetti nuovi: la lista finisce negli attributi di un
    sensore, e Home Assistant confronta gli attributi con una copia superficiale
    di quelli precedenti. Una lista modificata sul posto risulterebbe uguale e lo
    stato non verrebbe riscritto.
    """
    limite = adesso - timedelta(days=GIORNI_STORICO)
    tenuti = []
    for voce in storico:
        istante = _istante(voce.get("ts"))
        if istante is None or istante < limite:
            continue
        tenuti.append((istante, voce))
    tenuti.sort(key=lambda coppia: coppia[0], reverse=True)
    return [
        {"ts": voce["ts"], "tipo": voce["tipo"], "attributi": dict(voce.get("attributi") or {})}
        for _, voce in tenuti[:VOCI_STORICO]
    ]


def con_evento(storico: list[dict[str, Any]], evento: dict[str, Any], adesso: datetime) -> list[dict[str, Any]]:
    """Lo storico con un evento in piu', senza doppioni."""
    doppione = any(v.get("ts") == evento["ts"] and v.get("tipo") == evento["tipo"] for v in storico)
    return potato(storico if doppione else [evento, *storico], adesso)


# -----------------------------------------------------------------------------
# Comandi e apertura pedonale
# -----------------------------------------------------------------------------
def _come_lista(valore: Any) -> list[str]:
    if valore is None:
        return []
    if isinstance(valore, str):
        return [valore]
    try:
        return [str(v) for v in valore]
    except TypeError:
        return []


def interpreta_servizio(
    dominio: str | None,
    servizio: str | None,
    dati: dict[str, Any],
    entita: dict[str, str | None],
) -> tuple[str, dict[str, Any]] | None:
    """Se una chiamata di servizio e' un comando per questo cancello: (azione, dettagli)."""
    bersagli = _come_lista(dati.get("entity_id"))
    if not bersagli:
        return None

    if dominio == "cover" and servizio in AZIONI_COVER and entita.get("cancello") in bersagli:
        azione = AZIONI_COVER[servizio]
        dettagli: dict[str, Any] = {}
        if azione == "posizione" and dati.get("position") is not None:
            dettagli["posizione"] = dati.get("position")
        return azione, dettagli

    if dominio == "button" and servizio == "press":
        for chiave, azione in AZIONI_PULSANTI.items():
            if entita.get(chiave) and entita[chiave] in bersagli:
                return azione, {}
    return None


def pedonale_dopo_comando(pedonale: bool, azione: str) -> bool:
    """L'apertura pedonale comincia col comando parziale e finisce con un comando di manovra.

    Stop, luce, registro e riavvio non la cambiano: dopo uno Stop il cancello a
    due ante ha ancora una sola anta aperta.
    """
    if azione == "parziale":
        return True
    if azione in AZIONI_FINE_PEDONALE:
        return False
    return pedonale


def pedonale_dopo_stato(pedonale: bool, stato: str | None) -> bool:
    """A cancello chiuso l'apertura pedonale e' finita, comunque ci si sia arrivati."""
    return False if stato == "closed" else pedonale
