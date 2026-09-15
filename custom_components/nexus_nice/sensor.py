"""Sensore «Mappa cancello»: cio' che serve alla card, leggibile da qualunque utente."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cancello import Cancello
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    cancello: Cancello = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MappaCancelloSensor(cancello)])


class MappaCancelloSensor(SensorEntity):
    """Stato: quanti eventi del modulo negli ultimi 30 giorni. Attributi: la mappa.

    Diagnostico, cosi' non finisce nelle plance automatiche. Gli attributi non
    vanno nel database: la mappa cambia a ogni comando e lo storico degli eventi
    e' gia' salvato dall'integrazione.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "mappa"
    _attr_icon = "mdi:gate"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, cancello: Cancello) -> None:
        self._cancello = cancello
        self._attr_unique_id = f"{cancello.entry.entry_id}_mappa"
        # Un dispositivo suo. Agganciarsi a quello del gateway con l'identificativo
        # ("mqtt", "nexus_nice_N") non funziona piu': da Home Assistant 2026 la
        # ricerca per identificativi e' limitata alla stessa integrazione, e ne
        # nascerebbe un secondo dispositivo senza nome.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cancello.entry.entry_id)},
            name=cancello.entry.title,
            manufacturer="Automatic Systems",
            model="Card Nexus Nice",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._cancello.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> int:
        return len(self._cancello.errori)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._cancello.attributi
