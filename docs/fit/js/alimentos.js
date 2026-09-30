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
      idx.push({ chave: ch, re: new RegExp(`(^|[^a-z0-9])(${escRe(ch)})(?:e?s)?(?=$|[^a-z0-9])`, "g"), item: it });
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
// Palavras de PREPARO/forma: descrevem o alimento, não são outro alimento
const DESCRITORES = new Set(("moido moida moidos desfiado desfiada picado picada cubos tiras fatiado fatiada ralado ralada " +
  "air fry fryer airfryer airfry forno panela pressao chapa brasa churrasqueira micro ondas microondas vapor " +
  "hamburguer hamburger burguer burger bife bifes almondega almondegas espeto espetinho file files posta medalhao " +
  "sem pele osso tempero temperado temperada azeite sal limao molho alho cebola caseiro caseira feito feita").split(" "));
// alimentos que, junto de uma carne no MESMO trecho, viram só a forma de preparo dela
const FORMAS_DE_CARNE = ["hamburguer", "burger", "almondega", "bife", "espeto", "espetinho", "carne moida", "moida"];

export function estimarLocal(texto) {
  // cada linha do texto é um trecho (a normalização juntaria tudo numa linha só)
  const linhas = String(texto || "").split(/\n+/).map((l) => normalizar(l)).filter(Boolean);
  let t = " " + linhas.join(" ; ")
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

  // --- Trechos: separados por linha, vírgula, ";", "+", " e ", " com " — mas
  // nunca no meio de um alimento reconhecido ("café com leite" é um só) ---
  const cortes = [0];
  const reSep = /[,;+]| e | com /g;
  let ms;
  while ((ms = reSep.exec(t))) if (!ocupado[ms.index + 1]) cortes.push(ms.index);
  cortes.push(t.length);
  const trechos = [];
  for (let k = 0; k + 1 < cortes.length; k++) trechos.push({ ini: cortes[k], fim: cortes[k + 1], texto: t.slice(cortes[k], cortes[k + 1]) });

  const monta = (item, gramas, extra = {}) => {
    const f = gramas / 100;
    return {
      nome: item.nome, quantidade: `${Math.round(gramas)} g`,
      kcal: Math.round(item.kcal * f), proteina: +(item.p * f).toFixed(1),
      carboidrato: +(item.c * f).toFixed(1), gordura: +(item.g * f).toFixed(1), fonte: item.fonte || "taco", ...extra,
    };
  };
  const gramasDe = (a, trechoAntes) => {
    const depois = t.slice(a.fim, a.fim + 12);
    const gDepois = depois.match(/^\s*(\d+[.,]?\d*)\s*(g|gr|gramas|ml)\b/);
    return gDepois ? parseFloat(gDepois[1].replace(",", ".")) : quantidadeGramas(trechoAntes, a.item);
  };
  const ehCarne = (it) => /carne|patinho|alcatra|picanha|frango|peito|porco|lombo|file|maminha|acem|musculo|costela|fraldinha|cupim|hamburguer bovino|peru|linguica/.test(normalizar(it.nome)) && !/lanchonete|x-/.test(normalizar(it.nome));
  const ehForma = (a) => FORMAS_DE_CARNE.some((f) => t.slice(a.ini, a.fim).includes(f)) || /lanchonete|almondega|hamburguer bovino/.test(normalizar(a.item.nome));

  const itens = [];
  const naoEncontrados = [];
  for (const tr of trechos) {
    const nesse = achados.filter((a) => a.ini >= tr.ini && a.fim <= tr.fim);
    if (!nesse.length) {
      // nenhum alimento conhecido nesse trecho → vai pra IA (sem palavras de preparo/quantidade)
      const resto = limparFragmento(tr.texto).split(" ").filter((w) => !DESCRITORES.has(w)).join(" ");
      if (resto.length >= 3) naoEncontrados.push(resto);
      continue;
    }
    const qtdExplicitas = (tr.texto.match(/\d+[.,]?\d*\s*(g|gr|gramas|ml|kg)?\b/g) || []).length;
    // Vários alimentos num trecho com UMA quantidade (ou nenhuma): é um alimento
    // só com descrição ("patinho moído hambúrguer na air fry"). Fica o principal
    // (a carne, se houver; senão o 1º) e a pessoa confirma.
    // mesmo alimento citado 2x ("bife de patinho" → bife = patinho): é um só, sem dúvida
    if (nesse.length > 1 && nesse.every((a) => a.item === nesse[0].item)) {
      itens.push(monta(nesse[0].item, quantidadeGramas(tr.texto, nesse[0].item)));
      continue;
    }
    if (nesse.length > 1 && qtdExplicitas <= 1) {
      // alimento "pronto" com porção própria (almôndega, hambúrguer bovino) vence a carne genérica
      const pronto = nesse.find((a) => /almondega|hamburguer bovino/.test(normalizar(a.item.nome)));
      const carne = nesse.find((a) => ehCarne(a.item));
      const principal = pronto || (carne && nesse.some((a) => a !== carne && ehForma(a)) ? carne : nesse[0]);
      const descricao = limparFragmento(tr.texto).split(" ").filter((w) => !normalizar(principal.item.nome).split(" ").includes(w)).join(" ");
      const gramas = quantidadeGramas(tr.texto, principal.item);
      const separados = nesse.map((a) => monta(a.item, gramasDe(a, t.slice(tr.ini, a.ini))));
      itens.push(monta(principal.item, gramas, {
        nome: descricao ? `${principal.item.nome} (${descricao})` : principal.item.nome,
        duvida: true, motivo: `Entendi "${tr.texto.trim()}" como um alimento só.`, separados,
      }));
      continue;
    }
    let inicio = tr.ini;
    for (const a of nesse) {
      itens.push(monta(a.item, gramasDe(a, t.slice(inicio, a.ini))));
      inicio = a.fim;
    }
  }

  const r = totalizar(itens, itens.length ? "Calculado pela tabela TACO." : "");
  r.naoEncontrados = [...new Set(naoEncontrados)];
  return r;
}

export function totalizar(itens, observacao = "") {
  const soma = (k) => Math.round(itens.reduce((s, i) => s + (Number(i[k]) || 0), 0) * 10) / 10;
  return { itens, kcal: Math.round(soma("kcal")), proteina: soma("proteina"), carboidrato: soma("carboidrato"), gordura: soma("gordura"), observacao };
}

export function tamanhoBase() { return BASE.length; }
