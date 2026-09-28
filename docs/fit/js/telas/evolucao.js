// EVOLUÇÃO — o coração do app: check-ins periódicos, comparador antes/depois
// (fotos com cortina deslizante + medidas), comparativos salvos com análise da
// IA, e métricas diárias com gráficos.
import { esc, num, toast, abrirSheet, confirmar, carregando, dataBR, diasEntre, somarDias, graficoLinha } from "../ui.js";
import { MEDIDAS, gorduraEstimada, FISICOS } from "../ciencia.js";
import { urlDe } from "../midia.js";
import { fotografarCorpo } from "../camera.js";
import { compararEvolucao, analisarFisico } from "../ia.js";
import { E, gravar, apagar, listar, salvarPerfil, salvarPrefs, metricasDoDia, salvarMetrica } from "../estado.js";
import { hojeISO } from "../db.js";

let aba = "comparar";
let selAntes = null, selDepois = null;
let metricaGraf = "peso";

export async function proximoCheckin() {
  const cks = await listar("checkins");
  const ult = cks[cks.length - 1];
  if (!ult) return { data: hojeISO(), dias: 0, ult: null };
  const data = somarDias(ult.data, E.prefs.intervaloCheckin || 30);
  return { data, dias: diasEntre(hojeISO(), data), ult };
}

export function irParaEvolucao(qualAba, antesId, depoisId) {
  aba = qualAba || "comparar";
  if (antesId) selAntes = antesId;
  if (depoisId) selDepois = depoisId;
}

export async function telaEvolucao(el, ctx) {
  const cks = await listar("checkins");
  const prox = await proximoCheckin();
  el.innerHTML = `
    <div class="tela entra">
      <div class="seg">
        ${[["comparar", "Comparar"], ["metricas", "Métricas"], ["historico", "Histórico"]].map(([k, t]) => `<button class="seg-b ${aba === k ? "seg-b--on" : ""}" data-aba="${k}">${t}</button>`).join("")}
      </div>
      <div class="card card--checkin ${prox.dias <= 0 ? "card--alerta" : ""}">
        <div>
          <div class="card-tag">📅 Check-in a cada ${E.prefs.intervaloCheckin} dias</div>
          <p>${prox.dias <= 0 ? "<b>Seu check-in está liberado!</b> Fotos + medidas de hoje." : `Próximo em <b>${prox.dias} dias</b> (${dataBR(prox.data, { day: "2-digit", month: "long" })})`}</p>
        </div>
        <button class="btn btn--peq" id="novo-ck">Novo check-in</button>
      </div>
      <div id="conteudo"></div>
    </div>`;
  el.querySelectorAll("[data-aba]").forEach((b) => b.onclick = () => { aba = b.dataset.aba; ctx.rerender(); });
  el.querySelector("#novo-ck").onclick = () => novoCheckin(cks, ctx.rerender);
  const c = el.querySelector("#conteudo");
  if (aba === "comparar") return abaComparar(c, cks, ctx);
  if (aba === "metricas") return abaMetricas(c, cks, ctx);
  return abaHistorico(c, cks, ctx);
}

// ---------- Comparar ----------
function difs(a, b) {
  const magra = (c) => c.peso * (1 - (c.gordura || 0) / 100);
  return {
    dias: diasEntre(a.data, b.data),
    peso: +(b.peso - a.peso).toFixed(1),
    gordura: a.gordura != null && b.gordura != null ? +(b.gordura - a.gordura).toFixed(1) : null,
    magra: a.gordura != null && b.gordura != null ? +(magra(b) - magra(a)).toFixed(1) : null,
    gorduraKg: a.gordura != null && b.gordura != null ? +((b.peso * b.gordura - a.peso * a.gordura) / 100).toFixed(1) : null,
    medidas: Object.fromEntries(MEDIDAS.map((m) => [m.id, a.medidas && b.medidas && a.medidas[m.id] && b.medidas[m.id] ? +(b.medidas[m.id] - a.medidas[m.id]).toFixed(1) : null])),
  };
}

// Verde quando a mudança vai na direção do objetivo.
function classeDelta(campo, v) {
  if (v == null || v === 0) return "";
  const obj = E.perfil.objetivo;
  const diminuirBom = ["gordura", "gorduraKg", "cintura", "quadril"];
  const aumentarBom = ["magra", "braco", "ombros", "peito", "coxa", "panturrilha"];
  if (campo === "peso") return obj === "massa" ? (v > 0 ? "bom" : "ruim") : obj === "emagrecer" ? (v < 0 ? "bom" : "ruim") : "";
  if (diminuirBom.includes(campo)) return v < 0 ? "bom" : "ruim";
  if (aumentarBom.includes(campo)) return obj === "emagrecer" && campo !== "magra" ? "" : v > 0 ? "bom" : "ruim";
  return "";
}
const sinal = (v, casas = 1) => (v == null ? "–" : `${v > 0 ? "+" : ""}${num(v, casas)}`);

function abaComparar(el, cks, ctx) {
  if (!cks.length) {
    el.innerHTML = `<div class="vazio"><span>📸</span><p>Faça seu primeiro check-in para começar a comparar.</p></div>`;
    return;
  }
  if (cks.length === 1) {
    const c = cks[0];
    el.innerHTML = `
      <div class="card">
        <div class="card-tag">📍 Seu ponto de partida — ${dataBR(c.data, { day: "2-digit", month: "long", year: "numeric" })}</div>
        <div class="fotos-par">${fotoOuVazio(c, "fotoFrente")}${fotoOuVazio(c, "fotoLado")}</div>
        <div class="grade-3">
          <div class="mini"><small>Peso</small><b>${num(c.peso, 1)} kg</b></div>
          <div class="mini"><small>Gordura</small><b>${num(c.gordura, 1)}%</b></div>
          <div class="mini"><small>Cintura</small><b>${c.medidas && c.medidas.cintura ? num(c.medidas.cintura, 1) + " cm" : "–"}</b></div>
        </div>
        <p class="nota">No próximo check-in você verá aqui o antes × depois lado a lado, com a diferença de cada medida.</p>
      </div>`;
    return;
  }
  const porId = (id) => cks.find((c) => c.id === id);
  let A = porId(selAntes) || cks[0];
  let B = porId(selDepois) || cks[cks.length - 1];
  if (A.data > B.data) [A, B] = [B, A];
  const d = difs(A, B);
  const vista = { lado: "fotoFrente" };

  const pintaFotos = () => {
    const box = el.querySelector("#cortina");
    const fa = A[vista.lado], fb = B[vista.lado];
    if (!fa || !fb) {
      box.innerHTML = `<div class="grafico-vazio">Um dos check-ins não tem foto de ${vista.lado === "fotoFrente" ? "frente" : "lado"}.</div>`;
      return;
    }
    box.innerHTML = `
      <div class="cortina">
        <img src="${urlDe(fb, `${B.id}-${vista.lado}`)}" alt="Depois">
        <div class="cortina-antes" style="width:50%"><img src="${urlDe(fa, `${A.id}-${vista.lado}`)}" alt="Antes"></div>
        <div class="cortina-linha" style="left:50%"><span>⇆</span></div>
        <span class="cortina-rot cortina-rot--a">ANTES · ${dataBR(A.data)}</span>
        <span class="cortina-rot cortina-rot--b">DEPOIS · ${dataBR(B.data)}</span>
        <input type="range" min="0" max="100" value="50" aria-label="Deslize para comparar">
      </div>`;
    const inp = box.querySelector("input");
    const img = box.querySelector(".cortina-antes img");
    const ajusta = () => {
      box.querySelector(".cortina-antes").style.width = `${inp.value}%`;
      box.querySelector(".cortina-linha").style.left = `${inp.value}%`;
      img.style.width = `${box.querySelector(".cortina").clientWidth}px`;
    };
    inp.oninput = ajusta;
    requestAnimationFrame(ajusta);
    window.addEventListener("resize", ajusta, { once: true });
  };

  el.innerHTML = `
    <div class="sel-datas">
      <label>Antes<select id="selA">${cks.map((c) => `<option value="${c.id}" ${c.id === A.id ? "selected" : ""}>${dataBR(c.data, { day: "2-digit", month: "2-digit", year: "2-digit" })}${c.tipo === "inicial" ? " (início)" : ""}</option>`).join("")}</select></label>
      <span class="sel-seta">→</span>
      <label>Depois<select id="selB">${cks.map((c) => `<option value="${c.id}" ${c.id === B.id ? "selected" : ""}>${dataBR(c.data, { day: "2-digit", month: "2-digit", year: "2-digit" })}</option>`).join("")}</select></label>
    </div>

    <div class="resumo-dif">
      <div class="dif-principal"><small>em ${d.dias} dias</small><b class="${classeDelta("peso", d.peso)}">${sinal(d.peso)} kg</b></div>
      <div class="dif-grade">
        <div><small>Gordura</small><b class="${classeDelta("gordura", d.gordura)}">${sinal(d.gordura)} pts</b></div>
        <div><small>Gordura (kg)</small><b class="${classeDelta("gorduraKg", d.gorduraKg)}">${sinal(d.gorduraKg)}</b></div>
        <div><small>Massa magra</small><b class="${classeDelta("magra", d.magra)}">${sinal(d.magra)} kg</b></div>
      </div>
    </div>

    <div class="seg seg--mini">
      <button class="seg-b seg-b--on" data-lado="fotoFrente">Frente</button>
      <button class="seg-b" data-lado="fotoLado">Lado</button>
      <button class="seg-b" data-lado="par">Lado a lado</button>
    </div>
    <div id="cortina"></div>

    <div class="card">
      <div class="card-tag">📏 Medidas</div>
      <table class="tabela">
        <thead><tr><th></th><th>${dataBR(A.data)}</th><th>${dataBR(B.data)}</th><th>Diferença</th></tr></thead>
        <tbody>
          <tr><td>Peso</td><td>${num(A.peso, 1)}</td><td>${num(B.peso, 1)}</td><td class="${classeDelta("peso", d.peso)}">${sinal(d.peso)} kg</td></tr>
          <tr><td>% gordura</td><td>${num(A.gordura, 1)}</td><td>${num(B.gordura, 1)}</td><td class="${classeDelta("gordura", d.gordura)}">${sinal(d.gordura)}</td></tr>
          ${MEDIDAS.map((m) => {
            const a = A.medidas && A.medidas[m.id], b = B.medidas && B.medidas[m.id];
            if (!a && !b) return "";
            return `<tr><td>${m.nome}</td><td>${a ? num(a, 1) : "–"}</td><td>${b ? num(b, 1) : "–"}</td><td class="${classeDelta(m.id, d.medidas[m.id])}">${d.medidas[m.id] != null ? sinal(d.medidas[m.id]) + " cm" : "–"}</td></tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>

    <div id="ia-comp"></div>

    <div class="linha-botoes linha-botoes--col">
      <button class="btn btn--grande" id="analisar">🤖 Analisar com IA e salvar comparativo</button>
      <button class="btn btn--sec" id="salvar-comp">💾 Salvar comparativo (sem IA)</button>
      <button class="btn btn--sec" id="imagem">📤 Gerar imagem antes/depois</button>
    </div>`;

  pintaFotos();
  el.querySelectorAll("[data-lado]").forEach((b) => b.onclick = () => {
    el.querySelectorAll("[data-lado]").forEach((x) => x.classList.toggle("seg-b--on", x === b));
    if (b.dataset.lado === "par") {
      el.querySelector("#cortina").innerHTML = `<div class="par-fotos">
        ${["fotoFrente", "fotoLado"].map((f) => `<div>${fotoOuVazio(A, f)}${fotoOuVazio(B, f)}</div>`).join("")}
      </div><div class="par-rot"><span>Antes · ${dataBR(A.data)}</span><span>Depois · ${dataBR(B.data)}</span></div>`;
    } else { vista.lado = b.dataset.lado; pintaFotos(); }
  });
  el.querySelector("#selA").onchange = (e) => { selAntes = e.target.value; ctx.rerender(); };
  el.querySelector("#selB").onchange = (e) => { selDepois = e.target.value; ctx.rerender(); };

  const salvarComp = async (ia) => gravar("comparativos", {
    data: hojeISO(), antesId: A.id, depoisId: B.id, antesData: A.data, depoisData: B.data, difs: d, ia: ia || null,
  });
  el.querySelector("#salvar-comp").onclick = async () => { await salvarComp(null); toast("Comparativo salvo no histórico ✅"); };
  el.querySelector("#imagem").onclick = () => gerarImagem(A, B, d);
  el.querySelector("#analisar").onclick = async (ev) => {
    if (E.modoLocal) return toast("A análise por IA precisa de uma conta (Perfil → Entrar).", "erro");
    ev.target.disabled = true;
    const box = el.querySelector("#ia-comp");
    box.innerHTML = carregando("A IA está comparando suas fotos e medidas…");
    try {
      const ia = await compararEvolucao({ perfil: E.perfil, antes: A, depois: B });
      await salvarComp(ia);
      box.innerHTML = blocoIA(ia);
      toast("Análise salva no histórico ✅");
    } catch (e) {
      box.innerHTML = `<p class="erro-txt">Não foi possível analisar agora: ${esc(e.message)}</p>`;
      ev.target.disabled = false;
    }
  };
}

function blocoIA(ia) {
  return `
    <div class="card card--ia entra">
      <div class="card-tag">🤖 Análise da evolução</div>
      <p class="ia-nota-geral">Nota do período: <b>${num(ia.nota)}/10</b></p>
      <p>${esc(ia.resumo)}</p>
      ${ia.mudancas_visiveis && ia.mudancas_visiveis.length ? `<p class="nota"><b>O que mudou:</b></p><ul class="regras">${ia.mudancas_visiveis.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
      ${ia.proximos_passos && ia.proximos_passos.length ? `<p class="nota"><b>Próximos passos:</b></p><ul class="regras">${ia.proximos_passos.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
      ${ia.motivacao ? `<p class="dica-ia">💬 ${esc(ia.motivacao)}</p>` : ""}
    </div>`;
}

function fotoOuVazio(c, campo) {
  return c[campo] ? `<img class="foto-comp" src="${urlDe(c[campo], `${c.id}-${campo}`)}" alt="">` : `<div class="foto-comp foto-comp--vazia">sem foto</div>`;
}

// Imagem pronta pra guardar/compartilhar: antes e depois lado a lado + números.
async function gerarImagem(A, B, d) {
  const fa = A.fotoFrente || A.fotoLado, fb = B.fotoFrente || B.fotoLado;
  if (!fa || !fb) return toast("Os dois check-ins precisam ter foto.", "erro");
  const carregar = (blob) => new Promise((r) => { const i = new Image(); i.onload = () => r(i); i.src = urlDe(blob); });
  const [ia, ib] = await Promise.all([carregar(fa), carregar(fb)]);
  const W = 1080, H = 1350, fotoH = 1040;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d");
  g.fillStyle = "#0b1220"; g.fillRect(0, 0, W, H);
  const cobre = (img, x) => {
    const escala = Math.max(W / 2 / img.width, fotoH / img.height);
    const w = img.width * escala, h = img.height * escala;
    g.save(); g.beginPath(); g.rect(x, 0, W / 2, fotoH); g.clip();
    g.drawImage(img, x + (W / 2 - w) / 2, (fotoH - h) / 2, w, h); g.restore();
  };
  cobre(ia, 0); cobre(ib, W / 2);
  g.fillStyle = "#ffffff"; g.fillRect(W / 2 - 2, 0, 4, fotoH);
  g.font = "700 38px Inter, sans-serif";
  const etiqueta = (txt, x) => {
    const w = g.measureText(txt).width + 36;
    g.fillStyle = "rgba(11,18,32,.75)"; g.beginPath(); g.roundRect(x, 24, w, 60, 30); g.fill();
    g.fillStyle = "#fff"; g.fillText(txt, x + 18, 67);
  };
  etiqueta(`ANTES · ${dataBR(A.data)}`, 24);
  etiqueta(`DEPOIS · ${dataBR(B.data)}`, W / 2 + 24);
  g.fillStyle = "#c6f432"; g.font = "800 64px 'Plus Jakarta Sans', Inter, sans-serif";
  g.fillText(`${sinal(d.peso)} kg em ${d.dias} dias`, 48, fotoH + 110);
  g.fillStyle = "#cbd5e1"; g.font = "500 38px Inter, sans-serif";
  const partes = [];
  if (d.medidas.cintura != null) partes.push(`cintura ${sinal(d.medidas.cintura)} cm`);
  if (d.gordura != null) partes.push(`gordura ${sinal(d.gordura)} pts`);
  if (d.magra != null) partes.push(`massa magra ${sinal(d.magra)} kg`);
  g.fillText(partes.join("  ·  "), 48, fotoH + 180);
  g.fillStyle = "#64748b"; g.font = "600 30px Inter, sans-serif";
  g.fillText("Evolua", W - 150, H - 40);
  const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
  const arq = new File([blob], `antes-depois-${B.data}.jpg`, { type: "image/jpeg" });
  if (navigator.canShare && navigator.canShare({ files: [arq] })) {
    try { await navigator.share({ files: [arq], title: "Minha evolução" }); return; } catch (e) { /* cancelou: baixa */ }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = arq.name; a.click();
}

// ---------- Novo check-in ----------
// Completa o "antes" (check-in inicial) quando a pessoa pulou medidas/fotos
// no cadastro. Mantém a data de início — é a base de todas as comparações.
export async function completarInicial(aoSalvar) {
  const cks = await listar("checkins");
  const ini = cks.find((c) => c.tipo === "inicial") || cks[0];
  if (!ini) return;
  const r = { medidas: { ...(ini.medidas || {}) }, fotoFrente: ini.fotoFrente || null, fotoLado: ini.fotoLado || null };
  const s = abrirSheet(`
    <h2>Complete seu "antes"</h2>
    <p class="sub">É a base de todas as comparações. Faça de manhã, em jejum, com roupa justa.</p>
    <label class="rotulo">Fotos</label>
    <div class="fotos-par" id="ci-fotos"></div>
    <label class="rotulo">Medidas (cm)</label>
    <div class="lista-medidas">
      ${MEDIDAS.map((m) => `
        <div class="medida"><div class="medida-txt"><b>${m.nome}${m.obrig === true || m.obrig === E.perfil.sexo ? ' <span class="obrig">*</span>' : ""}</b><small>${m.dica}</small></div>
        <div class="campo-unid campo-unid--mini"><input class="campo" data-medida="${m.id}" type="number" inputmode="decimal" step="0.1" value="${esc(r.medidas[m.id] || "")}" placeholder="–"><span>cm</span></div></div>`).join("")}
    </div>
    <button class="btn btn--grande" id="ci-salvar">Salvar ✅</button>`, { cheia: true });
  const pintaFotos = () => {
    s.el.querySelector("#ci-fotos").innerHTML = ["Frente", "Lado"].map((l) => {
      const b = r[`foto${l}`];
      return `<button class="foto-slot ${b ? "foto-slot--ok" : ""}" data-f="${l}">${b ? `<img src="${urlDe(b)}" alt="">` : `<span class="foto-slot-mais">＋</span>`}<span class="foto-slot-rot">${b ? "Refazer" : l}</span></button>`;
    }).join("");
    s.el.querySelectorAll("[data-f]").forEach((b) => b.onclick = async () => {
      const f = await fotografarCorpo({ titulo: `Foto de ${b.dataset.f.toLowerCase()}` });
      if (f) { r[`foto${b.dataset.f}`] = f; pintaFotos(); }
    });
  };
  pintaFotos();
  s.el.querySelector("#ci-salvar").onclick = async () => {
    const medidas = {};
    s.el.querySelectorAll("[data-medida]").forEach((i) => { const v = +String(i.value).replace(",", "."); if (v > 0) medidas[i.dataset.medida] = v; });
    const gordura = gorduraEstimada({ ...E.perfil, peso: ini.peso }, medidas);
    await gravar("checkins", { ...ini, medidas, gordura, fotoFrente: r.fotoFrente, fotoLado: r.fotoLado });
    // Perfil usa as medidas mais recentes: só atualiza se ainda não houve outro check-in
    if (cks.length === 1) await salvarPerfil({ ...E.perfil, medidas });
    s.fechar();
    toast("Seu ponto de partida está completo ✅");
    aoSalvar && aoSalvar();
  };
}

async function novoCheckin(cks, aoSalvar) {
  const ult = cks[cks.length - 1];
  const r = { peso: E.perfil.peso, medidas: { ...(ult ? ult.medidas : E.perfil.medidas) }, fotoFrente: null, fotoLado: null };
  const s = abrirSheet(`
    <h2>Novo check-in</h2>
    <p class="sub">Mesmas condições da última vez: de manhã, em jejum, mesma roupa e mesmo lugar.</p>
    <label class="rotulo">Peso de hoje</label>
    <div class="campo-unid"><input id="ck-peso" class="campo" type="number" inputmode="decimal" step="0.1" value="${esc(r.peso)}"><span>kg</span></div>
    <label class="rotulo">Fotos</label>
    <div class="fotos-par" id="ck-fotos"></div>
    <p class="nota">📸 A câmera mostra sua foto anterior transparente para você repetir a pose. Use o ⏱ temporizador com o celular apoiado.</p>
    <label class="rotulo">Medidas (cm) — preenchidas com as últimas, atualize</label>
    <div class="lista-medidas">
      ${MEDIDAS.map((m) => `
        <div class="medida"><div class="medida-txt"><b>${m.nome}</b><small>${m.dica}</small></div>
        <div class="campo-unid campo-unid--mini"><input class="campo" data-medida="${m.id}" type="number" inputmode="decimal" step="0.1" value="${esc(r.medidas[m.id] || "")}" placeholder="–"><span>cm</span></div></div>`).join("")}
    </div>
    <button class="btn btn--grande" id="ck-salvar">Salvar check-in ✅</button>`, { cheia: true });

  const pintaFotos = () => {
    s.el.querySelector("#ck-fotos").innerHTML = ["Frente", "Lado"].map((l) => {
      const b = r[`foto${l}`];
      return `<button class="foto-slot ${b ? "foto-slot--ok" : ""}" data-f="${l}">${b ? `<img src="${urlDe(b)}" alt="">` : `<span class="foto-slot-mais">＋</span>`}<span class="foto-slot-rot">${b ? "Refazer" : l}</span></button>`;
    }).join("");
    s.el.querySelectorAll("[data-f]").forEach((b) => b.onclick = async () => {
      const l = b.dataset.f;
      const anterior = [...cks].reverse().find((c) => c[`foto${l}`]);
      const f = await fotografarCorpo({ titulo: `Foto de ${l.toLowerCase()}`, fantasma: anterior ? anterior[`foto${l}`] : null });
      if (f) { r[`foto${l}`] = f; pintaFotos(); }
    });
  };
  pintaFotos();

  s.el.querySelector("#ck-salvar").onclick = async (ev) => {
    const peso = +String(s.el.querySelector("#ck-peso").value).replace(",", ".");
    if (!(peso > 30)) return toast("Informe o peso.", "erro");
    ev.target.disabled = true;
    const medidas = {};
    s.el.querySelectorAll("[data-medida]").forEach((i) => { const v = +String(i.value).replace(",", "."); if (v > 0) medidas[i.dataset.medida] = v; });
    const perfil = { ...E.perfil, peso, medidas };
    const gordura = gorduraEstimada(perfil, medidas);
    const novo = await gravar("checkins", { data: hojeISO(), tipo: "periodico", peso, medidas, gordura, fotoFrente: r.fotoFrente, fotoLado: r.fotoLado });
    await salvarPerfil(perfil);
    await salvarMetrica(hojeISO(), { peso, cintura: medidas.cintura || null });
    // Todo check-in já gera um comparativo com o anterior (fica no histórico).
    if (ult) {
      await gravar("comparativos", { data: hojeISO(), antesId: ult.id, depoisId: novo.id, antesData: ult.data, depoisData: novo.data, difs: difs(ult, novo), ia: null, automatico: true });
    }
    s.fechar();
    toast("Check-in salvo! Veja a comparação 👇");
    aba = "comparar"; selAntes = ult ? ult.id : null; selDepois = novo.id;
    aoSalvar();
  };
}

// ---------- Métricas diárias ----------
const CAMPOS_METRICA = [
  { id: "peso", nome: "Peso", unid: "kg", passo: 0.1, graf: true, media: 7 },
  { id: "cintura", nome: "Cintura", unid: "cm", passo: 0.1, graf: true },
  { id: "passos", nome: "Passos", unid: "", passo: 100, graf: true },
  { id: "sono", nome: "Sono", unid: "h", passo: 0.5, graf: true },
  { id: "agua", nome: "Água", unid: "L", passo: 0.25, graf: true },
  { id: "energia", nome: "Energia (1–5)", unid: "", passo: 1, graf: true },
];

async function abaMetricas(el, cks, ctx) {
  const lista = await listar("metricas");
  const hoje = await metricasDoDia();
  const campo = CAMPOS_METRICA.find((c) => c.id === metricaGraf);
  const pontos = lista.filter((m) => m[metricaGraf] != null && m[metricaGraf] !== "").map((m) => ({ x: m.data, y: +m[metricaGraf] }));
  const pontosGordura = cks.filter((c) => c.gordura != null).map((c) => ({ x: c.data, y: c.gordura }));
  const metaLinha = metricaGraf === "peso" && E.perfil.pesoMeta ? E.perfil.pesoMeta : null;
  const primeiro = pontos[0], ultimo = pontos[pontos.length - 1];

  el.innerHTML = `
    <div class="card">
      <div class="card-tag">✍️ Métricas de hoje</div>
      <div class="grade-metricas">
        ${CAMPOS_METRICA.map((c) => `
          <label class="metrica-in"><small>${c.nome}</small>
            <div class="campo-unid campo-unid--mini"><input class="campo" data-met="${c.id}" type="number" inputmode="decimal" step="${c.passo}" value="${esc(hoje[c.id] ?? "")}" placeholder="–">${c.unid ? `<span>${c.unid}</span>` : ""}</div>
          </label>`).join("")}
      </div>
      <textarea class="campo" id="met-nota" rows="2" placeholder="Anotação do dia (ex.: dormi mal, fui a um churrasco)">${esc(hoje.nota || "")}</textarea>
      <button class="btn" id="met-salvar">Salvar métricas</button>
      <p class="nota">Dica: o peso varia até 2 kg de um dia pro outro (água, sal, intestino). Olhe a <b>linha da média</b>, não o número do dia.</p>
    </div>

    <div class="card">
      <div class="chips-rolar">${CAMPOS_METRICA.map((c) => `<button class="chip ${c.id === metricaGraf ? "chip--on" : ""}" data-graf="${c.id}">${c.nome}</button>`).join("")}<button class="chip ${metricaGraf === "gordura" ? "chip--on" : ""}" data-graf="gordura">% Gordura</button></div>
      ${metricaGraf === "gordura"
        ? graficoLinha(pontosGordura, { unidade: "%" })
        : graficoLinha(pontos, { unidade: campo.unid, media: campo.media || 0, meta: metaLinha })}
      ${metricaGraf !== "gordura" && primeiro && ultimo && primeiro !== ultimo ? `<p class="nota">Desde ${dataBR(primeiro.x)}: <b>${sinal(ultimo.y - primeiro.y, campo.passo < 1 ? 1 : 0)} ${campo.unid}</b>${campo.media ? " · linha tracejada = média de 7 dias" : ""}</p>` : ""}
    </div>

    ${lista.length ? `
    <div class="card">
      <div class="card-tag">🗒️ Registros</div>
      ${lista.slice(-14).reverse().map((m) => `
        <button class="linha-hist linha-hist--btn" data-dia="${m.data}">
          <span>${dataBR(m.data, { weekday: "short", day: "2-digit", month: "short" })}</span>
          <small>${CAMPOS_METRICA.filter((c) => m[c.id] != null && m[c.id] !== "").map((c) => `${c.nome.split(" ")[0]} ${num(m[c.id], c.passo < 1 ? 1 : 0)}${c.unid}`).join(" · ") || "—"}</small>
        </button>`).join("")}
    </div>` : ""}`;

  el.querySelectorAll("[data-graf]").forEach((b) => b.onclick = () => { metricaGraf = b.dataset.graf; ctx.rerender(); });
  el.querySelector("#met-salvar").onclick = async () => {
    const campos = { nota: el.querySelector("#met-nota").value.trim() };
    el.querySelectorAll("[data-met]").forEach((i) => { campos[i.dataset.met] = i.value === "" ? null : +String(i.value).replace(",", "."); });
    await salvarMetrica(hojeISO(), campos);
    toast("Métricas salvas ✅");
    ctx.rerender();
  };
  el.querySelectorAll("[data-dia]").forEach((b) => b.onclick = () => editarDia(b.dataset.dia, ctx.rerender));
}

async function editarDia(data, aoSalvar) {
  const m = await metricasDoDia(data);
  const s = abrirSheet(`
    <h2>${dataBR(data, { weekday: "long", day: "2-digit", month: "long" })}</h2>
    <div class="grade-metricas">
      ${CAMPOS_METRICA.map((c) => `<label class="metrica-in"><small>${c.nome}</small><div class="campo-unid campo-unid--mini"><input class="campo" data-met="${c.id}" type="number" inputmode="decimal" step="${c.passo}" value="${esc(m[c.id] ?? "")}">${c.unid ? `<span>${c.unid}</span>` : ""}</div></label>`).join("")}
    </div>
    <textarea class="campo" id="nota" rows="2">${esc(m.nota || "")}</textarea>
    <button class="btn btn--grande" id="ok">Salvar</button>`);
  s.el.querySelector("#ok").onclick = async () => {
    const campos = { nota: s.el.querySelector("#nota").value.trim() };
    s.el.querySelectorAll("[data-met]").forEach((i) => { campos[i.dataset.met] = i.value === "" ? null : +String(i.value).replace(",", "."); });
    await salvarMetrica(data, campos);
    s.fechar(); aoSalvar();
  };
}

// ---------- Histórico ----------
async function abaHistorico(el, cks, ctx) {
  const comps = await listar("comparativos", { ordem: "desc" });
  const porId = (id) => cks.find((c) => c.id === id);
  el.innerHTML = `
    <div class="card">
      <div class="card-tag">⚙️ Intervalo entre check-ins</div>
      <div class="dias-sel">${[7, 14, 30, 60, 90].map((d) => `<button class="dia-b dia-b--larg ${E.prefs.intervaloCheckin === d ? "dia-b--on" : ""}" data-int="${d}">${d} dias</button>`).join("")}</div>
    </div>

    <h3 class="secao">📊 Comparativos salvos</h3>
    ${comps.length ? comps.map((c) => {
      const a = porId(c.antesId), b = porId(c.depoisId);
      return `
      <button class="comp-item" data-comp="${c.id}">
        <span class="comp-fotos">${a && a.fotoFrente ? `<img src="${urlDe(a.fotoFrente, `${a.id}-fotoFrente`)}" alt="">` : "<i></i>"}${b && b.fotoFrente ? `<img src="${urlDe(b.fotoFrente, `${b.id}-fotoFrente`)}" alt="">` : "<i></i>"}</span>
        <span class="comp-txt">
          <b>${dataBR(c.antesData)} → ${dataBR(c.depoisData)}</b>
          <small>${c.difs.dias} dias · <span class="${classeDelta("peso", c.difs.peso)}">${sinal(c.difs.peso)} kg</span>${c.difs.medidas.cintura != null ? ` · cintura ${sinal(c.difs.medidas.cintura)} cm` : ""}</small>
          ${c.ia ? `<small class="comp-ia">🤖 Nota ${num(c.ia.nota)}/10</small>` : ""}
        </span>
      </button>`;
    }).join("") : `<p class="nota">Cada check-in gera um comparativo automático com o anterior. Você também pode salvar comparativos na aba "Antes × Depois".</p>`}

    <h3 class="secao">📸 Check-ins</h3>
    ${[...cks].reverse().map((c) => `
      <div class="ck-item">
        ${c.fotoFrente ? `<img src="${urlDe(c.fotoFrente, `${c.id}-fotoFrente`)}" alt="">` : `<span class="ck-sem">📷</span>`}
        <div><b>${dataBR(c.data, { day: "2-digit", month: "long", year: "numeric" })}${c.tipo === "inicial" ? " · início" : ""}</b><small>${num(c.peso, 1)} kg · ${num(c.gordura, 1)}% gordura${c.medidas && c.medidas.cintura ? ` · cintura ${num(c.medidas.cintura, 1)}` : ""}</small></div>
        ${c.tipo !== "inicial" ? `<button class="icone-btn" data-del="${c.id}" aria-label="Apagar">🗑</button>` : ""}
      </div>`).join("")}

    ${cks[0] && cks[0].fotoFrente ? `<button class="btn btn--sec" id="refazer-ia">🤖 Refazer análise de físico com a foto mais recente</button><div id="ia-fis"></div>` : ""}`;

  el.querySelectorAll("[data-int]").forEach((b) => b.onclick = async () => { await salvarPrefs({ intervaloCheckin: +b.dataset.int }); ctx.rerender(); });
  el.querySelectorAll("[data-comp]").forEach((b) => b.onclick = () => {
    const c = comps.find((x) => x.id === b.dataset.comp);
    if (c.ia) {
      abrirSheet(`<h2>${dataBR(c.antesData)} → ${dataBR(c.depoisData)}</h2>${blocoIA(c.ia)}<button class="btn btn--grande" id="ver">Ver fotos e medidas</button>`).el.querySelector("#ver").onclick = () => {
        document.querySelector(".sheet-fundo").click();
        selAntes = c.antesId; selDepois = c.depoisId; aba = "comparar"; ctx.rerender();
      };
    } else {
      selAntes = c.antesId; selDepois = c.depoisId; aba = "comparar"; ctx.rerender();
    }
  });
  el.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
    if (!(await confirmar("Apagar este check-in (fotos e medidas)?", { ok: "Apagar", perigo: true }))) return;
    await apagar("checkins", b.dataset.del);
    ctx.rerender();
  });
  const refazer = el.querySelector("#refazer-ia");
  if (refazer) refazer.onclick = async () => {
    if (E.modoLocal) return toast("A análise por IA precisa de uma conta.", "erro");
    const ult = [...cks].reverse().find((c) => c.fotoFrente || c.fotoLado);
    const fisico = FISICOS[E.perfil.sexo].find((f) => f.id === (E.perfil.fisicoAlvo || "atletico")) || FISICOS[E.perfil.sexo][1];
    const box = el.querySelector("#ia-fis");
    box.innerHTML = carregando("Analisando…");
    try {
      const { estimarTempoFisico } = await import("../ciencia.js");
      const est = estimarTempoFisico(E.perfil, fisico);
      const a = await analisarFisico({ perfil: E.perfil, frente: ult.fotoFrente, lado: ult.fotoLado, fisicoAlvo: fisico, estimativaCiencia: { meses: est.meses, minimo: est.minimo, maximo: est.maximo, gordura_fita: E.perfil.gordura } });
      await gravar("checkins", { ...ult, analiseIA: a });
      const { pintaAnaliseIA } = await import("./onboarding.js");
      pintaAnaliseIA(box, a);
    } catch (e) { box.innerHTML = `<p class="erro-txt">${esc(e.message)}</p>`; }
  };
}
