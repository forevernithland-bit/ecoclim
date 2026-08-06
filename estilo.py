# -*- coding: utf-8 -*-
"""
Design System do Ecoclim ERP (Parte 8).
Portado do sistema que o usuário aprovou (ERP Consorbens / modulos/tema.py):
fundo claro elegante, fontes Plus Jakarta Sans + Inter, botões verdes,
inputs nítidos, métricas em card, sidebar em pílulas e SELETOR DE COR do sistema.
Somente front-end — nenhuma regra de negócio aqui.

app.py usa: estilo.init_tema(), estilo.aplicar_tema(), estilo.render_seletor_tema_sidebar()
"""
import os
import base64
import streamlit as st

# ==========================================================
# PALETAS (o usuário troca pela engrenagem de cor na sidebar)
# ==========================================================
TEMAS = {
    "verde":    {"nome": "Esmeralda",   "emoji": "🟩", "brand": "#0f9d58", "dark": "#0b7c45", "glow": "15,157,88"},
    "teal":     {"nome": "Petróleo",    "emoji": "🟢", "brand": "#2c7a73", "dark": "#1f5b55", "glow": "44,122,115"},
    "azul":     {"nome": "Corporativo", "emoji": "🔵", "brand": "#2563eb", "dark": "#1d4ed8", "glow": "37,99,235"},
    "roxo":     {"nome": "Violeta",     "emoji": "🟣", "brand": "#7c3aed", "dark": "#6d28d9", "glow": "124,58,237"},
    "laranja":  {"nome": "Âmbar",       "emoji": "🟠", "brand": "#ea580c", "dark": "#c2410c", "glow": "234,88,12"},
    "vermelho": {"nome": "Rubi",        "emoji": "🔴", "brand": "#e74c3c", "dark": "#c0392b", "glow": "231,76,60"},
    "grafite":  {"nome": "Grafite",     "emoji": "⚫", "brand": "#334155", "dark": "#1e293b", "glow": "51,65,85"},
}
TEMA_PADRAO = "verde"


def init_tema():
    if "tema_cor" not in st.session_state:
        st.session_state.tema_cor = TEMA_PADRAO


def tema_atual():
    return TEMAS.get(st.session_state.get("tema_cor", TEMA_PADRAO), TEMAS[TEMA_PADRAO])


def render_seletor_tema_sidebar():
    """Popover na sidebar para escolher a cor do sistema."""
    with st.popover("🎨  Cor do sistema", use_container_width=True):
        st.caption("Escolha a identidade visual do painel.")
        for chave, cfg in TEMAS.items():
            marcado = "  ✓" if chave == st.session_state.get("tema_cor", TEMA_PADRAO) else ""
            if st.button(f"{cfg['emoji']}  {cfg['nome']}{marcado}", key=f"tema_{chave}", use_container_width=True):
                st.session_state.tema_cor = chave
                st.rerun()


def aplicar_tema():
    init_tema()
    st.markdown(montar_css(), unsafe_allow_html=True)


def montar_css(chave_tema=None):
    cfg = TEMAS.get(chave_tema or st.session_state.get("tema_cor", TEMA_PADRAO), TEMAS[TEMA_PADRAO])
    brand, dark, glow = cfg["brand"], cfg["dark"], cfg["glow"]
    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    :root {{
        --brand: {brand};
        --brand-dark: {dark};
        --brand-soft: rgba({glow}, 0.10);
        --brand-mid: rgba({glow}, 0.22);
        --brand-glow: rgba({glow}, 0.30);
        --green: #1fc17a; --green-dark: #14a866;
        --ink: #0f172a; --muted: #64748b; --line: #e9eef5;
        --field-line: #aeb9c9;
        --field-line: color-mix(in srgb, var(--brand) 22%, #94a3b8);
        --field-line-hover: color-mix(in srgb, var(--brand) 45%, #7c8a9e);
        --card: #ffffff;
        --shadow-sm: 0 1px 2px rgba(15,23,42,0.04), 0 4px 14px rgba(15,23,42,0.04);
        --shadow-md: 0 6px 24px rgba(15,23,42,0.07), 0 1px 2px rgba(15,23,42,0.04);
        --shadow-lg: 0 18px 45px rgba(15,23,42,0.13);
        --radius: 14px;
        --ease: cubic-bezier(0.22, 1, 0.36, 1);
    }}

    /* ---- Fundo claro elegante da marca ---- */
    .stApp {{
        background-color: #f4f7fb !important;
        background-image:
            radial-gradient(1100px 520px at 88% -12%, var(--brand-soft), transparent 60%),
            linear-gradient(180deg, #f7fafc 0%, #eef2f7 100%) !important;
        background-attachment: fixed !important;
    }}

    /* ---- Tipografia ---- */
    html, body, .stApp, [data-testid="stSidebar"], input, textarea, button, select, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }}
    h1, h2, h3, h4, h5, [data-testid="stMetricValue"] {{
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
        color: var(--ink); letter-spacing: -0.025em;
    }}
    [data-testid="stMain"] h1 {{ font-weight: 800 !important; font-size: 2rem !important; }}
    [data-testid="stMain"] h2 {{ font-weight: 800 !important; }}
    [data-testid="stMain"] h3 {{ font-weight: 700 !important; margin: 0.5rem 0 !important; }}
    .block-container {{ padding: 1.4rem 2.2rem 2.5rem !important; max-width: 1480px; }}

    [data-testid="stMain"] .block-container > div > div > div {{ animation: cbUp 0.45s var(--ease) both; }}
    @keyframes cbUp {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes cbPop {{ from {{ opacity: 0; transform: scale(0.97); }} to {{ opacity: 1; transform: scale(1); }} }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}

    /* ---- Botões ---- */
    .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button,
    [data-testid="stLinkButton"] a, [data-testid="stPopover"] button {{
        border-radius: 11px !important; font-weight: 600 !important; padding: 0.5rem 1.05rem !important;
        transition: transform 0.18s var(--ease), box-shadow 0.18s var(--ease),
                    background-color 0.18s var(--ease), border-color 0.18s var(--ease), color 0.18s var(--ease) !important;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stPopover"] button:hover {{
        transform: translateY(-2px); box-shadow: var(--shadow-md);
        border-color: var(--brand) !important; color: var(--brand) !important;
    }}
    .stButton > button:active {{ transform: translateY(0) scale(0.98); }}
    /* Primário = pílula branca com borda (outline) na cor do tema */
    button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
        background: #ffffff !important; color: var(--brand) !important;
        border: 1.6px solid var(--brand) !important; font-weight: 700 !important;
        border-radius: 999px !important; box-shadow: var(--shadow-sm) !important;
    }}
    button[kind="primary"]:hover {{
        transform: translateY(-2px) !important; background: var(--brand-soft) !important;
        color: var(--brand) !important; border-color: var(--brand-dark) !important; box-shadow: var(--shadow-md) !important;
    }}

    /* ---- Inputs ---- */
    .stTextInput div[data-baseweb="input"], .stNumberInput div[data-baseweb="input"],
    .stDateInput div[data-baseweb="input"], .stTextInput div[data-baseweb="base-input"],
    .stNumberInput div[data-baseweb="base-input"], div[data-baseweb="select"] > div,
    div[data-baseweb="input"], div[data-baseweb="base-input"], .stTextArea textarea, .stDateInput > div > div {{
        background-color: #ffffff !important; border: 1.5px solid var(--field-line) !important;
        border-radius: 11px !important; box-shadow: 0 1px 2px rgba(15,23,42,0.05) !important;
        transition: border-color 0.16s var(--ease), box-shadow 0.16s var(--ease) !important;
    }}
    .stTextInput input, .stNumberInput input, .stDateInput input,
    div[data-baseweb="input"] input, div[data-baseweb="base-input"] input, div[data-baseweb="select"] input {{
        background-color: transparent !important; border: none !important; color: var(--ink) !important;
    }}
    .stTextArea textarea {{ color: var(--ink) !important; }}
    .stTextInput div[data-baseweb="input"]:hover, .stNumberInput div[data-baseweb="input"]:hover,
    .stDateInput div[data-baseweb="input"]:hover, div[data-baseweb="select"] > div:hover,
    div[data-baseweb="base-input"]:hover, .stTextArea textarea:hover {{ border-color: var(--field-line-hover) !important; }}
    .stTextInput div[data-baseweb="input"]:focus-within, .stNumberInput div[data-baseweb="input"]:focus-within,
    .stDateInput div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="base-input"]:focus-within, .stTextArea textarea:focus {{
        border-color: var(--brand) !important; box-shadow: 0 0 0 3.5px var(--brand-soft) !important;
    }}
    .stNumberInput button {{ border: 1.5px solid var(--field-line) !important; background: #fff !important; }}
    .stNumberInput button:hover {{ border-color: var(--brand) !important; color: var(--brand) !important; }}
    input::placeholder, textarea::placeholder {{ color: #94a3b8 !important; opacity: 1 !important; }}
    [data-testid="stFileUploader"] section {{ border-radius: 14px !important; border: 1.5px dashed #cbd5e1 !important; transition: border-color 0.2s var(--ease), background-color 0.2s var(--ease); }}
    [data-testid="stFileUploader"] section:hover {{ border-color: var(--brand) !important; background: var(--brand-soft); }}

    /* ---- Métricas como cards ---- */
    [data-testid="stMetric"] {{
        background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 17px 19px;
        box-shadow: var(--shadow-sm); position: relative; overflow: hidden;
        transition: transform 0.24s var(--ease), box-shadow 0.24s var(--ease), border-color 0.24s var(--ease);
        animation: cbPop 0.4s var(--ease) both;
    }}
    [data-testid="stMetric"]::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: linear-gradient(180deg, var(--brand), var(--brand-dark)); opacity: 0; transition: opacity 0.24s var(--ease); }}
    [data-testid="stMetric"]:hover {{ transform: translateY(-4px); box-shadow: var(--shadow-lg); border-color: var(--brand-mid); }}
    [data-testid="stMetric"]:hover::before {{ opacity: 1; }}
    [data-testid="stMetricValue"] {{ font-size: 1.55rem !important; font-weight: 800 !important; white-space: normal !important; overflow: visible !important; line-height: 1.15 !important; }}
    [data-testid="stMetricValue"] > div {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}
    [data-testid="stMetricLabel"] {{ color: var(--muted) !important; font-weight: 600 !important; }}

    /* ---- Abas ---- */
    [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid var(--line); padding-bottom: 2px; }}
    button[data-baseweb="tab"] {{ font-size: 15px !important; font-weight: 600 !important; color: var(--muted) !important; border-radius: 11px 11px 0 0 !important; padding: 9px 17px !important; transition: background-color 0.2s var(--ease), color 0.2s var(--ease) !important; }}
    button[data-baseweb="tab"]:hover {{ background: #f1f5f9; color: var(--brand) !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ background: var(--brand-soft) !important; color: var(--brand) !important; }}
    [data-baseweb="tab-highlight"] {{ background: var(--brand) !important; height: 3px !important; border-radius: 3px; }}
    [data-testid="stTabPanel"] {{ animation: cbUp 0.35s var(--ease) both; }}

    /* ---- Expanders / formulários / cards ---- */
    [data-testid="stExpander"] {{ border: 1px solid var(--line) !important; border-radius: 16px !important; box-shadow: var(--shadow-sm); background: var(--card); overflow: hidden; transition: box-shadow 0.24s var(--ease), border-color 0.24s var(--ease); }}
    [data-testid="stExpander"]:hover {{ box-shadow: var(--shadow-md); border-color: var(--brand-mid) !important; }}
    [data-testid="stExpander"] summary {{ font-weight: 600 !important; transition: color 0.18s var(--ease); }}
    [data-testid="stExpander"] summary:hover {{ color: var(--brand) !important; }}
    [data-testid="stForm"] {{ border: 1px solid var(--line) !important; border-radius: 18px !important; padding: 24px !important; box-shadow: var(--shadow-md); background: var(--card); }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 16px; }}

    [data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stDataEditor"] {{ border-radius: 14px !important; overflow: hidden; border: 1px solid var(--line) !important; box-shadow: var(--shadow-sm); }}
    [data-testid="stAlert"] {{ border-radius: 13px !important; border: none !important; box-shadow: var(--shadow-sm); }}
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 10px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: var(--brand); }}

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {{ border-right: 1px solid var(--line) !important; box-shadow: 6px 0 28px rgba(15,23,42,0.04); }}
    [data-testid="stSidebar"] > div:first-child {{ background: linear-gradient(180deg, #ffffff 0%, #fafbfd 100%) !important; }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {{ color: #0f172a !important; }}
    [data-testid="stSidebar"] hr {{ border-bottom-color: var(--line) !important; margin: 0.5rem 0 !important; }}
    [data-testid="stSidebar"] button {{ border: 1px solid #cbd5e1 !important; background-color: #f8fafc !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{ padding: 6px 12px !important; border-radius: 10px !important; margin: 1.5px 0 !important; position: relative; overflow: hidden; transition: background-color 0.2s var(--ease), color 0.2s var(--ease), transform 0.2s var(--ease) !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label::before {{ content: ""; position: absolute; left: 0; top: 18%; bottom: 18%; width: 3px; border-radius: 3px; background: var(--brand); transform: scaleY(0); transition: transform 0.25s var(--ease); }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background-color: #f1f5f9 !important; transform: translateX(2px); }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover p {{ color: var(--brand) !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{ background-color: var(--brand-soft) !important; }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before {{ transform: scaleY(1); }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {{ color: var(--brand) !important; font-weight: 700 !important; }}
    header[data-testid="stHeader"] {{ background-color: transparent !important; }}

    /* ---- Componentes utilitários (Home) ---- */
    .eco-hero {{ background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--brand);
        border-radius: 16px; padding: 16px 22px; box-shadow: var(--shadow-sm); position: relative; overflow: hidden; margin-bottom: 16px; }}
    .eco-hero::after {{ content: ""; position: absolute; right: -30px; top: -46px; width: 170px; height: 170px; border-radius: 50%; background: radial-gradient(circle at 42% 42%, var(--brand-soft), transparent 70%); }}
    .eco-hero .chip {{ display: inline-block; background: var(--brand-soft); color: var(--brand); border: 1px solid var(--brand-mid); padding: 3px 11px; border-radius: 999px; font-size: .72rem; font-weight: 700; letter-spacing: .05em; }}
    .eco-hero .htitle {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.4rem; color: var(--ink); margin: 10px 0 2px; letter-spacing: -.02em; }}
    .eco-hero .sub {{ color: var(--muted); font-size: .92rem; }}
    .eco-sectiontitle {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; color: var(--ink); font-size: 1.08rem; display: flex; align-items: center; gap: 8px; margin: 10px 0 12px; letter-spacing: -.02em; }}
    .eco-sectiontitle::before {{ content: ""; width: 4px; height: 18px; border-radius: 3px; background: linear-gradient(180deg, var(--brand), var(--brand-dark)); }}

    /* ================= RESPONSIVIDADE (mobile / tablet) ================= */
    @media screen and (max-width: 820px) {{
        .block-container {{ padding: 1rem 0.7rem 2rem !important; }}
        div[data-testid="stHorizontalBlock"] {{ flex-direction: column !important; align-items: stretch !important; }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{ width: 100% !important; min-width: 100% !important; flex: 1 1 100% !important; }}
        .stTextInput, .stNumberInput, .stTextArea, div[data-baseweb="select"] {{ width: 100% !important; }}
        .stButton > button {{ min-height: 48px !important; font-size: 1rem !important; width: 100% !important; }}
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ overflow-x: auto !important; }}
        [data-testid="stMetricValue"] {{ font-size: 1.3rem !important; }}
    }}
</style>
"""


def _login_svg_b64():
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "login_bg.svg")
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


def css_fundo_login():
    """CSS da tela de login: fundo claro da marca + cena ilustrada no rodapé
    (estilo ERP Consorbens). Vem DEPOIS de aplicar_tema(), então usa var(--brand)."""
    b64 = _login_svg_b64()
    camada = f'url("data:image/svg+xml;base64,{b64}"), ' if b64 else ""
    return f"""
<style>
    [data-testid="stSidebar"], header[data-testid="stHeader"] {{ display:none !important; }}
    [data-testid="stAppViewContainer"] {{
        background-color:#e9f4ee !important;
        background-image: {camada}
            radial-gradient(1100px 460px at 85% -12%, var(--brand-soft), transparent 60%),
            linear-gradient(180deg, #f5faf7 0%, #e3efe9 100%) !important;
        background-position: bottom center, center, center !important;
        background-size: 100% auto, cover, cover !important;
        background-repeat: no-repeat, no-repeat, no-repeat !important;
        background-attachment: fixed, fixed, fixed !important;
    }}
    [data-testid="stAppViewContainer"]::after {{ content: none !important; }}
    .block-container {{ padding-top: 6vh !important; }}
    /* Cartão do login */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background:#ffffff !important; border:1px solid #e6ebf3 !important; border-radius:20px !important;
        box-shadow:0 24px 55px rgba(15,23,42,0.16) !important; padding:2.3rem 2.1rem !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]::before {{ content:none !important; }}
    .login-head {{ text-align:center; margin:6px 0 16px; }}
    .login-head .wel {{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.5rem; color:var(--ink); letter-spacing:-.02em; }}
    .login-head .sub {{ color:var(--muted); font-size:.95rem; margin-top:2px; }}
    div[data-testid="stVerticalBlockBorderWrapper"] label {{ color:#33414f !important; font-weight:600 !important; }}
    /* Botão ENTRAR — cor da marca */
    .login-btn-container div.stButton > button {{
        background: linear-gradient(135deg, var(--brand), var(--brand-dark)) !important; color:#fff !important;
        border:none !important; border-radius:11px !important; font-weight:700 !important; min-height:46px !important;
        letter-spacing:.3px !important; box-shadow: 0 8px 20px var(--brand-glow) !important; transition: all .2s ease !important;
    }}
    .login-btn-container div.stButton > button:hover {{ transform:translateY(-2px); filter:brightness(1.05); color:#fff !important; }}
    .login-chips {{ display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin-top:18px; }}
    .login-chips span {{ font-size:.72rem; font-weight:700; color:var(--muted); background:var(--brand-soft);
        border:1px solid var(--brand-mid); padding:5px 11px; border-radius:999px; }}
    .login-foot {{ text-align:center; color:#94a3b8; font-size:.74rem; margin-top:12px; }}
    @media screen and (max-width:768px) {{
        .block-container {{ padding-left:1rem !important; padding-right:1rem !important; }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1),
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) {{ display:none !important; }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {{ width:100% !important; min-width:100% !important; }}
    }}
</style>
"""


# Compat: mantido caso algo ainda chame; a Home usa st.metric agora.
def kpi_html(icone, valor, rotulo, rodape=""):
    return (f"<div style='background:var(--card);border:1px solid var(--line);border-radius:16px;"
            f"padding:15px 17px;box-shadow:var(--shadow-sm);'>"
            f"<div style='font-size:18px'>{icone}</div>"
            f"<div style='color:var(--muted);font-size:.72rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:.05em;margin-top:8px'>{rotulo}</div>"
            f"<div style='font-family:\"Plus Jakarta Sans\";font-weight:800;font-size:1.5rem;color:var(--ink)'>{valor}</div>"
            f"<div style='color:var(--muted);font-size:.74rem'>{rodape}</div></div>")
