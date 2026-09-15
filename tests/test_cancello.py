"""Prove a tavolino del controller: entita', eventi, comandi, riavvio.

    python tests/test_cancello.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import finto_ha  # noqa: E402
from finto_ha import ADESSO, MEMORIA, Entry, Hass  # noqa: E402

from nexus_nice.cancello import Cancello  # noqa: E402
from nexus_nice.logica import ENTITA, unique_id  # noqa: E402

passate = 0
fallite: list[str] = []


def v(condizione: bool, descrizione: str) -> None:
    global passate
    if condizione:
        passate += 1
        print(f"  ok  {descrizione}")
    else:
        fallite.append(descrizione)
        print(f"  NO  {descrizione}")


NOMI = {
    "cancello": "cover.nexus_t_cancello_cancello",
    "passo_passo": "button.nexus_t_cancello_cancello_passo_passo",
    "parziale": "button.nexus_t_cancello_cancello_apertura_parziale",
    "luce": "button.giardino_nexus_t_cancello_cancello_luce_di_cortesia",
    "riavvia": "button.giardino_nexus_t_cancello_cancello_riavvia_interfaccia",
    "registro_leggi": "button.giardino_nexus_t_cancello_cancello_leggi_registro_eventi",
    "registro": "sensor.giardino_nexus_t_cancello_cancello_registro_eventi",
    "sorgente_posizione": "sensor.giardino_nexus_t_cancello_cancello_sorgente_posizione",
    "manovre_accensione": "sensor.giardino_nexus_t_cancello_cancello_manovre_totali",
    "manovre_manutenzione": "sensor.giardino_nexus_t_cancello_cancello_manovre_manutenzione",
    "manutenzione_dovuta": "binary_sensor.giardino_nexus_t_cancello_cancello_manutenzione_dovuta",
    "motivo_arresto": "sensor.giardino_nexus_t_cancello_cancello_motivo_arresto",
    "ostacolo": "binary_sensor.giardino_nexus_t_cancello_cancello_ostacolo",
    "eventi": "event.giardino_nexus_t_cancello_cancello_eventi",
}
SIDECAR_VECCHIO = ("cancello", "passo_passo", "parziale")


def registra(hass: Hass, chiavi, slot: int = 1) -> None:
    for chiave in chiavi:
        dominio = ENTITA[chiave][0]
        hass.registro.voci[(dominio, "mqtt", unique_id(slot, chiave))] = NOMI[chiave]


def ts(minuti: int = 0, giorni: int = 0) -> str:
    return (ADESSO[0] - timedelta(minutes=minuti, days=giorni)).isoformat()


async def nuovo(hass: Hass, **cfg) -> tuple[Cancello, list]:
    notifiche: list = []
    entry = Entry({"slot": 1, "tipologia": "due_ante", **cfg})
    c = Cancello(hass, entry)
    await c.async_start()
    c.async_add_listener(lambda: notifiche.append(1))
    return c, notifiche


async def main() -> None:
    print("\n1. Entita' trovate per unique_id")
    MEMORIA.clear()
    hass = Hass()
    registra(hass, ENTITA)
    c, notifiche = await nuovo(hass)
    v(c.entita == NOMI, "tutte e 14 le entita' del sidecar V3, con gli entity_id rinominati")
    a = c.attributi
    v(a["ruolo"] == "mappa_cancello" and a["tipologia"] == "due_ante" and a["verso"] == "sinistra" and a["slot"] == 1, "attributi di base (verso predefinito: sinistra)")
    v(a["entita"] is not c.entita, "la mappa negli attributi e' una copia")

    hass2 = Hass()
    registra(hass2, SIDECAR_VECCHIO)
    c2, _ = await nuovo(hass2)
    v(c2.entita["cancello"] and c2.entita["luce"] is None and c2.entita["eventi"] is None, "sidecar vecchio: solo cover, passo-passo, parziale; il resto None")
    registra(hass2, ("luce", "eventi"))
    notifiche2: list = []
    c2.async_add_listener(lambda: notifiche2.append(1))
    hass2.bus.spara("entity_registry_updated", {"action": "create"})
    v(c2.entita["luce"] == NOMI["luce"] and len(notifiche2) == 1, "entita' comparse dopo (aggiornamento del gateway): trovate e notificate")
    hass2.bus.spara("entity_registry_updated", {"action": "update"})
    v(len(notifiche2) == 1, "evento del registro senza cambi per noi: nessuna notifica")

    print("\n2. Eventi del modulo nello storico")
    eventi = NOMI["eventi"]
    hass.stati.imposta(eventi, ts(minuti=3), {"event_type": "ostruzione", "codice_base": 12, "event_types": ["ostruzione"], "friendly_name": "Eventi"})
    v(len(c.errori) == 1 and c.errori[0]["attributi"] == {"codice_base": "12"}, "evento registrato con i soli attributi utili")
    v(len(notifiche) == 1, "sensore notificato")
    fotografia = dict(c.attributi)  # come fa Home Assistant: copia superficiale
    hass.stati.imposta(eventi, ts(minuti=1), {"event_type": "errore_bluebus", "errore_bluebus": 3})
    v(len(c.errori) == 2 and c.errori[0]["tipo"] == "errore_bluebus", "secondo evento in testa")
    v(c.attributi != fotografia, "attributi diversi dalla fotografia precedente: Home Assistant riscrive lo stato")
    hass.stati.imposta(eventi, ts(minuti=1), {"event_type": "errore_bluebus", "errore_bluebus": 3, "friendly_name": "nuovo nome"})
    v(len(c.errori) == 2 and len(notifiche) == 2, "cambio dei soli attributi: nessun evento in piu'")
    hass.stati.imposta(eventi, "unavailable", {})
    hass.stati.imposta(eventi, ts(minuti=1), {"event_type": "errore_bluebus", "errore_bluebus": 3})
    v(len(c.errori) == 2, "modulo scollegato e ricollegato allo stesso evento: nessun doppione")
    v(MEMORIA["nexus_nice.voce1"]["errori"][0]["tipo"] == "errore_bluebus", "storico salvato")

    print("\n3. Comandi da qualunque fonte")
    cover, pedonale = NOMI["cancello"], NOMI["parziale"]
    hass.stati.imposta(cover, "closed", {"current_position": 0})
    hass.bus.spara("call_service", {"domain": "button", "service": "press", "service_data": {"entity_id": [pedonale]}})
    v(c.pedonale and c.ultimo_comando["azione"] == "parziale" and c.ultimo_movimento, "pedonale premuto: apertura pedonale, movimento registrato")
    hass.stati.imposta(cover, "opening", {"current_position": 20})
    hass.stati.imposta(cover, "open", {"current_position": 50})
    v(c.pedonale, "in apertura e aperto: resta pedonale")
    hass.bus.spara("call_service", {"domain": "cover", "service": "stop_cover", "service_data": {"entity_id": cover}})
    v(c.pedonale and c.ultimo_comando["azione"] == "stop", "Stop: resta pedonale")
    movimento = c.ultimo_movimento
    ADESSO[0] += timedelta(seconds=10)
    hass.bus.spara("call_service", {"domain": "button", "service": "press", "service_data": {"entity_id": NOMI["luce"]}})
    v(c.ultimo_comando["azione"] == "luce" and c.ultimo_movimento == movimento and c.pedonale, "Luce: ultimo comando si', movimento no, pedonale invariato")
    hass.bus.spara("call_service", {"domain": "cover", "service": "open_cover", "service_data": {"entity_id": cover}})
    v(not c.pedonale and c.ultimo_comando["azione"] == "apri" and c.ultimo_movimento != movimento, "Apri: fine del pedonale, nuovo movimento")
    hass.bus.spara("call_service", {"domain": "button", "service": "press", "service_data": {"entity_id": pedonale}})
    hass.stati.imposta(cover, "closing", {"current_position": 30})
    hass.stati.imposta(cover, "closed", {"current_position": 0})
    v(not c.pedonale, "cancello chiuso: fine del pedonale")
    prima = dict(c.ultimo_comando)
    hass.bus.spara("call_service", {"domain": "cover", "service": "open_cover", "service_data": {"entity_id": "cover.garage_vicino"}})
    hass.bus.spara("call_service", {"domain": "light", "service": "turn_on", "service_data": {"entity_id": "light.portico"}})
    v(c.ultimo_comando == prima, "comandi ad altre entita': ignorati")
    hass.bus.spara("call_service", {"domain": "cover", "service": "set_cover_position", "service_data": {"entity_id": cover, "position": 60}})
    v(c.ultimo_comando["azione"] == "posizione" and c.ultimo_comando["posizione"] == 60, "posizione dallo slider col valore")

    print("\n4. Riavvio di Home Assistant")
    hass.bus.spara("call_service", {"domain": "button", "service": "press", "service_data": {"entity_id": pedonale}})
    await c.async_stop()
    notifiche_prima = len(notifiche)
    hass.stati.imposta(eventi, ts(), {"event_type": "reset", "causa_reset": "7"})
    hass.bus.spara("call_service", {"domain": "cover", "service": "open_cover", "service_data": {"entity_id": cover}})
    v(len(notifiche) == notifiche_prima and len(c.errori) == 2, "fermato: nessun ascoltatore resta attivo")
    c3, _ = await nuovo(hass)
    v([e["tipo"] for e in c3.errori][:2] == ["reset", "errore_bluebus"] and len(c3.errori) == 3, "al riavvio: storico ripreso e l'evento arrivato a integrazione ferma registrato")
    v(c3.pedonale and c3.ultimo_comando["azione"] == "parziale", "al riavvio: pedonale e ultimo comando ripresi")
    await c3.async_stop()
    c4, _ = await nuovo(hass)
    v(len(c4.errori) == 3, "secondo riavvio: nessun doppione dell'ultimo evento")
    await c4.async_stop()

    print("\n5. Storico vecchio")
    ADESSO[0] += timedelta(days=31)
    c5, _ = await nuovo(hass)
    v(c5.errori == [], "dopo 31 giorni lo storico ripreso e' vuoto")
    await c5.async_stop()

    print("\n6. Tipologia e verso dalle opzioni")
    entry = Entry({"slot": 1, "tipologia": "scorrevole", "verso": "sinistra"}, options={"tipologia": "una_anta", "verso": "destra"})
    c6 = Cancello(Hass(), entry)
    v(c6.tipologia == "una_anta" and c6.verso == "destra", "le opzioni prevalgono sui dati iniziali")


asyncio.run(main())
totale = passate + len(fallite)
print(f"\nCONTROLLER: {passate}/{totale} superate")
sys.exit(1 if fallite else 0)
