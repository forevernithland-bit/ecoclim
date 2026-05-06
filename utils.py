import streamlit as st
import pandas as pd
import numpy as np
import datetime
import re
import os
import io
from supabase import create_client
from fpdf import FPDF

# Meses Globais
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

# (Aqui depois vamos colocar também as funções do Banco de Dados e PDF que estavam soltas no app.py)
