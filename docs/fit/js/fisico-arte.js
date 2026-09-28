// Figura ilustrada de físico (SVG gerado). A mesma função desenha o físico-alvo
// e o físico ATUAL da pessoa (a partir do % de gordura e FFMI dela), então dá
// pra mostrar "você hoje → você no objetivo" com o mesmo estilo visual.
//
// Fotos reais: coloque imagens licenciadas em pwa/img/fisicos/<M|F>-<id>.jpg
// (ex.: M-atletico.jpg). Se o arquivo existir, a foto aparece por cima da
// ilustração; se não existir, fica a ilustração.

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
let seq = 0;

export function parametros(sexo, gordura, ffmi) {
  const m = sexo === "F" ? clamp((ffmi - 14.5) / 5.5, 0, 1.2) : clamp((ffmi - 18) / 6.5, 0, 1.2);
  const f = sexo === "F" ? clamp((gordura - 13) / 22, 0, 1.3) : clamp((gordura - 6) / 22, 0, 1.3);
  return { m, f };
}

export function desenharFisico(sexo, gordura, ffmi, { classe = "fig", destaque = false } = {}) {
  const { m, f } = parametros(sexo, gordura, ffmi);
  const F = sexo === "F";
  const id = `g${++seq}`;
  const cx = 60;

  // meias-larguras do tronco em cada altura (y)
  const pesc = F ? 5.5 + 1.2 * m : 7 + 3.5 * m;
  const ombro = F ? 19 + 6 * m + 2.5 * f : 23 + 12 * m + 2 * f;
  const axila = F ? 16 + 4 * m + 4 * f : 19 + 8 * m + 4 * f;
  const peito = F ? 15.5 + 2.5 * m + 6 * f : 18 + 6 * m + 5 * f;
  const cintura = F ? 11 + 1 * m + 13 * f : 13.5 + 1.5 * m + 15 * f;
  const barriga = F ? 12 + 15 * f : 14.5 + 1.5 * m + 18 * f;
  const quadril = F ? 20 + 3 * m + 9 * f : 18 + 2.5 * m + 6 * f;
  const coxa = F ? 9.5 + 3.5 * m + 5 * f : 9.5 + 5 * m + 4 * f;
  const joelho = F ? 6 + 0.6 * m + 1.4 * f : 6.3 + 1 * m + 1.2 * f;
  const pant = F ? 5.6 + 1.4 * m + 1.6 * f : 5.8 + 2.4 * m + 1.2 * f;
  const tornoz = 3.4;
  const braco = F ? 4.3 + 2.4 * m + 2.6 * f : 4.8 + 5 * m + 2.2 * f;
  const antebr = F ? 3.7 + 1.2 * m + 1 * f : 4 + 2.6 * m + 0.8 * f;

  const yO = 50, yAx = 64, yP = 78, yC = 102, yB = 112, yQ = 128, yG = 140;
  // Tronco (lado direito, depois espelhado)
  const ladoD = [
    `M${cx + pesc},38`,
    `C${cx + pesc},44 ${cx + ombro - 8},${yO - 5} ${cx + ombro},${yO}`,
    `C${cx + ombro + 2},${yO + 6} ${cx + axila + 1},${yAx - 4} ${cx + axila},${yAx}`,
    `C${cx + peito},${yP - 6} ${cx + peito},${yP} ${cx + (peito + cintura) / 2},${(yP + yC) / 2}`,
    `C${cx + cintura},${yC - 6} ${cx + cintura},${yC} ${cx + barriga},${yB}`,
    `C${cx + quadril},${yQ - 8} ${cx + quadril},${yQ} ${cx + quadril - 1},${yG}`,
  ].join(" ");
  const tronco = `${ladoD} L${cx - quadril + 1},${yG} ` + [
    `C${cx - quadril},${yQ} ${cx - quadril},${yQ - 8} ${cx - barriga},${yB}`,
    `C${cx - cintura},${yC} ${cx - cintura},${yC - 6} ${cx - (peito + cintura) / 2},${(yP + yC) / 2}`,
    `C${cx - peito},${yP} ${cx - peito},${yP - 6} ${cx - axila},${yAx}`,
    `C${cx - axila - 1},${yAx - 4} ${cx - ombro - 2},${yO + 6} ${cx - ombro},${yO}`,
    `C${cx - ombro + 8},${yO - 5} ${cx - pesc},44 ${cx - pesc},38 Z`,
  ].join(" ");

  // Braço como cápsula que afina: ombro → cotovelo → punho
  const bracoPath = (lado) => {
    const s = lado;
    const x0 = cx + s * (ombro - braco * 0.6), y0 = yO + 2;
    const x1 = cx + s * (axila + braco + 4), y1 = 100;
    const x2 = cx + s * (axila + braco + 6 + f * 2), y2 = 136;
    const bi = braco * (1 + 0.25 * m); // bíceps "enche" no meio
    return `M${x0 - s * braco},${y0}
      C${x0 + s * (bi + 2)},${y0 + 6} ${x1 + s * bi},${y1 - 20} ${x1 + s * antebr * 1.1},${y1}
      C${x1 + s * antebr * 1.3},${y1 + 12} ${x2 + s * antebr * 0.8},${y2 - 12} ${x2 + s * 2.6},${y2}
      C${x2 + s * 2},${y2 + 6} ${x2 - s * 3},${y2 + 6} ${x2 - s * 3},${y2}
      C${x2 - s * antebr * 1.2},${y2 - 14} ${x1 - s * antebr},${y1 + 8} ${x1 - s * braco * 0.9},${y1}
      C${x1 - s * braco},${y1 - 16} ${x0 - s * braco * 0.4},${y0 + 16} ${x0 - s * braco},${y0} Z`;
  };

  // Perna: quadril → joelho → tornozelo
  const pernaPath = (lado) => {
    const s = lado;
    const xe = cx + s * (quadril - 1), xi = cx + s * 1.2;
    const xm = cx + s * (quadril * 0.5 + 1);
    const yJ = 184, yT = 228;
    return `M${xi},${yG - 4} L${xe},${yG - 6}
      C${xe + s * (coxa * 0.35)},${yG + 12} ${xm + s * (joelho + coxa * 0.3)},${yJ - 22} ${xm + s * joelho},${yJ}
      C${xm + s * (pant + 1)},${yJ + 10} ${xm + s * pant},${yJ + 22} ${xm + s * tornoz},${yT}
      L${xm - s * tornoz},${yT}
      C${xm - s * (pant * 0.8)},${yJ + 22} ${xm - s * (pant * 0.9)},${yJ + 10} ${xm - s * joelho},${yJ}
      C${xm - s * (joelho + 1)},${yJ - 20} ${xi + s * 0.5},${yG + 16} ${xi},${yG - 4} Z`;
  };

  // Definição muscular: aparece com gordura baixa (opacidade proporcional)
  const def = clamp(F ? (24 - gordura) / 8 : (17 - gordura) / 8, 0, 1);
  const defPeito = clamp(F ? 0 : (22 - gordura) / 8, 0, 1) * clamp(m + 0.3, 0, 1);
  const linhas = [];
  if (defPeito > 0.05) {
    linhas.push(`<path d="M${cx - peito + 3},${yP - 2} Q${cx - 6},${yP + 4} ${cx},${yP - 3} Q${cx + 6},${yP + 4} ${cx + peito - 3},${yP - 2}" opacity="${defPeito}"/>`);
    linhas.push(`<path d="M${cx},${yAx - 8} V${yP - 3}" opacity="${defPeito * 0.7}"/>`);
  }
  if (def > 0.05) {
    const w = 5.5;
    linhas.push(`<path d="M${cx},${yP + 2} V${yB + 4}" opacity="${def}"/>`);
    for (const y of [yP + 9, yP + 17, yP + 25]) linhas.push(`<path d="M${cx - w},${y} Q${cx},${y + 1.5} ${cx + w},${y}" opacity="${def * 0.85}"/>`);
    linhas.push(`<path d="M${cx - cintura + 2},${yC - 10} Q${cx - cintura + 5},${yB} ${cx - 4},${yG - 6} M${cx + cintura - 2},${yC - 10} Q${cx + cintura - 5},${yB} ${cx + 4},${yG - 6}" opacity="${def * 0.7}"/>`);
  }
  if (m > 0.35 && def > 0.2) {
    // separação do deltoide e do quadríceps
    for (const s of [-1, 1]) {
      linhas.push(`<path d="M${cx + s * (ombro - 3)},${yO + 2} Q${cx + s * (ombro - 1)},${yAx + 2} ${cx + s * (axila + 3)},${yAx + 6}" opacity="${def * 0.6}"/>`);
      linhas.push(`<path d="M${cx + s * (quadril * 0.5 + 1 + coxa * 0.6)},${yG + 10} Q${cx + s * (quadril * 0.5)},${170} ${cx + s * (quadril * 0.5 - 2)},${180}" opacity="${def * 0.5}"/>`);
    }
  }
  const umbigo = `<ellipse cx="${cx}" cy="${yB - 2}" rx="1.1" ry="1.6" class="fig-sombra"/>`;
  const busto = F ? `<path d="M${cx - peito + 2},${yP - 4} Q${cx - peito / 2},${yP + 8 + 3 * f} ${cx - 1},${yP - 2} M${cx + 1},${yP - 2} Q${cx + peito / 2},${yP + 8 + 3 * f} ${cx + peito - 2},${yP - 4}" class="fig-linha" opacity=".55"/>` : "";

  // Roupa: short (e top) para a figura ficar "de academia"
  const short = `<path d="M${cx - quadril + 0.5},${yQ - 6} L${cx + quadril - 0.5},${yQ - 6} L${cx + quadril + 1 + coxa * 0.25},${yG + 18} L${cx + 2},${yG + 18} L${cx},${yG + 4} L${cx - 2},${yG + 18} L${cx - quadril - 1 - coxa * 0.25},${yG + 18} Z" class="fig-roupa"/>`;
  const top = F ? `<path d="M${cx - axila + 1},${yAx - 2} Q${cx},${yAx + 4} ${cx + axila - 1},${yAx - 2} L${cx + peito - 1},${yP + 6} Q${cx},${yP + 10} ${cx - peito + 1},${yP + 6} Z" class="fig-roupa"/>` : "";

  return `
  <svg viewBox="0 0 120 240" class="${classe} ${destaque ? "fig--destaque" : ""}" role="img" aria-label="Ilustração de físico">
    <defs>
      <linearGradient id="${id}" x1="0" x2="1">
        <stop offset="0" class="fig-c1"/><stop offset=".5" class="fig-c2"/><stop offset="1" class="fig-c1"/>
      </linearGradient>
    </defs>
    <ellipse cx="60" cy="234" rx="28" ry="3.5" class="fig-chao"/>
    <g fill="url(#${id})" class="fig-corpo">
      <path d="${pernaPath(-1)}"/><path d="${pernaPath(1)}"/>
      <path d="${bracoPath(-1)}"/><path d="${bracoPath(1)}"/>
      <path d="${tronco}"/>
      <ellipse cx="${cx}" cy="24" rx="${F ? 10 : 10.5}" ry="${F ? 12.5 : 13}"/>
      <rect x="${cx - pesc}" y="32" width="${pesc * 2}" height="9" rx="3"/>
    </g>
    ${F ? `<path d="M${cx - 10.5},20 Q${cx - 12},6 ${cx},10 Q${cx + 12},6 ${cx + 10.5},20 Q${cx + 13},34 ${cx + 9},40 L${cx + 8},26 Q${cx},16 ${cx - 8},26 L${cx - 9},40 Q${cx - 13},34 ${cx - 10.5},20 Z" class="fig-cabelo"/>` : `<path d="M${cx - 10.5},20 Q${cx - 11},8 ${cx},9 Q${cx + 11},8 ${cx + 10.5},20 Q${cx + 6},13 ${cx},13.5 Q${cx - 6},13 ${cx - 10.5},20 Z" class="fig-cabelo"/>`}
    ${short}${top}
    <g class="fig-linha">${linhas.join("")}</g>
    ${busto}${umbigo}
  </svg>`;
}

// Cartão com foto opcional por cima (pwa/img/fisicos/<sexo>-<id>.jpg)
export function figuraComFoto(sexo, fis) {
  return `<div class="fig-caixa">
    ${desenharFisico(sexo, fis.gordura, fis.ffmi)}
    <img class="fig-foto" src="./img/fisicos/${sexo}-${fis.id}.jpg" alt="" loading="lazy" onerror="this.remove()">
  </div>`;
}
