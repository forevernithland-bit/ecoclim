// Utilitários de interface: escape, toasts, bottom sheets, gráficos SVG.

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export const $ = (sel, raiz = document) => raiz.querySelector(sel);
export const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

export function num(v, casas = 0) {
  const n = Number(v);
  if (!isFinite(n)) return "–";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

export function dataBR(iso, opts = { day: "2-digit", month: "short" }) {
  if (!iso) return "";
  const [a, m, d] = String(iso).slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d).toLocaleDateString("pt-BR", opts).replace(".", "");
}

export function diasEntre(isoA, isoB) {
  const a = new Date(`${isoA}T12:00:00`), b = new Date(`${isoB}T12:00:00`);
  return Math.round((b - a) / 864e5);
}

export function somarDias(iso, n) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export function saudacao() {
  const h = new Date().getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

// ---------- Toast ----------
export function toast(msg, tipo = "ok") {
  let el = $("#toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.className = `toast toast--${tipo} toast--on`;
  el.textContent = msg;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("toast--on"), 2800);
}

// ---------- Bottom sheet (modal que sobe de baixo) ----------
export function abrirSheet(html, { aoFechar, cheia = false } = {}) {
  const fundo = document.createElement("div");
  fundo.className = "sheet-fundo";
  fundo.innerHTML = `<div class="sheet ${cheia ? "sheet--cheia" : ""}" role="dialog" aria-modal="true"><div class="sheet-alca"></div><div class="sheet-corpo">${html}</div></div>`;
  document.body.appendChild(fundo);
  document.body.classList.add("sem-rolagem");
  requestAnimationFrame(() => fundo.classList.add("sheet-fundo--on"));
  const fechar = () => {
    fundo.classList.remove("sheet-fundo--on");
    document.body.classList.remove("sem-rolagem");
    setTimeout(() => fundo.remove(), 280);
    aoFechar && aoFechar();
  };
  fundo.addEventListener("click", (e) => { if (e.target === fundo) fechar(); });
  fundo.querySelectorAll("[data-fechar]").forEach((b) => b.addEventListener("click", fechar));
  return { el: fundo.querySelector(".sheet-corpo"), fechar };
}

export function confirmar(texto, { ok = "Confirmar", perigo = false } = {}) {
  return new Promise((res) => {
    const s = abrirSheet(`
      <p class="sheet-texto">${esc(texto)}</p>
      <div class="linha-botoes">
        <button class="btn btn--sec" data-r="0">Cancelar</button>
        <button class="btn ${perigo ? "btn--perigo" : ""}" data-r="1">${esc(ok)}</button>
      </div>`, { aoFechar: () => res(false) });
    s.el.querySelectorAll("[data-r]").forEach((b) => b.addEventListener("click", () => { res(b.dataset.r === "1"); s.fechar(); }));
  });
}

// ---------- Anel de progresso ----------
export function anel(valor, meta, { tam = 168, espessura = 14, rotulo = "", sub = "" } = {}) {
  const r = (tam - espessura) / 2;
  const c = 2 * Math.PI * r;
  const pct = meta > 0 ? Math.min(1.15, valor / meta) : 0;
  const passou = valor > meta * 1.05;
  return `
  <svg class="anel" viewBox="0 0 ${tam} ${tam}" width="${tam}" height="${tam}" aria-label="${esc(rotulo)}">
    <circle cx="${tam / 2}" cy="${tam / 2}" r="${r}" class="anel-trilho" stroke-width="${espessura}" fill="none"/>
    <circle cx="${tam / 2}" cy="${tam / 2}" r="${r}" class="anel-valor ${passou ? "anel-valor--passou" : ""}" stroke-width="${espessura}" fill="none"
      stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - Math.min(1, pct))}" stroke-linecap="round"
      transform="rotate(-90 ${tam / 2} ${tam / 2})"/>
    <text x="50%" y="47%" text-anchor="middle" class="anel-num">${esc(rotulo)}</text>
    <text x="50%" y="62%" text-anchor="middle" class="anel-sub">${esc(sub)}</text>
  </svg>`;
}

export function barraMacro(nome, valor, meta, cls) {
  const pct = meta > 0 ? Math.min(100, (valor / meta) * 100) : 0;
  return `
  <div class="macro">
    <div class="macro-topo"><span>${esc(nome)}</span><span><b>${num(valor)}</b> / ${num(meta)} g</span></div>
    <div class="macro-trilho"><div class="macro-barra ${cls}" style="width:${pct}%"></div></div>
  </div>`;
}

// ---------- Gráfico de linha (SVG puro, sem biblioteca) ----------
// pontos: [{x: 'AAAA-MM-DD', y: número}]; opcional linha de tendência (média móvel)
export function graficoLinha(pontos, { altura = 170, unidade = "", media = 0, meta = null } = {}) {
  const pts = pontos.filter((p) => isFinite(p.y)).sort((a, b) => a.x.localeCompare(b.x));
  if (pts.length < 2) return `<div class="grafico-vazio">Registre pelo menos 2 dias para ver o gráfico.</div>`;
  const L = 320, A = altura, pe = 34, pd = 12, pt = 14, pb = 24;
  const xs = pts.map((p) => new Date(`${p.x}T12:00:00`).getTime());
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const ysAll = pts.map((p) => p.y).concat(meta != null ? [meta] : []);
  let y0 = Math.min(...ysAll), y1 = Math.max(...ysAll);
  const folga = Math.max(0.5, (y1 - y0) * 0.15);
  y0 -= folga; y1 += folga;
  const X = (t) => pe + ((t - x0) / Math.max(1, x1 - x0)) * (L - pe - pd);
  const Y = (v) => pt + (1 - (v - y0) / (y1 - y0)) * (A - pt - pb);
  const caminho = pts.map((p, i) => `${i ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(p.y).toFixed(1)}`).join(" ");
  let tendencia = "";
  if (media > 1 && pts.length >= 3) {
    const mm = pts.map((_, i) => {
      const jan = pts.slice(Math.max(0, i - media + 1), i + 1);
      return jan.reduce((s, p) => s + p.y, 0) / jan.length;
    });
    tendencia = `<path d="${mm.map((v, i) => `${i ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}" class="graf-tendencia"/>`;
  }
  const area = `${caminho} L${X(xs[xs.length - 1]).toFixed(1)},${A - pb} L${X(xs[0]).toFixed(1)},${A - pb} Z`;
  const ticksY = [y0 + folga, (y0 + y1) / 2, y1 - folga].map((v) =>
    `<text x="${pe - 6}" y="${Y(v) + 4}" text-anchor="end" class="graf-eixo">${num(v, (y1 - y0) < 6 ? 1 : 0)}</text>
     <line x1="${pe}" x2="${L - pd}" y1="${Y(v)}" y2="${Y(v)}" class="graf-grade"/>`).join("");
  const linhaMeta = meta != null ? `<line x1="${pe}" x2="${L - pd}" y1="${Y(meta)}" y2="${Y(meta)}" class="graf-meta"/><text x="${L - pd}" y="${Y(meta) - 4}" text-anchor="end" class="graf-eixo graf-eixo--meta">meta</text>` : "";
  const ult = pts[pts.length - 1];
  return `
  <svg viewBox="0 0 ${L} ${A}" class="grafico" role="img" aria-label="Gráfico de evolução">
    ${ticksY}${linhaMeta}
    <path d="${area}" class="graf-area"/>
    <path d="${caminho}" class="graf-linha"/>
    ${tendencia}
    ${pts.map((p, i) => `<circle cx="${X(xs[i]).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="${pts.length > 40 ? 1.5 : 3}" class="graf-ponto"><title>${dataBR(p.x)}: ${num(p.y, 1)} ${unidade}</title></circle>`).join("")}
    <text x="${pe}" y="${A - 6}" class="graf-eixo">${dataBR(pts[0].x)}</text>
    <text x="${L - pd}" y="${A - 6}" text-anchor="end" class="graf-eixo">${dataBR(ult.x)}</text>
  </svg>`;
}

// Barras simples (ex.: calorias da semana)
export function graficoBarras(itens, { meta = null, altura = 140 } = {}) {
  const L = 320, A = altura, pb = 22, pt = 10;
  const max = Math.max(...itens.map((i) => i.y), meta || 0, 1) * 1.1;
  const w = (L - 8) / itens.length;
  const Y = (v) => pt + (1 - v / max) * (A - pt - pb);
  return `
  <svg viewBox="0 0 ${L} ${A}" class="grafico" role="img" aria-label="Gráfico de barras">
    ${meta ? `<line x1="4" x2="${L - 4}" y1="${Y(meta)}" y2="${Y(meta)}" class="graf-meta"/>` : ""}
    ${itens.map((it, i) => {
      const h = Math.max(0, A - pb - Y(it.y));
      const acima = meta && it.y > meta * 1.05;
      return `<rect x="${4 + i * w + w * 0.18}" y="${Y(it.y)}" width="${w * 0.64}" height="${h}" rx="5" class="graf-barra ${acima ? "graf-barra--acima" : ""} ${it.hoje ? "graf-barra--hoje" : ""}"><title>${esc(it.rotulo)}: ${num(it.y)}</title></rect>
      <text x="${4 + i * w + w / 2}" y="${A - 6}" text-anchor="middle" class="graf-eixo">${esc(it.rotulo)}</text>`;
    }).join("")}
  </svg>`;
}

export function carregando(texto = "Carregando…") {
  return `<div class="carregando"><div class="pulso"></div><span>${esc(texto)}</span></div>`;
}
