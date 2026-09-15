/**
 * Nexus Nice — card del cancello Nice collegato a Nexus-T.
 *
 * Si configura con il solo sensore «Mappa cancello» dell'integrazione: da li'
 * prende le entita' del gateway, la tipologia, il verso, lo storico degli eventi
 * e l'ultimo comando. I comandi passano dai servizi di Home Assistant.
 */

const VERSIONE_CARD = "1.0.1";

const TIPI = {
  scorrevole: { nome: "Cancello scorrevole", femminile: false, parziale: "Apertura pedonale" },
  due_ante: { nome: "Cancello a due ante", femminile: false, parziale: "Apertura pedonale" },
  una_anta: { nome: "Cancello a un'anta", femminile: false, parziale: "Apertura pedonale" },
  sezionale: { nome: "Porta sezionale", femminile: true, parziale: "Apertura parziale" },
  basculante: { nome: "Porta basculante", femminile: true, parziale: "Apertura parziale" },
};
const VERSI = {
  scorrevole: { sinistra: "scorre verso sinistra", destra: "scorre verso destra" },
  una_anta: { sinistra: "cerniera a sinistra", destra: "cerniera a destra" },
};

const ETICHETTE_EVENTI = {
  ostruzione: "Ostruzione",
  errore_bluebus: "Errore BlueBUS",
  reset: "Riavvio della centrale",
  batteria: "Batteria di un accessorio",
  manutenzione: "Manutenzione",
  corrente_motore: "Corrente del motore",
  diagnostica: "Diagnostica",
  posizione_rifiutata: "Posizione rifiutata",
  posizione_interrotta: "Posizione interrotta",
  riavvio_rifiutato: "Riavvio rifiutato",
  riavvio_interfaccia: "Riavvio dell'interfaccia",
  altro: "Altro evento",
};
const EVENTI_ERRORE = new Set(["ostruzione", "errore_bluebus", "reset", "batteria", "posizione_interrotta"]);
const MOTIVI = {
  posizione_sconosciuta: "posizione sconosciuta",
  tempo_di_manovra_non_appreso: "tempo di manovra non appreso: serve prima una corsa completa",
  encoder_perso: "encoder perso",
  movimento_non_visto: "movimento non rilevato",
  sessione_caduta: "collegamento col modulo caduto",
  cancello_in_movimento: "il cancello si sta muovendo",
};
const AZIONI = {
  apri: "Apri",
  chiudi: "Chiudi",
  stop: "Stop",
  posizione: "Posizione",
  inverti: "Inverti",
  parziale: "Apertura pedonale",
  passo_passo: "Passo-passo",
  luce: "Luce di cortesia",
  riavvia: "Riavvio interfaccia",
  registro: "Lettura registro",
};
const ATTESA_RIAVVIO_MS = 30000;
const GIORNI_STORICO = 30;

const STILE = `
  :host { display: block; }
  ha-card { display: block; overflow: hidden; }
  * { box-sizing: border-box; }
  .corpo { --nn-verde: #2E9E6B; --nn-verde-scuro: #23805A; --nn-rosso: #DE4A51; --nn-rosso-scuro: #C93C43; --nn-ambra: #E39B32;
    --nn-testo: var(--primary-text-color, #1F2933); --nn-grigio: var(--secondary-text-color, #56616F); --nn-grigio-chiaro: #8C98A5;
    --nn-riquadro: var(--card-background-color, #fff); --nn-bordo: var(--divider-color, #E1E6EC);
    background: color-mix(in srgb, var(--nn-testo) 3%, transparent); color: var(--nn-testo); padding-bottom: 4px; }
  .testata { display: flex; align-items: center; gap: 10px; padding: 14px 16px 6px; }
  .testata h3 { margin: 0; font-size: 17px; font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .collegamento { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--nn-grigio); white-space: nowrap; }
  .collegamento i { width: 8px; height: 8px; border-radius: 50%; background: var(--nn-verde); display: inline-block; }
  .collegamento.giu i { background: var(--nn-rosso); }
  .banner { margin: 8px 16px 0; padding: 8px 12px; border-radius: 10px; background: #FBE7E8; color: var(--nn-rosso-scuro); font-size: 13px; font-weight: 600; }
  .scena { position: relative; margin: 4px 16px 0; background: var(--nn-riquadro); border: 1px solid var(--nn-bordo); border-radius: 14px; padding: 10px 10px 4px; }
  .stato-pill { position: absolute; top: 10px; left: 12px; padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; background: color-mix(in srgb, var(--nn-grigio) 12%, transparent); color: var(--nn-grigio); }
  .stato-pill.aperto { background: #E6F4EC; color: var(--nn-verde-scuro); }
  .stato-pill.moto { background: #FDF1DE; color: #A8660F; }
  .stato-pill.allarme { background: #FBE7E8; color: var(--nn-rosso-scuro); }
  .percentuale { position: absolute; top: 6px; right: 14px; text-align: right; }
  .percentuale b { font-size: 26px; font-weight: 700; letter-spacing: -.02em; }
  .percentuale small { display: block; font-size: 11px; color: var(--nn-grigio-chiaro); margin-top: -2px; }
  svg.disegno { display: block; width: 100%; height: auto; margin-top: 26px; }
  svg.disegno .scorre { transition: transform .8s linear; }
  svg.disegno.in-moto .lampeggiante { animation: lampeggia .8s steps(2, jump-none) infinite; }
  @keyframes lampeggia { 0% { fill: #F2A33A; } 100% { fill: #E6EAEF; } }
  .slider-blocco { padding: 10px 18px 2px; }
  .slider-testa { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--nn-grigio); text-transform: uppercase; }
  .slider-testa .nota { font-weight: 500; letter-spacing: 0; text-transform: none; color: var(--nn-grigio-chiaro); }
  .binario { position: relative; height: 34px; margin-top: 4px; }
  .binario .pista { position: absolute; left: 0; right: 0; top: 14px; height: 6px; border-radius: 3px; background: color-mix(in srgb, var(--nn-grigio) 20%, transparent); }
  .binario .riempito { position: absolute; left: 0; top: 14px; height: 6px; border-radius: 3px; background: var(--nn-verde); transition: width .3s linear; }
  .binario .obiettivo { position: absolute; top: 6px; width: 2px; height: 22px; background: var(--nn-ambra); border-radius: 1px; transform: translateX(-1px); }
  .binario input { position: absolute; inset: 0; width: 100%; margin: 0; background: transparent; -webkit-appearance: none; appearance: none; cursor: pointer; }
  .binario input::-webkit-slider-runnable-track { height: 34px; background: transparent; }
  .binario input::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; margin-top: 6px; border-radius: 50%; background: #fff; border: 3px solid var(--nn-verde); box-shadow: 0 1px 4px rgba(0,0,0,.2); }
  .binario input::-moz-range-thumb { width: 18px; height: 18px; border-radius: 50%; background: #fff; border: 3px solid var(--nn-verde); }
  .binario input:disabled { cursor: not-allowed; }
  .binario input:disabled::-webkit-slider-thumb { border-color: #B9C3CE; }
  .scala { display: flex; justify-content: space-between; font-size: 11px; color: var(--nn-grigio-chiaro); margin-top: -2px; }
  .comandi { display: grid; grid-template-columns: 2fr 1fr; gap: 10px; padding: 12px 16px 4px; }
  .verdi { display: flex; gap: 8px; }
  .verdi button { flex: 1; min-width: 0; }
  .verdi.doppi button { font-size: 15px; gap: 5px; padding-left: 6px; padding-right: 6px; }
  .verdi.doppi button svg { width: 18px; height: 18px; }
  .riga-secondaria { grid-column: 1 / -1; display: grid; grid-template-columns: 2fr 1fr; gap: 10px; }
  .riga-secondaria.sola { grid-template-columns: 1fr; }
  button.cmd { font: inherit; border: 0; border-radius: 14px; padding: 14px 10px; font-size: 16px; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; transition: transform .05s, opacity .15s; }
  button.cmd:active { transform: scale(.98); }
  button.cmd:disabled { opacity: .45; cursor: not-allowed; }
  button.cmd svg { width: 22px; height: 22px; flex: none; }
  .verde { background: var(--nn-verde); color: #fff; box-shadow: 0 2px 6px rgba(46,158,107,.35); }
  .rosso { background: var(--nn-rosso); color: #fff; box-shadow: 0 2px 6px rgba(222,74,81,.35); }
  .rosso.evidente { animation: pulsa 1.2s ease-in-out infinite; }
  @keyframes pulsa { 50% { box-shadow: 0 0 0 6px rgba(222,74,81,.18); } }
  .neutro { background: var(--nn-riquadro); color: var(--nn-testo); border: 1px solid var(--nn-bordo) !important; font-size: 15px; font-weight: 600; padding: 11px 10px; }
  .riscontro { margin: 8px 16px 0; min-height: 18px; font-size: 13px; color: var(--nn-grigio); }
  .riscontro.ok { color: var(--nn-verde-scuro); }
  .riscontro.no { color: var(--nn-rosso-scuro); }
  .riquadri { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 8px 16px 4px; }
  .riq { position: relative; background: var(--nn-riquadro); border: 1px solid var(--nn-bordo); border-radius: 14px; padding: 10px 12px 10px 16px; }
  .riq::before { content: ""; position: absolute; left: 0; top: 12px; bottom: 12px; width: 4px; border-radius: 2px; background: var(--accento, var(--nn-grigio-chiaro)); }
  .riq .cap { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--accento-testo, var(--nn-grigio)); }
  .riq .val { font-size: 18px; font-weight: 600; margin-top: 3px; }
  .riq .val small { font-size: 13px; color: var(--nn-grigio-chiaro); font-weight: 500; }
  .riq .sotto { font-size: 11px; color: var(--nn-grigio-chiaro); margin-top: 2px; }
  .barra { height: 5px; border-radius: 3px; background: color-mix(in srgb, var(--nn-grigio) 15%, transparent); margin-top: 6px; overflow: hidden; }
  .barra i { display: block; height: 100%; background: var(--nn-ambra); border-radius: 3px; }
  details.diag { margin: 12px 16px 12px; background: var(--nn-riquadro); border: 1px solid var(--nn-bordo); border-radius: 14px; }
  details.diag summary { list-style: none; cursor: pointer; padding: 12px 14px; font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--nn-grigio); display: flex; align-items: center; gap: 8px; }
  details.diag summary::-webkit-details-marker { display: none; }
  details.diag summary .conta { margin-left: auto; font-size: 11px; letter-spacing: 0; text-transform: none; font-weight: 600; padding: 2px 8px; border-radius: 999px; background: color-mix(in srgb, var(--nn-grigio) 12%, transparent); }
  details.diag summary .conta.rosso-t { background: #FBE7E8; color: var(--nn-rosso-scuro); }
  details.diag summary .freccia { transition: transform .15s; }
  details.diag[open] summary .freccia { transform: rotate(90deg); }
  .diag-corpo { padding: 0 14px 14px; }
  .diag h4 { margin: 12px 0 6px; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--nn-grigio-chiaro); }
  .lista { border: 1px solid var(--nn-bordo); border-radius: 10px; overflow: hidden; }
  .riga { display: grid; grid-template-columns: 86px 1fr; gap: 8px; padding: 7px 10px; font-size: 13px; border-top: 1px solid color-mix(in srgb, var(--nn-bordo) 70%, transparent); }
  .riga:first-child { border-top: 0; }
  .riga .quando { color: var(--nn-grigio-chiaro); font-variant-numeric: tabular-nums; }
  .riga .cosa b { font-weight: 600; }
  .riga .codici { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; color: var(--nn-grigio); word-break: break-word; }
  .vuoto { padding: 10px; font-size: 13px; color: var(--nn-grigio-chiaro); text-align: center; }
  .coppie { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; font-size: 13px; }
  .coppie span:nth-child(odd) { color: var(--nn-grigio-chiaro); }
  .azioni-diag { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .piccolo { font: inherit; font-size: 13px; font-weight: 600; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--nn-bordo); background: var(--nn-riquadro); color: var(--nn-testo); cursor: pointer; }
  .piccolo.pericolo { color: var(--nn-rosso-scuro); border-color: #F2C6C9; }
  .piccolo:disabled { opacity: .45; cursor: not-allowed; }
  .spento { opacity: .45; pointer-events: none; }
  .velo { position: absolute; inset: 0; background: rgba(31,41,51,.35); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 2; }
  .dialogo { background: var(--nn-riquadro); color: var(--nn-testo); border-radius: 16px; padding: 18px; max-width: 340px; box-shadow: 0 10px 30px rgba(0,0,0,.2); }
  .dialogo h5 { margin: 0 0 8px; font-size: 16px; }
  .dialogo p { margin: 0 0 14px; font-size: 14px; color: var(--nn-grigio); line-height: 1.45; }
  .dialogo .azioni-diag { justify-content: flex-end; }
  .avviso-config { padding: 16px; color: var(--nn-rosso-scuro, #C93C43); }
  [hidden] { display: none !important; }
`;

const ICONE = {
  apri: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  chiudi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  pedonale: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="5" r="2"/><path d="M12 8v6M9 21l3-7 3 7M8 11h8"/></svg>',
  luce: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V17h5v-1.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/></svg>',
};

// ---------------------------------------------------------------------------
// Disegni: uno per tipologia, stessa scena 600x200
// ---------------------------------------------------------------------------
const SUOLO = '<rect x="0" y="176" width="600" height="24" fill="#EEF2F6"/>';
const LAMPEGGIANTE = (x, y) => `<rect x="${x}" y="${y}" width="22" height="14" rx="4" class="lampeggiante" fill="#E6EAEF" stroke="#C5CED8" stroke-width="2"/>`;
const PILASTRO = (x) => `<rect x="${x}" y="44" width="30" height="134" rx="4" fill="#E9EDF2" stroke="#C5CED8" stroke-width="2"/>`;
const OSTACOLO = (x, y) => `<g class="avviso-ostacolo" style="display:none"><circle cx="${x}" cy="${y}" r="30" fill="#DE4A51" opacity=".95"/><path d="M${x} ${y - 18} v22 M${x} ${y + 14} v2" stroke="#fff" stroke-width="7" stroke-linecap="round"/></g>`;
const LED = (x, y) => `<circle cx="${x}" cy="${y}" r="3" class="led" fill="#2E9E6B"/>`;
const FACCIATA = '<rect x="70" y="10" width="460" height="168" fill="#F1F4F8"/><rect x="120" y="40" width="360" height="138" fill="#CCD4DD"/>' +
  '<rect x="278" y="16" width="44" height="16" rx="4" fill="#E9EDF2" stroke="#AEB8C3" stroke-width="2"/>' + LED(288, 24);
const CORNICE = '<path d="M116 178 V36 H484 V178" fill="none" stroke="#8C98A5" stroke-width="6" stroke-linejoin="round"/>';
let contatoreClip = 0;

function anta(cardine, direzione, larghezza, percentuale) {
  // Anta a battente vista di fronte: ruotando si accorcia e il bordo libero,
  // che viene verso chi guarda, si allunga.
  const angolo = (80 * Math.PI / 180) * percentuale / 100;
  const visibile = larghezza * Math.cos(angolo);
  const e = 16 * Math.sin(angolo);
  const x2 = cardine + direzione * visibile;
  const alto = 62, basso = 172;
  let s = `<polygon points="${cardine},${alto} ${x2},${alto - e} ${x2},${basso + e} ${cardine},${basso}" fill="#FFFFFF" fill-opacity="0.35" stroke="#8C98A5" stroke-width="4" stroke-linejoin="round"/>`;
  const sbarre = Math.max(3, Math.round(larghezza / 32));
  for (let i = 1; i < sbarre; i++) {
    const f = i / sbarre, x = cardine + direzione * visibile * f;
    s += `<line x1="${x}" y1="${alto - e * f + 10}" x2="${x}" y2="${basso + e * f - 10}" stroke="#AEB8C3" stroke-width="5" stroke-linecap="round"/>`;
  }
  return s + `<line x1="${cardine}" y1="117" x2="${x2}" y2="117" stroke="#C5CED8" stroke-width="4"/>`;
}

const SCENE = {
  scorrevole: {
    disegno: () => SUOLO +
      '<line x1="20" y1="178" x2="580" y2="178" stroke="#B9C3CE" stroke-width="4" stroke-linecap="round"/>' +
      '<g stroke="#D3DAE2" stroke-width="3"><line x1="30" y1="78" x2="300" y2="78"/><line x1="30" y1="150" x2="300" y2="150"/></g>' +
      '<rect x="262" y="136" width="44" height="40" rx="6" fill="#E9EDF2" stroke="#AEB8C3" stroke-width="2"/>' + LED(272, 148) +
      '<g class="scorre"><rect x="300" y="60" width="252" height="112" rx="6" fill="#FFFFFF" fill-opacity="0.35" stroke="#8C98A5" stroke-width="4"/>' +
      '<g stroke="#AEB8C3" stroke-width="5" stroke-linecap="round">' +
      [330, 360, 390, 420, 450, 480, 510].map((x) => `<line x1="${x}" y1="70" x2="${x}" y2="162"/>`).join("") + "</g>" +
      '<line x1="304" y1="116" x2="548" y2="116" stroke="#C5CED8" stroke-width="4"/>' +
      '<circle cx="330" cy="178" r="7" fill="#8C98A5"/><circle cx="522" cy="178" r="7" fill="#8C98A5"/></g>' +
      PILASTRO(552) + LAMPEGGIANTE(556, 30) + OSTACOLO(430, 116),
    // Stile CSS e non attributo: solo cosi' la transizione rende fluido lo scorrimento.
    muovi: (svg, a) => { svg.querySelector(".scorre").style.transform = `translate(${-252 * a / 100}px, 0px)`; },
  },
  due_ante: {
    disegno: () => SUOLO + PILASTRO(40) + PILASTRO(530) + LAMPEGGIANTE(534, 30) +
      '<rect x="72" y="146" width="28" height="12" rx="3" fill="#E9EDF2" stroke="#AEB8C3" stroke-width="2"/>' +
      '<rect x="500" y="146" width="28" height="12" rx="3" fill="#E9EDF2" stroke="#AEB8C3" stroke-width="2"/>' + LED(80, 152) +
      '<g class="ante"></g>' + OSTACOLO(300, 116),
    muovi: (svg, a, b) => { svg.querySelector(".ante").innerHTML = anta(70, 1, 230, a) + anta(530, -1, 230, b); },
  },
  una_anta: {
    disegno: () => SUOLO + PILASTRO(40) + PILASTRO(530) + LAMPEGGIANTE(534, 30) +
      '<rect x="72" y="146" width="28" height="12" rx="3" fill="#E9EDF2" stroke="#AEB8C3" stroke-width="2"/>' + LED(80, 152) +
      '<g class="ante"></g>' + OSTACOLO(300, 116),
    muovi: (svg, a) => { svg.querySelector(".ante").innerHTML = anta(70, 1, 460, a); },
  },
  sezionale: {
    disegno: () => {
      const id = `nexus-nice-porta-${++contatoreClip}`;
      return SUOLO + FACCIATA +
        `<clipPath id="${id}"><rect x="120" y="40" width="360" height="138"/></clipPath>` +
        `<g clip-path="url(#${id})"><g class="scorre">` +
        [0, 1, 2, 3].map((i) => {
          const y = 40 + i * 34.5;
          return `<rect x="122" y="${y + 1}" width="356" height="32.5" rx="3" fill="#F7F9FB" stroke="#AEB8C3" stroke-width="2"/>` +
            `<line x1="136" y1="${y + 17}" x2="464" y2="${y + 17}" stroke="#DCE2E9" stroke-width="3"/>`;
        }).join("") + "</g></g>" + CORNICE + LAMPEGGIANTE(492, 20) + OSTACOLO(300, 116);
    },
    muovi: (svg, a) => { svg.querySelector(".scorre").style.transform = `translate(0px, ${-138 * a / 100}px)`; },
  },
  basculante: {
    disegno: () => SUOLO + FACCIATA + '<g class="basc"></g>' + CORNICE + LAMPEGGIANTE(492, 20) + OSTACOLO(300, 116),
    muovi: (svg, a) => {
      // Il pannello ruota e sale: in basso si avvicina (si allarga) e la sua
      // altezza apparente si riduce.
      const yb = 40 + 138 * (1 - a / 100), k = 22 * Math.sin(Math.PI * a / 100);
      let s = `<polygon points="122,40 478,40 ${478 + k},${yb} ${122 - k},${yb}" fill="#F7F9FB" stroke="#8C98A5" stroke-width="3" stroke-linejoin="round"/>`;
      if (yb - 40 > 12) {
        for (let i = 1; i < 9; i++) {
          const f = i / 9, xt = 122 + 356 * f, xb = 122 - k + (356 + 2 * k) * f;
          s += `<line x1="${xt}" y1="46" x2="${xb}" y2="${yb - 6}" stroke="#D3DAE2" stroke-width="3" stroke-linecap="round"/>`;
        }
      }
      svg.querySelector(".basc").innerHTML = s;
    },
  },
};

// ---------------------------------------------------------------------------
// Utilita'
// ---------------------------------------------------------------------------
const NON_VALIDI = new Set(["unknown", "unavailable", "", undefined, null]);

function testoSicuro(valore) {
  return String(valore ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function dataOra(istante) {
  const d = new Date(istante);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function oraLocaleModulo(testo) {
  // Ora LOCALE del modulo senza fuso, oppure «non sincronizzata».
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(testo || ""));
  return m ? `${m[3]}/${m[2]} ${m[4]}:${m[5]}` : (testo ? String(testo) : "");
}

function azioneT4(valore) {
  // Dal sidecar V3 il gateway la decodifica («nessun codice (000)»); letture
  // precedenti la portano ancora in base64 del codice a tre cifre.
  const testo = String(valore ?? "");
  if (/^[A-Za-z0-9+/]{4}$/.test(testo)) {
    try {
      const codice = atob(testo);
      if (/^\d{3}$/.test(codice)) return codice === "000" ? "nessun codice (000)" : `codice ${codice}`;
    } catch (_e) { /* non era base64 */ }
  }
  return testo;
}

function vocePerRegistro(voce) {
  const tipo = String(voce.tipo || "");
  const azioni = { open: "apertura", close: "chiusura", stop: "stop" };
  if (tipo === "DoorAction") return ["Manovra", azioni[voce.azione] || voce.azione || ""];
  if (tipo === "T4 action") return ["Comando T4", azioneT4(voce.azione_t4)];
  if (tipo === "Power ON") return ["Accensione", voce.ambito === "modulo" ? "modulo" : "centrale"];
  if (tipo === "connect") return ["Collegamento", voce.ambito || ""];
  return [tipo || "Voce", voce.azione || voce.stato || ""];
}

function numero(stato) {
  if (!stato || NON_VALIDI.has(stato.state)) return null;
  const n = Number(stato.state);
  return Number.isFinite(n) ? n : null;
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------
class NexusNiceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._el = null;
    this._firmaScena = null;
    this._trascinando = false;
    this._obiettivo = null;
    this._eventoVisto = undefined;
    this._timerMessaggio = null;
    this._timerRiavvio = null;
    this._confermaAperta = false;
  }

  static getConfigElement() {
    return document.createElement("nexus-nice-card-editor");
  }

  static getStubConfig(hass) {
    const trovata = Object.keys(hass.states).find((id) => hass.states[id].attributes.ruolo === "mappa_cancello");
    return { entity: trovata || "" };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("Indica il sensore «Mappa cancello» di Nexus Nice");
    this._config = config;
    this._el = null;
    this._firmaScena = null;
    this.shadowRoot.innerHTML = "";
    if (this._hass) this._aggiorna();
  }

  set hass(hass) {
    this._hass = hass;
    this._aggiorna();
  }

  getCardSize() {
    return 10;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  disconnectedCallback() {
    clearTimeout(this._timerMessaggio);
    clearTimeout(this._timerRiavvio);
  }

  // -------------------------------------------------------------------------
  _mappa() {
    const stato = this._hass && this._config ? this._hass.states[this._config.entity] : null;
    return stato ? stato.attributes : null;
  }

  _stato(chiave) {
    const mappa = this._mappa();
    const id = mappa && mappa.entita ? mappa.entita[chiave] : null;
    return id ? this._hass.states[id] || null : null;
  }

  _costruisci() {
    const r = this.shadowRoot;
    r.innerHTML = `<style>${STILE}</style>
      <ha-card>
        <div class="corpo">
          <div class="testata"><h3 class="titolo"></h3><span class="collegamento"><i></i><span class="coll-testo"></span></span></div>
          <div class="banner" hidden>Modulo Nice non raggiungibile: comandi sospesi</div>
          <div class="scena">
            <span class="stato-pill"></span>
            <div class="percentuale"><b class="pct"></b><small class="fonte"></small></div>
            <svg class="disegno" viewBox="0 0 600 200" aria-hidden="true"></svg>
          </div>
          <div class="slider-blocco">
            <div class="slider-testa"><span>Apertura</span><span class="nota"></span></div>
            <div class="binario">
              <div class="pista"></div><div class="riempito"></div><div class="obiettivo" hidden></div>
              <input type="range" min="0" max="100" step="1" value="0" aria-label="Apertura in percentuale">
            </div>
            <div class="scala"><span class="scala-chiuso"></span><span>50%</span><span class="scala-aperto"></span></div>
          </div>
          <div class="comandi">
            <div class="verdi">
              <button class="cmd verde" data-cmd="apri">${ICONE.apri}<span>Apri</span></button>
              <button class="cmd verde" data-cmd="chiudi">${ICONE.chiudi}<span>Chiudi</span></button>
            </div>
            <button class="cmd rosso" data-cmd="stop">${ICONE.stop}<span>Stop</span></button>
            <div class="riga-secondaria">
              <button class="cmd neutro" data-cmd="parziale">${ICONE.pedonale}<span class="etichetta-parziale"></span></button>
              <button class="cmd neutro" data-cmd="luce">${ICONE.luce}<span>Luce</span></button>
            </div>
          </div>
          <div class="riscontro"></div>
          <div class="riquadri">
            <div class="riq" data-riq="ostacolo"><div class="cap">Ostacolo</div><div class="val"></div><div class="sotto">aggiornato a manovra finita</div></div>
            <div class="riq" data-riq="arresto" style="--accento:#8C98A5"><div class="cap">Ultimo arresto</div><div class="val"></div><div class="sotto">motivo dalla centrale</div></div>
            <div class="riq" data-riq="accensione" style="--accento:#3C84C6;--accento-testo:#2F6FA8"><div class="cap">Manovre dall'accensione</div><div class="val"></div><div class="sotto">dall'ultima mancanza di corrente</div></div>
            <div class="riq" data-riq="manutenzione"><div class="cap">Manutenzione</div><div class="val"></div><div class="barra"><i></i></div><div class="sotto"></div></div>
          </div>
          <details class="diag">
            <summary><span class="freccia">▸</span> Diagnostica <span class="conta"></span></summary>
            <div class="diag-corpo">
              <h4>Errori e avvisi</h4>
              <div class="lista lista-errori"></div>
              <div class="blocco-registro">
                <h4>Registro eventi del modulo</h4>
                <div class="coppie"><span>Letto</span><span class="letto"></span></div>
                <div class="lista lista-registro" style="margin-top:6px"></div>
              </div>
              <h4>Automazione</h4>
              <div class="coppie">
                <span>Tipologia</span><span class="v-tipo"></span>
                <span>Posizione</span><span class="v-sorgente"></span>
                <span>Ultimo comando</span><span class="v-ultimo"></span>
              </div>
              <div class="azioni-diag">
                <button class="piccolo" data-cmd="registro">Leggi registro</button>
                <button class="piccolo pericolo" data-cmd="riavvia">Riavvia interfaccia…</button>
              </div>
            </div>
          </details>
        </div>
      </ha-card>`;

    const q = (s) => r.querySelector(s);
    this._el = {
      q,
      titolo: q(".titolo"), collegamento: q(".collegamento"), collTesto: q(".coll-testo"), banner: q(".banner"),
      scena: q(".scena"), pill: q(".stato-pill"), pct: q(".pct"), fonte: q(".fonte"), svg: q("svg.disegno"),
      slider: q("input"), riempito: q(".riempito"), obiettivo: q(".obiettivo"), nota: q(".slider-testa .nota"),
      scalaChiuso: q(".scala-chiuso"), scalaAperto: q(".scala-aperto"), sliderBlocco: q(".slider-blocco"),
      comandi: q(".comandi"), verdi: q(".verdi"), apri: q('[data-cmd="apri"]'), chiudi: q('[data-cmd="chiudi"]'),
      stop: q('[data-cmd="stop"]'), secondaria: q(".riga-secondaria"), parziale: q('[data-cmd="parziale"]'),
      etichettaParziale: q(".etichetta-parziale"), luce: q('[data-cmd="luce"]'), riscontro: q(".riscontro"),
      riquadri: q(".riquadri"), diag: q("details.diag"), conta: q(".conta"), listaErrori: q(".lista-errori"),
      bloccoRegistro: q(".blocco-registro"), letto: q(".letto"), listaRegistro: q(".lista-registro"),
      tipo: q(".v-tipo"), sorgente: q(".v-sorgente"), ultimo: q(".v-ultimo"),
      registro: q('[data-cmd="registro"]'), riavvia: q('[data-cmd="riavvia"]'),
    };

    const el = this._el;
    el.apri.addEventListener("click", () => this._cover("open_cover"));
    el.chiudi.addEventListener("click", () => this._cover("close_cover"));
    el.stop.addEventListener("click", () => this._cover("stop_cover"));
    el.parziale.addEventListener("click", () => this._premi("parziale", `${this._tipo().parziale}: comando inviato`));
    el.luce.addEventListener("click", () => this._premi("luce", "Luce di cortesia: comando inviato"));
    el.registro.addEventListener("click", () => this._premi("registro_leggi", "Lettura del registro richiesta"));
    el.riavvia.addEventListener("click", () => this._chiediRiavvio());
    el.slider.addEventListener("input", () => {
      this._trascinando = true;
      this._disegnaSlider(Number(el.slider.value), Number(el.slider.value));
    });
    el.slider.addEventListener("change", () => {
      this._trascinando = false;
      const valore = Number(el.slider.value);
      this._obiettivo = { valore, da: Date.now() };
      this._cover("set_cover_position", { position: valore }, `Vado al ${valore}%`);
    });
  }

  _tipo() {
    const mappa = this._mappa();
    return TIPI[mappa && mappa.tipologia] || TIPI.scorrevole;
  }

  // -------------------------------------------------------------------------
  // Comandi
  // -------------------------------------------------------------------------
  _cover(servizio, dati = {}, messaggio) {
    const mappa = this._mappa();
    const id = mappa && mappa.entita ? mappa.entita.cancello : null;
    if (!id) return;
    const testi = { open_cover: "Apertura in corso", close_cover: "Chiusura in corso", stop_cover: "Stop inviato" };
    this._invia("cover", servizio, id, dati, messaggio || testi[servizio]);
  }

  _premi(chiave, messaggio) {
    const mappa = this._mappa();
    const id = mappa && mappa.entita ? mappa.entita[chiave] : null;
    if (id) this._invia("button", "press", id, {}, messaggio);
  }

  _invia(dominio, servizio, entityId, dati, messaggio) {
    Promise.resolve(this._hass.callService(dominio, servizio, dati, { entity_id: entityId }))
      .then(() => { if (messaggio) this._messaggio(messaggio, "ok"); })
      .catch((errore) => this._messaggio(`Comando non riuscito: ${errore && errore.message ? errore.message : errore}`, "no"));
  }

  _messaggio(testo, tono) {
    if (!this._el) return;
    this._el.riscontro.textContent = testo;
    this._el.riscontro.className = `riscontro ${tono || ""}`;
    clearTimeout(this._timerMessaggio);
    this._timerMessaggio = setTimeout(() => { if (this._el) this._el.riscontro.textContent = ""; }, 6000);
  }

  _chiediRiavvio() {
    if (this._confermaAperta) return;
    this._confermaAperta = true;
    const velo = document.createElement("div");
    velo.className = "velo";
    velo.innerHTML = `<div class="dialogo" role="dialog" aria-modal="true">
        <h5>Riavviare l'interfaccia WiFi?</h5>
        <p>Il modulo Nice si scollega per circa un minuto e l'automazione non risponde ai comandi finché non torna. Non avvia nessuna manovra.</p>
        <div class="azioni-diag"><button class="piccolo" data-scelta="no">Annulla</button><button class="piccolo pericolo" data-scelta="si">Riavvia</button></div>
      </div>`;
    const chiudi = (conferma) => {
      velo.remove();
      this._confermaAperta = false;
      if (conferma) this._premi("riavvia", "Riavvio dell'interfaccia richiesto: il modulo torna fra circa un minuto");
    };
    velo.addEventListener("click", (evento) => {
      const scelta = evento.target && evento.target.dataset ? evento.target.dataset.scelta : null;
      if (scelta) chiudi(scelta === "si");
      else if (evento.target === velo) chiudi(false);
    });
    this.shadowRoot.querySelector("ha-card").style.position = "relative";
    this.shadowRoot.querySelector("ha-card").appendChild(velo);
  }

  // -------------------------------------------------------------------------
  // Disegno
  // -------------------------------------------------------------------------
  _aggiorna() {
    if (!this._hass || !this._config) return;
    const mappa = this._mappa();
    if (!mappa) {
      this.shadowRoot.innerHTML = `<style>${STILE}</style><ha-card><div class="avviso-config">Entità ${testoSicuro(this._config.entity)} non trovata: controlla la card o l'integrazione Nexus Nice.</div></ha-card>`;
      this._el = null;
      return;
    }
    if (!this._el) this._costruisci();
    const el = this._el;
    const tipologia = TIPI[mappa.tipologia] ? mappa.tipologia : "scorrevole";
    const tipo = TIPI[tipologia];
    const f = tipo.femminile;

    const firma = `${tipologia}|${mappa.verso}`;
    if (firma !== this._firmaScena) {
      const specchia = VERSI[tipologia] && mappa.verso === "destra";
      el.svg.innerHTML = specchia
        ? `<g transform="translate(600 0) scale(-1 1)">${SCENE[tipologia].disegno()}</g>`
        : SCENE[tipologia].disegno();
      this._firmaScena = firma;
    }

    const cover = this._stato("cancello");
    const disponibile = Boolean(cover) && !NON_VALIDI.has(cover.state);
    const statoCover = cover ? cover.state : "unavailable";
    const inMoto = statoCover === "opening" || statoCover === "closing";
    let pos = cover ? Number(cover.attributes.current_position) : NaN;
    if (!Number.isFinite(pos)) pos = statoCover === "closed" ? 0 : statoCover === "open" ? 100 : 0;
    pos = Math.max(0, Math.min(100, pos));
    const pedonale = tipologia === "due_ante" && Boolean(mappa.pedonale) && statoCover !== "closed";
    const ostacolo = this._stato("ostacolo");
    const ostacoloOn = ostacolo && ostacolo.state === "on";
    const sorgente = this._stato("sorgente_posizione");
    const stima = sorgente && /stima/i.test(sorgente.state);

    // Testata
    el.titolo.textContent = this._config.title || mappa.nome || (f ? "Garage" : "Cancello");
    el.collegamento.classList.toggle("giu", !disponibile);
    el.collTesto.textContent = disponibile ? "Modulo collegato" : "Modulo scollegato";
    el.banner.hidden = disponibile;
    el.scena.classList.toggle("spento", !disponibile);

    // Stato e disegno
    let testo, tono = "";
    if (!disponibile) { testo = "Non raggiungibile"; tono = "allarme"; }
    else if (statoCover === "opening") { testo = "In apertura"; tono = "moto"; }
    else if (statoCover === "closing") { testo = "In chiusura"; tono = "moto"; }
    else if (ostacoloOn && statoCover !== "closed") { testo = `${f ? "Ferma" : "Fermo"} · ostacolo`; tono = "allarme"; }
    else if (statoCover === "closed") testo = f ? "Chiusa" : "Chiuso";
    else if (pedonale) { testo = "Aperto · pedonale"; tono = "aperto"; }
    else if (pos >= 100) { testo = f ? "Aperta" : "Aperto"; tono = "aperto"; }
    else { testo = `${f ? "Ferma" : "Fermo"} al ${Math.round(pos)}%`; tono = "aperto"; }
    el.pill.textContent = testo;
    el.pill.className = `stato-pill ${tono}`;
    el.pct.textContent = disponibile ? `${Math.round(pos)}%` : "—";
    el.fonte.textContent = sorgente && !NON_VALIDI.has(sorgente.state) ? (stima ? "stima a tempo" : "encoder") : "";

    const svg = el.svg;
    // Un solo numero di posizione per tutto il cancello: nell'apertura pedonale
    // del due ante lo si attribuisce all'anta che si apre, l'altra resta chiusa.
    SCENE[tipologia].muovi(svg, pos, pedonale ? 0 : pos);
    svg.classList.toggle("in-moto", inMoto);
    svg.querySelectorAll(".led").forEach((led) => led.setAttribute("fill", disponibile ? "#2E9E6B" : "#DE4A51"));
    svg.querySelectorAll(".avviso-ostacolo").forEach((a) => { a.style.display = ostacoloOn ? "" : "none"; });

    // Slider
    const posizionabile = disponibile && (Number(cover.attributes.supported_features) & 4) === 4;
    el.slider.disabled = !posizionabile;
    if (this._obiettivo && ((!inMoto && Math.abs(pos - this._obiettivo.valore) <= 2) || Date.now() - this._obiettivo.da > 120000)) {
      this._obiettivo = null;
    }
    if (!this._trascinando) {
      el.slider.value = String(Math.round(pos));
      this._disegnaSlider(pos, inMoto && this._obiettivo ? this._obiettivo.valore : null);
    }
    el.nota.textContent = !posizionabile
      ? (disponibile ? "posizione non comandabile" : "")
      : inMoto && this._obiettivo ? `obiettivo ${this._obiettivo.valore}%`
        : stima && Math.round(pos) === 50 && statoCover === "open" ? "posizione non nota, a metà"
          : "trascina per scegliere la posizione";
    el.scalaChiuso.textContent = f ? "chiusa" : "chiuso";
    el.scalaAperto.textContent = f ? "aperta" : "aperto";

    // Comandi: chiuso solo Apri, tutto aperto solo Chiudi, fermo a meta' entrambi.
    el.apri.hidden = !inMoto && pos >= 100 && !pedonale;
    el.chiudi.hidden = !inMoto && statoCover === "closed";
    el.verdi.classList.toggle("doppi", !el.apri.hidden && !el.chiudi.hidden);
    el.apri.disabled = el.chiudi.disabled = !disponibile || inMoto;
    el.stop.disabled = !disponibile;
    el.stop.classList.toggle("evidente", inMoto);
    const conParziale = Boolean(mappa.entita && mappa.entita.parziale);
    const conLuce = Boolean(mappa.entita && mappa.entita.luce);
    el.parziale.hidden = !conParziale;
    el.luce.hidden = !conLuce;
    el.secondaria.hidden = !conParziale && !conLuce;
    el.secondaria.classList.toggle("sola", conParziale !== conLuce);
    el.etichettaParziale.textContent = tipo.parziale;
    el.parziale.disabled = el.luce.disabled = !disponibile;

    this._aggiornaRiquadri(mappa);
    this._aggiornaDiagnostica(mappa, tipologia, disponibile, inMoto);
    this._riscontroEventi();
  }

  _disegnaSlider(valore, obiettivo) {
    const el = this._el;
    el.riempito.style.width = `${valore}%`;
    if (obiettivo === null || obiettivo === undefined) {
      el.obiettivo.hidden = true;
    } else {
      el.obiettivo.hidden = false;
      el.obiettivo.style.left = `${obiettivo}%`;
    }
  }

  _aggiornaRiquadri(mappa) {
    const el = this._el;
    const q = el.q;
    const e = mappa.entita || {};
    const presenti = ["ostacolo", "motivo_arresto", "manovre_accensione", "manovre_manutenzione"].filter((k) => e[k]);
    el.riquadri.hidden = presenti.length === 0;

    const riqOst = q('[data-riq="ostacolo"]');
    const ost = this._stato("ostacolo");
    riqOst.hidden = !e.ostacolo;
    if (ost) {
      const on = ost.state === "on";
      riqOst.querySelector(".val").textContent = NON_VALIDI.has(ost.state) ? "—" : on ? "Rilevato" : "Nessuno";
      riqOst.style.setProperty("--accento", on ? "#DE4A51" : "#2E9E6B");
      riqOst.style.setProperty("--accento-testo", on ? "#C93C43" : "#23805A");
    }

    const riqArr = q('[data-riq="arresto"]');
    const arr = this._stato("motivo_arresto");
    riqArr.hidden = !e.motivo_arresto;
    if (arr) riqArr.querySelector(".val").textContent = NON_VALIDI.has(arr.state) ? "—" : arr.state;

    const riqAcc = q('[data-riq="accensione"]');
    const acc = numero(this._stato("manovre_accensione"));
    riqAcc.hidden = !e.manovre_accensione;
    riqAcc.querySelector(".val").textContent = acc === null ? "—" : String(acc);

    const riqMan = q('[data-riq="manutenzione"]');
    const manStato = this._stato("manovre_manutenzione");
    const man = numero(manStato);
    riqMan.hidden = !e.manovre_manutenzione;
    const soglia = manStato ? Number(manStato.attributes.soglia_manutenzione) : NaN;
    const dovuta = this._stato("manutenzione_dovuta");
    const dovutaOn = dovuta && dovuta.state === "on";
    riqMan.style.setProperty("--accento", dovutaOn ? "#DE4A51" : "#E39B32");
    riqMan.style.setProperty("--accento-testo", dovutaOn ? "#C93C43" : "#C9801F");
    riqMan.querySelector(".val").innerHTML = man === null ? "—"
      : Number.isFinite(soglia) && soglia > 0 ? `${man} <small>/ ${soglia}</small>` : String(man);
    const barra = riqMan.querySelector(".barra");
    barra.hidden = !(man !== null && Number.isFinite(soglia) && soglia > 0);
    if (!barra.hidden) barra.querySelector("i").style.width = `${Math.min(100, (man / soglia) * 100).toFixed(1)}%`;
    riqMan.querySelector(".sotto").textContent = dovutaOn ? "manutenzione dovuta" : "manovre dall'ultima manutenzione";
  }

  _aggiornaDiagnostica(mappa, tipologia, disponibile, inMoto) {
    const el = this._el;
    const limite = Date.now() - GIORNI_STORICO * 86400000;
    const errori = (mappa.errori || []).filter((v) => new Date(v.ts).getTime() >= limite);
    const gravi = errori.some((v) => EVENTI_ERRORE.has(v.tipo));
    el.conta.textContent = errori.length ? `${errori.length} ${errori.length === 1 ? "evento" : "eventi"}` : "nessun errore";
    el.conta.classList.toggle("rosso-t", gravi);
    const firmaErrori = JSON.stringify(errori.map((v) => [v.ts, v.tipo]));
    if (firmaErrori !== this._firmaErrori) {
      this._firmaErrori = firmaErrori;
      el.listaErrori.innerHTML = errori.length
        ? errori.slice(0, 20).map((v) => {
          const codici = Object.entries(v.attributi || {}).map(([k, val]) => `${k}: ${val}`).join(" · ");
          return `<div class="riga"><span class="quando">${testoSicuro(dataOra(v.ts))}</span><span class="cosa"><b>${testoSicuro(ETICHETTE_EVENTI[v.tipo] || v.tipo)}</b>${codici ? `<br><span class="codici">${testoSicuro(codici)}</span>` : ""}</span></div>`;
        }).join("")
        : `<div class="vuoto">Nessun errore dal modulo negli ultimi ${GIORNI_STORICO} giorni</div>`;
    }

    const registro = this._stato("registro");
    el.bloccoRegistro.hidden = !registro;
    if (registro) {
      const voci = Array.isArray(registro.attributes.eventi) ? registro.attributes.eventi : [];
      el.letto.textContent = NON_VALIDI.has(registro.state)
        ? "mai letto"
        : `${dataOra(registro.state)} · ${registro.attributes.voci ?? voci.length} voci`;
      const firmaRegistro = `${registro.state}|${voci.length}`;
      if (firmaRegistro !== this._firmaRegistro) {
        this._firmaRegistro = firmaRegistro;
        el.listaRegistro.innerHTML = voci.length
          ? voci.slice(-6).reverse().map((voce) => {
            const [titolo, dettaglio] = vocePerRegistro(voce);
            return `<div class="riga"><span class="quando">${testoSicuro(oraLocaleModulo(voce.ora))}</span><span class="cosa"><b>${testoSicuro(titolo)}</b>${dettaglio ? ` · ${testoSicuro(dettaglio)}` : ""}</span></div>`;
          }).join("")
          : '<div class="vuoto">Premi «Leggi registro» per scaricarlo dal modulo</div>';
      }
    }

    const verso = VERSI[tipologia] ? ` · ${VERSI[tipologia][mappa.verso] || VERSI[tipologia].sinistra}` : "";
    el.tipo.textContent = `${TIPI[tipologia].nome}${verso}`;
    const sorgente = this._stato("sorgente_posizione");
    el.sorgente.textContent = sorgente && !NON_VALIDI.has(sorgente.state) ? sorgente.state : "—";
    const ultimo = mappa.ultimo_comando;
    el.ultimo.textContent = ultimo
      ? `${AZIONI[ultimo.azione] || ultimo.azione}${ultimo.azione === "posizione" && ultimo.posizione !== undefined ? ` ${ultimo.posizione}%` : ""} · ${dataOra(ultimo.ts)}`
      : "—";

    el.registro.hidden = !(mappa.entita && mappa.entita.registro_leggi);
    el.registro.disabled = !disponibile;
    el.riavvia.hidden = !(mappa.entita && mappa.entita.riavvia);
    // Il gateway rifiuta il riavvio col cancello in movimento e nei 30 secondi
    // dopo un comando di manovra: il pulsante lo dice prima di premerlo.
    const trascorso = mappa.ultimo_movimento ? Date.now() - new Date(mappa.ultimo_movimento).getTime() : Infinity;
    const attesa = ATTESA_RIAVVIO_MS - trascorso;
    el.riavvia.disabled = !disponibile || inMoto || attesa > 0;
    clearTimeout(this._timerRiavvio);
    if (attesa > 0) this._timerRiavvio = setTimeout(() => this._aggiorna(), attesa + 200);
  }

  _riscontroEventi() {
    // L'esito di un comando che non muove il cancello, o un rifiuto, arriva come
    // evento: si mostra solo se e' nuovo rispetto a quando la card e' stata aperta.
    // Il riferimento e' l'ultimo istante valido visto: «unknown» (nessun evento
    // mai arrivato) conta come riferimento, cosi' il primo evento in assoluto
    // viene mostrato; il ritorno da «unavailable» allo stesso evento no.
    const evento = this._stato("eventi");
    if (!evento) return;
    if (this._eventoVisto === undefined) {
      this._eventoVisto = NON_VALIDI.has(evento.state) ? null : evento.state;
      return;
    }
    if (NON_VALIDI.has(evento.state) || evento.state === this._eventoVisto) return;
    this._eventoVisto = evento.state;
    if (Date.now() - new Date(evento.state).getTime() > 120000) return;

    const a = evento.attributes || {};
    const tipo = a.event_type;
    const motivo = MOTIVI[a.motivo] || a.motivo;
    const testi = {
      ostruzione: ["Ostacolo: la manovra si è fermata", "no"],
      errore_bluebus: ["Errore BlueBUS segnalato dal modulo", "no"],
      reset: ["La centrale si è riavviata", "no"],
      batteria: ["Batteria di un accessorio da controllare", "no"],
      posizione_rifiutata: [`Posizione rifiutata${motivo ? `: ${motivo}` : ""}`, "no"],
      posizione_interrotta: [`Movimento a posizione interrotto${motivo ? `: ${motivo}` : ""}`, "no"],
      riavvio_rifiutato: [`Riavvio rifiutato${motivo ? `: ${motivo}` : ""}`, "no"],
      riavvio_interfaccia: [a.esito === "rifiutato" ? "Il modulo ha rifiutato il riavvio" : "Riavvio dell'interfaccia in corso", a.esito === "rifiutato" ? "no" : "ok"],
    };
    if (testi[tipo]) this._messaggio(testi[tipo][0], testi[tipo][1]);
  }
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------
const SCHEMA_EDITOR = [
  { name: "entity", required: true, selector: { entity: { integration: "nexus_nice", domain: "sensor" } } },
  { name: "title", selector: { text: {} } },
];

class NexusNiceCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._aggiorna(); }
  set hass(hass) { this._hass = hass; this._aggiorna(); }

  _aggiorna() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = SCHEMA_EDITOR;
      this._form.computeLabel = (voce) => (voce.name === "entity" ? "Mappa del cancello" : "Titolo (facoltativo)");
      this._form.addEventListener("value-changed", (evento) => {
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: evento.detail.value }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
  }
}

// Registrazione idempotente e non fatale: un doppio caricamento non deve
// lanciare, e un errore qui non deve impedire l'avvio dell'interfaccia.
try {
  if (!customElements.get("nexus-nice-card")) {
    customElements.define("nexus-nice-card", NexusNiceCard);
    customElements.define("nexus-nice-card-editor", NexusNiceCardEditor);
    window.customCards = window.customCards || [];
    window.customCards.push({
      type: "nexus-nice-card",
      name: "Nexus Nice",
      description: "Cancello o porta da garage Nice collegati a Nexus-T: comandi, posizione in tempo reale e diagnostica.",
      preview: false,
      documentationURL: "https://github.com/Pacco24626/nexus_nice",
    });
    console.info(`%c NEXUS-NICE-CARD %c ${VERSIONE_CARD} `, "color:#fff;background:#2E9E6B;font-weight:700;", "color:#2E9E6B;background:#E6F4EC;font-weight:700;");
  }
} catch (errore) {
  console.error("Nexus Nice: registrazione della card non riuscita", errore);
}
