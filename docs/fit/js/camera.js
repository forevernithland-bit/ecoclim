// Câmera de check-in: mostra a foto anterior "fantasma" por cima da imagem ao
// vivo, pra repetir exatamente a mesma pose/distância — é o que torna a
// comparação antes/depois confiável. Tem temporizador (celular apoiado).
// Sem getUserMedia (ou permissão negada) cai no seletor de arquivo comum.
import { comprimirImagem, escolherFoto, urlDe } from "./midia.js";

export async function fotografarCorpo({ titulo = "Foto", fantasma = null } = {}) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return escolherFoto({ camera: true });
  return new Promise((resolver) => {
    const tela = document.createElement("div");
    tela.className = "camera";
    tela.innerHTML = `
      <video playsinline autoplay muted></video>
      ${fantasma ? `<img class="camera-fantasma" src="${urlDe(fantasma)}" alt="">` : `<svg class="camera-guia" viewBox="0 0 60 120"><circle cx="30" cy="14" r="9"/><path d="M16 28h28l6 36-7 2-4-26v76h-8V80h-2v36h-8V40l-4 26-7-2z"/></svg>`}
      <div class="camera-topo">
        <button class="camera-b" data-a="fechar" aria-label="Fechar">✕</button>
        <b>${titulo}</b>
        <button class="camera-b" data-a="virar" aria-label="Trocar câmera">🔄</button>
      </div>
      <div class="camera-contagem oculto"></div>
      <div class="camera-base">
        ${fantasma ? `<label class="camera-op"><input type="range" min="0" max="70" value="35" data-a="opac"> Guia</label>` : `<span class="camera-op">Encaixe o corpo na silhueta</span>`}
        <button class="camera-disparo" data-a="foto" aria-label="Tirar foto"></button>
        <button class="camera-b camera-b--txt" data-a="timer">⏱ 10s</button>
      </div>
      <button class="camera-galeria" data-a="galeria">Escolher da galeria</button>`;
    document.body.appendChild(tela);
    document.body.classList.add("sem-rolagem");
    const video = tela.querySelector("video");
    let stream = null;
    let frente = false;
    let timer = false;

    const parar = () => { if (stream) stream.getTracks().forEach((t) => t.stop()); };
    const fim = (v) => { parar(); tela.remove(); document.body.classList.remove("sem-rolagem"); resolver(v); };

    const ligar = async () => {
      parar();
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: frente ? "user" : "environment", width: { ideal: 1920 }, height: { ideal: 1920 } }, audio: false });
        video.srcObject = stream;
        video.classList.toggle("espelho", frente);
      } catch (e) {
        fim(await escolherFoto({ camera: true }));
      }
    };

    const capturar = async () => {
      const c = document.createElement("canvas");
      c.width = video.videoWidth; c.height = video.videoHeight;
      const ctx = c.getContext("2d");
      if (frente) { ctx.translate(c.width, 0); ctx.scale(-1, 1); }
      ctx.drawImage(video, 0, 0);
      const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
      fim(await comprimirImagem(blob));
    };

    tela.addEventListener("click", async (ev) => {
      const a = ev.target.closest("[data-a]");
      if (!a) return;
      const acao = a.dataset.a;
      if (acao === "fechar") fim(null);
      if (acao === "virar") { frente = !frente; ligar(); }
      if (acao === "galeria") { parar(); const f = await escolherFoto({ camera: false }); tela.remove(); document.body.classList.remove("sem-rolagem"); resolver(f); }
      if (acao === "timer") { timer = !timer; a.classList.toggle("camera-b--on", timer); }
      if (acao === "foto") {
        if (!timer) return capturar();
        const cont = tela.querySelector(".camera-contagem");
        cont.classList.remove("oculto");
        for (let s = 10; s > 0; s--) {
          cont.textContent = s;
          if (navigator.vibrate && s <= 3) navigator.vibrate(60);
          await new Promise((r) => setTimeout(r, 1000));
        }
        cont.classList.add("oculto");
        capturar();
      }
    });
    const op = tela.querySelector('[data-a="opac"]');
    if (op) op.oninput = () => { tela.querySelector(".camera-fantasma").style.opacity = op.value / 100; };
    ligar();
  });
}
