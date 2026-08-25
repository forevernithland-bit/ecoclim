import { login, sessaoAtual, logout } from "./auth.js";
import { lerServicos, lerServico, enfileirar } from "./db.js";
import { sincronizarTudo, iniciarSyncAutomatico, statusAtual, aoMudarStatusSync } from "./sync.js";
import { adicionarMidia, enviarMidiasPendentes, puxarMidias, urlPublicaMidia, listarPendentesLocal } from "./midias.js";
import { puxarVisitas, visitasPendentesNovas, criarVisita, atualizarStatusVisita, contarNaoVistas, marcarTodasComoVistas, salvarRespostaInstalador } from "./agenda.js";
import { puxarMinhasListas, puxarMateriaisPadrao, salvarLista, atualizarLista, listasPendentesNovas, puxarListaDoServico, sugerirNovoMaterial, puxarModelosMateriais } from "./materiais.js";
import {
  agruparPorMes, formatarMes, servicosFinalizadosAReceber, servicosEmAndamentoSemData, totalGeralAReceber,
} from "./financeiro.js";
import { puxarAdiantamentos, totalAdiantadoAberto } from "./adiantamentos.js";
import {
  puxarCatalogoProdutos, puxarCatalogoServicos, puxarCatalogoOutros,
  puxarRascunhos, carregarRascunho, excluirRascunho, salvarOrcamento,
  buscarSugestao, gerarPdfOrcamento, calcularCustos,
} from "./orcamentos.js";

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

// "Nome do cliente - Bairro" — padrão pedido pelo Breno pra ficar mais
// fácil do instalador lembrar de qual instalação é qual só de bater o olho
// no cartão, sem precisar abrir o endereço completo.
function nomeComBairro(s) {
  const nome = s.nome_cliente || "Sem nome";
  const bairro = String(s.bairro_cliente || "").trim();
  return bairro ? `${nome} - ${bairro}` : nome;
}

// escapeHTML sozinho não escapa aspas — ok dentro de texto, mas quebra
// quando o valor vai dentro de um atributo (ex: item com " no nome, tipo
// 32x1", fecha o value="..." no meio e derruba o HTML). Usar esta função
// pra tudo que vira valor de atributo.
function escapeAttr(s) {
  return escapeHTML(s).replace(/"/g, "&quot;");
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
const ITENS_NAV_BASE = [
  { id: "instalacoes", icone: "🏠", label: "Instalações" },
  { id: "agenda", icone: "📅", label: "Agenda" },
  { id: "materiais", icone: "📋", label: "Materiais" },
  { id: "financeiro", icone: "💰", label: "Financeiro" },
];

// Aba extra só pro admin (Breno) — pedido explícito: mesmo acesso do
// instalador + Orçamentos Personalizados, idêntico ao ERP desktop.
function itensNav() {
  return sessao && sessao.admin
    ? [...ITENS_NAV_BASE, { id: "orcamentos", icone: "🧾", label: "Orçamentos" }]
    : ITENS_NAV_BASE;
}

function navBarHTML(ativo) {
  return `<nav class="nav-inferior">${itensNav().map((i) => `
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
      else if (alvo === "orcamentos") viewOrcamentos();
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

function chaveMesHoje() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function chaveMesAnterior() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function renderConcluidosFiltrado(grupos, filtro, cartaoFn) {
  const atual = chaveMesHoje();
  const anterior = chaveMesAnterior();
  const filtrados = filtro === "todos"
    ? grupos
    : filtro === "recentes"
      ? grupos.filter((g) => g.chave === atual || g.chave === anterior)
      : grupos.filter((g) => g.chave === filtro);
  if (!filtrados.length) return `<p class="vazio">Nenhuma instalação concluída nesse período.</p>`;
  return filtrados.map((g) => `
    <h2 class="secao-titulo">${g.chave === "sem-data" ? "Sem data registrada" : formatarMes(g.chave)} (${g.itens.length})</h2>
    ${g.itens.map(cartaoFn).join("")}
  `).join("");
}

async function viewLista() {
  telaAtual = "lista";
  const todos = await lerServicos();
  const abertos = todos.filter((s) => !estaConcluida(s));
  const concluidos = todos.filter((s) => estaConcluida(s));
  const gruposConcluidos = agruparConcluidosPorMes(concluidos);

  const cartao = (s) => `
    <button class="cartao cartao--clicavel" data-id="${s.id}">
      <div class="cartao-titulo">${escapeHTML(nomeComBairro(s))}</div>
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
    <div class="conteudo">
      ${badgeAgenda > 0 ? `
        <button id="banner-notif-agenda" class="banner-notificacao">
          🔔 Você tem ${badgeAgenda} nova${badgeAgenda > 1 ? "s" : ""} tarefa${badgeAgenda > 1 ? "s" : ""} na Agenda!
          <span class="banner-notificacao-ver">Ver agora →</span>
        </button>
      ` : ""}

      <div class="abas-segmento">
        <button type="button" class="ativa" data-aba-lista="andamento">Em Andamento</button>
        <button type="button" data-aba-lista="finalizadas">Finalizadas</button>
      </div>

      <div id="aba-lista-andamento" style="margin-top:12px;">
        ${abertos.length ? abertos.map(cartao).join("") : `<p class="vazio">Nenhuma instalação em andamento.</p>`}
      </div>

      <div id="aba-lista-finalizadas" style="display:none; margin-top:12px;">
        ${concluidos.length ? `
          <select id="filtro-mes-concluidos" class="campo-select" style="margin-bottom:10px;">
            <option value="recentes">Mês atual + anterior</option>
            <option value="todos">Todos os meses</option>
            ${gruposConcluidos.map((g) => `<option value="${g.chave}">${g.chave === "sem-data" ? "Sem data" : formatarMes(g.chave)}</option>`).join("")}
          </select>
          <div id="lista-concluidos-filtrada">
            ${renderConcluidosFiltrado(gruposConcluidos, "recentes", cartao)}
          </div>
        ` : `<p class="vazio">Nenhuma instalação finalizada ainda.</p>`}
      </div>

      <div id="faixa-sync" class="faixa-sync"></div>
    </div>
    ${navBarHTML("instalacoes")}
  `;

  document.getElementById("btn-sair").addEventListener("click", async () => {
    await logout();
    sessao = null;
    viewLogin();
  });
  const ligarCliquesCartoes = () => {
    raiz.querySelectorAll(".cartao--clicavel").forEach((el) => {
      el.onclick = () => viewDetalhe(Number(el.dataset.id));
    });
  };
  ligarCliquesCartoes();

  raiz.querySelectorAll("[data-aba-lista]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alvo = btn.dataset.abaLista;
      raiz.querySelectorAll("[data-aba-lista]").forEach((b) => b.classList.toggle("ativa", b === btn));
      document.getElementById("aba-lista-andamento").style.display = alvo === "andamento" ? "block" : "none";
      document.getElementById("aba-lista-finalizadas").style.display = alvo === "finalizadas" ? "block" : "none";
    });
  });

  const filtroMesConcluidos = document.getElementById("filtro-mes-concluidos");
  if (filtroMesConcluidos) {
    filtroMesConcluidos.addEventListener("change", () => {
      document.getElementById("lista-concluidos-filtrada").innerHTML =
        renderConcluidosFiltrado(gruposConcluidos, filtroMesConcluidos.value, cartao);
      ligarCliquesCartoes();
    });
  }
  const bannerNotif = document.getElementById("banner-notif-agenda");
  if (bannerNotif) {
    bannerNotif.addEventListener("click", () => viewAgenda());
  }
  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// Liga um botão de "gravar áudio" (grava no próprio navegador, sem precisar
// de app de câmera/gravador do aparelho). `btn` é o elemento do botão
// (referência direta, não um id — evita depender de todo botão ter um id
// único no HTML). `ref` = { servico_id } ou { visita_id }; ao terminar, o
// áudio entra na fila de envio (mesma lógica de fotos/vídeos) e a galeria
// em `elId` é atualizada.
function ligarBotaoGravarAudio(btn, ref, elId) {
  if (!btn) return;
  let gravador = null;
  let pedacos = [];
  let gravando = false;

  btn.addEventListener("click", async () => {
    if (!gravando) {
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        alert("Este aparelho/navegador não suporta gravação de áudio direto aqui.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        pedacos = [];
        gravador = new MediaRecorder(stream);
        gravador.ondataavailable = (e) => { if (e.data.size > 0) pedacos.push(e.data); };
        gravador.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          const blob = new Blob(pedacos, { type: "audio/webm" });
          const arquivo = new File([blob], `audio_${Date.now()}.webm`, { type: "audio/webm" });
          const el = document.getElementById(elId);
          if (el) el.innerHTML = `<p class="dica">Enviando áudio...</p>`;
          await adicionarMidia(ref, arquivo, sessao.instaladorVinculado);
          await renderizarMidias(ref, elId);
        };
        gravador.start();
        gravando = true;
        btn.textContent = "⏹️ Parar e Enviar";
        btn.classList.add("botao--gravando");
      } catch (e) {
        alert("Não consegui acessar o microfone. Verifique a permissão do navegador.");
      }
    } else {
      gravador.stop();
      gravando = false;
      btn.textContent = "🎤 Gravar Áudio";
      btn.classList.remove("botao--gravando");
    }
  });
}

// `ref` = { servico_id } ou { visita_id }; `elId` = id do container onde
// desenhar a galeria (cada card de agenda tem o seu próprio, por isso não é
// fixo em "midias-lista").
async function renderizarMidias(ref, elId) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (navigator.onLine) {
    await enviarMidiasPendentes(ref, sessao.instaladorVinculado);
  }
  const [confirmadas, pendentesLocal] = await Promise.all([
    puxarMidias(ref),
    listarPendentesLocal(ref),
  ]);
  // A tela pode ter mudado enquanto isso (network/upload demorou) — não
  // escreve num elemento que já não existe mais.
  const elAtual = document.getElementById(elId);
  if (!elAtual) return;
  if (!confirmadas.length && !pendentesLocal.length) {
    elAtual.innerHTML = `<p class="vazio">Nenhuma foto, vídeo ou áudio ainda.</p>`;
    return;
  }
  const itemHTML = (m) => {
    const url = urlPublicaMidia(m.storage_path);
    if (m.tipo === "video") return `<video src="${url}" controls class="midia-item"></video>`;
    if (m.tipo === "audio") return `<audio src="${url}" controls class="midia-item midia-item--audio"></audio>`;
    return `<img src="${url}" class="midia-item" alt="foto" />`;
  };
  const itensConfirmados = confirmadas.map(itemHTML).join("");
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
      <div class="topo-titulo">${escapeHTML(nomeComBairro(s))}</div>
      <div style="width:34px"></div>
    </div>
    <div class="conteudo">
      <div class="cartao">
        <div class="campo"><span class="rotulo">Telefone</span><span>${escapeHTML(s.telefone_cliente || "-")}</span></div>
        <div class="campo"><span class="rotulo">Endereço</span><span>${escapeHTML(s.endereco_cliente || "Não informado")}</span></div>
        ${s.endereco_cliente ? `
          <div style="display:flex; gap:8px; margin-top:8px;">
            <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(s.endereco_cliente)}" target="_blank" rel="noopener" class="botao botao--secundario botao--mini" style="display:inline-block; text-decoration:none; text-align:center; flex:1;">🗺️ Maps</a>
            <a href="https://waze.com/ul?q=${encodeURIComponent(s.endereco_cliente)}&navigate=yes" target="_blank" rel="noopener" class="botao botao--secundario botao--mini" style="display:inline-block; text-decoration:none; text-align:center; flex:1;">🚗 Waze</a>
          </div>
        ` : ""}
        <div class="campo"><span class="rotulo">Status</span><span>${escapeHTML(s.status_projeto || "")}</span></div>
      </div>

      ${!estaConcluida(s) ? `
        <div class="cartao">
          <h3 class="cartao-secao">🗓️ Data Prevista de Instalação</h3>
          <input type="date" id="in-data-prevista" value="${s.data_prevista_instalacao ? String(s.data_prevista_instalacao).slice(0, 10) : ""}" />
          <button id="btn-salvar-data-prevista" class="botao botao--secundario">💾 Salvar Data Prevista</button>
          <p class="dica">Ajuda o Breno a prever quando o pagamento dessa instalação deve cair no Financeiro.</p>
        </div>
      ` : ""}

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
        <h3 class="cartao-secao">📷 Fotos, Vídeos e Áudios</h3>
        <div id="midias-lista" class="midias-grade"><p class="dica">Carregando...</p></div>
        <input type="file" id="in-midia" accept="image/*,video/*,audio/*" multiple style="display:none" />
        <button id="btn-add-midia" class="botao botao--secundario">📷 Adicionar Foto/Vídeo</button>
        <button id="btn-gravar-audio" class="botao botao--secundario">🎤 Gravar Áudio</button>
      </div>

      <div class="cartao">
        <h3 class="cartao-secao">📋 Lista de Materiais</h3>
        <div id="materiais-lista-cliente"><p class="dica">Carregando...</p></div>
        <button id="btn-toggle-nova-lista-cliente" class="botao botao--secundario">+ Nova Lista de Materiais</button>
        <div id="form-nova-lista-cliente" style="display:none; margin-top:10px;">
          <label>Começar de uma lista padrão (opcional)</label>
          <div style="display:flex; gap:8px; align-items:center;">
            <select id="ml-modelo-select" style="flex:1;"><option value="">-- nenhuma --</option></select>
            <button type="button" id="btn-usar-modelo" class="botao botao--secundario botao--mini">📥 Usar</button>
          </div>
          <label>Buscar material</label>
          <input type="text" id="ml-busca" placeholder="Ex: 22, joel, cpvc..." autocomplete="off" />
          <div id="ml-resultados-busca" class="ml-resultados"></div>
          <div id="ml-itens" style="margin-top:10px;"></div>
          <button type="button" id="btn-salvar-lista" class="botao botao--principal">💾 Salvar Lista deste Cliente</button>
        </div>
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

      <div id="faixa-sync" class="faixa-sync"></div>
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
      await adicionarMidia({ servico_id: id }, arquivo, sessao.instaladorVinculado);
    }
    e.target.value = "";
    await renderizarMidias({ servico_id: id }, "midias-lista");
  });
  renderizarMidias({ servico_id: id }, "midias-lista");
  ligarBotaoGravarAudio(document.getElementById("btn-gravar-audio"), { servico_id: id }, "midias-lista");

  renderizarListaMateriaisCliente(id, "materiais-lista-cliente");
  itensListaAtual = [];
  let materiaisPadraoCacheDetalhe = [];
  let modelosCacheDetalhe = [];
  document.getElementById("btn-toggle-nova-lista-cliente").addEventListener("click", async () => {
    const f = document.getElementById("form-nova-lista-cliente");
    const vaiAbrir = f.style.display === "none";
    f.style.display = vaiAbrir ? "block" : "none";
    formularioAbertoAgendaOuMateriais = vaiAbrir;
    if (vaiAbrir) {
      if (!materiaisPadraoCacheDetalhe.length) materiaisPadraoCacheDetalhe = await puxarMateriaisPadrao();
      if (!modelosCacheDetalhe.length) {
        modelosCacheDetalhe = await puxarModelosMateriais();
        preencherSelectModelos("ml-modelo-select", modelosCacheDetalhe);
      }
      renderizarItensLista();
    }
  });
  document.getElementById("btn-usar-modelo").addEventListener("click", () => {
    const idModelo = document.getElementById("ml-modelo-select").value;
    const modelo = modelosCacheDetalhe.find((m) => String(m.id) === idModelo);
    if (!modelo) return;
    itensListaAtual = lerItensDoFormularioBruto();
    for (const it of modelo.itens || []) itensListaAtual.push({ ...it, manual: false });
    renderizarItensLista();
  });
  document.getElementById("ml-busca").addEventListener("input", (e) => {
    renderizarResultadosBuscaMaterial(e.target.value, materiaisPadraoCacheDetalhe, "ml-resultados-busca", (dados) => {
      itensListaAtual = lerItensDoFormularioBruto();
      itensListaAtual.push({ item: dados.item, qtd: 1, unidade: dados.unidade, categoria: dados.categoria, manual: dados.manual });
      renderizarItensLista();
      document.getElementById("ml-busca").value = "";
      document.getElementById("ml-resultados-busca").innerHTML = "";
    });
  });
  document.getElementById("btn-salvar-lista").addEventListener("click", async () => {
    const itens = lerItensDoFormulario();
    if (!itens.length) { alert("Adicione pelo menos um item."); return; }
    await salvarLista({
      instalador: sessao.instaladorVinculado,
      cliente_nome: s.nome_cliente || null,
      servico_id: id,
      itens,
    });
    for (const it of itens.filter((i) => i.manual)) {
      await sugerirNovoMaterial({ item: it.item, instalador: sessao.instaladorVinculado, clienteNome: s.nome_cliente, servicoId: id });
    }
    document.getElementById("materiais-lista-cliente").innerHTML = `<p class="dica">Salvando...</p>`;
    // Espera a sincronização de verdade antes de recarregar — senão o
    // resumo consulta o servidor rápido demais e mostra "nenhuma lista"
    // por um instante, mesmo já tendo salvo certinho.
    await sincronizarTudo(sessao.instaladorVinculado);
    document.getElementById("form-nova-lista-cliente").style.display = "none";
    formularioAbertoAgendaOuMateriais = false;
    itensListaAtual = [];
    await renderizarListaMateriaisCliente(id, "materiais-lista-cliente");
  });

  const btnSalvarDataPrevista = document.getElementById("btn-salvar-data-prevista");
  if (btnSalvarDataPrevista) {
    btnSalvarDataPrevista.addEventListener("click", async (e) => {
      const data = document.getElementById("in-data-prevista").value;
      await enfileirar(id, { data_prevista_instalacao: data || null });
      e.target.textContent = "✅ Salvo";
      setTimeout(() => { e.target.textContent = "💾 Salvar Data Prevista"; }, 1500);
      sincronizarTudo(sessao.instaladorVinculado);
    });
  }

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
          conclusao_vista_pelo_admin: false,
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
        conclusao_vista_pelo_admin: true,
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
  const historico = [...visitas.filter((v) => v.status && v.status !== "Agendada")]
    .sort((a, b) => String(b.data_hora || "").localeCompare(String(a.data_hora || "")));

  const chaveMesVisita = (v) => String(v.data_hora || "").slice(0, 7) || "sem-data";
  const mesAtualChaveAgenda = chaveMesHoje();
  const mesesHistorico = Array.from(new Set([mesAtualChaveAgenda, ...historico.map(chaveMesVisita)]))
    .filter((m) => m !== "sem-data")
    .sort((a, b) => b.localeCompare(a));
  const renderHistoricoFiltrado = (mes, cartaoFn) => {
    const filtrados = mes === "todos" ? historico : historico.filter((v) => chaveMesVisita(v) === mes);
    return filtrados.length ? filtrados.map(cartaoFn).join("") : `<p class="vazio">Nenhuma visita realizada neste período.</p>`;
  };

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
      ${v.endereco ? `<div class="cartao-sub">📍 ${escapeHTML(v.endereco)}</div>
        <div style="display:flex; gap:8px; margin:6px 0;">
          <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(v.endereco)}" target="_blank" rel="noopener" class="botao botao--secundario botao--mini" style="display:inline-block; text-decoration:none; text-align:center; flex:1;">🗺️ Maps</a>
          <a href="https://waze.com/ul?q=${encodeURIComponent(v.endereco)}&navigate=yes" target="_blank" rel="noopener" class="botao botao--secundario botao--mini" style="display:inline-block; text-decoration:none; text-align:center; flex:1;">🚗 Waze</a>
        </div>` : ""}
      ${v.telefone ? `<div class="cartao-sub">📞 ${escapeHTML(v.telefone)}</div>` : ""}
      ${v.observacoes ? `<div class="cartao-sub">📝 ${escapeHTML(v.observacoes)}</div>` : ""}
      ${v.comentario_instalador ? `<div class="cartao-sub">💬 Você respondeu: ${escapeHTML(v.comentario_instalador)}</div>` : ""}
      ${v.valor_sugerido ? `<div class="cartao-sub">💰 Valor sugerido: ${formatarBRL(v.valor_sugerido)}</div>` : ""}
      ${!pendente && (!v.status || v.status === "Agendada") ? `
        <div class="cartao-rodape">
          <button class="botao botao--secundario botao--mini" data-realizar="${v.id}">✅ Realizada</button>
          <button class="botao botao--secundario botao--mini" data-cancelar="${v.id}">❌ Cancelar</button>
        </div>` : ""}
      ${!pendente ? `
        <button class="botao botao--secundario botao--mini" data-responder="${v.id}" style="margin-top:8px;">💬 Comentar / Valor / Fotos</button>
        <div id="resposta-${v.id}" style="display:none; margin-top:10px;">
          <label>Comentário pro Breno</label>
          <textarea id="resp-obs-${v.id}" rows="2" placeholder="Ex: cliente confirmou, precisa de X material...">${escapeHTML(v.comentario_instalador || "")}</textarea>
          <label>Valor sugerido (opcional)</label>
          <input type="number" id="resp-valor-${v.id}" min="0" step="0.01" value="${v.valor_sugerido || ""}" placeholder="R$" />
          <button class="botao botao--principal botao--mini" data-salvar-resposta="${v.id}" style="margin-top:8px;">💾 Enviar pro Breno</button>
          <div id="midias-visita-${v.id}" class="midias-grade" style="margin-top:10px;"><p class="dica">Carregando...</p></div>
          <input type="file" id="midia-visita-${v.id}" accept="image/*,video/*,audio/*" multiple style="display:none" />
          <button class="botao botao--secundario botao--mini" data-add-midia-visita="${v.id}">📷 Foto/Vídeo</button>
          <button class="botao botao--secundario botao--mini" data-gravar-audio-visita="${v.id}">🎤 Áudio</button>
        </div>
      ` : ""}
    </div>
  `;

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">📅 Agenda</div></div>
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

      <div class="abas-segmento">
        <button type="button" class="ativa" data-aba-agenda="agendadas">Agendadas</button>
        <button type="button" data-aba-agenda="realizadas">Realizadas</button>
      </div>

      <div id="aba-agenda-agendadas" style="margin-top:12px;">
        <h2 class="secao-titulo">🗓️ Agendadas (${agendadas.length + pendentesNovas.length})</h2>
        ${pendentesNovas.map((p) => cartaoVisita(p.dados, true)).join("")}
        ${agendadas.length ? agendadas.map((v) => cartaoVisita(v, false)).join("") : (pendentesNovas.length ? "" : `<p class="vazio">Nenhuma visita agendada.</p>`)}
      </div>

      <div id="aba-agenda-realizadas" style="display:none; margin-top:12px;">
        <label style="margin-top:0;">📅 Filtrar por mês</label>
        <select id="filtro-mes-agenda">
          ${mesesHistorico.map((m) => `<option value="${m}" ${m === mesAtualChaveAgenda ? "selected" : ""}>${formatarMes(m)}</option>`).join("")}
          <option value="todos">Todos os meses</option>
        </select>
        <div id="lista-agenda-realizadas" style="margin-top:12px;">${renderHistoricoFiltrado(mesAtualChaveAgenda, (v) => cartaoVisita(v, false))}</div>
      </div>

      <div id="faixa-sync" class="faixa-sync"></div>
    </div>
    ${navBarHTML("agenda")}
  `;

  raiz.querySelectorAll("[data-aba-agenda]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alvo = btn.dataset.abaAgenda;
      raiz.querySelectorAll("[data-aba-agenda]").forEach((b) => b.classList.toggle("ativa", b === btn));
      document.getElementById("aba-agenda-agendadas").style.display = alvo === "agendadas" ? "block" : "none";
      document.getElementById("aba-agenda-realizadas").style.display = alvo === "realizadas" ? "block" : "none";
    });
  });
  const filtroMesAgenda = document.getElementById("filtro-mes-agenda");
  if (filtroMesAgenda) {
    filtroMesAgenda.addEventListener("change", () => {
      document.getElementById("lista-agenda-realizadas").innerHTML =
        renderHistoricoFiltrado(filtroMesAgenda.value, (v) => cartaoVisita(v, false));
      ligarAcoesVisita();
    });
  }

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
  function ligarAcoesVisita() {
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

    raiz.querySelectorAll("[data-responder]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const vid = btn.dataset.responder;
        const bloco = document.getElementById(`resposta-${vid}`);
        const vaiAbrir = bloco.style.display === "none";
        bloco.style.display = vaiAbrir ? "block" : "none";
        formularioAbertoAgendaOuMateriais = vaiAbrir;
        if (vaiAbrir) {
          renderizarMidias({ visita_id: Number(vid) }, `midias-visita-${vid}`);
        }
      });
    });
    raiz.querySelectorAll("[data-salvar-resposta]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const vid = btn.dataset.salvarResposta;
        const v = visitas.find((x) => x.id === Number(vid));
        if (!v) return;
        const comentario = document.getElementById(`resp-obs-${vid}`).value.trim();
        const valorTxt = document.getElementById(`resp-valor-${vid}`).value;
        const valor = valorTxt ? Number(valorTxt) : null;
        await salvarRespostaInstalador(v, comentario, valor);
        btn.textContent = "✅ Enviado";
        sincronizarTudo(sessao.instaladorVinculado);
        setTimeout(() => { btn.textContent = "💾 Enviar pro Breno"; }, 1500);
      });
    });
    raiz.querySelectorAll("[data-add-midia-visita]").forEach((btn) => {
      const vid = btn.dataset.addMidiaVisita;
      btn.addEventListener("click", () => document.getElementById(`midia-visita-${vid}`).click());
    });
    raiz.querySelectorAll("input[id^='midia-visita-']").forEach((input) => {
      const vid = input.id.replace("midia-visita-", "");
      input.addEventListener("change", async (e) => {
        const arquivos = Array.from(e.target.files || []);
        const el = document.getElementById(`midias-visita-${vid}`);
        if (el) el.innerHTML = `<p class="dica">Enviando...</p>`;
        for (const arquivo of arquivos) {
          await adicionarMidia({ visita_id: Number(vid) }, arquivo, sessao.instaladorVinculado);
        }
        e.target.value = "";
        await renderizarMidias({ visita_id: Number(vid) }, `midias-visita-${vid}`);
      });
    });
    raiz.querySelectorAll("[data-gravar-audio-visita]").forEach((btn) => {
      const vid = btn.dataset.gravarAudioVisita;
      ligarBotaoGravarAudio(btn, { visita_id: Number(vid) }, `midias-visita-${vid}`);
    });
  }
  ligarAcoesVisita();
  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// ---------- Orçamentos (só admin) ----------
let orcItens = [];
let orcRascunhoId = null;
let orcNumeroProposta = null;
let orcPdfAtual = null;
let orcAssinaturaAuto = "";

// ---------- Materiais (catálogo com busca + listas por cliente/avulsas) ----------
let itensListaAtual = [];
// id da lista sendo editada (via botão "✏️ Editar" numa lista já salva) —
// null quando o formulário está criando uma lista nova.
let listaEmEdicaoId = null;

// Remove acento/caixa pra busca funcionar digitando de qualquer jeito
// ("cpvc", "CPVC", "cpvç" tudo bate igual).
function normalizarBuscaTexto(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

// Busca por substring em qualquer parte do nome (não só no começo) — digitar
// "22" acha tudo que tem 22 em algum lugar do nome, "joel" acha todo joelho.
// Limita a tela (poucos resultados por vez, bem legíveis) em vez de jogar
// dezenas de botões espremidos — celular tem pouco espaço pra ler.
const LIMITE_RESULTADOS_BUSCA_MATERIAL = 8;
function buscarMateriaisFiltrados(query, todosOsPadrao) {
  const q = normalizarBuscaTexto(query).trim();
  if (!q) return { resultados: [], total: 0 };
  const todos = todosOsPadrao
    .filter((m) => normalizarBuscaTexto(m.item).includes(q))
    .sort((a, b) => a.item.localeCompare(b.item, "pt-BR"));
  return { resultados: todos.slice(0, LIMITE_RESULTADOS_BUSCA_MATERIAL), total: todos.length };
}

// Deixa em negrito o trecho que bateu com a busca, pra ficar fácil de achar
// visualmente na lista. Só funciona quando o texto digitado aparece igual
// (sem acento removido) no item — se não achar, mostra o nome normal, sem
// quebrar nada.
function destacarTrechoBusca(nomeItem, query) {
  const idx = nomeItem.toLowerCase().indexOf(query.trim().toLowerCase());
  if (idx === -1) return escapeHTML(nomeItem);
  const antes = nomeItem.slice(0, idx);
  const meio = nomeItem.slice(idx, idx + query.trim().length);
  const depois = nomeItem.slice(idx + query.trim().length);
  return `${escapeHTML(antes)}<mark>${escapeHTML(meio)}</mark>${escapeHTML(depois)}`;
}

// Desenha os resultados da busca embaixo do campo, cada um numa linha
// própria (fácil de ler e de acertar o toque no celular) com a categoria
// como legenda e o trecho buscado destacado. Sempre tem, no fim, a opção de
// adicionar manualmente o que foi digitado, caso não esteja no catálogo.
// `onAdicionar` recebe {item, categoria, unidade, manual}.
function renderizarResultadosBuscaMaterial(query, todosOsPadrao, elId, onAdicionar) {
  const el = document.getElementById(elId);
  if (!el) return;
  const texto = query.trim();
  if (!texto) { el.innerHTML = ""; return; }
  const { resultados, total } = buscarMateriaisFiltrados(texto, todosOsPadrao);
  const botoesResultado = resultados.map((m) => `
    <button type="button" class="resultado-busca" data-item="${escapeAttr(m.item)}" data-categoria="${escapeAttr(m.categoria || "")}" data-unidade="${escapeAttr(m.unidade || "un")}">
      <span class="resultado-busca-nome">${destacarTrechoBusca(m.item, texto)}</span>
      ${m.categoria ? `<span class="resultado-busca-cat">${escapeHTML(NOMES_CATEGORIA_MATERIAL[m.categoria] || "Outros")}</span>` : ""}
    </button>`);
  const avisoMais = total > resultados.length
    ? `<p class="resultado-busca-aviso">Mostrando ${resultados.length} de ${total} — digite mais letras pra achar exatamente o que precisa</p>`
    : "";
  const botaoManual = `
    <button type="button" class="resultado-busca resultado-busca--manual" data-manual="1">
      ➕ Adicionar "${escapeHTML(texto)}" (não achei na lista)
    </button>`;
  el.innerHTML = botoesResultado.join("") + avisoMais + botaoManual;
  el.querySelectorAll("[data-item]").forEach((btn) => {
    btn.addEventListener("click", () => onAdicionar({
      item: btn.dataset.item, categoria: btn.dataset.categoria || null, unidade: btn.dataset.unidade || "un", manual: false,
    }));
  });
  const btnManual = el.querySelector("[data-manual]");
  if (btnManual) {
    btnManual.addEventListener("click", () => onAdicionar({ item: texto, categoria: null, unidade: "un", manual: true }));
  }
}

// Preenche o <select> de "lista padrão" com os modelos cadastrados pelo
// admin — usado nas duas telas onde dá pra criar uma lista de materiais.
function preencherSelectModelos(elId, modelos) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = `<option value="">-- nenhuma --</option>` +
    (modelos || []).map((m) => `<option value="${escapeAttr(m.id)}">${escapeHTML(m.nome)} (${(m.itens || []).length} itens)</option>`).join("");
}

function linhaItemHTML(it, idx) {
  return `
    <div class="linha-item" data-idx="${idx}" data-categoria="${escapeAttr(it.categoria || "")}" data-manual="${it.manual ? "1" : ""}">
      <input type="text" class="li-item" value="${escapeAttr(it.item || "")}" placeholder="Item" />
      <input type="number" class="li-qtd" value="${it.qtd ?? 1}" min="0" step="1" />
      <input type="text" class="li-unidade" value="${escapeAttr(it.unidade || "un")}" placeholder="un" />
      <button type="button" class="botao-icone" data-remover-item="${idx}">🗑️</button>
    </div>`;
}

function renderizarItensLista() {
  const el = document.getElementById("ml-itens");
  if (!el) return;
  el.innerHTML = itensListaAtual.map(linhaItemHTML).join("") || `<p class="dica">Nenhum item ainda. Use a busca acima.</p>`;
  el.querySelectorAll("[data-remover-item]").forEach((btn) => {
    btn.addEventListener("click", () => {
      itensListaAtual.splice(Number(btn.dataset.removerItem), 1);
      renderizarItensLista();
    });
  });
}

// Lê as linhas exatamente como estão (inclusive as ainda em branco) —
// preserva categoria/manual guardados nos data-attributes de cada linha
// (não dá pra descobrir isso só pelo texto digitado).
function lerItensDoFormularioBruto() {
  const linhas = document.querySelectorAll("#ml-itens .linha-item");
  return Array.from(linhas).map((l) => ({
    item: l.querySelector(".li-item").value,
    qtd: Number(l.querySelector(".li-qtd").value) || 0,
    unidade: l.querySelector(".li-unidade").value.trim() || "un",
    categoria: l.dataset.categoria || null,
    manual: l.dataset.manual === "1",
  }));
}

// Versão "limpa", só com linhas de fato preenchidas — usada na hora de
// salvar de verdade.
function lerItensDoFormulario() {
  return lerItensDoFormularioBruto()
    .map((i) => ({ ...i, item: i.item.trim() }))
    .filter((i) => i.item);
}

// ---------- Texto formatado pra WhatsApp ----------
const NOMES_CATEGORIA_MATERIAL = {
  agua_quente: "Material Água Quente - CPVC",
  agua_fria: "Material Água Fria - PVC",
  bronze_cobre: "Material Bronze/Cobre",
};
const ORDEM_CATEGORIAS_MATERIAL = ["agua_quente", "agua_fria", "bronze_cobre", "geral_hidraulico"];

function gerarTextoListaMateriais(clienteNome, itens) {
  const porCategoria = {};
  for (const it of itens || []) {
    const cat = ORDEM_CATEGORIAS_MATERIAL.includes(it.categoria) ? it.categoria : "geral_hidraulico";
    if (!porCategoria[cat]) porCategoria[cat] = [];
    porCategoria[cat].push(it);
  }
  const blocos = [];
  for (const cat of ORDEM_CATEGORIAS_MATERIAL) {
    const lista = porCategoria[cat];
    if (!lista || !lista.length) continue;
    const titulo = NOMES_CATEGORIA_MATERIAL[cat] || "Outros";
    const ordenados = [...lista].sort((a, b) => a.item.localeCompare(b.item, "pt-BR"));
    const linhas = ordenados.map((it) => `${it.qtd} ${it.item}`);
    blocos.push(`*${titulo}*\n${linhas.join("\n")}`);
  }
  const cabecalho = clienteNome ? `*Lista de Materiais Cliente ${clienteNome}*` : `*Lista de Materiais*`;
  return [cabecalho, ...blocos].join("\n\n");
}

function botaoWhatsAppListaHTML(idx) {
  return `
    <div style="display:flex; gap:8px; margin-top:6px;">
      <button type="button" class="botao botao--secundario botao--mini" data-copiar-lista="${idx}" style="flex:1;">📋 Copiar</button>
      <button type="button" class="botao botao--secundario botao--mini" data-whatsapp-lista="${idx}" style="flex:1;">📤 WhatsApp</button>
    </div>`;
}

function ligarBotoesWhatsAppLista(elId, listas) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.querySelectorAll("[data-whatsapp-lista]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const lista = listas[Number(btn.dataset.whatsappLista)];
      if (!lista) return;
      const texto = gerarTextoListaMateriais(lista.cliente_nome, lista.itens || []);
      window.open(`https://wa.me/?text=${encodeURIComponent(texto)}`, "_blank");
    });
  });
  el.querySelectorAll("[data-copiar-lista]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const lista = listas[Number(btn.dataset.copiarLista)];
      if (!lista) return;
      const texto = gerarTextoListaMateriais(lista.cliente_nome, lista.itens || []);
      try {
        await navigator.clipboard.writeText(texto);
        const original = btn.textContent;
        btn.textContent = "✅ Copiado!";
        setTimeout(() => { btn.textContent = original; }, 1500);
      } catch (e) {
        alert("Não consegui copiar automaticamente. Copie manualmente:\n\n" + texto);
      }
    });
  });
}

// Lista de materiais de UM cliente específico, mostrada dentro da tela de
// detalhe da instalação — diferente da lista "avulsa" da aba Materiais.
async function renderizarListaMateriaisCliente(servicoId, elId) {
  const el = document.getElementById(elId);
  if (!el) return;
  const listas = await puxarListaDoServico(servicoId);
  const elAtual = document.getElementById(elId);
  if (!elAtual) return;
  if (!listas.length) {
    elAtual.innerHTML = `<p class="vazio">Nenhuma lista de materiais registrada ainda.</p>`;
    return;
  }
  elAtual.innerHTML = listas.map((l, idx) => `
    <div class="cartao" style="margin-bottom:8px;">
      <div class="cartao-sub">${(l.itens || []).length} item(ns)</div>
      <div class="cartao-sub">${(l.itens || []).map((i) => `${i.qtd}x ${escapeHTML(i.item)} (${escapeHTML(i.unidade || "un")})`).join(", ")}</div>
      ${botaoWhatsAppListaHTML(idx)}
    </div>
  `).join("");
  ligarBotoesWhatsAppLista(elId, listas);
}

async function viewMateriais() {
  telaAtual = "materiais";
  formularioAbertoAgendaOuMateriais = false;
  const [minhasListas, padrao, pendentesNovas, modelos] = await Promise.all([
    puxarMinhasListas(sessao.instaladorVinculado),
    puxarMateriaisPadrao(),
    listasPendentesNovas(),
    puxarModelosMateriais(),
  ]);
  itensListaAtual = [];
  listaEmEdicaoId = null;

  const cartaoLista = (l, pendente, idx) => `
    <div class="cartao">
      ${pendente ? `<span class="etiqueta etiqueta--pendente">⏳ pendente</span>` : ""}
      <div class="cartao-titulo">${escapeHTML(l.cliente_nome || "Lista sem cliente")}</div>
      <div class="cartao-sub">${(l.itens || []).length} item(ns) — ${l.servico_id ? "vinculada a uma instalação" : "avulsa"}</div>
      <div class="cartao-sub">${(l.itens || []).map((i) => `${i.qtd}x ${escapeHTML(i.item)} (${escapeHTML(i.unidade || "un")})`).join(", ")}</div>
      ${pendente ? "" : `<button type="button" class="botao botao--secundario botao--mini" data-editar-lista="${idx}" style="margin-top:6px;">✏️ Editar</button>`}
      ${pendente ? "" : botaoWhatsAppListaHTML(idx)}
    </div>`;

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">📋 Materiais</div></div>
    <div class="conteudo">
      <button id="btn-nova-lista" class="botao botao--principal">+ Nova Lista</button>
      <div id="form-nova-lista" class="cartao" style="display:none; margin-top:12px;">
        <label>Cliente (opcional, se não escolher deixa "Avulsa")</label>
        <input type="text" id="ml-cliente" placeholder="Nome do cliente" />
        <label>Começar de uma lista padrão (opcional)</label>
        <div style="display:flex; gap:8px; align-items:center;">
          <select id="ml-modelo-select" style="flex:1;"><option value="">-- nenhuma --</option></select>
          <button type="button" id="btn-usar-modelo" class="botao botao--secundario botao--mini">📥 Usar</button>
        </div>
        <label>Buscar material</label>
        <input type="text" id="ml-busca" placeholder="Ex: 22, joel, cpvc..." autocomplete="off" />
        <div id="ml-resultados-busca" class="ml-resultados"></div>
        <div id="ml-itens" style="margin-top:10px;"></div>
        <button type="button" id="btn-salvar-lista" class="botao botao--principal">💾 Salvar Lista</button>
      </div>

      <h2 class="secao-titulo">📄 Minhas Listas (${minhasListas.length + pendentesNovas.length})</h2>
      ${pendentesNovas.map((p) => cartaoLista(p.dados, true)).join("")}
      ${minhasListas.length ? minhasListas.map((l, idx) => cartaoLista(l, false, idx)).join("") : (pendentesNovas.length ? "" : `<p class="vazio">Nenhuma lista criada ainda.</p>`)}

      <div id="faixa-sync" class="faixa-sync"></div>
    </div>
    ${navBarHTML("materiais")}
  `;

  preencherSelectModelos("ml-modelo-select", modelos);
  document.getElementById("btn-nova-lista").addEventListener("click", () => {
    const f = document.getElementById("form-nova-lista");
    const vaiAbrir = f.style.display === "none";
    f.style.display = vaiAbrir ? "block" : "none";
    formularioAbertoAgendaOuMateriais = vaiAbrir;
    if (vaiAbrir) renderizarItensLista();
  });

  document.getElementById("btn-usar-modelo").addEventListener("click", () => {
    const idModelo = document.getElementById("ml-modelo-select").value;
    const modelo = modelos.find((m) => String(m.id) === idModelo);
    if (!modelo) return;
    itensListaAtual = lerItensDoFormularioBruto();
    for (const it of modelo.itens || []) itensListaAtual.push({ ...it, manual: false });
    renderizarItensLista();
  });

  document.getElementById("ml-busca").addEventListener("input", (e) => {
    renderizarResultadosBuscaMaterial(e.target.value, padrao, "ml-resultados-busca", (dados) => {
      itensListaAtual = lerItensDoFormularioBruto();
      itensListaAtual.push({ item: dados.item, qtd: 1, unidade: dados.unidade, categoria: dados.categoria, manual: dados.manual });
      renderizarItensLista();
      document.getElementById("ml-busca").value = "";
      document.getElementById("ml-resultados-busca").innerHTML = "";
    });
  });

  document.getElementById("btn-salvar-lista").addEventListener("click", async () => {
    const itens = lerItensDoFormulario();
    if (!itens.length) { alert("Adicione pelo menos um item."); return; }
    const clienteNome = document.getElementById("ml-cliente").value.trim() || null;
    if (listaEmEdicaoId) {
      try {
        await atualizarLista(listaEmEdicaoId, { cliente_nome: clienteNome, itens });
      } catch (e) {
        alert("Não deu pra salvar a edição agora — confira sua internet e tente de novo.");
        return;
      }
      listaEmEdicaoId = null;
    } else {
      await salvarLista({
        instalador: sessao.instaladorVinculado,
        cliente_nome: clienteNome,
        itens,
      });
      for (const it of itens.filter((i) => i.manual)) {
        await sugerirNovoMaterial({ item: it.item, instalador: sessao.instaladorVinculado, clienteNome });
      }
    }
    sincronizarTudo(sessao.instaladorVinculado);
    await viewMateriais();
  });

  raiz.querySelectorAll("[data-editar-lista]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const lista = minhasListas[Number(btn.dataset.editarLista)];
      if (!lista) return;
      listaEmEdicaoId = lista.id;
      itensListaAtual = JSON.parse(JSON.stringify(lista.itens || []));
      document.getElementById("ml-cliente").value = lista.cliente_nome || "";
      const f = document.getElementById("form-nova-lista");
      f.style.display = "block";
      formularioAbertoAgendaOuMateriais = true;
      renderizarItensLista();
      f.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  ligarBotoesWhatsAppLista("app", minhasListas);

  renderizarItensLista();
  ligarNav();

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// ---------- Financeiro (a receber x recebido, por mês) ----------
async function viewFinanceiro() {
  telaAtual = "financeiro";
  const [todos, adiantamentos] = await Promise.all([
    lerServicos(),
    puxarAdiantamentos(sessao.instaladorVinculado),
  ]);
  const grupos = agruparPorMes(todos);
  const finalizadosAReceber = servicosFinalizadosAReceber(todos);
  const emAndamentoSemData = servicosEmAndamentoSemData(todos);
  const totalAdiantado = totalAdiantadoAberto(adiantamentos);
  const totalFinalizadosAReceber = finalizadosAReceber.reduce((acc, s) => acc + Number(s.custo_terceirizados), 0);
  const totalEmAndamentoSemData = emAndamentoSemData.reduce((acc, s) => acc + Number(s.custo_terceirizados), 0);
  const liquidoFinalizados = totalFinalizadosAReceber - totalAdiantado;

  // Filtro de mês do "Recebidos" — vem pré-selecionado no mês anterior (o
  // mês atual normalmente ainda não fechou os recebimentos todos). Sempre
  // inclui o mês atual e o anterior na lista, mesmo sem nada recebido
  // neles ainda, pra sempre dar pra escolher os dois.
  const mesAtualChave = chaveMesHoje();
  const mesAnteriorChave = chaveMesAnterior();
  const mesesDisponiveis = Array.from(new Set([mesAtualChave, mesAnteriorChave, ...grupos.map((g) => g.mes)])).sort((a, b) => b.localeCompare(a));
  const grupoDoMes = (mes) => grupos.find((g) => g.mes === mes) || { recebido: 0, itensRecebido: [] };

  const linhaCliente = (s, cor) => `
    <div class="campo" style="font-size:0.88rem;">
      <span>${escapeHTML(nomeComBairro(s))}${!estaConcluida(s) ? " (em andamento)" : ""}</span>
      <span style="color:${cor};font-weight:700;">${formatarBRL(s.custo_terceirizados)}</span>
    </div>`;

  // Igual linhaCliente, mas clicável — leva direto pro cliente (útil pra
  // marcar como pago, ou pra preencher a Data Prevista de Instalação).
  const linhaClienteClicavel = (s, cor) => `
    <button class="cartao--clicavel campo" data-ir-cliente="${s.id}" style="font-size:0.88rem; width:100%; border:none; background:none; padding:6px 0; font-family:inherit;">
      <span>${escapeHTML(nomeComBairro(s))}${!estaConcluida(s) ? " (em andamento)" : ""}</span>
      <span style="color:${cor};font-weight:700;">${formatarBRL(s.custo_terceirizados)}</span>
    </button>`;

  const cartaoQuadrante = (chave, titulo, cor, total, itens, dica) => `
    <div class="cartao cartao--clicavel" data-quad="${chave}">
      <div class="cartao-titulo">${titulo}</div>
      <div class="campo"><span class="rotulo">${itens.length} cliente(s)</span><span style="color:${cor};font-weight:800;font-size:1.05rem;">${formatarBRL(total)}</span></div>
    </div>
    <div id="detalhe-quad-${chave}" class="cartao" style="display:none; margin-top:-6px; margin-bottom:12px;">
      ${dica ? `<p class="dica">${dica}</p>` : ""}
      ${itens.length ? itens.map((s) => linhaClienteClicavel(s, cor)).join("") : `<p class="vazio">Nenhum cliente aqui no momento.</p>`}
    </div>`;

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">💰 Financeiro</div></div>
    <div class="conteudo">
      <div class="abas-segmento">
        <button type="button" class="ativa" data-aba-fin="receber">A Receber</button>
        <button type="button" data-aba-fin="recebido">Recebidos</button>
      </div>

      <div id="aba-fin-receber" style="margin-top:12px;">
        <div class="cartao cartao--destaque">
          <div class="cartao--destaque-topo">✅ Serviços Finalizados a Receber</div>
          <div class="cartao--destaque-corpo">
            <div class="campo"><span class="rotulo">${finalizadosAReceber.length} cliente(s)</span><span style="color:var(--brand-dark);font-weight:800;font-size:1.15rem;">${formatarBRL(totalFinalizadosAReceber)}</span></div>
            ${totalAdiantado > 0 ? `
              <div class="campo"><span class="rotulo">💵 Adiantamento (em aberto)</span><span style="color:var(--danger);font-weight:700;">− ${formatarBRL(totalAdiantado)}</span></div>
              <div class="campo" style="border-top:1px dashed var(--line); padding-top:8px; margin-top:4px;"><span class="rotulo"><b>Líquido a Receber</b></span><span style="color:var(--ink);font-weight:800;">${formatarBRL(liquidoFinalizados)}</span></div>
            ` : ""}
            <div style="margin-top:12px; border-top:1px solid var(--line); padding-top:10px;">
              ${finalizadosAReceber.length ? finalizadosAReceber.map((s) => linhaClienteClicavel(s, "var(--brand-dark)")).join("") : `<p class="vazio">Nenhum serviço finalizado aguardando pagamento.</p>`}
            </div>
          </div>
        </div>

        <h2 class="secao-titulo">Clique pra ver os clientes</h2>
        ${cartaoQuadrante(
          "semdata", "🔧 Serviços em Andamento a Receber (sem data)", "var(--warn)",
          totalEmAndamentoSemData, emAndamentoSemData,
          "Preencha a \"Data Prevista de Instalação\" desses clientes (toque no nome pra abrir) pra eles entrarem na previsão do mês certo.",
        )}
      </div>

      <div id="aba-fin-recebido" style="display:none; margin-top:12px;">
        <label style="margin-top:0;">📅 Ver recebimento do mês</label>
        <select id="filtro-mes-financeiro">
          ${mesesDisponiveis.map((m) => `<option value="${m}" ${m === mesAtualChave ? "selected" : ""}>${formatarMes(m)}</option>`).join("")}
        </select>
        <div id="cartao-recebido-mes" style="margin-top:12px;"></div>

        ${adiantamentos.length ? `
          <h2 class="secao-titulo">💵 Histórico de Adiantamentos</h2>
          ${adiantamentos.map((a) => {
            let dataFmt = "";
            try { dataFmt = formatarData(String(a.data)); } catch (e) { dataFmt = String(a.data || ""); }
            const saldo = Number(a._saldo) || 0;
            const baixado = Number(a._baixado) || 0;
            const quitado = saldo <= 0.005;
            const historicoBaixas = (a._baixas || []).map((b) => {
              let bDataFmt = "";
              try { bDataFmt = formatarData(String(b.data)); } catch (e) { bDataFmt = String(b.data || ""); }
              return `<div class="campo" style="font-size:0.82rem; color:var(--muted);">
                <span>　↳ ${bDataFmt}: baixou</span><span>${formatarBRL(b.valor)}</span>
              </div>`;
            }).join("");
            return `<div class="cartao">
              <div class="campo"><span>${dataFmt} — ${escapeHTML(a.motivo || "sem motivo informado")}</span><span style="font-weight:700;">${formatarBRL(a.valor)}</span></div>
              ${baixado > 0.005 ? `<div class="campo" style="font-size:0.85rem;"><span class="rotulo">Já baixado: ${formatarBRL(baixado)} · Saldo</span><span style="font-weight:700;">${formatarBRL(saldo)}</span></div>${historicoBaixas}` : ""}
              <span class="etiqueta ${quitado ? "etiqueta--ok" : "etiqueta--pendente"}">${quitado ? "✅ Quitado" : "⏳ Em aberto"}</span>
            </div>`;
          }).join("")}
        ` : ""}
      </div>

      <div id="faixa-sync" class="faixa-sync"></div>
    </div>
    ${navBarHTML("financeiro")}
  `;

  raiz.querySelectorAll("[data-aba-fin]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alvo = btn.dataset.abaFin;
      raiz.querySelectorAll("[data-aba-fin]").forEach((b) => b.classList.toggle("ativa", b === btn));
      document.getElementById("aba-fin-receber").style.display = alvo === "receber" ? "block" : "none";
      document.getElementById("aba-fin-recebido").style.display = alvo === "recebido" ? "block" : "none";
    });
  });

  const renderRecebidoMes = (mes) => {
    const g = grupoDoMes(mes);
    const el = document.getElementById("cartao-recebido-mes");
    if (!el) return;
    el.innerHTML = cartaoQuadrante(
      "recebido-mes", `✅ Recebido em ${formatarMes(mes)}`, "var(--ok)",
      g.recebido, g.itensRecebido, null,
    );
    el.querySelectorAll("[data-quad]").forEach((elq) => {
      elq.addEventListener("click", () => {
        const det = document.getElementById(`detalhe-quad-${elq.dataset.quad}`);
        det.style.display = det.style.display === "none" ? "block" : "none";
      });
    });
    el.querySelectorAll("[data-ir-cliente]").forEach((elc) => {
      elc.addEventListener("click", (ev) => {
        ev.stopPropagation();
        viewDetalhe(Number(elc.dataset.irCliente));
      });
    });
  };
  renderRecebidoMes(mesAtualChave);
  document.getElementById("filtro-mes-financeiro").addEventListener("change", (e) => renderRecebidoMes(e.target.value));

  raiz.querySelectorAll("[data-quad]").forEach((el) => {
    el.addEventListener("click", () => {
      const det = document.getElementById(`detalhe-quad-${el.dataset.quad}`);
      det.style.display = det.style.display === "none" ? "block" : "none";
    });
  });
  raiz.querySelectorAll("[data-ir-cliente]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.stopPropagation(); // não fecha o quadrante ao navegar
      viewDetalhe(Number(el.dataset.irCliente));
    });
  });
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

// ---------- Orçamentos (aba exclusiva do admin) ----------
function formatarTelefoneOrc(tel) {
  const numeros = String(tel || "").replace(/\D/g, "");
  if (numeros.length === 11) return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 7)}-${numeros.slice(7)}`;
  return tel || "";
}

function totalOrcItens() {
  return orcItens.reduce((acc, it) => acc + Number(it.quantidade || 0) * Number(it.venda_unitario || 0), 0);
}

function itemOrcamentoCardHTML(it, idx) {
  return `
    <div class="cartao" style="margin-bottom:8px;" data-orc-item="${idx}">
      <div class="cartao-titulo">${escapeHTML(it.nome)}</div>
      <div style="display:flex; gap:8px; margin-top:6px;">
        <div style="flex:1;">
          <label style="font-size:0.75rem;">Qtd</label>
          <input type="number" min="0" step="1" value="${it.quantidade}" data-orc-campo="quantidade" style="width:100%;" />
        </div>
        <div style="flex:1.4;">
          <label style="font-size:0.75rem;">Custo Unt.</label>
          <input type="number" min="0" step="0.01" value="${it.custo_unitario}" data-orc-campo="custo_unitario" style="width:100%;" />
        </div>
        <div style="flex:1.4;">
          <label style="font-size:0.75rem;">Venda Unt.</label>
          <input type="number" min="0" step="0.01" value="${it.venda_unitario}" data-orc-campo="venda_unitario" style="width:100%;" />
        </div>
      </div>
      <div class="campo" style="margin-top:6px;">
        <span class="rotulo">Subtotal</span>
        <span style="font-weight:700;">${formatarBRL(Number(it.quantidade || 0) * Number(it.venda_unitario || 0))}</span>
      </div>
      <button type="button" class="botao botao--secundario botao--mini" data-orc-remover="${idx}" style="margin-top:4px;">🗑️ Remover</button>
    </div>`;
}

function renderizarItensOrcamento() {
  const el = document.getElementById("orc-itens");
  if (!el) return;
  el.innerHTML = orcItens.length
    ? orcItens.map((it, idx) => itemOrcamentoCardHTML(it, idx)).join("")
    : `<p class="vazio">Nenhum equipamento adicionado ainda.</p>`;

  el.querySelectorAll("[data-orc-campo]").forEach((input) => {
    input.addEventListener("input", (e) => {
      const card = e.target.closest("[data-orc-item]");
      const idx = Number(card.dataset.orcItem);
      orcItens[idx][e.target.dataset.orcCampo] = Number(e.target.value) || 0;
      atualizarTotalOrcamentoDOM();
    });
  });
  el.querySelectorAll("[data-orc-remover]").forEach((btn) => {
    btn.addEventListener("click", () => {
      orcItens.splice(Number(btn.dataset.orcRemover), 1);
      renderizarItensOrcamento();
      atualizarTotalOrcamentoDOM();
      atualizarSugestaoAutomatica();
    });
  });
  atualizarTotalOrcamentoDOM();
}

function lerValoresOrcamentoForm() {
  const $ = (id) => document.getElementById(id);
  return {
    nomeCliente: $("orc-nome").value.trim(),
    telefone: formatarTelefoneOrc($("orc-whatsapp").value),
    endereco: $("orc-endereco").value.trim(),
    modeloCapa: $("orc-capa").value,
    descricaoServico: $("orc-servico-desc").value,
    valorServico: Number($("orc-servico-valor").value) || 0,
    descricaoOutros: $("orc-outros-desc").value,
    valorOutros: Number($("orc-outros-valor").value) || 0,
    observacoes: $("orc-obs").value,
    mostrarPrecos: $("orc-mostrar-precos").checked,
    detalharItens: $("orc-detalhar-itens").checked,
  };
}

function atualizarTotalOrcamentoDOM() {
  const v = lerValoresOrcamentoForm();
  const total = totalOrcItens() + v.valorServico + v.valorOutros;
  const el = document.getElementById("orc-total");
  if (el) el.textContent = formatarBRL(total);
  const elSub = document.getElementById("orc-subtotal-equip");
  if (elSub) elSub.textContent = formatarBRL(totalOrcItens());
}

async function atualizarSugestaoAutomatica() {
  const assinatura = orcItens.map((it) => it.nome).join("|");
  if (assinatura === orcAssinaturaAuto) return;
  orcAssinaturaAuto = assinatura;
  if (!orcItens.length) return;
  try {
    const sug = await buscarSugestao(orcItens.map((it) => ({ nome: it.nome, quantidade: it.quantidade, venda_unitario: it.venda_unitario })));
    if (sug.capa_sugerida) document.getElementById("orc-capa").value = sug.capa_sugerida;
    if (sug.servico_detalhe) {
      document.getElementById("orc-servico-desc").value = `${sug.servico_detalhe.nome}\n${sug.servico_detalhe.descricao}`.trim();
      document.getElementById("orc-servico-valor").value = sug.servico_detalhe.valor;
      atualizarTotalOrcamentoDOM();
    } else if (sug.sugestao && sug.sugestao.nome_sugerido) {
      alert(`Identifiquei uma instalação "${sug.sugestao.nome_sugerido}" mas não achei o serviço correspondente no catálogo. Preencha manualmente.`);
    }
  } catch (e) {
    // automação é um bônus — se a API estiver fora do ar, o orçamento continua editável manualmente
  }
}

function resetarFormularioOrcamento() {
  orcItens = [];
  orcRascunhoId = null;
  orcNumeroProposta = null;
  orcPdfAtual = null;
  orcAssinaturaAuto = "";
}

async function viewOrcamentos() {
  telaAtual = "orcamentos";
  const [produtos, servicos, outros, rascunhos] = await Promise.all([
    puxarCatalogoProdutos(), puxarCatalogoServicos(), puxarCatalogoOutros(), puxarRascunhos(),
  ]);

  raiz.innerHTML = `
    <div class="topo"><div class="topo-titulo">🧾 Orçamentos</div></div>
    <div class="conteudo">
      ${rascunhos.length ? `
        <div class="cartao" style="margin-bottom:12px;">
          <div class="cartao-titulo">📂 Continuar Rascunho</div>
          <select id="orc-rascunho-select" style="width:100%; margin-top:6px;">
            <option value="">-- novo orçamento --</option>
            ${rascunhos.map((r) => `<option value="${r.id}">${escapeHTML(r.nome_cliente || "Sem nome")} (${formatarBRL(r.valor_venda_total)})</option>`).join("")}
          </select>
          <div style="display:flex; gap:8px; margin-top:8px;">
            <button type="button" id="btn-orc-carregar" class="botao botao--secundario botao--mini">📥 Carregar</button>
            <button type="button" id="btn-orc-excluir" class="botao botao--secundario botao--mini">🗑️ Excluir</button>
          </div>
        </div>` : ""}

      <div class="cartao" style="margin-bottom:12px;">
        <div class="cartao-titulo">👤 Dados do Cliente</div>
        <label>Nome do Cliente</label>
        <input type="text" id="orc-nome" />
        <label>WhatsApp</label>
        <input type="text" id="orc-whatsapp" placeholder="(31) 99999-9999" />
        <label>Endereço (opcional)</label>
        <input type="text" id="orc-endereco" placeholder="Rua, número, bairro, cidade - UF" />
        <label>Modelo para Capa</label>
        <select id="orc-capa">
          ${["Aquecedor Solar Tradicional", "Aquecedor Solar a Vácuo Acoplado", "Aquecedor Solar Modular", "Aquecedor de Piscina - Tradicional", "Aquecedor de Piscina - Trocador de Calor", "Sistema de Pressurização"]
            .map((c) => `<option value="${escapeAttr(c)}">${escapeHTML(c)}</option>`).join("")}
        </select>
      </div>

      <div class="cartao" style="margin-bottom:12px;">
        <div class="cartao-titulo">⚙️ 1. Equipamentos</div>
        <label style="display:flex; align-items:center; gap:6px; font-weight:400;"><input type="checkbox" id="orc-detalhar-itens" style="width:auto;" /> Detalhar valor de cada item no PDF</label>
        <label style="display:flex; align-items:center; gap:6px; font-weight:400;"><input type="checkbox" id="orc-mostrar-precos" style="width:auto;" /> Mostrar preços unitários no PDF</label>
        <div style="display:flex; gap:8px; align-items:flex-end; margin-top:8px;">
          <div style="flex:1;">
            <label>Adicionar produto do catálogo</label>
            <select id="orc-select-produto">
              <option value="">-- escolher --</option>
              ${produtos.map((p) => `<option value="${escapeAttr(p.item)}">${escapeHTML(p.item)}</option>`).join("")}
              <option value="__manual__">OUTRO (digitar manualmente)</option>
            </select>
          </div>
          <button type="button" id="btn-orc-add-produto" class="botao botao--secundario botao--mini">➕</button>
        </div>
        <div id="orc-itens" style="margin-top:10px;"></div>
        <div class="campo" style="margin-top:6px;"><span class="rotulo">Subtotal Equipamentos</span><span id="orc-subtotal-equip" style="font-weight:800; color:#004488;"></span></div>
      </div>

      <div class="cartao" style="margin-bottom:12px;">
        <div class="cartao-titulo">🛠️ 2. Serviços</div>
        <select id="orc-select-servico">
          <option value="">-- escolher --</option>
          ${servicos.map((s) => `<option value="${escapeAttr(s.item)}">${escapeHTML(s.item)}</option>`).join("")}
          <option value="__manual__">Manual</option>
        </select>
        <label>Descrição</label>
        <textarea id="orc-servico-desc" rows="3"></textarea>
        <label>Valor do Serviço (R$)</label>
        <input type="number" min="0" step="0.01" id="orc-servico-valor" value="0" />
      </div>

      <div class="cartao" style="margin-bottom:12px;">
        <div class="cartao-titulo">🤝 3. Outros / Terceiros</div>
        <select id="orc-select-outros">
          <option value="">-- escolher --</option>
          ${outros.map((o) => `<option value="${escapeAttr(o.item)}">${escapeHTML(o.item)}</option>`).join("")}
          <option value="__manual__">Manual</option>
        </select>
        <label>Descrição</label>
        <textarea id="orc-outros-desc" rows="2"></textarea>
        <label>Valor Adicional (R$)</label>
        <input type="number" min="0" step="0.01" id="orc-outros-valor" value="0" />
      </div>

      <div class="cartao" style="margin-bottom:12px;">
        <div class="campo"><span style="font-weight:800; font-size:1.1rem;">💰 INVESTIMENTO TOTAL</span><span id="orc-total" style="font-weight:800; font-size:1.1rem; color:#004488;"></span></div>
        <label style="margin-top:8px;">Observações no PDF</label>
        <textarea id="orc-obs" rows="2">Material Hidráulico não incluído na proposta</textarea>
      </div>

      <details class="cartao" style="margin-bottom:12px;">
        <summary style="font-weight:700; cursor:pointer;">🧮 Cálculo de Custos — Lucro Líquido</summary>
        <div style="margin-top:10px;">
          <label style="display:flex; align-items:center; gap:6px; font-weight:400;"><input type="checkbox" id="cc-emite-nf" style="width:auto;" /> Emitir Nota Fiscal?</label>
          <label>Forma de Pagamento</label>
          <select id="cc-pagamento"><option value="Nenhum / Dinheiro / PIX">Nenhum / Dinheiro / PIX</option></select>
          <label>Comissão (%)</label>
          <input type="number" min="0" step="0.01" id="cc-comissao" value="0" />
          <label>Desconto concedido (R$)</label>
          <input type="number" min="0" step="0.01" id="cc-desconto" value="0" />
          <button type="button" id="btn-orc-calcular" class="botao botao--secundario" style="margin-top:8px;">Calcular</button>
          <div id="orc-resultado-custos" style="margin-top:10px;"></div>
        </div>
      </details>

      <div id="orc-resultado-pdf" style="margin-bottom:12px;"></div>

      <div style="display:flex; flex-direction:column; gap:8px;">
        <button type="button" id="btn-orc-previa" class="botao botao--secundario">👁️ Gerar Prévia (PDF)</button>
        <button type="button" id="btn-orc-rascunho" class="botao botao--secundario">💾 Salvar Rascunho</button>
        <button type="button" id="btn-orc-salvar" class="botao botao--principal">✅ Salvar no Sistema</button>
      </div>
    </div>
    ${navBarHTML("orcamentos")}
  `;

  renderizarItensOrcamento();
  ligarNav();

  document.getElementById("btn-orc-add-produto").addEventListener("click", () => {
    const sel = document.getElementById("orc-select-produto");
    const valor = sel.value;
    if (!valor) return;
    if (valor === "__manual__") {
      const nome = prompt("Nome do produto:");
      if (!nome) return;
      orcItens.push({ nome, descricao: "", quantidade: 1, custo_unitario: 0, venda_unitario: 0 });
    } else {
      const p = produtos.find((x) => x.item === valor);
      orcItens.push({ nome: p.item, descricao: p.descricao, quantidade: 1, custo_unitario: p.custo, venda_unitario: p.venda });
    }
    sel.value = "";
    renderizarItensOrcamento();
    atualizarSugestaoAutomatica();
  });

  document.getElementById("orc-select-servico").addEventListener("change", (e) => {
    if (e.target.value === "__manual__") {
      document.getElementById("orc-servico-desc").value = "";
      document.getElementById("orc-servico-valor").value = 0;
    } else if (e.target.value) {
      const s = servicos.find((x) => x.item === e.target.value);
      document.getElementById("orc-servico-desc").value = `${s.item}\n${s.descricao}`.trim();
      document.getElementById("orc-servico-valor").value = s.venda;
    }
    atualizarTotalOrcamentoDOM();
  });
  document.getElementById("orc-servico-valor").addEventListener("input", atualizarTotalOrcamentoDOM);

  document.getElementById("orc-select-outros").addEventListener("change", (e) => {
    if (e.target.value === "__manual__") {
      document.getElementById("orc-outros-desc").value = "";
      document.getElementById("orc-outros-valor").value = 0;
    } else if (e.target.value) {
      const o = outros.find((x) => x.item === e.target.value);
      document.getElementById("orc-outros-desc").value = `${o.item}\n${o.descricao}`.trim();
      document.getElementById("orc-outros-valor").value = o.venda;
    }
    atualizarTotalOrcamentoDOM();
  });
  document.getElementById("orc-outros-valor").addEventListener("input", atualizarTotalOrcamentoDOM);

  if (rascunhos.length) {
    document.getElementById("btn-orc-carregar").addEventListener("click", async () => {
      const id = Number(document.getElementById("orc-rascunho-select").value);
      if (!id) { resetarFormularioOrcamento(); await viewOrcamentos(); return; }
      const r = await carregarRascunho(id);
      if (!r) return;
      orcRascunhoId = r.id;
      const dc = r.dados_contrato || {};
      orcItens = (r.detalhamento_itens || []).map((it) => ({
        nome: it.Item, descricao: it["Descrição"] || "", quantidade: Number(it.Qtd) || 0,
        custo_unitario: Number(it["Custo Un."]) || 0, venda_unitario: Number(it["Venda Un."]) || 0,
      }));
      await viewOrcamentos();
      document.getElementById("orc-nome").value = r.nome_cliente || "";
      document.getElementById("orc-whatsapp").value = r.telefone_cliente || "";
      document.getElementById("orc-endereco").value = r.endereco_cliente || "";
      document.getElementById("orc-servico-desc").value = r.servicos_adquiridos || "";
      document.getElementById("orc-servico-valor").value = dc.val_servico || 0;
      document.getElementById("orc-outros-desc").value = dc.txt_outros || "";
      document.getElementById("orc-outros-valor").value = dc.val_outros || 0;
      document.getElementById("orc-obs").value = dc.obs_pdf || "Material Hidráulico não incluído na proposta";
      renderizarItensOrcamento();
    });
    document.getElementById("btn-orc-excluir").addEventListener("click", async () => {
      const id = Number(document.getElementById("orc-rascunho-select").value);
      if (!id) return;
      if (!confirm("Excluir este rascunho permanentemente?")) return;
      await excluirRascunho(id);
      if (orcRascunhoId === id) resetarFormularioOrcamento();
      await viewOrcamentos();
    });
  }

  document.getElementById("btn-orc-calcular").addEventListener("click", async () => {
    const v = lerValoresOrcamentoForm();
    try {
      const r = await calcularCustos({
        venda_produtos: totalOrcItens(),
        custo_produtos: orcItens.reduce((a, it) => a + Number(it.quantidade || 0) * Number(it.custo_unitario || 0), 0),
        venda_instalacao: v.valorServico, custo_instalacao: v.valorServico,
        venda_outros: v.valorOutros, custo_outros: 0,
        emite_nf: document.getElementById("cc-emite-nf").checked,
        forma_pagamento: document.getElementById("cc-pagamento").value,
        comissao_pct: Number(document.getElementById("cc-comissao").value) || 0,
        desconto_reais: Number(document.getElementById("cc-desconto").value) || 0,
      });
      const selPag = document.getElementById("cc-pagamento");
      if (selPag.options.length <= 1) {
        selPag.innerHTML = r.opcoes_pagamento.map((o) => `<option value="${escapeAttr(o)}">${escapeHTML(o)}</option>`).join("");
      }
      document.getElementById("orc-resultado-custos").innerHTML = `
        <div class="campo"><span class="rotulo">Receita Líquida</span><span>${formatarBRL(r.venda_liquida)}</span></div>
        <div class="campo"><span class="rotulo">Custo NF (${r.taxa_nf_pct}%)</span><span>${formatarBRL(r.custo_nf)}</span></div>
        <div class="campo"><span class="rotulo">Custo Cartão</span><span>${formatarBRL(r.custo_cartao)}</span></div>
        <div class="campo"><span class="rotulo">Comissão</span><span>${formatarBRL(r.custo_comissao)}</span></div>
        <div class="campo"><span class="rotulo">Custo Total</span><span>${formatarBRL(r.custo_total)}</span></div>
        <div class="campo" style="background:#e6ffe6; padding:8px; border-radius:6px; margin-top:6px;">
          <span style="font-weight:800; color:#006600;">💸 Lucro Líquido</span>
          <span style="font-weight:800; color:#006600;">${formatarBRL(r.lucro_liquido)} (${r.margem_pct.toFixed(1)}%)</span>
        </div>`;
    } catch (e) {
      alert("Não deu pra calcular agora — confira sua internet e tente de novo.");
    }
  });

  document.getElementById("btn-orc-previa").addEventListener("click", async () => {
    const v = lerValoresOrcamentoForm();
    if (!v.nomeCliente) { alert("Preencha o nome do cliente!"); return; }
    if (!orcNumeroProposta) orcNumeroProposta = new Date().toISOString().replace(/[-:T]/g, "").slice(2, 11);
    const btn = document.getElementById("btn-orc-previa");
    btn.disabled = true; btn.textContent = "Gerando...";
    try {
      const r = await gerarPdfOrcamento({
        nome_cliente: v.nomeCliente, telefone: v.telefone, endereco: v.endereco,
        modelo_capa: v.modeloCapa, itens: orcItens,
        descricao_servico: v.descricaoServico, valor_servico: v.valorServico,
        descricao_outros: v.descricaoOutros, valor_outros: v.valorOutros,
        observacoes: v.observacoes, mostrar_precos_unitarios: v.mostrarPrecos,
        detalhar_itens_pdf: v.detalharItens, numero_orcamento: orcNumeroProposta,
      });
      orcPdfAtual = r;
      const blob = await (await fetch(`data:application/pdf;base64,${r.pdf_base64}`)).blob();
      const url = URL.createObjectURL(blob);
      document.getElementById("orc-resultado-pdf").innerHTML = `
        <div class="cartao">
          <div class="cartao-titulo">✅ PDF gerado — ${escapeHTML(r.nome_arquivo)}</div>
          <a href="${url}" download="${escapeAttr(r.nome_arquivo)}" class="botao botao--secundario" style="display:block; text-align:center; margin-top:6px;">📥 Baixar PDF</a>
          ${r.drive_link ? `<a href="${r.drive_link}" target="_blank" class="botao botao--secundario" style="display:block; text-align:center; margin-top:6px;">☁️ Abrir no Drive</a>` : ""}
        </div>`;
    } catch (e) {
      alert("Não deu pra gerar o PDF agora — confira sua internet e tente de novo.\n" + e.message);
    } finally {
      btn.disabled = false; btn.textContent = "👁️ Gerar Prévia (PDF)";
    }
  });

  document.getElementById("btn-orc-rascunho").addEventListener("click", async () => {
    const v = lerValoresOrcamentoForm();
    if (!v.nomeCliente) { alert("Preencha ao menos o nome do cliente!"); return; }
    try {
      orcRascunhoId = await salvarOrcamento({
        status: "Rascunho", rascunhoId: orcRascunhoId,
        numeroOrcamento: orcNumeroProposta || `RASC-${Date.now()}`,
        dados: { nomeCliente: v.nomeCliente, telefone: v.telefone, endereco: v.endereco, itens: orcItens,
          descricaoServico: v.descricaoServico, valorServico: v.valorServico,
          descricaoOutros: v.descricaoOutros, valorOutros: v.valorOutros,
          observacoes: v.observacoes, totalInvestimento: totalOrcItens() + v.valorServico + v.valorOutros },
      });
      alert("✅ Rascunho salvo!");
    } catch (e) {
      alert("Não deu pra salvar o rascunho agora — confira sua internet e tente de novo.");
    }
  });

  document.getElementById("btn-orc-salvar").addEventListener("click", async () => {
    const v = lerValoresOrcamentoForm();
    if (!v.nomeCliente) { alert("Preencha o nome do cliente!"); return; }
    if (!orcNumeroProposta) orcNumeroProposta = new Date().toISOString().replace(/[-:T]/g, "").slice(2, 11);
    try {
      await salvarOrcamento({
        status: "Orçamento Enviado", rascunhoId: orcRascunhoId, numeroOrcamento: `ORC-${orcNumeroProposta}`,
        dados: { nomeCliente: v.nomeCliente, telefone: v.telefone, endereco: v.endereco, itens: orcItens,
          descricaoServico: v.descricaoServico, valorServico: v.valorServico,
          descricaoOutros: v.descricaoOutros, valorOutros: v.valorOutros,
          observacoes: v.observacoes, totalInvestimento: totalOrcItens() + v.valorServico + v.valorOutros },
      });
      alert("✅ Orçamento salvo com sucesso no sistema!");
      resetarFormularioOrcamento();
      await viewOrcamentos();
    } catch (e) {
      alert("Não deu pra salvar agora — confira sua internet e tente de novo.");
    }
  });
}

// ---------- Boot ----------
async function iniciarApp() {
  // Admin (Breno) não é vinculado a um instalador específico — as telas de
  // Instalações/Agenda/Materiais/Financeiro (e a sincronização automática)
  // são filtradas por instalador e ficariam vazias/sem sentido pra ele, então
  // cai direto na aba nova (Orçamentos). As outras abas continuam no menu,
  // mas assumem um instalador vinculado — não são o foco do acesso admin.
  if (sessao.admin) {
    await viewOrcamentos();
    return;
  }
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
