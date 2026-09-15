"""Costanti dell'integrazione Nexus Nice."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "nexus_nice"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_SLOT = "slot"
CONF_TIPOLOGIA = "tipologia"
CONF_VERSO = "verso"
CONF_NOME = "nome"

TIPOLOGIE = ["scorrevole", "due_ante", "una_anta", "sezionale", "basculante"]
# Il verso serve solo al disegno, e solo dove il cancello e' asimmetrico.
TIPOLOGIE_CON_VERSO = ("scorrevole", "una_anta")
VERSI = ["sinistra", "destra"]
TIPOLOGIA_PREDEFINITA = "scorrevole"
VERSO_PREDEFINITO = "sinistra"

RUOLO_MAPPA = "mappa_cancello"

STORAGE_VERSION = 1
SALVATAGGIO_RITARDO = 5

CARD_URL_BASE = "/nexus_nice"
CARD_FILE = "nexus-nice-card.js"
