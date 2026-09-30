// Esportes e atividades fora da musculação, com gasto calórico estimado pelo
// Compêndio de Atividades Físicas (Ainsworth/Herrmann, versão 2024):
//   kcal ≈ MET × peso (kg) × horas
// Mostramos também o gasto ACIMA do repouso (MET − 1), que é o que realmente
// soma ao dia — o gasto em repouso já está na sua meta.
import { hojeISO } from "./db.js";

// [id, nome, emoji, MET leve, moderado, intenso, usaDistancia]
const LISTA = [
  ["corrida", "Corrida", "🏃", 7.0, 9.8, 11.8, true],
  ["caminhada", "Caminhada", "🚶", 3.0, 3.8, 5.0, true],
  ["bike", "Bicicleta (rua)", "🚴", 5.8, 8.0, 10.0, true],
  ["spinning", "Bike ergométrica / spinning", "🚲", 5.0, 7.0, 8.5, false],
  ["natacao", "Natação", "🏊", 5.8, 8.3, 9.8, true],
  ["jiujitsu", "Jiu-jitsu / judô", "🥋", 6.0, 7.8, 10.3, false],
  ["luta", "Muay thai / boxe / MMA", "🥊", 7.8, 9.5, 12.0, false],
  ["futebol", "Futebol", "⚽", 7.0, 8.0, 10.0, false],
  ["volei", "Vôlei", "🏐", 3.0, 4.0, 6.0, false],
  ["basquete", "Basquete", "🏀", 4.5, 6.5, 8.0, false],
  ["tenis", "Tênis / beach tennis / padel", "🎾", 5.0, 7.0, 8.0, false],
  ["crossfit", "Crossfit / HIIT / funcional", "🔥", 5.5, 8.0, 10.0, false],
  ["danca", "Dança / zumba", "💃", 5.0, 6.5, 8.0, false],
  ["yoga", "Yoga / pilates / alongamento", "🧘", 2.5, 3.0, 4.0, false],
  ["remo", "Remo", "🚣", 4.8, 7.0, 8.5, true],
  ["eliptico", "Elíptico / transport", "〰️", 5.0, 5.8, 7.0, false],
  ["corda", "Pular corda", "🪢", 8.8, 11.8, 12.3, false],
  ["trilha", "Trilha / caminhada em montanha", "🥾", 5.3, 6.0, 7.8, true],
  ["escalada", "Escalada", "🧗", 5.8, 7.5, 8.0, false],
  ["surf", "Surf / stand up", "🏄", 3.0, 5.0, 6.3, false],
  ["skate", "Skate / patins", "🛹", 5.0, 7.0, 9.0, false],
  ["outro", "Outro esporte", "🏅", 4.0, 6.0, 8.0, false],
];
export const ESPORTES = LISTA.map(([id, nome, emoji, leve, moderado, intenso, distancia]) => ({ id, nome, emoji, met: { leve, moderado, intenso }, distancia }));
export const esporte = (id) => ESPORTES.find((e) => e.id === id) || ESPORTES[ESPORTES.length - 1];

export const INTENSIDADES = [
  { id: "leve", nome: "Leve", emoji: "🙂", desc: "Dava pra conversar tranquilo" },
  { id: "moderado", nome: "Moderada", emoji: "😅", desc: "Conversava com esforço, suor forte" },
  { id: "intenso", nome: "Intensa", emoji: "🥵", desc: "Quase não dava pra falar" },
];

// Corrida/bike/natação/caminhada com distância: MET pela velocidade (mais preciso)
function metPelaVelocidade(id, kmh) {
  if (!kmh) return null;
  const faixas = {
    corrida: [[6.4, 6.0], [8.0, 8.3], [9.7, 9.8], [11.3, 11.0], [12.9, 11.8], [14.5, 12.8], [16.1, 14.5], [99, 16.0]],
    caminhada: [[3.2, 2.8], [4.0, 3.0], [4.8, 3.5], [5.6, 4.3], [6.4, 5.0], [99, 6.3]],
    bike: [[16, 4.0], [19, 6.8], [22, 8.0], [25, 10.0], [30, 12.0], [99, 15.8]],
    natacao: [[1.5, 5.8], [2.5, 8.3], [99, 9.8]],
    trilha: [[3, 5.3], [4.5, 6.0], [99, 7.8]],
    remo: [[6, 4.8], [9, 7.0], [99, 8.5]],
  }[id];
  if (!faixas) return null;
  for (const [ate, met] of faixas) if (kmh <= ate) return met;
  return null;
}

export function gastoAtividade({ id, minutos, intensidade = "moderado", km = null, peso }) {
  const e = esporte(id);
  const horas = (Number(minutos) || 0) / 60;
  let met = e.met[intensidade] || e.met.moderado;
  const pelaVel = km && horas ? metPelaVelocidade(e.id, km / horas) : null;
  if (pelaVel) met = pelaVel;
  const total = Math.round(met * peso * horas);
  const liquida = Math.round(Math.max(0, met - 1) * peso * horas);
  return { met, total, liquida, velocidade: km && horas ? Math.round((km / horas) * 10) / 10 : null };
}

// Quanto a atividade do dia soma na meta de calorias. Usamos METADE do gasto
// acima do repouso: relógios e tabelas costumam superestimar, e comer tudo de
// volta atrapalha o déficit. A calibração pelo peso corrige com o tempo.
export function bonusDoDia(treinos, data = hojeISO()) {
  const doDia = treinos.filter((t) => t.data === data);
  const liquida = doDia.reduce((a, t) => a + (t.tipo === "esporte" ? t.kcalLiquida || 0 : t.kcalCardio || 0), 0);
  return { liquida, bonus: Math.round((liquida * 0.5) / 10) * 10 };
}
