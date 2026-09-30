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
  // ---- extras pra quem usa GLP-1 / tirzepatida (comendo pouco) ----
  {
    id: "multi", nome: "Multivitamínico simples", nivel: "B", emoji: "💊",
    dose: "1 comprimido por dia com uma refeição (dose de 100% da IDR, sem megadoses).",
    porque: "Com o remédio você come bem menos comida — e menos comida = menos vitaminas e minerais. É um seguro barato enquanto durar o tratamento.",
    para: (p) => !!p.medicamento,
  },
  {
    id: "eletrolitos", nome: "Eletrólitos (sódio, potássio, magnésio)", nivel: "B", emoji: "🧂",
    dose: "Isotônico sem açúcar ou sais de reidratação nos dias de diarreia, vômito ou treino com muito suor.",
    porque: "Pouca comida + pouca sede + efeitos intestinais = desidratação, tontura e câimbra. Repor sais resolve a maior parte do 'cansaço' do remédio.",
    para: (p) => !!p.medicamento,
  },
];

// Chás: o que cada um faz DE VERDADE (e o que é marketing).
export const CHAS = [
  { nome: "Chá verde", emoji: "🍵", nivel: "C",
    efeito: "Catequinas (EGCG) + cafeína aumentam um pouco o gasto de energia e a queima de gordura. Na média dos estudos: ~1 kg a mais em 12 semanas — ajuda, não faz milagre.",
    uso: "2 a 3 xícaras por dia, entre as refeições (atrapalha a absorção de ferro se tomar junto). Não depois das 16 h (cafeína).",
    cuidado: "Evite cápsulas de extrato concentrado: acima de ~800 mg de EGCG por dia há casos de lesão no fígado (EFSA 2018). O chá em si é seguro." },
  { nome: "Mate / chimarrão / tereré", emoji: "🧉", nivel: "C",
    efeito: "Tem cafeína e antioxidantes; pequeno efeito na saciedade e no gasto de energia, parecido com o chá verde.",
    uso: "À vontade durante o dia, contando a cafeína (1 cuia ≈ 1 xícara de café). Ótimo antes do treino.",
    cuidado: "Bebidas MUITO quentes (acima de ~65 °C) todo dia aumentam o risco de câncer de esôfago — espere amornar." },
  { nome: "Gengibre", emoji: "🫚", nivel: "B",
    efeito: "Boa evidência contra náusea (gravidez, quimioterapia, enjoo). Excelente pra quem usa Mounjaro/Ozempic. Efeito no peso é mínimo.",
    uso: "1 a 1,5 g por dia (≈ 2 fatias finas de raiz em infusão), em goles ao longo do dia quando vier o enjoo.",
    cuidado: "Quem usa anticoagulante ou tem cálculo na vesícula: fale com o médico antes de usar muito." },
  { nome: "Hibisco", emoji: "🌺", nivel: "C",
    efeito: "Reduz um pouco a pressão arterial (bem estudado). Pra emagrecer: evidência fraca — perde-se mais água que gordura.",
    uso: "1 a 2 xícaras por dia, se gostar.",
    cuidado: "Evite na gravidez/tentando engravidar e se já toma remédio pra pressão ou diurético (pode baixar demais)." },
  { nome: "Camomila / melissa / mulungu", emoji: "🌼", nivel: "C",
    efeito: "Leve efeito calmante que pode ajudar a dormir. Sono ruim aumenta a fome no dia seguinte — então ajuda indiretamente.",
    uso: "1 xícara 30–60 min antes de deitar.",
    cuidado: "Camomila: evite se tem alergia a margarida/ambrosia." },
  { nome: "Hortelã", emoji: "🌿", nivel: "C",
    efeito: "Alivia gases e estufamento depois das refeições.",
    uso: "1 xícara depois do almoço ou jantar.",
    cuidado: "Piora o refluxo/azia — se você tem, prefira gengibre ou camomila." },
];

// Ioimbina: evidência pequena, riscos reais. Mostramos o protocolo DOS ESTUDOS,
// com todas as contraindicações — decisão final é médica.
export function ioimbina(peso = 75) {
  const dose = Math.round(peso * 0.2);
  const teste = Math.round(peso * 0.1);
  return {
    nome: "Ioimbina", emoji: "⚠️", nivel: "C",
    oque: "Bloqueia os receptores alfa-2 das células de gordura — os mesmos que deixam barriga, lombar e culote mais 'teimosos'. Com isso a gordura dessas regiões é liberada mais fácil, mas SÓ quando a insulina está baixa (jejum).",
    evidencia: "Poucos estudos pequenos. O mais citado (Ostojic 2006, atletas de futebol): ~20 mg/dia por 3 semanas baixou o % de gordura de 9,3% para 7,1%, sem mudar o peso. Não substitui o déficit calórico — é o 'último 1%' pra quem já está magro e com dieta em dia.",
    protocolo: [
      `Dose dos estudos: 0,2 mg por kg — pra você ≈ ${dose} mg/dia.`,
      `Comece com metade (≈ ${teste} mg) por 3–4 dias pra testar a tolerância.`,
      "Tome em JEJUM, 15–30 min antes do cardio ou treino da manhã. Comer carboidrato antes (insulina alta) anula o efeito.",
      "Espere ~1 hora depois do treino pra comer.",
      "Nunca à tarde/noite (insônia) e no máximo 1 café junto — nada de termogênico ou pré-treino.",
      "Use em ciclos de 4–8 semanas, na fase final do emagrecimento.",
    ],
    contra: [
      "Pressão alta, arritmia ou qualquer doença do coração",
      "Ansiedade, síndrome do pânico, depressão ou transtorno bipolar",
      "Uso de antidepressivos (especialmente IMAO e tricíclicos), remédios de pressão ou estimulantes",
      "Gravidez, amamentação, doença nos rins ou no fígado",
      "Início de Mounjaro/Ozempic (piora náusea e aumenta a frequência cardíaca, que o remédio já sobe um pouco)",
    ],
    efeitos: "Ansiedade, tremor, coração acelerado, aumento da pressão, calor, insônia, enjoo. Se sentir qualquer um: pare.",
    brasil: "No Brasil a Anvisa não permite ioimbina em suplemento alimentar — só manipulada com receita. Produtos importados com 'ioimbina' costumam ter dose errada ou vir misturados com outros estimulantes.",
  };
}

export const NAO_VALE = [
  { nome: "BCAA", porque: "Se você come proteína suficiente, não acrescenta nada." },
  { nome: "Termogênicos / 'queimadores'", porque: "O efeito é basicamente da cafeína — mais caro e com mais riscos." },
  { nome: "Glutamina", porque: "Não melhora ganho de músculo nem recuperação em pessoas saudáveis." },
  { nome: "Pré-treinos com 'fórmula secreta'", porque: "Cafeína + marketing. Um café faz o mesmo." },
  { nome: "'Hormonais naturais' (tribulus etc.)", porque: "Não aumentam testosterona de forma relevante." },
  { nome: "Chás 'detox' / 'seca barriga' / cavalinha", porque: "São diuréticos: a balança baixa por perda de ÁGUA, que volta no dia seguinte. Não queimam gordura." },
  { nome: "Rauwolscina (alfa-ioimbina)", porque: "Vendida como 'ioimbina mais forte', mas quase não tem estudo em humanos — risco sem benefício provado." },
];

export function sugerirSuplementos(perfil) {
  return LISTA.filter((s) => s.para(perfil));
}

export const AVISO_SUPLEMENTOS =
  "Informação educativa, não substitui consulta. Gestantes, pessoas com doença renal, cardíaca ou que usam remédios devem falar com o médico antes.";
