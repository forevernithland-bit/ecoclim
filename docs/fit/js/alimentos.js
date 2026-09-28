// Base local de alimentos comuns no Brasil (valores por 100 g, arredondados da
// Tabela TACO/UNICAMP e rótulos médios). Serve de "plano B" quando a IA não
// está disponível (sem internet ou backend fora) — o texto digitado ou falado
// é quebrado em itens e somado aqui. Com a IA ligada, a análise é dela.
//
// porcao = quantos gramas tem "1 unidade/porção" quando a pessoa não diz o peso.
const A = (nome, chaves, kcal, p, c, g, porcao, unidade = "porção") => ({ nome, chaves, kcal, p, c, g, porcao, unidade });

export const ALIMENTOS = [
  A("Arroz branco cozido", ["arroz"], 128, 2.5, 28, 0.2, 150, "escumadeira cheia"),
  A("Arroz integral cozido", ["arroz integral"], 124, 2.6, 26, 1, 150, "escumadeira cheia"),
  A("Feijão cozido", ["feijao", "feijão", "feijoada"], 77, 4.8, 14, 0.5, 140, "concha"),
  A("Macarrão cozido", ["macarrao", "macarrão", "espaguete", "massa", "lasanha"], 158, 5.8, 31, 0.9, 200, "prato raso"),
  A("Batata cozida", ["batata"], 52, 1.2, 12, 0.1, 150, "unidade média"),
  A("Batata frita", ["batata frita", "fritas"], 312, 3.4, 41, 15, 120, "porção pequena"),
  A("Batata-doce cozida", ["batata doce", "batata-doce"], 77, 0.6, 18, 0.1, 150, "unidade média"),
  A("Mandioca cozida", ["mandioca", "aipim", "macaxeira"], 125, 0.6, 30, 0.3, 150, "pedaço"),
  A("Farofa", ["farofa"], 406, 2.1, 80, 9, 30, "colher de sopa cheia"),
  A("Cuscuz de milho", ["cuscuz"], 113, 2.2, 25, 0.7, 150, "fatia"),
  A("Tapioca (massa)", ["tapioca"], 240, 0, 60, 0, 60, "unidade"),
  A("Pão francês", ["pao frances", "pão francês", "pao", "pão", "pãozinho", "paozinho"], 300, 8, 58, 3.1, 50, "unidade"),
  A("Pão de forma", ["pao de forma", "pão de forma", "torrada"], 253, 12, 44, 2.7, 25, "fatia"),
  A("Pão de queijo", ["pao de queijo", "pão de queijo"], 363, 5.1, 34, 24, 40, "unidade média"),
  A("Aveia em flocos", ["aveia"], 394, 14, 67, 8.5, 30, "3 colheres de sopa"),
  A("Granola", ["granola"], 420, 9, 66, 14, 40, "porção"),
  A("Peito de frango grelhado", ["frango", "peito de frango", "file de frango", "filé de frango"], 159, 32, 0, 2.5, 120, "filé"),
  A("Coxa de frango assada", ["coxa", "sobrecoxa"], 215, 27, 0, 11, 100, "unidade"),
  A("Carne bovina magra (patinho)", ["patinho", "carne moida", "carne moída", "bife", "carne"], 219, 36, 0, 7.3, 120, "bife"),
  A("Picanha / carne gorda", ["picanha", "costela", "cupim", "fraldinha", "churrasco"], 289, 26, 0, 20, 150, "porção"),
  A("Carne de porco (lombo)", ["porco", "lombo", "bisteca"], 210, 32, 0, 8, 120, "bife"),
  A("Linguiça", ["linguica", "linguiça", "salsicha"], 296, 16, 1, 25, 60, "gomo"),
  A("Peixe (tilápia grelhada)", ["peixe", "tilapia", "tilápia", "merluza"], 128, 26, 0, 2.7, 120, "filé"),
  A("Salmão grelhado", ["salmao", "salmão"], 243, 26, 0, 15, 120, "posta"),
  A("Atum em água", ["atum"], 116, 26, 0, 1, 80, "lata drenada"),
  A("Ovo cozido/mexido", ["ovo", "ovos", "omelete"], 146, 13, 0.6, 9.5, 50, "unidade"),
  A("Queijo muçarela", ["mussarela", "muçarela", "queijo"], 330, 23, 3, 25, 20, "fatia"),
  A("Queijo minas frescal", ["minas", "frescal", "queijo branco"], 264, 17, 3.2, 20, 30, "fatia"),
  A("Requeijão", ["requeijao", "requeijão"], 257, 9.6, 2.4, 23, 30, "colher de sopa"),
  A("Presunto", ["presunto", "peito de peru"], 110, 17, 2, 4, 15, "fatia"),
  A("Leite integral", ["leite"], 61, 3.2, 4.7, 3.3, 200, "copo"),
  A("Leite desnatado", ["leite desnatado"], 35, 3.4, 5, 0.1, 200, "copo"),
  A("Iogurte natural", ["iogurte"], 61, 4, 5, 3, 170, "pote"),
  A("Iogurte grego", ["grego"], 120, 5, 9, 7, 100, "pote"),
  A("Whey protein", ["whey"], 390, 78, 8, 6, 30, "scoop"),
  A("Banana", ["banana"], 98, 1.3, 26, 0.1, 90, "unidade"),
  A("Maçã", ["maca", "maçã"], 56, 0.3, 15, 0, 130, "unidade"),
  A("Laranja", ["laranja", "mexerica", "tangerina"], 46, 1, 11, 0.1, 150, "unidade"),
  A("Mamão", ["mamao", "mamão"], 40, 0.5, 10, 0.1, 150, "fatia"),
  A("Manga", ["manga"], 64, 0.4, 17, 0.3, 150, "unidade pequena"),
  A("Abacate", ["abacate"], 96, 1.2, 6, 8.4, 100, "meia unidade pequena"),
  A("Morango", ["morango", "morangos"], 30, 0.9, 7, 0.3, 100, "xícara"),
  A("Uva", ["uva", "uvas"], 53, 0.7, 14, 0.2, 100, "cacho pequeno"),
  A("Açaí com xarope (tigela)", ["acai", "açaí"], 110, 1, 21, 3, 300, "tigela média"),
  A("Salada verde (folhas)", ["salada", "alface", "rucula", "rúcula", "folhas"], 15, 1.3, 2.4, 0.2, 60, "prato de sobremesa"),
  A("Tomate", ["tomate"], 15, 1.1, 3.1, 0.2, 80, "unidade"),
  A("Legumes cozidos", ["legumes", "brocolis", "brócolis", "cenoura", "abobrinha", "chuchu", "vagem", "couve"], 30, 1.8, 5.5, 0.3, 100, "porção"),
  A("Azeite", ["azeite", "oleo", "óleo"], 884, 0, 0, 100, 8, "colher de sopa"),
  A("Manteiga / margarina", ["manteiga", "margarina"], 720, 0.4, 0, 81, 10, "ponta de faca"),
  A("Pasta de amendoim", ["pasta de amendoim", "amendoim"], 590, 25, 20, 49, 15, "colher de sopa"),
  A("Castanhas", ["castanha", "castanhas", "nozes", "amendoas", "amêndoas"], 640, 15, 13, 60, 20, "punhado"),
  A("Chocolate", ["chocolate", "bombom"], 540, 7, 58, 31, 25, "barrinha"),
  A("Bolo simples", ["bolo"], 330, 5, 53, 11, 60, "fatia"),
  A("Biscoito recheado", ["biscoito", "bolacha"], 472, 5.5, 70, 20, 30, "3 unidades"),
  A("Pizza (fatia)", ["pizza"], 270, 11, 30, 11, 110, "fatia"),
  A("Hambúrguer de lanchonete", ["hamburguer", "hambúrguer", "x-burguer", "x burguer", "lanche", "sanduiche", "sanduíche"], 250, 13, 24, 11, 220, "unidade"),
  A("Coxinha / salgado frito", ["coxinha", "pastel", "salgado", "kibe", "quibe", "esfiha"], 290, 9, 30, 15, 100, "unidade"),
  A("Sushi / japonês", ["sushi", "temaki", "sashimi", "hot roll"], 150, 6, 25, 2.5, 30, "peça"),
  A("Refrigerante", ["refrigerante", "coca", "guarana", "guaraná"], 42, 0, 10.6, 0, 350, "lata"),
  A("Refrigerante zero", ["zero", "diet"], 1, 0, 0, 0, 350, "lata"),
  A("Suco de laranja natural", ["suco"], 45, 0.7, 10, 0.2, 250, "copo"),
  A("Cerveja", ["cerveja", "chopp", "chope"], 43, 0.5, 3.6, 0, 350, "lata"),
  A("Vinho", ["vinho"], 85, 0.1, 2.6, 0, 150, "taça"),
  A("Café com açúcar", ["cafe com acucar", "café com açúcar"], 40, 0.3, 9.5, 0, 100, "xícara"),
  A("Café sem açúcar", ["cafe", "café"], 2, 0.1, 0, 0, 100, "xícara"),
  A("Açúcar", ["acucar", "açúcar"], 387, 0, 100, 0, 5, "colher de chá"),
  A("Mel", ["mel"], 309, 0.3, 84, 0, 15, "colher de sopa"),
  A("Sorvete", ["sorvete"], 200, 3.5, 24, 10, 100, "bola dupla"),
  A("Tofu", ["tofu"], 76, 8, 2, 4.8, 100, "porção"),
  A("Lentilha / grão-de-bico", ["lentilha", "grao de bico", "grão de bico", "grão-de-bico"], 116, 9, 20, 0.4, 130, "concha"),
];

const NUMEROS = { um: 1, uma: 1, dois: 2, duas: 2, "três": 3, tres: 3, quatro: 4, cinco: 5, seis: 6, meio: 0.5, meia: 0.5 };
const PORCOES_TEXTO = [
  [/prato (fundo|cheio)/, 1.6], [/prato/, 1.2], [/(concha|escumadeira) cheia/, 1.3],
  [/(pouco|pouquinho)/, 0.6], [/(grande|bastante)/, 1.5],
];

function normalizar(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

function acharAlimento(trecho) {
  const t = normalizar(trecho);
  let melhor = null, tam = 0;
  for (const a of ALIMENTOS) {
    for (const ch of a.chaves) {
      const c = normalizar(ch);
      if (t.includes(c) && c.length > tam) { melhor = a; tam = c.length; }
    }
  }
  return melhor;
}

// "2 ovos, 150g de frango e 1 concha de feijão" → itens com calorias
export function estimarLocal(texto) {
  const partes = normalizar(texto).split(/,|\s+e\s+|\s+com\s+|\+|\n|;/).map((s) => s.trim()).filter(Boolean);
  const itens = [];
  for (const parte of partes) {
    const a = acharAlimento(parte);
    if (!a) continue;
    let gramas = null;
    const mg = parte.match(/(\d+[.,]?\d*)\s*(g|gr|gramas|ml)\b/);
    const mkg = parte.match(/(\d+[.,]?\d*)\s*(kg|l|litro)/);
    if (mg) gramas = parseFloat(mg[1].replace(",", "."));
    else if (mkg) gramas = parseFloat(mkg[1].replace(",", ".")) * 1000;
    else {
      let qtd = 1;
      const mn = parte.match(/^(\d+[.,]?\d*)/);
      if (mn) qtd = parseFloat(mn[1].replace(",", "."));
      else {
        const pal = parte.split(/\s+/)[0];
        if (NUMEROS[pal] != null) qtd = NUMEROS[pal];
      }
      if (/colher(es)? de sopa/.test(parte)) gramas = 15 * qtd;
      else if (/colher(es)? de cha/.test(parte)) gramas = 5 * qtd;
      else {
        let fator = 1;
        for (const [re, f] of PORCOES_TEXTO) if (re.test(parte)) { fator = f; break; }
        gramas = a.porcao * qtd * fator;
      }
    }
    const f = gramas / 100;
    itens.push({
      nome: a.nome,
      quantidade: `${Math.round(gramas)} g`,
      kcal: Math.round(a.kcal * f),
      proteina: Math.round(a.p * f * 10) / 10,
      carboidrato: Math.round(a.c * f * 10) / 10,
      gordura: Math.round(a.g * f * 10) / 10,
    });
  }
  return totalizar(itens, itens.length ? "Estimativa pela tabela TACO (modo offline)." : "");
}

export function totalizar(itens, observacao = "") {
  const soma = (k) => Math.round(itens.reduce((s, i) => s + (Number(i[k]) || 0), 0) * 10) / 10;
  return { itens, kcal: Math.round(soma("kcal")), proteina: soma("proteina"), carboidrato: soma("carboidrato"), gordura: soma("gordura"), observacao };
}
