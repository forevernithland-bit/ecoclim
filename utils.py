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
        # Correção principal: ordenando por 'item' para evitar erro se a tabela não tiver a coluna 'id'
        res = supabase.table(table_name).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=["Item", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])
        df = df.rename(columns={"item": "Item", "custo": "Custo (R$)", "margem": "Margem (%)", "lucro": "Lucro (R$)", "venda": "Venda (R$)"})
        return df[["Item", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"]]
    except Exception as e:
        st.error(f"Erro ao carregar a tabela {table_name} do banco de dados: {e}")
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
# FUNÇÕES FINANCEIRAS
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
    if not val_str or pd.isna(val_str): return 0.0
    s = str(val_str).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# ==========================================
# GERAÇÃO DE PDF (PROPOSTA COMERCIAL E ESCOPO)
# ==========================================
IMG_CAPA = "http://googleusercontent.com/image_collection/image_retrieval/6422524173617068594"
IMG_VACUO = "http://googleusercontent.com/image_collection/image_retrieval/4744835434356641686"
IMG_TRADICIONAL = "http://googleusercontent.com/image_collection/image_retrieval/1248258249000705016"
IMG_PISCINA = "http://googleusercontent.com/image_collection/image_retrieval/7319541597131710314"
IMG_AR = "http://googleusercontent.com/image_collection/image_retrieval/13303198893195767277"

def gerar_pdf_orcamento(nome, tel, capa_tipo, df_items, d_serv, v_serv, d_out, v_out, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # PÁGINA 1: CAPA
    try:
        p.drawImage(IMG_CAPA, 0, 0, width=largura, height=altura, mask='auto')
        try: p.drawImage("logo.png", 2*cm, altura - 5*cm, width=6*cm, preserveAspectRatio=True, mask='auto')
        except: pass
        p.setFillColor(colors.HexColor("#001529"))
        p.rect(0, 0, largura, 5*cm, fill=1, stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 36)
        p.drawCentredString(largura/2, 2*cm, "PROPOSTA DE SERVIÇO")
        p.showPage()
    except:
        p.showPage()

    # PÁGINA 2: PROPOSTA COMERCIAL
    try: p.drawImage("logo.png", 1.5*cm, altura - 3*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except: pass
    
    p.setFont("Helvetica-Bold", 16)
    p.setFillColor(colors.black)
    p.drawString(10*cm, altura - 2*cm, "PROPOSTA COMERCIAL")
    
    p.setFont("Helvetica", 10)
    p.drawRightString(largura - 1.5*cm, altura - 2*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    p.drawRightString(largura - 1.5*cm, altura - 2.5*cm, "Validade: 15 dias")

    p.setFillColor(colors.HexColor("#004488"))
    p.rect(1.5*cm, altura - 4.5*cm, largura - 3*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(1.8*cm, altura - 4.05*cm, "DADOS DO CLIENTE")
    
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 10)
    p.rect(1.5*cm, altura - 6.5*cm, largura - 3*cm, 2*cm, fill=0, stroke=1)
    p.drawString(1.8*cm, altura - 5.3*cm, f"Nome: {nome}")
    p.drawString(1.8*cm, altura - 6.0*cm, f"WhatsApp: {tel}")

    y = altura - 8*cm
    p.setFillColor(colors.HexColor("#333333"))
    p.rect(1.5*cm, y, largura - 3*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.drawString(1.8*cm, y + 0.2*cm, "1. EQUIPAMENTOS")
    
    y -= 0.6*cm
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(1.8*cm, y - 0.3*cm, "Item")
    p.drawString(12*cm, y - 0.3*cm, "Qtd")
    p.drawRightString(largura - 1.8*cm, y - 0.3*cm, "Subtotal")
    
    p.setFont("Helvetica", 9)
    y -= 0.8*cm
    for _, row in df_items.iterrows():
        if row['Quantidade'] > 0:
            item_nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
            p.drawString(1.8*cm, y, str(item_nome)[:55])
            p.drawString(12.3*cm, y, str(int(row['Quantidade'])))
            p.drawRightString(largura - 1.8*cm, y, to_br_currency(row.get('Venda Total', 0)))
            y -= 0.5*cm
            if y < 4*cm:
                p.showPage()
                y = altura - 3*cm

    y -= 1*cm
    p.setFillColor(colors.HexColor("#666666"))
    p.rect(1.5*cm, y, largura - 3*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(1.8*cm, y + 0.2*cm, "2. SERVIÇOS")
    
    y -= 0.7*cm
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    p.drawString(1.8*cm, y - 0.3*cm, str(d_serv)[:80])
    p.drawRightString(largura - 1.8*cm, y - 0.3*cm, to_br_currency(v_serv))

    y -= 2*cm
    p.setFillColor(colors.HexColor("#004488"))
    p.rect(1.5*cm, y, largura - 3*cm, 1.2*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1.8*cm, y + 0.4*cm, "INVESTIMENTO TOTAL")
    p.drawRightString(largura - 1.8*cm, y + 0.4*cm, to_br_currency(total))

    y -= 1.5*cm
    p.setFillColor(colors.red)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.5*cm, y, "OBSERVAÇÕES:")
    p.setFont("Helvetica", 9)
    p.drawString(1.5*cm, y - 0.5*cm, obs)

    p.showPage()

    # PÁGINA 3: ESCOPO DE SERVIÇOS
    p.setFillColor(colors.HexColor("#f4f4f4"))
    p.rect(0, 0, largura, altura, fill=1, stroke=0)
    
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(largura/2, altura - 2*cm, "CONHEÇA NOSSAS SOLUÇÕES")
    
    def draw_service_box(x, y, img_url, title):
        try:
            p.drawImage(img_url, x, y, width=8*cm, height=6*cm, preserveAspectRatio=True)
            p.setFillColor(colors.HexColor("#004488"))
            p.rect(x, y - 1*cm, 8*cm, 0.8*cm, fill=1, stroke=0)
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 10)
            p.drawCentredString(x + 4*cm, y - 0.5*cm, title)
        except: pass

    draw_service_box(1.5*cm, altura - 9*cm, IMG_VACUO, "AQUECEDOR A VÁCUO")
    draw_service_box(largura - 9.5*cm, altura - 9*cm, IMG_TRADICIONAL, "SISTEMA TRADICIONAL")
    draw_service_box(1.5*cm, altura - 17*cm, IMG_PISCINA, "AQUECIMENTO DE PISCINA")
    draw_service_box(largura - 9.5*cm, altura - 17*cm, IMG_AR, "AR CONDICIONADO")

    p.save()
    buffer.seek(0)
    return buffer
