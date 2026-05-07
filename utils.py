import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# ==========================================
# VARIÁVEIS GLOBAIS DE DATA
# ==========================================
hoje = datetime.date.today()
ano_atual = hoje.year
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
mes_hoje_idx = hoje.month
mes_atual_nome = meses_pt[mes_hoje_idx - 1]

def init_connection():
    from supabase import create_client
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ==========================================
# FUNÇÕES FINANCEIRAS
# ==========================================
def load_year_data(nome_tabela, contas_padrao, ano):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(nome_tabela).select("*").eq("ano", ano).execute()
        df_banco = pd.DataFrame(res.data)
        
        if df_banco.empty:
            df_novo = pd.DataFrame({"MESES": contas_padrao})
            for mes in meses_pt: df_novo[mes] = 0.0
            return df_novo
        
        df_banco.columns = df_banco.columns.str.upper()
        colunas_ordenadas = ["MESES"] + meses_pt
        for col in colunas_ordenadas:
            if col not in df_banco.columns: df_banco[col] = 0.0 if col != "MESES" else ""
        return df_banco[colunas_ordenadas]
    except:
        return pd.DataFrame({"MESES": contas_padrao, **{m: 0.0 for m in meses_pt}})

def save_to_supabase(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    dados_finais = []
    for _, linha in df.iterrows():
        registro = {"ano": ano, "MESES": linha["MESES"]}
        for mes_coluna in meses_pt: registro[mes_coluna] = float(linha[mes_coluna]) if pd.notna(linha[mes_coluna]) else 0.0
        dados_finais.append(registro)
    try:
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        supabase.table(nome_tabela).insert(dados_finais).execute()
    except Exception as e: st.error(f"Erro ao salvar: {e}")

# ==========================================
# CATÁLOGOS E UTILITÁRIOS (BLINDADO)
# ==========================================
def load_catalog(nome_tabela):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(nome_tabela).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        mapeamento = {"item": "Item", "descricao": "Descrição", "custo": "Custo (R$)", "margem": "Margem (%)", "lucro": "Lucro (R$)", "venda": "Venda (R$)"}
        if df.empty: return pd.DataFrame(columns=list(mapeamento.values()))
        df = df.rename(columns={k: v for k, v in mapeamento.items() if k in df.columns})
        for coluna in mapeamento.values():
            if coluna not in df.columns: df[coluna] = "" if "Desc" in coluna or "Item" in coluna else 0.0
        return df[list(mapeamento.values())]
    except: return pd.DataFrame(columns=["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])

def save_catalog(nome_tabela, df):
    supabase = st.session_state.supabase
    lista_dados = []
    for _, linha in df.iterrows():
        if linha['Item'] and str(linha['Item']).strip() != "":
            lista_dados.append({
                "item": linha['Item'], "descricao": str(linha['Descrição']),
                "custo": float(linha.get('Custo (R$)', 0)), "margem": float(linha.get('Margem (%)', 0)),
                "lucro": float(linha.get('Lucro (R$)', 0)), "venda": float(linha.get('Venda (R$)', 0))
            })
    try:
        supabase.table(nome_tabela).delete().neq("item", "___VAZIO___").execute()
        if lista_dados: supabase.table(nome_tabela).insert(lista_dados).execute()
    except Exception as e: st.error(f"Erro ao salvar catálogo: {e}")

def to_br_currency(valor, incluir_simbolo=True):
    try: valor_float = float(valor)
    except: valor_float = 0.0
    res = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if incluir_simbolo else res

def parse_br_currency(texto_valor):
    if isinstance(texto_valor, (int, float)): return float(texto_valor)
    s = str(texto_valor).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def load_taxas():
    try:
        res = st.session_state.supabase.table('catalogo_taxas').select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(columns=["Item", "Taxa (%)"])
        return df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
    except: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    dados = [{"item": r['Item'], "taxa_percentual": float(r['Taxa (%)'])} for _, r in df.iterrows() if r['Item']]
    st.session_state.supabase.table('catalogo_taxas').delete().neq("item", "___").execute()
    if dados: st.session_state.supabase.table('catalogo_taxas').insert(dados).execute()
