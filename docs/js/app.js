import { login, sessaoAtual, logout } from "./auth.js";
import { lerServicos, lerServico, enfileirar } from "./db.js";
import { sincronizarTudo, iniciarSyncAutomatico, statusAtual, aoMudarStatusSync } from "./sync.js";

const raiz = document.getElementById("app");
let sessao = null;
// Qual tela está visível agora — usado só pra decidir se o sync em segundo
// plano pode redesenhar a lista sozinho (nunca redesenha a tela de detalhe:
// o instalador pode estar digitando uma observação, e um sync automático no
// meio disso não pode apagar o que ele ainda não terminou de escrever).
let telaAtual = null;

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

async function viewLista() {
  telaAtual = "lista";
  const todos = await lerServicos();
  const abertos = todos.filter((s) => !s.instalacao_concluida_instalador);
  const concluidos = todos.filter((s) => s.instalacao_concluida_instalador);

  const cartao = (s) => `
    <button class="cartao cartao--clicavel" data-id="${s.id}">
      <div class="cartao-titulo">${escapeHTML(s.nome_cliente || "Sem nome")}</div>
      <div class="cartao-sub">${escapeHTML(s.produtos_adquiridos || "")}</div>
      <div class="cartao-rodape">
        <span class="etiqueta">${escapeHTML(s.status_projeto || "")}</span>
        ${s.instalacao_concluida_instalador
          ? `<span class="etiqueta etiqueta--ok">✅ ${formatarData(s.data_conclusao_instalador)}</span>`
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
        <h2 class="secao-titulo">✅ Concluídas (${concluidos.length})</h2>
        ${concluidos.map(cartao).join("")}
      ` : ""}
    </div>
  `;

  document.getElementById("btn-sair").addEventListener("click", async () => {
    await logout();
    sessao = null;
    viewLogin();
  });
  raiz.querySelectorAll(".cartao--clicavel").forEach((el) => {
    el.addEventListener("click", () => viewDetalhe(Number(el.dataset.id)));
  });

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
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
        <h3 class="cartao-secao">📝 Observação</h3>
        <textarea id="in-obs" rows="4" placeholder="Deixe aqui alguma observação sobre esta instalação...">${escapeHTML(s.observacao_instalador || "")}</textarea>
        <button id="btn-salvar-obs" class="botao botao--secundario">💾 Salvar Observação</button>
      </div>

      <div class="cartao" id="cartao-concluir">
        ${s.instalacao_concluida_instalador
          ? `<p class="valor-somente-leitura">✅ Instalação concluída em ${formatarData(s.data_conclusao_instalador)}</p>`
          : `<button id="btn-concluir" class="botao botao--principal">✅ Marcar Instalação Concluída</button>`}
      </div>
    </div>
  `;

  document.getElementById("btn-voltar").addEventListener("click", viewLista);

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
        await enfileirar(id, {
          instalacao_concluida_instalador: true,
          data_conclusao_instalador: hojeLocalISO(),
        });
        sincronizarTudo(sessao.instaladorVinculado);
        await viewDetalhe(id);
      });
      document.getElementById("btn-cancelar-conclusao").addEventListener("click", () => {
        viewDetalhe(id);
      });
    });
  }

  const { pendentes } = await statusAtual();
  renderFaixaSync(navigator.onLine ? "sincronizado" : "offline", pendentes);
}

// ---------- Boot ----------
async function iniciarApp() {
  await viewLista();
  iniciarSyncAutomatico(sessao.instaladorVinculado);
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
