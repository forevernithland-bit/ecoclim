// "Analista de nutrição" local: lê as refeições registradas e percebe padrões
// (grupos de alimentos, macros, distribuição da proteína) → dicas que ENSINAM,
// cada uma com o "porquê". Vitaminas/minerais são estimados pelos grupos de
// alimentos (método do Guia Alimentar Brasileiro), não por miligrama.
// Também monta sugestões pra "fechar o dia" com o que falta de calorias/proteína.
import { normalizar } from "./alimentos.js";
import { todos, hojeISO } from "./db.js";

const GRUPOS = {
  fruta: ["banana", "maca", "laranja", "mexerica", "tangerina", "mamao", "manga", "abacaxi", "melancia", "melao", "uva", "morango", "abacate", "kiwi", "goiaba", "maracuja", "pessego", "ameixa", "caqui", "pera", "salada de frutas", "acai puro", "fruta"],
  verdura: ["salada", "alface", "rucula", "agriao", "tomate", "pepino", "cenoura", "brocolis", "couve", "abobrinha", "abobora", "chuchu", "vagem", "berinjela", "beterraba", "legume", "repolho", "pimentao", "quiabo", "palmito", "cogumelo", "espinafre", "sopa de legumes", "vinagrete", "verdura"],
  leguminosa: ["feijao", "lentilha", "grao de bico", "grao-de-bico", "ervilha", "soja", "tofu", "homus", "feijoada", "tropeiro", "baiao"],
  integral: ["integral", "aveia", "chia", "linhaca", "granola", "quinoa"],
  peixe: ["peixe", "tilapia", "salmao", "atum", "sardinha", "camarao", "bacalhau", "moqueca", "sushi", "sashimi", "temaki", "merluza", "pescada"],
  laticinio: ["leite", "iogurte", "queijo", "requeijao", "cottage", "ricota", "coalho", "mussarela", "mucarela", "minas"],
  oleaginosa: ["castanha", "amendoa", "nozes", "amendoim", "pasta de amendoim", "mix de nuts"],
  embutido: ["linguica", "calabresa", "salsicha", "presunto", "mortadela", "salame", "bacon", "peito de peru", "nugget"],
  frito: ["frito", "frita", "fritas", "coxinha", "pastel", "kibe", "quibe", "empada", "enroladinho", "churros", "milanesa", "acaraje", "donut", "polenta frita", "mandioca frita", "batata palha"],
  doce: ["refrigerante comum", "biscoito recheado", "bolo", "chocolate", "bombom", "brigadeiro", "beijinho", "sorvete", "pudim", "mousse", "acucar", "leite condensado", "cereal matinal", "doce de leite", "goiabada", "pacoca", "achocolatado", "suco de caixinha", "energetico", "picole", "churros", "donut", "gelatina"],
  alcool: ["cerveja", "chopp", "chope", "vinho", "caipirinha", "destilado", "cachaca", "vodka", "whisky"],
  carneVermelha: ["patinho", "alcatra", "picanha", "costela", "cupim", "fraldinha", "carne", "bife", "figado", "hamburguer", "almondega"],
};
const EXCECOES = { verdura: ["molho de tomate", "ketchup"], laticinio: ["whey", "leite condensado", "creme de leite", "doce de leite"], doce: ["refrigerante zero"] };

export function gruposDoAlimento(nome) {
  const n = ` ${normalizar(nome)} `;
  const g = new Set();
  for (const [grupo, chaves] of Object.entries(GRUPOS)) {
    if ((EXCECOES[grupo] || []).some((x) => n.includes(x))) continue;
    if (chaves.some((c) => n.includes(c))) g.add(grupo);
  }
  if (g.has("frito")) g.delete("verdura");
  return g;
}

const somarDias = (iso, n) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() + n); return hojeISO(d); };

// Analisa os últimos N dias com refeições registradas
export async function analisarAlimentacao(perfil, metas, { dias = 7 } = {}) {
  const hoje = hojeISO();
  const ini = somarDias(hoje, -(dias - 1));
  const refs = (await todos("refeicoes")).filter((r) => r.data >= ini && r.data <= hoje);
  const datas = [...new Set(refs.map((r) => r.data))];
  const nDias = datas.length;
  if (!nDias) return { nDias: 0, insights: [] };

  const diasCom = {}; const porcoes = {};
  for (const g of Object.keys(GRUPOS)) { diasCom[g] = new Set(); porcoes[g] = 0; }
  let kcal = 0, p = 0, c = 0, g = 0;
  const refeicoesComProt = [];
  for (const r of refs) {
    kcal += r.kcal || 0; p += r.proteina || 0; c += r.carboidrato || 0; g += r.gordura || 0;
    refeicoesComProt.push({ tipo: r.tipo, prot: r.proteina || 0, data: r.data });
    for (const it of r.itens || []) for (const gr of gruposDoAlimento(it.nome)) { diasCom[gr].add(r.data); porcoes[gr]++; }
  }
  const pctGord = kcal ? (g * 9) / kcal : 0;
  const pctCarb = kcal ? (c * 4) / kcal : 0;
  const d = (gr) => diasCom[gr].size;
  const fracao = (gr) => d(gr) / nDias;
  const nao = (perfil.naoGosta || []).map(normalizar);
  const evita = (x) => nao.some((n) => normalizar(x).includes(n) || n.includes(normalizar(x)));
  const veg = (perfil.dietas || []).some((x) => x === "vegetariano" || x === "vegano");
  const semLactose = (perfil.dietas || []).includes("sem_lactose") || (perfil.dietas || []).includes("vegano");
  const ins = [];
  const add = (o) => ins.push(o);

  // --- Grupos de alimentos → vitaminas/minerais prováveis ---
  if (fracao("fruta") < 0.5) add({
    id: "fruta", nivel: "alerta", emoji: "🍊", titulo: "Pouca fruta = provavelmente pouca vitamina C e fibra",
    texto: `Fruta apareceu em ${d("fruta")} de ${nDias} dias.`,
    acao: `Meta simples: 2 frutas por dia. ${["laranja", "kiwi", "goiaba", "morango"].filter((x) => !evita(x)).slice(0, 2).join(" e ")} são campeãs de vitamina C.`,
    porque: "Vitamina C ajuda na imunidade e na absorção do ferro; as fibras das frutas dão saciedade (ajuda muito no déficit) e fazem bem pro intestino.",
  });
  if (fracao("verdura") < 0.6) add({
    id: "verdura", nivel: "alerta", emoji: "🥦", titulo: "Poucas verduras e legumes = pouca vitamina A, K, folato, potássio e magnésio",
    texto: `Verduras/legumes em ${d("verdura")} de ${nDias} dias.`,
    acao: "Coloque metade do prato do almoço e do jantar com salada ou legumes — quase não tem caloria e enche.",
    porque: "Folhas verde-escuras e legumes coloridos trazem vitaminas A e K, folato, magnésio e potássio (este ajuda a controlar a pressão e a cãibra no treino).",
  });
  if (d("leguminosa") < Math.min(3, nDias) && !evita("feijao")) add({
    id: "leguminosa", nivel: "dica", emoji: "🫘", titulo: "Pouco feijão/lentilha = menos fibra, ferro e magnésio",
    texto: `Leguminosas em ${d("leguminosa")} de ${nDias} dias.`,
    acao: "Uma concha de feijão por dia já faz diferença (e ainda soma ~5 g de proteína).",
    porque: "O arroz com feijão é uma das combinações mais completas que existem: fibras, ferro, magnésio e proteína de boa qualidade quando juntos.",
  });
  if (nDias >= 5 && d("peixe") === 0 && !veg) add({
    id: "peixe", nivel: "dica", emoji: "🐟", titulo: "Sem peixe na semana = provavelmente pouco ômega-3",
    texto: "Nenhum peixe registrado nos últimos dias.",
    acao: evita("peixe") ? "Como você não gosta de peixe, vale conversar com a Nina sobre ômega-3 em cápsula (EPA+DHA) ou linhaça/chia/nozes." : "2 porções de peixe por semana (sardinha e atum em lata são baratos e práticos).",
    porque: "Ômega-3 (EPA/DHA) protege coração e articulações e reduz inflamação — importante pra quem treina.",
  });
  if (fracao("laticinio") < 0.4 && !semLactose) add({
    id: "laticinio", nivel: "dica", emoji: "🥛", titulo: "Poucos laticínios = cálcio provavelmente baixo",
    texto: `Leite, iogurte ou queijo em ${d("laticinio")} de ${nDias} dias.`,
    acao: "1 iogurte (de preferência natural ou proteico) + 1 fatia de queijo branco por dia resolvem boa parte do cálcio.",
    porque: "Cálcio é essencial pros ossos e pra contração muscular; iogurte ainda soma proteína de alta qualidade.",
  });
  if (veg) add({
    id: "b12", nivel: "dica", emoji: "💊", titulo: "Alimentação vegetariana/vegana: atenção à vitamina B12",
    texto: "A B12 praticamente só existe em alimentos de origem animal.",
    acao: "Converse com seu médico sobre exame e suplementação de B12.",
    porque: "Falta de B12 causa cansaço, anemia e problemas neurológicos com o tempo.",
  });
  if (d("carneVermelha") === 0 && d("leguminosa") < 2 && nDias >= 4 && !veg) add({
    id: "ferro", nivel: "dica", emoji: "🩸", titulo: "Ferro pode estar baixo",
    texto: "Pouca carne vermelha e pouco feijão nos últimos dias.",
    acao: "Inclua carne magra 2–3x na semana ou feijão/lentilha todo dia (com uma fruta cítrica junto pra absorver melhor).",
    porque: "Ferro transporta oxigênio pro músculo — com ele baixo, o treino rende menos e o cansaço aparece.",
  });

  // --- Excessos ---
  if (pctGord > 0.36) add({
    id: "gordura", nivel: "alerta", emoji: "🧈", titulo: `Gordura alta: ${Math.round(pctGord * 100)}% das calorias (ideal 20–35%)`,
    texto: `Média de ${Math.round(g / nDias)} g/dia de gordura (meta ~${metas.gord} g).`,
    acao: d("frito") ? "Troque frituras por assado/grelhado/air fryer e meça o óleo com colher (1 colher de sopa = 90 kcal)." : "Meça azeite/óleo com colher e prefira carnes magras (patinho, frango, peixe).",
    porque: "Gordura tem 9 kcal por grama (mais que o dobro de proteína e carboidrato). É fácil passar da meta sem perceber — e sobra menos espaço pra proteína.",
  });
  if (porcoes.frito / nDias >= 0.7) add({
    id: "frito", nivel: "alerta", emoji: "🍟", titulo: "Frituras frequentes",
    texto: `${porcoes.frito} itens fritos em ${nDias} dias.`,
    acao: "Deixe fritura pra 1–2x na semana. Air fryer ou forno dão a mesma crocância com bem menos óleo.",
    porque: "Frituras somam muitas calorias vazias e gordura de baixa qualidade, e atrapalham o déficit.",
  });
  if (porcoes.embutido / nDias >= 0.6) add({
    id: "sodio", nivel: "alerta", emoji: "🧂", titulo: "Muitos embutidos = sódio provavelmente alto",
    texto: `Presunto, salsicha, linguiça, bacon etc. em ${d("embutido")} dias.`,
    acao: "Troque por frango desfiado, ovo ou queijo branco no lanche.",
    porque: "Embutidos têm muito sal e conservantes; o excesso de sódio retém líquido (a balança engana) e pesa na pressão.",
  });
  if (porcoes.doce / nDias >= 1) add({
    id: "acucar", nivel: "alerta", emoji: "🍬", titulo: "Açúcar e doces todos os dias",
    texto: `${porcoes.doce} itens doces/açucarados em ${nDias} dias.`,
    acao: "Refrigerante → versão zero ou água com gás e limão; doce → 1x ao dia, depois do almoço, em porção pequena.",
    porque: "Açúcar líquido não dá saciedade e soma calorias rápido; doce todo dia treina o cérebro a pedir mais.",
  });
  if (porcoes.alcool >= 3) add({
    id: "alcool", nivel: "alerta", emoji: "🍺", titulo: "Álcool atrapalhando o resultado",
    texto: `${porcoes.alcool} registros de bebida alcoólica em ${nDias} dias.`,
    acao: "Defina um limite (ex.: só no sábado) e intercale com água. Cerveja zero e drinks sem açúcar ajudam.",
    porque: "Álcool tem 7 kcal/g, abre o apetite e reduz a síntese de músculo e a qualidade do sono.",
  });

  // --- Proteína: quantidade e distribuição ---
  const protDia = p / nDias;
  if (protDia < metas.prot * 0.85) {
    add({
      id: "proteina", nivel: "alerta", emoji: "🥩", titulo: `Proteína abaixo da meta (${Math.round(protDia)} de ${metas.prot} g/dia)`,
      texto: "É o nutriente mais importante pro seu objetivo.",
      acao: "Garanta uma fonte de proteína em TODA refeição: ovos no café, carne/frango no almoço e jantar, iogurte/whey no lanche.",
      porque: "Em déficit, proteína alta é o que impede o corpo de usar músculo como energia — e é o tijolo pro braço crescer.",
    });
  }
  const principais = refeicoesComProt.filter((r) => ["cafe", "almoco", "jantar"].includes(r.tipo));
  const cafes = refeicoesComProt.filter((r) => r.tipo === "cafe");
  if (cafes.length >= 3 && cafes.filter((r) => r.prot < 20).length / cafes.length > 0.6) add({
    id: "cafe", nivel: "dica", emoji: "🍳", titulo: "Café da manhã fraco em proteína",
    texto: `Na maioria dos dias o café da manhã teve menos de 20 g de proteína.`,
    acao: "3 ovos mexidos ou iogurte proteico + aveia já passam de 20 g.",
    porque: "O músculo responde melhor com ~25–40 g de proteína espalhados em 3–5 refeições do que com tudo concentrado no jantar (Schoenfeld & Aragon 2018).",
  });
  else if (principais.length >= 5 && principais.filter((r) => r.prot < 20).length / principais.length > 0.5) add({
    id: "distribuicao", nivel: "dica", emoji: "⏰", titulo: "Proteína mal distribuída ao longo do dia",
    texto: "Muitas refeições principais com menos de 20 g de proteína.",
    acao: "Tente ~30 g em cada refeição principal (ex.: 1 filé de frango, 1 lata de atum, 4 ovos).",
    porque: "Espalhar a proteína estimula a construção de músculo várias vezes ao dia.",
  });

  // --- Elogios (ensinar também é reforçar o que está bom) ---
  if (fracao("fruta") >= 0.8 && fracao("verdura") >= 0.8) add({ id: "ok-veg", nivel: "bom", emoji: "🌈", titulo: "Frutas e verduras em dia!", texto: "Vitaminas e fibras bem cobertas.", acao: "Continue variando as cores do prato.", porque: "Cada cor traz nutrientes diferentes (licopeno, betacaroteno, flavonoides…)." });
  if (protDia >= metas.prot * 0.95) add({ id: "ok-prot", nivel: "bom", emoji: "💪", titulo: "Proteína batendo a meta", texto: `Média de ${Math.round(protDia)} g/dia.`, acao: "É isso que protege e constrói músculo.", porque: "Proteína suficiente + treino = recomposição acontecendo." });
  if (pctGord >= 0.2 && pctGord <= 0.33 && nDias >= 3) add({ id: "ok-gord", nivel: "bom", emoji: "✅", titulo: "Gordura na medida certa", texto: `${Math.round(pctGord * 100)}% das calorias.`, acao: "Prefira azeite, castanhas, abacate e peixe como fontes.", porque: "Gordura boa é necessária pros hormônios (inclusive testosterona)." });

  const ordem = { alerta: 0, dica: 1, bom: 2 };
  ins.sort((a, b) => ordem[a.nivel] - ordem[b.nivel]);
  return { nDias, insights: ins, pctGord, pctCarb, protDia };
}

// ---------- "O que como pra fechar o dia?" (sem IA) ----------
const PROTEINAS = [
  { nome: "Peito de frango grelhado", k: 1.59, p: 0.32, c: 0, g: 0.025, max: 220, animal: true },
  { nome: "Patinho grelhado", k: 2.19, p: 0.36, c: 0, g: 0.073, max: 200, animal: true },
  { nome: "Ovos", k: 1.46, p: 0.133, c: 0.006, g: 0.095, max: 200, un: 50, unNome: "ovo", plural: "ovos", animal: true, ovo: true },
  { nome: "Atum em lata (água)", k: 1.16, p: 0.255, c: 0, g: 0.008, max: 160, animal: true, peixe: true },
  { nome: "Tilápia grelhada", k: 1.28, p: 0.26, c: 0, g: 0.027, max: 220, animal: true, peixe: true },
  { nome: "Iogurte proteico", k: 0.7, p: 0.1, c: 0.05, g: 0.008, max: 320, un: 160, unNome: "pote de iogurte proteico", plural: "potes de iogurte proteico", animal: true, lacteo: true },
  { nome: "Whey protein", k: 3.9, p: 0.78, c: 0.08, g: 0.06, max: 60, un: 30, unNome: "scoop de whey", plural: "scoops de whey", animal: true, lacteo: true },
  { nome: "Queijo cottage", k: 0.98, p: 0.11, c: 0.034, g: 0.043, max: 200, animal: true, lacteo: true },
  { nome: "Tofu", k: 0.76, p: 0.08, c: 0.019, g: 0.048, max: 300 },
  { nome: "Lentilha cozida", k: 0.93, p: 0.063, c: 0.163, g: 0.005, max: 300 },
];
const CARBOS = [
  { nome: "Arroz branco", k: 1.28, p: 0.025, c: 0.281, g: 0.002, max: 300 },
  { nome: "Batata-doce", k: 0.77, p: 0.006, c: 0.184, g: 0.001, max: 350 },
  { nome: "Pão francês", k: 3.0, p: 0.08, c: 0.586, g: 0.031, un: 50, unNome: "pão francês", plural: "pães franceses", max: 100 },
  { nome: "Tapioca", k: 2.4, p: 0, c: 0.6, g: 0, un: 60, unNome: "tapioca", plural: "tapiocas", max: 120 },
  { nome: "Banana", k: 0.98, p: 0.013, c: 0.26, g: 0.001, un: 90, unNome: "banana", plural: "bananas", max: 180 },
  { nome: "Aveia", k: 3.94, p: 0.139, c: 0.666, g: 0.085, max: 80 },
  { nome: "Macarrão", k: 1.58, p: 0.058, c: 0.309, g: 0.009, max: 300 },
];

function descreve(item, gramas) {
  if (item.un) {
    const n = Math.max(1, Math.round(gramas / item.un));
    return `${n} ${n > 1 ? item.plural || `${item.unNome}s` : item.unNome}`;
  }
  return `${Math.round(gramas / 10) * 10} g de ${item.nome.toLowerCase()}`;
}

export function sugerirFecharDia(perfil, restante) {
  const nao = (perfil.naoGosta || []).map(normalizar);
  const dietas = perfil.dietas || [];
  const ok = (x) => !nao.some((n) => normalizar(x.nome).includes(n) || (x.ovo && n.includes("ovo")) || (x.peixe && n.includes("peixe")))
    && !((dietas.includes("vegetariano") && x.animal && !x.ovo && !x.lacteo))
    && !(dietas.includes("vegano") && x.animal)
    && !(dietas.includes("sem_lactose") && x.lacteo);
  const R = Math.max(0, restante.kcal), P = Math.max(0, restante.prot);
  if (R < 120 && P < 10) return { fechado: true, opcoes: [] };
  const hora = new Date().getHours();
  const momento = hora < 10 ? "no café da manhã" : hora < 15 ? "no almoço" : hora < 18 ? "no lanche" : hora < 22 ? "no jantar" : "na ceia";
  const provs = PROTEINAS.filter(ok);
  const carbs = CARBOS.filter(ok);
  const opcoes = [];
  for (const pr of P >= 15 ? provs : []) {
    if (opcoes.length >= 3) break;
    // proteína cobre ~90% do que falta (sem passar do limite do alimento nem das calorias)
    let gp = Math.min(pr.max, (P * 0.9) / pr.p, (R * 0.75) / pr.k);
    if (gp < 30) continue;
    const kp = gp * pr.k;
    let texto = [descreve(pr, gp)];
    let tot = { k: kp, p: gp * pr.p, c: gp * pr.c, g: gp * pr.g };
    const sobra = R - kp;
    if (sobra > 90 && carbs.length) {
      const ca = carbs[opcoes.length % carbs.length];
      const gc = Math.min(ca.max || 300, sobra / ca.k);
      texto.push(descreve(ca, gc));
      tot = { k: tot.k + gc * ca.k, p: tot.p + gc * ca.p, c: tot.c + gc * ca.c, g: tot.g + gc * ca.g };
    }
    // ainda sobrando bastante? completa com fruta (+ fonte de gordura boa se for muito)
    if (R - tot.k > 150) { texto.push("1 fruta"); tot.k += 70; tot.c += 17; }
    if (R - tot.k > 250) { texto.push("1 punhado de castanhas"); tot.k += 180; tot.g += 16; tot.p += 5; }
    if (R > 400) texto.push("salada/legumes à vontade");
    opcoes.push({ itens: texto, kcal: Math.round(tot.k), prot: Math.round(tot.p), carb: Math.round(tot.c), gord: Math.round(tot.g) });
  }
  // Proteína já batida, mas ainda sobram calorias: carboidrato + fruta
  if (!opcoes.length && R >= 120) {
    for (const ca of carbs.slice(0, 3)) {
      const gc = Math.min(ca.max || 300, (R * 0.8) / ca.k);
      opcoes.push({ itens: [descreve(ca, gc), "1 fruta"], kcal: Math.round(gc * ca.k + 60), prot: Math.round(gc * ca.p), carb: Math.round(gc * ca.c + 15), gord: Math.round(gc * ca.g) });
    }
  }
  return { fechado: false, momento, opcoes, restante: { kcal: Math.round(R), prot: Math.round(P) } };
}
