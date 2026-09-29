// Base de alimentos + leitor de refeições em texto.
//
// Ordem de busca (do mais barato pro mais caro):
//  1. Base TACO embarcada (data/alimentos.json — funciona offline)
//  2. Base do Supabase (fit_alimentos) — inclui o que a IA já aprendeu
//  3. Só o que não foi encontrado vai pra IA; a resposta dela é salva na base
//     (fonte = 'ia') pra próxima vez sair na hora e sem gastar crédito.
import { kvGet, kvSet } from "./db.js";

let BASE = [];          // [{nome, chaves[], kcal, p, c, g, porcao, unidade, fonte}]
let INDICE = [];        // [{chave, re, item}] ordenado da chave mais longa pra mais curta
let carregada = null;

export function normalizar(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim();
}
const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function montarIndice() {
  const porNome = new Map();
  for (const it of BASE) porNome.set(normalizar(it.nome), it); // último vence (Supabase/IA sobre o JSON)
  const itens = [...porNome.values()];
  const idx = [];
  for (const it of itens) {
    for (const ch of new Set([...(it.chaves || []), normalizar(it.nome)].map(normalizar))) {
      if (ch.length < 2) continue;
      idx.push({ chave: ch, re: new RegExp(`(^|[^a-z0-9])(${escRe(ch)})s?(?=$|[^a-z0-9])`, "g"), item: it });
    }
  }
  idx.sort((a, b) => b.chave.length - a.chave.length);
  INDICE = idx;
}

export async function carregarBase() {
  if (carregada) return carregada;
  carregada = (async () => {
    let json = [];
    try { json = (await (await fetch("./data/alimentos.json")).json()).alimentos || []; } catch (e) { /* offline no 1º uso */ }
    const doBanco = (await kvGet("alimentosDB", { lista: [] })).lista || [];
    const aprendidosLocal = (await kvGet("alimentosIA", [])) || [];
    BASE = [...json, ...doBanco, ...aprendidosLocal];
    montarIndice();
    return BASE.length;
  })();
  return carregada;
}

// Chamado pelo sync (nuvem.js) quando baixa a tabela fit_alimentos.
export async function atualizarBaseDoBanco(lista) {
  await kvSet("alimentosDB", { lista, em: Date.now() });
  carregada = null;
  await carregarBase();
}

// Guarda localmente o que a IA ensinou (e devolve o registro pra ir pro banco)
export async function aprenderDaIA(itemIA, textoOriginal) {
  const m = String(itemIA.quantidade || "").match(/(\d+[.,]?\d*)\s*(g|gr|gramas|ml)\b/i);
  const gramas = m ? parseFloat(m[1].replace(",", ".")) : 0;
  if (!gramas || !itemIA.nome || !(itemIA.kcal >= 0)) return null;
  const f = 100 / gramas;
  const chaves = [normalizar(itemIA.nome)];
  const txt = limparFragmento(textoOriginal || "");
  if (txt && txt.split(" ").length <= 4) chaves.push(txt);
  const novo = {
    nome: itemIA.nome, chaves: [...new Set(chaves)],
    kcal: Math.round(itemIA.kcal * f), p: +(itemIA.proteina * f).toFixed(1), c: +(itemIA.carboidrato * f).toFixed(1), g: +(itemIA.gordura * f).toFixed(1),
    porcao: Math.round(gramas), unidade: itemIA.quantidade.replace(/\(.*?\)/g, "").trim() || "porção", fonte: "ia",
  };
  const lista = (await kvGet("alimentosIA", [])) || [];
  if (!lista.some((x) => normalizar(x.nome) === normalizar(novo.nome))) {
    lista.push(novo);
    await kvSet("alimentosIA", lista);
    BASE.push(novo);
    montarIndice();
  }
  return novo;
}

// ---------- Leitor de texto ----------
const NUMEROS = { um: 1, uma: 1, dois: 2, duas: 2, tres: 3, quatro: 4, cinco: 5, seis: 6, sete: 7, oito: 8, dez: 10, meio: 0.5, meia: 0.5 };
const PALAVRAS_VAZIAS = new Set(("de do da dos das com e um uma o a os as no na nos nas em pra para por sem mais pouco pouquinho bastante muito " +
  "grande pequeno pequena medio media cheio cheia fundo raso rasa colher colheres sopa cha prato pratos concha conchas copo copos xicara xicaras " +
  "fatia fatias pedaco pedacos unidade unidades porcao porcoes lata latas pote potes scoop scoops dose doses taca tacas g gr gramas ml litro litros kg " +
  "um uma dois duas tres quatro cinco seis sete oito nove dez meio meia metade " +
  "cozido cozidos cozida cozidas frito fritos frita fritas assado assados assada assadas grelhado grelhados grelhada grelhadas " +
  "mexido mexidos refogado refogados refogada cru crua caseiro caseira quente gelado gelada natural pequenos grandes medios " +
  "colheresdesopa colheresdecha comi tomei bebi almocei jantei lanchei hoje ontem agora eu tambem ai que ja so metade inteiro inteira mais ou menos tipo acho umas uns " +
  "manha almoco janta jantar lanche ceia refeicao").split(" "));
const ALIAS_CAFE_MANHA = /cafe da manha/g;

function limparFragmento(s) {
  return normalizar(s).replace(/\d+[.,]?\d*/g, " ").split(/[^a-z]+/).filter((w) => w.length > 1 && !PALAVRAS_VAZIAS.has(w)).join(" ").trim();
}

function quantidadeGramas(trecho, item) {
  const t = trecho;
  const mg = t.match(/(\d+[.,]?\d*)\s*(g|gr|gramas|ml)\b/);
  if (mg) return parseFloat(mg[1].replace(",", "."));
  const mkg = t.match(/(\d+[.,]?\d*)\s*(kg|l|litros?)\b/);
  if (mkg) return parseFloat(mkg[1].replace(",", ".")) * 1000;
  let qtd = 1;
  const mn = t.match(/(\d+[.,]?\d*)\s*[a-z]*\s*$/) || t.match(/(\d+[.,]?\d*)/);
  if (mn) qtd = parseFloat(mn[1].replace(",", "."));
  else {
    const palavras = t.split(/\s+/).filter(Boolean);
    for (let i = palavras.length - 1; i >= 0; i--) if (NUMEROS[palavras[i]] != null) { qtd = NUMEROS[palavras[i]]; break; }
  }
  if (/colheresdesopa/.test(t)) return 15 * qtd;
  if (/colheresdecha/.test(t)) return 5 * qtd;
  let fator = 1;
  if (/prato (fundo|cheio)/.test(t)) fator = 1.6;
  else if (/prato/.test(t) && !/prato/.test(item.unidade || "")) fator = 1.2;
  else if (/(concha|escumadeira) cheia/.test(t)) fator = 1.3;
  else if (/(pouco|pouquinho|metade)/.test(t)) fator = 0.6;
  else if (/(grande|bastante|cheio)/.test(t)) fator = 1.5;
  else if (/(pequen)/.test(t)) fator = 0.7;
  return item.porcao * qtd * fator;
}

// "2 ovos mexidos, 150g de frango e café com leite" →
//   { itens: [...], naoEncontrados: ["..."] , kcal, proteina, ... }
export function estimarLocal(texto) {
  let t = " " + normalizar(texto)
    .replace(ALIAS_CAFE_MANHA, " ")
    // medidas caseiras viram uma palavra só (senão "colher de SOPA" vira sopa, "de CHA" vira chá)
    .replace(/colher(es)? de sopa/g, "colheresdesopa").replace(/colher(es)? de cha/g, "colheresdecha")
    // plurais irregulares: pães→pão, pastéis→pastel, limões→limão
    .replace(/\b([a-z]+)aes\b/g, "$1ao").replace(/\b([a-z]+)oes\b/g, "$1ao").replace(/\b([a-z]+)eis\b/g, (m, r) => (m === "seis" ? m : `${r}el`)) + " ";
  const ocupado = new Array(t.length).fill(false);
  const achados = [];
  for (const { re, item } of INDICE) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(t))) {
      const ini = m.index + m[1].length, fim = ini + m[2].length;
      let livre = true;
      for (let k = ini; k < fim; k++) if (ocupado[k]) { livre = false; break; }
      if (!livre) continue;
      for (let k = ini; k < fim; k++) ocupado[k] = true;
      achados.push({ ini, fim, item });
    }
  }
  achados.sort((a, b) => a.ini - b.ini);

  const itens = [];
  let fimAnterior = 0;
  for (const a of achados) {
    // quantidade: texto entre o separador anterior e o alimento
    let trecho = t.slice(fimAnterior, a.ini);
    const sep = Math.max(trecho.lastIndexOf(","), trecho.lastIndexOf(";"), trecho.lastIndexOf("+"), trecho.lastIndexOf(" e "), trecho.lastIndexOf("\n"));
    if (sep >= 0) trecho = trecho.slice(sep + 1);
    // "150g de frango" ou "frango 150g"
    const depois = t.slice(a.fim, a.fim + 12);
    const gDepois = depois.match(/^\s*(\d+[.,]?\d*)\s*(g|gr|gramas|ml)\b/);
    const gramas = gDepois ? parseFloat(gDepois[1].replace(",", ".")) : quantidadeGramas(trecho, a.item);
    const f = gramas / 100;
    itens.push({
      nome: a.item.nome, quantidade: `${Math.round(gramas)} g`,
      kcal: Math.round(a.item.kcal * f), proteina: +(a.item.p * f).toFixed(1),
      carboidrato: +(a.item.c * f).toFixed(1), gordura: +(a.item.g * f).toFixed(1), fonte: a.item.fonte || "taco",
    });
    fimAnterior = a.fim;
  }

  // O que sobrou do texto (sem alimentos reconhecidos nem palavras de quantidade)
  let resto = "";
  for (let k = 0; k < t.length; k++) resto += ocupado[k] ? "|" : t[k];
  const naoEncontrados = resto.split(/[|,;+\n]| e /).map(limparFragmento).filter((x) => x.length >= 3);

  const r = totalizar(itens, itens.length ? "Calculado pela tabela TACO." : "");
  r.naoEncontrados = [...new Set(naoEncontrados)];
  return r;
}

export function totalizar(itens, observacao = "") {
  const soma = (k) => Math.round(itens.reduce((s, i) => s + (Number(i[k]) || 0), 0) * 10) / 10;
  return { itens, kcal: Math.round(soma("kcal")), proteina: soma("proteina"), carboidrato: soma("carboidrato"), gordura: soma("gordura"), observacao };
}

export function tamanhoBase() { return BASE.length; }
