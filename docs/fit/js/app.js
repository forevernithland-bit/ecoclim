// Ponto de entrada: decide entre boas-vindas/login, cadastro inicial e o app
// com as abas (Hoje, Comida, Treino, Evolução, Coach).
import { carregarEstado, E } from "./estado.js";
import { kvSet, todos } from "./db.js";
import { cadastrar, entrar, usuarioAtual, puxarTudo, iniciarSyncAutomatico, aoMudarSync, enfileirar } from "./nuvem.js";
import { esc, toast } from "./ui.js";
import { rodarOnboarding } from "./telas/onboarding.js";
import { telaHoje } from "./telas/hoje.js";
import { telaComida, resetDiaComida } from "./telas/comida.js";
import { telaTreino } from "./telas/treino.js";
import { telaEvolucao } from "./telas/evolucao.js";
import { telaCoach, abrirAgente } from "./telas/coach.js";
import { telaPerfil } from "./telas/perfil.js";

const raiz = document.getElementById("app");

const ABAS = [
  { id: "hoje", nome: "Hoje", icone: '<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>', tela: telaHoje },
  { id: "comida", nome: "Comida", icone: '<path d="M7 2v8a3 3 0 0 0 3 3v9M4 2v6a3 3 0 0 0 3 3M10 2v6M17 22V2c-2.5 1-4 4-4 8v4h4"/>', tela: telaComida },
  { id: "treino", nome: "Treino", icone: '<path d="M6.5 6.5v11M17.5 6.5v11M3 9.5v5M21 9.5v5M6.5 12h11"/>', tela: telaTreino },
  { id: "evolucao", nome: "Evolução", icone: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>', tela: telaEvolucao },
  { id: "coach", nome: "Coach", icone: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>', tela: telaCoach },
];

let abaAtual = "hoje";

async function ir(aba, opts = {}) {
  if (aba === "coach" && opts.agente) abrirAgente(opts.agente);
  if (aba === "comida" && abaAtual !== "comida") resetDiaComida();
  abaAtual = aba;
  window.scrollTo(0, 0);
  await renderApp();
}

async function renderApp() {
  if (!raiz.querySelector(".app-casca")) {
    raiz.innerHTML = `
      <div class="app-casca">
        <div id="faixa-sync" class="faixa-sync oculto"></div>
        <main id="tela"></main>
        <nav class="nav">${ABAS.map((a) => `
          <button class="nav-b" data-aba="${a.id}" aria-label="${a.nome}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${a.icone}</svg>
            <span>${a.nome}</span>
          </button>`).join("")}</nav>
      </div>`;
    raiz.querySelectorAll(".nav-b").forEach((b) => b.onclick = () => ir(b.dataset.aba));
  }
  raiz.querySelectorAll(".nav-b").forEach((b) => b.classList.toggle("nav-b--on", b.dataset.aba === abaAtual));
  const tela = raiz.querySelector("#tela");
  const ctx = { rerender: renderApp, ir };
  try {
    if (abaAtual === "perfil") await telaPerfil(tela, ctx);
    else await ABAS.find((a) => a.id === abaAtual).tela(tela, ctx);
  } catch (e) {
    console.error(e);
    tela.innerHTML = `<div class="vazio"><span>😵</span><p>Algo deu errado nesta tela.<br><small>${esc(e.message)}</small></p><button class="btn" onclick="location.reload()">Recarregar</button></div>`;
  }
}

// ---------- Boas-vindas / login ----------
function telaBoasVindas(aoEntrar) {
  let modo = "cadastro";
  const pinta = () => {
    raiz.innerHTML = `
      <div class="boas-vindas">
        <div class="bv-arte" aria-hidden="true"><div class="bv-bola b1"></div><div class="bv-bola b2"></div><div class="bv-bola b3"></div></div>
        <div class="bv-logo"><img src="./icons/icon-192.png" alt=""></div>
        <h1>Evolua</h1>
        <p class="sub">Emagreça ou ganhe massa com uma nutricionista e um personal de IA no seu bolso. Tudo baseado na ciência, explicado de um jeito simples.</p>
        <ul class="bv-lista">
          <li>📸 Foto do prato → calorias na hora</li>
          <li>🏋️ Treino que evolui com você, com vídeos</li>
          <li>📊 Antes × depois com fotos e medidas</li>
        </ul>
        <form class="bv-form" id="form">
          <input class="campo" id="email" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="Usuário ou e-mail" required>
          <input class="campo" id="senha" type="password" autocomplete="${modo === "cadastro" ? "new-password" : "current-password"}" placeholder="Senha (mín. 4 caracteres)" required minlength="4">
          <button class="btn btn--grande" id="ok">${modo === "cadastro" ? "Criar minha conta" : "Entrar"}</button>
          <p class="erro-txt" id="erro"></p>
        </form>
        <button class="link" id="trocar">${modo === "cadastro" ? "Já tenho conta" : "Criar conta nova"}</button>
        <button class="link link--fraco" id="local">Só quero testar (sem conta, sem IA)</button>
        <p class="assinatura">Desenvolvido por <b>Breno Lima</b></p>
      </div>`;
    raiz.querySelector("#trocar").onclick = () => { modo = modo === "cadastro" ? "entrar" : "cadastro"; pinta(); };
    raiz.querySelector("#local").onclick = async () => { await kvSet("modoLocal", true); E.modoLocal = true; aoEntrar(); };
    raiz.querySelector("#form").onsubmit = async (e) => {
      e.preventDefault();
      const btn = raiz.querySelector("#ok");
      btn.disabled = true; btn.textContent = "Aguarde…";
      const email = raiz.querySelector("#email").value, senha = raiz.querySelector("#senha").value;
      const r = modo === "cadastro" ? await cadastrar(email, senha) : await entrar(email, senha);
      if (!r.ok) {
        raiz.querySelector("#erro").textContent = r.erro;
        btn.disabled = false; btn.textContent = modo === "cadastro" ? "Criar minha conta" : "Entrar";
        if (r.confirmar) { modo = "entrar"; setTimeout(pinta, 4000); }
        return;
      }
      await kvSet("modoLocal", false);
      E.modoLocal = false;
      if (E.perfil) {
        // Vinha do modo teste: sobe o que já foi registrado neste aparelho.
        btn.textContent = "Enviando seus dados…";
        await kvSet("perfilSujo", true);
        for (const s of ["refeicoes", "checkins", "treinos", "chat", "metricas", "comparativos"]) {
          for (const r of await todos(s)) await enfileirar(s, r.id);
        }
      } else {
        btn.textContent = "Buscando seus dados…";
        try { await puxarTudo(); } catch (e2) { /* primeira vez: nada na nuvem */ }
      }
      await carregarEstado();
      aoEntrar();
    };
  };
  pinta();
}

function mostrarSync(status) {
  const f = document.getElementById("faixa-sync");
  if (!f) return;
  if (status === "erro" && !navigator.onLine) { f.className = "faixa-sync"; f.textContent = "Sem internet — seus registros ficam salvos e sobem sozinhos depois."; }
  else f.className = "faixa-sync oculto";
}

async function iniciar() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!window.__recarregando) { window.__recarregando = true; location.reload(); }
    });
  }
  await carregarEstado();
  const user = E.modoLocal ? null : await usuarioAtual();

  const seguir = () => {
    if (!E.modoLocal) { iniciarSyncAutomatico(); aoMudarSync(mostrarSync); }
    if (!E.perfil || !E.plano) {
      rodarOnboarding(raiz, async () => { await carregarEstado(); raiz.innerHTML = ""; abaAtual = "hoje"; renderApp(); toast("Bem-vindo(a)! Seu plano está pronto 🎉"); });
    } else {
      renderApp();
    }
  };

  if (user || E.modoLocal) seguir();
  else telaBoasVindas(seguir);
}

window.addEventListener("online", () => mostrarSync("ok"));
window.addEventListener("offline", () => mostrarSync("erro"));
iniciar();
