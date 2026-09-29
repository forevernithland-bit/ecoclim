// Entende exercícios digitados/falados em português livre:
//   "3x12 rosca scott 15kg, supino declinado e 20 min de esteira"
// → [{nome, slot, series, reps, kg, minutos, tipo}], com sugestões quando
// não reconhece. Tudo local (sem IA): rápido e grátis.
import { PADROES, linkVideo } from "./treino.js";
import { normalizar } from "./alimentos.js";

// Exercícios comuns de academia que não estão nos padrões do gerador,
// ligados ao músculo (slot) mais parecido — assim contam no volume semanal.
const EXTRA = [
  ["Rosca Scott", "biceps", ["scott", "rosca scott", "banco scott"]],
  ["Rosca 21", "biceps", ["rosca 21", "21"]],
  ["Rosca inversa", "biceps", ["rosca inversa", "rosca pronada"]],
  ["Rosca no cabo / polia", "biceps", ["rosca cabo", "rosca na polia", "rosca polia"]],
  ["Tríceps banco / mergulho", "triceps", ["triceps banco", "mergulho", "paralelas", "dips", "triceps mergulho"]],
  ["Tríceps pulley (barra)", "triceps", ["pulley", "triceps pulley", "triceps barra", "triceps na barra"]],
  ["Tríceps coice", "triceps", ["coice", "triceps coice", "kickback"]],
  ["Crucifixo", "supinoInc", ["crucifixo", "fly", "crucifixo reto"]],
  ["Crossover", "supinoInc", ["crossover", "cross over", "cross"]],
  ["Voador / peck deck", "supinoInc", ["voador", "peck deck", "peckdeck", "fly maquina"]],
  ["Supino declinado", "supino", ["supino declinado", "declinado"]],
  ["Flexão de braço", "supino", ["flexao", "flexoes", "apoio", "flexao de braco"]],
  ["Pulldown / puxada alta", "puxada", ["pulldown", "puxada alta", "puxada aberta", "puxada fechada", "puxada triangulo"]],
  ["Barra fixa", "puxada", ["barra fixa", "pull up", "pullup", "chin up", "graviton"]],
  ["Remada sentada na máquina", "remada", ["remada maquina", "remada sentada", "remada articulada", "low row"]],
  ["Serrote (remada unilateral)", "remada", ["serrote"]],
  ["Levantamento terra", "dobradica", ["terra", "levantamento terra", "deadlift", "terra convencional"]],
  ["Encolhimento (trapézio)", "remada", ["encolhimento", "trapezio", "shrug"]],
  ["Remada alta", "lateral", ["remada alta", "upright row"]],
  ["Elevação frontal", "desenvolvimento", ["elevacao frontal", "frontal"]],
  ["Crucifixo inverso", "posteriorOmbro", ["crucifixo inverso", "voador invertido", "peck deck inverso"]],
  ["Hack / agachamento na máquina", "agachamento", ["hack", "hack machine", "agachamento maquina"]],
  ["Agachamento sumô", "agachamento", ["sumo", "agachamento sumo"]],
  ["Afundo / passada", "extensora", ["afundo", "passada", "avanco", "lunge"]],
  ["Leg press", "agachamento", ["leg press", "leg", "legpress", "leg 45"]],
  ["Stiff", "dobradica", ["stiff", "rdl", "romeno"]],
  ["Cadeira abdutora", "gluteo", ["abdutora", "cadeira abdutora", "abducao"]],
  ["Cadeira adutora", "extensora", ["adutora", "cadeira adutora", "aducao"]],
  ["Glúteo 4 apoios / coice", "gluteo", ["gluteo 4 apoios", "quatro apoios", "coice gluteo", "gluteo no cabo"]],
  ["Hip thrust / elevação pélvica", "gluteo", ["hip thrust", "elevacao pelvica", "ponte"]],
  ["Panturrilha sentado", "panturrilha", ["panturrilha sentado", "gemeos", "soleo"]],
  ["Abdominal supra", "core", ["abdominal", "abdominal supra", "supra", "crunch"]],
  ["Abdominal infra", "core", ["infra", "abdominal infra", "elevacao de pernas"]],
  ["Abdominal oblíquo", "core", ["obliquo", "abdominal obliquo", "russian twist"]],
  ["Prancha lateral", "core", ["prancha lateral"]],
];

// Cardio / atividades por tempo (não entram no volume de musculação)
const CARDIO = [
  ["Esteira (caminhada)", ["esteira", "caminhada", "caminhar", "andar"]],
  ["Corrida", ["corrida", "correr", "corri", "trote", "run"]],
  ["Bicicleta", ["bike", "bicicleta", "ergometrica", "spinning", "pedal"]],
  ["Elíptico / transport", ["eliptico", "transport"]],
  ["Escada / simulador de escada", ["escada", "stair", "simulador de escada"]],
  ["Pular corda", ["corda", "pular corda"]],
  ["Natação", ["natacao", "nadar", "piscina"]],
  ["HIIT / funcional", ["hiit", "funcional", "circuito", "crossfit", "burpee", "polichinelo"]],
  ["Remo ergômetro", ["remo", "ergometro"]],
  ["Dança / zumba", ["zumba", "danca", "dancar", "ritmos"]],
  ["Lutas / boxe", ["boxe", "luta", "muay thai", "jiu jitsu", "kickboxing"]],
  ["Futebol / esporte", ["futebol", "bola", "volei", "basquete", "tenis", "beach tennis", "padel"]],
];

let CATALOGO = null;
function catalogo() {
  if (CATALOGO) return CATALOGO;
  const itens = [];
  const LIGA = new Set(["com", "na", "no", "de", "do", "da", "em"]);
  for (const [slot, pad] of Object.entries(PADROES)) {
    const nomes = new Set(Object.values(pad.v).flat());
    for (const nome of nomes) {
      const n = normalizar(nome);
      // também aceita as 2 primeiras palavras ("puxada frontal", "rosca direta")
      const duas = n.split(" ").filter((w) => !LIGA.has(w)).slice(0, 2).join(" ");
      itens.push({ nome, slot, tipo: "forca", chaves: [...new Set([n, duas])] });
    }
  }
  for (const [nome, slot, chaves] of EXTRA) itens.push({ nome, slot, tipo: "forca", chaves: chaves.map(normalizar) });
  for (const [nome, chaves] of CARDIO) itens.push({ nome, slot: null, tipo: "cardio", chaves: chaves.map(normalizar) });
  for (const it of itens) it.palavras = new Set(it.chaves.join(" ").split(" ").filter((w) => w.length > 2));
  CATALOGO = itens;
  return itens;
}

const VAZIAS = new Set("de da do com na no em e a o as os um uma series serie repeticoes repeticao reps rep vezes x kg quilos kilos min minutos minuto segundos seg km metros fiz fazer vou hoje depois tambem mais pra para cada lado".split(" "));
const palavrasDe = (t) => normalizar(t).replace(/\d+[.,]?\d*/g, " ").split(/[^a-z]+/).filter((w) => w.length > 2 && !VAZIAS.has(w));

// Distância de edição (pra aceitar erro de digitação: "tricps" ≈ "triceps")
function distancia(a, b) {
  if (Math.abs(a.length - b.length) > 2) return 9;
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  }
  return d[a.length][b.length];
}
const parecida = (w, p) => w === p || (w.length >= 5 && p.length >= 5 && (distancia(w, p) <= (w.length >= 8 ? 2 : 1) || p.startsWith(w) || w.startsWith(p)));

// Pontua o quanto o item explica o que foi digitado (0–1). Vale mais quem
// cobre TODAS as palavras da pessoa ("tríceps corda" → tríceps com corda,
// não "pular corda"); palavras sobrando no nome do catálogo pesam um pouco.
function pontuar(texto, item) {
  const ws = palavrasDe(texto);
  if (!ws.length) return 0;
  const t = ` ${normalizar(texto)} `;
  let melhor = 0;
  for (const ch of item.chaves) {
    if (t.includes(` ${ch} `) || t.includes(` ${ch}s `)) {
      const cobertas = ws.filter((w) => ch.split(" ").some((p) => parecida(w, p))).length;
      melhor = Math.max(melhor, 0.5 + 0.5 * (cobertas / ws.length));
    }
  }
  let bate = 0;
  for (const w of ws) if ([...item.palavras].some((p) => parecida(w, p))) bate += w.length >= 5 && !item.palavras.has(w) ? 0.85 : 1;
  const sobra = Math.max(0, item.palavras.size - bate);
  melhor = Math.max(melhor, (bate / ws.length) * 0.92 - 0.03 * sobra);
  return melhor;
}

function extrairNumeros(seg) {
  const t = normalizar(seg);
  const r = {};
  let m = t.match(/(\d+)\s*(?:x|×|\*)\s*(\d+(?:\s*(?:a|-|–)\s*\d+)?)/);
  if (m) { r.series = +m[1]; r.reps = m[2].replace(/\s*(a|-)\s*/, "–"); }
  m = t.match(/(\d+)\s*series?\s*(?:de)?\s*(\d+(?:\s*(?:a|-|–)\s*\d+)?)/);
  if (!r.series && m) { r.series = +m[1]; r.reps = m[2].replace(/\s*(a|-)\s*/, "–"); }
  m = t.match(/(\d+[.,]?\d*)\s*(kg|quilos?|kilos?)\b/);
  if (m) r.kg = parseFloat(m[1].replace(",", "."));
  m = t.match(/(\d+)\s*(min|minutos?)\b/);
  if (m) r.minutos = +m[1];
  m = t.match(/(\d+[.,]?\d*)\s*km\b/);
  if (m) r.km = parseFloat(m[1].replace(",", "."));
  return r;
}

// Interpreta o texto inteiro → lista de itens (reconhecidos ou com sugestões)
export function interpretarExercicios(texto) {
  const cat = catalogo();
  const partes = String(texto || "").split(/\n|;|,(?!\d)|\s+e\s+|\s+\+\s+/).map((s) => s.trim()).filter((s) => palavrasDe(s).length || /\d/.test(s));
  const itens = [];
  for (const seg of partes) {
    const nums = extrairNumeros(seg);
    const ranking = cat.map((it) => ({ it, p: pontuar(seg, it) })).filter((x) => x.p > 0.15).sort((a, b) => b.p - a.p);
    const top = ranking[0];
    const nomeDigitado = seg.replace(/\d+\s*(x|×)\s*\d+(\s*(a|-|–)\s*\d+)?/gi, "").replace(/\d+[.,]?\d*\s*(kg|quilos?|kilos?|min(utos?)?|km)\b/gi, "").replace(/\d+\s*s[ée]ries?\s*(de)?\s*\d*/gi, "").replace(/\s+/g, " ").trim();
    const sugestoes = ranking.slice(0, 4).map((x) => x.it);
    if (!palavrasDe(seg).length) continue; // só números soltos
    if (top && top.p >= 0.55) itens.push(montarItem(top.it, nums, seg, sugestoes.slice(1)));
    else itens.push({ reconhecido: false, digitado: nomeDigitado || seg, textoOriginal: seg, nums, sugestoes });
  }
  return itens;
}

export function montarItem(it, nums = {}, textoOriginal = "", outras = []) {
  const pad = it.slot ? PADROES[it.slot] : null;
  if (it.tipo === "cardio") {
    return {
      reconhecido: true, tipo: "cardio", nome: it.nome, slot: null, grupo: "Cardio", textoOriginal, outras,
      minutos: nums.minutos || 20, km: nums.km || null, series: 1, reps: `${nums.minutos || 20} min`, descanso: "0 s", rir: "–",
      dica: "Ritmo em que dá pra conversar, mas não cantar (zona 2) — ótimo pra queimar gordura sem atrapalhar o treino.",
      video: linkVideo(it.nome),
    };
  }
  return {
    reconhecido: true, tipo: "forca", nome: it.nome, slot: it.slot, grupo: pad ? pad.grupo : "Personalizado", textoOriginal, outras,
    series: nums.series || 3, reps: nums.reps || (pad && pad.composto ? "8–12" : "10–15"), kg: nums.kg || "",
    descanso: pad && pad.composto ? "2 min" : "75 s", rir: "1–2",
    dica: pad ? pad.dica : "Movimento controlado, amplitude completa, sem dar impulso.",
    video: linkVideo(it.nome), composto: pad ? pad.composto : false,
  };
}

// Item "do jeito que o usuário escreveu" (quando nada no catálogo serve)
export function itemPersonalizado(nome, nums = {}) {
  const cardio = /\b(min|minutos?)\b/i.test(nome) || nums.minutos;
  return {
    reconhecido: true, tipo: cardio && !nums.series ? "cardio" : "forca", nome: nome.charAt(0).toUpperCase() + nome.slice(1), slot: null,
    grupo: "Personalizado", series: nums.series || (cardio ? 1 : 3), reps: nums.reps || (cardio ? `${nums.minutos || 20} min` : "10–12"),
    kg: nums.kg || "", minutos: nums.minutos || null, descanso: cardio ? "0 s" : "75 s", rir: "1–2",
    dica: "Exercício personalizado.", video: linkVideo(nome), personalizado: true,
  };
}

// Converte o item interpretado pro formato de exercício do treino/sessão
export function paraExercicio(item) {
  return {
    slot: item.slot, nome: item.nome, original: item.nome, grupo: item.grupo, dica: item.dica, video: item.video,
    series: item.series, reps: item.reps, descanso: item.descanso, rir: item.rir, composto: !!item.composto,
    kgSugerido: item.kg || "", tipo: item.tipo, adicionado: true,
  };
}
