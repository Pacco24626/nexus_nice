"""Il cancello visto dal server: entita', storico degli eventi, ultimo comando.

La card gira nel browser con i permessi di chi e' collegato. Sul tablet a muro,
con un utente di casa, non puo' leggere il registro delle entita' (serve per gli
unique_id) ne' conservare uno storico: si fanno qui e se ne pubblica il risultato
negli attributi di un sensore che chiunque puo' leggere.

Nessun collegamento al modulo Nice: accetta una sola sessione e quella e' del
gateway. Tutto passa dalle entita' che Nexus-T crea in Home Assistant.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SLOT,
    CONF_TIPOLOGIA,
    CONF_VERSO,
    DOMAIN,
    RUOLO_MAPPA,
    SALVATAGGIO_RITARDO,
    STORAGE_VERSION,
    TIPOLOGIA_PREDEFINITA,
    VERSO_PREDEFINITO,
)
from .logica import (
    AZIONI_MOVIMENTO,
    ENTITA,
    con_evento,
    interpreta_servizio,
    pedonale_dopo_comando,
    pedonale_dopo_stato,
    potato,
    pulisci_evento,
    unique_id,
)

_LOGGER = logging.getLogger(__name__)


def chiave_storage(entry_id: str) -> str:
    return f"{DOMAIN}.{entry_id}"


class Cancello:
    """Un cancello del gateway (una config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        cfg = {**entry.data, **entry.options}
        self.slot: int = int(cfg[CONF_SLOT])
        self.tipologia: str = cfg.get(CONF_TIPOLOGIA, TIPOLOGIA_PREDEFINITA)
        self.verso: str = cfg.get(CONF_VERSO, VERSO_PREDEFINITO)

        self.entita: dict[str, str | None] = {}
        self.errori: list[dict[str, Any]] = []
        self.ultimo_comando: dict[str, Any] | None = None
        self.ultimo_movimento: str | None = None
        self.pedonale = False

        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, chiave_storage(entry.entry_id))
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub: list[CALLBACK_TYPE] = []
        self._unsub_stati: CALLBACK_TYPE | None = None

    # -------------------------------------------------------------------------
    # Ciclo di vita
    # -------------------------------------------------------------------------
    async def async_start(self) -> None:
        dati = await self._store.async_load() or {}
        self.errori = potato(dati.get("errori") or [], dt_util.utcnow())
        self.pedonale = bool(dati.get("pedonale", False))
        self.ultimo_comando = dati.get("ultimo_comando")
        self.ultimo_movimento = dati.get("ultimo_movimento")

        self._risolvi()
        # Le entita' nascono via MQTT discovery, anche dopo l'avvio: un gateway
        # aggiornato al sidecar V3 aggiunge luce, registro e diagnostica da solo.
        self._unsub.append(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._su_registro)
        )
        self._unsub.append(self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._su_servizio))

        # L'ultimo evento del modulo potrebbe essere arrivato mentre
        # l'integrazione era spenta: lo si registra, senza doppioni.
        if self._registra_evento(self._stato("eventi")):
            self._salva()

    async def async_stop(self) -> None:
        for annulla in self._unsub:
            annulla()
        self._unsub.clear()
        if self._unsub_stati is not None:
            self._unsub_stati()
            self._unsub_stati = None
        await self._store.async_save(self._dati())

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(update)

        @callback
        def _rimuovi() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return _rimuovi

    @callback
    def notify(self) -> None:
        for update in list(self._listeners):
            update()

    # -------------------------------------------------------------------------
    # Entita' del gateway
    # -------------------------------------------------------------------------
    def _stato(self, chiave: str) -> State | None:
        entity_id = self.entita.get(chiave)
        return self.hass.states.get(entity_id) if entity_id else None

    @callback
    def _su_registro(self, _event: Event) -> None:
        # Arriva per qualunque entita' di Home Assistant: si ricontrollano le
        # nostre (14 letture di un dizionario) e si notifica solo se cambiano.
        if self._risolvi():
            self.notify()

    def _risolvi(self) -> bool:
        """Cerca le entita' per unique_id. True se la mappa e' cambiata."""
        registro = er.async_get(self.hass)
        nuove = {
            chiave: registro.async_get_entity_id(dominio, "mqtt", unique_id(self.slot, chiave))
            for chiave, (dominio, _) in ENTITA.items()
        }
        if nuove == self.entita:
            return False
        self.entita = nuove
        self._sottoscrivi_stati()
        return True

    def _sottoscrivi_stati(self) -> None:
        if self._unsub_stati is not None:
            self._unsub_stati()
            self._unsub_stati = None
        seguite = [e for e in (self.entita.get("eventi"), self.entita.get("cancello")) if e]
        if seguite:
            self._unsub_stati = async_track_state_change_event(self.hass, seguite, self._su_stato)

    @callback
    def _su_stato(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        nuovo: State | None = event.data.get("new_state")
        vecchio: State | None = event.data.get("old_state")
        if nuovo is None:
            return

        if entity_id == self.entita.get("eventi"):
            # Un evento nuovo cambia lo stato (l'istante). Un cambio dei soli
            # attributi, o il ritorno da unavailable allo stesso istante, no.
            if vecchio is not None and vecchio.state == nuovo.state:
                return
            if self._registra_evento(nuovo):
                self._salva()
                self.notify()
            return

        if entity_id == self.entita.get("cancello"):
            pedonale = pedonale_dopo_stato(self.pedonale, nuovo.state)
            if pedonale != self.pedonale:
                self.pedonale = pedonale
                self._salva()
                self.notify()

    def _registra_evento(self, stato: State | None) -> bool:
        if stato is None:
            return False
        evento = pulisci_evento(stato.state, stato.attributes.get("event_type"), dict(stato.attributes))
        if evento is None:
            return False
        nuovo = con_evento(self.errori, evento, dt_util.utcnow())
        if nuovo == self.errori:
            return False
        self.errori = nuovo
        return True

    # -------------------------------------------------------------------------
    # Comandi, da qualunque parte arrivino (card, automazioni, assistenti vocali)
    # -------------------------------------------------------------------------
    @callback
    def _su_servizio(self, event: Event) -> None:
        esito = interpreta_servizio(
            event.data.get("domain"),
            event.data.get("service"),
            event.data.get("service_data") or {},
            self.entita,
        )
        if esito is None:
            return
        azione, dettagli = esito
        adesso = dt_util.utcnow().isoformat()
        self.ultimo_comando = {"azione": azione, "ts": adesso, **dettagli}
        if azione in AZIONI_MOVIMENTO:
            self.ultimo_movimento = adesso
        self.pedonale = pedonale_dopo_comando(self.pedonale, azione)
        self._salva()
        self.notify()

    # -------------------------------------------------------------------------
    # Salvataggio e attributi
    # -------------------------------------------------------------------------
    def _dati(self) -> dict[str, Any]:
        return {
            "errori": self.errori,
            "pedonale": self.pedonale,
            "ultimo_comando": self.ultimo_comando,
            "ultimo_movimento": self.ultimo_movimento,
        }

    def _salva(self) -> None:
        self._store.async_delay_save(self._dati, SALVATAGGIO_RITARDO)

    @property
    def attributi(self) -> dict[str, Any]:
        """Gli attributi del sensore, sempre con oggetti nuovi (niente copie superficiali condivise)."""
        return {
            "ruolo": RUOLO_MAPPA,
            "nome": self.entry.title,
            "slot": self.slot,
            "tipologia": self.tipologia,
            "verso": self.verso,
            "entita": dict(self.entita),
            "errori": [{**voce, "attributi": dict(voce.get("attributi") or {})} for voce in self.errori],
            "ultimo_comando": dict(self.ultimo_comando) if self.ultimo_comando else None,
            "ultimo_movimento": self.ultimo_movimento,
            "pedonale": self.pedonale,
        }
