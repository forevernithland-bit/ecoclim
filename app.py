import streamlit as st
import pandas as pd
import numpy as np
import datetime

# Configuração da Página para Ocupar 100% do espaço
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- MÊS ATUAL AUTOMÁTICO ---
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
mes_atual_idx = datetime.datetime.now().month - 1
mes_atual_str = meses_pt[mes_atual_idx]

# Calcula qual o número da coluna (no HTML) corresponde ao mês atual.
# Coluna 1 = MESES. Janeiro = 2, Fevereiro = 3... Maio = 6.
coluna_css_idx = mes_atual_idx + 2

# --- CSS DEFINITIVO ---
st.markdown(f"""
    <style>
    /* Respiro no topo e aproveitamento máximo das laterais da tela */
    .block-container {{ padding-top: 3rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }}
    
    /* Zera os espaços apenas entre as tabelas */
    div.container-tabelas div.st-emotion-cache-1wivap2 {{ gap: 0rem !important; }}
    div.container-tabelas div[data-testid="stVerticalBlock"] {{ gap: 0px !important; }}
    
    /* Centraliza o texto nas células */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th {{ text-align: center !important; }}

    /* TRAVA DE TITÂNIO: Força todas as tabelas a terem a mesma estrutura */
    .stDataFrame table, .stDataEditor table {{
        table-layout: fixed !important;
        width: 100% !important;
    }}

    /* 
       FIM DA GAVETA: ESCONDER CABEÇALHOS VIA CSS DIRETO
       Esconde os elementos <thead> das tabelas 2, 3 e 4.
    */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead {{ display: none !important; }}
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead {{ display: none !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead {{ display: none !important; }}

    /* Tira o arredondamento para colar as tabelas perfeitamente retas */
    section.main div[data-testid="stDataEditor"] > div > div {{ border-radius: 0px !important; }}
    section.main div[data-testid="stDataFrame"] > div > div {{ border-radius: 0px !important; border-top: none !important; border-bottom: none !important; }}

    /* Remove a margem extra que fica ao esconder o thead */
    section.main div[data-testid="stDataFrame"] table {{ margin-top: 0px !important; }}

    /* 
       A MÁGICA DA COR VIA CSS: Pinta a coluna do mês atual em TODAS as tabelas! 
       Usamos nth-child para mirar na coluna certa baseada no mês em que estamos.
    */
    
    /* Pinta a coluna nas tabelas editáveis (1 e 3) e na tabela final (4) de cinza claro */
    section.main div[data-testid="stDataEditor"] td:nth-child({coluna_css_idx}), 
    section.main div[data-testid="stDataEditor"] th:nth-child({coluna_css_idx}),
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) td:nth-child({coluna_css_idx}) {{
        background-color: #E2E8F0 !important;
        color: black !important;
        font-weight: bold !important;
    }}

    /* Pinta a linha do Patrimônio Líquido (tabela 2, linha 1) na coluna do mês atual */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) tbody tr:nth-child(1) td:nth-child({coluna_css_idx}) {{
        background-color: #E6D9B1 !important; /* Amarelo escuro */
    }}
    
    /* Pinta a linha do Patrimônio Total (tabela 2, linha 2) na coluna do mês atual */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) tbody tr:nth-child(2) td:nth-child({coluna_css_idx}) {{
        background-color: #CC7A00 !important; /* Laranja escuro */
    }}

    /* Pinta as linhas de Variação (tabela 2, linhas 3 e 4) na coluna do mês atual */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) tbody tr:nth-child(3) td:nth-child({coluna_css_idx}),
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) tbody tr:nth-child(4) td:nth-child({coluna_css_idx}) {{
        background-color: #E2E8F0 !important; /* Cinza claro */
    }}

    /* Pinta a linha do Salário (tabela 4, linha 1) na coluna do mês atual */
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) tbody tr:nth-child(1) td:nth-child({coluna_css_idx}) {{
        background-color: #7FAFE0 !important; /* Azul escuro */
    }}

    /* Estilo dos Indicadores (Compactos) */
    div[data-testid="stMetricValue"] {{ font-size: 1.2rem !important; }}
    div[data-testid="stMetricLabel"] {{ font-size: 0.8rem !important; font-weight: bold !important; }}
    div[data-testid="stMetric"] {{
        background-color: #ffffff; padding: 8px 12px !important; border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; border: 1px solid #e0e0e0;
    }}
    .main {{ background-color: #f8f9fa; }}
    </style>
    """, unsafe_allow_html=True)

# --- MENU LATERAL ---
with st.sidebar:
    st.title("📈 Consorbens")
    menu = st.radio("Navegação", ["🏠 Dashboard Consolidado", "❄️ Ecoclim", "🏠 Airbnb", "📄 Documentos"])
    st.write("---")
    if st.button("🔄 Limpar Memória do App"):
        st.session_state.clear()
        st.rerun()

# --- CONFIGURAÇÃO DE DADOS ---
meses_base = ['dez/25'] + meses_pt
meses_view = meses_pt 

linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_patrimonio' not in st.session_state or 'MESES' not in st.session_state.df_patrimonio.columns:
    df_p = pd.DataFrame(0.0, index=range(len(linhas_patrimonio)), columns=meses_base)
    df_p.insert(0, 'MESES', linhas_patrimonio)
    st.session_state.df_patrimonio = df_p

if 'df_entradas' not in st.session_state or 'MESES' not in st.session_state.df_entradas.columns:
    df_e = pd.DataFrame(0.0, index=range(len(linhas_entradas)), columns=meses_base)
    df_e.insert(0, 'MESES', linhas_entradas)
    st.session_state.df_entradas = df_e

# =====================================================================
# TRAVA DE COLUNAS ÚNICA
# =====================================================================
col_config_master = {"MESES": st.column_config.TextColumn("MESES", width=210, disabled=True)}
for mes in meses_view:
    col_config_master[mes] = st.column_config.NumberColumn(mes, width=70)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO EDITÁVEL (Sem Styler do Pandas!)
    # ------------------------------------------------------------------
    df_view_patr = st.session_state.df_patrimonio[['MESES'] + meses_view]
    df_editado_view_patr = st.data_editor(df_view_patr, hide_index=True, column_config=col_config_master, use_container_width=True, height=280)
    
    for mes in meses_view:
        st.session_state.df_patrimonio[mes] = df_editado_view_patr[mes]
    
    df_num_patr = st.session_state.df_patrimonio.set_index('MESES')
    patrimonio_liquido = df_num_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_num_patr.loc['IMÓVEIS'] + df_num_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({'MESES': ['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio', '% var patrimônio']})
    for mes in meses_view:
        df_resultados_patr[mes] = [patrimonio_liquido[mes], patrimonio_total[mes], var_rs[mes], var_pct[mes]]

    # O Styler agora SÓ pinta as linhas base (Amarelo e Laranja). O CSS cuida do destaque do mês!
    def style_linhas_base_patrimonio(row):
        styles = []
        nome = row['MESES']
        for col in row.index:
            bg = 'white'
            fw = 'normal'
            if nome == 'PATRIMONIO LÍQUIDO': bg = '#FFF2CC'; fw = 'bold'
            elif nome == 'PATRIMONIO TOTAL': bg = '#FF9900'; fw = 'bold'
            elif nome == 'Var $ patrimonio': bg = '#FFF2CC'
            
            styles.append(f'background-color: {bg}; font-weight: {fw}; color: black; border-bottom: 1px solid #ccc;')
        return styles

    styled_df_patr = df_resultados_patr.style\
        .apply(style_linhas_base_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view}, subset=pd.IndexSlice[[0, 1, 2], meses_view])\
        .format(formatter={col: '{:.2f}%' for col in meses_view}, subset=pd.IndexSlice[[3], meses_view])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config_master, use_container_width=True, height=145)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS EDITÁVEL (Sem Styler do Pandas!)
    # ------------------------------------------------------------------
    df_view_ent = st.session_state.df_entradas[['MESES'] + meses_view]
    df_editado_view_ent = st.data_editor(df_view_ent, hide_index=True, column_config=col_config_master, use_container_width=True, height=170)
    
    for mes in meses_view:
        st.session_state.df_entradas[mes] = df_editado_view_ent[mes]
    
    df_num_ent = st.session_state.df_entradas.set_index('MESES')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'MESES': ['SALÁRIO MÊS:']})
    for mes in meses_view:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    # O Styler agora SÓ pinta a linha base (Azul). O CSS cuida do destaque do mês!
    def style_linha_base_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border-bottom: 1px solid #ccc;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_linha_base_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view})
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config_master, use_container_width=True, height=45)

    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # BLOCO 3: INDICADORES
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📊 Indicadores de Performance")
    
    meses_ativos = patrimonio_total[patrimonio_total > 0].shape[0]
    meses_ativos = meses_ativos if meses_ativos > 0 else 1 

    media_aplicacao = var_rs.sum() / meses_ativos
    soma_salarial = salario_mes.sum()
    media_salarial = soma_salarial / meses_ativos
    
    patr_atual = patrimonio_total.replace(0, np.nan).dropna().iloc[-1] if not patrimonio_total.replace(0, np.nan).dropna().empty else 0
    patr_inicial = patrimonio_total.iloc[0]
    avanco_patrimonial = patr_atual - patr_inicial
    
    col1, col2, col3 = st.columns(3)
    col1.metric("MÉDIA APLICAÇÃO MÊS", f"R$ {media_aplicacao:,.2f}")
    col2.metric("MÉDIA SALÁRIAL LÍQUIDA", f"R$ {media_salarial:,.2f}")
    col3.metric("SOMA SALÁRIAL ANUAL", f"R$ {soma_salarial:,.2f}")
    
    col4, col5 = st.columns(2)
    col4.metric("AVANÇO ANUAL DE APLICAÇÃO", "Em breve...")
    col5.metric("AVANÇO ANUAL PATRIMONIAL", f"R$ {avanco_patrimonial:,.2f}")

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
