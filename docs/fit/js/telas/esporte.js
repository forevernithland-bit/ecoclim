// Registrar esporte/atividade fora da musculação (natação, corrida, jiu-jitsu…)
// com gasto calórico estimado e a pergunta de intensidade.
import { esc, num, toast, abrirSheet, somarDias } from "../ui.js";
import { ESPORTES, INTENSIDADES, gastoAtividade, esporte } from "../esportes.js";
import { E, gravar } from "../estado.js";
import { hojeISO } from "../db.js";

export function abrirRegistrarEsporte(aoSalvar) {
  const st = { id: null, minutos: 60, km: "", intensidade: null, data: hojeISO(), outroNome: "" };
  const sh = abrirSheet(`
    <h2>🏅 Registrar atividade</h2>
    <p class="sub">Esporte ou atividade além da musculação. O app estima as calorias gastas.</p>
    <label class="rotulo">Qual atividade?</label>
    <div class="esp-grade">${ESPORTES.map((e) => `<button type="button" class="esp-op" data-esp="${e.id}"><span>${e.emoji}</span><small>${esc(e.nome)}</small></button>`).join("")}</div>
    <input class="campo oculto" id="esp-outro" placeholder="Qual esporte? (ex.: handebol)">
    <label class="rotulo">Quanto tempo?</label>
    <div class="dias-sel">${[30, 45, 60, 90, 120].map((m) => `<button type="button" class="dia-b dia-b--larg ${m === 60 ? "dia-b--on" : ""}" data-min="${m}">${m} min</button>`).join("")}</div>
    <div class="campo-unid campo-unid--mini esp-min"><input class="campo" id="esp-minutos" type="number" inputmode="numeric" value="60"><span>min</span></div>
    <div id="esp-km-caixa" class="oculto">
      <label class="rotulo">Distância (opcional — deixa o cálculo mais preciso)</label>
      <div class="campo-unid campo-unid--mini"><input class="campo" id="esp-km" type="number" inputmode="decimal" step="0.1" placeholder="–"><span>km</span></div>
    </div>
    <label class="rotulo">Qual foi a intensidade?</label>
    <div class="opcoes">${INTENSIDADES.map((i) => `<button type="button" class="opcao opcao--linha" data-int="${i.id}"><span class="opcao-emoji">${i.emoji}</span><span><b>${i.nome}</b><small>${i.desc}</small></span></button>`).join("")}</div>
    <label class="rotulo">Quando?</label>
    <div class="dias-sel"><button type="button" class="dia-b dia-b--larg dia-b--on" data-dia="0">Hoje</button><button type="button" class="dia-b dia-b--larg" data-dia="-1">Ontem</button></div>
    <div id="esp-resultado"></div>
    <button class="btn btn--grande" id="esp-salvar" disabled>Salvar atividade</button>`, { cheia: true });

  const $ = (q) => sh.el.querySelector(q);
  const calcula = () => {
    const pronto = st.id && st.intensidade && st.minutos > 0;
    $("#esp-salvar").disabled = !pronto;
    if (!pronto) { $("#esp-resultado").innerHTML = `<p class="nota">${!st.id ? "Escolha a atividade" : !st.intensidade ? "Diga a intensidade" : "Informe o tempo"} pra ver as calorias.</p>`; return null; }
    const g = gastoAtividade({ id: st.id, minutos: st.minutos, intensidade: st.intensidade, km: +String(st.km).replace(",", ".") || null, peso: E.perfil.peso });
    $("#esp-resultado").innerHTML = `
      <div class="esp-gasto">
        <div><small>Gasto estimado</small><b>≈ ${num(g.total)} kcal</b></div>
        <div><small>Acima do repouso</small><b>+${num(g.liquida)} kcal</b></div>
      </div>
      <p class="nota">${g.velocidade ? `Velocidade média ${String(g.velocidade).replace(".", ",")} km/h. ` : ""}MET ${String(g.met).replace(".", ",")} (Compêndio de Atividades Físicas) × seu peso × tempo. Metade do gasto acima do repouso entra na sua meta de calorias de hoje — estimativas costumam exagerar um pouco.</p>`;
    return g;
  };

  sh.el.querySelectorAll("[data-esp]").forEach((b) => b.onclick = () => {
    st.id = b.dataset.esp;
    sh.el.querySelectorAll("[data-esp]").forEach((x) => x.classList.toggle("esp-op--on", x === b));
    $("#esp-km-caixa").classList.toggle("oculto", !esporte(st.id).distancia);
    $("#esp-outro").classList.toggle("oculto", st.id !== "outro");
    calcula();
  });
  sh.el.querySelectorAll("[data-min]").forEach((b) => b.onclick = () => {
    st.minutos = +b.dataset.min; $("#esp-minutos").value = st.minutos;
    sh.el.querySelectorAll("[data-min]").forEach((x) => x.classList.toggle("dia-b--on", x === b));
    calcula();
  });
  $("#esp-minutos").oninput = (e) => { st.minutos = +e.target.value || 0; sh.el.querySelectorAll("[data-min]").forEach((x) => x.classList.remove("dia-b--on")); calcula(); };
  $("#esp-km").oninput = (e) => { st.km = e.target.value; calcula(); };
  $("#esp-outro").oninput = (e) => { st.outroNome = e.target.value.trim(); };
  sh.el.querySelectorAll("[data-int]").forEach((b) => b.onclick = () => {
    st.intensidade = b.dataset.int;
    sh.el.querySelectorAll("[data-int]").forEach((x) => x.classList.toggle("opcao--on", x === b));
    calcula();
  });
  sh.el.querySelectorAll("[data-dia]").forEach((b) => b.onclick = () => {
    st.data = somarDias(hojeISO(), +b.dataset.dia);
    sh.el.querySelectorAll("[data-dia]").forEach((x) => x.classList.toggle("dia-b--on", x === b));
  });
  calcula();

  $("#esp-salvar").onclick = async () => {
    const g = calcula();
    if (!g) return;
    const e = esporte(st.id);
    const nome = st.id === "outro" && st.outroNome ? st.outroNome : e.nome;
    await gravar("treinos", {
      data: st.data, tipo: "esporte", livre: true, esporte: e.id, emoji: e.emoji, nome, minutos: st.minutos,
      km: +String(st.km).replace(",", ".") || null, intensidade: st.intensidade, kcal: g.total, kcalLiquida: g.liquida, duracaoMin: st.minutos,
      exercicios: [], series: 0, volume: 0,
    });
    sh.fechar();
    toast(`${e.emoji} ${nome}: ≈ ${num(g.total)} kcal registradas ✅`);
    aoSalvar && aoSalvar();
  };
}
