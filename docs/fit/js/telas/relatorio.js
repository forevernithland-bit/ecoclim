// RELATÓRIO diário / semanal / mensal: meta × realizado, nota de aderência,
// projeção "se continuar assim" e dicas automáticas a partir dos registros.
import { esc, num, anel, dataBR, somarDias, graficoBarras, carregando, toast } from "../ui.js";
import { E, metasAtuais, listar } from "../estado.js";
import { todos, hojeISO } from "../db.js";
import { projetarRitmo } from "../ciencia.js";
import { cardio, PADRAO_DIAS } from "../treino.js";
import { conversar, resumoPerfil } from "../ia.js";
import { analisarAlimentacao } from "../nutri-insights.js";

const PERIODOS = { dia: { nome: "Hoje", dias: 1 }, semana: { nome: "Semana", dias: 7 }, mes: { nome: "Mês", dias: 30 } };
let periodo = "semana";
export const abrirRelatorio = (p) => { if (p) periodo = p; };

// ---------- Cálculo ----------
export async function calcularRelatorio(qual = periodo) {
  const p = E.perfil, m = metasAtuais();
  const n = PERIODOS[qual].dias;
  const fim = hojeISO();
  const ini = somarDias(fim, -(n - 1));
  const datas = Array.from({ length: n }, (_, i) => somarDias(ini, i));
  const [refs, mets, treinos] = await Promise.all([todos("refeicoes"), todos("metricas"), todos("treinos")]);
  const noPeriodo = (x) => x.data >= ini && x.data <= fim;

  const dias = datas.map((d) => {
    const rs = refs.filter((r) => r.data === d);
    const mt = mets.find((x) => x.data === d) || {};
    return {
      data: d,
      registrou: rs.length > 0,
      kcal: Math.round(rs.reduce((a, r) => a + (r.kcal || 0), 0)),
      prot: Math.round(rs.reduce((a, r) => a + (r.proteina || 0), 0)),
      refs: rs,
      agua: +mt.agua || 0, passos: +mt.passos || 0, sono: +mt.sono || 0, peso: +mt.peso || 0,
      treinou: treinos.some((t) => t.data === d),
      planejado: (E.plano.diasSemana || PADRAO_DIAS[E.plano.dias] || []).includes(new Date(`${d}T12:00:00`).getDay()),
    };
  });

  const obj = p.objetivo;
  const naMeta = (k) => {
    if (!k) return false;
    if (obj === "emagrecer") return k >= m.kcal * 0.8 && k <= m.kcal * 1.05;
    if (obj === "massa") return k >= m.kcal * 0.95 && k <= m.kcal * 1.15;
    return k >= m.kcal * 0.88 && k <= m.kcal * 1.08;
  };
  const registrados = dias.filter((d) => d.registrou);
  const kcalMedia = registrados.length ? Math.round(registrados.reduce((a, d) => a + d.kcal, 0) / registrados.length) : 0;
  const protMedia = registrados.length ? Math.round(registrados.reduce((a, d) => a + d.prot, 0) / registrados.length) : 0;
  const diasKcalOk = dias.filter((d) => naMeta(d.kcal)).length;
  const diasProtOk = dias.filter((d) => d.prot >= m.prot * 0.9).length;
  const planejados = dias.filter((d) => d.planejado).length;
  const feitos = dias.filter((d) => d.treinou).length;
  const comAgua = dias.filter((d) => d.agua > 0);
  const aguaMedia = comAgua.length ? comAgua.reduce((a, d) => a + d.agua, 0) / comAgua.length : 0;
  const comPassos = dias.filter((d) => d.passos > 0);
  const passosMedia = comPassos.length ? Math.round(comPassos.reduce((a, d) => a + d.passos, 0) / comPassos.length) : 0;
  const comSono = dias.filter((d) => d.sono > 0);
  const sonoMedia = comSono.length ? comSono.reduce((a, d) => a + d.sono, 0) / comSono.length : 0;

  // Nota de aderência (0–100). Dia sem registro conta como 0 — registrar É parte do método.
  const partes = [
    { id: "kcal", nome: "Calorias", peso: 35, valor: diasKcalOk / n },
    { id: "prot", nome: "Proteína", peso: 20, valor: diasProtOk / n },
  ];
  if (planejados > 0) partes.push({ id: "treino", nome: "Treinos", peso: 30, valor: Math.min(1, feitos / planejados) });
  partes.push({ id: "agua", nome: "Água", peso: 15, valor: Math.min(1, (aguaMedia * comAgua.length) / (m.agua * n)) });
  const somaPesos = partes.reduce((a, x) => a + x.peso, 0);
  const nota = Math.round((partes.reduce((a, x) => a + x.peso * x.valor, 0) / somaPesos) * 100);

  // Treino pra projeção: no relatório do dia usa os últimos 7 dias (1 dia não diz nada)
  let aderenciaTreino = planejados ? feitos / planejados : 1;
  if (qual === "dia") {
    const ini7 = somarDias(fim, -6);
    const d7 = Array.from({ length: 7 }, (_, i) => somarDias(ini7, i));
    const plan7 = d7.filter((d) => (E.plano.diasSemana || []).includes(new Date(`${d}T12:00:00`).getDay())).length;
    const feit7 = d7.filter((d) => treinos.some((t) => t.data === d)).length;
    aderenciaTreino = plan7 ? feit7 / plan7 : 1;
  }

  const temDados = registrados.length > 0;
  const balanco = temDados ? kcalMedia - m.gasto : null;
  const assim = temDados ? projetarRitmo(p, { balanco, aderenciaTreino, proteinaOk: protMedia >= m.prot * 0.9 }, 6) : null;
  const ideal = projetarRitmo(p, { balanco: m.kcal - m.gasto, aderenciaTreino: 1, proteinaOk: true }, 6);

  // Peso real no período (tendência)
  const pesos = [...mets].filter((x) => x.peso && x.data >= somarDias(fim, -Math.max(n, 14)) && x.data <= fim).sort((a, b) => a.data.localeCompare(b.data));

  return {
    qual, n, ini, fim, dias, m, p, nota, partes, kcalMedia, protMedia, diasKcalOk, diasProtOk, planejados, feitos,
    aguaMedia, passosMedia, sonoMedia, registrados: registrados.length, balanco, assim, ideal, pesos, aderenciaTreino,
  };
}

// ---------- Dicas automáticas (regras, sem IA) ----------
const FONTES_PROTEINA = [
  ["Frango", "150 g de frango (48 g)"], ["Ovo", "3 ovos (20 g)"], ["Iogurte", "1 iogurte grego/proteico (10–15 g)"],
  ["Whey", "1 scoop de whey (24 g)"], ["Atum", "1 lata de atum (25 g)"], ["Carne", "120 g de patinho (43 g)"], ["Feijão", "2 conchas de feijão (13 g)"],
];

export function gerarDicas(r) {
  const d = [];
  const { p, m, n } = r;
  const nao = (p.naoGosta || []).map((x) => x.toLowerCase());
  const podeComer = (nome) => !nao.some((x) => nome.toLowerCase().includes(x) || x.includes(nome.toLowerCase()));

  if (r.registrados === 0) {
    d.push({ e: "📝", t: `Nenhuma refeição registrada ${r.qual === "dia" ? "hoje" : "no período"}. Sem registro não dá pra medir — tire foto do prato ou fale o que comeu, leva 10 segundos.` });
    return d;
  }
  if (r.registrados < n * 0.7 && n > 1) {
    d.push({ e: "📝", t: `Você registrou comida em ${r.registrados} de ${n} dias. Quem registra todo dia tem o dobro de resultado nos estudos — mesmo que seja só uma foto.` });
  }
  // Proteína
  if (r.protMedia < m.prot * 0.9) {
    const falta = Math.round(m.prot - r.protMedia);
    const opcoes = FONTES_PROTEINA.filter(([nome]) => podeComer(nome)).slice(0, 3).map(([, t]) => t).join(", ");
    d.push({ e: "🥩", t: `Faltaram em média ${falta} g de proteína por dia (meta ${m.prot} g). É ela que segura e constrói músculo${p.focoMuscular === "bracos" ? " — inclusive o braço" : ""}. Fácil de completar: ${opcoes}.` });
  } else {
    d.push({ e: "💪", t: `Proteína em dia (média ${r.protMedia} g). Ótimo pra construir músculo${p.focoMuscular === "bracos" ? " e fazer o braço crescer" : ""}.` });
  }
  // Calorias
  const dif = r.kcalMedia - m.kcal;
  if ((p.objetivo === "emagrecer" || p.objetivo === "recomp") && dif > m.kcal * 0.08) {
    const porAlimento = {};
    for (const dia of r.dias) for (const ref of dia.refs) for (const it of ref.itens || []) porAlimento[it.nome] = (porAlimento[it.nome] || 0) + (it.kcal || 0);
    const top = Object.entries(porAlimento).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([nome, k]) => `${nome} (${num(k)} kcal)`).join(", ");
    d.push({ e: "🔥", t: `Média de ${num(r.kcalMedia)} kcal/dia, ${num(dif)} acima da meta. Os itens que mais somaram: ${top}. Trocar só um deles já resolve boa parte.` });
  } else if (p.objetivo === "massa" && dif < -m.kcal * 0.05) {
    d.push({ e: "🍚", t: `Faltaram ~${num(-dif)} kcal/dia pra meta de ganho. Sem sobra de energia o músculo não cresce: acrescente um lanche (ex.: vitamina de banana com aveia ~350 kcal).` });
  } else if (r.kcalMedia < m.kcal * 0.75) {
    d.push({ e: "⚠️", t: `Comendo bem abaixo da meta (${num(r.kcalMedia)} kcal). Cortar demais faz perder músculo e dá efeito sanfona — suba pra perto de ${num(m.kcal)} kcal.` });
  } else if (n > 1 && r.diasKcalOk / n < 0.6) {
    const ks = r.dias.filter((x) => x.registrou).map((x) => x.kcal);
    d.push({ e: "🎢", t: `Na média ficou perto da meta, mas só ${r.diasKcalOk} de ${n} dias ficaram dentro dela — oscilou entre ${num(Math.min(...ks))} e ${num(Math.max(...ks))} kcal. Dias mais parecidos entre si dão menos fome e resultado mais previsível.` });
  } else {
    d.push({ e: "🎯", t: `Calorias na medida (média ${num(r.kcalMedia)} de ${num(m.kcal)} kcal). É exatamente assim que o resultado aparece.` });
  }
  // Fim de semana
  if (n >= 7) {
    const fds = r.dias.filter((x) => x.registrou && [0, 6].includes(new Date(`${x.data}T12:00:00`).getDay()));
    const util = r.dias.filter((x) => x.registrou && ![0, 6].includes(new Date(`${x.data}T12:00:00`).getDay()));
    if (fds.length && util.length) {
      const mf = fds.reduce((a, x) => a + x.kcal, 0) / fds.length, mu = util.reduce((a, x) => a + x.kcal, 0) / util.length;
      if (mf - mu > 350) d.push({ e: "🗓️", t: `No fim de semana você come ~${num(mf - mu)} kcal a mais por dia. Planeje a refeição livre (1 por fim de semana) em vez de liberar o sábado inteiro.` });
    }
  }
  // Treinos
  if (r.planejados > 0) {
    if (r.feitos >= r.planejados) d.push({ e: "🏆", t: `Todos os ${r.planejados} treinos planejados feitos! Constância é o que mais faz diferença.` });
    else d.push({ e: "🏋️", t: `${r.feitos} de ${r.planejados} treinos feitos. ${r.feitos === 0 ? "Comece com o próximo — mesmo um treino curto vale." : "Deixe a roupa separada na noite anterior: tira a decisão do caminho."}` });
  }
  // Água, sono, passos
  if (r.aguaMedia && r.aguaMedia < m.agua * 0.7) d.push({ e: "💧", t: `Água em média ${num(r.aguaMedia, 1)} L (meta ${num(m.agua, 1)} L). Uma garrafa sempre à vista resolve.` });
  if (r.sonoMedia && r.sonoMedia < 7) d.push({ e: "😴", t: `Dormindo ${num(r.sonoMedia, 1)} h em média. Menos de 7 h aumenta a fome e atrapalha o ganho de músculo.` });
  const metaPassos = cardio(p).passos;
  if (r.passosMedia && r.passosMedia < metaPassos * 0.75) d.push({ e: "🚶", t: `Média de ${num(r.passosMedia)} passos (meta ${num(metaPassos)}). Uma caminhada de 20 min depois do almoço soma ~2.000.` });
  // Tendência de peso real
  if (r.pesos.length >= 3) {
    const a = r.pesos[0], b = r.pesos[r.pesos.length - 1];
    const semanas = Math.max(1, (new Date(b.data) - new Date(a.data)) / (7 * 864e5));
    const porSemana = (b.peso - a.peso) / semanas;
    const esperado = ((m.kcal - m.gasto) * 7) / 7700;
    let obs = "";
    if (Math.abs(porSemana - esperado) < 0.25) obs = " Dentro do esperado ✅";
    else if (porSemana < esperado - 0.3 && porSemana < -(p.peso * 0.01)) obs = " Mais rápido que o ideal (acima de 1% do peso por semana) — risco de perder músculo; coma um pouco mais perto da meta.";
    else if (porSemana < esperado) obs = " Um pouco mais rápido que o previsto — no começo é normal (água e intestino).";
    else obs = " Mais devagar que o previsto — confira se está registrando tudo (óleo, bebidas, beliscos).";
    d.push({ e: "⚖️", t: `Seu peso está ${porSemana <= 0 ? "caindo" : "subindo"} ~${num(Math.abs(porSemana), 2)} kg/semana (o plano prevê ${esperado <= 0 ? "−" : "+"}${num(Math.abs(esperado), 2)}).${obs}` });
  }
  return d.slice(0, 6);
}

// ---------- Tela ----------
const corNota = (n) => (n >= 80 ? "bom" : n >= 60 ? "medio" : "ruim");
const rotuloNota = (n) => (n >= 80 ? "Excelente 🔥" : n >= 60 ? "Bom caminho 👍" : "Dá pra melhorar 💪");
const pct = (a, b) => (b > 0 ? Math.min(999, Math.round((a / b) * 100)) : 0);
const sinal = (v, c = 1) => `${v > 0 ? "+" : ""}${num(v, c)}`;

function barra(nome, valor, meta, unidade, txt) {
  const x = pct(valor, meta);
  return `
    <div class="rel-linha">
      <div class="rel-linha-topo"><span>${nome}</span><b>${txt || `${num(valor)} / ${num(meta)} ${unidade}`}</b></div>
      <div class="macro-trilho"><div class="macro-barra ${x >= 90 ? "rel-ok" : x >= 60 ? "rel-medio" : "rel-baixo"}" style="width:${Math.min(100, x)}%"></div></div>
    </div>`;
}

function graficoProjecao(assim, ideal) {
  const L = 320, A = 170, pe = 34, pd = 12, pt = 14, pb = 26;
  const vals = [...(assim || []), ...ideal].map((x) => x.peso);
  let y0 = Math.min(...vals), y1 = Math.max(...vals);
  const folga = Math.max(0.8, (y1 - y0) * 0.15); y0 -= folga; y1 += folga;
  const X = (m) => pe + (m / 6) * (L - pe - pd);
  const Y = (v) => pt + (1 - (v - y0) / (y1 - y0)) * (A - pt - pb);
  const linha = (tr, cls) => `<path d="${tr.map((x, i) => `${i ? "L" : "M"}${X(x.mes).toFixed(1)},${Y(x.peso).toFixed(1)}`).join(" ")}" class="${cls}"/>` +
    tr.filter((x) => [0, 1, 3, 6].includes(x.mes)).map((x) => `<circle cx="${X(x.mes)}" cy="${Y(x.peso)}" r="3.5" class="${cls}-p"/>`).join("");
  const ticks = [y0 + folga, (y0 + y1) / 2, y1 - folga].map((v) => `<text x="${pe - 6}" y="${Y(v) + 4}" text-anchor="end" class="graf-eixo">${num(v, 1)}</text><line x1="${pe}" x2="${L - pd}" y1="${Y(v)}" y2="${Y(v)}" class="graf-grade"/>`).join("");
  return `
  <svg viewBox="0 0 ${L} ${A}" class="grafico" role="img" aria-label="Projeção de peso">
    ${ticks}
    ${linha(ideal, "proj-ideal")}
    ${assim ? linha(assim, "proj-assim") : ""}
    ${[0, 1, 3, 6].map((mm) => `<text x="${X(mm)}" y="${A - 8}" text-anchor="middle" class="graf-eixo">${mm === 0 ? "hoje" : `${mm}m`}</text>`).join("")}
  </svg>
  <div class="legenda"><span><i class="lg-assim"></i>Se continuar assim</span><span><i class="lg-ideal"></i>Cumprindo 100%</span></div>`;
}

export async function telaRelatorio(el, ctx) {
  el.innerHTML = carregando("Montando seu relatório…");
  const r = await calcularRelatorio(periodo);
  const dicas = gerarDicas(r);
  try {
    const a = await analisarAlimentacao(E.perfil, r.m, { dias: r.n });
    for (const x of a.insights.filter((i) => i.nivel !== "bom" && !["proteina"].includes(i.id)).slice(0, 3)) dicas.push({ e: x.emoji, t: `${x.titulo}. ${x.acao}` });
  } catch (e) { /* sem dados */ }
  const { m, p } = r;
  const tituloPeriodo = r.qual === "dia" ? dataBR(r.fim, { weekday: "long", day: "2-digit", month: "long" }) : `${dataBR(r.ini)} a ${dataBR(r.fim)}`;
  const at = r.assim, id = r.ideal;
  const marco = (tr, mes) => tr && tr[mes];

  el.innerHTML = `
    <div class="tela entra">
      <div class="rel-topo">
        <button class="icone-btn" id="voltar" aria-label="Voltar">←</button>
        <h2>📊 Seu relatório</h2>
      </div>
      <div class="seg">${Object.entries(PERIODOS).map(([k, v]) => `<button class="seg-b ${k === periodo ? "seg-b--on" : ""}" data-per="${k}">${v.nome}</button>`).join("")}</div>
      <p class="nota centro rel-datas">${esc(tituloPeriodo)}${r.qual === "dia" ? " · o dia ainda está rolando" : ""}</p>

      <div class="card rel-nota rel-nota--${corNota(r.nota)}">
        ${anel(r.nota, 100, { rotulo: `${r.nota}%`, sub: "da meta", tam: 132, espessura: 12 })}
        <div>
          <div class="card-tag">Aderência ao plano</div>
          <b class="rel-nota-txt">${rotuloNota(r.nota)}</b>
          <div class="rel-partes">${r.partes.map((x) => `<span>${x.nome} <b>${Math.round(x.valor * 100)}%</b></span>`).join("")}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-tag">🎯 Meta × realizado ${r.qual === "dia" ? "" : "(média por dia)"}</div>
        ${barra("Calorias", r.kcalMedia, m.kcal, "kcal")}
        ${barra("Proteína", r.protMedia, m.prot, "g")}
        ${r.planejados ? barra("Treinos", r.feitos, r.planejados, "", r.feitos > r.planejados ? `${r.feitos} feitos (${r.feitos - r.planejados} a mais que o plano 💪)` : `${r.feitos} de ${r.planejados} feitos`) : `<p class="nota">Nenhum treino planejado ${r.qual === "dia" ? "hoje (dia de descanso 😴)" : "no período"}.</p>`}
        ${barra("Água", r.aguaMedia, m.agua, "L", `${num(r.aguaMedia, 1)} / ${num(m.agua, 1)} L`)}
        ${r.passosMedia ? barra("Passos", r.passosMedia, cardio(p).passos, "") : ""}
        ${r.qual !== "dia" ? `<p class="nota">Dias com calorias na meta: <b>${r.diasKcalOk} de ${r.n}</b> · proteína ok: <b>${r.diasProtOk} de ${r.n}</b> · dias registrados: <b>${r.registrados} de ${r.n}</b></p>` : ""}
      </div>

      ${r.qual !== "dia" ? `
      <div class="card">
        <div class="card-tag">🍽️ Calorias por dia</div>
        ${graficoBarras(r.dias.map((x) => ({ rotulo: r.n > 7 ? String(+x.data.slice(8)) : dataBR(x.data, { weekday: "short" }).slice(0, 3), y: x.kcal, hoje: x.data === r.fim })), { meta: m.kcal })}
        <p class="nota">Linha vermelha = sua meta (${num(m.kcal)} kcal). Barras laranja = dias acima.</p>
      </div>` : ""}

      <div class="card card--destaque">
        <div class="card-tag">🔮 Se você continuar assim…</div>
        ${at ? `
          <p class="rel-frase">Com o que você ${r.qual === "dia" ? "fez hoje" : "fez nesse período"}, você atingiu <b>${r.nota}% da meta</b>. Mantendo esse ritmo, em <b>3 meses</b> você estará com <b>~${num(at[3].peso, 1)} kg</b>, <b>${num(at[3].gordura, 1)}% de gordura</b> e <b>${num(at[3].magra, 1)} kg de massa magra</b>.</p>
          <div class="rel-marcos">
            ${[1, 3, 6].map((mes) => `
              <div class="rel-marco">
                <small>${mes} ${mes === 1 ? "mês" : "meses"}</small>
                <b>${num(marco(at, mes).peso, 1)} kg</b>
                <span>${num(marco(at, mes).gordura, 1)}% gord.</span>
                <span>${sinal(marco(at, mes).magra - at[0].magra)} kg músculo</span>
              </div>`).join("")}
          </div>
          ${graficoProjecao(at, id)}
          <p class="rel-comparar">Cumprindo 100% do plano, em 3 meses: <b>~${num(id[3].peso, 1)} kg</b>, <b>${num(id[3].gordura, 1)}% de gordura</b> e <b>${sinal(id[3].magra - id[0].magra)} kg de músculo</b>.
            ${id[3].gordura < at[3].gordura - 0.3
              ? ` Seguir o plano te deixaria com <b>${num(at[3].gordura - id[3].gordura, 1)} pontos a menos de gordura</b>.`
              : id[3].magra - at[3].magra > 0.2
                ? ` Você está perdendo peso mais rápido que o plano, mas ganharia <b>${num(id[3].magra - at[3].magra, 1)} kg a mais de músculo</b> seguindo a meta — é o músculo que dá o formato do corpo.`
                : " Você está praticamente no ritmo do plano 👏"}</p>
          <p class="nota">Estimativa pelo seu balanço médio (${sinal(r.balanco, 0)} kcal/dia vs. gasto de ${num(m.gasto)}) e ${Math.round(Math.min(1, r.aderenciaTreino) * 100)}% dos treinos cumpridos. Serve pra mostrar a direção — os check-ins confirmam na prática.</p>
        ` : `<p>Registre suas refeições ${r.qual === "dia" ? "de hoje" : "no período"} pra ver onde esse ritmo te leva.</p>
             <p class="nota">Cumprindo 100% do plano, em 3 meses: ~${num(id[3].peso, 1)} kg e ${num(id[3].gordura, 1)}% de gordura.</p>`}
      </div>

      <div class="card">
        <div class="card-tag">💡 Dicas pra você</div>
        <div class="rel-dicas">${dicas.map((x) => `<div class="rel-dica"><span>${x.e}</span><p>${esc(x.t)}</p></div>`).join("")}</div>
        <button class="btn btn--sec btn--peq" id="nina">💬 Pedir análise da Nina (IA)</button>
        <div id="nina-resp"></div>
      </div>
    </div>`;

  el.querySelector("#voltar").onclick = () => ctx.ir("hoje");
  el.querySelectorAll("[data-per]").forEach((b) => b.onclick = () => { periodo = b.dataset.per; ctx.rerender(); });
  el.querySelector("#nina").onclick = async (ev) => {
    if (E.modoLocal) return toast("A análise da Nina precisa de uma conta.", "erro");
    ev.target.disabled = true;
    const box = el.querySelector("#nina-resp");
    box.innerHTML = carregando("A Nina está lendo seu relatório…");
    try {
      const resumo = {
        periodo: PERIODOS[r.qual].nome, dias: r.n, nota_aderencia: r.nota, kcal_media: r.kcalMedia, meta_kcal: m.kcal, gasto: m.gasto,
        proteina_media: r.protMedia, meta_proteina: m.prot, treinos: `${r.feitos}/${r.planejados}`, agua_media: r.aguaMedia, sono_medio: r.sonoMedia,
        dias_registrados: r.registrados, projecao_3_meses: r.assim ? r.assim[3] : null, dicas_do_app: dicas.map((x) => x.t),
      };
      const pergunta = `Analise meu relatório (${PERIODOS[r.qual].nome.toLowerCase()}) e me dê os 3 ajustes mais importantes, bem práticos, pro próximo período.`;
      const resp = await conversar({ agente: "nutri", historico: [{ papel: "user", texto: pergunta }], contexto: { perfil: resumoPerfil(p), metas: m, relatorio: resumo } });
      box.innerHTML = `<div class="dica-ia">🥗 <span>${esc(resp.resposta).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>")}</span></div>`;
    } catch (e) {
      box.innerHTML = `<p class="erro-txt">${esc(e.message)}</p>`;
      ev.target.disabled = false;
    }
  };
}
