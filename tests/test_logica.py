"""Prove a tavolino della logica del cancello, senza Home Assistant.

    python tests/test_logica.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "nexus_nice"))
)

from logica import (  # noqa: E402
    AZIONI_MOVIMENTO,
    ENTITA,
    VOCI_STORICO,
    cancelli_disponibili,
    con_evento,
    interpreta_servizio,
    nome_predefinito,
    pedonale_dopo_comando,
    pedonale_dopo_stato,
    potato,
    pulisci_evento,
    slot_da_identificativi,
    unique_id,
)

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


ADESSO = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)


def ts(**indietro) -> str:
    return (ADESSO - timedelta(**indietro)).isoformat()


print("\n1. Entita' e dispositivi del gateway")
v(unique_id(1, "cancello") == "nexus_nice_1", "cover: nexus_nice_1")
v(unique_id(3, "manovre_accensione") == "nexus_nice_3_manovre_totali", "le manovre dall'accensione sono l'id _manovre_totali")
v(unique_id(1, "eventi") == "nexus_nice_1_eventi", "eventi: nexus_nice_1_eventi")
v(len(ENTITA) == 14 and len({s for _, s in ENTITA.values()}) == 14, "14 entita', suffissi tutti diversi")
v(slot_da_identificativi([("mqtt", "nexus_nice_1")]) == 1, "slot dal dispositivo MQTT")
v(slot_da_identificativi([("mqtt", "nexus_nice_12")]) == 12, "slot a due cifre")
v(slot_da_identificativi([("mqtt", "tecnoalarm_gateway")]) is None, "altri dispositivi MQTT esclusi")
v(slot_da_identificativi([("zha", "nexus_nice_1")]) is None, "solo il dominio mqtt")
v(slot_da_identificativi([("mqtt", "nexus_nice_1_extra")]) is None, "identificativo intero, non un prefisso")
v(nome_predefinito("Nexus-T Cancello") == "Cancello", "«Nexus-T Cancello» -> «Cancello»")
v(nome_predefinito("Garage box") == "Garage box", "nome senza prefisso invariato")
v(nome_predefinito(None) == "Cancello", "nome mancante -> «Cancello»")
disponibili = cancelli_disponibili(
    [
        ([("mqtt", "nexus_nice_2")], "Nexus-T Garage"),
        ([("mqtt", "nexus_nice_1")], "Nexus-T Cancello"),
        ([("mqtt", "tecnoalarm_gateway")], "Centrale"),
        ([("mqtt", "nexus_nice_3")], "Nexus-T Box"),
    ],
    gia_configurati=[3],
)
v(disponibili == [(1, "Nexus-T Cancello"), (2, "Nexus-T Garage")], f"cancelli ordinati per slot, esclusi i configurati ({disponibili})")

print("\n2. Voci di storico dagli eventi")
e = pulisci_evento(ts(minutes=5), "ostruzione", {"codice_base": 12, "stato": "stopped", "mac": "F4:65:0B", "friendly_name": "x", "event_types": ["a"]})
v(e is not None and e["tipo"] == "ostruzione", "evento valido riconosciuto")
v(e["attributi"] == {"codice_base": "12", "stato": "stopped"}, f"solo gli attributi della specifica, come testo ({e['attributi']})")
v(pulisci_evento("unknown", "ostruzione", {}) is None, "stato unknown: nessun evento")
v(pulisci_evento("unavailable", "ostruzione", {}) is None, "stato unavailable: nessun evento")
v(pulisci_evento(ts(minutes=1), None, {}) is None, "senza event_type: nessun evento")
v(pulisci_evento("2026-09-16T10:00:00", "reset", {}) is None, "orario senza fuso: scartato, non si puo' confrontare")
lungo = pulisci_evento(ts(minutes=1), "altro", {"causa": "x" * 90})
v(len(lungo["attributi"]["causa"]) == 40, "testi tagliati a 40 caratteri")

print("\n3. Storico: doppioni, 30 giorni, 50 voci, oggetti nuovi")
s0: list = []
e1 = pulisci_evento(ts(hours=2), "ostruzione", {"codice_base": 1})
s1 = con_evento(s0, e1, ADESSO)
v(len(s1) == 1 and s1 is not s0, "primo evento: lista nuova")
s2 = con_evento(s1, dict(e1), ADESSO)
v(len(s2) == 1, "stesso istante e stesso tipo: nessun doppione")
e2 = pulisci_evento(ts(hours=1), "errore_bluebus", {"errore_bluebus": 3})
s3 = con_evento(s2, e2, ADESSO)
v([x["tipo"] for x in s3] == ["errore_bluebus", "ostruzione"], "dal piu' recente")
v(s3[1] is not s1[0] and s3[1]["attributi"] is not s1[0]["attributi"], "voci e attributi copiati, mai condivisi")
vecchio = pulisci_evento(ts(days=31), "reset", {})
v(len(con_evento(s3, vecchio, ADESSO)) == 2, "evento di 31 giorni fa scartato")
molti = []
for i in range(70):
    molti = con_evento(molti, pulisci_evento(ts(minutes=i), "diagnostica", {"tipo": str(i)}), ADESSO)
v(len(molti) == VOCI_STORICO and molti[0]["attributi"]["tipo"] == "0", "al massimo 50 voci, tenute le piu' recenti")
v(potato([{"ts": "rotto", "tipo": "x"}], ADESSO) == [], "voce con orario illeggibile scartata")

print("\n4. Comandi riconosciuti")
entita = {"cancello": "cover.cancello", "parziale": "button.pedonale", "luce": "button.luce", "passo_passo": "button.sbs", "riavvia": "button.riavvia", "registro_leggi": "button.leggi"}
v(interpreta_servizio("cover", "open_cover", {"entity_id": "cover.cancello"}, entita) == ("apri", {}), "Apri")
v(interpreta_servizio("cover", "close_cover", {"entity_id": ["cover.altro", "cover.cancello"]}, entita) == ("chiudi", {}), "Chiudi con piu' bersagli")
v(interpreta_servizio("cover", "set_cover_position", {"entity_id": "cover.cancello", "position": 40}, entita) == ("posizione", {"posizione": 40}), "Posizione col valore")
v(interpreta_servizio("button", "press", {"entity_id": "button.pedonale"}, entita) == ("parziale", {}), "Pedonale")
v(interpreta_servizio("button", "press", {"entity_id": "button.luce"}, entita) == ("luce", {}), "Luce")
v(interpreta_servizio("cover", "open_cover", {"entity_id": "cover.garage"}, entita) is None, "altra cover: ignorata")
v(interpreta_servizio("light", "turn_on", {"entity_id": "cover.cancello"}, entita) is None, "altro dominio: ignorato")
v(interpreta_servizio("cover", "open_cover", {}, entita) is None, "senza entity_id: ignorato")
v(interpreta_servizio("button", "press", {"entity_id": "button.luce"}, {"cancello": "cover.c", "luce": None}) is None, "pulsante assente (sidecar vecchio): ignorato")
v("luce" not in AZIONI_MOVIMENTO and "registro" not in AZIONI_MOVIMENTO and "parziale" in AZIONI_MOVIMENTO, "luce e registro non bloccano il riavvio, il pedonale si'")

print("\n5. Apertura pedonale")
p = pedonale_dopo_comando(False, "parziale")
v(p is True, "il comando pedonale la comincia")
v(pedonale_dopo_comando(p, "stop") is True, "dopo Stop resta pedonale (una sola anta aperta)")
v(pedonale_dopo_comando(p, "luce") is True, "la luce non la cambia")
v(pedonale_dopo_comando(p, "apri") is False, "Apri la chiude: si aprono entrambe le ante")
v(pedonale_dopo_comando(p, "posizione") is False, "una posizione dallo slider la chiude")
v(pedonale_dopo_comando(p, "passo_passo") is False, "il passo-passo la chiude (non si sa cosa fara')")
v(pedonale_dopo_stato(True, "closed") is False, "cancello chiuso: finita")
v(pedonale_dopo_stato(True, "opening") is True and pedonale_dopo_stato(True, "open") is True, "in apertura o aperto: continua")

totale = passate + len(fallite)
print(f"\nLOGICA: {passate}/{totale} superate")
sys.exit(1 if fallite else 0)
