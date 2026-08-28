import { API_BASE } from "./config.js";

// Chave pública do servidor — pode ficar no app, é ela que identifica quem
// tem permissão de mandar notificação pra este app. A privada fica só no
// servidor.
const VAPID_PUBLIC = "BAuussOkrNIF1ZA_5awDoaC1JG7USV_gaPSk4rPqXYHnvjeWk7Q4IxZtcuscw5kSpI_w98Uyg2OGQ08eHEp6idI";

function base64ParaUint8(base64) {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64);
  return Uint8Array.from([...bin].map((c) => c.charCodeAt(0)));
}

export function suportaPush() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function rodandoInstalado() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

export function ehIOS() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

/** No iPhone a Apple só entrega push pra app instalado na tela inicial —
 *  pedir permissão no Safari comum falha e ainda queima a chance de pedir
 *  de novo, então nem oferecemos nesse caso. */
export function podePedirPermissao() {
  if (!suportaPush()) return false;
  if (ehIOS() && !rodandoInstalado()) return false;
  return Notification.permission === "default";
}

export function permissaoConcedida() {
  return suportaPush() && Notification.permission === "granted";
}

/** Pede permissão e registra o aparelho no servidor.
 *  Precisa ser chamado a partir de um toque do usuário — navegador nenhum
 *  aceita pedido de notificação vindo do nada. */
export async function ativarNotificacoes(sessao) {
  if (!suportaPush()) {
    return { ok: false, erro: "Este aparelho não suporta notificações." };
  }
  if (ehIOS() && !rodandoInstalado()) {
    return { ok: false, erro: "No iPhone é preciso instalar o app na tela de início para receber avisos." };
  }

  let permissao = Notification.permission;
  if (permissao === "default") permissao = await Notification.requestPermission();
  if (permissao !== "granted") {
    return { ok: false, erro: "Você não autorizou as notificações." };
  }

  try {
    const reg = await navigator.serviceWorker.ready;
    // Reaproveita a assinatura existente; criar outra geraria aviso duplicado.
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,   // exigido: todo push tem que virar aviso visível
        applicationServerKey: base64ParaUint8(VAPID_PUBLIC),
      });
    }
    const json = sub.toJSON();
    const resp = await fetch(`${API_BASE}/push/registrar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario: sessao.usuario,
        perfil: sessao.admin ? "Admin" : "Instalador",
        instalador_vinculado: sessao.instaladorVinculado || null,
        endpoint: sub.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
        user_agent: navigator.userAgent.slice(0, 250),
      }),
    });
    if (!resp.ok) return { ok: false, erro: "Não consegui registrar no servidor." };
    return { ok: true };
  } catch (e) {
    return { ok: false, erro: e.message || "Falha ao ativar notificações." };
  }
}

/** Avisa alguém — usado quando o instalador faz algo que o Breno precisa saber. */
export async function notificar({ titulo, mensagem, perfil, instalador, usuario, tag }) {
  try {
    await fetch(`${API_BASE}/push/enviar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, mensagem, perfil, instalador, usuario, tag }),
    });
  } catch (e) {
    // Notificação é acessório: se falhar, o que o usuário salvou continua salvo.
  }
}

/** Limpa o selo numérico do ícone quando a pessoa abre o app. */
export function limparSelo() {
  if ("clearAppBadge" in navigator) navigator.clearAppBadge().catch(() => {});
}
