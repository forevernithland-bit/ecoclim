"""Base fundamentalista de ações da B3, montada a partir dos DADOS ABERTOS DA CVM
(gratuitos, oficiais): lucro líquido anual, quantidade de ações, setor e os
tickers de cada companhia aberta. É o que permite checar, sem nenhuma
assinatura paga, "lucro nos últimos 7 anos consecutivos" para qualquer ação.

Pesado de propósito (baixa ~90 MB de zips da CVM), então NÃO roda a cada
abertura da tela: gera um JSON compacto que fica guardado no Supabase
(`fin_configuracoes`, chave `acoes_base_fundamentos`) e é relido pela aba Ações.
Atualizar 1x por ano (quando saem os balanços anuais, ~março/abril) ou pelo
botão da própria aba:

    python acoes_base.py            # baixa, monta e grava no Supabase

Módulo sem Streamlit.
"""
import datetime
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile

import pandas as pd

CVM = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
CACHE = os.path.join(tempfile.gettempdir(), "ecoclim_cvm_cache")
CHAVE_SUPABASE = "acoes_base_fundamentos"
ANOS_EXIGIDOS = 7

# Setor da CVM -> grupo "amigável" da carteira (o usuário pode trocar o grupo de
# cada ação à mão; isto é só o palpite inicial).
_GRUPOS = [
    (r"^bancos", "Bancos"),
    (r"seguradoras", "Seguros e Corretoras"),
    (r"intermedia|arrendamento|emp\. adm\. part\. - intermedia", "Financeiro (outros)"),
    (r"energia el", "Energia Elétrica"),
    (r"saneamento", "Saneamento"),
    (r"petr[óo]leo e g", "Petróleo e Gás"),
    (r"extra[çc][ãa]o mineral", "Mineração"),
    (r"metalurgia", "Siderurgia e Metalurgia"),
    (r"bebidas", "Bebidas"),
    (r"alimentos", "Alimentos"),
    (r"agricultura", "Agro"),
    (r"telecom", "Telecomunicações"),
    (r"com[ée]rcio", "Varejo e Comércio"),
    (r"papel e celulose", "Papel e Celulose"),
    (r"transporte e log", "Transporte e Logística"),
    (r"constru[çc][ãa]o civil|const\. civil|explora[çc][ãa]o de im[óo]veis", "Construção e Imóveis"),
    (r"m[ée]dicos|farmac", "Saúde"),
    (r"petroqu[íi]micos", "Química"),
    (r"m[áa]quinas|m[áa]qs|outras atividades industriais|embalagens", "Indústria"),
    (r"bolsas de valores|cr[ée]dito imobili", "Financeiro (outros)"),
    (r"comunica[çc][ãa]o e inform", "Tecnologia"),
    (r"t[êe]xtil", "Têxtil e Vestuário"),
    (r"educa[çc][ãa]o", "Educação"),
    (r"hospedagem|brinquedos", "Turismo e Lazer"),
]


# A FCA da CVM não lista o ticker de algumas companhias (cadastro opcional).
# Complemento manual: ticker -> CNPJ. Acrescente aqui quando notar uma lacuna.
TICKERS_EXTRAS = {
    "CSNA3": "33.042.730/0001-04",
    "BPAC11": "30.306.294/0001-45", "BPAC3": "30.306.294/0001-45", "BPAC5": "30.306.294/0001-45",
}


# Correções de grupo por ticker (a classificação da CVM erra alguns casos conhecidos).
GRUPO_MANUAL = {"VBBR3": "Petróleo e Gás", "CSAN3": "Petróleo e Gás", "ALOS3": "Construção e Imóveis", "B3SA3": "Financeiro (outros)"}


def grupo_do_setor(setor_cvm):
    s = re.sub(r"^emp\. adm\. part\. - ", "", str(setor_cvm or "").lower())
    for padrao, grupo in _GRUPOS:
        if re.search(padrao, s):
            return grupo
    return "Outros"


def _baixar(url, nome):
    os.makedirs(CACHE, exist_ok=True)
    caminho = os.path.join(CACHE, nome)
    velho = os.path.exists(caminho) and (datetime.datetime.now().timestamp() - os.path.getmtime(caminho)) > 7 * 86400 and str(datetime.date.today().year - 1) in nome
    if not os.path.exists(caminho) or os.path.getsize(caminho) < 1000 or velho:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            dados = r.read()
        with open(caminho, "wb") as f:
            f.write(dados)
    return caminho


def _csv(zf, sufixo, **kw):
    nome = next((n for n in zf.namelist() if n.endswith(sufixo)), None)
    if not nome:
        return None
    return pd.read_csv(zf.open(nome), sep=";", encoding="latin1", dtype=str, **kw)


_RE_LL = re.compile(r"^lucro( ou |/)preju[íi]zo( l[íi]quido)?( consolidado)?( do (per[íi]odo|exerc[íi]cio))$", re.I)


def _lucro_do_ano(dre):
    """Lucro líquido (R$) por CNPJ nas linhas ÚLTIMO exercício de uma DRE.
    Prefere o "atribuído a sócios da controladora" (é o que pertence ao
    acionista), mas só se estiver preenchido: várias companhias deixam essa
    linha zerada e o lucro real fica só no total do período."""
    d = dre[dre["ORDEM_EXERC"].str.upper().str.startswith(("ÚLTIMO", "ULTIMO"), na=False)].copy()
    d["VERSAO"] = pd.to_numeric(d["VERSAO"], errors="coerce").fillna(0)
    d["VL"] = pd.to_numeric(d["VL_CONTA"], errors="coerce") * d["ESCALA_MOEDA"].map(lambda x: 1000 if str(x).upper() == "MIL" else 1)
    saida = {}
    for cnpj, g in d.groupby("CNPJ_CIA"):
        g = g[g["VERSAO"] == g["VERSAO"].max()]
        cons = g[g["DS_CONTA"].str.strip().map(lambda t: bool(_RE_LL.match(str(t)))) & (g["CD_CONTA"].str.count(r"\.") == 1)]
        if cons.empty:
            continue
        cod = cons.iloc[0]["CD_CONTA"]
        valor = cons.iloc[0]["VL"]
        ctrl = g[(g["CD_CONTA"] == f"{cod}.01") & g["DS_CONTA"].str.contains("ontrolador", na=False)]
        if not ctrl.empty and pd.notna(ctrl.iloc[0]["VL"]) and ctrl.iloc[0]["VL"] != 0:
            valor = ctrl.iloc[0]["VL"]
        if pd.notna(valor):
            saida[cnpj] = float(valor)
    return saida


def _normalizar_acoes(serie):
    """A CVM mistura "unidades" e "milhares" na quantidade de ações de um ano
    pra outro (ex.: PETR4 13.044 em 2020 e 13.044.200 depois). Alinha todos
    os anos à escala do ano mais recente quando a razão é ~1000."""
    if not serie:
        return serie
    ref = serie[max(serie)]
    saida = {}
    for a, v in serie.items():
        for f in (1, 1000, 0.001):
            if ref / 3 <= v * f <= ref * 3:
                v = v * f
                break
        saida[a] = v
    return saida


def construir_base(ano_final=None, anos=ANOS_EXIGIDOS, progresso=None):
    """Devolve o dict da base. `ano_final` = último exercício a procurar."""
    def avisa(msg):
        if progresso:
            progresso(msg)
    hoje = datetime.date.today()
    # a DFP do ano anterior só existe depois de ~abril
    ano_final = ano_final or (hoje.year - 1 if hoje.month >= 4 else hoje.year - 2)
    lista_anos = list(range(ano_final - anos + 1, ano_final + 1))

    lucros, acoes = {}, {}
    for ano in lista_anos:
        avisa(f"Baixando balanços de {ano}…")
        try:
            zf = zipfile.ZipFile(_baixar(f"{CVM}/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip", f"dfp_{ano}.zip"))
        except Exception as e:
            avisa(f"  {ano} indisponível ({str(e)[:60]})")
            continue
        dre = _csv(zf, f"DRE_con_{ano}.csv")
        dre_ind = _csv(zf, f"DRE_ind_{ano}.csv")
        por_cnpj = _lucro_do_ano(dre) if dre is not None else {}
        if dre_ind is not None:  # companhia que só publica individual
            for cnpj, v in _lucro_do_ano(dre_ind).items():
                if not por_cnpj.get(cnpj):  # ausente OU zerado no consolidado -> usa o individual
                    por_cnpj[cnpj] = v
        for cnpj, v in por_cnpj.items():
            lucros.setdefault(cnpj, {})[str(ano)] = v
        cc = _csv(zf, f"composicao_capital_{ano}.csv")
        if cc is not None:
            cc["VERSAO"] = pd.to_numeric(cc["VERSAO"], errors="coerce").fillna(0)
            cc = cc.sort_values("VERSAO").drop_duplicates("CNPJ_CIA", keep="last")
            for _, r in cc.iterrows():
                try:
                    total = float(r["QT_ACAO_TOTAL_CAP_INTEGR"]) - float(r["QT_ACAO_TOTAL_TESOURO"] or 0)
                    if total > 0:
                        acoes.setdefault(r["CNPJ_CIA"], {})[str(ano)] = total
                except (TypeError, ValueError):
                    pass

    avisa("Lendo cadastro e tickers…")
    req = urllib.request.Request(f"{CVM}/CAD/DADOS/cad_cia_aberta.csv", headers={"User-Agent": "Mozilla/5.0"})
    cad = pd.read_csv(io.BytesIO(urllib.request.urlopen(req, timeout=120).read()), sep=";", encoding="latin1", dtype=str)
    cad = cad[["CNPJ_CIA", "DENOM_SOCIAL", "DENOM_COMERC", "SETOR_ATIV", "SIT"]].drop_duplicates("CNPJ_CIA")
    info = cad.set_index("CNPJ_CIA").to_dict("index")

    tickers = {}
    for ano in (ano_final + 1, ano_final, ano_final - 1):
        try:
            fca = zipfile.ZipFile(_baixar(f"{CVM}/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip", f"fca_{ano}.zip"))
        except Exception:
            continue
        vm = _csv(fca, f"valor_mobiliario_{ano}.csv")
        if vm is None:
            continue
        vm = vm[vm["Valor_Mobiliario"].isin(["Ações Ordinárias", "Ações Preferenciais", "Units"]) & (vm["Mercado"] == "Bolsa")]
        vm = vm[vm["Codigo_Negociacao"].notna() & vm["Data_Fim_Negociacao"].isna()]
        for _, r in vm.iterrows():
            tk = str(r["Codigo_Negociacao"]).strip().upper()
            if re.fullmatch(r"[A-Z][A-Z0-9]{3}\d{1,2}", tk):
                tickers[tk] = r["CNPJ_Companhia"]
        break

    for tk, cnpj in TICKERS_EXTRAS.items():
        tickers.setdefault(tk, cnpj)

    empresas = {}
    manual_cnpj = {tickers[t]: g for t, g in GRUPO_MANUAL.items() if t in tickers}
    for cnpj in set(tickers.values()):
        i = info.get(cnpj, {})
        empresas[cnpj] = {
            "n": (i.get("DENOM_COMERC") if isinstance(i.get("DENOM_COMERC"), str) else None) or i.get("DENOM_SOCIAL") or cnpj,
            "s": i.get("SETOR_ATIV"), "g": manual_cnpj.get(cnpj) or grupo_do_setor(i.get("SETOR_ATIV")),
            "l": {a: round(v / 1e6, 2) for a, v in lucros.get(cnpj, {}).items()},
            "a": {a: round(v / 1e6, 4) for a, v in _normalizar_acoes(acoes.get(cnpj, {})).items()},
        }
    return {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "anos": lista_anos, "fonte": "CVM — Dados Abertos (DFP/FCA/Cadastro)",
        "empresas": empresas, "tickers": tickers,
    }


def anos_consecutivos_com_lucro(empresa, anos):
    """Quantos exercícios SEGUIDOS, contando do mais recente, com lucro > 0
    (para no primeiro ano sem dado ou com prejuízo)."""
    n = 0
    for a in sorted(anos, reverse=True):
        v = (empresa.get("l") or {}).get(str(a))
        if v is None or v <= 0:
            break
        n += 1
    return n


def salvar(sb, base):
    blob = json.dumps(base, ensure_ascii=False, separators=(",", ":"))
    antigo = sb.table("fin_configuracoes").select("valor1").eq("chave", CHAVE_SUPABASE).execute().data
    sb.table("fin_configuracoes").delete().eq("chave", CHAVE_SUPABASE).execute()
    try:
        sb.table("fin_configuracoes").insert({"chave": CHAVE_SUPABASE, "valor1": blob}).execute()
    except Exception:
        if antigo:  # devolve a base anterior se a nova falhar
            sb.table("fin_configuracoes").insert({"chave": CHAVE_SUPABASE, "valor1": antigo[0]["valor1"]}).execute()
        raise
    return len(blob)


def carregar(sb):
    try:
        r = sb.table("fin_configuracoes").select("valor1").eq("chave", CHAVE_SUPABASE).execute().data
        return json.loads(r[0]["valor1"]) if r else None
    except Exception:
        return None


if __name__ == "__main__":
    base = construir_base(progresso=print)
    qualificam = [t for t, c in base["tickers"].items() if anos_consecutivos_com_lucro(base["empresas"][c], base["anos"]) >= ANOS_EXIGIDOS]
    print(f"{len(base['empresas'])} companhias, {len(base['tickers'])} tickers, {len(qualificam)} tickers com {ANOS_EXIGIDOS} anos seguidos de lucro")
    if "--local" in sys.argv:
        with open("base_fundamentos_acoes.json", "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False)
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import utils
        print("gravado no Supabase:", salvar(utils.get_supabase_client(), base), "bytes")
