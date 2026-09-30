// Calibra o gasto calórico com os dados reais da pessoa (como os apps de
// nutrição mais modernos): média de passos, e — com ≥ 2 semanas de registro —
// o gasto REAL = média comida − (variação do peso × 7.700 kcal/kg) ÷ dias.
// Roda 1x por dia ao abrir o app e salva em perfil.calibracao.
import { todos, kvGet, kvSet, hojeISO } from "./db.js";
import { E, salvarPerfil } from "./estado.js";

const somarDias = (iso, n) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() + n); return hojeISO(d); };

export async function calibrar({ forcar = false } = {}) {
  if (!E.perfil) return null;
  const ultima = await kvGet("calibradoEm", 0);
  if (!forcar && Date.now() - ultima < 20 * 3600 * 1000) return E.perfil.calibracao || null;
  await kvSet("calibradoEm", Date.now());

  const hoje = hojeISO();
  const [refs, mets] = await Promise.all([todos("refeicoes"), todos("metricas")]);

  // Passos: média dos últimos 14 dias (mínimo 3 registros)
  const ini14 = somarDias(hoje, -14);
  const passos = mets.filter((m) => m.data >= ini14 && m.data < hoje && +m.passos > 0).map((m) => +m.passos);
  const passosMedia = passos.length >= 3 ? Math.round(passos.reduce((a, b) => a + b, 0) / passos.length) : null;

  // Gasto real: janela de até 28 dias, dias COMPLETOS registrados (≥ 800 kcal, pra não contar dia esquecido)
  const ini = somarDias(hoje, -28);
  const porDia = {};
  for (const r of refs) if (r.data >= ini && r.data < hoje) porDia[r.data] = (porDia[r.data] || 0) + (r.kcal || 0);
  const diasComida = Object.values(porDia).filter((k) => k >= 800);
  const pesos = mets.filter((m) => m.data >= ini && m.data <= hoje && +m.peso > 0).map((m) => ({ t: new Date(`${m.data}T12:00:00`).getTime() / 864e5, p: +m.peso }));
  let gastoReal = null, dias = 0;
  if (diasComida.length >= 10 && pesos.length >= 4) {
    const span = pesos[pesos.length - 1].t - pesos[0].t;
    if (span >= 10) {
      // tendência do peso por regressão linear (menos sensível a água/intestino que "último − primeiro")
      const n = pesos.length, mx = pesos.reduce((a, x) => a + x.t, 0) / n, my = pesos.reduce((a, x) => a + x.p, 0) / n;
      const incl = pesos.reduce((a, x) => a + (x.t - mx) * (x.p - my), 0) / pesos.reduce((a, x) => a + (x.t - mx) ** 2, 0);
      const mediaKcal = diasComida.reduce((a, b) => a + b, 0) / diasComida.length;
      gastoReal = Math.round(mediaKcal - incl * 7700);
      dias = diasComida.length;
    }
  }

  // Ritmo de perda/ganho (kg/semana) pelas pesagens dos últimos 21 dias — usado nos alertas
  const ini21 = somarDias(hoje, -21);
  const p21 = mets.filter((m) => m.data >= ini21 && m.data <= hoje && +m.peso > 0).map((m) => ({ t: new Date(`${m.data}T12:00:00`).getTime() / 864e5, p: +m.peso }));
  let ritmoSemana = null;
  if (p21.length >= 4 && p21[p21.length - 1].t - p21[0].t >= 10) {
    const n = p21.length, mx = p21.reduce((a, x) => a + x.t, 0) / n, my = p21.reduce((a, x) => a + x.p, 0) / n;
    ritmoSemana = Math.round((p21.reduce((a, x) => a + (x.t - mx) * (x.p - my), 0) / p21.reduce((a, x) => a + (x.t - mx) ** 2, 0)) * 7 * 100) / 100;
  }

  const antes = E.perfil.calibracao || {};
  const nova = { passosMedia, gastoReal, dias, ritmoSemana, em: Date.now() };
  if (antes.passosMedia !== passosMedia || Math.abs((antes.gastoReal || 0) - (gastoReal || 0)) > 30 || antes.ritmoSemana !== ritmoSemana) {
    await salvarPerfil({ ...E.perfil, calibracao: nova });
  }
  return nova;
}
