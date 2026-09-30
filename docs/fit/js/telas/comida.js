// Registro de refeições: foto do prato, voz ou texto → IA estima calorias.
import { esc, num, toast, abrirSheet, confirmar, carregando, dataBR, somarDias, barraMacro, anel, graficoBarras } from "../ui.js";
import { escolherFoto, urlDe, ouvir, suportaVoz } from "../midia.js";
import { analisarRefeicao } from "../ia.js";
import { totalizar } from "../alimentos.js";
import { E, gravar, apagar, metasAtuais } from "../estado.js";
import { porData, todos, hojeISO } from "../db.js";
import { urlFotoRemota } from "../nuvem.js";
import { sugerirSuplementos, NAO_VALE, AVISO_SUPLEMENTOS } from "../suplementos.js";
import { analisarAlimentacao, sugerirFecharDia } from "../nutri-insights.js";
import { miniaturaRefeicao } from "../emoji-comida.js";

export const TIPOS = [
  { id: "cafe", nome: "Café da manhã", emoji: "☕", ate: 10 },
  { id: "almoco", nome: "Almoço", emoji: "🍽️", ate: 15 },
  { id: "lanche", nome: "Lanche", emoji: "🍎", ate: 18 },
  { id: "jantar", nome: "Jantar", emoji: "🌙", ate: 22 },
  { id: "ceia", nome: "Ceia", emoji: "🥛", ate: 24 },
];
const tipoPorHora = () => (TIPOS.find((t) => new Date().getHours() < t.ate) || TIPOS[4]).id;

export async function totaisDoDia(data = hojeISO()) {
  const refs = await porData("refeicoes", data);
  const s = (k) => refs.reduce((a, r) => a + (Number(r[k]) || 0), 0);
  return { refs, kcal: Math.round(s("kcal")), proteina: Math.round(s("proteina")), carboidrato: Math.round(s("carboidrato")), gordura: Math.round(s("gordura")) };
}

let diaVisto = hojeISO();

export async function telaComida(el, ctx) {
  const { rerender } = ctx;
  const m = metasAtuais();
  const t = await totaisDoDia(diaVisto);
  const ehHoje = diaVisto === hojeISO();

  // semana para o gráfico
  const semana = [];
  for (let i = 6; i >= 0; i--) {
    const d = somarDias(diaVisto, -i);
    const tt = await porData("refeicoes", d);
    semana.push({ rotulo: dataBR(d, { weekday: "short" }).slice(0, 3), y: tt.reduce((a, r) => a + (r.kcal || 0), 0), hoje: d === diaVisto });
  }
  const comRegistro = semana.filter((s) => s.y > 0);
  const mediaSemana = comRegistro.length ? Math.round(comRegistro.reduce((a, s) => a + s.y, 0) / comRegistro.length) : 0;
  const fechar = ehHoje ? sugerirFecharDia(E.perfil, { kcal: m.kcal - t.kcal, prot: m.prot - t.proteina }) : null;
  const analise = await analisarAlimentacao(E.perfil, m);

  el.innerHTML = `
    <div class="tela entra">
      <div class="dia-nav">
        <button class="icone-btn" id="ant" aria-label="Dia anterior">‹</button>
        <b>${ehHoje ? "Hoje" : dataBR(diaVisto, { weekday: "long", day: "2-digit", month: "short" })}</b>
        <button class="icone-btn" id="prox" ${ehHoje ? "disabled" : ""} aria-label="Próximo dia">›</button>
      </div>

      <div class="card card--anel">
        ${anel(t.kcal, m.kcal, { rotulo: num(Math.max(0, m.kcal - t.kcal)), sub: t.kcal > m.kcal ? `${num(t.kcal - m.kcal)} acima` : "kcal restantes" })}
        <div class="macros">
          ${barraMacro("Proteína", t.proteina, m.prot, "m-p")}
          ${barraMacro("Carboidrato", t.carboidrato, m.carb, "m-c")}
          ${barraMacro("Gordura", t.gordura, m.gord, "m-g")}
        </div>
      </div>

      <div class="acoes-rapidas">
        <button class="acao" data-add="foto"><span>📸</span>Foto do prato</button>
        <button class="acao" data-add="voz"><span>🎙️</span>Falar</button>
        <button class="acao" data-add="texto"><span>✍️</span>Digitar</button>
      </div>

      ${TIPOS.map((tp) => {
        const lista = t.refs.filter((r) => r.tipo === tp.id).sort((a, b) => (a.hora || "").localeCompare(b.hora || ""));
        if (!lista.length) return "";
        return `
        <section class="grupo-ref">
          <h3>${tp.emoji} ${tp.nome} <small>${num(lista.reduce((a, r) => a + r.kcal, 0))} kcal</small></h3>
          ${lista.map((r) => `
            <button class="ref-item" data-ref="${r.id}">
              ${r.foto || r.fotoPath ? `<img class="ref-foto" data-foto-ref="${r.id}" alt="">` : miniaturaRefeicao(r)}
              <span class="ref-txt"><b>${esc(r.titulo || r.itens.map((i) => i.nome).join(", "))}</b><small>${r.hora || ""} · P ${num(r.proteina)} · C ${num(r.carboidrato)} · G ${num(r.gordura)}</small></span>
              <span class="ref-kcal">${num(r.kcal)}<small>kcal</small></span>
            </button>`).join("")}
        </section>`;
      }).join("") || `<div class="vazio"><span>🍽️</span><p>Nada registrado ${ehHoje ? "hoje" : "neste dia"}.<br>Tire uma foto do prato — a IA faz a conta pra você.</p></div>`}

      ${fechar ? cartaoFecharDia(fechar) : ""}

      ${cartaoInsights(analise)}

      <div class="card">
        <div class="card-tag">📊 Últimos 7 dias</div>
        ${graficoBarras(semana, { meta: m.kcal })}
        <p class="nota">Média nos dias registrados: <b>${num(mediaSemana)} kcal</b> (meta ${num(m.kcal)}). O que importa é a média da semana, não um dia isolado.</p>
      </div>

      <button class="card card--link" id="suplementos">
        <span class="card-tag">💊 Suplementos que valem a pena</span>
        <span class="nota">Veja o que a ciência recomenda para o seu objetivo ›</span>
      </button>
    </div>`;

  el.querySelector("#ant").onclick = () => { diaVisto = somarDias(diaVisto, -1); rerender(); };
  el.querySelector("#prox").onclick = () => { if (!ehHoje) { diaVisto = somarDias(diaVisto, 1); rerender(); } };
  el.querySelectorAll("[data-add]").forEach((b) => b.onclick = () => abrirNovaRefeicao(b.dataset.add, { data: diaVisto, aoSalvar: rerender }));
  el.querySelectorAll("[data-ref]").forEach((b) => b.onclick = () => detalheRefeicao(t.refs.find((r) => r.id === b.dataset.ref), rerender));
  el.querySelector("#suplementos").onclick = abrirSuplementos;
  const bNina = el.querySelector("#fechar-nina");
  if (bNina) bNina.onclick = () => ctx.ir("coach", { agente: "nutri", pergunta: "O que eu como pra bater o resto do dia? Me dê 3 opções com quantidades." });
  const bIns = el.querySelector("#ins-nina");
  if (bIns) bIns.onclick = () => ctx.ir("coach", { agente: "nutri", pergunta: "Analise minha alimentação desta semana e me ensine o que melhorar, começando pelo mais importante." });
  const bTodas = el.querySelector("#ins-todas");
  if (bTodas) bTodas.onclick = () => { el.querySelectorAll(".ins-oculto").forEach((x) => x.classList.remove("ins-oculto")); bTodas.remove(); };
  // fotos (locais ou da nuvem)
  for (const img of el.querySelectorAll("[data-foto-ref]")) {
    const r = t.refs.find((x) => x.id === img.dataset.fotoRef);
    if (r.foto) img.src = urlDe(r.foto, `ref-${r.id}`);
    else if (r.fotoPath) urlFotoRemota(r.fotoPath).then((u) => { img.src = u; });
  }
}

export function resetDiaComida() { diaVisto = hojeISO(); }

// ---------- Nova refeição ----------
export async function abrirNovaRefeicao(modo, { data = hojeISO(), aoSalvar } = {}) {
  let foto = null;
  if (modo === "foto") {
    foto = await escolherFoto({ camera: true });
    if (!foto) return;
  }
  const s = abrirSheet(`
    <h2>Nova refeição</h2>
    <div class="tipos-ref">${TIPOS.map((t) => `<button class="chip ${t.id === tipoPorHora() ? "chip--on" : ""}" data-tipo="${t.id}">${t.emoji} ${t.nome}</button>`).join("")}</div>
    ${foto ? `<img class="foto-prev" src="${urlDe(foto)}" alt="Foto do prato">` : ""}
    <label class="rotulo">${foto ? "Quer detalhar? (opcional — ajuda a IA)" : "O que você comeu?"}</label>
    <div class="campo-voz">
      <textarea id="desc" class="campo" rows="3" placeholder="${foto ? "Ex.: o arroz era integral, a carne era patinho" : "Ex.: 2 ovos mexidos, 1 pão francês com manteiga e café com leite"}"></textarea>
      ${suportaVoz ? `<button class="mic" id="mic" aria-label="Falar">🎙️</button>` : ""}
    </div>
    <p class="nota" id="status-voz"></p>
    <button class="btn btn--grande" id="analisar">Calcular calorias ✨</button>
    <div id="resultado"></div>`, { cheia: true });

  let tipo = tipoPorHora();
  s.el.querySelectorAll("[data-tipo]").forEach((b) => b.onclick = () => {
    tipo = b.dataset.tipo;
    s.el.querySelectorAll("[data-tipo]").forEach((x) => x.classList.toggle("chip--on", x === b));
  });

  const desc = s.el.querySelector("#desc");
  const mic = s.el.querySelector("#mic");
  let rec = null;
  const pararVoz = () => { if (rec) { rec.stop(); rec = null; mic.classList.remove("mic--on"); } };
  if (mic) {
    mic.onclick = () => {
      if (rec) return pararVoz();
      mic.classList.add("mic--on");
      s.el.querySelector("#status-voz").textContent = "Ouvindo… fale o que comeu e toque no microfone para parar.";
      const base = desc.value ? desc.value + " " : "";
      rec = ouvir({
        aoParcial: (t) => { desc.value = base + t; },
        aoFinal: () => { mic.classList.remove("mic--on"); rec = null; s.el.querySelector("#status-voz").textContent = ""; },
        aoErro: (m) => { s.el.querySelector("#status-voz").textContent = m; mic.classList.remove("mic--on"); rec = null; },
      });
    };
    if (modo === "voz") setTimeout(() => mic.click(), 350);
  }
  if (modo === "texto") setTimeout(() => desc.focus(), 350);

  const btn = s.el.querySelector("#analisar");
  const res = s.el.querySelector("#resultado");
  btn.onclick = async () => {
    pararVoz();
    const texto = desc.value.trim();
    if (!texto && !foto) return toast("Descreva a refeição ou tire uma foto.", "erro");
    btn.disabled = true;
    res.innerHTML = carregando(foto ? "Olhando seu prato…" : "Calculando…");
    try {
      const r = await analisarRefeicao({ texto, foto, perfil: E.perfil });
      btn.classList.add("oculto");
      mostrarResultado(res, r, async (final) => {
        const agora = new Date();
        await gravar("refeicoes", {
          data, tipo, hora: `${String(agora.getHours()).padStart(2, "0")}:${String(agora.getMinutes()).padStart(2, "0")}`,
          descricao: texto, foto, ...final,
        });
        s.fechar();
        toast(`Registrado: ${num(final.kcal)} kcal ✅`);
        aoSalvar && aoSalvar();
      });
    } catch (e) {
      res.innerHTML = `<p class="erro-txt">${esc(e.message)}</p>`;
      btn.disabled = false;
    }
  };
}

// Mostra os itens encontrados, deixa ajustar porções e remover itens.
// gramas de uma quantidade ("150 g", "1 unidade (50 g)", "200 ml") — null se não der pra saber
const gramasDaQtd = (q) => { const m = String(q || "").match(/([0-9]+[.,]?[0-9]*)[ ]*(g|gr|gramas|ml)(?![a-z])/i); return m ? parseFloat(m[1].replace(",", ".")) : null; };
const comGramas = (i) => { const g0 = gramasDaQtd(i.quantidade); return { ...i, fator: 1, g0, gramas: g0 }; };

function mostrarResultado(el, r, aoSalvar) {
  let itens = r.itens.map(comGramas);
  const pinta = () => {
    // quantidade em gramas → todos os nutrientes recalculados na mesma proporção
    const ajustados = itens.filter((i) => i.fator > 0).map((i) => ({
      ...i, kcal: Math.round(i.kcal * i.fator), proteina: +(i.proteina * i.fator).toFixed(1),
      carboidrato: +(i.carboidrato * i.fator).toFixed(1), gordura: +(i.gordura * i.fator).toFixed(1),
      quantidade: i.g0 ? `${Math.round(i.gramas)} g` : i.quantidade,
    }));
    ajustados.forEach((i) => { delete i.fator; delete i.g0; delete i.gramas; });
    ajustados.forEach((i) => { delete i.duvida; delete i.separados; delete i.motivo; });
    const tot = totalizar(ajustados);
    const pendentes = itens.filter((i) => i.duvida && i.fator > 0).length;
    el.innerHTML = `
      <div class="resultado-ref entra">
        ${r.aviso ? `<p class="aviso">${esc(r.aviso)}</p>` : ""}
        <p class="rotulo">Entendi assim:</p>
        <div class="total-ref"><b>${num(tot.kcal)}</b> kcal <span>P ${num(tot.proteina)}g · C ${num(tot.carboidrato)}g · G ${num(tot.gordura)}g</span></div>
        ${itens.map((i, k) => `
          <div class="item-ref ${i.fator === 0 ? "item-ref--off" : ""} ${i.duvida && i.fator > 0 ? "item-ref--duvida" : ""}">
            <div class="item-ref-linha">
              <div class="item-ref-nome"><b>${i.duvida && i.fator > 0 ? "❓ " : ""}${esc(i.nome)}</b><small>${num(i.kcal * i.fator)} kcal · P ${num(i.proteina * i.fator, 1)} · C ${num(i.carboidrato * i.fator, 1)} · G ${num(i.gordura * i.fator, 1)}</small></div>
              ${i.g0 ? `
              <div class="qtd-g">
                <button data-k="${k}" data-d="-10" aria-label="Menos 10 gramas">−</button>
                <label><input type="number" inputmode="decimal" min="0" step="5" value="${Math.round(i.gramas)}" data-g="${k}" aria-label="Gramas"><span>g</span></label>
                <button data-k="${k}" data-d="10" aria-label="Mais 10 gramas">+</button>
                <small class="qtd-pct">${Math.round(i.fator * 100)}%</small>
              </div>` : `
              <div class="porcao">
                <button data-k="${k}" data-d="-0.25" aria-label="Menos">−</button>
                <span>${i.fator === 0 ? "0" : `${num(i.fator * 100)}%`}</span>
                <button data-k="${k}" data-d="0.25" aria-label="Mais">+</button>
              </div>`}
            </div>
            ${i.duvida && i.fator > 0 ? `
              <div class="confirmar-item">
                <small>${esc(i.motivo || "Confira este item.")} É isso mesmo?</small>
                <div class="linha-botoes">
                  <button class="chip chip--mini chip--on" data-sim="${k}">✓ Sim, é isso</button>
                  ${i.separados && i.separados.length > 1 ? `<button class="chip chip--mini" data-sep="${k}">Contar separado (${i.separados.map((s) => esc(s.nome)).join(" + ")})</button>` : ""}
                  <button class="chip chip--mini" data-nao="${k}">✕ Não, tirar</button>
                </div>
              </div>` : ""}
          </div>`).join("")}
        ${r.observacao ? `<p class="nota">${esc(r.observacao)}</p>` : ""}
        ${r.dica ? `<div class="dica-ia">🥗 <span>${esc(r.dica)}</span></div>` : ""}
        <p class="nota">Ajuste a quantidade em gramas (ou com − / +) — calorias, proteína, carboidrato e gordura são recalculados na hora. Se algo saiu errado, reescreva mais detalhado (ex.: "150 g de hambúrguer caseiro de patinho").</p>
        ${pendentes ? `<p class="aviso">Confirme ${pendentes === 1 ? "o item com ❓" : `os ${pendentes} itens com ❓`} pra salvar.</p>` : ""}
        <button class="btn btn--grande" id="salvar-ref" ${pendentes ? "disabled" : ""}>Salvar refeição</button>
      </div>`;
    el.querySelectorAll("[data-k]").forEach((b) => b.onclick = () => {
      const it = itens[+b.dataset.k];
      if (it.g0) { it.gramas = Math.max(0, Math.round((it.gramas || 0) + +b.dataset.d)); it.fator = it.gramas / it.g0; }
      else it.fator = Math.max(0, Math.min(4, +(it.fator + +b.dataset.d).toFixed(2)));
      pinta();
    });
    el.querySelectorAll("[data-g]").forEach((inp) => {
      const aplica = () => {
        const it = itens[+inp.dataset.g];
        const v = parseFloat(String(inp.value).replace(",", "."));
        if (!(v >= 0)) return;
        it.gramas = Math.min(it.g0 * 10, v); it.fator = it.gramas / it.g0;
        pinta();
        const novo = el.querySelector(`[data-g="${inp.dataset.g}"]`);
        if (novo) { novo.focus(); novo.setSelectionRange && novo.select(); }
      };
      inp.onchange = aplica;
      inp.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); aplica(); } };
    });
    el.querySelectorAll("[data-sim]").forEach((b) => b.onclick = () => { itens[+b.dataset.sim].duvida = false; pinta(); });
    el.querySelectorAll("[data-nao]").forEach((b) => b.onclick = () => { itens[+b.dataset.nao].fator = 0; itens[+b.dataset.nao].duvida = false; pinta(); });
    el.querySelectorAll("[data-sep]").forEach((b) => b.onclick = () => {
      const k = +b.dataset.sep;
      itens = [...itens.slice(0, k), ...itens[k].separados.map(comGramas), ...itens.slice(k + 1)];
      pinta();
    });
    el.querySelector("#salvar-ref").onclick = () => aoSalvar({ ...tot, itens: ajustados, titulo: r.titulo || ajustados.map((i) => i.nome.replace(/\s*\(.*\)$/, "")).join(", "), fonte: r.fonte });
  };
  pinta();
}

function detalheRefeicao(r, aoMudar) {
  const s = abrirSheet(`
    <h2>${esc(r.titulo || "Refeição")}</h2>
    <p class="nota">${dataBR(r.data, { day: "2-digit", month: "long" })} · ${r.hora || ""} · ${{ tabela: "tabela TACO", local: "tabela TACO", "tabela+ia": "tabela TACO + IA", ia: "estimado por IA" }[r.fonte] || "estimado"}</p>
    ${r.foto ? `<img class="foto-prev" src="${urlDe(r.foto, `ref-${r.id}`)}" alt="">` : r.fotoPath ? `<img class="foto-prev" id="fr" alt="">` : miniaturaRefeicao(r, "foto-prev foto-prev--ilustra")}
    <div class="total-ref"><b>${num(r.kcal)}</b> kcal <span>P ${num(r.proteina)}g · C ${num(r.carboidrato)}g · G ${num(r.gordura)}g</span></div>
    ${r.itens.map((i) => `<div class="item-ref"><div><b>${esc(i.nome)}</b><small>${esc(i.quantidade || "")}</small></div><span>${num(i.kcal)} kcal</span></div>`).join("")}
    ${r.descricao ? `<p class="nota">"${esc(r.descricao)}"</p>` : ""}
    <div class="linha-botoes">
      <button class="btn btn--sec" id="dup">Comi de novo</button>
      <button class="btn btn--perigo" id="del">Apagar</button>
    </div>`);
  if (!r.foto && r.fotoPath) urlFotoRemota(r.fotoPath).then((u) => { const i = s.el.querySelector("#fr"); if (i) i.src = u; });
  s.el.querySelector("#del").onclick = async () => {
    if (!(await confirmar("Apagar esta refeição?", { ok: "Apagar", perigo: true }))) return;
    await apagar("refeicoes", r.id);
    s.fechar(); aoMudar();
  };
  s.el.querySelector("#dup").onclick = async () => {
    const agora = new Date();
    const copia = { ...r, id: undefined, data: hojeISO(), hora: `${String(agora.getHours()).padStart(2, "0")}:${String(agora.getMinutes()).padStart(2, "0")}`, foto: r.foto || null };
    delete copia.fotoPath;
    await gravar("refeicoes", copia);
    s.fechar(); toast("Registrado de novo hoje ✅"); aoMudar();
  };
}

export function abrirSuplementos() {
  const lista = sugerirSuplementos(E.perfil || {});
  abrirSheet(`
    <h2>💊 Suplementos</h2>
    <p class="sub">Primeiro a comida, o sono e o treino. Suplemento é o "1% final". Estes têm evidência real:</p>
    ${lista.map((s) => `
      <details class="supl">
        <summary><span>${s.emoji}</span><b>${esc(s.nome)}</b><span class="nivel nivel--${s.nivel}">Evidência ${s.nivel}</span></summary>
        <p>${esc(s.porque)}</p>
        <p class="nota"><b>Como usar:</b> ${esc(s.dose)}</p>
      </details>`).join("")}
    <h3>🚫 Não gaste dinheiro com</h3>
    ${NAO_VALE.map((n) => `<p class="nota"><b>${esc(n.nome)}:</b> ${esc(n.porque)}</p>`).join("")}
    <p class="aviso">${esc(AVISO_SUPLEMENTOS)}</p>`, { cheia: true });
}

export async function todasRefeicoes() { return todos("refeicoes"); }

// ---------- Cartões de inteligência ----------
function cartaoFecharDia(f) {
  if (f.fechado) return `<div class="card card--fechado"><div class="card-tag">🎯 Meta do dia batida!</div><p class="nota">Calorias e proteína completas. Se bater fome, vá de salada, legumes ou uma fruta.</p></div>`;
  if (!f.opcoes.length) return "";
  return `
    <div class="card card--fechar">
      <div class="card-tag">🍽️ Pra fechar o dia ${f.momento}</div>
      <p>Faltam <b>${num(f.restante.kcal)} kcal</b> e <b>${num(f.restante.prot)} g de proteína</b>. Algumas opções que batem certinho:</p>
      <div class="fechar-opcoes">
        ${f.opcoes.map((o, i) => `
          <div class="fechar-op">
            <span class="fechar-num">${i + 1}</span>
            <div><b>${o.itens.map(esc).join(" + ")}</b><small>~${num(o.kcal)} kcal · P ${num(o.prot)} g · C ${num(o.carb)} g · G ${num(o.gord)} g</small></div>
          </div>`).join("")}
      </div>
      <button class="btn btn--sec btn--peq" id="fechar-nina">💬 Pedir mais ideias à Nina</button>
    </div>`;
}

function cartaoInsights(a) {
  if (!a.nDias) return "";
  const lista = a.insights;
  if (!lista.length) return "";
  return `
    <div class="card card--insights">
      <div class="card-tag">🧠 O que a Nina percebeu (${a.nDias} ${a.nDias === 1 ? "dia" : "dias"} registrados)</div>
      <div class="ins-lista">
        ${lista.map((x, i) => `
          <details class="ins ins--${x.nivel} ${i >= 3 ? "ins-oculto" : ""}">
            <summary><span class="ins-emoji">${x.emoji}</span><span><b>${esc(x.titulo)}</b><small>${esc(x.texto)}</small></span></summary>
            <div class="ins-corpo">
              <p><b>O que fazer:</b> ${esc(x.acao)}</p>
              <p class="nota"><b>Por quê?</b> ${esc(x.porque)}</p>
            </div>
          </details>`).join("")}
      </div>
      ${lista.length > 3 ? `<button class="link" id="ins-todas">Ver todas (${lista.length})</button>` : ""}
      <p class="nota">Vitaminas e minerais são estimados pelos grupos de alimentos (frutas, verduras, peixe…), como no Guia Alimentar. Toque em cada item pra entender o porquê.</p>
      <button class="btn btn--sec btn--peq" id="ins-nina">💬 Conversar com a Nina sobre isso</button>
    </div>`;
}
