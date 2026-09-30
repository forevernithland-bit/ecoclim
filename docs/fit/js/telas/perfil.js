// Perfil: dados, metas, objetivo/físico-alvo, conta e exportação.
import { esc, num, toast, confirmar, abrirSheet, temaAtual, aplicarTema } from "../ui.js";
import { OBJETIVOS, FISICOS, estimarTempoFisico, formatarMeses, imc, ffmi, projecaoObjetivo } from "../ciencia.js";
import { E, salvarPerfil, metasAtuais, listar } from "../estado.js";
import { usuarioAtual, sair, pendentes, sincronizar } from "../nuvem.js";
import { abrirSuplementos } from "./comida.js";
import { limparTudo, kvSet } from "../db.js";
import { VERSAO } from "../versao.js";
import { editorGostos } from "../gostos.js";
import { instalar, rodandoInstalado } from "../instalar.js";
import { editorMedicamento } from "../medicamentos.js";

export async function telaPerfil(el, ctx) {
  const p = E.perfil;
  const m = metasAtuais();
  const user = E.modoLocal ? null : await usuarioAtual();
  const fisico = FISICOS[p.sexo].find((f) => f.id === p.fisicoAlvo) || FISICOS[p.sexo][1];
  const est = estimarTempoFisico(p, fisico);
  const pend = await pendentes();

  el.innerHTML = `
    <div class="tela entra">
      <div class="perfil-topo">
        <div class="avatar avatar--g">${esc(p.nome.slice(0, 1).toUpperCase())}</div>
        <div><h1>${esc(p.nome)}</h1><small>${p.idade} anos · ${p.altura} cm · ${num(p.peso, 1)} kg</small></div>
      </div>

      <div class="grade-3">
        <div class="mini"><small>IMC</small><b>${num(imc(p.peso, p.altura), 1)}</b></div>
        <div class="mini"><small>Gordura</small><b>${num(p.gordura, 1)}%</b></div>
        <div class="mini"><small>FFMI</small><b>${num(ffmi(p.peso, p.altura, p.gordura), 1)}</b></div>
      </div>

      <div class="card">
        <div class="card-tag">🎯 Objetivo</div>
        <div class="chips-rolar">${Object.entries(OBJETIVOS).map(([k, o]) => `<button class="chip ${p.objetivo === k ? "chip--on" : ""}" data-obj="${k}">${o.emoji} ${o.rotulo}</button>`).join("")}</div>
        <label class="rotulo">Peso meta</label>
        <div class="campo-unid campo-unid--mini"><input class="campo" id="pesoMeta" type="number" inputmode="decimal" step="0.1" value="${esc(p.pesoMeta || "")}" placeholder="–"><span>kg</span></div>
        <div id="meta-info">${infoPesoMeta(p, p.pesoMeta)}</div>
        <label class="rotulo">Físico de referência</label>
        <div class="chips-rolar">${FISICOS[p.sexo].map((f) => `<button class="chip ${fisico.id === f.id ? "chip--on" : ""}" data-fis="${f.id}">${f.nome}</button>`).join("")}</div>
        <p class="nota">Tempo até o físico "${esc(fisico.nome)}" (pela gordura e massa muscular do modelo, não pelo peso): <b>${est.inalcancavel ? "fora do alcance natural" : `${formatarMeses(est.minimo)} a ${formatarMeses(est.maximo)}`}</b></p>
      </div>

      <div class="card">
        <div class="card-tag">🥗 Suas metas diárias</div>
        <div class="kcal-grande">${num(m.kcal)} <small>kcal</small></div>
        <div class="macros-linha"><span class="pill pill--p">P ${m.prot} g</span><span class="pill pill--c">C ${m.carb} g</span><span class="pill pill--g">G ${m.gord} g</span><span class="pill">Fibra ${m.fibra} g</span></div>
        <p class="nota">${esc(m.explic)}</p>
        <p class="nota">ℹ️ As metas do dia usam seu <b>peso atual</b> (${num(p.peso, 1)} kg) e o <b>objetivo</b> — o peso meta não muda as calorias, só o prazo. Conforme você registra o peso em Hoje → "Peso de hoje", tudo se recalcula.</p>
        <details class="calc">
          <summary>🔬 Como suas metas são calculadas</summary>
          <ol class="calc-passos">
            <li><b>Gasto em repouso (TMB):</b> ${num(m.tmb)} kcal — fórmula de Mifflin-St Jeor com seu peso (${num(p.peso, 1)} kg), altura (${p.altura} cm), idade (${p.idade}) e sexo.</li>
            <li><b>Atividade:</b> × ${String(m.fator).replace(".", ",")} pelos ${p.diasTreino || 3} treinos/semana = ${num(Math.round(m.tmb * m.fator))} kcal.</li>
            <li><b>Passos:</b> ${m.passos ? `${m.passos > 0 ? "+" : ""}${num(m.passos)} kcal pela sua média de ${num(p.calibracao.passosMedia)} passos/dia` : "registre seus passos em Métricas pra ajustar (hoje considera ~7.000/dia)"}.</li>
            <li><b>Calibração pelos seus dados:</b> ${m.calibrado ? `✅ gasto real medido ~${num(m.gastoReal)} kcal (comida registrada × variação do peso em ${p.calibracao.dias} dias) — misturado com a fórmula` : "ainda não — com 2 semanas registrando comida e se pesando, o app mede seu gasto real e ajusta sozinho"}.</li>
            <li><b>Gasto total considerado:</b> ${num(m.gasto)} kcal/dia.</li>
            <li><b>Meta de calorias:</b> ${num(m.kcal)} kcal (${m.deficit > 0 ? "+" : ""}${num(m.deficit)} kcal/dia pro seu objetivo).</li>
            <li><b>Proteína:</b> ${m.prot} g = ${String(m.protPorKg).replace(".", ",")} g/kg de peso ou ${String(m.protPorMagra).replace(".", ",")} g/kg da sua massa magra (${num(m.magra, 1)} kg). Faixa científica pra você: ${m.protFaixa[0]}–${m.protFaixa[1]} g.</li>
            ${m.medicamento ? `<li><b>💉 Ajuste pelo ${esc(m.medicamento.nome)}:</b> piso mínimo de ${num(m.pisoKcal)} kcal, déficit limitado a ~25%, proteína ≥ 1,6 g/kg do peso de referência (${m.protRefeicao} g por refeição), gordura 25%, fibra ${m.fibra} g e +0,5 L de água (aviso conjunto ACLM/ASN/OMA/TOS 2025).</li>` : ""}
            <li><b>Gordura:</b> ${m.gord} g (${m.medicamento ? 25 : 27}% das calorias — faixa saudável 20–35%). <b>Carboidrato:</b> o restante, ${m.carb} g (energia pro treino).</li>
          </ol>
          <p class="nota">Tudo se recalcula sozinho quando seu peso, seus passos ou seus registros mudam.</p>
          <button class="btn btn--sec btn--peq" id="revisar-metas">💬 Pedir pra Nina revisar minhas metas</button>
        </details>
      </div>

      <div class="card">
        <div class="card-tag">🍽️ Gostos alimentares</div>
        <p class="nota">A Nina nunca sugere o que você não gosta e troca por algo equivalente. Se você contar pra ela no chat, ela anota aqui sozinha.</p>
        <div id="editor-gostos"></div>
      </div>

      <div class="card">
        <div class="card-tag">💉 Remédio para emagrecer</div>
        <p class="nota">Usa Mounjaro, Ozempic, Wegovy, Saxenda ou similar? O app adapta proteína, calorias, fibra, água e treino pro que a ciência recomenda pra quem usa.</p>
        <div id="editor-med"></div>
      </div>

      <button class="card card--link" id="supl"><span class="card-tag">💊 Suplementos recomendados</span><span class="nota">Com nível de evidência científica ›</span></button>

      <div class="card">
        <div class="card-tag">📲 App no celular</div>
        ${rodandoInstalado()
          ? `<p class="nota">✅ Instalado. As atualizações chegam sozinhas sempre que você abre o app.</p>`
          : `<p class="nota">Instale para abrir como app, com ícone na tela inicial. As atualizações chegam sozinhas.</p><button class="btn btn--peq" id="instalar">📲 Instalar app</button>`}
        <button class="link link--fraco" id="buscar-atualizacao">Procurar atualização agora</button>
      </div>

      <div class="card">
        <div class="card-tag">🎨 Aparência</div>
        <div class="seg seg--mini">
          ${[["auto", "Automático"], ["light", "☀️ Claro"], ["dark", "🌙 Escuro"]].map(([k, t]) => `<button class="seg-b ${temaAtual() === k ? "seg-b--on" : ""}" data-tema="${k}">${t}</button>`).join("")}
        </div>
        <p class="nota">Automático segue o tema do seu celular.</p>
      </div>

      <div class="card">
        <div class="card-tag">☁️ Conta e backup</div>
        ${user
          ? `<p>${esc(user.email.endsWith("@evolua.app") ? user.email.replace("@evolua.app", "") : user.email)}</p><p class="nota">${pend ? `${pend} alteração(ões) aguardando envio.` : "Tudo salvo na nuvem ✅"}</p>
             <div class="linha-botoes"><button class="btn btn--sec btn--peq" id="sync">Sincronizar</button><button class="btn btn--sec btn--peq" id="sair">Sair</button></div>`
          : `<p class="nota">Modo teste: seus dados estão só neste aparelho e a IA fica desligada.</p><button class="btn btn--peq" id="entrar">Criar conta / entrar</button>`}
        <button class="btn btn--sec btn--peq" id="exportar">⬇️ Exportar meus dados (JSON)</button>
      </div>

      <p class="aviso">Este app é educativo e não substitui médico, nutricionista ou educador físico. Com doenças, gravidez ou uso de remédios, procure acompanhamento profissional.</p>
      <p class="assinatura">Evolua · versão ${VERSAO}<br>Desenvolvido por <b>Breno Lima</b></p>
    </div>`;

  el.querySelectorAll("[data-obj]").forEach((b) => b.onclick = async () => { await salvarPerfil({ ...p, objetivo: b.dataset.obj }); toast("Objetivo atualizado — metas recalculadas"); ctx.rerender(); });
  el.querySelectorAll("[data-fis]").forEach((b) => b.onclick = async () => { await salvarPerfil({ ...p, fisicoAlvo: b.dataset.fis }); ctx.rerender(); });
  let tMeta = null;
  el.querySelector("#pesoMeta").oninput = (e) => {
    const v = +String(e.target.value).replace(",", ".") || null;
    el.querySelector("#meta-info").innerHTML = infoPesoMeta(E.perfil, v);
    const bt = el.querySelector("#trocar-obj");
    if (bt) bt.onclick = async () => { clearTimeout(tMeta); await salvarPerfil({ ...E.perfil, objetivo: bt.dataset.obj, pesoMeta: v }); toast("Objetivo atualizado — metas recalculadas"); ctx.rerender(); };
    clearTimeout(tMeta);
    tMeta = setTimeout(async () => { if (v === null || (v >= 30 && v <= 300)) { await salvarPerfil({ ...E.perfil, pesoMeta: v }); toast("Peso meta salvo ✅"); } }, 900);
  };
  el.querySelector("#pesoMeta").dispatchEvent(new Event("input"));
  clearTimeout(tMeta);
  el.querySelector("#supl").onclick = abrirSuplementos;
  el.querySelector("#revisar-metas").onclick = () => ctx.ir("coach", { agente: "nutri", pergunta: `Revise minhas metas como nutricionista: ${m.kcal} kcal, ${m.prot} g de proteína, ${m.carb} g de carboidrato e ${m.gord} g de gordura por dia (gasto estimado ${m.gasto} kcal). Estão adequadas pro meu objetivo, peso e rotina? Se algo estiver fora, diga o que ajustaria e por quê.` });
  const bInst = el.querySelector("#instalar");
  if (bInst) bInst.onclick = instalar;
  el.querySelector("#buscar-atualizacao").onclick = async () => {
    toast("Procurando atualização…");
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      if (reg) await reg.update();
      setTimeout(() => { if (!window.__recarregando) toast(`Você está na versão mais nova (${VERSAO}) ✅`); }, 3000);
    } catch (e) { toast("Sem internet agora — tento de novo depois.", "erro"); }
  };
  el.querySelectorAll("[data-tema]").forEach((b) => b.onclick = () => {
    aplicarTema(b.dataset.tema);
    el.querySelectorAll("[data-tema]").forEach((x) => x.classList.toggle("seg-b--on", x === b));
  });
  const gostos = { naoGosta: [...(p.naoGosta || [])], dietas: [...(p.dietas || ["tudo"])], alergias: p.alergias || "" };
  let tGostos = null;
  editorGostos(el.querySelector("#editor-gostos"), gostos, () => {
    clearTimeout(tGostos);
    tGostos = setTimeout(async () => {
      await salvarPerfil({ ...E.perfil, ...gostos, gostosPerguntados: true });
      toast("Preferências salvas ✅");
    }, 700);
  });
  const med = { medicamento: p.medicamento ? { ...p.medicamento } : null };
  let tMed = null;
  editorMedicamento(el.querySelector("#editor-med"), med, () => {
    clearTimeout(tMed);
    tMed = setTimeout(async () => {
      await salvarPerfil({ ...E.perfil, medicamento: med.medicamento });
      toast("Salvo — metas recalculadas ✅");
    }, 800);
  });
  const bs = el.querySelector("#sync");
  if (bs) bs.onclick = async () => { await sincronizar(); toast("Sincronizado"); ctx.rerender(); };
  const bsair = el.querySelector("#sair");
  if (bsair) bsair.onclick = async () => {
    const n = await pendentes();
    if (!(await confirmar(n ? `Há ${n} alteração(ões) ainda não enviadas. Sair apaga os dados deste aparelho. Continuar?` : "Sair da conta? Os dados continuam salvos na nuvem.", { ok: "Sair", perigo: !!n }))) return;
    await sair(); await limparTudo(); location.reload();
  };
  const be = el.querySelector("#entrar");
  if (be) be.onclick = async () => { await kvSet("modoLocal", false); await kvSet("querConta", true); location.reload(); };
  el.querySelector("#exportar").onclick = async () => {
    const dados = { perfil: E.perfil, plano: E.plano, prefs: E.prefs };
    for (const s of ["refeicoes", "checkins", "treinos", "metricas", "comparativos"]) {
      dados[s] = (await listar(s)).map((r) => { const c = { ...r }; for (const k of Object.keys(c)) if (c[k] instanceof Blob) c[k] = "[foto]"; return c; });
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(dados, null, 2)], { type: "application/json" }));
    a.download = `meus-dados-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  };
}

// Prazo até o peso meta + coerência com o objetivo (atualiza enquanto digita).
function infoPesoMeta(p, meta) {
  if (!meta || meta < 30 || meta > 300) return `<p class="nota">Digite o peso que você quer chegar pra ver o prazo estimado.</p>`;
  const pr = projecaoObjetivo(p, meta);
  const dif = meta - p.peso;
  const partes = [];
  if (Math.abs(dif) < 0.5) partes.push(`<p class="nota">Você já está no peso meta 🎯 — agora o foco é composição (menos gordura, mais músculo).</p>`);
  else if (pr.conflito) partes.push(`<p class="aviso">⚠️ ${esc(pr.texto)}</p>`);
  else if (pr.semanas) partes.push(`<p class="nota">${dif > 0 ? "📈" : "📉"} ${dif > 0 ? "+" : ""}${num(dif, 1)} kg · tempo médio até ${num(meta, 1)} kg: <b>${formatarMeses(Math.round(pr.semanas / 4.35))}</b> <small>(${pr.semanas} semanas)</small></p><p class="nota">${esc(pr.texto)}</p>`);
  else partes.push(`<p class="nota">${esc(pr.texto)}</p>`);
  if (pr.lento) partes.push(`<button class="link" id="trocar-obj" data-obj="${pr.lento}">Quer chegar mais rápido? Mudar objetivo para "${esc(OBJETIVOS[pr.lento].rotulo)}" ›</button>`);
  if (imc(meta, p.altura) < 18.5) partes.push(`<p class="aviso">⚠️ ${num(meta, 1)} kg deixaria seu IMC abaixo de 18,5 (abaixo do peso saudável).</p>`);
  return partes.join("");
}
