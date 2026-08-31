import streamlit as st
import pandas as pd
import datetime
import re
import unicodedata
import difflib
import utils

# ---------------------------------------------------------------------------
# Automação por Equipamentos (Partes 1 e 2)
# ---------------------------------------------------------------------------
# O tipo de instalação é detectado por palavra-chave no nome do produto (o
# catálogo não possui campo de categoria) e alimenta DUAS automações:
#   Parte 1 -> Modelo da Capa
#   Parte 2 -> Serviço sugerido + valor (buscado no catálogo de Serviços)
#
# Prioridade dos tipos: ACOPLADO > MODULAR > TRADICIONAL.
TIPOS_INSTALACAO = [
    # (tipo canônico, termos em minúsculo)
    ("acoplado",    ["acoplado"]),
    ("modular",     ["modular", "modul", "módul", "vácuo", "vacuo"]),
    ("tradicional", ["coletor", "tradicional", "placa"]),
]

CAPA_POR_TIPO = {
    "acoplado":    "Aquecedor Solar a Vácuo Acoplado",
    "modular":     "Aquecedor Solar Modular",
    "tradicional": "Aquecedor Solar Tradicional",
}

# Unidade da medida que compõe o nome do serviço, por tipo, e de qual produto
# a medida deve ser lida:
#   acoplado    -> nº de TUBOS lido do próprio produto acoplado
#   modular     -> LITROS lidos da linha do Boiler
#   tradicional -> LITROS lidos da linha do Boiler
UNIDADE_POR_TIPO = {"acoplado": "tubos", "modular": "litros", "tradicional": "litros"}


def _norm(texto):
    """minúsculas + sem acentos, para comparações robustas."""
    t = str(texto).lower()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')


def _nome_produto_linha(linha):
    """Retorna o nome do produto de uma linha do orçamento (base ou manual)."""
    base = str(linha.get('Produto da Base', '')).strip()
    if base.upper() in ['', 'NONE', 'NAN', 'OUTRO']:
        return str(linha.get('Produto Manual', '')).strip()
    return base


def _nomes_produtos(df):
    """Lista dos nomes de produto preenchidos, na ordem das linhas."""
    if df is None or getattr(df, 'empty', True):
        return []
    return [n for n in (_nome_produto_linha(l) for _, l in df.iterrows()) if n]


def detectar_tipo_instalacao(df):
    """Tipo de instalação (acoplado/modular/tradicional) a partir dos equipamentos.

    Varre todos os produtos e decide por prioridade fixa, de modo determinístico
    independentemente da ordem das linhas. Retorna None se nada for reconhecido.
    """
    nomes_norm = [_norm(n) for n in _nomes_produtos(df)]
    for tipo, termos in TIPOS_INSTALACAO:
        termos_norm = [_norm(t) for t in termos]
        if any(any(t in nome for t in termos_norm) for nome in nomes_norm):
            return tipo
    return None


def detectar_capa_por_produtos(df):
    """Parte 1: modelo de capa sugerido a partir dos equipamentos (ou None)."""
    return CAPA_POR_TIPO.get(detectar_tipo_instalacao(df))


def _extrair_numero(nome, padrao):
    m = re.search(padrao, _norm(nome))
    return int(m.group(1)) if m else None


def _medida_do_tipo(df, tipo):
    """Retorna (numero, unidade) da medida que compõe o nome do serviço.

    - acoplado    -> nº de tubos lido do próprio produto acoplado
    - modular/trad -> litros lidos da linha do Boiler (ignora tubos do módulo /
                      quantidade de coletores)
    Retorna (None, unidade) quando a medida não é encontrada.
    """
    unidade = UNIDADE_POR_TIPO.get(tipo, "")
    nomes = _nomes_produtos(df)

    if tipo == "acoplado":
        for nome in nomes:
            if "acoplado" in _norm(nome):
                n = _extrair_numero(nome, r'(\d+)\s*tubos?')
                if n:
                    return n, unidade
        return None, unidade

    # modular / tradicional -> litros do Boiler
    for nome in nomes:
        n_norm = _norm(nome)
        if "boiler" in n_norm or "reservat" in n_norm:
            n = _extrair_numero(nome, r'(\d+)\s*(?:litros?|lts?|l)\b')
            if n is None:  # Boiler sem unidade explícita: usa o 1º número do nome
                n = _extrair_numero(nome, r'(\d+)')
            if n:
                return n, unidade
    return None, unidade


def _buscar_servico_catalogo(db_servicos, tipo, medida, unidade):
    """Procura no catálogo de Serviços o item que casa com tipo + número + unidade.

    Match tolerante a variações de grafia: exige o tipo, a raiz da unidade
    (tubo/litro) e o número como palavra inteira. Retorna o nome exato do item
    cadastrado (para casar com o selectbox) ou None.
    """
    if db_servicos is None or getattr(db_servicos, 'empty', True):
        return None
    raiz_unidade = "tubo" if unidade == "tubos" else "litro"
    candidatos = []
    for item in db_servicos['Item'].dropna():
        n = _norm(item)
        if tipo in n and raiz_unidade in n and re.search(rf'\b{medida}\b', n):
            candidatos.append(str(item))
    if not candidatos:
        return None
    # Preferir itens que contenham "instala" e, em empate, o nome mais curto.
    candidatos.sort(key=lambda x: (0 if "instala" in _norm(x) else 1, len(x)))
    return candidatos[0]


def sugerir_servico_por_produtos(df, db_servicos):
    """Parte 2: monta a sugestão de serviço a partir dos equipamentos.

    Retorna None quando nenhum tipo é reconhecido (ex.: orçamento só de peças).
    Caso contrário, um dict:
        {tipo, medida, unidade, nome_sugerido, item_catalogo}
    onde:
      - medida = None  -> tipo reconhecido mas medida não identificada
      - item_catalogo  -> nome exato do serviço no catálogo, ou None se não achou
    """
    tipo = detectar_tipo_instalacao(df)
    if not tipo:
        return None
    medida, unidade = _medida_do_tipo(df, tipo)
    if medida is None:
        return {"tipo": tipo, "medida": None, "unidade": unidade,
                "nome_sugerido": None, "item_catalogo": None}
    nome_sugerido = f"INSTALAÇÃO {tipo.upper()} {medida} {unidade.upper()}"
    item_catalogo = _buscar_servico_catalogo(db_servicos, tipo, medida, unidade)
    return {"tipo": tipo, "medida": medida, "unidade": unidade,
            "nome_sugerido": nome_sugerido, "item_catalogo": item_catalogo}


def _assinatura_produtos(df):
    """Assinatura dos produtos selecionados, para detectar mudanças na seleção."""
    return tuple(_nomes_produtos(df))


# ---------------------------------------------------------------------------
# Nome do arquivo do orçamento salvo no Drive
#   Formato: {numero}_{primeiro_nome}_{descricao}
#   Ex.: 260806-1850_paulo_800lit_mod
# A descrição identifica o EQUIPAMENTO PRINCIPAL do orçamento por palavra-chave,
# na mesma linha da detecção que já existe para capa/serviço. Prioridade:
#   piscina > trocador(BTU) > aquecedor(acoplado>modular>tradicional) > pressurizador > peças
# ---------------------------------------------------------------------------
def _primeiro_nome_cliente(nome_cliente):
    base = _norm(nome_cliente)
    tokens = re.sub(r'[^a-z0-9]+', ' ', base).split()
    return tokens[0] if tokens else "cliente"

def gerar_descricao_arquivo(df):
    """Código curto do equipamento principal, para compor o nome do arquivo."""
    nomes = _nomes_produtos(df)
    if not nomes:
        return "pecas"
    nn = [(_norm(n), n) for n in nomes]

    def achar(*termos):
        return [orig for (nrm, orig) in nn if any(t in nrm for t in termos)]

    suf_tipo = {"acoplado": "acopl", "modular": "mod", "tradicional": "trad"}

    # 1) Piscina (coletores/placas p/ piscina) -> volume em litros + tipo do coletor
    pisc = achar("piscina")
    if pisc:
        n = _extrair_numero(pisc[0], r'(\d+)\s*(?:litros?|lts?|l)\b') or _extrair_numero(pisc[0], r'(\d+)')
        tipo = detectar_tipo_instalacao(df) or "tradicional"
        suf = suf_tipo.get(tipo, "trad")
        return f"{n}lt_pisc_{suf}" if n else f"pisc_{suf}"

    # 2) Trocador / bomba de calor (BTU) -> nº de BTU, sem "lt"
    troc = achar("trocador", "bomba de calor", "btu")
    if troc:
        n = _extrair_numero(troc[0], r'(\d+)\s*btu') or _extrair_numero(troc[0], r'(\d+)')
        return f"{n}_btu" if n else "btu"

    # 3) Aquecedor residencial (acoplado > modular > tradicional)
    tipo = detectar_tipo_instalacao(df)
    if tipo:
        medida, _un = _medida_do_tipo(df, tipo)
        if tipo == "acoplado":
            return f"{medida}t_acopl" if medida else "acopl"
        return f"{medida}lit_{suf_tipo[tipo]}" if medida else suf_tipo[tipo]

    # 4) Pressurizador / bomba (que não seja de calor) -> modelo
    press = [o for (nrm, o) in nn if ("pressuriz" in nrm) or ("bomba" in nrm and "calor" not in nrm)]
    if press:
        n = _extrair_numero(press[0], r'(\d+)')
        return f"{n}_press" if n else "press"

    # 5) Nada reconhecido -> peças/acessórios
    return "pecas"

def gerar_nome_arquivo_orcamento(numero, nome_cliente, df):
    """Nome-base (sem extensão) do PDF do orçamento salvo no Drive."""
    return f"{numero}_{_primeiro_nome_cliente(nome_cliente)}_{gerar_descricao_arquivo(df)}"


# ---------------------------------------------------------------------------
# Prévia → Rascunho automático + histórico de versões (2026-08-25)
# Toda vez que uma prévia de PDF é gerada (ERP ou PWA), o cliente já vira um
# Rascunho automaticamente, e cada prévia gerada fica registrada em
# orcamento_versoes — sempre vinculada ao MESMO cliente (achado por telefone,
# e na falta pelo nome), pra nunca duplicar o mesmo cliente várias vezes na
# lista de rascunhos só porque foram geradas várias prévias/versões pra ele.
# ---------------------------------------------------------------------------
def _dt_rascunho(r):
    """Data/hora em que a prévia foi gerada, lida do próprio número do
    orçamento (RASC-YYMMDD-HHMM) — não existe coluna created_at em
    servicos_andamento. Usada pra ordenar a lista de rascunhos (mais recente
    primeiro) e pra mostrar a data pro Breno sem precisar de coluna nova."""
    m = re.search(r'(\d{6})-(\d{4})', str(r.get('numero_orcamento') or ''))
    if not m:
        return datetime.datetime.min
    try:
        return datetime.datetime.strptime(m.group(1) + m.group(2), '%y%m%d%H%M')
    except Exception:
        return datetime.datetime.min


def _achar_rascunho_existente(supabase, nome_cliente, telefone):
    """Procura um Rascunho já existente pro mesmo cliente — telefone primeiro
    (mais confiável), nome como fallback (case/acento-insensível)."""
    tel_digitos = re.sub(r'\D', '', str(telefone or ''))
    if tel_digitos:
        res = supabase.table("servicos_andamento").select("id, telefone_cliente").eq("status_projeto", "Rascunho").execute()
        for r in (res.data or []):
            if re.sub(r'\D', '', str(r.get('telefone_cliente') or '')) == tel_digitos:
                return r['id']
    nome_norm = _norm(nome_cliente)
    if nome_norm:
        res = supabase.table("servicos_andamento").select("id, nome_cliente").eq("status_projeto", "Rascunho").execute()
        for r in (res.data or []):
            if _norm(r.get('nome_cliente') or '') == nome_norm:
                return r['id']
    return None


def registrar_previa_como_rascunho(supabase, rascunho_id_atual, nome_cliente, telefone, endereco,
                                    df_itens, descricao_servico, valor_servico, descricao_outros,
                                    valor_outros, observacoes, numero_orcamento, valor_total,
                                    drive_link=None, nome_arquivo=None):
    """Chamado sempre que uma prévia de PDF é gerada. Se `rascunho_id_atual` já
    existir (sessão já estava editando um rascunho), reaproveita direto — senão
    procura um rascunho existente do mesmo cliente antes de criar um novo.
    Sempre grava a versão em orcamento_versoes. Retorna o id do rascunho
    (novo ou reaproveitado) pra quem chamou continuar usando."""
    snapshot_itens = []
    for _, r in df_itens.iterrows():
        qtd_r = float(r.get('Quantidade') or 0)
        if qtd_r <= 0:
            continue
        nome_item = _nome_produto_linha(r)
        snapshot_itens.append({
            "Item": nome_item, "Qtd": qtd_r,
            "Venda Un.": float(r.get('Venda (R$)') or 0), "Custo Un.": float(r.get('Custo (R$)') or 0),
            "Descrição": str(r.get('Descrição', '') or ''),
        })

    payload_rascunho = {
        "nome_cliente": nome_cliente, "telefone_cliente": telefone, "endereco_cliente": endereco,
        "servicos_adquiridos": descricao_servico, "valor_venda_total": valor_total,
        "status_projeto": "Rascunho", "detalhamento_itens": snapshot_itens,
        "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
        "dados_contrato": {
            "val_servico": valor_servico, "txt_outros": descricao_outros,
            "val_outros": valor_outros, "obs_pdf": observacoes,
        },
    }

    rascunho_id = rascunho_id_atual or _achar_rascunho_existente(supabase, nome_cliente, telefone)
    if rascunho_id:
        supabase.table("servicos_andamento").update(payload_rascunho).eq("id", rascunho_id).execute()
    else:
        payload_rascunho["numero_orcamento"] = f"RASC-{numero_orcamento}"
        res = supabase.table("servicos_andamento").insert(payload_rascunho).execute()
        rascunho_id = res.data[0]['id']

    supabase.table("orcamento_versoes").insert({
        "servico_id": rascunho_id, "numero_orcamento": numero_orcamento, "valor_venda_total": valor_total,
        "detalhamento_itens": snapshot_itens, "descricao_servico": descricao_servico, "valor_servico": valor_servico,
        "descricao_outros": descricao_outros, "valor_outros": valor_outros, "observacoes": observacoes,
        "drive_link": drive_link, "nome_arquivo": nome_arquivo,
    }).execute()

    return rascunho_id


# ---------------------------------------------------------------------------
# Parte 3: Modal "Cálculo de Custos" (Lucro Líquido detalhado)
# ---------------------------------------------------------------------------
def _ler_taxas_cadastradas():
    """Lê o catálogo de taxas e retorna (taxa_nf%, opcoes_cartao, dict_taxas).

    - taxa_nf: % do item que contém "NF"/"NOTA FISCAL" (padrão 6%).
    - opcoes_cartao / dict_taxas: demais itens (parcelamentos de maquininha).
    Mesma leitura usada na aba Orçamento Rápido, para manter consistência.
    """
    taxa_nf = 6.0
    opcoes_cartao = ["Nenhum / Dinheiro / PIX"]
    dict_taxas = {"Nenhum / Dinheiro / PIX": 0.0}
    db_taxas = st.session_state.get('db_taxas')
    if db_taxas is not None and not db_taxas.empty:
        for _, t in db_taxas.iterrows():
            item_nome = str(t.get('Item', '')).strip()
            up = item_nome.upper()
            try:
                taxa_val = float(t.get('Taxa (%)', 0.0))
            except Exception:
                taxa_val = 0.0
            if "NF" in up or "NOTA FISCAL" in up:
                taxa_nf = taxa_val
            elif item_nome:
                opcoes_cartao.append(item_nome)
                dict_taxas[item_nome] = taxa_val
    return taxa_nf, opcoes_cartao, dict_taxas


@st.dialog("🧮 Cálculo de Custos — Lucro Líquido", width="large")
def _modal_calculo_custos(dados, limpar_func):
    st.caption("Valores puxados do orçamento e taxas cadastradas no sistema. "
               "Todos os campos são editáveis antes de confirmar.")

    # ---------- 1. Valores do orçamento (auto, editáveis) ----------
    st.markdown("##### 💵 Valores do Orçamento")
    c1, c2 = st.columns(2)
    venda_produtos = c1.number_input("Venda dos Produtos (R$)", min_value=0.0, format="%.2f", key="cc_venda_prod")
    custo_produtos = c2.number_input("Custo dos Produtos (R$)", min_value=0.0, format="%.2f", key="cc_custo_prod")
    c3, c4 = st.columns(2)
    venda_instalacao = c3.number_input("Venda Instalação / Serviço (R$)", min_value=0.0, format="%.2f", key="cc_venda_serv")
    custo_instalacao = c4.number_input("Custo Instalação / Serviço (R$)", min_value=0.0, format="%.2f", key="cc_custo_serv")
    c5, c6 = st.columns(2)
    venda_outros = c5.number_input("Venda Outros / Terceiros (R$)", min_value=0.0, format="%.2f", key="cc_venda_outros")
    custo_outros = c6.number_input("Custo Outros / Terceiros (R$)", min_value=0.0, format="%.2f", key="cc_custo_outros")

    # ---------- 2. Impostos, taxas e condições ----------
    st.markdown("##### 🧾 Impostos, Taxas e Condições")
    taxa_nf_val, opcoes_cartao, dict_taxas = _ler_taxas_cadastradas()

    t1, t2 = st.columns(2)
    emite_nf = t1.radio(f"Emitir Nota Fiscal? (imposto {taxa_nf_val:.1f}%)", ["Não", "Sim"], horizontal=True, key="cc_nf")
    sel_cartao = t2.selectbox("Pagamento no Cartão (maquininha)", opcoes_cartao, key="cc_cartao")
    venda_bruta = venda_produtos + venda_instalacao + venda_outros

    t3, t4 = st.columns(2)
    comissao_pct = t3.number_input("Comissão (%)", min_value=0.0, format="%.2f", key="cc_comissao")
    modo_desconto = t4.radio("Desconto em", ["R$", "%"], horizontal=True, key="cc_desconto_modo")
    if modo_desconto == "%":
        desconto_pct = t4.number_input("Desconto concedido (%)", min_value=0.0, max_value=100.0, format="%.2f", key="cc_desconto_pct")
        desconto = venda_bruta * (desconto_pct / 100.0)
        t4.caption(f"= {utils.to_br_currency(desconto)}")
    else:
        desconto = t4.number_input("Desconto concedido (R$)", min_value=0.0, format="%.2f", key="cc_desconto")
        desconto_pct = (desconto / venda_bruta * 100.0) if venda_bruta > 0 else 0.0
        t4.caption(f"= {desconto_pct:.2f}% da receita bruta")

    # ---------- 3. Cálculos ----------
    venda_liquida = max(venda_bruta - desconto, 0.0)

    taxa_cartao_pct = dict_taxas.get(sel_cartao, 0.0)
    custo_nf = venda_liquida * (taxa_nf_val / 100.0) if emite_nf == "Sim" else 0.0
    custo_cartao = venda_liquida * (taxa_cartao_pct / 100.0)
    custo_comissao = venda_liquida * (comissao_pct / 100.0)

    custo_fixo = custo_produtos + custo_instalacao + custo_outros
    custo_variavel = custo_nf + custo_cartao + custo_comissao
    custo_total = custo_fixo + custo_variavel
    lucro_liquido = venda_liquida - custo_total
    margem = (lucro_liquido / venda_liquida * 100.0) if venda_liquida > 0 else 0.0

    # ---------- 4. Detalhamento ----------
    def _row(lbl, val, sinal="−", cor="#cc0000"):
        return (f"<div style='display:flex;justify-content:space-between;padding:2px 0;'>"
                f"<span>{lbl}</span><span style='color:{cor};'>{sinal} {utils.to_br_currency(val)}</span></div>")

    linhas = [f"<div style='display:flex;justify-content:space-between;padding:2px 0;'>"
              f"<span><b>Receita Bruta</b></span><span><b>{utils.to_br_currency(venda_bruta)}</b></span></div>"]
    if desconto > 0:
        linhas.append(_row(f"Desconto concedido ({desconto_pct:.1f}%)", desconto))
        linhas.append(f"<div style='display:flex;justify-content:space-between;padding:2px 0;border-top:1px dashed #999;'>"
                      f"<span><b>Receita Líquida</b></span><span><b>{utils.to_br_currency(venda_liquida)}</b></span></div>")
    linhas.append(_row("Custo dos Produtos", custo_produtos))
    if custo_instalacao > 0:
        linhas.append(_row("Custo da Instalação", custo_instalacao))
    if custo_outros > 0:
        linhas.append(_row("Custo Outros / Terceiros", custo_outros))
    if custo_nf > 0:
        linhas.append(_row(f"Imposto NF ({taxa_nf_val:.1f}%)", custo_nf))
    if custo_cartao > 0:
        linhas.append(_row(f"Taxa Maquininha ({taxa_cartao_pct:.2f}%)", custo_cartao))
    if custo_comissao > 0:
        linhas.append(_row(f"Comissão ({comissao_pct:.2f}%)", custo_comissao))

    st.markdown(
        "<div style='border:1px solid rgba(128,128,128,.35);border-radius:8px;padding:12px 16px;font-size:14px;'>"
        + "".join(linhas) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Custo Total Acumulado", utils.to_br_currency(custo_total))
    m2.metric("Venda Líquida", utils.to_br_currency(venda_liquida))
    m3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_liquido), delta=f"{margem:.1f}% margem real")

    # ---------- 5. Ações finais ----------
    breakdown = {
        "origem": "calculo_custos",
        "venda_produtos": venda_produtos, "custo_produtos": custo_produtos,
        "venda_instalacao": venda_instalacao, "custo_instalacao": custo_instalacao,
        "venda_outros": venda_outros, "custo_outros": custo_outros,
        "nf": emite_nf, "taxa_nf": taxa_nf_val,
        "cartao": sel_cartao, "taxa_cartao": taxa_cartao_pct,
        "comissao_pct": comissao_pct,
        "desconto": desconto, "desconto_pct": desconto_pct, "desconto_modo": modo_desconto,
        "venda_bruta": venda_bruta, "venda_liquida": venda_liquida,
        "custo_fixo": custo_fixo, "custo_variavel": custo_variavel,
        "custo_total": custo_total, "lucro_liquido": lucro_liquido, "margem": margem,
    }

    def _salvar(status, rotulo):
        if not str(dados.get('nome_cliente', '')).strip():
            st.error("⚠️ Preencha o nome do cliente no orçamento antes de salvar.")
            return
        try:
            payload = {
                "nome_cliente": dados['nome_cliente'],
                "telefone_cliente": dados['telefone'],
                "endereco_cliente": dados.get('endereco', ''),
                "produtos_adquiridos": dados['produtos_texto'],
                "servicos_adquiridos": dados['servicos_texto'],
                "valor_venda_total": venda_liquida,
                "lucro_estimado": lucro_liquido,
                "status_projeto": status,
                "detalhamento_itens": dados['snapshot_itens'],
                "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                "dados_contrato": breakdown,
                # Colunas que o painel de Serviços em Andamento lê para JÁ vir tudo
                # preenchido ao migrar (NF, cartão, comissão, serviço e outros).
                # Base = venda_liquida = valor_venda_total, então o painel recalcula
                # as mesmas % e chega exatamente nos mesmos valores.
                "custo_impostos": custo_nf,
                "custo_cartao": custo_cartao,
                "custo_comissao": custo_comissao,
                "custo_terceirizados": custo_instalacao,
                "custo_adicional_materiais": custo_outros,
            }
            if st.session_state.get('rascunho_id'):
                st.session_state.supabase.table("servicos_andamento").update(payload).eq('id', st.session_state.rascunho_id).execute()
            else:
                payload["numero_orcamento"] = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
                st.session_state.supabase.table("servicos_andamento").insert(payload).execute()

            st.session_state['calc_custos_msg'] = (
                f"✅ {rotulo} — Lucro líquido {utils.to_br_currency(lucro_liquido)} "
                f"({margem:.1f}%)."
            )
            st.session_state.pop('calc_custos_dados', None)
            limpar_func()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    st.divider()
    b1, b2, b3 = st.columns(3)
    if b1.button("✅ Custos → Serviços em Andamento", use_container_width=True, type="primary"):
        _salvar("Em Andamento", "Enviado para Serviços em Andamento")
    if b2.button("📁 Arquivar como Orçamento", use_container_width=True):
        _salvar("Orçamento Enviado", "Arquivado como Orçamento")
    if b3.button("🗑️ Descartar", use_container_width=True):
        st.session_state.pop('calc_custos_dados', None)
        st.rerun()


def renderizar(lista_nomes_produtos, limpar_func):
    deve_rerun = False
    cat_produtos = st.session_state.db_produtos

    # Mensagem de retorno do modal Cálculo de Custos (Parte 3)
    if st.session_state.get('calc_custos_msg'):
        st.success(st.session_state.pop('calc_custos_msg'))

    try:
        res_rascunhos = st.session_state.supabase.table('servicos_andamento').select('id, nome_cliente, telefone_cliente, valor_venda_total, numero_orcamento').eq('status_projeto', 'Rascunho').execute()
        rascunhos_db = res_rascunhos.data
        # Mais recente primeiro. Não existe coluna created_at nesta tabela —
        # o número do orçamento já carrega a data/hora de quando a prévia foi
        # gerada ("RASC-YYMMDD-HHMM"), então é dali que a ordem (e a data
        # mostrada pro Breno) vêm, sem precisar de coluna nova.
        rascunhos_db.sort(key=_dt_rascunho, reverse=True)
    except Exception:
        rascunhos_db = []

    if rascunhos_db or st.session_state.get('rascunho_id'):
        with st.expander("📂 Continuar Rascunho Salvo", expanded=True if st.session_state.get('rascunho_id') else False):
            if st.session_state.get('rascunho_id'):
                st.success("✏️ Você está editando um rascunho em andamento.")
                if st.button("❌ Fechar Rascunho e Iniciar Novo Orçamento", use_container_width=True):
                    limpar_func()
                    deve_rerun = True
            else:
                busca_rasc = st.text_input("🔍 Buscar cliente...", key="busca_rascunho_orc", placeholder="Nome, telefone ou nº do orçamento")
                rascunhos_filtrados = [
                    r for r in rascunhos_db
                    if utils.bate_busca(busca_rasc, r.get('nome_cliente', ''), r.get('telefone_cliente', ''), r.get('numero_orcamento', ''))
                ] if busca_rasc.strip() else rascunhos_db

                c_sel, c_btn_load, c_btn_del = st.columns([3, 1, 1])
                def _rotulo_rascunho(r):
                    dt = _dt_rascunho(r)
                    data_txt = dt.strftime('%d/%m %H:%M') if dt != datetime.datetime.min else "sem data"
                    return f"{r['nome_cliente']} (R$ {r.get('valor_venda_total', 0):.2f}) — {data_txt} - ID: {r['id']}"
                opcoes_rascunhos = {_rotulo_rascunho(r): r['id'] for r in rascunhos_filtrados}
                if not opcoes_rascunhos:
                    st.caption("Nenhum rascunho encontrado com esse nome.")
                rasc_selecionado = c_sel.selectbox("Selecione um rascunho (mais recentes primeiro):", list(opcoes_rascunhos.keys()), label_visibility="collapsed")

                if c_btn_load.button("📥 Carregar", use_container_width=True, disabled=not opcoes_rascunhos):
                    id_r = opcoes_rascunhos[rasc_selecionado]
                    res_full = st.session_state.supabase.table('servicos_andamento').select('*').eq('id', id_r).execute()
                    if res_full.data:
                        r_data = res_full.data[0]
                        st.session_state.rascunho_id = r_data['id']
                        st.session_state.input_nome_cliente = r_data.get('nome_cliente', '')
                        st.session_state.input_whatsapp = r_data.get('telefone_cliente', '')
                        st.session_state.input_endereco_cliente = r_data.get('endereco_cliente', '') or ''
                        st.session_state.txt_servico = r_data.get('servicos_adquiridos', '')
                        
                        d_ct = r_data.get('dados_contrato') or {}
                        st.session_state.val_servico = float(d_ct.get('val_servico', 0.0))
                        st.session_state.txt_outros = d_ct.get('txt_outros', '')
                        st.session_state.val_outros = float(d_ct.get('val_outros', 0.0))
                        st.session_state.input_obs_pdf = d_ct.get('obs_pdf', 'Material Hidráulico não incluído na proposta')

                        itens = r_data.get('detalhamento_itens', [])
                        novo_df = []
                        for it in itens:
                            v_un = float(it.get('Venda Un.', 0.0))
                            qtd = float(it.get('Qtd', 0))
                            
                            c_un = 0.0
                            p_nome = it.get('Item', '')
                            p_manual = ""
                            
                            if p_nome and p_nome not in lista_nomes_produtos and p_nome != "OUTRO":
                                p_manual = p_nome
                                p_nome = "OUTRO"
                            elif p_nome:
                                match_c = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == p_nome]
                                if not match_c.empty:
                                    c_un = float(match_c.get('Custo (R$)', pd.Series([0.0])).values[0])

                            novo_df.append({
                                "Produto da Base": p_nome,
                                "Produto Manual": p_manual,
                                "Descrição": it.get('Descrição', ''),
                                "Quantidade": qtd,
                                "Custo (R$)": c_un,
                                "Venda (R$)": v_un,
                                "Custo Total": qtd * c_un,
                                "Venda Total": qtd * v_un
                            })
                            
                        while len(novo_df) < 5:
                            novo_df.append({"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0})
                        
                        st.session_state.df_orc = pd.DataFrame(novo_df)
                        st.session_state.df_orc_prev = st.session_state.df_orc.copy()
                        if "editor_orc_base" in st.session_state: 
                            del st.session_state["editor_orc_base"]
                        deve_rerun = True

                if c_btn_del.button("🗑️ Excluir", use_container_width=True, disabled=not opcoes_rascunhos):
                    id_r = opcoes_rascunhos[rasc_selecionado]
                    st.session_state.supabase.table('servicos_andamento').delete().eq('id', id_r).execute()
                    st.success("✅ Rascunho excluído permanentemente.")
                    deve_rerun = True

    # Automação por equipamentos (Partes 1 e 2): quando a seleção de equipamentos
    # muda, sugere o modelo de capa e o serviço/valor correspondentes. Ambos
    # continuam totalmente editáveis; só são reajustados quando a seleção de
    # produtos volta a mudar (mudança de quantidade não dispara).
    df_atual = st.session_state.get('df_orc')
    assinatura_atual = _assinatura_produtos(df_atual)
    if 'auto_equip_assinatura' not in st.session_state:
        st.session_state.auto_equip_assinatura = assinatura_atual
    elif assinatura_atual != st.session_state.auto_equip_assinatura:
        st.session_state.auto_equip_assinatura = assinatura_atual

        # Parte 1: capa
        capa_sugerida = detectar_capa_por_produtos(df_atual)
        if capa_sugerida:
            st.session_state.input_modelo_capa = capa_sugerida

        # Parte 2: serviço + valor (do catálogo de Serviços)
        st.session_state.servico_auto_aviso = ""
        sug = sugerir_servico_por_produtos(df_atual, st.session_state.get('db_servicos'))
        if sug and sug["item_catalogo"]:
            # Achou no catálogo: seleciona o serviço; o handler do selectbox
            # abaixo preenche descrição e valor a partir do catálogo.
            st.session_state.sel_servico_base = sug["item_catalogo"]
        elif sug and sug["medida"] is not None:
            st.session_state.servico_auto_aviso = (
                f"⚠️ Verifique o campo **Serviços**: identifiquei "
                f"**{sug['nome_sugerido']}**, mas não encontrei um serviço "
                f"correspondente no catálogo (Configurações → Serviços). "
                f"Selecione ou preencha manualmente."
            )
        elif sug:
            st.session_state.servico_auto_aviso = (
                f"⚠️ Verifique o campo **Serviços**: identifiquei uma instalação "
                f"**{sug['tipo'].upper()}**, mas não consegui ler a medida "
                f"({'nº de tubos' if sug['unidade'] == 'tubos' else 'litros do Boiler'}). "
                f"Selecione ou preencha manualmente."
            )

    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        col1, col2 = st.columns(2)

        nome_cliente = col1.text_input("Nome do Cliente", key="input_nome_cliente")
        whatsapp = col2.text_input("WhatsApp", placeholder="(31) 99715-1596", key="input_whatsapp")
        endereco_cliente = st.text_input("Endereço (opcional)", placeholder="Rua, número, bairro, cidade - UF", key="input_endereco_cliente")

        # Default inicial via session_state (em vez de index=) para conviver com a
        # automação da Parte 1 sem warning do Streamlit.
        st.session_state.setdefault("input_modelo_capa", "Aquecedor Solar a Vácuo Acoplado")
        modelo_capa = st.selectbox("Modelo para Capa", [
            "Aquecedor Solar Tradicional",
            "Aquecedor Solar a Vácuo Acoplado",
            "Aquecedor Solar Modular",
            "Aquecedor de Piscina - Tradicional",
            "Aquecedor de Piscina - Trocador de Calor",
            "Sistema de Pressurização"
        ], key="input_modelo_capa")

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        # Um único controle (antes eram dois: "Detalhar valor de cada item" +
        # "Mostrar Preços Unitários", o segundo só liberado se o primeiro
        # estivesse marcado — redundante e confuso). Desmarcado é o padrão:
        # o PDF sai só com quantidade, sem nenhum valor por item. Marcado,
        # mostra valor unitário E subtotal de cada item.
        detalhar_itens_pdf = st.checkbox("Detalhar valor de cada item no PDF?", value=False,
                                          help="Desmarcado (padrão): o PDF mostra só o subtotal de Equipamentos, sem preço por item. Marque pra listar o valor unitário e o subtotal de cada peça.")
        mostrar_precos_unitarios = detalhar_itens_pdf
        
        if 'df_orc' not in st.session_state:
            linhas_iniciais = []
            for _ in range(5):
                linhas_iniciais.append({
                    "Produto da Base": "", 
                    "Produto Manual": "", 
                    "Descrição": "", 
                    "Quantidade": 0, 
                    "Custo (R$)": 0.0, 
                    "Venda (R$)": 0.0, 
                    "Custo Total": 0.0, 
                    "Venda Total": 0.0
                })
            st.session_state.df_orc = pd.DataFrame(linhas_iniciais)
        
        if 'df_orc_prev' not in st.session_state:
            st.session_state.df_orc_prev = st.session_state.df_orc.copy()
        
        configuracao_colunas = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_nomes_produtos + ["OUTRO"], width="medium"), 
            "Produto Manual": st.column_config.TextColumn("Nome Manual", width="medium"),
            "Descrição": st.column_config.TextColumn("Detalhes / Garantia"), 
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, step=1, width="small"),
            "Custo (R$)": st.column_config.NumberColumn("Custo Unt.", format="R$ %.2f", width="small"),
            "Venda (R$)": st.column_config.NumberColumn("Venda Unt.", format="R$ %.2f", width="small"),
            "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %.2f", disabled=True, width="small"),
            "Venda Total": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True, width="small")
        }
        
        sequencia_colunas = ["Produto da Base", "Produto Manual", "Quantidade", "Custo (R$)", "Venda (R$)", "Custo Total", "Venda Total"]
        
        df_editavel = st.data_editor(
            st.session_state.df_orc, 
            column_config=configuracao_colunas, 
            column_order=sequencia_colunas,
            num_rows="dynamic", 
            use_container_width=True, 
            key="editor_orc_base"
        )
        df_editavel = df_editavel.reset_index(drop=True)
        
        # Só a escolha de um PRODUTO no selectbox obriga a redesenhar a tela: é
        # quando o sistema precisa trazer preço e descrição do catálogo, dados
        # que o usuário não digitou e portanto ainda não estão na tela.
        #
        # Recalcular Custo Total / Venda Total NÃO entra aqui de propósito. Eles
        # são derivados (qtd × preço) e antes disparavam um redesenho a cada
        # tecla digitada — e como o redesenho descartava o estado do editor, o
        # que estava sendo preenchido se perdia. Agora eles são só recalculados
        # em memória; o subtotal logo abaixo já sai correto, e a coluna Total da
        # linha se acerta na próxima interação.
        produto_trocado = False

        for i in range(len(df_editavel)):
            produto_atual = str(df_editavel.at[i, 'Produto da Base']).strip()
            if produto_atual.lower() in ['nan', 'none', '']: 
                produto_atual = ""
            
            produto_anterior = ""
            if i < len(st.session_state.df_orc_prev):
                produto_anterior = str(st.session_state.df_orc_prev.at[i, 'Produto da Base']).strip()
                if produto_anterior.lower() in ['nan', 'none', '']: 
                    produto_anterior = ""

            df_editavel.at[i, 'Produto da Base'] = produto_atual

            if produto_atual != produto_anterior and produto_atual != "" and produto_atual != "OUTRO":
                match_base = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == produto_atual]
                
                if not match_base.empty:
                    val_venda = match_base['Venda (R$)'].values[0]
                    val_custo = match_base.get('Custo (R$)', pd.Series([0.0])).values[0]
                    desc_base = match_base['Descrição'].values[0]
                    
                    try: preco_novo = float(val_venda)
                    except Exception: preco_novo = 0.0
                        
                    try: custo_novo = float(val_custo)
                    except Exception: custo_novo = 0.0
                        
                    df_editavel.at[i, 'Venda (R$)'] = preco_novo
                    df_editavel.at[i, 'Custo (R$)'] = custo_novo
                    df_editavel.at[i, 'Descrição'] = str(desc_base) if pd.notna(desc_base) and str(desc_base).lower() != 'nan' else ""
                    
                    if pd.isna(df_editavel.at[i, 'Quantidade']) or float(df_editavel.at[i, 'Quantidade']) <= 0:
                        df_editavel.at[i, 'Quantidade'] = 1

                    produto_trocado = True

            qtd = utils.safe_float(df_editavel.at[i, 'Quantidade'])
            preco = utils.safe_float(df_editavel.at[i, 'Venda (R$)'])
            custo_un = utils.safe_float(df_editavel.at[i, 'Custo (R$)'])

            df_editavel.at[i, 'Quantidade'] = qtd
            df_editavel.at[i, 'Venda (R$)'] = preco
            df_editavel.at[i, 'Custo (R$)'] = custo_un
            df_editavel.at[i, 'Venda Total'] = qtd * preco
            df_editavel.at[i, 'Custo Total'] = qtd * custo_un

        # Guarda o estado a cada passagem (sem redesenhar): é o que permite
        # comparar o produto da próxima vez e é o que os botões de PDF/salvar
        # leem depois.
        st.session_state.df_orc = df_editavel
        st.session_state.df_orc_prev = df_editavel.copy()

        if produto_trocado:
            # Aqui o redesenho é necessário e esperado — o preço acabou de vir
            # do catálogo e precisa aparecer. A chave do editor é preservada de
            # propósito: apagá-la descartaria o que o usuário digitou nas outras
            # células antes de escolher o produto.
            deve_rerun = True

        subtotal_equipamentos = pd.to_numeric(df_editavel['Venda Total'], errors='coerce').fillna(0).sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(subtotal_equipamentos)}]")
        
        mostrar_lucro = st.toggle("Exibir Custos, Margem e Lucro Estimado", value=False)
        if mostrar_lucro:
            custo_total_produtos = pd.to_numeric(df_editavel["Custo Total"], errors='coerce').fillna(0).sum()
            venda_total_produtos = subtotal_equipamentos
            lucro_total_produtos = venda_total_produtos - custo_total_produtos
            
            st.markdown(f"""
                <div style='display: flex; justify-content: flex-start; gap: 25px; margin-top: 10px; margin-bottom: 5px;'>
                    <span style='color: #cc0000; font-size: 15px;'><b>Custo Total Produtos:</b> {utils.to_br_currency(custo_total_produtos)}</span>
                    <span style='color: #006600; font-size: 15px;'><b>Lucro Total Produtos:</b> {utils.to_br_currency(lucro_total_produtos)}</span>
                </div>
            """, unsafe_allow_html=True)
            
            margem_equip = (lucro_total_produtos / custo_total_produtos * 100) if custo_total_produtos > 0 else (100.0 if lucro_total_produtos > 0 else 0.0)
            
            html_lucro = f"""
            <div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px; border: 1px solid #006600; margin-top: 10px; margin-bottom: 5px;'>
                <span style='color: #006600; font-weight: bold; font-size: 16px;'>💸 Lucro Projetado: {utils.to_br_currency(lucro_total_produtos)} ({margem_equip:.1f}%)</span><br>
                <small style='color: #444;'><i>(Calculado apenas sobre o custo total acumulado dos equipamentos)</i></small>
            </div>
            """
            st.markdown(html_lucro, unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços")
        
        lista_servicos = st.session_state.db_servicos['Item'].dropna().tolist() if not st.session_state.db_servicos.empty else []

        # key="sel_servico_base": permite que a automação (Parte 2) pré-selecione o
        # serviço detectado pelos equipamentos. O usuário pode trocar livremente.
        servico_atual = st.selectbox("Selecionar Serviço da Base:", [""] + lista_servicos + ["Manual"], key="sel_servico_base")

        if servico_atual != st.session_state.servico_selecionado_anterior:
            st.session_state.servico_selecionado_anterior = servico_atual
            st.session_state.servico_auto_aviso = ""  # qualquer troca resolve o aviso
            if servico_atual == "Manual":
                st.session_state.txt_servico = ""
                st.session_state.val_servico = 0.0
            elif servico_atual != "":
                linha_base = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==servico_atual]
                descricao_base = str(linha_base['Descrição'].values[0]) if pd.notna(linha_base['Descrição'].values[0]) else ""
                st.session_state.txt_servico = f"{servico_atual}\n{descricao_base}".strip()
                st.session_state.val_servico = float(linha_base['Venda (R$)'].values[0]) if pd.notna(linha_base['Venda (R$)'].values[0]) else 0.0
            else:
                st.session_state.txt_servico = ""
                st.session_state.val_servico = 0.0

        # Aviso da automação (Parte 2): só aparece quando um tipo foi identificado
        # mas não há serviço correspondente/medida, e o campo ainda está vazio.
        if st.session_state.get('servico_auto_aviso') and not str(st.session_state.get('txt_servico', '')).strip():
            st.warning(st.session_state.servico_auto_aviso)

        descricao_final_servico = st.text_area("Descrição detalhada do Serviço:", key="txt_servico", height=100)
        valor_final_servico = st.number_input("Valor do Serviço (R$):", key="val_servico", format="%.2f")

    with st.container(border=True):
        st.subheader("🤝 3. Outros / Terceiros")

        lista_outros = st.session_state.db_outros['Item'].dropna().tolist() if not st.session_state.db_outros.empty else []
        
        outros_atual = st.selectbox("Adicionar Outros / Terceiros:", [""] + lista_outros + ["Manual"])
        
        if outros_atual != st.session_state.outros_selecionado_anterior:
            st.session_state.outros_selecionado_anterior = outros_atual
            if outros_atual == "Manual":
                st.session_state.txt_outros = ""
                st.session_state.val_outros = 0.0
            elif outros_atual != "":
                linha_base_o = st.session_state.db_outros.loc[st.session_state.db_outros['Item']==outros_atual]
                descricao_base_o = str(linha_base_o['Descrição'].values[0]) if pd.notna(linha_base_o['Descrição'].values[0]) else ""
                st.session_state.txt_outros = f"{outros_atual}\n{descricao_base_o}".strip()
                st.session_state.val_outros = float(linha_base_o['Venda (R$)'].values[0]) if pd.notna(linha_base_o['Venda (R$)'].values[0]) else 0.0
            else:
                st.session_state.txt_outros = ""
                st.session_state.val_outros = 0.0

        descricao_final_outros = st.text_area("Descrição de Diversos:", key="txt_outros", height=80)
        valor_final_outros = st.number_input("Valor Adicional (R$):", key="val_outros", format="%.2f")

    total_investimento = subtotal_equipamentos + valor_final_servico + valor_final_outros
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_investimento)}</h3>", unsafe_allow_html=True)
    
    if "input_obs_pdf" not in st.session_state: 
        st.session_state.input_obs_pdf = "Material Hidráulico não incluído na proposta"
    
    obs_pdf = st.text_area("Observações no PDF:", key="input_obs_pdf")

    def formatar_telefone(tel):
        numeros = ''.join(filter(str.isdigit, tel))
        if len(numeros) == 11:
            return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
        return tel

    # ---------------------- Parte 3: Cálculo de Custos ----------------------
    st.markdown("<hr style='margin-top:6px;margin-bottom:8px;'>", unsafe_allow_html=True)
    if st.button("🧮 CÁLCULO DE CUSTOS — LUCRO LÍQUIDO DETALHADO", use_container_width=True):
        # Monta o snapshot dos itens e os totais no momento da abertura
        snapshot_itens = []
        lista_prods_texto = []
        for _, r in df_editavel.iterrows():
            qtd_r = float(r['Quantidade']) if pd.notna(r['Quantidade']) else 0.0
            if qtd_r > 0:
                p_base = str(r.get('Produto da Base', '')).strip()
                p_man = str(r.get('Produto Manual', '')).strip()
                nome_item = p_base if p_base not in ["", "OUTRO", "None"] else p_man
                snapshot_itens.append({
                    "Item": nome_item,
                    "Qtd": qtd_r,
                    "Venda Un.": float(r['Venda (R$)']) if pd.notna(r['Venda (R$)']) else 0.0,
                    "Custo Un.": float(r['Custo (R$)']) if pd.notna(r['Custo (R$)']) else 0.0,
                    "Descrição": str(r.get('Descrição', '')),
                })
                lista_prods_texto.append(f"{int(qtd_r)}x {nome_item}")

        custo_produtos_open = float(pd.to_numeric(df_editavel["Custo Total"], errors='coerce').fillna(0).sum())

        st.session_state.calc_custos_dados = {
            "nome_cliente": nome_cliente,
            "telefone": formatar_telefone(whatsapp),
            "endereco": endereco_cliente,
            "produtos_texto": ", ".join(lista_prods_texto),
            "servicos_texto": descricao_final_servico,
            "venda_produtos": float(subtotal_equipamentos),
            "custo_produtos": custo_produtos_open,
            "valor_servico": float(valor_final_servico),
            "valor_outros": float(valor_final_outros),
            "snapshot_itens": snapshot_itens,
        }

        # Semeia os campos do modal (padrão = valores puxados). Feito só na
        # abertura, para que edições dentro do modal persistam nos reruns internos
        # e um novo clique recomece dos valores atuais do orçamento.
        d = st.session_state.calc_custos_dados
        st.session_state.cc_venda_prod = d["venda_produtos"]
        st.session_state.cc_custo_prod = d["custo_produtos"]
        st.session_state.cc_venda_serv = d["valor_servico"]
        st.session_state.cc_custo_serv = d["valor_servico"]  # padrão: custo = venda da instalação
        st.session_state.cc_venda_outros = d["valor_outros"]
        st.session_state.cc_custo_outros = 0.0
        st.session_state.cc_nf = "Não"
        st.session_state.cc_cartao = "Nenhum / Dinheiro / PIX"
        st.session_state.cc_comissao = 0.0
        st.session_state.cc_desconto_modo = "R$"
        st.session_state.cc_desconto = 0.0
        st.session_state.cc_desconto_pct = 0.0

        _modal_calculo_custos(d, limpar_func)

    col_btn_previa, col_btn_rasc, col_btn_salvar = st.columns([1, 1.2, 1.2])
    
    with col_btn_previa:
        if st.button("👁️ GERAR PRÉVIA", use_container_width=True):
            if not nome_cliente: 
                st.warning("Preencha o nome do cliente!")
            else:
                tel_formatado = formatar_telefone(whatsapp)
                st.session_state['pdf_gerado'] = utils.gerar_pdf_orcamento(
                    nome_cliente, 
                    tel_formatado, 
                    modelo_capa, 
                    df_editavel, 
                    descricao_final_servico, 
                    valor_final_servico, 
                    descricao_final_outros, 
                    valor_final_outros, 
                    total_investimento,
                    obs_pdf,
                    mostrar_precos_unitarios,
                    detalhar_itens_pdf
                )
                st.session_state['nome_cliente_previa'] = nome_cliente

                # --- Salva o orçamento AUTOMATICAMENTE no Drive (pasta Orçamentos) ---
                # Número da proposta: gerado na 1ª prévia e reaproveitado, para o
                # nome do arquivo bater com o ORC-... salvo depois no sistema.
                if not st.session_state.get('num_proposta_atual'):
                    st.session_state['num_proposta_atual'] = datetime.datetime.now().strftime('%y%m%d-%H%M')
                numero_prop = st.session_state['num_proposta_atual']
                nome_base = gerar_nome_arquivo_orcamento(numero_prop, nome_cliente, df_editavel)
                fname = f"{nome_base}.pdf"
                try:
                    # "Salva um novo a cada clique": desambigua se o nome já existir.
                    if utils.drive_nome_existe(utils.DRIVE_FOLDER_ORCAMENTOS, fname):
                        _i = 2
                        while utils.drive_nome_existe(utils.DRIVE_FOLDER_ORCAMENTOS, f"{nome_base}_v{_i}.pdf"):
                            _i += 1
                        fname = f"{nome_base}_v{_i}.pdf"
                    _ok_orc, _res_orc = utils.upload_to_drive_folder_id(
                        st.session_state['pdf_gerado'], fname, "application/pdf", utils.DRIVE_FOLDER_ORCAMENTOS)
                except Exception as _e_orc:
                    _ok_orc, _res_orc = False, str(_e_orc)
                if _ok_orc:
                    st.session_state['orc_drive_link'] = _res_orc
                    st.session_state['orc_drive_nome'] = fname
                    st.toast(f"☁️ Orçamento salvo no Drive como {fname}", icon="✅")
                else:
                    st.session_state['orc_drive_link'] = None
                    st.warning(f"Prévia gerada, mas o envio automático ao Drive falhou ({_res_orc}).")

                # Toda prévia já vira Rascunho automaticamente, agrupado no
                # MESMO cliente (por telefone/nome) — nunca duplica o cliente
                # na lista só por gerar mais de uma prévia/versão pra ele.
                try:
                    st.session_state.rascunho_id = registrar_previa_como_rascunho(
                        st.session_state.supabase, st.session_state.get('rascunho_id'),
                        nome_cliente, tel_formatado, endereco_cliente, df_editavel,
                        descricao_final_servico, valor_final_servico, descricao_final_outros,
                        valor_final_outros, obs_pdf, numero_prop, total_investimento,
                        drive_link=(f"https://drive.google.com/file/d/{_res_orc}/view" if _ok_orc else None),
                        nome_arquivo=fname,
                    )
                except Exception as _e_rasc:
                    st.warning(f"Prévia gerada, mas não deu pra registrar o rascunho automaticamente: {_e_rasc}")

        if st.session_state.get('orc_drive_link') and st.session_state.get('nome_cliente_previa') == nome_cliente:
            st.caption(f"☁️ Salvo no Drive: **{st.session_state.get('orc_drive_nome','')}**  ·  "
                       f"[abrir](https://drive.google.com/file/d/{st.session_state['orc_drive_link']}/view)")
        
        if 'pdf_gerado' in st.session_state and st.session_state.get('nome_cliente_previa') == nome_cliente:
            st.download_button(
                "📥 BAIXAR RASCUNHO", 
                data=st.session_state['pdf_gerado'], 
                file_name=f"ORCAMENTO_{nome_cliente}.pdf", 
                mime="application/pdf", 
                use_container_width=True
            )

    with col_btn_rasc:
        if st.button("💾 SALVAR RASCUNHO", use_container_width=True):
            if not nome_cliente:
                st.warning("Preencha ao menos o nome do cliente para salvar o rascunho!")
            else:
                tel_formatado = formatar_telefone(whatsapp)
                snapshot_itens = []
                for _, r in df_editavel.iterrows():
                    if r['Quantidade'] > 0 or str(r.get('Produto da Base', '')) != "" or str(r.get('Produto Manual', '')) != "":
                        p_base = str(r.get('Produto da Base', '')).strip()
                        p_man = str(r.get('Produto Manual', '')).strip()
                        nome_item = p_base if p_base not in ["", "OUTRO", "None"] else p_man
                        
                        snapshot_itens.append({
                            "Item": nome_item,
                            "Qtd": r['Quantidade'],
                            "Custo Un.": r['Custo (R$)'],
                            "Venda Un.": r['Venda (R$)'],
                            "Descrição": r['Descrição']
                        })

                payload_rascunho = {
                    "nome_cliente": nome_cliente,
                    "telefone_cliente": tel_formatado,
                    "endereco_cliente": endereco_cliente,
                    "servicos_adquiridos": descricao_final_servico,
                    "valor_venda_total": total_investimento,
                    "status_projeto": "Rascunho",
                    "detalhamento_itens": snapshot_itens,
                    "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                    "dados_contrato": {
                        "val_servico": valor_final_servico,
                        "txt_outros": descricao_final_outros,
                        "val_outros": valor_final_outros,
                        "obs_pdf": obs_pdf
                    }
                }

                if st.session_state.get('rascunho_id'):
                    st.session_state.supabase.table("servicos_andamento").update(payload_rascunho).eq('id', st.session_state.rascunho_id).execute()
                    st.success("✅ Rascunho atualizado com sucesso!")
                else:
                    string_data = datetime.datetime.now().strftime('%y%m%d-%H%M')
                    payload_rascunho["numero_orcamento"] = f"RASC-{string_data}"
                    res = st.session_state.supabase.table("servicos_andamento").insert(payload_rascunho).execute()
                    st.session_state.rascunho_id = res.data[0]['id']
                    st.success("✅ Rascunho criado com sucesso!")

    with col_btn_salvar:
        if st.button("✅ SALVAR NO SISTEMA", type="primary", use_container_width=True):
            if not nome_cliente: 
                st.error("Preencha o nome do cliente!")
            else:
                string_data = st.session_state.get('num_proposta_atual') or datetime.datetime.now().strftime('%y%m%d-%H%M')
                numero_do_orcamento = f"ORC-{string_data}"
                try:
                    tel_formatado = formatar_telefone(whatsapp)
                    snapshot_itens = []
                    lista_prods_texto = []
                    
                    for _, r in df_editavel.iterrows():
                        if r['Quantidade'] > 0:
                            p_base = str(r.get('Produto da Base', '')).strip()
                            p_man = str(r.get('Produto Manual', '')).strip()
                            nome_item = p_base if p_base not in ["", "OUTRO", "None"] else p_man
                            
                            snapshot_itens.append({
                                "Item": nome_item, 
                                "Qtd": r['Quantidade'], 
                                "Venda Un.": r['Venda (R$)'], 
                                "Descrição": r['Descrição']
                            })
                            lista_prods_texto.append(f"{int(r['Quantidade'])}x {nome_item}")
                    
                    string_produtos = ", ".join(lista_prods_texto)
                    
                    payload_final = {
                        "numero_orcamento": numero_do_orcamento,
                        "nome_cliente": nome_cliente,
                        "telefone_cliente": tel_formatado,
                        "endereco_cliente": endereco_cliente,
                        "produtos_adquiridos": string_produtos,
                        "servicos_adquiridos": descricao_final_servico,
                        "valor_venda_total": total_investimento,
                        "status_projeto": "Orçamento Enviado",
                        "detalhamento_itens": snapshot_itens,
                        "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                        "dados_contrato": {}
                    }
                    
                    if st.session_state.get('rascunho_id'):
                        st.session_state.supabase.table("servicos_andamento").update(payload_final).eq('id', st.session_state.rascunho_id).execute()
                    else:
                        st.session_state.supabase.table("servicos_andamento").insert(payload_final).execute()
                    
                    st.success(f"✅ Orçamento {numero_do_orcamento} salvo com sucesso no banco de dados!")
                    limpar_func()
                    deve_rerun = True
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    return deve_rerun
