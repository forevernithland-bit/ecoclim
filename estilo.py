# -*- coding: utf-8 -*-
"""
Design System global do Ecoclim ERP (Parte 8).
Somente front-end: injeta o tema (claro/escuro), fontes, componentes e
responsividade. Não contém regra de negócio.

Uso no app.py (após st.set_page_config e antes do resto):
    import estilo
    estilo.init_tema()          # garante st.session_state.tema
    estilo.aplicar_tema()       # injeta o CSS global

Paleta alinhada à logo (verde + dourado) e ao PDF (grafite).
"""
import streamlit as st

VERDE = "#6FA218"
VERDE_CLARO = "#8CC63F"
DOURADO = "#E4A100"
GRAFITE = "#2b3440"
GRAFITE_DEEP = "#171c24"


def init_tema():
    if "tema" not in st.session_state:
        st.session_state.tema = "claro"


def alternar_tema():
    st.session_state.tema = "escuro" if st.session_state.get("tema") == "claro" else "claro"


def _tokens(tema: str) -> str:
    if tema == "escuro":
        # Dark "preto & dourado" (luxo): base grafite/preta, dourado como acento.
        return """
      --bg:#15171d; --bg-grad1:#15171d; --bg-grad2:#0e0f14;
      --surface:#1c1f27; --surface-2:#242833; --surface-3:#2e333f;
      --ink:#efeee9; --ink-soft:#d6d3ca; --muted:#a29c8f; --hair:#2f333d; --hair-2:#3d4250;
      --primary:#E7B84A; --primary-d:#C6912A; --primary-ink:#1a1610;
      --accent:#F6D488; --accent-soft:#3a3220;
      --graphite:#2b3039; --brandbar1:#14161c; --brandbar2:#2b2f39;
      --good:#3ecf8e; --warn:#f5b301; --bad:#ff6b78;
      --shadow-sm:0 1px 2px rgba(0,0,0,.5);
      --shadow:0 12px 30px rgba(0,0,0,.6);
      --shadow-lg:0 18px 48px rgba(0,0,0,.66);
      --ring:rgba(231,184,74,.35);
      --kpi-glow:rgba(231,184,74,.20);
      --primary-tint:rgba(231,184,74,.16);
      --cta:#E7B84A; --cta-ink:#1a1610; --cta-hover:#f0c766;
        """
    # Claro "tech-luxe" (PADRÃO): base clara/clean, azul elétrico + dourado, grafite no hero.
    return """
      --bg:#f5f8fc; --bg-grad1:#f5f8fc; --bg-grad2:#eaf1f9;
      --surface:#ffffff; --surface-2:#f5f9fd; --surface-3:#eaf1fa;
      --ink:#141a24; --ink-soft:#2b3444; --muted:#69748a; --hair:#e6ebf3; --hair-2:#dbe3ef;
      --primary:#1573FF; --primary-d:#0E57D0; --primary-ink:#ffffff;
      --accent:#E4A100; --accent-soft:#fbf1d6;
      --graphite:#141a26; --brandbar1:#141a26; --brandbar2:#1f2b45;
      --good:#1f8a4c; --warn:#b8860b; --bad:#d64550;
      --shadow-sm:0 1px 2px rgba(20,26,40,.06);
      --shadow:0 10px 28px rgba(21,80,200,.12);
      --shadow-lg:0 18px 48px rgba(21,80,200,.16);
      --ring:rgba(21,115,255,.28);
      --kpi-glow:rgba(6,182,212,.18);
      --primary-tint:rgba(21,115,255,.12);
      --cta:#141a26; --cta-ink:#ffffff; --cta-hover:#20293a;
        """


def aplicar_tema():
    init_tema()
    tema = st.session_state.get("tema", "claro")
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@500;600;700;800&display=swap');

    :root{
    %TOKENS%
      --font-body:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
      --font-head:'Poppins','Inter',-apple-system,'Segoe UI',sans-serif;
      --r-sm:8px; --r:12px; --r-lg:16px; --r-xl:22px;
      --t:180ms cubic-bezier(.2,.7,.3,1);
    }

    html, body, [class*="css"], .stApp, .block-container { font-family:var(--font-body); }
    .stApp{
      background:
        radial-gradient(1200px 600px at 88% -8%, var(--kpi-glow), transparent 60%),
        linear-gradient(180deg, var(--bg-grad1), var(--bg-grad2));
      color:var(--ink);
    }
    .block-container{ padding-top:2.4rem !important; padding-left:2rem !important; padding-right:2rem !important; max-width:100% !important; }

    h1,h2,h3,h4,h5{ font-family:var(--font-head) !important; color:var(--ink) !important; letter-spacing:.2px; font-weight:700; }
    h1{ font-size:1.9rem; } h2{ font-size:1.5rem; } h3{ font-size:1.22rem; }
    p, span, label, .stMarkdown, .stCaption, div[data-testid="stCaptionContainer"]{ color:var(--ink); }
    small, .stCaption, div[data-testid="stCaptionContainer"] p{ color:var(--muted) !important; }
    a{ color:var(--primary-d); }

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"]{
      background:linear-gradient(180deg, var(--surface), var(--surface-2)) !important;
      border-right:1px solid var(--hair);
    }
    [data-testid="stSidebar"] .block-container{ padding-top:1.2rem !important; }
    [data-testid="stSidebar"] img{ filter:drop-shadow(0 4px 10px rgba(0,0,0,.10)); }

    /* ---------- Radio como itens de menu (sidebar) ---------- */
    [data-testid="stSidebar"] div[role="radiogroup"]{ gap:4px; display:flex; flex-direction:column; }
    [data-testid="stSidebar"] div[role="radiogroup"] label{
      border:1px solid transparent; border-radius:10px; padding:9px 12px !important; margin:0 !important;
      transition:var(--t); cursor:pointer; font-weight:600; color:var(--ink-soft) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover{ background:var(--surface-3); border-color:var(--hair-2); }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
      background:linear-gradient(135deg, var(--primary), var(--primary-d));
      color:var(--primary-ink) !important; border-color:transparent; box-shadow:var(--shadow-sm);
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) *{ color:var(--primary-ink) !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] input{ position:absolute; opacity:0; }

    /* ---------- Botões ---------- */
    div.stButton > button{
      font-family:var(--font-body); font-weight:600; border-radius:var(--r) !important;
      transition:var(--t) !important; letter-spacing:.2px;
    }
    /* Primário = CTA refinado (grafite no claro, dourado no escuro; azul só acento) */
    div.stButton > button[kind="primary"]{
      background:var(--cta) !important; color:var(--cta-ink) !important; border:1px solid transparent !important;
      box-shadow:var(--shadow-sm) !important; min-height:40px !important; font-weight:600 !important;
    }
    div.stButton > button[kind="primary"]:hover{ background:var(--cta-hover) !important; transform:translateY(-1px); box-shadow:var(--shadow) !important; }
    div.stButton > button[kind="primary"]:active{ transform:translateY(0); }
    /* Secundário = superfície/card */
    div.stButton > button[kind="secondary"]{
      background:var(--surface) !important; color:var(--ink) !important;
      border:1px solid var(--hair-2) !important; box-shadow:var(--shadow-sm) !important; min-height:42px !important;
    }
    div.stButton > button[kind="secondary"]:hover{ border-color:var(--primary) !important; color:var(--primary-d) !important; transform:translateY(-2px); box-shadow:var(--shadow) !important; }
    div.stButton > button:focus-visible{ outline:3px solid var(--ring) !important; outline-offset:2px; }
    div.stDownloadButton > button{
      background:var(--graphite) !important; color:#fff !important; border:none !important; border-radius:var(--r) !important;
      font-weight:600; transition:var(--t) !important;
    }
    div.stDownloadButton > button:hover{ transform:translateY(-2px); box-shadow:var(--shadow) !important; }

    /* ---------- Inputs ---------- */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, div[data-baseweb="select"] > div, .stDateInput input{
      background:var(--surface) !important; color:var(--ink) !important;
      border:1px solid var(--hair-2) !important; border-radius:var(--r-sm) !important; transition:var(--t) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus{
      border-color:var(--primary) !important; box-shadow:0 0 0 3px var(--ring) !important;
    }
    div[data-baseweb="select"] > div:focus-within{ border-color:var(--primary) !important; box-shadow:0 0 0 3px var(--ring) !important; }
    label, .stCheckbox label, .stRadio label{ font-weight:600; }

    /* ---------- Cards (containers com borda) ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"]{
      background:var(--surface) !important; border:1px solid var(--hair) !important; border-radius:var(--r-lg) !important;
      box-shadow:var(--shadow-sm); transition:var(--t); padding:1.1rem 1.15rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover{ box-shadow:var(--shadow); }

    /* ---------- Métricas como KPI ---------- */
    div[data-testid="stMetric"]{
      background:var(--surface); border:1px solid var(--hair); border-radius:var(--r);
      padding:14px 16px; box-shadow:var(--shadow-sm); transition:var(--t);
    }
    div[data-testid="stMetric"]:hover{ transform:translateY(-2px); box-shadow:var(--shadow); border-color:var(--hair-2); }
    div[data-testid="stMetricLabel"] p{ color:var(--muted) !important; font-weight:600; letter-spacing:.04em; text-transform:uppercase; font-size:.72rem !important; }
    div[data-testid="stMetricValue"]{ font-family:var(--font-head); font-weight:700; color:var(--ink) !important;
      font-size:1.35rem !important; white-space:normal !important; overflow:visible !important; line-height:1.15 !important; }
    div[data-testid="stMetricValue"] > div{ white-space:normal !important; overflow:visible !important; text-overflow:clip !important; }

    /* ---------- Tabs ---------- */
    button[data-baseweb="tab"]{ font-weight:600; color:var(--muted); }
    button[data-baseweb="tab"][aria-selected="true"]{ color:var(--primary-d) !important; }
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] ~ div{ background:var(--primary) !important; }

    /* ---------- Expander ---------- */
    div[data-testid="stExpander"]{ border:1px solid var(--hair) !important; border-radius:var(--r) !important; overflow:hidden; background:var(--surface); }
    div[data-testid="stExpander"] summary{ font-weight:600; }
    div[data-testid="stExpander"] summary:hover{ color:var(--primary-d); }

    /* ---------- Tabelas / data editor ---------- */
    .stDataFrame, div[data-testid="stDataFrame"], div[data-testid="stDataEditor"]{ border-radius:var(--r); overflow:hidden; }
    div[data-testid="stDataFrame"] thead, div[data-testid="stDataEditor"] thead{ background:var(--surface-2); }
    div[data-testid="stAlert"]{ border-radius:var(--r); }

    /* ---------- Scrollbar ---------- */
    ::-webkit-scrollbar{ width:10px; height:10px; }
    ::-webkit-scrollbar-thumb{ background:var(--hair-2); border-radius:20px; }
    ::-webkit-scrollbar-thumb:hover{ background:var(--muted); }

    /* ---------- Componentes utilitários (HTML custom) ---------- */
    .eco-hero{
      background:linear-gradient(135deg, var(--surface), var(--surface-2));
      border:1px solid var(--hair); border-left:4px solid var(--primary);
      border-radius:var(--r-lg); padding:16px 22px; color:var(--ink); position:relative; overflow:hidden;
      box-shadow:var(--shadow-sm); margin-bottom:16px;
    }
    .eco-hero::after{ content:""; position:absolute; right:-30px; top:-46px; width:170px; height:170px; border-radius:50%;
      background:radial-gradient(circle at 42% 42%, var(--kpi-glow), transparent 70%); }
    .eco-hero .chip{ display:inline-block; background:var(--surface-3); color:var(--muted); border:1px solid var(--hair-2);
      padding:3px 11px; border-radius:999px; font-size:.72rem; font-weight:700; letter-spacing:.06em; }
    .eco-hero .htitle{ font-family:var(--font-head); font-weight:800; font-size:1.3rem; color:var(--ink); margin:9px 0 2px; }
    .eco-hero .sub{ color:var(--muted); font-size:.9rem; }

    .eco-kpi{ background:var(--surface); border:1px solid var(--hair); border-radius:var(--r-lg); padding:16px 18px;
      box-shadow:var(--shadow-sm); transition:var(--t); position:relative; overflow:hidden; height:100%; }
    .eco-kpi:hover{ transform:translateY(-3px); box-shadow:var(--shadow); }
    .eco-kpi .ic{ width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center; font-size:19px;
      background:var(--primary-tint); color:var(--primary); }
    .eco-kpi .lbl{ color:var(--muted); font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-top:10px; }
    .eco-kpi .val{ font-family:var(--font-head); font-weight:800; font-size:1.55rem; color:var(--ink); line-height:1.1; }
    .eco-kpi .foot{ color:var(--muted); font-size:.74rem; margin-top:2px; }
    .eco-kpi .bar{ position:absolute; left:0; top:0; bottom:0; width:4px; background:linear-gradient(180deg,var(--primary),var(--accent)); }

    .eco-shortcut{ display:flex; gap:12px; align-items:center; background:var(--surface); border:1px solid var(--hair);
      border-radius:var(--r-lg); padding:16px; box-shadow:var(--shadow-sm); transition:var(--t); height:100%; }
    .eco-shortcut:hover{ transform:translateY(-3px); box-shadow:var(--shadow); border-color:var(--primary); }
    .eco-shortcut .ic{ width:46px; height:46px; min-width:46px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:22px;
      background:var(--surface-3); }
    .eco-shortcut .t{ font-family:var(--font-head); font-weight:700; color:var(--ink); font-size:1rem; }
    .eco-shortcut .d{ color:var(--muted); font-size:.8rem; }

    .eco-sectiontitle{ font-family:var(--font-head); font-weight:700; color:var(--ink); font-size:1.05rem;
      display:flex; align-items:center; gap:8px; margin:6px 0 10px; }
    .eco-sectiontitle::before{ content:""; width:4px; height:18px; border-radius:3px; background:linear-gradient(180deg,var(--primary),var(--accent)); }

    /* ---------- Animação ---------- */
    @keyframes ecoFade{ from{opacity:0; transform:translateY(8px);} to{opacity:1; transform:none;} }
    .main .block-container > div{ animation:ecoFade .35s ease both; }
    @media (prefers-reduced-motion:reduce){ *{ animation:none !important; transition:none !important; } }

    /* ================= RESPONSIVIDADE (mobile / tablet) ================= */
    @media screen and (max-width:820px){
      .block-container{ padding-left:.7rem !important; padding-right:.7rem !important; padding-top:1.6rem !important; }
      /* empilha colunas */
      div[data-testid="stHorizontalBlock"]{ flex-direction:column !important; align-items:stretch !important; }
      div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{ width:100% !important; min-width:100% !important; flex:1 1 100% !important; }
      /* inputs e botões cheios e "touch" */
      .stTextInput, .stNumberInput, .stTextArea, div[data-baseweb="select"]{ width:100% !important; }
      div.stButton > button{ min-height:48px !important; font-size:1rem !important; width:100% !important; }
      /* tabelas rolam horizontalmente dentro do próprio container */
      div[data-testid="stDataFrame"], div[data-testid="stDataEditor"]{ overflow-x:auto !important; }
      .eco-hero{ padding:18px; } .eco-hero h2{ font-size:1.25rem; }
      div[data-testid="stMetricValue"]{ font-size:1.3rem !important; }
    }
    </style>
    """
    css = css.replace("%TOKENS%", _tokens(tema))
    st.markdown(css, unsafe_allow_html=True)


def toggle_tema_sidebar():
    """Botão de alternância claro/escuro para colocar na sidebar."""
    tema = st.session_state.get("tema", "claro")
    rotulo = "🌙  Modo escuro" if tema == "claro" else "☀️  Modo claro"
    if st.button(rotulo, use_container_width=True, key="btn_toggle_tema"):
        alternar_tema()
        st.rerun()


# ---------- helpers de HTML para a Home ----------
def kpi_html(icone, valor, rotulo, rodape=""):
    return (f"<div class='eco-kpi'><div class='bar'></div>"
            f"<div class='ic'>{icone}</div>"
            f"<div class='lbl'>{rotulo}</div>"
            f"<div class='val'>{valor}</div>"
            f"<div class='foot'>{rodape}</div></div>")
