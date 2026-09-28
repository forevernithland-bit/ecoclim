// Cadastro inicial em etapas (uma pergunta por tela — rápido e sem assustar).
import { esc, num, toast, carregando } from "../ui.js";
import { OBJETIVOS, NIVEIS, FISICOS, MEDIDAS, imc, faixaImc, gorduraEstimada, metas, projecaoObjetivo, estimarTempoFisico, formatarMeses, ffmi, objetivoSugerido } from "../ciencia.js";
import { EQUIPAMENTOS, gerarPlano, nomeDivisao, DIAS_SEMANA, PADRAO_DIAS, MINUTOS, treinosDoCiclo } from "../treino.js";
import { desenharFisico, figuraComFoto } from "../fisico-arte.js";
import { urlDe } from "../midia.js";
import { fotografarCorpo } from "../camera.js";
import { analisarFisico } from "../ia.js";
import { E, salvarPerfil, salvarPlano, gravar } from "../estado.js";
import { hojeISO } from "../db.js";
import { editorGostos } from "../gostos.js";

const PULAVEL = {
  medidas: "Não tenho fita agora — preencher depois",
  fotos: "Tirar as fotos depois",
};

const ETAPAS = ["nome", "basico", "corpo", "medidas", "fotos", "fisico", "objetivo", "gostos", "treino", "resultado"];

export function rodarOnboarding(raiz, aoConcluir) {
  const r = { medidas: {}, diasTreino: 3, diasSemana: [1, 3, 5], minutosTreino: 60, equipamento: "academia", nivel: "iniciante", ...(E.perfil || {}) };
  const comGordura = () => ({ ...r, gordura: gorduraEstimada(r, r.medidas) });
  const fisicoEscolhido = () => FISICOS[r.sexo].find((f) => f.id === r.fisicoAlvo);
  let i = 0;
  let analiseIA = null;

  const pinta = () => {
    const etapa = ETAPAS[i];
    const pct = Math.round((i / (ETAPAS.length - 1)) * 100);
    raiz.innerHTML = `
      <div class="onb">
        <header class="onb-topo">
          ${i > 0 ? `<button class="icone-btn" id="voltar" aria-label="Voltar">←</button>` : `<span></span>`}
          <div class="onb-progresso"><div style="width:${pct}%"></div></div>
          <span class="onb-passo">${i + 1}/${ETAPAS.length}</span>
        </header>
        <main class="onb-corpo entra">${TELAS[etapa]()}</main>
        ${etapa !== "resultado" ? `<footer class="onb-rodape">
          <button class="btn btn--grande" id="seguir">${etapa === "treino" ? "Ver meu plano ✨" : "Continuar"}</button>
          ${PULAVEL[etapa] ? `<button class="link link--fraco" id="pular">${PULAVEL[etapa]}</button>` : ""}
        </footer>` : ""}
      </div>`;
    const v = raiz.querySelector("#voltar");
    if (v) v.onclick = () => { i--; pinta(); };
    const s = raiz.querySelector("#seguir");
    if (s) s.onclick = () => { if (VALIDA[etapa]()) { i++; pinta(); window.scrollTo(0, 0); } };
    const pular = raiz.querySelector("#pular");
    if (pular) pular.onclick = () => {
      if (etapa === "medidas") { VALIDA.medidas(); r.medidasDepois = true; }
      if (etapa === "fotos") r.fotosDepois = true;
      i++; pinta(); window.scrollTo(0, 0);
    };
    LIGA[etapa] && LIGA[etapa]();
    const primeiro = raiz.querySelector(".onb-corpo input:not([type=hidden])");
    if (primeiro && ["nome", "basico", "corpo"].includes(etapa)) setTimeout(() => primeiro.focus(), 250);
  };

  const campo = (id) => raiz.querySelector(`#${id}`);
  const erro = (msg) => { toast(msg, "erro"); return false; };

  const TELAS = {
    nome: () => `
      <div class="onb-hero">👋</div>
      <h1>Vamos montar seu plano</h1>
      <p class="sub">Algumas perguntas rápidas. Com elas, nossos especialistas em nutrição e treino calculam tudo com base na ciência.</p>
      <label class="rotulo">Como você quer ser chamado(a)?</label>
      <input id="nome" class="campo" autocomplete="given-name" placeholder="Seu nome" value="${esc(r.nome || "")}">`,
    basico: () => `
      <h1>Prazer, ${esc(r.nome)}!</h1>
      <p class="sub">Sexo biológico e idade mudam quanto seu corpo gasta de energia.</p>
      <label class="rotulo">Sexo</label>
      <div class="opcoes opcoes--2">
        ${[["M", "Masculino", "♂"], ["F", "Feminino", "♀"]].map(([v, t, e]) => `<button class="opcao ${r.sexo === v ? "opcao--on" : ""}" data-sexo="${v}"><span class="opcao-emoji">${e}</span>${t}</button>`).join("")}
      </div>
      <label class="rotulo">Idade</label>
      <div class="campo-unid"><input id="idade" class="campo" type="number" inputmode="numeric" min="14" max="90" value="${esc(r.idade || "")}" placeholder="30"><span>anos</span></div>`,
    corpo: () => `
      <h1>Altura e peso</h1>
      <p class="sub">Pese-se de manhã, em jejum, depois de ir ao banheiro — é o horário mais confiável.</p>
      <label class="rotulo">Altura</label>
      <div class="campo-unid"><input id="altura" class="campo" type="number" inputmode="numeric" min="120" max="230" value="${esc(r.altura || "")}" placeholder="170"><span>cm</span></div>
      <label class="rotulo">Peso atual</label>
      <div class="campo-unid"><input id="peso" class="campo" type="number" inputmode="decimal" step="0.1" min="30" max="300" value="${esc(r.peso || "")}" placeholder="75,0"><span>kg</span></div>`,
    medidas: () => `
      <h1>Medidas com fita métrica</h1>
      <p class="sub">São elas que mostram a evolução de verdade (a balança engana!). Fita encostada na pele, sem apertar. <b>Pescoço e cintura${r.sexo === "F" ? " e quadril" : ""}</b> calculam seu % de gordura.</p>
      <div class="lista-medidas">
        ${MEDIDAS.map((m) => {
          const obrig = m.obrig === true || m.obrig === r.sexo;
          return `
          <div class="medida">
            <div class="medida-txt"><b>${m.nome}${obrig ? ' <span class="obrig">*</span>' : ""}</b><small>${m.dica}</small></div>
            <div class="campo-unid campo-unid--mini"><input class="campo" data-medida="${m.id}" type="number" inputmode="decimal" step="0.1" value="${esc(r.medidas[m.id] || "")}" placeholder="–"><span>cm</span></div>
          </div>`;
        }).join("")}
      </div>
      <p class="nota">Sem fita agora? Toque em "preencher depois" lá embaixo — vamos te lembrar na tela inicial. Enquanto isso, o % de gordura é estimado pelo peso e altura.</p>`,
    fotos: () => `
      <h1>Fotos de "antes" 📸</h1>
      <p class="sub">Daqui a algumas semanas você vai agradecer por ter tirado. Ficam guardadas só pra você.</p>
      <div class="dicas-foto">
        <span>👕 Roupa justa ou de banho</span><span>💡 Mesmo lugar e mesma luz sempre</span>
        <span>📏 Celular na altura do umbigo, ~2 m</span><span>🧍 Corpo relaxado, braços soltos</span>
      </div>
      <div class="fotos-par">
        ${["Frente", "Lado"].map((l) => {
          const blob = r[`foto${l}`];
          return `<button class="foto-slot ${blob ? "foto-slot--ok" : ""}" data-foto="${l}">
            ${blob ? `<img src="${urlDe(blob)}" alt="Foto de ${l.toLowerCase()}">` : silhueta(l)}
            <span class="foto-slot-rot">${blob ? "Trocar" : `Foto de ${l.toLowerCase()}`}</span>
          </button>`;
        }).join("")}
      </div>
      <p class="nota">Com as fotos, a IA estima seu % de gordura visualmente e compara com o físico que você quer.</p>`,
    objetivo: () => `
      <h1>Qual é o seu objetivo?</h1>
      <div class="opcoes">
        ${Object.entries(OBJETIVOS).map(([k, o]) => `
          <button class="opcao opcao--linha ${r.objetivo === k ? "opcao--on" : ""}" data-obj="${k}">
            <span class="opcao-emoji">${o.emoji}</span><span><b>${o.rotulo}</b><small>${o.desc}</small>${k === r.objetivoSugerido ? `<em class="selo">Recomendado para o físico "${esc(fisicoEscolhido().nome)}"</em>` : ""}</span>
          </button>`).join("")}
      </div>
      <div id="meta-peso" class="${r.objetivo === "emagrecer" || r.objetivo === "massa" ? "" : "oculto"}">
        <label class="rotulo">Peso que você quer chegar (opcional)</label>
        <div class="campo-unid"><input id="pesoMeta" class="campo" type="number" inputmode="decimal" step="0.1" value="${esc(r.pesoMeta || "")}" placeholder="${r.objetivo === "massa" ? num(r.peso * 1.08) : num(r.peso * 0.9)}"><span>kg</span></div>
      </div>
      <div id="estimativa-obj"></div>`,
    fisico: () => `
      <h1>Selecione o estilo de físico que você gostaria de obter</h1>
      <p class="sub">Toque no corpo que é a sua meta. Vamos calcular quanto tempo leva pra chegar lá saindo de onde você está hoje.</p>
      <div class="fisicos">
        ${FISICOS[r.sexo].map((f) => `
          <button class="fisico ${r.fisicoAlvo === f.id ? "fisico--on" : ""}" data-fis="${f.id}">
            ${figuraComFoto(r.sexo, f)}
            <b>${f.nome}</b>
            <small>~${f.gordura}% de gordura</small>
            <span>${f.desc}</span>
          </button>`).join("")}
      </div>`,
    gostos: () => `
      <h1>Seus gostos na comida 🍽️</h1>
      <p class="sub">A dieta só funciona se for gostosa pra você. Marque o que você não gosta — a Nina nunca vai sugerir e troca por algo equivalente.</p>
      <div id="editor-gostos"></div>`,
    treino: () => `
      <h1>Sua rotina de treino</h1>
      <label class="rotulo">Em quais dias da semana você vai treinar?</label>
      <div class="semana-sel">${DIAS_SEMANA.map((d, k) => `<button class="sem-b ${r.diasSemana.includes(k) ? "sem-b--on" : ""}" data-sem="${k}">${d}</button>`).join("")}</div>
      <p class="nota" id="dica-dias">${dicaDias(r.diasSemana.length)}</p>
      <label class="rotulo">Quanto tempo por dia?</label>
      <div class="dias-sel">${MINUTOS.map((m) => `<button class="dia-b dia-b--larg ${+r.minutosTreino === m ? "dia-b--on" : ""}" data-min="${m}">${m} min</button>`).join("")}</div>
      <p class="nota" id="dica-min">${dicaMin(r.minutosTreino)}</p>
      <div id="previa-rotina"></div>
      <label class="rotulo">Onde você vai treinar?</label>
      <div class="opcoes">
        ${Object.entries(EQUIPAMENTOS).map(([k, o]) => `
          <button class="opcao opcao--linha ${r.equipamento === k ? "opcao--on" : ""}" data-eq="${k}"><span class="opcao-emoji">${o.emoji}</span><span><b>${o.rotulo}</b><small>${o.desc}</small></span></button>`).join("")}
      </div>
      <label class="rotulo">Sua experiência com musculação</label>
      <div class="opcoes">
        ${Object.entries(NIVEIS).map(([k, o]) => `
          <button class="opcao opcao--linha ${r.nivel === k ? "opcao--on" : ""}" data-niv="${k}"><span><b>${o.rotulo}</b><small>${o.desc}</small></span></button>`).join("")}
      </div>
      <label class="rotulo">Alguma lesão ou dor? (opcional)</label>
      <textarea id="restricoes" class="campo" rows="2" placeholder="Ex.: dor no joelho direito, hérnia de disco">${esc(r.restricoes || "")}</textarea>`,
    resultado: () => carregando("Nossos especialistas estão montando seu plano…"),
  };

  const VALIDA = {
    nome: () => { r.nome = campo("nome").value.trim(); return r.nome ? true : erro("Digite seu nome."); },
    basico: () => {
      r.idade = +campo("idade").value;
      if (!r.sexo) return erro("Escolha o sexo.");
      if (!(r.idade >= 14 && r.idade <= 90)) return erro("Idade entre 14 e 90 anos.");
      return true;
    },
    corpo: () => {
      r.altura = +campo("altura").value;
      r.peso = +String(campo("peso").value).replace(",", ".");
      if (!(r.altura >= 120 && r.altura <= 230)) return erro("Altura em centímetros (ex.: 172).");
      if (!(r.peso >= 30 && r.peso <= 300)) return erro("Peso em kg (ex.: 78,5).");
      return true;
    },
    medidas: () => {
      raiz.querySelectorAll("[data-medida]").forEach((inp) => {
        const v = +String(inp.value).replace(",", ".");
        if (v > 0) r.medidas[inp.dataset.medida] = v; else delete r.medidas[inp.dataset.medida];
      });
      return true;
    },
    fotos: () => true,
    objetivo: () => {
      if (!r.objetivo) return erro("Escolha um objetivo.");
      const pm = campo("pesoMeta");
      r.pesoMeta = pm && +pm.value > 0 ? +String(pm.value).replace(",", ".") : null;
      return true;
    },
    fisico: () => {
      if (!r.fisicoAlvo) return erro("Toque no físico que você quer.");
      r.objetivoSugerido = objetivoSugerido(comGordura(), fisicoEscolhido());
      if (!r.objetivoManual) r.objetivo = r.objetivoSugerido;
      return true;
    },
    gostos: () => { r.gostosPerguntados = true; return true; },
    treino: () => {
      if (!r.diasSemana.length) return erro("Escolha pelo menos 1 dia de treino.");
      r.diasTreino = r.diasSemana.length;
      r.restricoes = campo("restricoes").value.trim();
      return true;
    },
    resultado: () => true,
  };

  const LIGA = {
    basico: () => raiz.querySelectorAll("[data-sexo]").forEach((b) => b.onclick = () => {
      r.sexo = b.dataset.sexo;
      raiz.querySelectorAll("[data-sexo]").forEach((x) => x.classList.toggle("opcao--on", x === b));
    }),
    fotos: () => raiz.querySelectorAll("[data-foto]").forEach((b) => b.onclick = async () => {
      const blob = await fotografarCorpo({ titulo: `Foto de ${b.dataset.foto.toLowerCase()}` });
      if (blob) { r[`foto${b.dataset.foto}`] = blob; pinta(); }
    }),
    objetivo: () => {
      const mostra = () => {
        const p = { ...r, gordura: gorduraEstimada(r, r.medidas) };
        const pm = campo("pesoMeta");
        const meta = pm && +pm.value > 0 ? +String(pm.value).replace(",", ".") : null;
        const pr = r.objetivo ? projecaoObjetivo(p, meta) : null;
        campo("estimativa-obj").innerHTML = pr ? `
          <div class="card card--ciencia entra">
            <div class="card-tag">🔬 O que a ciência diz</div>
            <p>${esc(pr.texto)}</p>
            ${pr.semanas ? `<p class="destaque">Tempo médio até ${num(meta, 1)} kg: <b>${formatarMeses(Math.round(pr.semanas / 4.35))}</b> <small>(${pr.semanas} semanas)</small></p>` : ""}
          </div>
          ${meta && imc(meta, r.altura) < 18.5 ? `<p class="aviso">⚠️ ${num(meta, 1)} kg deixaria seu IMC abaixo de 18,5 (abaixo do peso saudável). Recomendamos uma meta a partir de ${num(Math.ceil(18.5 * (r.altura / 100) ** 2), 0)} kg, ou acompanhamento profissional.</p>` : ""}` : "";
      };
      raiz.querySelectorAll("[data-obj]").forEach((b) => b.onclick = () => {
        r.objetivo = b.dataset.obj;
        r.objetivoManual = r.objetivo !== r.objetivoSugerido;
        raiz.querySelectorAll("[data-obj]").forEach((x) => x.classList.toggle("opcao--on", x === b));
        campo("meta-peso").classList.toggle("oculto", !(r.objetivo === "emagrecer" || r.objetivo === "massa"));
        mostra();
      });
      const pm = campo("pesoMeta");
      if (pm) pm.oninput = mostra;
      mostra();
    },
    fisico: () => raiz.querySelectorAll("[data-fis]").forEach((b) => b.onclick = () => {
      r.fisicoAlvo = b.dataset.fis;
      raiz.querySelectorAll("[data-fis]").forEach((x) => x.classList.toggle("fisico--on", x === b));
    }),
    treino: () => {
      const previa = () => {
        const p = { ...comGordura(), diasTreino: r.diasSemana.length || 1 };
        const fis = fisicoEscolhido();
        const est = estimarTempoFisico(p, fis);
        campo("previa-rotina").innerHTML = r.diasSemana.length ? `
          <div class="card card--ciencia">
            <div class="card-tag">⏱️ Com essa rotina</div>
            <p>${r.diasSemana.length}x por semana, ${r.minutosTreino} min: você chega no físico <b>"${esc(fis.nome)}"</b> em <b>~${formatarMeses(est.meses)}</b>.</p>
            <p class="nota">Mais dias ou mais tempo aceleram o ganho de músculo (até um limite).</p>
          </div>` : "";
      };
      raiz.querySelectorAll("[data-sem]").forEach((b) => b.onclick = () => {
        const d = +b.dataset.sem;
        r.diasSemana = r.diasSemana.includes(d) ? r.diasSemana.filter((x) => x !== d) : [...r.diasSemana, d].sort();
        if (r.diasSemana.length > 6) { r.diasSemana = r.diasSemana.filter((x) => x !== d); return toast("No máximo 6 dias — o corpo precisa de 1 dia de descanso.", "erro"); }
        b.classList.toggle("sem-b--on", r.diasSemana.includes(d));
        campo("dica-dias").textContent = dicaDias(r.diasSemana.length);
        previa();
      });
      raiz.querySelectorAll("[data-min]").forEach((b) => b.onclick = () => {
        r.minutosTreino = +b.dataset.min;
        raiz.querySelectorAll("[data-min]").forEach((x) => x.classList.toggle("dia-b--on", x === b));
        campo("dica-min").textContent = dicaMin(r.minutosTreino);
        previa();
      });
      previa();
      raiz.querySelectorAll("[data-eq]").forEach((b) => b.onclick = () => {
        r.equipamento = b.dataset.eq;
        raiz.querySelectorAll("[data-eq]").forEach((x) => x.classList.toggle("opcao--on", x === b));
      });
      raiz.querySelectorAll("[data-niv]").forEach((b) => b.onclick = () => {
        r.nivel = b.dataset.niv;
        raiz.querySelectorAll("[data-niv]").forEach((x) => x.classList.toggle("opcao--on", x === b));
      });
    },
    gostos: () => editorGostos(campo("editor-gostos"), r),
    resultado: () => montarResultado(),
  };

  async function montarResultado() {
    const p = { ...r, gordura: gorduraEstimada(r, r.medidas) };
    const fisico = FISICOS[p.sexo].find((f) => f.id === p.fisicoAlvo);
    const m = metas(p);
    const est = estimarTempoFisico(p, fisico);
    const plano = gerarPlano(p);
    const corpo = raiz.querySelector(".onb-corpo");
    const temFotos = r.fotoFrente || r.fotoLado;

    const ffmiHoje = ffmi(p.peso, p.altura, p.gordura);
    const dataMeta = new Date();
    dataMeta.setMonth(dataMeta.getMonth() + est.meses);
    const mesAno = dataMeta.toLocaleDateString("pt-BR", { month: "long", year: "numeric" }).replace(/^./, (c) => c.toUpperCase());
    // Marcos da jornada: 1º mês, alguns intermediários e o final
    const idxs = [...new Set([1, Math.round(est.meses / 3), Math.round((2 * est.meses) / 3), est.meses].filter((x) => x >= 1 && x <= est.trilha.length))];
    const marcos = idxs.map((k) => est.trilha[k - 1]);
    const treinos = treinosDoCiclo(plano);
    const diasTxt = plano.diasSemana.map((d) => DIAS_SEMANA[d]).join(", ");

    corpo.innerHTML = `
      <div class="resultado-hero entra">
        <p class="resultado-pre">${esc(p.nome)}, se você seguir o programa à risca,</p>
        ${est.inalcancavel
          ? `<h1>o físico "${esc(fisico.nome)}" está acima do limite natural para a sua estrutura.</h1><p class="nota">Sugerimos escolher um físico intermediário — dá pra trocar depois no Perfil.</p>`
          : `<h1>você vai atingir o físico <span class="realce">"${esc(fisico.nome)}"</span> em aproximadamente <span class="realce">${formatarMeses(est.meses)}</span></h1>
             <p class="resultado-data">📅 Previsão: <b>${mesAno}</b> · faixa realista de ${formatarMeses(est.minimo)} a ${formatarMeses(est.maximo)}</p>`}
        <div class="antes-depois-fig">
          <div><div class="fig-caixa">${desenharFisico(p.sexo, p.gordura, ffmiHoje)}</div><b>Você hoje</b><small>${num(p.peso, 1)} kg · ${num(p.gordura, 0)}% gordura</small></div>
          <span class="seta-fig">→</span>
          <div><div class="fig-caixa">${desenharFisico(p.sexo, fisico.gordura, fisico.ffmi, { destaque: true })}</div><b>Você em ${formatarMeses(est.meses)}</b><small>~${num(est.pesoFinal, 1)} kg · ${fisico.gordura}% gordura</small></div>
        </div>
      </div>

      ${!est.inalcancavel && marcos.length > 1 ? `
      <div class="card">
        <div class="card-tag">🗺️ Sua jornada, mês a mês</div>
        <div class="marcos">
          ${marcos.map((mk) => `<div class="marco"><i></i><div><b>Mês ${mk.mes}</b><small>~${num(mk.peso, 1)} kg · ${num(mk.gordura, 0)}% de gordura</small></div></div>`).join("")}
        </div>
        <p class="nota">${est.mesesDefinicao ? `~${formatarMeses(est.mesesDefinicao)} de definição (perder gordura)` : ""}${est.mesesDefinicao && est.mesesConstrucao ? " + " : ""}${est.mesesConstrucao ? `~${formatarMeses(est.mesesConstrucao)} de construção muscular` : ""}. A cada ${E.prefs.intervaloCheckin || 30} dias você faz um check-in e compara com hoje.</p>
      </div>` : ""}

      <div class="card card--destaque">
        <div class="card-tag">🔬 Como chegamos nesse número</div>
        <p class="nota">Cálculo com seu % de gordura (${r.medidas.cintura && r.medidas.pescoco ? "pela fita métrica" : "estimado"}), massa magra (${num(p.peso * (1 - p.gordura / 100), 1)} kg), sexo, idade, experiência e a rotina de ${plano.dias}x/semana de ${plano.minutos} min — usando os ritmos que a ciência considera realistas para perder gordura sem perder músculo e para ganhar músculo naturalmente.</p>
        <div id="analise-ia">${temFotos ? carregando("A IA está analisando suas fotos…") : `<p class="nota">💡 Adicione fotos depois (Evolução) para a IA refinar essa estimativa.</p>`}</div>
      </div>

      <div class="grade-3">
        <div class="mini"><small>IMC</small><b>${num(imc(p.peso, p.altura), 1)}</b><span>${faixaImc(imc(p.peso, p.altura))}</span></div>
        <div class="mini"><small>Gordura</small><b>${num(p.gordura, 1)}%</b><span>${r.medidas.cintura && r.medidas.pescoco ? "pela fita" : "estimada"}</span></div>
        <div class="mini"><small>Massa magra</small><b>${num(p.peso * (1 - p.gordura / 100), 1)} kg</b><span>FFMI ${num(ffmiHoje, 1)}</span></div>
      </div>

      <div class="card">
        <div class="card-tag">🥗 O programa: nutrição diária</div>
        <div class="kcal-grande">${num(m.kcal)} <small>kcal/dia</small></div>
        <div class="macros-linha">
          <span class="pill pill--p">Proteína ${m.prot} g</span><span class="pill pill--c">Carbo ${m.carb} g</span><span class="pill pill--g">Gordura ${m.gord} g</span>
        </div>
        <p class="nota">Você gasta ~${num(m.gasto)} kcal/dia. ${esc(m.explic)} Água: ${num(m.agua, 1)} L/dia.</p>
      </div>

      <div class="card">
        <div class="card-tag">🏋️ O programa: treino</div>
        <p><b>${diasTxt} · ${plano.minutos} min por dia</b><br><span class="nota">${esc(nomeDivisao(plano))}</span></p>
        ${treinos.map((t) => `<div class="linha-hist"><span>${DIAS_SEMANA[t.diaSemana] || ""}</span><b>Treino ${t.letra} — ${esc(t.nome)}</b><small>~${t.minutos} min</small></div>`).join("")}
        <p class="nota">Os exercícios mudam a cada ${plano.semanasCiclo} semanas para o corpo continuar evoluindo. Todos têm vídeo de execução.</p>
      </div>

      <button class="btn btn--grande" id="comecar">Aceito o desafio — começar 🚀</button>`;

    if (temFotos && !E.modoLocal) {
      analisarFisico({ perfil: p, frente: r.fotoFrente, lado: r.fotoLado, fisicoAlvo: fisico, estimativaCiencia: { meses: est.meses, minimo: est.minimo, maximo: est.maximo, gordura_fita: p.gordura } })
        .then((a) => { analiseIA = a; pintaAnaliseIA(corpo.querySelector("#analise-ia"), a); })
        .catch((e) => { corpo.querySelector("#analise-ia").innerHTML = `<p class="nota">A análise por IA não rodou agora (${esc(e.message)}). Dá pra refazer em Evolução.</p>`; });
    } else if (temFotos) {
      corpo.querySelector("#analise-ia").innerHTML = `<p class="nota">Análise por IA disponível ao entrar com uma conta.</p>`;
    }

    corpo.querySelector("#comecar").onclick = async (ev) => {
      ev.target.disabled = true;
      const perfil = { ...p };
      delete perfil.fotoFrente; delete perfil.fotoLado;
      perfil.criadoEm = perfil.criadoEm || hojeISO();
      if (analiseIA) perfil.analiseInicial = analiseIA;
      await salvarPerfil(perfil);
      await salvarPlano(plano);
      await gravar("checkins", {
        data: hojeISO(), tipo: "inicial", peso: p.peso, medidas: { ...p.medidas }, gordura: p.gordura,
        fotoFrente: r.fotoFrente || null, fotoLado: r.fotoLado || null, analiseIA,
        fisicoAlvo: fisico.id, estimativa: { meses: est.meses, minimo: est.minimo, maximo: est.maximo },
      });
      await gravar("metricas", { id: `m-${hojeISO()}`, data: hojeISO(), peso: p.peso, cintura: p.medidas.cintura || null });
      aoConcluir();
    };
  }

  pinta();
}

export function pintaAnaliseIA(el, a) {
  if (!el || !a) return;
  el.innerHTML = `
    <div class="ia-bloco entra">
      <div class="card-tag">🤖 Análise das suas fotos</div>
      <p>${esc(a.resumo)}</p>
      <div class="grade-2">
        <div class="mini"><small>Gordura (visual)</small><b>${num(a.gordura_visual_min)}–${num(a.gordura_visual_max)}%</b></div>
        <div class="mini"><small>Tempo (IA)</small><b>${num(a.meses_min)}–${num(a.meses_max)} meses</b></div>
      </div>
      ${a.pontos_fortes && a.pontos_fortes.length ? `<p class="nota"><b>Pontos fortes:</b> ${a.pontos_fortes.map(esc).join(" · ")}</p>` : ""}
      ${a.prioridades && a.prioridades.length ? `<p class="nota"><b>Prioridades:</b> ${a.prioridades.map(esc).join(" · ")}</p>` : ""}
    </div>`;
}

function dicaMin(m) {
  return {
    30: "30 min: treino enxuto, só o essencial (4 exercícios). Funciona!",
    45: "45 min: ótimo custo-benefício (5 exercícios).",
    60: "60 min: o tempo ideal para a maioria (6 exercícios).",
    75: "75 min: mais volume, bom para quem quer ganhar massa (7 exercícios).",
    90: "90 min: volume alto — só vale com sono e comida em dia (8 exercícios).",
  }[m] || "";
}

function dicaDias(d) {
  return {
    0: "Toque nos dias em que você consegue treinar.",
    1: "1 dia já ajuda a manter, mas o ideal para mudar o corpo é 3 ou mais.",
    2: "2 treinos de corpo inteiro por semana já dão ótimos resultados para iniciantes.",
    3: "3 dias é o ponto ideal para a maioria: resultado ótimo com recuperação tranquila.",
    4: "4 dias permitem dividir em superiores e inferiores — mais volume por músculo.",
    5: "5 dias: ótimo volume. Garanta sono e comida em dia para recuperar.",
    6: "6 dias: para quem tem experiência. O descanso vira parte do treino!",
  }[d] || "";
}

function silhueta(lado) {
  return lado === "Frente"
    ? `<svg viewBox="0 0 60 120" class="silhueta"><circle cx="30" cy="14" r="9"/><path d="M16 28h28l6 36-7 2-4-26v76h-8V80h-2v36h-8V40l-4 26-7-2z"/></svg>`
    : `<svg viewBox="0 0 60 120" class="silhueta"><circle cx="30" cy="14" r="9"/><path d="M24 28h13l4 18-2 22-4-1 1-18-1-6v73h-8V80h-1v36h-7V40z"/></svg>`;
}
