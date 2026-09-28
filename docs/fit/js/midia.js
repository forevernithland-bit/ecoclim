// Fotos (compressão no aparelho antes de guardar/enviar) e voz (ditado).

// Reduz a foto pra no máximo `lado` px e JPEG — foto de 4 MB do celular vira
// ~150 KB, cabe no banco local e sobe rápido mesmo no 4G.
export async function comprimirImagem(arquivo, lado = 1280, qualidade = 0.82) {
  const bmp = await carregarBitmap(arquivo);
  const escala = Math.min(1, lado / Math.max(bmp.width, bmp.height));
  const w = Math.round(bmp.width * escala), h = Math.round(bmp.height * escala);
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  canvas.getContext("2d").drawImage(bmp, 0, 0, w, h);
  return new Promise((res) => canvas.toBlob(res, "image/jpeg", qualidade));
}

async function carregarBitmap(arquivo) {
  if ("createImageBitmap" in window) {
    try { return await createImageBitmap(arquivo, { imageOrientation: "from-image" }); } catch (e) { /* cai no <img> */ }
  }
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = rej;
    img.src = URL.createObjectURL(arquivo);
  });
}

export function blobParaBase64(blob) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1]);
    r.onerror = rej;
    r.readAsDataURL(blob);
  });
}

const urls = new Map();
// URL de exibição para um Blob guardado (reaproveita pra não vazar memória).
export function urlDe(blob, chave) {
  if (!blob) return "";
  if (chave && urls.has(chave)) return urls.get(chave);
  const u = URL.createObjectURL(blob);
  if (chave) urls.set(chave, u);
  return u;
}

// Abre a câmera/galeria e devolve a foto já comprimida.
export function escolherFoto({ camera = true } = {}) {
  return new Promise((res) => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = "image/*";
    if (camera) inp.capture = "environment";
    inp.onchange = async () => {
      const f = inp.files && inp.files[0];
      res(f ? await comprimirImagem(f) : null);
    };
    inp.click();
  });
}

// ---------- Voz ----------
const Reconhecimento = window.SpeechRecognition || window.webkitSpeechRecognition;
export const suportaVoz = !!Reconhecimento;

// Ditado em português: devolve o texto conforme a pessoa fala (parcial) e o final.
export function ouvir({ aoParcial, aoFinal, aoErro }) {
  if (!Reconhecimento) { aoErro && aoErro("Seu navegador não suporta ditado por voz. Use o teclado (o microfone do teclado também funciona!)."); return null; }
  const r = new Reconhecimento();
  r.lang = "pt-BR";
  r.interimResults = true;
  r.continuous = true;
  let final = "";
  r.onresult = (ev) => {
    let parcial = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) final += t + " ";
      else parcial += t;
    }
    aoParcial && aoParcial((final + parcial).trim());
  };
  r.onerror = (e) => aoErro && aoErro(e.error === "not-allowed" ? "Permita o uso do microfone para falar a refeição." : "Não entendi, tente de novo.");
  r.onend = () => aoFinal && aoFinal(final.trim());
  r.start();
  return r;
}
