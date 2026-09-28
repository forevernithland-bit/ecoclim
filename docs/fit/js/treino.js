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

const DIAS = {
  FA: { nome: "Corpo inteiro A", slots: ["agachamento", "supino", "remada", "dobradica", "lateral", "core"] },
  FB: { nome: "Corpo inteiro B", slots: ["dobradica", "desenvolvimento", "puxada", "extensora", "biceps", "triceps"] },
  FC: { nome: "Corpo inteiro C", slots: ["gluteo", "supinoInc", "remada", "agachamento", "posteriorOmbro", "panturrilha"] },
  UA: { nome: "Superiores A", slots: ["supino", "remada", "desenvolvimento", "puxada", "biceps", "triceps"] },
  LA: { nome: "Inferiores A", slots: ["agachamento", "flexora", "extensora", "gluteo", "panturrilha", "core"] },
  UB: { nome: "Superiores B", slots: ["supinoInc", "puxada", "lateral", "remada", "posteriorOmbro", "triceps"] },
  LB: { nome: "Inferiores B", slots: ["dobradica", "agachamento", "gluteo", "flexora", "panturrilha", "core"] },
  PUSH: { nome: "Empurrar (peito, ombro, tríceps)", slots: ["supino", "desenvolvimento", "supinoInc", "lateral", "triceps"] },
  PULL: { nome: "Puxar (costas, bíceps)", slots: ["puxada", "remada", "posteriorOmbro", "biceps", "core"] },
  LEGS: { nome: "Pernas e glúteos", slots: ["agachamento", "dobradica", "extensora", "flexora", "gluteo", "panturrilha"] },
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
export const MINUTOS = [30, 45, 60, 75, 90];
// quantos exercícios cabem na sessão (aquecimento + séries + descanso)
const EXERCICIOS_POR_TEMPO = { 30: 4, 45: 5, 60: 6, 75: 7, 90: 8 };
const EXTRAS = ["core", "lateral", "panturrilha", "posteriorOmbro", "biceps", "triceps", "gluteo"];

function prescricao(objetivo, nivel, composto) {
  const series = nivel === "iniciante" ? 3 : composto ? 4 : 3;
  if (objetivo === "massa") return { series, reps: composto ? "6–10" : "10–15", descanso: composto ? "2 min" : "75 s", rir: "1–2" };
  if (objetivo === "emagrecer") return { series: Math.min(series, 3), reps: composto ? "8–12" : "12–15", descanso: composto ? "90 s" : "60 s", rir: "1–3" };
  return { series, reps: composto ? "8–12" : "10–15", descanso: composto ? "90 s" : "60 s", rir: "1–2" };
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
  };
}

// Monta os treinos do ciclo atual (lista de dias com exercícios).
export function treinosDoCiclo(plano, ciclo = cicloAtual(plano)) {
  const div = DIVISOES[plano.dias];
  const eq = plano.equipamento;
  const contagem = {}; // mesmo padrão 2x na semana → variação diferente
  return div.dias.map((codigo, i) => {
    const dia = DIAS[codigo];
    let slots = [...dia.slots];
    // Mulheres: um estímulo extra de glúteo nos dias de perna (pedido mais comum
    // e o grupo que mais responde a volume nelas).
    if (plano.sexo === "F" && ["LA", "LB", "LEGS"].includes(codigo) && !slots.includes("gluteo")) slots.push("gluteo");
    // Ajusta ao tempo disponível: corta os acessórios do fim ou acrescenta extras.
    const alvo = EXERCICIOS_POR_TEMPO[plano.minutos || 60] || 6;
    if (slots.length > alvo) slots = slots.slice(0, alvo);
    for (const x of EXTRAS) { if (slots.length >= alvo) break; if (!slots.includes(x)) slots.push(x); }
    let exercicios = slots.map((slot) => {
      const pad = PADROES[slot];
      const variantes = pad.v[eq];
      const n = contagem[slot] = (contagem[slot] ?? -1) + 1;
      const nome = variantes[(ciclo + n) % variantes.length];
      const presc = prescricao(plano.objetivo, plano.nivel, pad.composto);
      if ((plano.minutos || 60) <= 30) { presc.series = Math.min(presc.series, 3); presc.descanso = pad.composto ? "75 s" : "45 s"; }
      if (/prancha/i.test(nome)) presc.reps = "30–45 s"; // isométrico: conta tempo, não repetição
      return { slot, nome, grupo: pad.grupo, dica: pad.dica, video: linkVideo(nome), ...presc };
    });
    // aquecimento 6 min + (execução ~50 s + descanso) por série + ~1 min de troca por exercício
    const duracao = () => 360 + exercicios.reduce((a, x) => a + 60 + x.series * (50 + (x.descanso.includes("min") ? parseFloat(x.descanso) * 60 : parseInt(x.descanso, 10))), 0);
    // Não pode passar do tempo escolhido: tira acessórios do fim (mínimo 4 exercícios)
    while (duracao() > ((plano.minutos || 60) + 4) * 60 && exercicios.length > 4) exercicios.pop();
    const segs = duracao();
    const diaSemana = (plano.diasSemana || [])[i];
    return { indice: i, codigo, nome: dia.nome, letra: String.fromCharCode(65 + i), exercicios, minutos: Math.round(segs / 60), diaSemana };
  });
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
