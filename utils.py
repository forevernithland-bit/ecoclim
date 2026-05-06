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

# ==========================================
# CONEXÃO BANCO DE DADOS (SUPABASE)
# ==========================================
def init_connection():
    from supabase import create_client
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ==========================================
# FUNÇÕES DE CATÁLOGO E CONFIGURAÇÕES
# ==========================================
def load_catalog(table_name):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table_name).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        
        mapping = {
            "item": "Item", 
            "custo": "Custo (R$)", 
            "margem": "Margem (%)", 
            "lucro": "Lucro (R$)", 
            "venda": "Venda (R$)"
        }
        
        if df.empty:
            return pd.DataFrame(columns=list(mapping.values()))
            
        df = df.rename(columns=mapping)
        
        # BLINDAGEM: Se alguma coluna estiver faltando no banco, cria como 0.0
        for col_sistema in mapping.values():
            if col_sistema not in df.columns:
                df[col_sistema] = 0.0
        
        return df[list(mapping.values())]
        
    except Exception as e:
        st.error(f"Erro ao carregar a tabela {table_name}: {e}")
        return pd.DataFrame(columns=["Item", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])

def save_catalog(table_name, df):
    supabase = st.session_state.supabase
    try:
        data = []
        for _, row in df.iterrows():
            if row['Item'] and str(row['Item']).strip() != "":
                data.append({
                    "item": row['Item'],
                    "custo": float(row['Custo (R$)']),
                    "margem": float(row['Margem (%)']),
                    "lucro": float(row['Lucro (R$)']),
                    "venda": float(row['Venda (R$)'])
                })
        supabase.table(table_name).delete().neq("item", "___vazio___").execute()
        if data:
            supabase.table(table_name).insert(data).execute()
    except Exception as e:
        st.error(f"Erro ao salvar catálogo: {e}")

# ==========================================
# BANCO DE DADOS: TAXAS E IMPOSTOS
# ==========================================
def load_taxas():
    supabase = st.session_state.supabase
    try:
        res = supabase.table('catalogo_taxas').select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=["Item", "Taxa (%)"])
        df = df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
        return df[["Item", "Taxa (%)"]]
    except:
        return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    supabase = st.session_state.supabase
    try:
        data = [{"item": row['Item'], "taxa_percentual": float(row['Taxa (%)'])} for _, row in df.iterrows() if row['Item'] and str(row['Item']).strip() != ""]
        supabase.table('catalogo_taxas').delete().neq("item", "___vazio___").execute()
        if data: supabase.table('catalogo_taxas').insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar taxas: {e}")

# ==========================================
# FUNÇÕES FINANCEIRAS E CONFIGURAÇÕES DE TELA
# ==========================================
def load_user_settings():
    return "JANEIRO", mes_atual_nome

def save_user_settings(inicio, fim):
    pass 

def load_year_data(table, default_accounts, year):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table).select("*").eq("ano", year).execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            df = pd.DataFrame({"MESES": default_accounts})
            for m in meses_pt: df[m] = 0.0
            return df
        
        cols = ["MESES"] + meses_pt
        for c in cols:
            if c not in df.columns:
                df[c] = 0.0 if c != "MESES" else ""
        return df[cols]
    except:
        df = pd.DataFrame({"MESES": default_accounts})
        for m in meses_pt: df[m] = 0.0
        return df

def save_to_supabase(table, df, year):
    supabase = st.session_state.supabase
    data = []
    for _, row in df.iterrows():
        record = {"ano": year, "MESES": row["MESES"]}
        for m in meses_pt:
            record[m] = float(row[m]) if pd.notna(row[m]) else 0.0
        data.append(record)
    try:
        supabase.table(table).delete().eq("ano", year).execute()
        supabase.table(table).insert(data).execute()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# ==========================================
# UTILITÁRIOS DE FORMATAÇÃO E EXCEL
# ==========================================
def to_br_currency(value, symbol=True):
    if pd.isna(value) or value is None: value = 0.0
    res = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if symbol else res

def parse_br_currency(val_str):
    if isinstance(val_str, (int, float)): return float(val_str)
    if not val_str
