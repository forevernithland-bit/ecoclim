// Preferências alimentares: o que a pessoa NÃO gosta (a IA nunca sugere e
// substitui por equivalente) + tipo de alimentação e alergias/intolerâncias.
// Fica salvo no perfil (sincroniza pra nuvem) e vai no contexto de toda IA.
import { esc } from "./ui.js";

export const COMUNS = [
  "Peixe", "Fígado", "Ovo", "Brócolis", "Couve-flor", "Berinjela", "Abobrinha", "Chuchu", "Quiabo", "Jiló",
  "Beterraba", "Cebola", "Pimentão", "Coentro", "Cogumelo", "Tomate", "Abacate", "Banana", "Mamão", "Leite",
  "Iogurte", "Queijo", "Aveia", "Batata-doce", "Feijão", "Lentilha", "Grão-de-bico", "Frango", "Carne de porco", "Atum",
];

export const DIETAS = [
  { id: "tudo", nome: "Como de tudo" },
  { id: "vegetariano", nome: "Vegetariano" },
  { id: "vegano", nome: "Vegano" },
  { id: "sem_lactose", nome: "Sem lactose" },
  { id: "sem_gluten", nome: "Sem glúten" },
  { id: "low_carb", nome: "Prefiro low carb" },
];

const norm = (s) => String(s || "").trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
const cap = (s) => { const t = String(s || "").trim(); return t ? t[0].toUpperCase() + t.slice(1) : t; };

// Junta itens novos sem duplicar (ignora acento/maiúscula).
export function juntar(lista, novos) {
  const r = [...(lista || [])];
  for (const n of novos || []) {
    const t = cap(n);
    if (t && !r.some((x) => norm(x) === norm(t))) r.push(t);
  }
  return r;
}
export function remover(lista, tirar) {
  const fora = new Set((tirar || []).map(norm));
  return (lista || []).filter((x) => !fora.has(norm(x)));
}

// Editor reaproveitado no cadastro e no Perfil. `p` é mutado direto.
export function editorGostos(el, p, aoMudar = () => {}) {
  p.naoGosta = p.naoGosta || [];
  p.dietas = p.dietas || ["tudo"];
  const extras = () => p.naoGosta.filter((x) => !COMUNS.some((c) => norm(c) === norm(x)));
  const pinta = () => {
    el.innerHTML = `
      <label class="rotulo">Tipo de alimentação</label>
      <div class="chips-quebra">${DIETAS.map((d) => `<button type="button" class="chip ${p.dietas.includes(d.id) ? "chip--on" : ""}" data-dieta="${d.id}">${d.nome}</button>`).join("")}</div>
      <label class="rotulo">Toque no que você NÃO gosta 🙅</label>
      <div class="chips-quebra">
        ${COMUNS.map((c) => `<button type="button" class="chip ${p.naoGosta.some((x) => norm(x) === norm(c)) ? "chip--nao" : ""}" data-ng="${esc(c)}">${esc(c)}</button>`).join("")}
        ${extras().map((c) => `<button type="button" class="chip chip--nao" data-ng="${esc(c)}">${esc(c)} ✕</button>`).join("")}
      </div>
      <div class="linha-add">
        <input class="campo" id="ng-novo" placeholder="Outro alimento (ex.: rúcula)">
        <button type="button" class="btn btn--peq" id="ng-add">Adicionar</button>
      </div>
      <label class="rotulo">Alergias ou intolerâncias (opcional)</label>
      <input class="campo" id="ng-alergias" placeholder="Ex.: camarão, amendoim" value="${esc(p.alergias || "")}">`;
    el.querySelectorAll("[data-dieta]").forEach((b) => b.onclick = () => {
      const id = b.dataset.dieta;
      if (id === "tudo") p.dietas = ["tudo"];
      else {
        p.dietas = p.dietas.filter((x) => x !== "tudo");
        p.dietas = p.dietas.includes(id) ? p.dietas.filter((x) => x !== id) : [...p.dietas, id];
        if (!p.dietas.length) p.dietas = ["tudo"];
      }
      pinta(); aoMudar();
    });
    el.querySelectorAll("[data-ng]").forEach((b) => b.onclick = () => {
      const item = b.dataset.ng;
      p.naoGosta = p.naoGosta.some((x) => norm(x) === norm(item)) ? remover(p.naoGosta, [item]) : juntar(p.naoGosta, [item]);
      pinta(); aoMudar();
    });
    const inp = el.querySelector("#ng-novo");
    const add = () => {
      const itens = inp.value.split(/,|\se\s/).map((s) => s.trim()).filter(Boolean);
      if (!itens.length) return;
      p.naoGosta = juntar(p.naoGosta, itens);
      pinta(); aoMudar();
    };
    el.querySelector("#ng-add").onclick = add;
    inp.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } };
    el.querySelector("#ng-alergias").onchange = (e) => { p.alergias = e.target.value.trim(); aoMudar(); };
  };
  pinta();
}

export function resumoGostos(p) {
  const d = (p.dietas || ["tudo"]).map((id) => (DIETAS.find((x) => x.id === id) || {}).nome).filter(Boolean).join(", ");
  const ng = (p.naoGosta || []).length ? `Não gosta: ${p.naoGosta.join(", ")}` : "Nenhum alimento marcado como 'não gosto'";
  return `${d}. ${ng}.${p.alergias ? ` Alergias: ${p.alergias}.` : ""}`;
}
