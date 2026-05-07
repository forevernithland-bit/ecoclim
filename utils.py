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
def load_year_data(table, default_accounts, year):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table).select("*").eq("ano", year).execute()
        df_db = pd.DataFrame(res.data)
        if df_db.empty:
            df = pd.DataFrame({"MESES": default_accounts})
            for m in meses_pt: df[m] = 0.0
            return df
        
        # Como o seu banco já tem MESES e MARÇO exatos, basta padronizar MAIÚSCULAS
        df_db.columns = df_db.columns.str.upper()
        
        cols = ["MESES"] + meses_pt
        for c in cols:
            if c not in df_db.columns: df_db[c] = 0.0 if c != "MESES" else ""
        return df_db[cols]
    except Exception:
        df = pd.DataFrame({"MESES": default_accounts})
        for m in meses_pt: df[m] = 0.0
        return df

def save_to_supabase(table, df, year):
    supabase = st.session_state.supabase
    data = []
    for _, row in df.iterrows():
        record = {"ano": year, "MESES": row["MESES"]}
        for m in meses_pt: record[m] = float(row[m]) if pd.notna(row[m]) else 0.0
        data.append(record)
    try:
        supabase.table(table).delete().eq("ano", year).execute()
        supabase.table(table).insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar: {e}")

# ==========================================
# CATÁLOGOS E UTILITÁRIOS
# ==========================================
def load_catalog(table_name):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table_name).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        mapping = {"item": "Item", "descricao": "Descrição", "custo": "Custo", "margem": "Margem (%)", "lucro": "Lucro", "venda": "Venda (R$)"}
        df = df.rename(columns={k:v for k,v in mapping.items() if k in df.columns})
        for c in ["Item", "Descrição", "Custo", "Margem (%)", "Lucro", "Venda (R$)"]:
            if c not in df.columns: df[c] = "" if "Item" in c or "Desc" in c else 0.0
        return df[["Item", "Descrição", "Custo", "Margem (%)", "Lucro", "Venda (R$)"]]
    except: return pd.DataFrame(columns=["Item", "Descrição", "Custo", "Margem (%)", "Lucro", "Venda (R$)"])

def save_catalog(table_name, df):
    supabase = st.session_state.supabase
    data = []
    for _, row in df.iterrows():
        if row['Item']:
            data.append({"item": row['Item'], "descricao": str(row['Descrição']), "custo": float(row['Custo']), "margem": float(row['Margem (%)']), "lucro": float(row['Lucro']), "venda": float(row['Venda (R$)'])})
    try:
        supabase.table(table_name).delete().neq("item", "___").execute()
        if data: supabase.table(table_name).insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar: {e}")

def to_br_currency(value, symbol=True):
    if pd.isna(value): value = 0.0
    res = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if symbol else res

def parse_br_currency(val_str):
    if isinstance(val_str, (int, float)): return float(val_str)
    s = str(val_str).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def load_taxas():
    try:
        res = st.session_state.supabase.table('catalogo_taxas').select("*").execute()
        df = pd.DataFrame(res.data)
        return df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
    except: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    data = [{"item": r['Item'], "taxa_percentual": float(r['Taxa (%)'])} for _, r in df.iterrows() if r['Item']]
    st.session_state.supabase.table('catalogo_taxas').delete().neq("item", "___").execute()
    if data: st.session_state.supabase.table('catalogo_taxas').insert(data).execute()

# ==========================================
# GERAÇÃO DE PDF (COM GORDURA EXTRA NA LINHA AZUL)
# ==========================================
def gerar_pdf_orcamento(nome, tel, capa, df_items, d_s, v_s, d_o, v_o, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    try: p.drawImage("logo.png", 2*cm, altura - 3.5*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except: p.setFont("Helvetica-Bold", 16); p.drawString(2*cm, altura - 2.5*cm, "ECOCLIM")
    p.setFont("Helvetica-Bold", 14); p.drawString(largura - 9*cm, altura - 1.5*cm, "PROPOSTA COMERCIAL")
    p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
    p.drawString(largura - 9*cm, altura - 2.1*cm, "WWW.ECOCLIM.COM.BR"); p.drawString(largura - 9*cm, altura - 2.5*cm, "COMERCIAL@ECOCLIM.COM.BR")
    p.setFillColor(colors.black); p.setFont("Helvetica", 9)
    p.drawString(largura - 9*cm, altura - 3.5*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    y = altura - 5.5*cm
    p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 1.5*cm, largura - 4*cm, 2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 10); p.drawString(2.3*cm, y, "DADOS DO CLIENTE")
    p.setFont("Helvetica", 10); p.drawString(2.3*cm, y - 0.5*cm, f"Nome: {nome}"); p.drawString(2.3*cm, y - 1*cm, f"WhatsApp: {tel}")
    y -= 2.2*cm
    img_map = {"AQUECEDOR SOLAR TRADICIONAL": "aquecedor_tradicional.jpg", "AQUECEDOR SOLAR A VÁCUO ACOPLADO": "vacuo_acoplado.jpg", "AQUECEDOR SOLAR MODULAR": "modular.jpg", "AQUECEDOR DE PISCINA - TRADICIONAL": "piscina.jpg", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR": "piscina.jpg", "SISTEMAS DE PRESSURIZAÇÃO": "pressurizacao.jpg"}
    try: p.drawImage(img_map.get(capa, ""), 2*cm, y - 5.5*cm, width=largura-4*cm, height=5.5*cm, preserveAspectRatio=True)
    except: pass
    y -= 6.5*cm
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "1. EQUIPAMENTOS")
    y -= 0.6*cm; p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 9)
    p.drawString(2.3*cm, y - 0.3*cm, "Item"); p.drawString(12.5*cm, y - 0.3*cm, "Qtd"); p.drawRightString(largura - 2.3*cm, y - 0.3*cm, "Subtotal")
    y -= 0.8*cm
    for _, row in df_items.iterrows():
        if row['Quantidade'] > 0:
            item = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
            p.setFont("Helvetica-Bold", 9); p.drawString(2.3*cm, y, str(item)[:60])
            p.setFont("Helvetica", 9); p.drawString(12.8*cm, y, str(int(row['Quantidade'])))
            p.drawRightString(largura - 2.3*cm, y, to_br_currency(row['Venda Total']))
            y -= 0.4*cm
            desc = str(row.get('Descrição', ""))
            if desc and desc != "nan":
                p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
                for l in desc.split('\n'): p.drawString(2.3*cm, y, l.strip()); y -= 0.35*cm
                p.setFillColor(colors.black)
            y -= 0.2*cm
    
    y -= 1.0*cm 
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "2. SERVIÇOS")
    y -= 0.8*cm; p.setFillColor(colors.black); p.setFont("Helvetica", 10)
    if d_s:
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_s))
        for l in d_s.split('\n'): p.drawString(2.3*cm, y, l); y -= 0.45*cm
    if d_o:
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_o))
        for l in d_o.split('\n'): p.drawString(2.3*cm, y, l); y -= 0.45*cm
    y -= 1.0*cm; p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 0.2*cm, largura - 4*cm, 1.2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 12); p.drawString(2.3*cm, y + 0.2*cm, "INVESTIMENTO TOTAL"); p.drawRightString(largura - 2.3*cm, y + 0.2*cm, to_br_currency(total))
    y -= 1.8*cm; p.setFillColor(colors.red); p.setFont("Helvetica-Bold", 10); p.drawString(2*cm, y, "OBSERVAÇÕES:"); p.setFont("Helvetica", 9); p.setFillColor(colors.black); p.drawString(2*cm, y - 0.5*cm, str(obs)[:100])
    p.save(); buffer.seek(0); return buffer
