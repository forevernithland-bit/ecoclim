import streamlit as st
import pandas as pd
import numpy as np
import datetime
import re
import os
import io
from supabase import create_client
from fpdf import FPDF

# ==========================================
# VARIÁVEIS GLOBAIS E FORMATAÇÃO
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_atual = hoje.year
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def init_connection():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

def to_br_currency(val, show_cents=True):
    try:
        v = float(val)
        if show_cents:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return f"R$ {int(v):,}".replace(",", ".")
    except: return "R$ 0,00"

def parse_br_currency(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        clean = re.sub(r'[^\d,-]', '', str(val)).replace(",", ".")
        return float(clean) if clean else 0.0
    except: return 0.0

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Base_Ecoclim')
    return output.getvalue()

# ==========================================
# BANCO DE DADOS: CATÁLOGOS (CONFIGURAÇÕES)
# ==========================================
def load_catalog(table_name):
    # Usa a conexão salva na sessão
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table_name).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=["Item", "Fornecedor", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)", "Descrição"])
        
        if "fornecedor" not in df.columns:
            df["fornecedor"] = ""
            
        df = df.rename(columns={"item": "Item", "fornecedor": "Fornecedor", "custo": "Custo (R$)", "margem": "Margem (%)", "descricao": "Descrição"})
        df['Venda (R$)'] = (df['Custo (R$)'] * (1 + df['Margem (%)'] / 100)).round().astype(float)
        df['Lucro (R$)'] = (df['Venda (R$)'] - df['Custo (R$)']).astype(float)
        return df[["Item", "Fornecedor", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)", "Descrição"]]
    except:
        return pd.DataFrame(columns=["Item", "Fornecedor", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)", "Descrição"])

def save_catalog(table_name, df):
    supabase = st.session_state.supabase
    try:
        data = []
        for _, row in df.iterrows():
            if row['Item'] and str(row['Item']).strip() != "":
                data.append({
                    "item": row['Item'],
                    "fornecedor": str(row.get('Fornecedor', '')),
                    "custo": float(row['Custo (R$)']),
                    "margem": float(row['Margem (%)']),
                    "descricao": str(row['Descrição']) if row['Descrição'] else ""
                })
        supabase.table(table_name).delete().neq("item", "___vazio___").execute()
        if data: supabase.table(table_name).insert(data).execute()
    except Exception as e: st.error(f"Erro ao sincronizar catálogo: {e}")

# ==========================================
# BANCO DE DADOS: FINANCEIRO
# ==========================================
def load_year_data(table_name, itens_padrao, ano_escolhido):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
        df_raw = pd.DataFrame(res.data)
        if df_raw.empty:
            df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
            df.insert(0, 'MESES', itens_padrao); return df
        df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0.0)
        for m in meses_pt:
            if m not in df_pivot.columns: df_pivot[m] = 0.0
        df_pivot = df_pivot[meses_pt].reset_index()
        df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
        for item in itens_padrao:
            if item not in df_pivot['MESES'].values:
                nova_linha = {m: 0.0 for m in meses_pt}; nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        df_pivot.set_index('MESES', inplace=True); df_pivot = df_pivot.reindex(itens_padrao).reset_index()
        df_pivot[meses_pt] = df_pivot[meses_pt].astype(float)
        return df_pivot
    except:
        df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao); return df

def save_to_supabase(table_name, df_float, ano_escolhido):
    supabase = st.session_state.supabase
    try:
        df_melted = df_float.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido; df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        df_melted['valor'] = df_melted['valor'].astype(float)
        data = df_melted.to_dict(orient='records')
        supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
        supabase.table(table_name).insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar financeiro: {e}")

# ==========================================
# CONFIGURAÇÕES DE USUÁRIO (SLIDER)
# ==========================================
def load_user_settings():
    supabase = st.session_state.supabase
    try:
        res = supabase.table('configuracoes').select("*").eq('user_id', 'breno.lima').execute()
        if res.data: return res.data[0]['mes_inicio'], res.data[0]['mes_fim']
    except: pass
    return "JANEIRO", mes_atual_nome

def save_user_settings(inicio, fim):
    supabase = st.session_state.supabase
    try:
        data = {"id": 1, "user_id": "breno.lima", "mes_inicio": inicio, "mes_fim": fim}
        supabase.table('configuracoes').upsert(data).execute()
    except: pass

# ==========================================
# GERADOR DE PDF
# ==========================================
def gerar_pdf_orcamento(cliente, tel, produto, df_equip, desc_s, val_s, desc_o, val_o, total, obs, mostrar_val):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    if os.path.exists("logo.png"): pdf.image("logo.png", 10, 8, 40)
    
    pdf.cell(0, 10, "PROPOSTA COMERCIAL", ln=True, align="R")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y')}", ln=True, align="R")
    pdf.cell(0, 5, "Validade: 15 dias", ln=True, align="R")
    pdf.ln(10)
    
    pdf.set_fill_color(230, 240, 255)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " DADOS DO CLIENTE", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, f" Nome: {cliente}", border=1, ln=True)
    pdf.cell(0, 8, f" Telefone: {tel}", border=1, ln=True)
    pdf.ln(5)

    img_urls = {
        "AQUECEDOR SOLAR TRADICIONAL": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+Solar+Tradicional",
        "AQUECEDOR SOLAR A VÁCUO ACOPLADO": "https://dummyimage.com/600x200/004488/fff&text=Tubos+a+Vacuo+Acoplado",
        "AQUECEDOR SOLAR MODULAR": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+Solar+Modular",
        "AQUECEDOR DE PISCINA - TRADICIONAL": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+de+Piscina",
        "AQUECEDOR DE PISCINA - TROCADOR DE CALOR": "https://dummyimage.com/600x200/004488/fff&text=Trocador+de+Calor",
        "SISTEMAS DE PRESSURIZAÇÃO": "https://dummyimage.com/600x200/004488/fff&text=Sistema+de+Pressurizacao"
    }
    try: pdf.image(img_urls.get(produto, img_urls["AQUECEDOR SOLAR TRADICIONAL"]), x=10, w=190)
    except: pdf.cell(0, 20, f"[IMAGEM: {produto}]", border=1, ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 8, " 1. EQUIPAMENTOS", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "B", 10)
    if mostrar_val:
        pdf.cell(100, 8, " Item", border=1); pdf.cell(30, 8, " Qtd", border=1, align="C"); pdf.cell(60, 8, " Subtotal", border=1, ln=True, align="R")
    else:
        pdf.cell(160, 8, " Item", border=1); pdf.cell(30, 8, " Qtd", border=1, ln=True, align="C")
    
    for _, row in df_equip.iterrows():
        nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
        if str(nome).strip() != "":
            q, v = float(row['Quantidade']), float(row['Venda (R$)'])
            pdf.set_font("helvetica", "B", 10); pdf.set_text_color(0, 0, 0)
            
            if mostrar_val:
                pdf.cell(100, 8, f" {nome}", border=1); pdf.cell(30, 8, f" {int(q)}", border=1, align="C"); pdf.cell(60, 8, f" {to_br_currency(q*v)}", border=1, ln=True, align="R")
            else:
                pdf.cell(160, 8, f" {nome}", border=1); pdf.cell(30, 8, f" {int(q)}", border=1, ln=True, align="C")
            
            if nome in st.session_state.db_produtos['Item'].values:
                desc_texto = st.session_state.db_produtos.loc[st.session_state.db_produtos['Item'] == nome, 'Descrição'].values[0]
                if str(desc_texto).strip() != "":
                    pdf.set_font("helvetica", "I", 8); pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(0, 5, f"  Detalhes: {desc_texto}", border=1)
                    pdf.set_text_color(0, 0, 0)

    if val_s > 0:
        pdf.ln(5); pdf.set_font("helvetica", "B", 12); pdf.cell(0, 8, " 2. SERVIÇOS", border=1, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10); pdf.multi_cell(0, 6, f" {desc_s}", border=1)
        pdf.cell(130, 8, " Valor do Serviço:", border=1); pdf.cell(60, 8, f" {to_br_currency(val_s)}", border=1, ln=True, align="R")

    if val_o > 0:
        pdf.ln(5); pdf.set_font("helvetica", "B", 12); pdf.cell(0, 8, " 3. DIVERSOS", border=1, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10); pdf.multi_cell(0, 6, f" {desc_o}", border=1)
        pdf.cell(130, 8, " Valor Adicional:", border=1); pdf.cell(60, 8, f" {to_br_currency(val_o)}", border=1, ln=True, align="R")

    pdf.ln(5); pdf.set_font("helvetica", "B", 14); pdf.set_fill_color(0, 68, 136); pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 10, " INVESTIMENTO TOTAL", border=1, fill=True); pdf.cell(60, 10, f" {to_br_currency(total)}", border=1, ln=True, align="R", fill=True)
    pdf.ln(10); pdf.set_text_color(200, 0, 0); pdf.set_font("helvetica", "B", 10); pdf.multi_cell(0, 6, f"OBSERVAÇÕES:\n{obs}", border=0)
    
    return bytes(pdf.output())
