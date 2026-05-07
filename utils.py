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
        
        mapping = {
            "item": "Item", 
            "descricao": "Descrição",
            "custo": "Custo (R$)", 
            "margem": "Margem (%)", 
            "lucro": "Lucro (R$)", 
            "venda": "Venda (R$)"
        }
        
        if df.empty: return pd.DataFrame(columns=["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])
        df = df.rename(columns={k:v for k,v in mapping.items() if k in df.columns})
        
        for col_sistema in mapping.values():
            if col_sistema not in df.columns:
                df[col_sistema] = "" if col_sistema == "Descrição" else 0.0
        return df[list(mapping.values())]
    except Exception as e:
        return pd.DataFrame(columns=["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"])

def save_catalog(table_name, df):
    supabase = st.session_state.supabase
    try:
        data = []
        for _, row in df.iterrows():
            if row['Item'] and str(row['Item']).strip() != "":
                record = {
                    "item": row['Item'],
                    "custo": float(row['Custo (R$)']),
                    "margem": float(row['Margem (%)']),
                    "lucro": float(row['Lucro (R$)']),
                    "venda": float(row['Venda (R$)'])
                }
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
    except Exception: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    supabase = st.session_state.supabase
    try:
        data = [{"item": row['Item'], "taxa_percentual": float(row['Taxa (%)'])} for _, row in df.iterrows() if row['Item'] and str(row['Item']).strip() != ""]
        supabase.table('catalogo_taxas').delete().neq("item", "___vazio___").execute()
        if data: supabase.table('catalogo_taxas').insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar taxas: {e}")

def load_user_settings(): return "JANEIRO", mes_atual_nome

def save_user_settings(inicio, fim): pass 

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
            if c not in df.columns: df[c] = 0.0 if c != "MESES" else ""
        return df[cols]
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

def to_br_currency(value, symbol=True):
    if pd.isna(value) or value is None: value = 0.0
    res = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if symbol else res

def parse_br_currency(val_str):
    if isinstance(val_str, (int, float)): return float(val_str)
    if not val_str or pd.isna(val_str): return 0.0
    s = str(val_str).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except Exception: return 0.0

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# ==========================================
# GERAÇÃO DE PDF (ESPAÇAMENTO CORRIGIDO)
# ==========================================
def gerar_pdf_orcamento(nome, tel, capa_tipo, df_items, d_serv, v_serv, d_out, v_out, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # 1. LOGO E CABEÇALHO (COM CONTATOS)
    try:
        p.drawImage("logo.png", 2*cm, altura - 3.5*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except Exception:
        p.setFont("Helvetica-Bold", 16)
        p.drawString(2*cm, altura - 2.5*cm, "ECOCLIM")
        
    p.setFont("Helvetica-Bold", 14)
    p.drawString(largura - 9*cm, altura - 1.5*cm, "PROPOSTA COMERCIAL")
    
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.grey)
    p.drawString(largura - 9*cm, altura - 2.1*cm, "WWW.ECOCLIM.COM.BR")
    p.drawString(largura - 9*cm, altura - 2.5*cm, "COMERCIAL@ECOCLIM.COM.BR")
    p.drawString(largura - 9*cm, altura - 2.9*cm, "(31) 99867-7808")
    
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    p.drawString(largura - 9*cm, altura - 3.5*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    p.drawString(largura - 9*cm, altura - 4.0*cm, "Validade: 15 dias")

    # 2. DADOS DO CLIENTE
    y = altura - 5.5*cm
    p.setFillColor(colors.HexColor("#f0f0f0"))
    p.rect(2*cm, y - 1.5*cm, largura - 4*cm, 2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2.3*cm, y, "DADOS DO CLIENTE")
    p.setFont("Helvetica", 10)
    p.drawString(2.3*cm, y - 0.5*cm, f"Nome: {nome}")
    p.drawString(2.3*cm, y - 1*cm, f"Telefone: {tel}")

    # 3. IMAGEM DE APRESENTAÇÃO
    y -= 2.2*cm
    img_map = {
        "AQUECEDOR SOLAR TRADICIONAL": "aquecedor_tradicional.jpg",
        "AQUECEDOR SOLAR A VÁCUO ACOPLADO": "vacuo_acoplado.jpg",
        "AQUECEDOR SOLAR MODULAR": "modular.jpg",
        "AQUECEDOR DE PISCINA - TRADICIONAL": "piscina.jpg",
        "AQUECEDOR DE PISCINA - TROCADOR DE CALOR": "piscina.jpg",
        "SISTEMAS DE PRESSURIZAÇÃO": "pressurizacao.jpg"
    }
    
    try:
        if capa_tipo in img_map:
            img_path = img_map[capa_tipo]
            p.drawImage(img_path, 2*cm, y - 5.5*cm, width=largura - 4*cm, height=5.5*cm, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    
    y -= 6.5*cm

    # 4. EQUIPAMENTOS
    p.setFillColor(colors.HexColor("#004488"))
    p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2.3*cm, y + 0.2*cm, "1. EQUIPAMENTOS")
    
    y -= 0.6*cm
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(2.3*cm, y - 0.3*cm, "Item")
    p.drawString(12.5*cm, y - 0.3*cm, "Qtd")
    p.drawRightString(largura - 2.3*cm, y - 0.3*cm, "Subtotal")
    
    y -= 0.8*cm
    
    for _, row in df_items.iterrows():
        if row['Quantidade'] > 0:
            item_nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
            
            p.setFont("Helvetica-Bold", 9)
            p.drawString(2.3*cm, y, str(item_nome)[:60])
            
            p.setFont("Helvetica", 9)
            p.drawString(12.8*cm, y, str(int(row['Quantidade'])))
            p.drawRightString(largura - 2.3*cm, y, to_br_currency(row.get('Venda Total', 0)))
            y -= 0.4*cm
            
            desc = str(row.get('Descrição', "")).strip()
            if desc and desc != "nan":
                p.setFont("Helvetica", 8)
                p.setFillColor(colors.HexColor("#555555")) 
                linhas_desc = desc.split('\n')
                for linha in linhas_desc:
                    if linha.strip():
                        linha_up = linha.upper()
                        prefix = "Detalhes: " if linha == linhas_desc[0] and not (linha_up.startswith("DETALHES") or linha_up.startswith("QUANTIDADE") or linha_up.startswith("GARANTIA") or linha_up.startswith("-")) else ""
                        p.drawString(2.3*cm, y, prefix + linha.strip())
                        y -= 0.35*cm
                p.setFillColor(colors.black)

    # ==========================================
    # CORREÇÃO CRUCIAL AQUI: Empurrar a caixa "2. SERVIÇOS" bem para baixo
    # ==========================================
    y -= 1.2*cm # Espaço seguro garantido para não sobrepor a última linha da descrição

    # 5. SERVIÇOS E DIVERSOS
    p.setFillColor(colors.HexColor("#004488"))
    p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0) # O rect desenha PARA CIMA a partir do y
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2.3*cm, y + 0.2*cm, "2. SERVIÇOS")
    
    y -= 0.8*cm
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 10)
    
    if str(d_serv).strip() != "":
        desc_s = str(d_serv).split('\n')[0][:75]
        p.drawString(2.3*cm, y, desc_s)
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_serv))
        y -= 0.6*cm
        
    if str(d_out).strip() != "":
        desc_o = str(d_out).split('\n')[0][:75]
        p.drawString(2.3*cm, y, desc_o)
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_out))
        y -= 0.6*cm

    # 6. INVESTIMENTO TOTAL
    y -= 0.5*cm
    p.setFillColor(colors.HexColor("#f0f0f0"))
    p.rect(2*cm, y, largura - 4*cm, 1*cm, fill=1, stroke=0)
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(2.3*cm, y + 0.3*cm, "INVESTIMENTO TOTAL")
    p.drawRightString(largura - 2.3*cm, y + 0.3*cm, to_br_currency(total))

    # 7. OBSERVAÇÕES
    y -= 1.5*cm
    p.setFillColor(colors.red)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2*cm, y, "OBSERVAÇÕES:")
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.black)
    p.drawString(2*cm, y - 0.5*cm, str(obs)[:100])
    
    p.setFont("Helvetica", 6)
    p.setFillColor(colors.lightgrey)
    p.drawString(2*cm, 1*cm, "v.2.3") # Verifique esta versão ao testar!

    p.save()
    buffer.seek(0)
    return buffer
