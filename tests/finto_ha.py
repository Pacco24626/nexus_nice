"""Un Home Assistant finto, quanto basta per provare il controller del cancello.

Si iniettano moduli con i soli nomi che l'integrazione importa: registro delle
entita', bus degli eventi, stati con i loro ascoltatori e uno storage in memoria
che sopravvive al «riavvio» (un nuovo controller sulla stessa voce).
"""

from __future__ import annotations

import os
import sys
import types
from datetime import datetime, timezone

ADESSO = [datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)]


def _modulo(nome: str, **attributi):
    m = types.ModuleType(nome)
    for chiave, valore in attributi.items():
        setattr(m, chiave, valore)
    sys.modules[nome] = m
    return m


def callback(funzione):
    return funzione


class State:
    def __init__(self, entity_id: str, state: str, attributes: dict | None = None) -> None:
        self.entity_id = entity_id
        self.state = state
        self.attributes = dict(attributes or {})


class Event:
    def __init__(self, event_type: str, data: dict) -> None:
        self.event_type = event_type
        self.data = data


class _Platform(str):
    SENSOR = "sensor"


class _EntityCategory(str):
    DIAGNOSTIC = "diagnostic"


EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"

_modulo("homeassistant")
_modulo("homeassistant.config_entries", ConfigEntry=object)
_modulo(
    "homeassistant.const",
    EVENT_CALL_SERVICE="call_service",
    EVENT_HOMEASSISTANT_STARTED="homeassistant_started",
    Platform=_Platform,
    MATCH_ALL="*",
    EntityCategory=_EntityCategory,
)
_modulo("homeassistant.core", CALLBACK_TYPE=object, Event=Event, HomeAssistant=object, State=State, callback=callback)
_modulo("homeassistant.helpers")


class Registro:
    def __init__(self) -> None:
        self.voci: dict[tuple[str, str, str], str] = {}

    def async_get_entity_id(self, dominio: str, piattaforma: str, unique_id: str):
        return self.voci.get((dominio, piattaforma, unique_id))


_REGISTRO_CORRENTE: list[Registro] = [Registro()]
_modulo(
    "homeassistant.helpers.entity_registry",
    EVENT_ENTITY_REGISTRY_UPDATED=EVENT_ENTITY_REGISTRY_UPDATED,
    async_get=lambda hass: hass.registro,
)


def async_track_state_change_event(hass, entity_ids, azione):
    ids = set(entity_ids)
    voce = (ids, azione)
    hass.stati.ascoltatori.append(voce)

    def annulla():
        if voce in hass.stati.ascoltatori:
            hass.stati.ascoltatori.remove(voce)

    return annulla


_modulo("homeassistant.helpers.event", async_track_state_change_event=async_track_state_change_event)

MEMORIA: dict[str, dict] = {}


class Store:
    def __init__(self, hass, versione, chiave) -> None:
        self.chiave = chiave

    async def async_load(self):
        import copy

        return copy.deepcopy(MEMORIA.get(self.chiave))

    def async_delay_save(self, funzione, ritardo):
        import copy

        MEMORIA[self.chiave] = copy.deepcopy(funzione())

    async def async_save(self, dati):
        import copy

        MEMORIA[self.chiave] = copy.deepcopy(dati)

    async def async_remove(self):
        MEMORIA.pop(self.chiave, None)


_modulo("homeassistant.helpers.storage", Store=Store)
# Solo perche' il pacchetto li importa nel suo __init__ (card e schema).
_modulo("homeassistant.components")
_modulo("homeassistant.components.frontend", add_extra_js_url=lambda hass, url: None)
_modulo("homeassistant.components.http", StaticPathConfig=lambda *a, **k: None)
_modulo("homeassistant.helpers.config_validation", config_entry_only_config_schema=lambda dominio: None)
_modulo("homeassistant.loader", async_get_integration=None)
_modulo("homeassistant.util")
_modulo("homeassistant.util.dt", utcnow=lambda: ADESSO[0])
sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]


class Stati:
    def __init__(self) -> None:
        self._stati: dict[str, State] = {}
        self.ascoltatori: list = []

    def get(self, entity_id):
        return self._stati.get(entity_id)

    def imposta(self, entity_id: str, stato: str, attributi: dict | None = None) -> None:
        vecchio = self._stati.get(entity_id)
        nuovo = State(entity_id, stato, attributi)
        self._stati[entity_id] = nuovo
        evento = Event("state_changed", {"entity_id": entity_id, "old_state": vecchio, "new_state": nuovo})
        for ids, azione in list(self.ascoltatori):
            if entity_id in ids:
                azione(evento)


class Bus:
    def __init__(self) -> None:
        self.ascoltatori: list[tuple[str, object]] = []

    def async_listen(self, tipo, azione):
        voce = (tipo, azione)
        self.ascoltatori.append(voce)

        def annulla():
            if voce in self.ascoltatori:
                self.ascoltatori.remove(voce)

        return annulla

    def spara(self, tipo: str, dati: dict) -> None:
        for t, azione in list(self.ascoltatori):
            if t == tipo:
                azione(Event(tipo, dati))


class Hass:
    def __init__(self) -> None:
        self.registro = Registro()
        self.stati = Stati()
        self.states = self.stati
        self.bus = Bus()
        self.data: dict = {}


class Entry:
    def __init__(self, data: dict, options: dict | None = None, title: str = "Cancello", entry_id: str = "voce1") -> None:
        self.data = data
        self.options = options or {}
        self.title = title
        self.entry_id = entry_id


sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components"))
)
