import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from io import BytesIO
import datetime

# Constantes de Imagens (URLs recuperadas para o seu projeto)
IMG_CAPA = "http://googleusercontent.com/image_collection/image_retrieval/6422524173617068594"
IMG_VACUO = "http://googleusercontent.com/image_collection/image_retrieval/4744835434356641686"
IMG_TRADICIONAL = "http://googleusercontent.com/image_collection/image_retrieval/1248258249000705016"
IMG_PISCINA = "http://googleusercontent.com/image_collection/image_retrieval/7319541597131710314"
IMG_AR = "http://googleusercontent.com/image_collection/image_retrieval/13303198893195767277"

def to_br_currency(value, symbol=True):
    if value is None: value = 0.0
    res = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if symbol else res

def gerar_pdf_orcamento(nome, tel, capa_tipo, df_items, d_serv, v_serv, d_out, v_out, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # =========================================================================
    # PÁGINA 1: CAPA
    # =========================================================================
    try:
        # Fundo da Capa (Imagem de Paisagem)
        p.drawImage(IMG_CAPA, 0, 0, width=largura, height=altura, mask='auto')
        
        # Logo (Tenta carregar local, senão deixa espaço)
        try: p.drawImage("logo.png", 2*cm, altura - 5*cm, width=6*cm, preserveAspectRatio=True, mask='auto')
        except: pass
        
        # Faixa Escura Inferior
        p.setFillColor(colors.HexColor("#001529"))
        p.rect(0, 0, largura, 5*cm, fill=1, stroke=0)
        
        # Texto da Capa
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 36)
        p.drawCentredString(largura/2, 2*cm, "PROPOSTA DE SERVIÇO")
        
        p.showPage()
    except:
        p.showPage() # Fallback caso a imagem da capa falhe

    # =========================================================================
    # PÁGINA 2: PROPOSTA COMERCIAL (CORRIGIDA)
    # =========================================================================
    # Cabeçalho
    try: p.drawImage("logo.png", 1.5*cm, altura - 3*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except: pass
    
    p.setFont("Helvetica-Bold", 16)
    p.setFillColor(colors.black)
    p.drawString(10*cm, altura - 2*cm, "PROPOSTA COMERCIAL")
    
    p.setFont("Helvetica", 10)
    p.drawRightString(largura - 1.5*cm, altura - 2*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    p.drawRightString(largura - 1.5*cm, altura - 2.5*cm, "Validade: 15 dias")

    # Dados do Cliente
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

    # 1. EQUIPAMENTOS
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
            p.drawRightString(largura - 1.8*cm, y, to_br_currency(row['Venda Total']))
            y -= 0.5*cm
            if y < 4*cm: # Nova página se necessário
                p.showPage()
                y = altura - 3*cm

    # 2. SERVIÇOS (CORREÇÃO DE ALINHAMENTO)
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
    p.drawRightString(largura - 1.8*cm, y - 0.3*cm, to_br_currency(v_serv)) # VALOR ALINHADO À DIREITA

    # INVESTIMENTO TOTAL
    y -= 2*cm
    p.setFillColor(colors.HexColor("#004488"))
    p.rect(1.5*cm, y, largura - 3*cm, 1.2*cm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1.8*cm, y + 0.4*cm, "INVESTIMENTO TOTAL")
    p.drawRightString(largura - 1.8*cm, y + 0.4*cm, to_br_currency(total))

    # OBSERVAÇÕES
    y -= 1.5*cm
    p.setFillColor(colors.red)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.5*cm, y, "OBSERVAÇÕES:")
    p.setFont("Helvetica", 9)
    p.drawString(1.5*cm, y - 0.5*cm, obs)

    p.showPage()

    # =========================================================================
    # PÁGINA 3: ESCOPO DE SERVIÇOS
    # =========================================================================
    p.setFillColor(colors.HexColor("#f4f4f4"))
    p.rect(0, 0, largura, altura, fill=1, stroke=0)
    
    # Título da Página de Escopo
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(largura/2, altura - 2*cm, "CONHEÇA NOSSAS SOLUÇÕES")
    
    # Galeria de Imagens (Grid 2x2)
    def draw_service_box(x, y, img_url, title):
        try:
            p.drawImage(img_url, x, y, width=8*cm, height=6*cm, preserveAspectRatio=True)
            p.setFillColor(colors.HexColor("#004488"))
            p.rect(x, y - 1*cm, 8*cm, 0.8*cm, fill=1, stroke=0)
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 10)
            p.drawCentredString(x + 4*cm, y - 0.5*cm, title)
        except: pass

    # Linha 1
    draw_service_box(1.5*cm, altura - 9*cm, IMG_VACUO, "AQUECEDOR A VÁCUO")
    draw_service_box(largura - 9.5*cm, altura - 9*cm, IMG_TRADICIONAL, "SISTEMA TRADICIONAL")
    
    # Linha 2
    draw_service_box(1.5*cm, altura - 17*cm, IMG_PISCINA, "AQUECIMENTO DE PISCINA")
    draw_service_box(largura - 9.5*cm, altura - 17*cm, IMG_AR, "AR CONDICIONADO")

    p.save()
    buffer.seek(0)
    return buffer
