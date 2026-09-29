// Instalação do app no celular (PWA) e atualização automática.
import { abrirSheet, toast } from "./ui.js";
import { VERSAO } from "./versao.js";

// O Chrome/Android avisa que dá pra instalar — guardamos o evento pra usar no nosso botão.
let promptInstalar = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  promptInstalar = e;
  document.dispatchEvent(new Event("pode-instalar"));
});
window.addEventListener("appinstalled", () => {
  promptInstalar = null;
  toast("App instalado! Procure o ícone Evolua na tela inicial 🎉");
});

export const ehIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
export const rodandoInstalado = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

export async function instalar() {
  if (rodandoInstalado()) return toast("O app já está instalado neste aparelho ✅");
  if (promptInstalar) {
    promptInstalar.prompt();
    const { outcome } = await promptInstalar.userChoice;
    promptInstalar = null;
    if (outcome === "accepted") return;
  }
  // iPhone (Safari não tem botão automático) ou navegador sem suporte: passo a passo
  abrirSheet(ehIOS() ? `
    <h2>📲 Instalar no iPhone</h2>
    <ol class="passos-inst">
      <li>Abra este site no <b>Safari</b> (no Chrome do iPhone não funciona).</li>
      <li>Toque no botão <b>Compartilhar</b> <span class="ic-ios">⬆︎</span> (quadrado com seta, na barra de baixo).</li>
      <li>Role e toque em <b>"Adicionar à Tela de Início"</b>.</li>
      <li>Toque em <b>Adicionar</b>. Pronto — o ícone Evolua aparece junto dos seus apps.</li>
    </ol>
    <p class="nota">Depois de instalado, as atualizações chegam sozinhas quando você abre o app.</p>` : `
    <h2>📲 Instalar no celular</h2>
    <ol class="passos-inst">
      <li>Abra este site no <b>Google Chrome</b>.</li>
      <li>Toque nos <b>⋮ três pontinhos</b> (canto superior direito).</li>
      <li>Toque em <b>"Instalar app"</b> ou <b>"Adicionar à tela inicial"</b>.</li>
      <li>Confirme. O ícone Evolua aparece junto dos seus apps.</li>
    </ol>
    <p class="nota">Depois de instalado, as atualizações chegam sozinhas quando você abre o app.</p>`);
}

// ---------- Atualização automática ----------
// Procura versão nova ao abrir, ao voltar pro app e a cada 30 min. Quando o
// service worker novo assume, recarrega na hora — mas nunca no meio de algo
// sendo digitado ou de uma janela aberta (espera o próximo momento livre).
export function iniciarAtualizacaoAutomatica() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("./sw.js").then((reg) => {
    const verificar = () => reg.update().catch(() => {});
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") verificar(); });
    setInterval(verificar, 30 * 60 * 1000);
  }).catch(() => {});

  let pendente = false;
  const ocupado = () => {
    const el = document.activeElement;
    return !!document.querySelector(".sheet-fundo, .camera") || (el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
  };
  const recarregar = () => {
    if (window.__recarregando) return;
    if (ocupado()) { pendente = true; return; }
    window.__recarregando = true;
    location.reload();
  };
  navigator.serviceWorker.addEventListener("controllerchange", recarregar);
  const tentarPendente = () => { if (pendente) recarregar(); };
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") tentarPendente(); });
  setInterval(tentarPendente, 15000);

  // Avisa depois que atualizou
  try {
    const ultima = localStorage.getItem("fit-versao");
    if (ultima && ultima !== VERSAO) setTimeout(() => toast(`✨ App atualizado para a versão ${VERSAO}`), 1200);
    localStorage.setItem("fit-versao", VERSAO);
  } catch (e) { /* modo privado */ }
}

// Cartão "instale o app" pra tela inicial (some depois de instalado ou dispensado)
export function deveSugerirInstalar() {
  if (rodandoInstalado()) return false;
  try { return localStorage.getItem("fit-inst-dispensado") !== "1"; } catch (e) { return true; }
}
export function dispensarSugestao() {
  try { localStorage.setItem("fit-inst-dispensado", "1"); } catch (e) { /* ok */ }
}
