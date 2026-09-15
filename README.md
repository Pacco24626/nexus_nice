<img src="icons/logo.png" alt="Nexus Nice" width="360">

# Nexus Nice

Card per Home Assistant del cancello o della porta da garage **Nice** collegati al gateway
**Nexus-T** tramite il modulo Nice BiDi-WiFi: comandi, posizione in tempo reale e
diagnostica in un'unica scheda, con il disegno della tua automazione che si muove mentre la
manovra avanza.

Funziona per cinque tipologie, scelte in configurazione:

| Tipologia | Disegno | Comando parziale |
|---|---|---|
| Cancello scorrevole | l'anta scorre sul binario, verso sinistra o destra | apre un tratto della corsa (pedonale) |
| Cancello a due ante | le ante ruotano dai pilastri | apre **una sola anta**, tutta |
| Cancello a un'anta | l'anta ruota, cerniera a sinistra o a destra | apre l'anta del tutto, come «Apri» |
| Porta sezionale | i pannelli salgono sotto l'architrave | apre un tratto della corsa |
| Porta basculante | il pannello si inclina e sale | apre un tratto della corsa |

## Cosa c'è nella card

- **Stato e posizione**: «Chiuso», «In apertura», «Fermo al 45%», «Aperto · pedonale», con la
  percentuale e la sua fonte (encoder della centrale o stima a tempo).
- **Slider di apertura**: segue la posizione mentre il cancello si muove; trascinalo e rilascialo
  per mandarlo a quella posizione. Una tacca indica dove sta andando.
- **Comandi**: il verde è «Apri» a cancello chiuso, «Chiudi» a cancello aperto, e diventano due
  pulsanti affiancati quando è fermo a metà. Il rosso è **Stop**, e pulsa durante la manovra.
  Sotto: apertura pedonale (o parziale) e **luce di cortesia**, che funziona solo se l'uscita della
  centrale è cablata.
- **Riquadri**: ostacolo, motivo dell'ultimo arresto, manovre dall'ultima accensione della
  centrale, manovre dall'ultima manutenzione con la soglia.
- **Diagnostica**: gli errori e gli avvisi mandati dal modulo negli ultimi 30 giorni, le ultime
  voci del registro eventi del modulo (con il pulsante per rileggerlo), tipologia, fonte della
  posizione, ultimo comando e riavvio dell'interfaccia WiFi con conferma.

Il passo-passo non compare fra i comandi: l'entità resta disponibile in Home Assistant.

## Requisiti

- Home Assistant 2024.12 o superiore, con l'integrazione MQTT.
- Gateway **Nexus-T** con un'automazione Nice configurata e la discovery MQTT attiva.
- Per luce di cortesia, registro eventi, riquadri diagnostici ed eventi del modulo serve il
  **sidecar Nice V3** (Nexus-T V0.8.38 o successivi). Con un gateway più vecchio la card funziona
  con quello che c'è: comandi, posizione e apertura parziale.

## Installazione

1. HACS → menu ⋮ → **Repository personalizzate**
2. URL `https://github.com/Pacco24626/nexus_nice`, categoria **Integration**
3. Installa, poi **riavvia Home Assistant**
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Nexus Nice**

La card viene servita e registrata dall'integrazione: non c'è nessuna risorsa da aggiungere a mano.

## Configurazione

L'integrazione elenca i cancelli che il gateway ha pubblicato in Home Assistant (fino a cinque)
e non ancora configurati. Per ognuno:

| Campo | Note |
|---|---|
| Cancello | lo slot del gateway (1-5) |
| Nome | il titolo della card; proposto dal nome del dispositivo |
| Tipologia | scorrevole · due ante · un'anta · sezionale · basculante |
| Verso | solo per scorrevole e un'anta: da che parte apre, serve al disegno |

Tipologia e verso si cambiano dopo da **Configura**; il nome rinominando la voce.

Ogni cancello crea un dispositivo con il suo nome e un sensore diagnostico **Mappa cancello**: è
quello da indicare nella card.

## La card

```yaml
type: custom:nexus-nice-card
entity: sensor.cancello_mappa_cancello
title: Cancello   # facoltativo
```

Si aggiunge anche dall'editor delle plance cercando **Nexus Nice**.

## Come funziona, e perché così

**Nessun collegamento al modulo Nice.** Il modulo BiDi-WiFi accetta una sola sessione e quella è
del gateway: un secondo client lo scollegherebbe e il cancello smetterebbe di rispondere anche da
KNX o Vimar. L'integrazione legge e comanda solo attraverso le entità che Nexus-T crea in Home
Assistant, trovate per `unique_id` e non per `entity_id` (quelli cambiano rinominandoli).

**Lo storico degli errori lo tiene l'integrazione.** Il modulo non conserva gli errori: li manda
quando accadono. L'integrazione ascolta l'entità degli eventi e salva gli ultimi 30 giorni (al
massimo 50 voci), anche attraverso i riavvii. I codici arrivano grezzi dalla centrale e vengono
mostrati come codici: il loro significato non è pubblicato e non viene inventato.

**Manovre dall'accensione, non totali.** Il contatore che il gateway chiama «manovre totali» riparte
a ogni mancanza di corrente della centrale: la card lo presenta per quello che è.

**Apertura pedonale del due ante.** Il gateway manda una sola posizione per tutto il cancello.
L'integrazione sa che è un'apertura pedonale quando il comando passa da Home Assistant (card,
automazioni, assistenti vocali) e allora disegna una sola anta aperta. Se la pedonale parte dal
telecomando, la card non può saperlo e disegna le due ante insieme.

**Riavvio dell'interfaccia.** Sempre dietro conferma, mai ripetuto in automatico. Il pulsante resta
disattivato con il cancello in movimento e nei 30 secondi dopo un comando di manovra, perché in quei
casi il gateway lo rifiuterebbe.

## Prove a tavolino

```bash
python tests/test_logica.py
python tests/test_cancello.py
python tests/test_config_flow.py
```

La card si collauda in un browser vero aprendo `tests/card/prova_card.html` (o con Edge/Chrome in
modalità headless e `--dump-dom`); con `?vista=1` e `?vista=2` mostra i casi principali affiancati.

## Licenza

Apache 2.0
