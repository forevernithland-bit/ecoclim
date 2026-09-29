// Janela "digite ou fale seus exercícios": interpreta o texto, mostra o que
// entendeu (séries × reps, carga, minutos) e, pro que não reconheceu,
// sugere exercícios parecidos ou deixa usar do jeito que foi escrito.
import { esc, abrirSheet, toast } from "../ui.js";
import { ouvir, suportaVoz } from "../midia.js";
import { interpretarExercicios, montarItem, itemPersonalizado, paraExercicio } from "../interpretar-treino.js";

export function abrirAdicionarExercicios({ titulo = "➕ Adicionar exercícios", botao = "Adicionar", aoConfirmar }) {
  const sh = abrirSheet(`
    <h2>${esc(titulo)}</h2>
    <p class="sub">Escreva do seu jeito — um por linha ou separados por vírgula.</p>
    <div class="campo-voz">
      <textarea id="txt-ex" class="campo" rows="4" placeholder="Ex.: 3x12 rosca scott 15kg, supino declinado, 4x10 leg press 120kg e 20 min de esteira"></textarea>
      ${suportaVoz ? `<button class="mic" id="mic-ex" aria-label="Falar">🎙️</button>` : ""}
    </div>
    <p class="nota" id="voz-ex"></p>
    <button class="btn" id="entender">Entender exercícios ✨</button>
    <div id="res-ex"></div>`, { cheia: true });

  const txt = sh.el.querySelector("#txt-ex");
  setTimeout(() => txt.focus(), 300);
  const mic = sh.el.querySelector("#mic-ex");
  let rec = null;
  if (mic) mic.onclick = () => {
    if (rec) { rec.stop(); rec = null; mic.classList.remove("mic--on"); return; }
    mic.classList.add("mic--on");
    sh.el.querySelector("#voz-ex").textContent = "Ouvindo… fale os exercícios e toque no microfone pra parar.";
    const base = txt.value ? `${txt.value}, ` : "";
    rec = ouvir({
      aoParcial: (t) => { txt.value = base + t; },
      aoFinal: () => { mic.classList.remove("mic--on"); rec = null; sh.el.querySelector("#voz-ex").textContent = ""; },
      aoErro: (m) => { sh.el.querySelector("#voz-ex").textContent = m; mic.classList.remove("mic--on"); rec = null; },
    });
  };

  let itens = [];
  const res = sh.el.querySelector("#res-ex");
  const pinta = () => {
    if (!itens.length) { res.innerHTML = `<p class="erro-txt">Não achei exercícios nesse texto. Tente algo como "3x10 supino reto 40kg".</p>`; return; }
    const pendentes = itens.filter((x) => !x.reconhecido).length;
    res.innerHTML = `
      <div class="interp-lista">
        ${itens.map((x, i) => x.reconhecido ? `
          <div class="interp-item interp-item--ok">
            <span class="interp-ic">${x.tipo === "cardio" ? "🏃" : "✅"}</span>
            <div class="interp-txt">
              <b>${esc(x.nome)}</b>
              <small>${x.tipo === "cardio" ? `${x.minutos || 20} min${x.km ? ` · ${x.km} km` : ""}` : `${x.series} × ${esc(x.reps)}${x.kg ? ` · ${x.kg} kg` : ""}`} · ${esc(x.grupo)}</small>
              ${x.outras && x.outras.length ? `<div class="interp-outras">Não é esse? ${x.outras.slice(0, 3).map((o, j) => `<button class="chip chip--mini" data-trocar="${i}" data-o="${j}">${esc(o.nome)}</button>`).join("")}</div>` : ""}
            </div>
            <button class="icone-btn icone-btn--mini" data-remover="${i}" aria-label="Remover">✕</button>
          </div>` : `
          <div class="interp-item interp-item--duvida">
            <span class="interp-ic">❓</span>
            <div class="interp-txt">
              <b>"${esc(x.digitado)}"</b>
              <small>Não reconheci. ${x.sugestoes.length ? "Você quis dizer:" : ""}</small>
              <div class="interp-outras">
                ${x.sugestoes.map((o, j) => `<button class="chip chip--mini" data-sug="${i}" data-o="${j}">${esc(o.nome)}</button>`).join("")}
                <button class="chip chip--mini chip--usar" data-usar="${i}">Usar "${esc(x.digitado)}" assim mesmo</button>
              </div>
            </div>
            <button class="icone-btn icone-btn--mini" data-remover="${i}" aria-label="Remover">✕</button>
          </div>`).join("")}
      </div>
      ${pendentes ? `<p class="nota">Resolva os itens com ❓ (toque numa sugestão, use como escreveu ou remova).</p>` : ""}
      <button class="btn btn--grande" id="confirmar" ${pendentes ? "disabled" : ""}>${esc(botao)} (${itens.length})</button>`;

    res.querySelectorAll("[data-remover]").forEach((b) => b.onclick = () => { itens.splice(+b.dataset.remover, 1); pinta(); });
    res.querySelectorAll("[data-sug]").forEach((b) => b.onclick = () => {
      const x = itens[+b.dataset.sug];
      itens[+b.dataset.sug] = montarItem(x.sugestoes[+b.dataset.o], x.nums, x.textoOriginal);
      pinta();
    });
    res.querySelectorAll("[data-trocar]").forEach((b) => b.onclick = () => {
      const x = itens[+b.dataset.trocar];
      const nums = { series: x.series, reps: x.reps, kg: x.kg, minutos: x.minutos, km: x.km };
      const novo = montarItem(x.outras[+b.dataset.o], nums, x.textoOriginal);
      novo.outras = [{ nome: x.nome, slot: x.slot, tipo: x.tipo, chaves: [] }, ...x.outras.filter((_, j) => j !== +b.dataset.o)];
      itens[+b.dataset.trocar] = novo;
      pinta();
    });
    res.querySelectorAll("[data-usar]").forEach((b) => b.onclick = () => {
      const x = itens[+b.dataset.usar];
      itens[+b.dataset.usar] = itemPersonalizado(x.digitado, x.nums);
      pinta();
    });
    const conf = res.querySelector("#confirmar");
    if (conf) conf.onclick = async () => {
      conf.disabled = true;
      await aoConfirmar(itens.map(paraExercicio));
      sh.fechar();
    };
  };

  sh.el.querySelector("#entender").onclick = () => {
    if (rec) { rec.stop(); rec = null; }
    if (!txt.value.trim()) return toast("Escreva ou fale pelo menos um exercício.", "erro");
    itens = interpretarExercicios(txt.value);
    pinta();
  };
}
