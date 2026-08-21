import { login, sessaoAtual, logout } from "./auth.js";
import { lerServicos, lerServico, enfileirar } from "./db.js";
import { sincronizarTudo, iniciarSyncAutomatico, statusAtual, aoMudarStatusSync } from "./sync.js";
import { adicionarMidia, enviarMidiasPendentes, puxarMidias, urlPublicaMidia, listarPendentesLocal } from "./midias.js";
import { puxarVisitas, visitasPendentesNovas, criarVisita, atualizarStatusVisita, contarNaoVistas, marcarTodasComoVistas } from "./agenda.js";
import { puxarMinhasListas, puxarMateriaisPadrao, salvarLista, adicionarItemAoPadrao, listasPendentesNovas } from "./materiais.js";
import { agruparPorMes, formatarMes } from "./financeiro.js";

const raiz = document.getElementById("app");
let sessao = null;
// Qual tela está visível agora — usado só pra decidir se o sync em segundo
// plano pode redesenhar a lista sozinho (nunca redesenha a tela de detalhe:
// o instalador pode estar digitando uma observação, e um sync automático no
// meio disso não pode apagar o que ele ainda não terminou de escrever).
let telaAtual = null;
// Quantas tarefas o Breno cadastrou que o instalador ainda não viu (selinho
// no ícone Agenda da barra inferior).
let badgeAgenda = 0;
// Verdadeiro enquanto o formulário de "Nova Visita" (Agenda) ou "Nova Lista"
// (Materiais) está aberto — a atualização automática de 10 em 10 minutos
// nunca redesenha a tela nesse caso, senão apagaria o que ele já digitou
// ali mas ainda não salvou.
let formularioAbertoAgendaOuMateriais = false;

// Segunda camada de proteção: se o toque estiver em cima de QUALQUER campo
// de texto/seleção no momento da atualização automática (mesmo fora de um
// formulário "grande"), também não mexe na tela nesse ciclo.
function usuarioEstaDigitando() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function hojeLocalISO() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function formatarData(iso) {
  if (!iso) return "";
  const [ano, mes, dia] = String(iso).slice(0, 10).split("-");
  if (!ano || !mes || !dia) return String(iso);
  return `${dia}/${mes}/${ano}`;
}

function formatarBRL(v) {
  const n = Number(v) || 0;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function escapeHTML(s) {
  const d = document.createElement("div");
  d.textContent = String(s ?? "");
  return d.innerHTML;
}

// ---------- Faixa de status de sincronização ----------
function renderFaixaSync(status, pendentes) {
  const el = document.getElementById("faixa-sync");
  if (!el) return;
  if (status === "sincronizando") {
    el.className = "faixa-sync faixa-sync--info";
    el.textContent = "🔄 Sincronizando...";
  } else if (status === "offline") {
    el.className = "faixa-sync faixa-sync--offline";
    el.textContent = pendentes > 0
      ? `🔴 Offline — ${pendentes} alteração(ões) pendente(s), será enviado quando voltar o sinal`
      : "🔴 Offline — mostrando dados salvos no aparelho";
  } else if (status === "pendente") {
    el.className = "faixa-sync faixa-sync--pendente";
    el.textContent = `🟡 Conectado — enviando ${pendentes} alteração(ões) pendente(s)...`;
  } else {
    el.className = "faixa-sync faixa-sync--ok";
    el.textContent = "✅ Tudo sincronizado";
  }
}

aoMudarStatusSync(async (status) => {
  const { pendentes } = await statusAtual();
  renderFaixaSync(status, pendentes);
  // A lista pode ter sido a primeira coisa mostrada (cache local ainda vazio,
  // no 1º login) — sem isso, os dados só apareciam depois que o instalador
  // saísse e voltasse pra tela, mesmo já sincronizado com sucesso.
  if (telaAtual === "lista" && (status === "sincronizado" || status === "pendente")) {
    await viewLista();
  }
});

// ---------- Navegação inferior (visível em toda tela, exceto login) ----------
const ITENS_NAV = [
  { id: "instalacoes", icone: "🏠", label: "Instalações" },
  { id: "agenda", icone: "📅", label: "Agenda" },
  { id: "materiais", icone: "📋", label: "Materiais" },
  { id: "financeiro", icone: "💰", label: "Financeiro" },
];

function navBarHTML(ativo) {
  return `<nav class="nav-inferior">${ITENS_NAV.map((i) => `
    <button class="nav-item ${i.id === ativo ? "nav-item--ativo" : ""}" data-nav="${i.id}">
      <span class="nav-icone-wrap">
        <span class="nav-icone">${i.icone}</span>
        ${i.id === "agenda" ? `<span class="nav-badge" id="nav-badge-agenda" style="display:${badgeAgenda > 0 ? "flex" : "none"}">${badgeAgenda > 9 ? "9+" : badgeAgenda}</span>` : ""}
      </span>
      <span class="nav-label">${i.label}</span>
    </button>
  `).join("")}</nav>`;
}

// Atualiza só o número do selinho no DOM (sem redesenhar nenhuma tela) —
// seguro chamar a qualquer momento, mesmo com um formulário aberto.
function atualizarBadgeDOM() {
  const el = document.getElementById("nav-badge-agenda");
  if (!el) return;
  el.style.display = badgeAgenda > 0 ? "flex" : "none";
  el.textContent = badgeAgenda > 9 ? "9+" : String(badgeAgenda);
}

async function atualizarContadorAgenda() {
  if (!sessao) return;
  badgeAgenda = await contarNaoVistas(sessao.instaladorVinculado);
  atualizarBadgeDOM();
}

function ligarNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alvo = btn.dataset.nav;
      if (alvo === "instalacoes") viewLista();
      else if (alvo === "agenda") viewAgenda();
      else if (alvo === "materiais") viewMateriais();
      else if (alvo === "financeiro") viewFinanceiro();
    });
  });
}

// ---------- Views ----------
function viewLogin(erro) {
  telaAtual = "login";
  raiz.innerHTML = `
    <div class="tela-login">
      <img src="icons/icon-192.png" alt="Ecoclim" class="login-logo" />
      <h1>Área do Instalador</h1>
      <p class="sub">Ecoclim Energia Solar</p>
      <form id="form-login" class="cartao">
        <label>Usuário</label>
        <input type="text" id="in-usuario" autocapitalize="none" autocomplete="username" required />
        <label>Senha</label>
        <input type="password" id="in-senha" autocomplete="current-password" required />
        ${erro ? `<p class="erro">${escapeHTML(erro)}</p>` : ""}
        <button type="submit" class="botao botao--principal">Entrar</button>
      </form>
      <p class="dica">Precisa de internet só na primeira vez que entrar neste aparelho.</p>
    </div>
  `;
  document.getElementById("form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const usuario = document.getElementById("in-usuario").value;
    const senha = document.getElementById("in-senha").value;
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    btn.textContent = "Entrando...";
    const r = await login(usuario, senha);
    if (r.ok) {
      sessao = r.sessao;
      await iniciarApp();
    } else {
      viewLogin(r.erro);
    }
  });
}

// Uma instalação conta como concluída se o instalador marcou pelo app OU se
// o Breno já fechou como Concluído PIX/CARTÃO no admin (mesmo que o
// instalador nunca tenha tocado em "marcar concluído") — mesmos status que
// o admin já trata como "Finalizados" em tela_servicos.py.
const STATUS_FINALIZADOS_ADMIN = ["Concluído PIX", "Concluído CARTÃO"];
function estaConcluida(s) {
  return Boolean(s.instalacao_concluida_instalador) || STATUS_FINALIZADOS_ADMIN.includes(s.status_projeto);
}
function dataConclusaoExibir(s) {
  return s.data_conclusao_instalador || s.data_conclusao || "";
}

// Agrupa concluídas por mês (mais recente primeiro) — usa a mesma data que
// já aparece no selo "✅" do cartão (instalador ou, na falta, admin).
function agruparConcluidosPorMes(lista) {
  const ordenados = [...lista].sort((a, b) => {
    const da = dataConclusaoExibir(a) || "";
    const db = dataConclusaoExibir(b) || "";
    return db.localeCompare(da); // datas ISO (YYYY-MM-DD) ordenam certo como texto
  });
  const grupos = [];
  const porChave = {};
  for (const s of ordenados) {
    const data = dataConclusaoExibir(s);
    const chave = data ? String(data).slice(0, 7) : "sem-data";
    if (!porChave[chave]) {
      porChave[chave] = { chave, itens: [] };
      grupos.push(porChave[chave]);
    }
    porChave[chave].itens.push(s);
  }
  return grupos;
}

async function viewLista() {
  telaAtual = "lista";
  const todos = await lerServicos();
  const abertos = todos.filter((s) => !estaConcluida(s));
  const concluidos = todos.filter((s) => estaConcluida(s));
  const gruposConcluidos = agruparConcluidosPorMes(concluidos);

  const cartao = (s) => `
    <button class="cartao cartao--clicavel" data-id="${s.id}">
      <div class="cartao-titulo">${escapeHTML(s.nome_cliente || "Sem nome")}</div>
      <div class="cartao-sub">${escapeHTML(s.produtos_adquiridos || "")}</div>
      <div class="cartao-rodape">
        <span class="etiqueta">${escapeHTML(s.status_projeto || "")}</span>
        ${estaConcluida(s)
          ? `<span class="etiqueta etiqueta--ok">✅ ${formatarData(dataConclusaoExibir(s))}</span>`
          : ""}
      </div>
    </button>
  `;

  raiz.innerHTML = `
    <div class="topo">
      <div>
        <div class="topo-titulo">${escapeHTML(sessao.nomeCompleto)}</div>
        <div class="topo-sub">${escapeHTML(sessao.instaladorVinculado)}</div>
      </div>
      <button id="btn-sair" class="botao-icone" title="Sair">🚪</button>
    </div>
    <div id="faixa-sync" class="faixa-sync"></div>
    <div class="conteudo">
      <h2 class="secao-titulo">📋 Em Aberto (${abertos.length})</h2>
      ${abertos.length ? abertos.map(cartao).join("") : `<p class="vazio">Nenhuma instalação em aberto.</p>`}

      ${concluidos.length ? `
        <button id="btn-toggle-concluidos" class="botao botao--secundario">✅ Ver Concluídas (${concluidos.length})</button>
        <div id="secao-concluidos" style="display:none; margin-top:12px;">
          ${gruposConcluidos.map((g) => `
            <h2 class="secao-titulo">${g.chave === "sem-data" ? "Sem data registrada" : formatarMes(g.chave)} (${g.itens.length})</h2>
            ${g.itens.map(cartao).join("")}
          `).join("")}
        </div>
      ` : ""}
    </div>
    ${navBarHTML("instalacoes")}
  `;

  document.getElementById("btn-sair").addEventListener("click", async () => {
    await logout();
    sessao = null;
    viewLogin();
  });
  raiz.querySelectorAll(".cartao--clicavel").forEach((el) => {
    el.addEventListener("click", () => viewDetalhe(Number(el.dataset.id)));
  });
  const btnToggleConcluidos = document.getElementById("btn-toggle-concluidos");
  if (btnToggleConcluidos) {
    btnToggleConcluidos.addEventListener("click", () => {
      const sec = document.getElementById("secao-concluidos");
      const estaAberto = sec.style.display !== "none";
      sec.style.display = estaAberto ? "none" : "block";
      btnToggleConcluidos.textContent = estaAberto
        ? `✅ Ver Concluídas (${concluidos.length})`
        : `🔼 Ocultar Concluídas`;
    });
  }
  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

async function renderizarMidias(servicoId) {
  const el = document.getElementById("midias-lista");
  if (!el) return;
  if (navigator.onLine) {
    await enviarMidiasPendentes(servicoId, sessao.instaladorVinculado);
  }
  const [confirmadas, pendentesLocal] = await Promise.all([
    puxarMidias(servicoId),
    listarPendentesLocal(servicoId),
  ]);
  // A tela pode ter mudado enquanto isso (network/upload demorou) — não
  // escreve num elemento que já não existe mais.
  const elAtual = document.getElementById("midias-lista");
  if (!elAtual) return;
  if (!confirmadas.length && !pendentesLocal.length) {
    elAtual.innerHTML = `<p class="vazio">Nenhuma foto ou vídeo ainda.</p>`;
    return;
  }
  const itensConfirmados = confirmadas.map((m) => {
    const url = urlPublicaMidia(m.storage_path);
    return m.tipo === "video"
      ? `<video src="${url}" controls class="midia-item"></video>`
      : `<img src="${url}" class="midia-item" alt="foto da instalação" />`;
  }).join("");
  const itensPendentes = pendentesLocal.map(() =>
    `<div class="midia-item midia-item--pendente">⏳<br>enviando...</div>`
  ).join("");
  elAtual.innerHTML = `<div class="midias-grid">${itensConfirmados}${itensPendentes}</div>`;
}

async function viewDetalhe(id) {
  telaAtual = "detalhe";
  const s = await lerServico(id);
  if (!s) { await viewLista(); return; }

  raiz.innerHTML = `
    <div class="topo">
      <button id="btn-voltar" class="botao-icone" title="Voltar">←</button>
      <div class="topo-titulo">${escapeHTML(s.nome_cliente || "")}</div>
      <div style="width:34px"></div>
    </div>
    <div id="faixa-sync" class="faixa-sync"></div>
    <div class="conteudo">
      <div class="cartao">
        <div class="campo"><span class="rotulo">Telefone</span><span>${escapeHTML(s.telefone_cliente || "-")}</span></div>
        <div class="campo"><span class="rotulo">Endereço</span><span>${escapeHTML(s.endereco_cliente || "Não informado")}</span></div>
        <div class="campo"><span class="rotulo">Status</span><span>${escapeHTML(s.status_projeto || "")}</span></div>
      </div>

      <div class="cartao">
        <h3 class="cartao-secao">🛠️ Equipamentos</h3>
        <p>${escapeHTML(s.produtos_adquiridos || "Nenhum produto listado.")}</p>
        ${s.servicos_adquiridos ? `<h3 class="cartao-secao">🔧 Serviço</h3><p>${escapeHTML(s.servicos_adquiridos)}</p>` : ""}
      </div>

      <div class="cartao">
        <h3 class="cartao-secao">💰 Valor da Instalação</h3>
        <p class="valor-somente-leitura">${formatarBRL(s.custo_terceirizados)}</p>
        <p class="dica">Só leitura — qualquer ajuste é feito pelo Breno.</p>
      </div>

      <div class="cartao">
        <h3 class="cartao-secao">📷 Fotos e Vídeos</h3>
        <div id="midias-lista" class="midias-grade"><p class="dica">Carregando...</p></div>
        <input type="file" id="in-midia" accept="image/*,video/*" multiple style="display:none" />
        <button id="btn-add-midia" class="botao botao--secundario">📷 Adicionar Foto/Vídeo</button>
      </div>

      <div class="cartao">
        <h3 class="cartao-secao">📝 Observação</h3>
        <textarea id="in-obs" rows="4" placeholder="Deixe aqui alguma observação sobre esta instalação...">${escapeHTML(s.observacao_instalador || "")}</textarea>
        <button id="btn-salvar-obs" class="botao botao--secundario">💾 Salvar Observação</button>
      </div>

      <div class="cartao" id="cartao-concluir">
        ${estaConcluida(s) ? `
          <p class="valor-somente-leitura">✅ Instalação concluída em ${formatarData(dataConclusaoExibir(s))}</p>
          ${s.instalacao_concluida_instalador
            ? `<button id="btn-desfazer-conclusao" class="botao botao--secundario">↩️ Cliquei por engano — Desfazer</button>`
            : `<p class="dica">Fechada pelo Breno no sistema — fale com ele se precisar mudar.</p>`}
        ` : `<button id="btn-concluir" class="botao botao--principal">✅ Marcar Instalação Concluída</button>`}
      </div>
    </div>
    ${navBarHTML("instalacoes")}
  `;

  document.getElementById("btn-voltar").addEventListener("click", viewLista);
  ligarNav();

  document.getElementById("btn-add-midia").addEventListener("click", () => {
    document.getElementById("in-midia").click();
  });
  document.getElementById("in-midia").addEventListener("change", async (e) => {
    const arquivos = Array.from(e.target.files || []);
    const el = document.getElementById("midias-lista");
    if (el) el.innerHTML = `<p class="dica">Enviando...</p>`;
    for (const arquivo of arquivos) {
      await adicionarMidia(id, arquivo, sessao.instaladorVinculado);
    }
    e.target.value = "";
    await renderizarMidias(id);
  });
  renderizarMidias(id);

  document.getElementById("btn-salvar-obs").addEventListener("click", async (e) => {
    const texto = document.getElementById("in-obs").value.trim();
    await enfileirar(id, { observacao_instalador: texto });
    e.target.textContent = "✅ Salvo";
    setTimeout(() => { e.target.textContent = "💾 Salvar Observação"; }, 1500);
    sincronizarTudo(sessao.instaladorVinculado);
  });

  const btnConcluir = document.getElementById("btn-concluir");
  if (btnConcluir) {
    // Confirmação feita dentro da própria página (não usa window.confirm):
    // em PWA instalado / navegador mobile, o diálogo nativo do confirm() é
    // inconsistente entre aparelhos e é fácil de tocar por engano. Um
    // segundo toque explícito na tela é mais confiável e mais claro.
    btnConcluir.addEventListener("click", () => {
      const cartaoConcluir = document.getElementById("cartao-concluir");
      cartaoConcluir.innerHTML = `
        <p class="confirma-texto">Confirma que esta instalação foi concluída hoje?</p>
        <button id="btn-confirmar-conclusao" class="botao botao--principal">✅ Sim, concluída</button>
        <button id="btn-cancelar-conclusao" class="botao botao--secundario">Cancelar</button>
      `;
      document.getElementById("btn-confirmar-conclusao").addEventListener("click", async () => {
        const hoje = hojeLocalISO();
        const patch = {
          instalacao_concluida_instalador: true,
          data_conclusao_instalador: hoje,
        };
        // Início da garantia é registrado automaticamente na data em que o
        // instalador confirma — só na primeira vez (se o Breno já tiver
        // ajustado antes, ex.: obra em construção, não sobrescreve).
        if (!s.data_inicio_garantia) {
          patch.data_inicio_garantia = hoje;
        }
        await enfileirar(id, patch);
        sincronizarTudo(sessao.instaladorVinculado);
        await viewDetalhe(id);
      });
      document.getElementById("btn-cancelar-conclusao").addEventListener("click", () => {
        viewDetalhe(id);
      });
    });
  }

  const btnDesfazer = document.getElementById("btn-desfazer-conclusao");
  if (btnDesfazer) {
    btnDesfazer.addEventListener("click", async () => {
      const patch = {
        instalacao_concluida_instalador: false,
        data_conclusao_instalador: null,
      };
      // Só limpa a data de início de garantia se ela ainda estiver no valor
      // automático (igual à data de conclusão) — se o Breno já mudou essa
      // data (ex.: pra começar a contar quando o cliente se mudar), o
      // "desfazer" do instalador não pode apagar esse ajuste dele.
      if (s.data_inicio_garantia === s.data_conclusao_instalador) {
        patch.data_inicio_garantia = null;
      }
      await enfileirar(id, patch);
      sincronizarTudo(sessao.instaladorVinculado);
      await viewDetalhe(id);
    });
  }

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// ---------- Agenda (visitas de orçamento e manutenção) ----------
function formatarDataHora(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${d.getFullYear()} às ${hh}:${mi}`;
  } catch (e) {
    return String(iso);
  }
}

async function viewAgenda() {
  telaAtual = "agenda";
  formularioAbertoAgendaOuMateriais = false;
  // Abrir a Agenda já conta como "visto" — some o selinho de notificação.
  await marcarTodasComoVistas(sessao.instaladorVinculado);
  badgeAgenda = 0;
  const [visitas, pendentesNovas] = await Promise.all([
    puxarVisitas(sessao.instaladorVinculado),
    visitasPendentesNovas(),
  ]);
  const agendadas = visitas.filter((v) => v.status === "Agendada" || !v.status);
  const historico = visitas.filter((v) => v.status && v.status !== "Agendada");

  const cartaoVisita = (v, pendente) => `
    <div class="cartao">
      <div class="cartao-rodape" style="margin-top:0;margin-bottom:8px;">
        ${v.criado_por === "admin" ? `<span class="etiqueta etiqueta--destaque">📋 Tarefa do Breno</span>` : ""}
        <span class="etiqueta">${escapeHTML(v.tipo || "")}</span>
        ${pendente ? `<span class="etiqueta etiqueta--pendente">⏳ pendente</span>` : ""}
        ${v.status && v.status !== "Agendada" ? `<span class="etiqueta ${v.status === "Realizada" ? "etiqueta--ok" : ""}">${escapeHTML(v.status)}</span>` : ""}
      </div>
      <div class="cartao-titulo">${escapeHTML(v.cliente_nome || "Sem nome")}</div>
      <div class="cartao-sub">${formatarDataHora(v.data_hora)}</div>
      ${v.endereco ? `<div class="cartao-sub">📍 ${escapeHTML(v.endereco)}</div>` : ""}
      ${v.telefone ? `<div class="cartao-sub">📞 ${escapeHTML(v.telefone)}</div>` : ""}
      ${v.observacoes ? `<div class="cartao-sub">📝 ${escapeHTML(v.observacoes)}</div>` : ""}
      ${!pendente && (!v.status || v.status === "Agendada") ? `
        <div class="cartao-rodape">
          <button class="botao botao--secundario botao--mini" data-realizar="${v.id}">✅ Realizada</button>
          <button class="botao botao--secundario botao--mini" data-cancelar="${v.id}">❌ Cancelar</button>
        </div>` : ""}
    </div>
  `;

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">📅 Agenda</div></div>
    <div id="faixa-sync" class="faixa-sync"></div>
    <div class="conteudo">
      <button id="btn-nova-visita" class="botao botao--principal">+ Nova Visita</button>
      <div id="form-nova-visita" class="cartao" style="display:none; margin-top:12px;">
        <label>Tipo</label>
        <select id="nv-tipo" class="campo-select"><option>Orçamento</option><option>Manutenção</option></select>
        <label>Cliente</label>
        <input type="text" id="nv-cliente" />
        <label>Telefone</label>
        <input type="text" id="nv-telefone" />
        <label>Endereço</label>
        <input type="text" id="nv-endereco" />
        <label>Data</label>
        <input type="date" id="nv-data" />
        <label>Hora</label>
        <input type="time" id="nv-hora" value="09:00" />
        <label>Observações</label>
        <textarea id="nv-obs" rows="2"></textarea>
        <button id="btn-salvar-visita" class="botao botao--principal">Salvar Visita</button>
      </div>

      <h2 class="secao-titulo">🗓️ Agendadas (${agendadas.length + pendentesNovas.length})</h2>
      ${pendentesNovas.map((p) => cartaoVisita(p.dados, true)).join("")}
      ${agendadas.length ? agendadas.map((v) => cartaoVisita(v, false)).join("") : (pendentesNovas.length ? "" : `<p class="vazio">Nenhuma visita agendada.</p>`)}

      ${historico.length ? `
        <h2 class="secao-titulo">🕓 Histórico (${historico.length})</h2>
        ${historico.map((v) => cartaoVisita(v, false)).join("")}
      ` : ""}
    </div>
    ${navBarHTML("agenda")}
  `;

  document.getElementById("btn-nova-visita").addEventListener("click", () => {
    const f = document.getElementById("form-nova-visita");
    const vaiAbrir = f.style.display === "none";
    f.style.display = vaiAbrir ? "block" : "none";
    formularioAbertoAgendaOuMateriais = vaiAbrir;
  });
  document.getElementById("btn-salvar-visita").addEventListener("click", async (e) => {
    const cliente = document.getElementById("nv-cliente").value.trim();
    const data = document.getElementById("nv-data").value;
    const hora = document.getElementById("nv-hora").value || "09:00";
    if (!cliente || !data) {
      alert("Preencha ao menos Cliente e Data.");
      return;
    }
    await criarVisita({
      instalador: sessao.instaladorVinculado,
      tipo: document.getElementById("nv-tipo").value,
      cliente_nome: cliente,
      telefone: document.getElementById("nv-telefone").value.trim(),
      endereco: document.getElementById("nv-endereco").value.trim(),
      data_hora: new Date(`${data}T${hora}:00`).toISOString(),
      status: "Agendada",
      observacoes: document.getElementById("nv-obs").value.trim(),
    });
    sincronizarTudo(sessao.instaladorVinculado);
    await viewAgenda();
  });
  raiz.querySelectorAll("[data-realizar]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const v = visitas.find((x) => x.id === Number(btn.dataset.realizar));
      if (v) { await atualizarStatusVisita(v, "Realizada"); sincronizarTudo(sessao.instaladorVinculado); await viewAgenda(); }
    });
  });
  raiz.querySelectorAll("[data-cancelar]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const v = visitas.find((x) => x.id === Number(btn.dataset.cancelar));
      if (v) { await atualizarStatusVisita(v, "Cancelada"); sincronizarTudo(sessao.instaladorVinculado); await viewAgenda(); }
    });
  });
  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// ---------- Materiais (lista padrão + listas por cliente/avulsas) ----------
const CATEGORIAS_MATERIAIS = ["modular", "tradicional", "acoplado", "piscina", "trocador", "pressurizador", "geral"];
let itensListaAtual = [];

function linhaItemHTML(it, idx) {
  return `
    <div class="linha-item" data-idx="${idx}">
      <input type="text" class="li-item" value="${escapeHTML(it.item || "")}" placeholder="Item" />
      <input type="number" class="li-qtd" value="${it.qtd ?? 1}" min="0" step="1" />
      <input type="text" class="li-unidade" value="${escapeHTML(it.unidade || "un")}" placeholder="un" />
      <button type="button" class="botao-icone" data-remover-item="${idx}">🗑️</button>
    </div>`;
}

function renderizarItensLista() {
  const el = document.getElementById("ml-itens");
  if (!el) return;
  el.innerHTML = itensListaAtual.map(linhaItemHTML).join("") || `<p class="dica">Nenhum item ainda.</p>`;
  el.querySelectorAll("[data-remover-item]").forEach((btn) => {
    btn.addEventListener("click", () => {
      itensListaAtual.splice(Number(btn.dataset.removerItem), 1);
      renderizarItensLista();
    });
  });
}

// Lê as linhas exatamente como estão (inclusive as ainda em branco) — usada
// pra sincronizar itensListaAtual antes de mexer na lista (add/remover
// linha, trocar categoria), sem descartar uma linha que o instalador ainda
// não terminou de preencher.
function lerItensDoFormularioBruto() {
  const linhas = document.querySelectorAll("#ml-itens .linha-item");
  return Array.from(linhas).map((l) => ({
    item: l.querySelector(".li-item").value,
    qtd: Number(l.querySelector(".li-qtd").value) || 0,
    unidade: l.querySelector(".li-unidade").value.trim() || "un",
  }));
}

// Versão "limpa", só com linhas de fato preenchidas — usada na hora de
// salvar de verdade (lista final ou item novo no padrão).
function lerItensDoFormulario() {
  return lerItensDoFormularioBruto()
    .map((i) => ({ ...i, item: i.item.trim() }))
    .filter((i) => i.item);
}

async function viewMateriais() {
  telaAtual = "materiais";
  formularioAbertoAgendaOuMateriais = false;
  const [minhasListas, padrao, pendentesNovas] = await Promise.all([
    puxarMinhasListas(sessao.instaladorVinculado),
    puxarMateriaisPadrao(),
    listasPendentesNovas(),
  ]);
  itensListaAtual = [];

  const cartaoLista = (l, pendente) => `
    <div class="cartao">
      ${pendente ? `<span class="etiqueta etiqueta--pendente">⏳ pendente</span>` : ""}
      <div class="cartao-titulo">${escapeHTML(l.cliente_nome || "Lista sem cliente")}</div>
      <div class="cartao-sub">${(l.itens || []).length} item(ns) — ${l.servico_id ? "vinculada a uma instalação" : "avulsa"}</div>
      <div class="cartao-sub">${(l.itens || []).map((i) => `${i.qtd}x ${escapeHTML(i.item)} (${escapeHTML(i.unidade || "un")})`).join(", ")}</div>
    </div>`;

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">📋 Materiais</div></div>
    <div id="faixa-sync" class="faixa-sync"></div>
    <div class="conteudo">
      <button id="btn-nova-lista" class="botao botao--principal">+ Nova Lista</button>
      <div id="form-nova-lista" class="cartao" style="display:none; margin-top:12px;">
        <label>Cliente (opcional, se não escolher deixa "Avulsa")</label>
        <input type="text" id="ml-cliente" placeholder="Nome do cliente" />
        <label>Categoria (pra carregar itens padrão)</label>
        <select id="ml-categoria" class="campo-select">
          ${CATEGORIAS_MATERIAIS.map((c) => `<option value="${c}">${c}</option>`).join("")}
        </select>
        <button type="button" id="btn-carregar-padrao" class="botao botao--secundario">📥 Carregar itens padrão desta categoria</button>
        <div id="ml-itens" style="margin-top:10px;"></div>
        <button type="button" id="btn-add-item" class="botao botao--secundario">+ Item em branco</button>
        <button type="button" id="btn-add-padrao" class="botao botao--secundario">⭐ Salvar item atual no padrão da categoria</button>
        <button type="button" id="btn-salvar-lista" class="botao botao--principal">💾 Salvar Lista</button>
      </div>

      <h2 class="secao-titulo">📄 Minhas Listas (${minhasListas.length + pendentesNovas.length})</h2>
      ${pendentesNovas.map((p) => cartaoLista(p.dados, true)).join("")}
      ${minhasListas.length ? minhasListas.map((l) => cartaoLista(l, false)).join("") : (pendentesNovas.length ? "" : `<p class="vazio">Nenhuma lista criada ainda.</p>`)}
    </div>
    ${navBarHTML("materiais")}
  `;

  document.getElementById("btn-nova-lista").addEventListener("click", () => {
    const f = document.getElementById("form-nova-lista");
    const vaiAbrir = f.style.display === "none";
    f.style.display = vaiAbrir ? "block" : "none";
    formularioAbertoAgendaOuMateriais = vaiAbrir;
  });

  document.getElementById("btn-carregar-padrao").addEventListener("click", () => {
    const cat = document.getElementById("ml-categoria").value;
    const itensCategoria = padrao.filter((p) => p.categoria === cat);
    itensListaAtual = itensCategoria.map((p) => ({ item: p.item, qtd: 1, unidade: p.unidade || "un" }));
    renderizarItensLista();
  });

  document.getElementById("btn-add-item").addEventListener("click", () => {
    itensListaAtual = lerItensDoFormularioBruto();
    itensListaAtual.push({ item: "", qtd: 1, unidade: "un" });
    renderizarItensLista();
  });

  document.getElementById("btn-add-padrao").addEventListener("click", async () => {
    const cat = document.getElementById("ml-categoria").value;
    const itens = lerItensDoFormulario();
    if (!itens.length) { alert("Adicione pelo menos um item antes."); return; }
    const ultimo = itens[itens.length - 1];
    await adicionarItemAoPadrao(cat, ultimo.item, ultimo.unidade);
    sincronizarTudo(sessao.instaladorVinculado);
    alert(`"${ultimo.item}" adicionado ao padrão de ${cat} para todos os instaladores.`);
  });

  document.getElementById("btn-salvar-lista").addEventListener("click", async () => {
    const itens = lerItensDoFormulario();
    if (!itens.length) { alert("Adicione pelo menos um item."); return; }
    await salvarLista({
      instalador: sessao.instaladorVinculado,
      cliente_nome: document.getElementById("ml-cliente").value.trim() || null,
      itens,
    });
    sincronizarTudo(sessao.instaladorVinculado);
    await viewMateriais();
  });

  renderizarItensLista();
  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// ---------- Financeiro (a receber x recebido, por mês) ----------
async function viewFinanceiro() {
  telaAtual = "financeiro";
  const todos = await lerServicos();
  const grupos = agruparPorMes(todos);
  const totalAReceber = grupos.reduce((acc, g) => acc + g.aReceber, 0);
  const totalRecebido = grupos.reduce((acc, g) => acc + g.recebido, 0);

  const cartaoMes = (g) => `
    <div class="cartao">
      <div class="cartao-titulo">${formatarMes(g.mes)}</div>
      <div class="campo"><span class="rotulo">A Receber</span><span style="color:var(--warn);font-weight:700;">${formatarBRL(g.aReceber)}</span></div>
      <div class="campo"><span class="rotulo">Recebido</span><span style="color:var(--ok);font-weight:700;">${formatarBRL(g.recebido)}</span></div>
    </div>`;

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">💰 Financeiro</div></div>
    <div id="faixa-sync" class="faixa-sync"></div>
    <div class="conteudo">
      <div class="cartao">
        <div class="campo"><span class="rotulo">Total a Receber</span><span style="color:var(--warn);font-weight:800;font-size:1.15rem;">${formatarBRL(totalAReceber)}</span></div>
        <div class="campo"><span class="rotulo">Total Recebido</span><span style="color:var(--ok);font-weight:800;font-size:1.15rem;">${formatarBRL(totalRecebido)}</span></div>
      </div>
      <h2 class="secao-titulo">Por mês</h2>
      ${grupos.length ? grupos.map(cartaoMes).join("") : `<p class="vazio">Nenhum valor de instalação registrado ainda.</p>`}
    </div>
    ${navBarHTML("financeiro")}
  `;

  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// Atualização automática de 10 em 10 minutos (ex.: pega tarefas novas que o
// Breno cadastrou). O selinho de notificação é sempre atualizado — é só um
// número, nunca atrapalha nada. Já redesenhar a TELA só acontece se: (a)
// não tem formulário de Agenda/Materiais aberto, e (b) o toque não está em
// cima de nenhum campo de texto/seleção agora — ou seja, nunca no meio de
// uma observação sendo digitada, um formulário em preenchimento, etc.
function iniciarAtualizacaoPeriodica(instaladorVinculado) {
  setInterval(async () => {
    await atualizarContadorAgenda();

    if (usuarioEstaDigitando() || formularioAbertoAgendaOuMateriais) return;
    if (telaAtual === "lista") await viewLista();
    else if (telaAtual === "agenda") await viewAgenda();
    else if (telaAtual === "materiais") await viewMateriais();
    else if (telaAtual === "financeiro") await viewFinanceiro();
    // "detalhe" (tem observação/fotos em edição) e "login" nunca atualizam sozinhos.
  }, 10 * 60 * 1000);
}

// ---------- Boot ----------
async function iniciarApp() {
  await viewLista();
  iniciarSyncAutomatico(sessao.instaladorVinculado);
  await atualizarContadorAgenda();
  iniciarAtualizacaoPeriodica(sessao.instaladorVinculado);
}

async function boot() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  // Se o armazenamento local (IndexedDB) falhar por qualquer motivo (modo
  // privado restrito, política do aparelho, etc.), mostra a tela de login
  // com um aviso em vez de deixar a tela em branco pra sempre.
  try {
    sessao = await sessaoAtual();
  } catch (e) {
    viewLogin("Não foi possível acessar o armazenamento deste aparelho. Tente reabrir o app.");
    return;
  }
  if (sessao) {
    try {
      await iniciarApp();
    } catch (e) {
      viewLogin("Erro ao carregar os dados salvos neste aparelho. Tente novamente.");
    }
  } else {
    viewLogin();
  }
}

boot();
