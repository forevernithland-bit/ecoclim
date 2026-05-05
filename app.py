import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components
import datetime

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- MÊS ATUAL AUTOMÁTICO ---
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
mes_atual_idx = datetime.datetime.now().month - 1
mes_atual_str = meses_pt[mes_atual_idx]

# --- CSS: ALINHAMENTO, GAVETA E MÉTRICAS MENORES ---
st.markdown("""
    <style>
    /* Dá um respiro no topo */
    .block-container { padding-top: 3rem !important; }
    
    /* Zera os espaços apenas entre as tabelas */
    div.container-tabelas div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    div.container-tabelas div[data-testid="stVerticalBlock"] { gap: 0px !important; }
    
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; }
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] { background-color: white !important; }

    /* A MÁGICA DA GAVETA (-39px) */
    section.main div[data-testid="stDataEditor"]:nth-of-type(1) { z-index: 10 !important; position: relative !important; }
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) { z-index: 9 !important; position: relative !important; margin-top: -39px !important; }
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) { z-index: 8 !important; position: relative !important; margin-top: -39px !important; }
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) { z-index: 7 !important; position: relative !important; margin-top: -39px !important; }

    /* Tira o arredondamento para colar as tabelas */
    section.main div[data-testid="stDataEditor"] > div > div { border-radius: 0px !important; }
    section.main div[data-testid="stDataFrame"] > div > div { border-radius: 0px !important; border-top: none !important; }

    /* --- ESTILO DOS INDICADORES (MENORES E COMPACTOS) --- */
    div[data-testid="stMetricValue"] {
        font-size: 1.2rem !important; /* Tamanho do Número menor */
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem !important; /* Tamanho do Texto menor */
        font-weight: bold !important;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 8px 12px !important; /* Caixinhas mais finas */
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
        border: 1px solid #e0e0e0;
    }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- JAVASCRIPT: SCROLL SINCRONIZADO BLINDADO ---
components.html("""
    <script>
    const parentDoc = window.parent.document;
    let isSyncing = false;

    // Escuta QUALQUER scroll que acontecer na página
    parentDoc.addEventListener('scroll', function(e) {
        // Se quem está rolando for uma tabela (.dvn-scroller)
        if (e.target && e.target.classList && e.target.classList.contains('dvn-scroller')) {
            if (!isSyncing) {
                isSyncing = true;
                const scrollers = parentDoc.querySelectorAll('.dvn-scroller');
                scrollers.forEach(scroller => {
                    if (scroller !== e.target) {
                        scroller.scrollLeft = e.target.scrollLeft;
                    }
                });
                window.requestAnimationFrame(() => { isSyncing = false; });
            }
        }
    }, true); // O 'true' garante que pegamos o evento na fase de captura!
    </script>
""", height=0, width=0)

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
meses_view = meses_pt # Tira dez/25 da visão

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

# TRAVA DE COLUNAS
col_config_top = {"MESES": st.column_config.TextColumn("MESES", width=250, disabled=True)}
col_config_bot = {"MESES": st.column_config.TextColumn(" ", width=250, disabled=True)}
for mes in meses_view:
    col_config_top[mes] = st.column_config.NumberColumn(mes, width=100)
    col_config_bot[mes] = st.column_config.NumberColumn(" ", width=100)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # --- FUNÇÕES DE ESTILIZAÇÃO DO MÊS ATUAL ---
    
    # Função para destacar as colunas nas tabelas editáveis
    def destaque_mes_editavel(col):
        if col.name == mes_atual_str:
            return ['background-color: #E8F0FE;'] * len(col) # Cinza/Azul clarinho
        return [''] * len(col)

    # Função para resultados de patrimônio
    def style_patrimonio_resultado(row):
        styles = []
        nome = row['MESES']
        for col in row.index:
            bg = '#FFF2CC' # Padrão Amarelo claro
            fw = 'normal'
            if nome == 'PATRIMONIO LÍQUIDO': fw = 'bold'
            elif nome == 'PATRIMONIO TOTAL': bg = '#FF9900'; fw = 'bold' # Padrão Laranja
            
            # Se a coluna for o mês atual, escurece um pouco pra destacar
            if col == mes_atual_str:
                if bg == '#FFF2CC': bg = '#FFE699'
                elif bg == '#FF9900': bg = '#E68A00'
            
            styles.append(f'background-color: {bg}; font-weight: {fw}; color: black; border-bottom: 1px solid #ccc;')
        return styles

    # Função para resultados de Entradas
    def style_entradas_resultado(row):
        styles = []
        for col in row.index:
            bg = '#9BC2E6' # Padrão Azul claro
            if col == mes_atual_str: 
                bg = '#7FAFE0' # Azul um pouco mais intenso
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-bottom: 1px solid #ccc;')
        return styles

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO EDITÁVEL 
    # ------------------------------------------------------------------
    df_view_patr = st.session_state.df_patrimonio[['MESES'] + meses_view]
    # Aplica a cor do mês atual
    styled_view_patr = df_view_patr.style.apply(destaque_mes_editavel, axis=0)
    df_editado_view_patr = st.data_editor(styled_view_patr, hide_index=True, column_config=col_config_top, use_container_width=True, height=285)
    
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

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio_resultado, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view}, subset=pd.IndexSlice[[0, 1, 2], meses_view])\
        .format(formatter={col: '{:.2f}%' for col in meses_view}, subset=pd.IndexSlice[[3], meses_view])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO 
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config_bot, use_container_width=True, height=180)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS EDITÁVEL 
    # ------------------------------------------------------------------
    df_view_ent = st.session_state.df_entradas[['MESES'] + meses_view]
    # Aplica a cor do mês atual
    styled_view_ent = df_view_ent.style.apply(destaque_mes_editavel, axis=0)
    df_editado_view_ent = st.data_editor(styled_view_ent, hide_index=True, column_config=col_config_bot, use_container_width=True, height=180)
    
    for mes in meses_view:
        st.session_state.df_entradas[mes] = df_editado_view_ent[mes]
    
    df_num_ent = st.session_state.df_entradas.set_index('MESES')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'MESES': ['SALÁRIO MÊS:']})
    for mes in meses_view:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas_resultado, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view})
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS 
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config_bot, use_container_width=True, height=75)

    st.markdown('</div>', unsafe_allow_html=True) # Fecha container das tabelas

    # ==========================================
    # BLOCO 3: INDICADORES RESTAURADOS E COMPACTOS
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
