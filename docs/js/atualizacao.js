/** Atualização do app sem reinstalar.
 *
 * O Service Worker guarda o app pra funcionar offline — o efeito colateral é
 * que, depois de publicada uma versão nova, o celular pode continuar abrindo
 * a antiga. Antes a saída era desinstalar e instalar de novo; aqui o próprio
 * app percebe que existe versão nova e oferece um botão pra aplicar.
 */

export const VERSAO_APP = "2026.09.03-1"; // suba junto com o CACHE do sw.js

let aoDetectar = null;

/** Liga o aviso automático. `callback` roda quando uma versão nova entrou. */
export function observarAtualizacoes(callback) {
  if (!("serviceWorker" in navigator)) return;
  aoDetectar = callback;

  // Dispara quando um SW novo assume o controle: a tela ainda está rodando o
  // código antigo, então é exatamente a hora de oferecer o recarregamento.
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (aoDetectar) aoDetectar();
  });

  navigator.serviceWorker.getRegistration().then((reg) => {
    if (!reg) return;
    reg.addEventListener("updatefound", () => {
      const novo = reg.installing;
      if (!novo) return;
      novo.addEventListener("statechange", () => {
        // "installed" com controller existente = já havia versão rodando,
        // ou seja, isto é uma atualização e não a primeira instalação.
        if (novo.state === "installed" && navigator.serviceWorker.controller && aoDetectar) {
          aoDetectar();
        }
      });
    });
  });
}

/** Pergunta ao servidor se existe versão nova. Retorna true se encontrou. */
export async function verificarAtualizacao() {
  if (!("serviceWorker" in navigator)) return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) return false;
    await reg.update();          // vai à rede buscar o sw.js
    return Boolean(reg.waiting || reg.installing);
  } catch (e) {
    return false;
  }
}

/** Aplica a versão nova: descarta o cache velho e recarrega a tela. */
export async function aplicarAtualizacao() {
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    if (reg && reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });
    // Limpar os caches garante que nenhum arquivo antigo sobreviva à troca —
    // o SW novo recria tudo no próximo carregamento.
    if ("caches" in window) {
      const chaves = await caches.keys();
      await Promise.all(chaves.map((k) => caches.delete(k)));
    }
  } catch (e) {
    /* mesmo falhando a limpeza, o reload abaixo já resolve na maioria dos casos */
  }
  window.location.reload();
}
