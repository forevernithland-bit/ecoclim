// Gerador de plano de treino. Cada "padrão de movimento" tem variações por
// equipamento; a cada ciclo (4–8 semanas, ajustável) o app troca a variação —
// mantém o estímulo novo sem perder o que a pessoa aprendeu (Schoenfeld 2017;
// Kassiano et al. 2022: variar exercício de tempos em tempos ajuda hipertrofia
// regional, mas trocar toda semana atrapalha a progressão de carga).

export const EQUIPAMENTOS = {
  academia: { rotulo: "Academia", emoji: "🏋️", desc: "Máquinas, barras e halteres" },
  casa: { rotulo: "Em casa com halteres", emoji: "🏠", desc: "Um par de halteres ajustáveis e um banco/cadeira" },
  corpo: { rotulo: "Só peso do corpo", emoji: "🤸", desc: "Sem equipamento nenhum" },
};

// dica = o que mais importa na execução, em 1 frase simples.
const PADROES = {
  agachamento: {
    grupo: "Pernas (quadríceps e glúteos)", composto: true,
    dica: "Pés na largura dos ombros, desça como se fosse sentar numa cadeira, joelhos na direção dos pés, coluna neutra.",
    v: {
      academia: ["Agachamento livre com barra", "Leg press 45°", "Agachamento no Smith", "Hack squat"],
      casa: ["Agachamento goblet com halter", "Agachamento búlgaro com halteres", "Agachamento sumô com halter"],
      corpo: ["Agachamento livre", "Agachamento búlgaro", "Agachamento com pausa embaixo"],
    },
  },
  dobradica: {
    grupo: "Posterior de coxa e glúteos", composto: true,
    dica: "Empurre o quadril para trás com os joelhos levemente dobrados; costas retas o tempo todo, sinta alongar atrás da coxa.",
    v: {
      academia: ["Levantamento terra romeno com barra", "Stiff com halteres", "Good morning no Smith"],
      casa: ["Stiff com halteres", "Stiff unilateral com halter"],
      corpo: ["Stiff unilateral (peso do corpo)", "Good morning com mochila"],
    },
  },
  flexora: {
    grupo: "Posterior de coxa", composto: false,
    dica: "Movimento controlado, sem tirar o quadril do banco; segure 1 segundo com a perna dobrada.",
    v: {
      academia: ["Mesa flexora", "Cadeira flexora"],
      casa: ["Flexão de joelho com halter entre os pés", "Ponte com calcanhar deslizando"],
      corpo: ["Ponte com calcanhar deslizando (toalha)", "Nordic curl assistido"],
    },
  },
  extensora: {
    grupo: "Quadríceps", composto: false,
    dica: "Tronco firme, joelho da frente acompanha o pé; desça até quase encostar o joelho de trás no chão.",
    v: {
      academia: ["Cadeira extensora", "Afundo no Smith"],
      casa: ["Afundo com halteres", "Step-up no banco com halteres"],
      corpo: ["Afundo alternado", "Step-up na cadeira"],
    },
  },
  gluteo: {
    grupo: "Glúteos", composto: true,
    dica: "Queixo no peito, empurre pelos calcanhares e aperte o bumbum no alto sem arquear a lombar.",
    v: {
      academia: ["Elevação pélvica com barra", "Glúteo na polia (coice)", "Abdução de quadril na máquina"],
      casa: ["Elevação pélvica com halter", "Elevação pélvica unilateral"],
      corpo: ["Elevação pélvica", "Ponte de glúteo unilateral", "Coice de glúteo em quatro apoios"],
    },
  },
  supino: {
    grupo: "Peito, ombro e tríceps", composto: true,
    dica: "Escápulas presas para trás, pés firmes no chão; desça controlado até o peito e empurre sem tirar o bumbum do banco.",
    v: {
      academia: ["Supino reto com barra", "Supino reto com halteres", "Chest press na máquina"],
      casa: ["Supino com halteres no chão", "Supino com halteres no banco"],
      corpo: ["Flexão de braço", "Flexão com pausa embaixo", "Flexão arqueiro"],
    },
  },
  supinoInc: {
    grupo: "Peito superior e ombros", composto: true,
    dica: "Banco a 30°; cotovelos a ~45° do corpo, descendo até a parte de cima do peito.",
    v: {
      academia: ["Supino inclinado com halteres", "Supino inclinado com barra", "Crucifixo na polia"],
      casa: ["Supino inclinado com halteres", "Crucifixo com halteres"],
      corpo: ["Flexão com pés elevados", "Flexão declinada lenta"],
    },
  },
  remada: {
    grupo: "Costas (meio) e bíceps", composto: true,
    dica: "Puxe o cotovelo em direção ao quadril e aperte as escápulas; não balance o tronco.",
    v: {
      academia: ["Remada baixa na polia", "Remada curvada com barra", "Remada unilateral com halter", "Remada cavalinho"],
      casa: ["Remada unilateral com halter", "Remada curvada com halteres"],
      corpo: ["Remada invertida debaixo da mesa", "Remada com toalha na porta"],
    },
  },
  puxada: {
    grupo: "Costas (largura) e bíceps", composto: true,
    dica: "Peito aberto, puxe a barra até o alto do peito levando os cotovelos para baixo e para trás.",
    v: {
      academia: ["Puxada frontal na polia", "Barra fixa (ou graviton)", "Puxada com pegada neutra"],
      casa: ["Pullover com halter", "Barra fixa de porta"],
      corpo: ["Barra fixa (ou só a descida lenta)", "Superman com puxada"],
    },
  },
  desenvolvimento: {
    grupo: "Ombros e tríceps", composto: true,
    dica: "Abdômen firme, empurre acima da cabeça sem arquear a lombar; desça até a altura das orelhas.",
    v: {
      academia: ["Desenvolvimento com halteres", "Desenvolvimento na máquina", "Desenvolvimento militar com barra"],
      casa: ["Desenvolvimento com halteres sentado", "Arnold press"],
      corpo: ["Flexão pike", "Flexão pike com pés elevados"],
    },
  },
  lateral: {
    grupo: "Ombros (lateral)", composto: false,
    dica: "Suba os braços para os lados até a altura dos ombros, cotovelos levemente dobrados, sem dar impulso.",
    v: {
      academia: ["Elevação lateral com halteres", "Elevação lateral na polia"],
      casa: ["Elevação lateral com halteres", "Elevação lateral inclinado"],
      corpo: ["Elevação lateral com garrafas de água", "Elevação lateral com mochila"],
    },
  },
  posteriorOmbro: {
    grupo: "Ombro posterior e postura", composto: false,
    dica: "Abra os braços para trás apertando entre as escápulas; carga leve e controle.",
    v: {
      academia: ["Face pull na polia", "Crucifixo inverso na máquina"],
      casa: ["Crucifixo inverso com halteres"],
      corpo: ["Y-T-W deitado de bruços"],
    },
  },
  biceps: {
    grupo: "Bíceps", composto: false,
    dica: "Cotovelos colados ao corpo, suba sem balançar e desça devagar (3 segundos).",
    v: {
      academia: ["Rosca direta com barra", "Rosca alternada com halteres", "Rosca martelo", "Rosca na polia"],
      casa: ["Rosca alternada com halteres", "Rosca martelo", "Rosca concentrada"],
      corpo: ["Rosca com mochila", "Barra fixa supinada (chin-up)"],
    },
  },
  triceps: {
    grupo: "Tríceps", composto: false,
    dica: "Cotovelo parado, só o antebraço se move; estenda totalmente o braço no final.",
    v: {
      academia: ["Tríceps na polia com corda", "Tríceps francês", "Tríceps testa"],
      casa: ["Tríceps francês com halter", "Tríceps coice"],
      corpo: ["Mergulho no banco/cadeira", "Flexão diamante"],
    },
  },
  panturrilha: {
    grupo: "Panturrilhas", composto: false,
    dica: "Suba o máximo na ponta dos pés, segure 1 segundo, desça até alongar bem.",
    v: {
      academia: ["Panturrilha em pé na máquina", "Panturrilha no leg press"],
      casa: ["Panturrilha unilateral com halter"],
      corpo: ["Panturrilha unilateral no degrau"],
    },
  },
  core: {
    grupo: "Abdômen e lombar", composto: false,
    dica: "Umbigo puxado para dentro e respiração controlada; qualidade vale mais que quantidade.",
    v: {
      academia: ["Prancha", "Abdominal na polia", "Elevação de pernas na barra"],
      casa: ["Prancha", "Abdominal bicicleta", "Dead bug"],
      corpo: ["Prancha", "Dead bug", "Elevação de pernas deitado"],
    },
  },
};

// Modelos de sessão (ordem = ordem de execução: o composto pesado de perna
// vem primeiro, sozinho; os demais podem virar supersets se o tempo apertar).
// Montados para cada grupo grande receber ~9–16 séries/semana (faixa com
// melhor custo-benefício pra hipertrofia — Schoenfeld 2017; Pelland 2024) e
// ser treinado 2x/semana sempre que a frequência permitir.
const DIAS = {
  FA: { nome: "Corpo inteiro A", slots: ["agachamento", "supino", "remada", "flexora", "lateral"] },
  FB: { nome: "Corpo inteiro B", slots: ["dobradica", "supinoInc", "puxada", "extensora", "desenvolvimento"] },
  FC: { nome: "Corpo inteiro C", slots: ["agachamento", "supino", "remada", "gluteo", "posteriorOmbro"] },
  UA: { nome: "Superiores A", slots: ["supino", "remada", "desenvolvimento", "puxada", "lateral"] },
  LA: { nome: "Inferiores A", slots: ["agachamento", "flexora", "extensora", "gluteo", "panturrilha"] },
  UB: { nome: "Superiores B", slots: ["supinoInc", "puxada", "supino", "remada", "lateral"] },
  LB: { nome: "Inferiores B", slots: ["dobradica", "agachamento", "flexora", "gluteo", "panturrilha"] },
  PUSH: { nome: "Empurrar (peito, ombro, tríceps)", slots: ["supino", "desenvolvimento", "supinoInc", "lateral", "triceps"] },
  PULL: { nome: "Puxar (costas, bíceps)", slots: ["puxada", "remada", "posteriorOmbro", "biceps", "core"] },
  LEGS: { nome: "Pernas e glúteos", slots: ["agachamento", "dobradica", "extensora", "flexora", "gluteo", "panturrilha"] },
};

// Músculos trabalhados por padrão (1 = alvo principal, 0,5 = ajuda).
// Usado pra: contar o volume semanal, e decidir quem pode formar superset
// (só pares que NÃO dividem músculo principal — ex.: peito + costas).
export const MUSCULOS_DO_PADRAO = {
  agachamento: { quadriceps: 1, gluteos: 0.5 }, dobradica: { posterior: 1, gluteos: 0.5 }, flexora: { posterior: 1 },
  extensora: { quadriceps: 1, gluteos: 0.3 }, gluteo: { gluteos: 1, posterior: 0.3 },
  supino: { peito: 1, triceps: 0.5, ombros: 0.3 }, supinoInc: { peito: 1, triceps: 0.5, ombros: 0.3 },
  remada: { costas: 1, biceps: 0.5 }, puxada: { costas: 1, biceps: 0.5 },
  desenvolvimento: { ombros: 1, triceps: 0.5 }, lateral: { ombros: 1 }, posteriorOmbro: { ombros: 0.7, costas: 0.3 },
  biceps: { biceps: 1 }, triceps: { triceps: 1 }, panturrilha: { panturrilha: 1 }, core: { abdomen: 1 },
};
export const NOMES_MUSCULOS = {
  peito: "Peito", costas: "Costas", ombros: "Ombros", biceps: "Bíceps", triceps: "Tríceps",
  quadriceps: "Quadríceps", posterior: "Posterior de coxa", gluteos: "Glúteos", panturrilha: "Panturrilha", abdomen: "Abdômen",
};

const DIVISOES = {
  1: { nome: "Corpo inteiro", dias: ["FA"] },
  2: { nome: "Corpo inteiro A/B", dias: ["FA", "FB"] },
  3: { nome: "Corpo inteiro A/B/C", dias: ["FA", "FB", "FC"] },
  4: { nome: "Superiores / Inferiores", dias: ["UA", "LA", "UB", "LB"] },
  5: { nome: "Sup/Inf + Empurrar/Puxar/Pernas", dias: ["UA", "LA", "PUSH", "PULL", "LEGS"] },
  6: { nome: "Empurrar / Puxar / Pernas (2x)", dias: ["PUSH", "PULL", "LEGS", "PUSH", "PULL", "LEGS"] },
  7: { nome: "Empurrar / Puxar / Pernas (2x) + descanso ativo", dias: ["PUSH", "PULL", "LEGS", "PUSH", "PULL", "LEGS"] },
};

export const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
export const PADRAO_DIAS = { 1: [3], 2: [1, 4], 3: [1, 3, 5], 4: [1, 2, 4, 5], 5: [1, 2, 3, 4, 5], 6: [1, 2, 3, 4, 5, 6], 7: [0, 1, 2, 3, 4, 5, 6] };
export const MINUTOS = [30, 45, 50, 60, 75, 90];

// Prescrição atual (hipertrofia/recomposição): 6–15 reps perto da falha
// (RIR 1–2) rendem o mesmo músculo; descanso mais longo nos compostos (2 min)
// gera mais ganho que 60–90 s (Schoenfeld 2016; Singer 2024).
function prescricao(objetivo, nivel, composto) {
  const series = nivel === "iniciante" ? 3 : composto ? 4 : 3;
  const descComp = nivel === "iniciante" ? "90 s" : "2 min";
  if (objetivo === "massa") return { series, reps: composto ? "6–10" : "10–15", descanso: composto ? descComp : "75 s", rir: "1–2" };
  if (objetivo === "emagrecer") return { series: Math.min(series, 3), reps: composto ? "8–12" : "12–15", descanso: composto ? "90 s" : "60 s", rir: "1–3" };
  return { series, reps: composto ? "8–12" : "10–15", descanso: composto ? descComp : "75 s", rir: "1–2" };
}

export function linkVideo(nome) {
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(`como fazer ${nome} execução correta`)}`;
}

// ciclo 0, 1, 2… — quantos ciclos inteiros se passaram desde o início do plano
export function cicloAtual(plano, hoje = new Date()) {
  const inicio = new Date(plano.inicio);
  const semanas = Math.floor((hoje - inicio) / (7 * 864e5));
  return Math.max(0, Math.floor(semanas / (plano.semanasCiclo || 6)));
}

export function diasParaTroca(plano, hoje = new Date()) {
  const inicio = new Date(plano.inicio);
  const ciclo = cicloAtual(plano, hoje);
  const proxima = new Date(inicio.getTime() + (ciclo + 1) * (plano.semanasCiclo || 6) * 7 * 864e5);
  return Math.max(0, Math.ceil((proxima - hoje) / 864e5));
}

export function gerarPlano(perfil, { inicio = new Date().toISOString().slice(0, 10), semanasCiclo = 6 } = {}) {
  const diasSemana = (perfil.diasSemana && perfil.diasSemana.length ? perfil.diasSemana : PADRAO_DIAS[perfil.diasTreino || 3]).slice().sort();
  return {
    inicio,
    semanasCiclo,
    diasSemana,
    minutos: Number(perfil.minutosTreino) || 60,
    dias: Math.min(6, Math.max(1, diasSemana.length)),
    equipamento: perfil.equipamento || "academia",
    objetivo: perfil.objetivo,
    nivel: perfil.nivel,
    sexo: perfil.sexo,
    foco: perfil.focoMuscular || "nenhum",
  };
}

// Prioridade muscular ("especialização"): o grupo escolhido ganha mais volume
// na semana (~14–20 séries, faixa de maior hipertrofia — Schoenfeld 2017,
// Pelland 2024) sem estourar o tempo, usando bi-sets (dois exercícios
// seguidos sem descanso entre eles).
export const FOCOS = {
  nenhum: { nome: "Equilibrado", emoji: "⚖️", slots: [] },
  bracos: { nome: "Braços", emoji: "💪", slots: ["biceps", "triceps"] },
  ombros: { nome: "Ombros", emoji: "🥥", slots: ["lateral", "posteriorOmbro"] },
  peito: { nome: "Peito", emoji: "🛡️", slots: ["supinoInc", "supino"] },
  costas: { nome: "Costas", emoji: "🦅", slots: ["puxada", "remada"] },
  pernas: { nome: "Pernas", emoji: "🦵", slots: ["agachamento", "extensora"] },
  gluteos: { nome: "Glúteos", emoji: "🍑", slots: ["gluteo", "dobradica"] },
  abdomen: { nome: "Abdômen", emoji: "🔥", slots: ["core"] },
};
const DIAS_SUPERIORES = ["FA", "FB", "FC", "UA", "UB", "PUSH", "PULL"];

export const segundos = (d) => (String(d).includes("min") ? parseFloat(d) * 60 : parseInt(d, 10) || 0);
const principais = (slot) => Object.entries(MUSCULOS_DO_PADRAO[slot] || {}).filter(([, f]) => f >= 1).map(([m]) => m);
const podemParear = (a, b) => {
  const pa = principais(a.slot), pb = principais(b.slot);
  const pesados = ["agachamento", "dobradica"];
  return !pa.some((m) => pb.includes(m)) && !(pesados.includes(a.slot) && pesados.includes(b.slot));
};

// Tempo estimado da sessão (s): aquecimento 6 min + preparo 45 s por exercício
// + séries (~45 s cada) + descansos. Em superset, as duas séries seguidas
// dividem um único descanso.
export function duracaoSessao(exs) {
  let t = 360;
  for (let k = 0; k < exs.length; k++) {
    const a = exs[k];
    if (a.biset && exs[k + 1]) {
      const b = exs[k + 1];
      const comum = Math.min(a.series, b.series);
      const desc = Math.max(segundos(a.descanso), segundos(b.descanso), 60);
      t += 90 + comum * (45 + 45 + 15 + desc);
      t += (a.series - comum) * (45 + desc) + (b.series - comum) * (45 + desc);
      k++;
    } else {
      t += 45 + a.series * (45 + segundos(a.descanso));
    }
  }
  return t;
}

// Superset: 1º do par sem descanso ("vá direto pro próximo"); descanso depois do par.
function parear(exs, desde = 1) {
  for (let k = desde; k + 1 < exs.length; k++) {
    const a = exs[k], b = exs[k + 1];
    if (a.biset || (k > 0 && exs[k - 1].biset)) continue;
    if (podemParear(a, b)) {
      a.biset = true; a.parTipo = a.foco && b.foco ? "braco" : "superset";
      a.descansoOriginal = a.descanso; a.descanso = "0 s";
      b.descanso = segundos(b.descanso) >= 120 || segundos(a.descansoOriginal) >= 120 ? "2 min" : "90 s";
      k++;
    }
  }
}

// Monta os treinos do ciclo atual (lista de dias com exercícios).
export function treinosDoCiclo(plano, ciclo = cicloAtual(plano)) {
  const div = DIVISOES[plano.dias];
  const eq = plano.equipamento;
  const foco = FOCOS[plano.foco] || FOCOS.nenhum;
  const minutos = plano.minutos || 60;
  const limite = (minutos + 3) * 60;
  const trocas = plano.trocas || {};
  const contagem = {}; // mesmo padrão 2x na semana → variação diferente
  const monta = (slot, ehFoco) => {
    const pad = PADROES[slot];
    const variantes = pad.v[eq];
    const n = contagem[slot] = (contagem[slot] ?? -1) + 1;
    const original = variantes[(ciclo + n) % variantes.length];
    const nome = trocas[original] || original;
    const presc = prescricao(plano.objetivo, plano.nivel, pad.composto);
    if (minutos <= 30) { presc.series = Math.min(presc.series, 3); presc.descanso = pad.composto ? "90 s" : "60 s"; }
    if (/prancha/i.test(nome)) presc.reps = "30–45 s"; // isométrico: conta tempo
    if (ehFoco) { presc.series = Math.min(4, presc.series + (plano.nivel === "iniciante" ? 0 : 1)); presc.reps = pad.composto ? presc.reps : "8–12"; }
    return { slot, nome, original, grupo: pad.grupo, dica: pad.dica, video: linkVideo(nome), foco: ehFoco, composto: pad.composto, ...presc };
  };

  // Volume da semana até agora (pra decidir foco e extras)
  const volume = (sessoes) => {
    const v = {};
    for (const exs of sessoes) for (const x of exs) for (const [m, f] of Object.entries(MUSCULOS_DO_PADRAO[x.slot] || {})) v[m] = (v[m] || 0) + x.series * f;
    return v;
  };

  // 1ª passada: a base de cada dia
  const sessoes = div.dias.map((codigo) => {
    const slots = [...DIAS[codigo].slots];
    if (plano.sexo === "F" && ["LA", "LB", "LEGS"].includes(codigo) && !slots.includes("gluteo")) slots.push("gluteo");
    return slots.map((s) => monta(s, false));
  });

  // 2ª passada: foco distribuído pelos dias (dias de superiores primeiro pra braço)
  // até o grupo prioritário chegar a ~17 séries/semana.
  if (foco.slots.length) {
    const alvoFoco = foco.slots.flatMap((sl) => principais(sl));
    const falta = () => { const v = volume(sessoes); return alvoFoco.some((m) => (v[m] || 0) < 16); };
    const ordemDias = div.dias.map((c, i) => i).sort((a, b) => (DIAS_SUPERIORES.includes(div.dias[b]) ? 1 : 0) - (DIAS_SUPERIORES.includes(div.dias[a]) ? 1 : 0));
    for (let rodada = 0; rodada < 2 && falta(); rodada++) {
      for (const i of ordemDias) {
        if (!falta()) break;
        const bloco = foco.slots.map((s) => monta(s, true));
        if (bloco.length === 2 && podemParear(bloco[0], bloco[1])) {
          bloco[0].biset = true; bloco[0].parTipo = plano.foco === "bracos" ? "braco" : "superset";
          bloco[0].descansoOriginal = bloco[0].descanso; bloco[0].descanso = "0 s"; bloco[1].descanso = "75 s";
        }
        sessoes[i].push(...bloco);
      }
    }
  }

  // 3ª passada: encaixar cada sessão no tempo, preservando volume
  for (const exs of sessoes) {
    // a) supersets entre músculos que não competem (peito+costas, perna+ombro…)
    if (duracaoSessao(exs) > limite) parear(exs, 1);
    // b) 4ª série dos compostos → 3 (a 4ª rende pouco a mais)
    for (let k = exs.length - 1; k >= 0 && duracaoSessao(exs) > limite; k--) if (!exs[k].foco && exs[k].series > 3) exs[k].series = 3;
    // c) acessórios (isolados, fora do foco) 3 → 2 séries
    for (let k = exs.length - 1; k >= 0 && duracaoSessao(exs) > limite; k--) if (!exs[k].foco && !exs[k].composto && exs[k].series > 2) exs[k].series = 2;
    // d) foco 4 → 3 séries
    for (let k = exs.length - 1; k >= 0 && duracaoSessao(exs) > limite; k--) if (exs[k].foco && exs[k].series > 3) exs[k].series = 3;
    // e) último recurso: tira o acessório não-foco do fim (nunca o 1º composto)
    while (duracaoSessao(exs) > limite && exs.length > 4) {
      let k = exs.length - 1;
      while (k > 0 && (exs[k].foco || exs[k].composto)) k--;
      if (k <= 0) k = exs.length - 1;
      if (k > 0 && exs[k - 1].biset) { exs[k - 1].biset = false; exs[k - 1].descanso = exs[k - 1].descansoOriginal || "75 s"; }
      exs.splice(k, 1);
    }
  }

  // 4ª passada: sobrou tempo? acrescenta exercício SÓ pra músculo abaixo de ~10 séries/semana
  const CANDIDATOS = { peito: "supinoInc", costas: "puxada", ombros: "lateral", quadriceps: "extensora", posterior: "flexora", gluteos: "gluteo", biceps: "biceps", triceps: "triceps", panturrilha: "panturrilha", abdomen: "core" };
  for (let rodada = 0; rodada < 3; rodada++) {
    for (const exs of sessoes) {
      const v = volume(sessoes);
      const faltando = Object.keys(CANDIDATOS).filter((m) => (v[m] || 0) < (["panturrilha", "abdomen"].includes(m) ? 6 : 10)).sort((a, b) => (v[a] || 0) - (v[b] || 0));
      for (const m of faltando) {
        const slot = CANDIDATOS[m];
        if (exs.some((e) => e.slot === slot)) continue;
        const novo = monta(slot, false);
        if (duracaoSessao([...exs, novo]) <= limite) { exs.push(novo); break; }
        contagem[slot]--;
      }
    }
  }

  return sessoes.map((exs, i) => ({
    indice: i, codigo: div.dias[i], nome: DIAS[div.dias[i]].nome, letra: String.fromCharCode(65 + i),
    exercicios: exs, minutos: Math.round(duracaoSessao(exs) / 60), diaSemana: (plano.diasSemana || [])[i],
  }));
}

// Volume semanal por músculo (séries; exercício "ajudante" conta fração).
// Faixas: 10–20 séries = ótimo pra hipertrofia; foco pode ir a ~22.
export function volumeSemanal(dias, foco = "nenhum") {
  const v = {};
  for (const d of dias) for (const x of d.exercicios) for (const [m, f] of Object.entries(MUSCULOS_DO_PADRAO[x.slot] || {})) v[m] = (v[m] || 0) + x.series * f;
  const doFoco = new Set((FOCOS[foco] || FOCOS.nenhum).slots.flatMap((s) => principais(s)));
  const grandes = ["peito", "costas", "ombros", "quadriceps", "posterior", "gluteos", "biceps", "triceps"];
  return grandes.map((m) => {
    const s = Math.round(v[m] || 0);
    const alvo = doFoco.has(m) ? [14, 22] : ["biceps", "triceps"].includes(m) ? [6, 16] : [9, 20];
    return { musculo: m, nome: NOMES_MUSCULOS[m], series: s, alvo, foco: doFoco.has(m), status: s < alvo[0] - 2 ? "baixo" : s > alvo[1] + 2 ? "alto" : "ok" };
  });
}

// Alternativas pra trocar um exercício: outras variações do mesmo padrão
// (primeiro as do equipamento do plano, depois as dos outros).
export function alternativas(slot, equipamento, atual) {
  const pad = PADROES[slot];
  if (!pad) return [];
  const ordem = [equipamento, ...Object.keys(pad.v).filter((e) => e !== equipamento)];
  const lista = [];
  for (const e of ordem) for (const n of pad.v[e]) if (n !== atual && !lista.some((x) => x.nome === n)) lista.push({ nome: n, equipamento: e });
  return lista;
}

export function nomeDivisao(plano) {
  return DIVISOES[plano.dias].nome;
}

export function cardio(perfil) {
  if (perfil.objetivo === "emagrecer") {
    return {
      passos: 9000,
      texto: "Caminhe 8–10 mil passos por dia (é o que mais queima caloria no fim do mês) e faça 2–3 sessões de 25 min de cardio leve — dá pra conversar, mas não cantar.",
    };
  }
  if (perfil.objetivo === "massa") {
    return { passos: 7000, texto: "2 sessões de 20 min de cardio leve por semana, longe do treino de pernas: saúde do coração sem atrapalhar o ganho." };
  }
  return { passos: 8000, texto: "Mantenha 7–9 mil passos por dia e 2 sessões de cardio de 20–30 min por semana." };
}

export const REGRAS_TREINO = [
  "Progressão dupla: quando fizer o topo da faixa de repetições em todas as séries, aumente a carga na próxima vez.",
  "RIR = repetições 'na reserva'. RIR 2 é parar sabendo que ainda sairiam 2 repetições com boa forma.",
  "Aqueça com 1–2 séries leves antes do primeiro exercício de cada grupo.",
  "A cada 3 ciclos, faça uma semana mais leve (metade das séries) para o corpo recuperar.",
  "Dormir 7–9 h vale tanto quanto o treino para o resultado aparecer.",
];
