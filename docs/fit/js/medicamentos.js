// Medicamentos para obesidade da família dos "análogos de incretina" (GLP-1,
// GIP/GLP-1, GIP/GLP-1/glucagon): tirzepatida (Mounjaro), semaglutida
// (Ozempic/Wegovy), liraglutida (Saxenda), retatrutida (em estudo)…
//
// O app NÃO sugere dose nem remédio — isso é do médico. O que ele faz é
// ajustar a NUTRIÇÃO e o TREINO pro que a ciência mais atual recomenda pra
// quem usa esses medicamentos:
//  • Aviso conjunto ACLM/ASN/OMA/TOS 2025 (Mozaffarian et al., Obesity/AJCN):
//    proteína 1,2–1,6 g/kg (peso ajustado), 25–30 g por refeição, fibra,
//    hidratação, micronutrientes, treino de força ≥ 2–3x/semana.
//  • SURMOUNT-1 (tirzepatida), STEP-1 (semaglutida), SCALE (liraglutida),
//    fase 2 da retatrutida (NEJM 2023): perda média e composição da perda.
//  • 25–40% do peso perdido pode ser massa magra se não houver proteína +
//    treino de força (DXA dos estudos STEP-1/SURMOUNT-1).
//  • Ao parar, sem mudança de hábitos, ~2/3 do peso volta em 1 ano
//    (extensão do STEP-1, 2022).
import { esc, num } from "./ui.js";
import { todos, hojeISO } from "./db.js";

export const MEDICAMENTOS = [
  { id: "tirzepatida", nome: "Tirzepatida", marcas: "Mounjaro / Zepbound", classe: "GIP + GLP-1", freq: "semanal", via: "injeção",
    estudo: "Perda média de 15–21% do peso em 72 semanas (estudo SURMOUNT-1).", aprovado: true },
  { id: "semaglutida", nome: "Semaglutida injetável", marcas: "Ozempic / Wegovy", classe: "GLP-1", freq: "semanal", via: "injeção",
    estudo: "Perda média de ~15% do peso em 68 semanas na dose de 2,4 mg (estudo STEP-1).", aprovado: true },
  { id: "semaglutida_oral", nome: "Semaglutida oral", marcas: "Rybelsus / comprimido", classe: "GLP-1", freq: "diário", via: "comprimido",
    estudo: "Tomar em jejum com até 120 ml de água e esperar 30 min pra comer ou tomar outros remédios — senão quase não é absorvida.", aprovado: true },
  { id: "liraglutida", nome: "Liraglutida", marcas: "Saxenda / Victoza", classe: "GLP-1", freq: "diário", via: "injeção",
    estudo: "Perda média de ~8% do peso em 56 semanas (estudo SCALE).", aprovado: true },
  { id: "retatrutida", nome: "Retatrutida", marcas: "em pesquisa", classe: "GIP + GLP-1 + glucagon", freq: "semanal", via: "injeção",
    estudo: "Até ~24% de perda em 48 semanas no estudo de fase 2 (NEJM 2023). Ainda em estudos de fase 3 — sem aprovação para venda no Brasil.", aprovado: false },
  { id: "outro", nome: "Outro da mesma família", marcas: "GLP-1 / análogo", classe: "incretina", freq: "semanal", via: "injeção",
    estudo: "", aprovado: true },
];
export const medicamento = (id) => MEDICAMENTOS.find((m) => m.id === id) || null;

export const FASES = [
  { id: "inicio", nome: "Começando / subindo dose", desc: "Primeiros 2–3 meses: mais náusea, fome some" },
  { id: "manutencao", nome: "Dose estável", desc: "Já me adaptei ao remédio" },
  { id: "parando", nome: "Reduzindo ou parei", desc: "Parei há menos de 6 meses ou estou desmamando" },
];

export const EFEITOS = [
  { id: "nausea", nome: "Náusea", dica: "Refeições menores e mais frequentes, comer devagar e parar no primeiro sinal de saciedade. Evite fritura e comida muito gordurosa (piora o enjoo). Chá de gengibre ajuda." },
  { id: "semfome", nome: "Sem fome nenhuma", dica: "Coma por horário, não por fome: comece SEMPRE pela proteína. Iogurte proteico, ovo, whey e shakes entram fácil quando nada desce." },
  { id: "intestino", nome: "Intestino preso", dica: "Aumente a água (+500 ml/dia) e a fibra aos poucos: aveia, chia, frutas com casca, feijão, psyllium. Caminhar depois das refeições também ajuda." },
  { id: "refluxo", nome: "Refluxo / azia", dica: "Não deite nas 3 h depois de comer, evite refeição grande à noite, café forte, hortelã, álcool e fritura." },
  { id: "diarreia", nome: "Diarreia", dica: "Reponha água e sais (soro caseiro ou isotônico sem açúcar). Diminua gordura e adoçantes tipo sorbitol/xilitol." },
  { id: "cansaco", nome: "Cansaço / fraqueza", dica: "Quase sempre é comer pouco demais (principalmente carboidrato e proteína) ou pouca água. Confira se está acima do piso de calorias do app." },
];

// Ajuste das metas. `base` = metas calculadas normalmente (ciencia.metas).
export function ajustarMetas(p, base) {
  const med = p.medicamento && medicamento(p.medicamento.id);
  if (!med) return base;
  const fase = p.medicamento.fase || "manutencao";
  const m = { ...base, medicamento: med, fase };
  // Piso de calorias: o remédio tira a fome — o risco passa a ser comer DE MENOS
  // (perda de músculo, queda de cabelo, cálculo na vesícula, carência de nutrientes).
  m.pisoKcal = Math.round(Math.max(p.sexo === "M" ? 1500 : 1200, base.tmb * 0.8) / 10) * 10;
  if (fase === "parando") {
    // saída do remédio: perto da manutenção + proteína e treino = segurar o peso
    m.kcal = Math.round(Math.max(base.kcal, base.gasto * 0.95) / 10) * 10;
    m.explic = "Fase de saída do remédio: calorias perto da manutenção, proteína alta e treino de força — é o que mais evita o reganho de peso (sem isso, ~2/3 do peso costuma voltar em 1 ano).";
  } else {
    // déficit nunca maior que ~25% (a fome baixa deixa fácil exagerar)
    m.kcal = Math.round(Math.max(m.pisoKcal, base.kcal, base.gasto * 0.75) / 10) * 10;
    m.explic = `${base.explic} Com ${med.nome}, a fome cai muito: a meta é o quanto você DEVE comer, não um limite. Abaixo de ${m.pisoKcal} kcal por dia você começa a perder músculo.`;
  }
  // Proteína: pelo menos 1,6 g/kg do peso de referência (massa magra ÷ 0,75 ≈ peso "sem o excesso")
  const pesoRef = Math.min(p.peso, base.magra / 0.75);
  m.prot = Math.max(base.prot, Math.round(pesoRef * 1.6));
  m.protRefeicao = 30;
  // Menos gordura (esvaziamento do estômago já está lento → gordura piora náusea/refluxo)
  m.gord = Math.round((m.kcal * 0.25) / 9);
  m.carb = Math.max(50, Math.round((m.kcal - m.prot * 4 - m.gord * 9) / 4));
  m.fibra = Math.max(base.fibra, p.sexo === "M" ? 30 : 25);
  m.agua = Math.round((base.agua + 0.5) * 10) / 10;
  m.protPorKg = Math.round((m.prot / p.peso) * 100) / 100;
  m.deficit = m.kcal - base.gasto;
  return m;
}

// Orientação resumida que vai pro contexto da Nina/Léo.
export function orientacaoIA(p) {
  const med = p && p.medicamento && medicamento(p.medicamento.id);
  if (!med) return null;
  const efeitos = (p.medicamento.efeitos || []).map((e) => EFEITOS.find((x) => x.id === e)?.nome).filter(Boolean);
  return {
    nome: `${med.nome} (${med.marcas}) — ${med.classe}, ${med.freq}`,
    fase: (FASES.find((f) => f.id === p.medicamento.fase) || FASES[1]).nome,
    dose_prescrita: p.medicamento.dose || "não informada",
    efeitos_colaterais: efeitos,
    regras: "Usuário usa medicamento para obesidade. NUNCA sugira, altere ou comente dose — isso é do médico. Priorize: proteína em toda refeição (25–30 g, comece o prato por ela), não ficar abaixo do piso de calorias, fibra e água, refeições menores, pouca fritura/gordura, treino de força 2–3x/semana pra não perder músculo (Léo: foco em manter carga, progressão conservadora nos dias de mais enjoo). Se relatar vômitos persistentes, dor abdominal forte (pode ser pancreatite/vesícula), desidratação ou desmaio, oriente procurar o médico imediatamente."
      + (med.aprovado ? "" : " Esse medicamento ainda está em estudo e sem aprovação: reforce que só deve ser usado em pesquisa clínica ou com médico, nunca comprado de 'peptídeos' pela internet (sem garantia do que tem dentro)."),
  };
}

// Alertas pro card da tela Hoje.
export async function alertasMedicamento(p, metasDia) {
  const med = p && p.medicamento && medicamento(p.medicamento.id);
  if (!med) return [];
  const al = [];
  const hoje = hojeISO();
  const dia = new Date().getDay();
  if (med.freq === "semanal" && p.medicamento.diaAplicacao != null && +p.medicamento.diaAplicacao === dia) {
    al.push({ nivel: "info", texto: "💉 Hoje é dia da aplicação. Nos 2–3 dias seguintes a fome costuma sumir: deixe proteína pronta (ovo, iogurte, frango, whey)." });
  }
  if (!med.aprovado) {
    al.push({ nivel: "atencao", texto: `${med.nome} ainda está em estudo, sem aprovação no Brasil. Use só com médico/pesquisa clínica — "peptídeos" vendidos pela internet não têm garantia do que contêm.` });
  }
  // Comendo abaixo do piso nos últimos dias completos?
  const refs = await todos("refeicoes");
  const porDia = {};
  for (const r of refs) if (r.data < hoje) porDia[r.data] = (porDia[r.data] || 0) + (r.kcal || 0);
  const ultimos = Object.entries(porDia).sort(([a], [b]) => (a < b ? 1 : -1)).slice(0, 5).map(([, k]) => k).filter((k) => k >= 300);
  if (ultimos.length >= 3 && metasDia.pisoKcal) {
    const media = ultimos.reduce((a, b) => a + b, 0) / ultimos.length;
    if (media < metasDia.pisoKcal) al.push({ nivel: "alerta", texto: `Sua média nos últimos dias foi ~${Math.round(media)} kcal — abaixo do piso seguro (${metasDia.pisoKcal}). Com o remédio isso vira perda de MÚSCULO, não só de gordura. Some um shake de proteína ou um lanche com iogurte/ovo.` });
  }
  // Perdendo rápido demais?
  const ritmo = p.calibracao && p.calibracao.ritmoSemana;
  if (ritmo != null && ritmo < -(p.peso * 0.01)) {
    al.push({ nivel: "alerta", texto: `Você está perdendo ~${Math.abs(ritmo).toFixed(1).replace(".", ",")} kg/semana (mais de 1% do peso). Acima disso cresce a perda de músculo e o risco de pedra na vesícula: capriche na proteína, não pule treino de força e converse com seu médico.` });
  }
  for (const e of p.medicamento.efeitos || []) {
    const ef = EFEITOS.find((x) => x.id === e);
    if (ef) al.push({ nivel: "dica", texto: `${ef.nome}: ${ef.dica}` });
  }
  return al;
}

// Guia completo (sheet "Seu tratamento").
export function htmlGuia(p, m) {
  const med = medicamento(p.medicamento.id);
  return `
    <h2>💉 ${esc(med.nome)} + Evolua</h2>
    <p class="sub">${esc(med.marcas)} · ${esc(med.classe)} · ${esc(med.via)} ${esc(med.freq)}</p>
    ${med.estudo ? `<p class="nota">📚 ${esc(med.estudo)}</p>` : ""}
    <div class="aviso">O app não indica nem ajusta dose — isso é só com seu médico. Aqui a gente cuida da comida e do treino pra que o peso perdido seja GORDURA, não músculo.</div>
    <h3>O que mudou nas suas metas</h3>
    <ul class="lista-simples">
      <li><b>Calorias: ${num(m.kcal)} kcal</b> — e nunca abaixo de <b>${num(m.pisoKcal)} kcal</b>. O remédio tira a fome; o risco agora é comer de menos.</li>
      <li><b>Proteína: ${num(m.prot)} g/dia</b>, ~${m.protRefeicao} g em cada refeição. Comece o prato pela proteína.</li>
      <li><b>Gordura: ${m.gord} g</b> (um pouco menor) — comida gordurosa piora enjoo e refluxo com o estômago mais lento.</li>
      <li><b>Fibra: ${m.fibra} g</b> e <b>água: ${String(m.agua).replace(".", ",")} L</b> — contra o intestino preso, o efeito mais comum.</li>
    </ul>
    <h3>Por que o treino de força é obrigatório</h3>
    <p class="nota">Nos estudos, 25–40% do peso perdido com esses remédios foi massa magra quando a pessoa não treinava. Músculo perdido = metabolismo mais baixo e reganho mais fácil. Treino de força 2–3x/semana + proteína reduz muito essa perda.</p>
    <h3>Quando parar o remédio</h3>
    <p class="nota">Sem mudar hábitos, cerca de 2/3 do peso volta em 1 ano. Por isso o app ensina a montar o prato e mede seu gasto real: quando marcar "Reduzindo ou parei", suas metas mudam pra segurar o resultado.</p>
    <h3>Procure o médico já se tiver</h3>
    <p class="nota">Vômitos que não param, dor forte na barriga (pode irradiar pras costas), pele/olhos amarelados, sinais de desidratação ou desmaio.</p>`;
}

// Editor (cadastro e Perfil). `st` é mutado; aoMudar() a cada alteração.
export function editorMedicamento(el, st, aoMudar = () => {}) {
  const pinta = () => {
    const med = st.medicamento && medicamento(st.medicamento.id);
    const mm = st.medicamento || {};
    el.innerHTML = `
      <div class="chips-quebra">
        <button type="button" class="chip ${!med ? "chip--on" : ""}" data-med="">Não uso</button>
        ${MEDICAMENTOS.map((x) => `<button type="button" class="chip ${med && med.id === x.id ? "chip--on" : ""}" data-med="${x.id}">${esc(x.nome)}${x.marcas && x.id !== "outro" ? ` <small>(${esc(x.marcas)})</small>` : ""}</button>`).join("")}
      </div>
      ${med ? `
        ${!med.aprovado ? `<p class="aviso">⚠️ ${esc(med.estudo)} Use só com acompanhamento médico.</p>` : ""}
        <label class="rotulo">Em que fase você está?</label>
        <div class="opcoes">${FASES.map((f) => `<button type="button" class="opcao opcao--linha ${(mm.fase || "manutencao") === f.id ? "opcao--on" : ""}" data-fase="${f.id}"><span><b>${f.nome}</b><small>${f.desc}</small></span></button>`).join("")}</div>
        ${med.freq === "semanal" ? `
          <label class="rotulo">Dia da aplicação</label>
          <div class="dias-sel">${["D", "S", "T", "Q", "Q", "S", "S"].map((d, i) => `<button type="button" class="dia-b ${+mm.diaAplicacao === i && mm.diaAplicacao != null ? "dia-b--on" : ""}" data-apl="${i}">${d}</button>`).join("")}</div>` : ""}
        <label class="rotulo">Dose prescrita pelo médico (opcional, só pra seu controle)</label>
        <input class="campo" id="med-dose" placeholder="Ex.: 5 mg" value="${esc(mm.dose || "")}">
        <label class="rotulo">Sente algum destes? (o app dá dicas pra cada um)</label>
        <div class="chips-quebra">${EFEITOS.map((e) => `<button type="button" class="chip ${(mm.efeitos || []).includes(e.id) ? "chip--on" : ""}" data-ef="${e.id}">${e.nome}</button>`).join("")}</div>
        <p class="nota">Com o remédio marcado, o app sobe a proteína, cria um piso mínimo de calorias, aumenta fibra e água e avisa se você perder peso rápido demais.</p>` : ""}`;
    el.querySelectorAll("[data-med]").forEach((b) => b.onclick = () => {
      const id = b.dataset.med;
      st.medicamento = id ? { fase: "inicio", efeitos: [], ...(st.medicamento || {}), id } : null;
      pinta(); aoMudar();
    });
    el.querySelectorAll("[data-fase]").forEach((b) => b.onclick = () => { st.medicamento.fase = b.dataset.fase; pinta(); aoMudar(); });
    el.querySelectorAll("[data-apl]").forEach((b) => b.onclick = () => { st.medicamento.diaAplicacao = +b.dataset.apl; pinta(); aoMudar(); });
    el.querySelectorAll("[data-ef]").forEach((b) => b.onclick = () => {
      const l = st.medicamento.efeitos || [];
      st.medicamento.efeitos = l.includes(b.dataset.ef) ? l.filter((x) => x !== b.dataset.ef) : [...l, b.dataset.ef];
      pinta(); aoMudar();
    });
    const dose = el.querySelector("#med-dose");
    if (dose) dose.oninput = () => { st.medicamento.dose = dose.value.trim(); aoMudar(); };
  };
  pinta();
}
