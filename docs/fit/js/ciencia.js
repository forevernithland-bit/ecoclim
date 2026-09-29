// Toda a "matemática com base científica" do app fica aqui — sem rede, sem IA.
// A IA (backend) refina em cima destes números, mas o app funciona só com eles.
//
// Referências principais (resumidas em linguagem simples nas telas):
// - Gasto basal: Mifflin-St Jeor (1990) — a fórmula mais precisa p/ população geral.
// - % de gordura por fita métrica: fórmula da Marinha dos EUA (Hodgdon & Beckett).
// - Ritmo de perda: 0,5–1% do peso/semana preserva músculo (Helms et al., 2014).
// - Proteína: 1,6–2,2 g/kg (Morton et al., 2018; Helms 2014 p/ déficit).
// - Ganho de músculo por nível de treino: modelo de Alan Aragon / Lyle McDonald.
// - Volume de treino: 10–20 séries/músculo/semana (Schoenfeld et al., 2017).

export const OBJETIVOS = {
  emagrecer: { rotulo: "Emagrecer", emoji: "🔥", desc: "Perder gordura mantendo os músculos" },
  massa: { rotulo: "Ganhar massa", emoji: "💪", desc: "Ganhar músculo com o mínimo de gordura" },
  recomp: { rotulo: "Definir (recomposição)", emoji: "⚖️", desc: "Perder gordura e ganhar músculo ao mesmo tempo" },
  saude: { rotulo: "Saúde e disposição", emoji: "🌱", desc: "Comer melhor, treinar e manter o peso" },
};

export const NIVEIS = {
  iniciante: { rotulo: "Iniciante", desc: "Nunca treinei ou treino há menos de 1 ano" },
  intermediario: { rotulo: "Intermediário", desc: "Treino com regularidade há 1–3 anos" },
  avancado: { rotulo: "Avançado", desc: "Treino sério há mais de 3 anos" },
};

// Físicos-alvo: cada um tem um % de gordura e um FFMI (índice de massa magra)
// típicos. É isso que permite estimar "quanto tempo até esse corpo".
// FFMI = massa magra (kg) / altura² — natural máximo realista ≈ 25 (homens) / 21 (mulheres).
export const FISICOS = {
  M: [
    { id: "saudavel", nome: "Saudável", gordura: 18, ffmi: 19.5, desc: "Barriga lisa, sem músculos marcados. Ótimo p/ saúde." },
    { id: "atletico", nome: "Atlético", gordura: 13, ffmi: 21, desc: "Abdômen começando a aparecer, ombros e braços desenhados." },
    { id: "fitness", nome: "Modelo fitness", gordura: 10, ffmi: 22, desc: "Tanquinho visível, 'corpo de capa de revista'." },
    { id: "forte", nome: "Forte / volumoso", gordura: 16, ffmi: 23.5, desc: "Muito músculo, pouca preocupação com tanquinho." },
    { id: "shredded", nome: "Fisiculturista (palco)", gordura: 7, ffmi: 24, desc: "Veias e cortes. Difícil de manter o ano todo." },
  ],
  F: [
    { id: "saudavel", nome: "Saudável", gordura: 28, ffmi: 15.5, desc: "Corpo leve, sem excessos. Ótimo p/ saúde e hormônios." },
    { id: "tonificada", nome: "Tonificada", gordura: 24, ffmi: 16.5, desc: "Braços e pernas firmes, cintura mais fina." },
    { id: "atletica", nome: "Atlética", gordura: 21, ffmi: 17.5, desc: "Abdômen com linhas, glúteos e pernas desenhados." },
    { id: "fitness", nome: "Modelo fitness", gordura: 18, ffmi: 18.5, desc: "Abdômen definido, curvas musculares evidentes." },
    { id: "wellness", nome: "Wellness / competição", gordura: 15, ffmi: 19.5, desc: "Muito glúteo e perna, pouquíssima gordura." },
  ],
};

export const MEDIDAS = [
  { id: "pescoco", nome: "Pescoço", dica: "Logo abaixo do pomo de adão, fita reta.", obrig: true },
  { id: "ombros", nome: "Ombros", dica: "Volta completa na parte mais larga dos ombros." },
  { id: "peito", nome: "Peito / busto", dica: "Na altura dos mamilos, sem prender a respiração." },
  { id: "braco", nome: "Braço (direito)", dica: "Meio do braço, relaxado." },
  { id: "cintura", nome: "Cintura", dica: "Na altura do umbigo, barriga relaxada.", obrig: true },
  { id: "quadril", nome: "Quadril", dica: "Na parte mais larga do bumbum.", obrig: "F" },
  { id: "coxa", nome: "Coxa (direita)", dica: "Logo abaixo do bumbum, na parte mais grossa." },
  { id: "panturrilha", nome: "Panturrilha", dica: "Na parte mais grossa, em pé." },
];

const r1 = (n) => Math.round(n * 10) / 10;
const br = (n) => r1(n).toLocaleString("pt-BR");

export function imc(pesoKg, alturaCm) {
  const m = alturaCm / 100;
  return r1(pesoKg / (m * m));
}

export function faixaImc(v) {
  if (v < 18.5) return "Abaixo do peso";
  if (v < 25) return "Peso normal";
  if (v < 30) return "Sobrepeso";
  if (v < 35) return "Obesidade grau I";
  if (v < 40) return "Obesidade grau II";
  return "Obesidade grau III";
}

// Fórmula da Marinha dos EUA (medidas em cm). Erro típico ±3–4 pontos —
// suficiente pra acompanhar tendência, que é o que importa.
export function gorduraMarinha({ sexo, alturaCm, pescoco, cintura, quadril }) {
  if (!alturaCm || !pescoco || !cintura) return null;
  let v;
  if (sexo === "F") {
    if (!quadril) return null;
    const x = cintura + quadril - pescoco;
    if (x <= 0) return null;
    v = 495 / (1.29579 - 0.35004 * Math.log10(x) + 0.221 * Math.log10(alturaCm)) - 450;
  } else {
    const x = cintura - pescoco;
    if (x <= 0) return null;
    v = 495 / (1.0324 - 0.19077 * Math.log10(x) + 0.15456 * Math.log10(alturaCm)) - 450;
  }
  if (!isFinite(v)) return null;
  return r1(Math.min(60, Math.max(3, v)));
}

// Sem medidas: estimativa pelo IMC (Deurenberg, 1991). Bem menos precisa.
export function gorduraPorImc({ sexo, idade, pesoKg, alturaCm }) {
  const v = 1.2 * imc(pesoKg, alturaCm) + 0.23 * idade - 10.8 * (sexo === "M" ? 1 : 0) - 5.4;
  return r1(Math.min(60, Math.max(3, v)));
}

export function gorduraEstimada(p, medidas) {
  const m = medidas || {};
  return gorduraMarinha({ sexo: p.sexo, alturaCm: p.altura, pescoco: +m.pescoco, cintura: +m.cintura, quadril: +m.quadril })
    ?? gorduraPorImc({ sexo: p.sexo, idade: p.idade, pesoKg: p.peso, alturaCm: p.altura });
}

export function ffmi(pesoKg, alturaCm, gorduraPct) {
  const magra = pesoKg * (1 - gorduraPct / 100);
  const m = alturaCm / 100;
  return r1(magra / (m * m));
}

export function tmb({ sexo, idade, peso, altura }) {
  return Math.round(10 * peso + 6.25 * altura - 5 * idade + (sexo === "M" ? 5 : -161));
}

// Fator de atividade conta os treinos + um NEAT "médio" (dia a dia).
export function fatorAtividade(diasTreino) {
  const d = Number(diasTreino) || 0;
  if (d <= 1) return 1.3;
  if (d <= 3) return 1.45;
  if (d <= 5) return 1.6;
  return 1.72;
}

export function gastoDiario(p) {
  return Math.round(tmb(p) * fatorAtividade(p.diasTreino));
}

// Metas diárias de calorias e macros de acordo com o objetivo.
export function metas(p) {
  const gasto = gastoDiario(p);
  const obj = p.objetivo || "saude";
  let kcal, protKg, explic;
  if (obj === "emagrecer") {
    // déficit de ~20%, com piso de segurança
    kcal = Math.max(gasto * 0.8, p.sexo === "M" ? 1500 : 1200);
    protKg = 2.0;
    explic = "Déficit de ~20% do seu gasto: rápido o bastante pra ver resultado, suave o bastante pra não perder músculo.";
  } else if (obj === "massa") {
    const sup = p.nivel === "iniciante" ? 0.12 : p.nivel === "avancado" ? 0.05 : 0.08;
    kcal = gasto * (1 + sup);
    protKg = 1.8;
    explic = `Superávit de ~${Math.round(sup * 100)}%: energia pro músculo crescer sem acumular gordura demais.`;
  } else if (obj === "recomp") {
    kcal = gasto * 0.92;
    protKg = 2.2;
    explic = "Levemente abaixo do gasto com proteína alta: perde gordura e ainda ganha músculo (funciona melhor p/ iniciantes).";
  } else {
    kcal = gasto;
    protKg = 1.6;
    explic = "Manutenção: mesmo peso, mais qualidade na comida e mais força.";
  }
  kcal = Math.round(kcal / 10) * 10;
  // Proteína por kg de massa magra-ajustada quando a pessoa tem muita gordura
  const pesoRef = p.gordura && p.gordura > (p.sexo === "M" ? 25 : 32)
    ? p.peso * (1 - p.gordura / 100) / (p.sexo === "M" ? 0.85 : 0.75)
    : p.peso;
  const prot = Math.round(pesoRef * protKg);
  const gord = Math.round((kcal * 0.27) / 9);
  const carb = Math.max(50, Math.round((kcal - prot * 4 - gord * 9) / 4));
  const agua = Math.round(p.peso * 35 / 100) / 10; // litros
  const fibra = Math.round(kcal / 1000 * 14);
  return { gasto, tmb: tmb(p), kcal, prot, carb, gord, agua, fibra, explic };
}

// Quanto a rotina escolhida entrega de estímulo, comparado a uma rotina
// "cheia" (4 dias × 60 min ≈ 16–20 séries/músculo/semana). Menos tempo de
// treino = ganho muscular mais lento (relação dose-resposta, Schoenfeld 2017).
export function fatorTreino(p) {
  const dias = Number(p.diasTreino) || 3;
  const min = Number(p.minutosTreino) || 60;
  return Math.min(1.1, Math.max(0.55, 0.5 + 0.5 * (dias * min) / 240));
}

// Sugere o objetivo a partir do físico escolhido x como a pessoa está hoje.
export function objetivoSugerido(p, fisico) {
  const ffmiHoje = ffmi(p.peso, p.altura, p.gordura);
  if (p.gordura > fisico.gordura + 4) return "emagrecer";
  if (ffmiHoje < fisico.ffmi - 1.5 && p.gordura <= fisico.gordura + 1.5) return "massa";
  return "recomp";
}

// Taxa realista de ganho de músculo por MÊS, em kg de massa magra.
function ganhoMagroMes(p, meses) {
  const base = { iniciante: 0.9, intermediario: 0.45, avancado: 0.2 }[p.nivel || "iniciante"];
  // mulheres: ~metade em valor absoluto; ritmo cai com o tempo
  const sexo = p.sexo === "F" ? 0.5 : 1;
  const idade = p.idade > 40 ? 0.8 : 1;
  const decai = meses > 12 ? 0.6 : 1;
  return base * sexo * idade * decai * fatorTreino(p);
}

// Projeção "se continuar assim": a partir do que a pessoa REALMENTE está
// fazendo (média de calorias, % dos treinos cumpridos, proteína), simula mês
// a mês peso, gordura e massa magra. 1 kg de gordura ≈ 7.700 kcal.
// balanco = calorias comidas − gasto (kcal/dia; negativo = déficit).
export function projetarRitmo(p, { balanco, aderenciaTreino = 1, proteinaOk = true }, meses = 6) {
  let magra = p.peso * (1 - p.gordura / 100);
  let gordKg = p.peso - magra;
  const trilha = [{ mes: 0, peso: r1(p.peso), gordura: r1(p.gordura), magra: r1(magra) }];
  for (let m = 1; m <= meses; m++) {
    const deltaPeso = (balanco * 30.4) / 7700;
    // músculo: depende do treino cumprido, da proteína e da energia disponível
    let ganho = ganhoMagroMes(p, m) * Math.min(1, aderenciaTreino) * (proteinaOk ? 1 : 0.6);
    if (balanco < -250) ganho *= p.nivel === "iniciante" ? 0.6 : 0.35; // em déficit cresce menos
    if (aderenciaTreino < 0.3) ganho = balanco < -250 ? -0.15 : 0;    // sem treino, déficit come músculo
    const deltaGord = deltaPeso - ganho;
    magra = Math.max(magra * 0.9, magra + ganho);
    gordKg = Math.max(p.peso * 0.03, gordKg + deltaGord);
    const peso = magra + gordKg;
    trilha.push({ mes: m, peso: r1(peso), gordura: r1((gordKg / peso) * 100), magra: r1(magra) });
  }
  return trilha;
}

// Estimativa de tempo até um físico-alvo. Simula mês a mês: primeiro reduz
// gordura (se precisar), depois constrói massa magra (se precisar).
export function estimarTempoFisico(p, fisico) {
  const gord0 = p.gordura;
  const magra0 = p.peso * (1 - gord0 / 100);
  const alt2 = (p.altura / 100) ** 2;
  const magraAlvo = fisico.ffmi * alt2;
  let magra = magra0;
  let gordKg = p.peso - magra0;
  const gordAlvoPct = fisico.gordura;
  let meses = 0;
  const trilha = [];
  let fasesCut = 0, fasesBulk = 0;
  while (meses < 120) {
    const peso = magra + gordKg;
    const pct = (gordKg / peso) * 100;
    const faltaMagra = magraAlvo - magra;
    const faltaGord = pct - gordAlvoPct;
    if (faltaMagra <= 0.3 && faltaGord <= 0.5) break;
    const ganho = ganhoMagroMes(p, meses);
    if (faltaGord > 0.5 && (pct > gordAlvoPct + 4 || faltaMagra <= 0.3)) {
      // fase de definição: ~0,7% do peso/semana ≈ 3% ao mês, 85% disso gordura
      const perde = peso * 0.03;
      gordKg -= perde * 0.85;
      magra += p.nivel === "iniciante" ? ganho * 0.3 : -perde * 0.05;
      fasesCut++;
    } else {
      // fase de construção: ganho magro + um pouco de gordura junto
      magra += ganho;
      gordKg += ganho * (p.nivel === "iniciante" ? 0.5 : 1);
      fasesBulk++;
    }
    meses++;
    trilha.push({ mes: meses, peso: r1(magra + gordKg), gordura: r1((gordKg / (magra + gordKg)) * 100) });
  }
  const pesoFinal = r1(magra + gordKg);
  // faixa de incerteza: pessoas respondem diferente (genética, sono, adesão)
  return {
    meses,
    minimo: Math.max(1, Math.round(meses * 0.75)),
    maximo: Math.round(meses * 1.4) + 1,
    pesoFinal,
    mesesDefinicao: fasesCut,
    mesesConstrucao: fasesBulk,
    trilha,
    inalcancavel: meses >= 120,
  };
}

// Projeção simples de peso ao longo do plano, para o objetivo escolhido.
export function projecaoObjetivo(p, pesoMeta) {
  const obj = p.objetivo;
  if (obj === "emagrecer" && pesoMeta && pesoMeta < p.peso) {
    const semanal = Math.min(1, Math.max(0.5, p.gordura > 30 ? 1 : p.gordura > 20 ? 0.75 : 0.5)) / 100;
    const kgSemana = p.peso * semanal;
    const semanas = Math.ceil(Math.log(pesoMeta / p.peso) / Math.log(1 - semanal));
    return {
      texto: `Perder ~${br(kgSemana)} kg por semana é o ritmo que a ciência considera seguro pra você.`,
      semanas,
      kgSemana: r1(kgSemana),
    };
  }
  if (obj === "massa") {
    const mes = ganhoMagroMes(p, 0);
    return {
      texto: `No seu nível, ganhar ~${br(mes)} kg de músculo por mês é realista (o peso na balança sobe um pouco mais, com água e glicogênio).`,
      kgMesMusculo: r1(mes),
      semanas: pesoMeta && pesoMeta > p.peso ? Math.ceil(((pesoMeta - p.peso) / (mes * 1.5)) * 4.3) : null,
    };
  }
  if (obj === "recomp") {
    return { texto: "Na recomposição o peso quase não muda — o que muda são as medidas e o espelho. Acompanhe a cintura e as fotos.", semanas: null };
  }
  return { texto: "Foco em hábitos: o peso deve ficar estável enquanto força e disposição sobem.", semanas: null };
}

export function formatarMeses(m) {
  if (m < 1) return "menos de 1 mês";
  if (m < 12) return `${m} ${m === 1 ? "mês" : "meses"}`;
  const a = Math.floor(m / 12), r = m % 12;
  return `${a} ${a === 1 ? "ano" : "anos"}${r ? ` e ${r} ${r === 1 ? "mês" : "meses"}` : ""}`;
}
