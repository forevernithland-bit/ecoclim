// Perfil: dados, metas, objetivo/físico-alvo, conta e exportação.
import { esc, num, toast, confirmar, abrirSheet } from "../ui.js";
import { OBJETIVOS, FISICOS, estimarTempoFisico, formatarMeses, imc, ffmi } from "../ciencia.js";
import { E, salvarPerfil, metasAtuais, listar } from "../estado.js";
import { usuarioAtual, sair, pendentes, sincronizar } from "../nuvem.js";
import { abrirSuplementos } from "./comida.js";
import { limparTudo, kvSet } from "../db.js";
import { VERSAO } from "../versao.js";
import { editorGostos } from "../gostos.js";

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
        <label class="rotulo">Físico de referência</label>
        <div class="chips-rolar">${FISICOS[p.sexo].map((f) => `<button class="chip ${fisico.id === f.id ? "chip--on" : ""}" data-fis="${f.id}">${f.nome}</button>`).join("")}</div>
        <p class="nota">Tempo estimado hoje até "${esc(fisico.nome)}": <b>${est.inalcancavel ? "fora do alcance natural" : `${formatarMeses(est.minimo)} a ${formatarMeses(est.maximo)}`}</b></p>
      </div>

      <div class="card">
        <div class="card-tag">🥗 Suas metas diárias</div>
        <div class="kcal-grande">${num(m.kcal)} <small>kcal</small></div>
        <div class="macros-linha"><span class="pill pill--p">P ${m.prot} g</span><span class="pill pill--c">C ${m.carb} g</span><span class="pill pill--g">G ${m.gord} g</span><span class="pill">Fibra ${m.fibra} g</span></div>
        <p class="nota">Gasto basal ${num(m.tmb)} kcal · gasto total ~${num(m.gasto)} kcal. ${esc(m.explic)}</p>
        <p class="nota">As metas se recalculam sozinhas quando seu peso muda.</p>
      </div>

      <div class="card">
        <div class="card-tag">🍽️ Gostos alimentares</div>
        <p class="nota">A Nina nunca sugere o que você não gosta e troca por algo equivalente. Se você contar pra ela no chat, ela anota aqui sozinha.</p>
        <div id="editor-gostos"></div>
      </div>

      <button class="card card--link" id="supl"><span class="card-tag">💊 Suplementos recomendados</span><span class="nota">Com nível de evidência científica ›</span></button>

      <div class="card">
        <div class="card-tag">☁️ Conta e backup</div>
        ${user
          ? `<p>${esc(user.email)}</p><p class="nota">${pend ? `${pend} alteração(ões) aguardando envio.` : "Tudo salvo na nuvem ✅"}</p>
             <div class="linha-botoes"><button class="btn btn--sec btn--peq" id="sync">Sincronizar</button><button class="btn btn--sec btn--peq" id="sair">Sair</button></div>`
          : `<p class="nota">Modo teste: seus dados estão só neste aparelho e a IA fica desligada.</p><button class="btn btn--peq" id="entrar">Criar conta / entrar</button>`}
        <button class="btn btn--sec btn--peq" id="exportar">⬇️ Exportar meus dados (JSON)</button>
      </div>

      <p class="aviso">Este app é educativo e não substitui médico, nutricionista ou educador físico. Com doenças, gravidez ou uso de remédios, procure acompanhamento profissional.</p>
      <p class="nota centro">Versão ${VERSAO}</p>
    </div>`;

  el.querySelectorAll("[data-obj]").forEach((b) => b.onclick = async () => { await salvarPerfil({ ...p, objetivo: b.dataset.obj }); toast("Objetivo atualizado — metas recalculadas"); ctx.rerender(); });
  el.querySelectorAll("[data-fis]").forEach((b) => b.onclick = async () => { await salvarPerfil({ ...p, fisicoAlvo: b.dataset.fis }); ctx.rerender(); });
  el.querySelector("#pesoMeta").onchange = async (e) => { await salvarPerfil({ ...p, pesoMeta: +String(e.target.value).replace(",", ".") || null }); toast("Peso meta salvo"); };
  el.querySelector("#supl").onclick = abrirSuplementos;
  const gostos = { naoGosta: [...(p.naoGosta || [])], dietas: [...(p.dietas || ["tudo"])], alergias: p.alergias || "" };
  let tGostos = null;
  editorGostos(el.querySelector("#editor-gostos"), gostos, () => {
    clearTimeout(tGostos);
    tGostos = setTimeout(async () => {
      await salvarPerfil({ ...E.perfil, ...gostos, gostosPerguntados: true });
      toast("Preferências salvas ✅");
    }, 700);
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
