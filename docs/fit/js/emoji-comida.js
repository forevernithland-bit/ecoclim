// Ilustração da refeição quando não há foto: até 3 emojis dos alimentos
// principais sobre um fundo colorido (sem direitos autorais, carrega na hora).
import { normalizar } from "./alimentos.js";

// Mais específico primeiro (a 1ª regra que casar vence por item)
const MAPA = [
  [["ovo mexido", "ovos mexidos", "omelete", "ovo frito"], "🍳"], [["ovo", "ovos", "clara"], "🥚"],
  [["pao de queijo"], "🧀"], [["pao", "torrada", "bisnaguinha", "sanduiche", "misto"], "🍞"], [["tapioca", "crepioca", "cuscuz"], "🫓"],
  [["pizza"], "🍕"], [["hamburguer", "x-", "x tudo", "lanche", "burger"], "🍔"], [["cachorro quente", "hot dog", "salsicha"], "🌭"],
  [["batata frita", "fritas"], "🍟"], [["sushi", "sashimi", "temaki", "hot roll", "japones"], "🍣"], [["macarrao", "espaguete", "lasanha", "nhoque", "yakisoba", "miojo"], "🍝"],
  [["arroz"], "🍚"], [["feijao", "feijoada", "lentilha", "grao de bico", "tropeiro"], "🫘"],
  [["frango", "sobrecoxa", "coxa", "nugget"], "🍗"], [["peixe", "tilapia", "salmao", "atum", "sardinha", "bacalhau", "moqueca"], "🐟"], [["camarao"], "🦐"],
  [["bacon", "linguica", "calabresa", "presunto", "mortadela", "salame", "peito de peru"], "🥓"],
  [["carne", "patinho", "bife", "alcatra", "picanha", "costela", "cupim", "fraldinha", "almondega", "estrogonofe", "parmegiana", "figado", "lombo", "porco"], "🥩"],
  [["queijo", "mussarela", "mucarela", "requeijao", "cottage", "ricota", "coalho"], "🧀"], [["iogurte", "leite", "vitamina", "shake", "whey"], "🥛"],
  [["cafe", "cappuccino"], "☕"], [["cha"], "🍵"], [["suco"], "🧃"], [["refrigerante", "coca", "guarana"], "🥤"], [["cerveja", "chopp"], "🍺"], [["vinho"], "🍷"], [["agua de coco"], "🥥"],
  [["banana"], "🍌"], [["maca"], "🍎"], [["laranja", "mexerica", "tangerina"], "🍊"], [["morango"], "🍓"], [["uva"], "🍇"], [["abacaxi"], "🍍"], [["melancia"], "🍉"], [["manga"], "🥭"], [["abacate"], "🥑"], [["kiwi"], "🥝"], [["mamao", "melao", "pera", "pessego", "goiaba", "fruta"], "🍑"], [["acai"], "🍇"],
  [["batata doce", "batata-doce", "mandioca", "aipim", "inhame"], "🍠"], [["batata", "pure"], "🥔"], [["milho", "pipoca", "polenta"], "🌽"],
  [["salada", "alface", "rucula", "folhas", "couve", "brocolis", "legume", "abobrinha", "chuchu", "vagem", "repolho"], "🥗"], [["tomate", "vinagrete"], "🍅"], [["cenoura"], "🥕"], [["cogumelo", "champignon"], "🍄"],
  [["aveia", "granola", "cereal"], "🥣"], [["castanha", "amendoa", "nozes", "amendoim", "pasta de amendoim"], "🥜"],
  [["chocolate", "bombom", "brigadeiro", "achocolatado", "nescau"], "🍫"], [["bolo"], "🍰"], [["sorvete", "picole"], "🍦"], [["biscoito", "bolacha", "cookie"], "🍪"], [["pudim", "mousse", "doce"], "🍮"], [["donut", "rosquinha", "sonho"], "🍩"],
  [["coxinha", "pastel", "esfiha", "kibe", "quibe", "empada", "salgado", "enroladinho"], "🥟"], [["sopa", "caldo", "canja"], "🍲"], [["wrap", "burrito", "tortilha"], "🌯"],
];
const CORES = { "🥩": "#fde2e2", "🍗": "#feeccf", "🐟": "#dbeafe", "🍚": "#f1f5f9", "🥗": "#dcfce7", "🍳": "#fef9c3", "🥚": "#fef9c3", "🍞": "#fdecc8", "🍊": "#ffedd5", "🍕": "#fee2e2", "🍔": "#fde68a", "☕": "#ede0d4", "🥛": "#e0f2fe" };

function emojiDoItem(nome) {
  const n = ` ${normalizar(nome)} `;
  for (const [chaves, e] of MAPA) if (chaves.some((c) => n.includes(c))) return e;
  return null;
}

export function emojisDaRefeicao(r) {
  const nomes = (r.itens && r.itens.length ? r.itens.map((i) => i.nome) : [r.titulo || r.descricao || ""]);
  // do mais calórico pro menos: o principal aparece maior
  const ordenados = r.itens && r.itens.length ? [...r.itens].sort((a, b) => (b.kcal || 0) - (a.kcal || 0)).map((i) => i.nome) : nomes;
  const lista = [];
  for (const nm of ordenados) { const e = emojiDoItem(nm); if (e && !lista.includes(e)) lista.push(e); if (lista.length === 3) break; }
  if (!lista.length) { const e = emojiDoItem(r.titulo || ""); if (e) lista.push(e); }
  return lista.length ? lista : ["🍽️"];
}

export function miniaturaRefeicao(r, classe = "ref-foto") {
  const es = emojisDaRefeicao(r);
  const cor = CORES[es[0]] || "#eef2f7";
  return `<span class="${classe} ref-ilustra ref-ilustra--${es.length}" style="--cor:${cor}" aria-hidden="true">${es.map((e, i) => `<i class="ri-${i}">${e}</i>`).join("")}</span>`;
}
