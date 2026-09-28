// Suplementos com base na força da evidência (posição da ISSN 2018/2021 e
// consenso do COI 2018). Nível A = muita pesquisa boa mostrando efeito.

const LISTA = [
  {
    id: "creatina", nome: "Creatina monohidratada", nivel: "A", emoji: "⚡",
    dose: "3–5 g por dia, todo dia (horário tanto faz). Não precisa de 'fase de saturação'.",
    porque: "O suplemento mais estudado do mundo: mais força, mais músculo e até benefícios para o cérebro. Seguro para rins saudáveis.",
    para: () => true,
  },
  {
    id: "whey", nome: "Whey protein", nivel: "A", emoji: "🥛",
    dose: "1 scoop (≈25 g de proteína) quando não bater a meta de proteína só com comida.",
    porque: "Não é mágico — é comida prática. Ajuda a atingir a proteína do dia, que é o que realmente importa.",
    para: () => true,
  },
  {
    id: "cafeina", nome: "Cafeína", nivel: "A", emoji: "☕",
    dose: "3 mg por kg, 30–60 min antes do treino (um café forte já resolve). Evite depois das 16 h.",
    porque: "Aumenta força, resistência e disposição no treino. Cortar o sono anula o benefício.",
    para: () => true,
  },
  {
    id: "vitd", nome: "Vitamina D", nivel: "B", emoji: "☀️",
    dose: "Só com exame: se estiver baixa, o médico ajusta a dose (comum 1.000–2.000 UI/dia).",
    porque: "Muita gente no Brasil tem deficiência mesmo com sol. Baixa vitamina D atrapalha imunidade, humor e ossos.",
    para: () => true,
  },
  {
    id: "omega3", nome: "Ômega-3 (EPA + DHA)", nivel: "B", emoji: "🐟",
    dose: "1–2 g de EPA+DHA por dia, se você come peixe menos de 2x por semana.",
    porque: "Bom para coração e articulações. Não emagrece, mas ajuda a saúde geral.",
    para: () => true,
  },
  {
    id: "fibra", nome: "Fibra (psyllium)", nivel: "B", emoji: "🌾",
    dose: "5–10 g por dia com bastante água, se tiver dificuldade de bater a meta de fibras.",
    porque: "Aumenta a saciedade e regula o intestino — muito útil no déficit calórico.",
    para: (p) => p.objetivo === "emagrecer" || p.objetivo === "recomp",
  },
  {
    id: "beta", nome: "Beta-alanina", nivel: "B", emoji: "🏃",
    dose: "3,2–6,4 g por dia divididos. Pode dar formigamento (inofensivo).",
    porque: "Ajuda em esforços de 1–4 minutos (séries longas, HIIT). Efeito pequeno na musculação tradicional.",
    para: (p) => p.nivel !== "iniciante",
  },
  {
    id: "ferro", nome: "Ferro", nivel: "B", emoji: "🩸",
    dose: "Só com exame de ferritina e orientação médica.",
    porque: "Mulheres que menstruam e quem treina muito têm mais risco de ferro baixo, que derruba o rendimento.",
    para: (p) => p.sexo === "F",
  },
];

export const NAO_VALE = [
  { nome: "BCAA", porque: "Se você come proteína suficiente, não acrescenta nada." },
  { nome: "Termogênicos / 'queimadores'", porque: "O efeito é basicamente da cafeína — mais caro e com mais riscos." },
  { nome: "Glutamina", porque: "Não melhora ganho de músculo nem recuperação em pessoas saudáveis." },
  { nome: "Pré-treinos com 'fórmula secreta'", porque: "Cafeína + marketing. Um café faz o mesmo." },
  { nome: "'Hormonais naturais' (tribulus etc.)", porque: "Não aumentam testosterona de forma relevante." },
];

export function sugerirSuplementos(perfil) {
  return LISTA.filter((s) => s.para(perfil));
}

export const AVISO_SUPLEMENTOS =
  "Informação educativa, não substitui consulta. Gestantes, pessoas com doença renal, cardíaca ou que usam remédios devem falar com o médico antes.";
