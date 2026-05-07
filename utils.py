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

def load_catalog(table_name):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(table_name).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        mapping = {"item": "Item", "descricao": "Descrição", "custo": "Custo (R$)", "margem": "Margem (%)", "lucro": "Lucro (R$)", "venda": "Venda (R$)"}
        if df.empty: return pd.DataFrame(columns=["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])
        df = df.rename(columns={k:v for k,v in mapping.items() if k in df.columns})
        for col_sistema in mapping.values():
            if col_sistema not in df.columns: df[col_sistema] = "" if col_sistema == "Descrição" else 0.0
        return df[list(mapping.values())]
    except: return pd.DataFrame(columns=["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])

def save_catalog(table_name, df):
    supabase = st.session_state.supabase
    try:
        data = []
        for _, row in df.iterrows():
            if row['Item'] and str(row['Item']).strip() != "":
                record = {"item": row['Item'], "custo": float(row['Custo (R$)']), "margem": float(row['Margem (%)']), "lucro": float(row['Lucro (R$)']), "venda": float(row['Venda (R$)'])}
                if 'Descrição' in row: record['descricao'] = str(row['Descrição'])
                data.append(record)
        supabase.table(table_name).delete().neq("item", "___vazio___").execute()
        if data: supabase.table(table_name).insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar catálogo: {e}")

def load_taxas():
    supabase = st.session_state.supabase
    try:
        res = supabase.table('catalogo_taxas').select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(columns=["Item", "Taxa (%)"])
        df = df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
        return df[["Item", "Taxa (%)"]]
    except: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    supabase = st.session_state.supabase
    try:
        data = [{"item": row['Item'], "taxa_percentual": float(row['Taxa (%)'])} for _, row in df.iterrows() if row['Item'] and str(row['Item']).strip() != ""]
        supabase.table('catalogo_taxas').delete().neq("item", "___vazio___").execute()
        if data: supabase.table('catalogo_taxas').insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar taxas: {e}")

def to_br_currency(value, symbol=True):
    if pd.isna(value) or value is None: value = 0.0
    res = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if symbol else res

# ==========================================
# GERAÇÃO DE PDF (v.2.5 - DESCRIÇÃO TOTAL)
# ==========================================
def gerar_pdf_orcamento(nome, tel, capa_tipo, df_items, d_serv, v_serv, d_out, v_out, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # 1. CABEÇALHO
    try: p.drawImage("logo.png", 2*cm, altura - 3.5*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except: p.setFont("Helvetica-Bold", 16); p.drawString(2*cm, altura - 2.5*cm, "ECOCLIM")
    
    p.setFont("Helvetica-Bold", 14); p.drawString(largura - 9*cm, altura - 1.5*cm, "PROPOSTA COMERCIAL")
    p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
    p.drawString(largura - 9*cm, altura - 2.1*cm, "WWW.ECOCLIM.COM.BR")
    p.drawString(largura - 9*cm, altura - 2.5*cm, "COMERCIAL@ECOCLIM.COM.BR")
    p.drawString(largura - 9*cm, altura - 2.9*cm, "(31) 99867-7808")
    
    p.setFillColor(colors.black); p.setFont("Helvetica", 9)
    p.drawString(largura - 9*cm, altura - 3.5*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    p.drawString(largura - 9*cm, altura - 4.0*cm, "Validade: 15 dias")

    # 2. CLIENTE
    y = altura - 5.5*cm
    p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 1.5*cm, largura - 4*cm, 2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 10); p.drawString(2.3*cm, y, "DADOS DO CLIENTE")
    p.setFont("Helvetica", 10); p.drawString(2.3*cm, y - 0.5*cm, f"Nome: {nome}"); p.drawString(2.3*cm, y - 1*cm, f"WhatsApp: {tel}")

    # 3. IMAGEM GRANDE
    y -= 2.2*cm
    img_map = {"AQUECEDOR SOLAR TRADICIONAL": "aquecedor_tradicional.jpg", "AQUECEDOR SOLAR A VÁCUO ACOPLADO": "vacuo_acoplado.jpg", "AQUECEDOR SOLAR MODULAR": "modular.jpg", "AQUECEDOR DE PISCINA - TRADICIONAL": "piscina.jpg", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR": "piscina.jpg", "SISTEMAS DE PRESSURIZAÇÃO": "pressurizacao.jpg"}
    try:
        if capa_tipo in img_map: p.drawImage(img_map[capa_tipo], 2*cm, y - 5.5*cm, width=largura - 4*cm, height=5.5*cm, preserveAspectRatio=True, mask='auto')
    except: pass
    
    y -= 6.5*cm

    # 4. EQUIPAMENTOS
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "1. EQUIPAMENTOS")
    y -= 0.6*cm; p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 9)
    p.drawString(2.3*cm, y - 0.3*cm, "Item"); p.drawString(12.5*cm, y - 0.3*cm, "Qtd"); p.drawRightString(largura - 2.3*cm, y - 0.3*cm, "Subtotal")
    p.setFont("Helvetica", 9); y -= 0.8*cm
    
    for _, row in df_items.iterrows():
        if row['Quantidade'] > 0:
            item_nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
            p.setFont("Helvetica-Bold", 9); p.drawString(2.3*cm, y, str(item_nome)[:60])
            p.setFont("Helvetica", 9); p.drawString(12.8*cm, y, str(int(row['Quantidade'])))
            p.drawRightString(largura - 2.3*cm, y, to_br_currency(row.get('Venda Total', 0)))
            y -= 0.4*cm
            desc = str(row.get('Descrição', "")).strip()
            if desc and desc != "nan":
                p.setFont("Helvetica", 8); p.setFillColor(colors.HexColor("#555555"))
                for linha in desc.split('\n'):
                    if linha.strip():
                        p.drawString(2.3*cm, y, linha.strip()[:95])
                        y -= 0.35*cm
                p.setFillColor(colors.black)
            y -= 0.1*cm

    # 5. SERVIÇOS (MULTILINHA CORRIGIDO)
    y -= 0.5*cm
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "2. SERVIÇOS E DIVERSOS")
    y -= 0.6*cm; p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 9)
    p.drawString(2.3*cm, y - 0.3*cm, "Descrição"); p.drawRightString(largura - 2.3*cm, y - 0.3*cm, "Subtotal")
    p.setFont("Helvetica", 10); y -= 0.8*cm
    
    # Processa descrição do serviço (puxando todas as linhas)
    if str(d_serv).strip() != "":
        # Preço alinhado na primeira linha do serviço
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_serv))
        for linha in str(d_serv).split('\n'):
            if linha.strip():
                p.drawString(2.3*cm, y, linha.strip()[:85])
                y -= 0.45*cm
    
    if str(d_out).strip() != "":
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_out))
        for linha in str(d_out).split('\n'):
            if linha.strip():
                p.drawString(2.3*cm, y, linha.strip()[:85])
                y -= 0.45*cm

    # 6. INVESTIMENTO TOTAL (POSIÇÃO DINÂMICA)
    y -= 0.2*cm
    p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 0.2*cm, largura - 4*cm, 1*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 12)
    p.drawString(2.3*cm, y + 0.2*cm, "INVESTIMENTO TOTAL")
    p.drawRightString(largura - 2.3*cm, y + 0.2*cm, to_br_currency(total))

    # 7. OBSERVAÇÕES
    y -= 1.8*cm
    p.setFillColor(colors.red); p.setFont("Helvetica-Bold", 10); p.drawString(2*cm, y, "OBSERVAÇÕES:")
    p.setFont("Helvetica", 9); p.setFillColor(colors.black); p.drawString(2*cm, y - 0.5*cm, str(obs)[:100])
    
    p.setFont("Helvetica", 6); p.setFillColor(colors.lightgrey); p.drawString(2*cm, 1*cm, "v.2.5")
    p.save()
    buffer.seek(0)
    return buffer
