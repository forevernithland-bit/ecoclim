import streamlit as st
import pandas as pd
import numpy as np
import io
import datetime
import altair as alt
import utils

# =============================================================================
# ROBÔ DE TRADUÇÃO DE MOEDA BRASILEIRA (EXTREMAMENTE ROBUSTO)
# =============================================================================
def parse_br_currency(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    val_str = str(val).strip()
    if val_str == '': return 0.0
    
    val_str = val_str.replace('R$', '').replace('\xa0', '').replace(' ', '')
    
    if ',' in val_str:
        val_str = val_str.replace('.', '') 
        val_str = val_str.replace(',', '.') 
    else:
        if '.' in val_str:
            partes = val_str.split('.')
            if len(partes) > 2:
                val_str = val_str.replace('.', '')
            else:
                if len(partes[1]) == 3:
                    val_str = val_str.replace('.', '')
    try:
        return float(val_str)
    except:
        return 0.0

# =============================================================================
# MOTORES DE BANCO DE DADOS BLINDADOS (ESPECÍFICOS POR ANO E ANTI-NAN)
# =============================================================================
def carregar_dados_fin(nome_tabela, lista_contas, ano):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(nome_tabela).select("*").eq("ano", ano).execute()
        df_banco = pd.DataFrame(res.data)
        if df_banco.empty:
            df_novo = pd.DataFrame({"MESES": lista_contas})
            for mes in utils.meses_pt: df_novo[mes] = 0.0
            return df_novo
        
        mapeamento = {"meses": "MESES", "marco": "MARÇO"}
        for m in utils.meses_pt:
            if m != "MARÇO": mapeamento[m.lower()] = m
        
        df_banco = df_banco.rename(columns=mapeamento)
        
        colunas_ordenadas = ["MESES"] + utils.meses_pt
        for col in colunas_ordenadas:
            if col not in df_banco.columns: df_banco[col] = 0.0 if col != "MESES" else ""
        
        df_banco = df_banco[df_banco['MESES'].isin(lista_contas)]
        df_banco['MESES'] = pd.Categorical(df_banco['MESES'], categories=lista_contas, ordered=True)
        return df_banco.sort_values('MESES')[colunas_ordenadas].reset_index(drop=True)
    except Exception as e:
        return pd.DataFrame({"MESES": lista_contas, **{m: 0.0 for m in utils.meses_pt}})

def salvar_dados_fin(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    dados_finais = []
    for _, linha in df.iterrows():
        registro = {
            "ano": ano,
            "meses": linha["MESES"],
            "janeiro": utils.safe_float(linha["JANEIRO"]),
            "fevereiro": utils.safe_float(linha["FEVEREIRO"]),
            "marco": utils.safe_float(linha["MARÇO"]),
            "abril": utils.safe_float(linha["ABRIL"]),
            "maio": utils.safe_float(linha["MAIO"]),
            "junho": utils.safe_float(linha["JUNHO"]),
            "julho": utils.safe_float(linha["JULHO"]),
            "agosto": utils.safe_float(linha["AGOSTO"]),
            "setembro": utils.safe_float(linha["SETEMBRO"]),
            "outubro": utils.safe_float(linha["OUTUBRO"]),
            "novembro": utils.safe_float(linha["NOVEMBRO"]),
            "dezembro": utils.safe_float(linha["DEZEMBRO"])
        }
        dados_finais.append(registro)
    try:
        # Apaga só as contas que estão sendo salvas (não o ano inteiro) — evita
        # apagar outras contas do mesmo ano que não fazem parte deste df (ex.:
        # linhas antigas de ECOCLIM/CONS INVESTIMENTOS, hoje calculadas ao vivo
        # e não mais gravadas aqui).
        contas_no_df = [linha["MESES"] for _, linha in df.iterrows()]
        if contas_no_df:
            supabase.table(nome_tabela).delete().eq("ano", ano).in_("meses", contas_no_df).execute()
        if dados_finais:
            supabase.table(nome_tabela).insert(dados_finais).execute()
    except Exception as e:
        st.error(f"Erro ao salvar tabela {nome_tabela}: {e}")

# =============================================================================
# APORTES DE CAPITAL — lista de lançamentos (vários por mês) na fin_aportes_itens
# =============================================================================
def carregar_aportes_itens(ano):
    """Lê os lançamentos de aporte do ano. Retorna DataFrame [Data, Mês, Conta, Valor, Obs].
    Nunca quebra a tela (se a tabela não existir ainda, devolve vazio)."""
    cols = ["Data", "Mês", "Conta", "Valor", "Origem", "Obs"]
    try:
        res = st.session_state.supabase.table('fin_aportes_itens').select("*").eq("ano", ano).order("mes").execute()
        linhas = []
        for r in (res.data or []):
            mes_idx = int(r.get("mes") or 0)
            data_str = r.get("data")
            data_obj = None
            if data_str:
                try:
                    data_obj = pd.to_datetime(data_str).date()
                except Exception:
                    data_obj = None
            linhas.append({
                "Data": data_obj,
                "Mês": utils.meses_pt[mes_idx - 1] if 1 <= mes_idx <= 12 else "",
                "Conta": str(r.get("conta") or "").upper(),
                "Valor": utils.safe_float(r.get("valor")),
                "Origem": str(r.get("origem") or "Capital externo"),
                "Obs": str(r.get("obs") or ""),
            })
        return pd.DataFrame(linhas, columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)

def salvar_aportes_itens(ano, df_itens):
    """Regrava os lançamentos do ano (apaga os do ano e reinsere os válidos)."""
    supabase = st.session_state.supabase
    registros = []
    if df_itens is not None and not df_itens.empty:
        for _, r in df_itens.iterrows():
            mes_nome = str(r.get("Mês", "")).strip().upper()
            conta = str(r.get("Conta", "")).strip().upper()
            valor = utils.safe_float(r.get("Valor", 0))
            if mes_nome in utils.meses_pt and conta in ("XP", "INTER", "ITAU") and valor != 0:
                data_val = r.get("Data")
                data_iso = None
                if pd.notna(data_val) and str(data_val).strip():
                    try:
                        data_iso = pd.to_datetime(data_val).strftime("%Y-%m-%d")
                    except Exception:
                        data_iso = None
                registros.append({
                    "ano": ano,
                    "mes": utils.meses_pt.index(mes_nome) + 1,
                    "conta": conta,
                    "valor": valor,
                    "origem": str(r.get("Origem", "") or "Capital externo"),
                    "obs": str(r.get("Obs", "") or ""),
                    "data": data_iso,
                })
    try:
        supabase.table('fin_aportes_itens').delete().eq("ano", ano).execute()
        if registros:
            try:
                supabase.table('fin_aportes_itens').insert(registros).execute()
            except Exception:
                # Coluna "data" ainda não existe (sql_fin_aportes_data.sql não
                # rodado nesse Supabase) — grava sem ela em vez de perder o
                # lançamento inteiro; a data só passa a ficar disponível
                # depois que a migração rodar.
                supabase.table('fin_aportes_itens').insert(
                    [{k: v for k, v in reg.items() if k != "data"} for reg in registros]
                ).execute()
    except Exception as e:
        st.error(f"Erro ao salvar aportes: {e}")

def agregar_aportes(df_itens):
    """Soma os lançamentos por mês para cada conta → (ap_xp, ap_it, ap_itau)
    como Series indexadas por utils.meses_pt (mesmo formato usado no cálculo)."""
    ap_xp = pd.Series(0.0, index=utils.meses_pt)
    ap_it = pd.Series(0.0, index=utils.meses_pt)
    ap_itau = pd.Series(0.0, index=utils.meses_pt)
    if df_itens is None or df_itens.empty:
        return ap_xp, ap_it, ap_itau
    for _, r in df_itens.iterrows():
        mes = str(r.get("Mês", "")).strip().upper()
        conta = str(r.get("Conta", "")).strip().upper()
        val = utils.safe_float(r.get("Valor", 0))
        if mes not in utils.meses_pt:
            continue
        if conta == "XP":
            ap_xp[mes] += val
        elif conta == "INTER":
            ap_it[mes] += val
        elif conta == "ITAU":
            ap_itau[mes] += val
    return ap_xp, ap_it, ap_itau

def carregar_meta_patrimonio():
    try:
        res = st.session_state.supabase.table('fin_configuracoes').select('*').eq('chave', 'meta_patrimonio').execute()
        if res.data:
            return utils.safe_float(res.data[0].get('valor1'))
    except Exception:
        pass
    return 0.0

def salvar_meta_patrimonio(valor):
    try:
        st.session_state.supabase.table('fin_configuracoes').delete().eq('chave', 'meta_patrimonio').execute()
        st.session_state.supabase.table('fin_configuracoes').insert({'chave': 'meta_patrimonio', 'valor1': str(valor)}).execute()
    except Exception:
        pass

def total_juros_ano(ano, meses):
    """Soma o rendimento (juros = variação − aportes) das 3 contas de investimento
    nos meses informados, para um ano qualquer. Usado no comparativo ano a ano."""
    contas = ['INVESTIMENTO XP', 'INVESTIMENTO INTER', 'INVESTIMENTO ITAU']
    dfp = carregar_dados_fin('fin_patrimonio', contas, ano).set_index('MESES')
    dfp_prev = carregar_dados_fin('fin_patrimonio', contas, ano - 1).set_index('MESES')
    ax, ai, at = agregar_aportes(carregar_aportes_itens(ano))
    total = 0.0
    for conta, apser in [('INVESTIMENTO XP', ax), ('INVESTIMENTO INTER', ai), ('INVESTIMENTO ITAU', at)]:
        v = dfp.loc[conta] if conta in dfp.index else pd.Series(0.0, index=utils.meses_pt)
        pdec = dfp_prev.loc[conta, 'DEZEMBRO'] if conta in dfp_prev.index else 0.0
        var = v - v.shift(1).fillna(pdec)
        juros = var - apser
        total += float(juros[meses].sum())
    return total

# =============================================================================
# RECEBIMENTOS EDITÁVEIS — lista de lançamentos (MAGGI/AIRNB, vários por mês)
# =============================================================================
def carregar_recebimentos_itens(ano):
    cols = ["Mês", "Conta", "Valor", "Obs"]
    try:
        res = st.session_state.supabase.table('fin_recebimentos_itens').select("*").eq("ano", ano).order("mes").execute()
        linhas = []
        for r in (res.data or []):
            mes_idx = int(r.get("mes") or 0)
            linhas.append({
                "Mês": utils.meses_pt[mes_idx - 1] if 1 <= mes_idx <= 12 else "",
                "Conta": str(r.get("conta") or "").upper(),
                "Valor": utils.safe_float(r.get("valor")),
                "Obs": str(r.get("obs") or ""),
            })
        return pd.DataFrame(linhas, columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)

def salvar_recebimentos_itens(ano, df_itens):
    supabase = st.session_state.supabase
    registros = []
    if df_itens is not None and not df_itens.empty:
        for _, r in df_itens.iterrows():
            mes_nome = str(r.get("Mês", "")).strip().upper()
            conta = str(r.get("Conta", "")).strip().upper()
            valor = utils.safe_float(r.get("Valor", 0))
            if mes_nome in utils.meses_pt and conta in ("AIRNB", "MAGGI") and valor != 0:
                registros.append({
                    "ano": ano, "mes": utils.meses_pt.index(mes_nome) + 1,
                    "conta": conta, "valor": valor, "obs": str(r.get("Obs", "") or ""),
                })
    try:
        supabase.table('fin_recebimentos_itens').delete().eq("ano", ano).execute()
        if registros:
            supabase.table('fin_recebimentos_itens').insert(registros).execute()
    except Exception as e:
        st.error(f"Erro ao salvar recebimentos: {e}")

def agregar_recebimentos(df_itens):
    """Soma os recebimentos manuais (AIRNB+MAGGI) por mês → Series por utils.meses_pt."""
    serie = pd.Series(0.0, index=utils.meses_pt)
    if df_itens is None or df_itens.empty:
        return serie
    for _, r in df_itens.iterrows():
        mes = str(r.get("Mês", "")).strip().upper()
        if mes in utils.meses_pt:
            serie[mes] += utils.safe_float(r.get("Valor", 0))
    return serie

def _receb_ja_migrado(ano):
    try:
        res = st.session_state.supabase.table('fin_configuracoes').select('chave').eq('chave', f'receb_migrado_{ano}').execute()
        return bool(res.data)
    except Exception:
        return False

def _marcar_receb_migrado(ano):
    try:
        st.session_state.supabase.table('fin_configuracoes').delete().eq('chave', f'receb_migrado_{ano}').execute()
        st.session_state.supabase.table('fin_configuracoes').insert({'chave': f'receb_migrado_{ano}', 'valor1': '1'}).execute()
    except Exception:
        pass

def migrar_entradas_para_itens(ano):
    """Converte a matriz antiga (fin_entradas: AIRNB/MAGGI CONSORCIOS) em lançamentos,
    para não perder o que já estava digitado."""
    dfm = carregar_dados_fin('fin_entradas', ['AIRNB', 'MAGGI CONSORCIOS'], ano).set_index('MESES')
    linhas = []
    for conta_nome, conta_curto in [('AIRNB', 'AIRNB'), ('MAGGI CONSORCIOS', 'MAGGI')]:
        if conta_nome in dfm.index:
            for m in utils.meses_pt:
                val = utils.safe_float(dfm.loc[conta_nome, m])
                if val != 0:
                    linhas.append({"Mês": m, "Conta": conta_curto, "Valor": val, "Obs": "migrado da matriz"})
    return pd.DataFrame(linhas, columns=["Mês", "Conta", "Valor", "Obs"])

# =============================================================================
# GRÁFICOS MODERNOS (Altair) — área/linha/barra com o visual do sistema
# =============================================================================
def _fin_df(serie):
    return pd.DataFrame({
        "Mês": [m[:3].title() for m in utils.meses_pt],
        "_ord": list(range(12)),
        "Valor": [utils.safe_float(serie.get(m, 0)) for m in utils.meses_pt],
    })

def _fin_enc(df):
    x = alt.X("Mês:N", sort=alt.SortField("_ord"),
              axis=alt.Axis(title=None, labelAngle=0, grid=False, domain=False, ticks=False, labelColor="#64748b"))
    y = alt.Y("Valor:Q",
              axis=alt.Axis(title=None, grid=True, gridColor="#eef1f5", tickCount=4, labelColor="#94a3b8", format="~s"))
    tip = [alt.Tooltip("Mês:N", title="Mês"), alt.Tooltip("Valor:Q", title="R$", format=",.2f")]
    return x, y, tip

def grafico_area(serie, cor):
    df = _fin_df(serie); x, y, tip = _fin_enc(df)
    b = alt.Chart(df).encode(x=x, y=y, tooltip=tip)
    ch = (b.mark_area(interpolate="monotone", opacity=0.14, color=cor)
          + b.mark_line(interpolate="monotone", strokeWidth=3, color=cor))
    return ch.properties(height=210).configure_view(strokeWidth=0)

def grafico_linha(serie, cor):
    df = _fin_df(serie); x, y, tip = _fin_enc(df)
    b = alt.Chart(df).encode(x=x, y=y, tooltip=tip)
    ch = b.mark_line(interpolate="monotone", strokeWidth=3, color=cor,
                     point=alt.OverlayMarkDef(color=cor, size=45))
    return ch.properties(height=210).configure_view(strokeWidth=0)

def grafico_barra(serie, cor):
    df = _fin_df(serie); x, y, tip = _fin_enc(df)
    b = alt.Chart(df).encode(x=x, y=y, tooltip=tip)
    ch = b.mark_bar(color=cor, cornerRadiusTopLeft=5, cornerRadiusTopRight=5, size=22)
    return ch.properties(height=210).configure_view(strokeWidth=0)

def carregar_periodo_visivel():
    if 'periodo_visivel_financeiro' in st.session_state:
        return st.session_state.periodo_visivel_financeiro
    try:
        res = st.session_state.supabase.table('fin_configuracoes').select('*').eq('chave', 'periodo_visivel').execute()
        if res.data:
            return (res.data[0].get('valor1', 'JANEIRO'), res.data[0].get('valor2', 'DEZEMBRO'))
    except: pass
    return ("JANEIRO", "DEZEMBRO")

def salvar_periodo_visivel(m_ini, m_fim):
    st.session_state.periodo_visivel_financeiro = (m_ini, m_fim)
    try:
        st.session_state.supabase.table('fin_configuracoes').delete().eq('chave', 'periodo_visivel').execute()
        st.session_state.supabase.table('fin_configuracoes').insert({
            'chave': 'periodo_visivel', 'valor1': m_ini, 'valor2': m_fim
        }).execute()
    except: pass

def limpar_e_garantir_linhas(df, lista_contas):
    if not df.empty and 'MESES' in df.columns:
        df = df[df['MESES'].astype(str).str.strip() != '']
        df = df[df['MESES'].notna()]
    else:
        df = pd.DataFrame(columns=["MESES"] + utils.meses_pt)
        
    contas_existentes = df['MESES'].tolist()
    for c in lista_contas:
        if c not in contas_existentes:
            df = pd.concat([df, pd.DataFrame([{"MESES": c, **{m: 0.0 for m in utils.meses_pt}}])], ignore_index=True)
            
    df = df[df['MESES'].isin(lista_contas)]
    df['MESES'] = pd.Categorical(df['MESES'], categories=lista_contas, ordered=True)
    return df.sort_values('MESES').reset_index(drop=True)

# =============================================================================
# LINHAS AUTOMÁTICAS DE "RECEBIMENTOS E PRÓ-LABORE"
# (CONS INVESTIMENTOS = Breno via ERP Consorbens; ECOCLIM = Gestão de Serviços)
# =============================================================================
def _eh_mes_futuro(ano, mes_idx):
    return (ano > utils.ano_atual) or (ano == utils.ano_atual and mes_idx > utils.mes_hoje_idx)

def carregar_breno_mensal(ano):
    """Lê resultado_socios_mensal (publicado pelo ERP Consorbens toda vez que
    a tela Financeiro de lá é aberta) e devolve uma Series por mês com o
    resultado do Breno. Sempre ao vivo (sem cache). Meses futuros e meses
    ainda não publicados ficam em 0 — nunca quebra a tela se a conexão/
    migração não estiver pronta."""
    serie = pd.Series(0.0, index=utils.meses_pt)
    sb = utils.iniciar_conexao_consorbens()
    if sb is None:
        return serie
    try:
        res = sb.table("resultado_socios_mensal").select("mes, breno").eq("ano", ano).execute()
        for r in (res.data or []):
            mes_idx = int(r.get("mes") or 0)
            if 1 <= mes_idx <= 12 and not _eh_mes_futuro(ano, mes_idx):
                serie[utils.meses_pt[mes_idx - 1]] = utils.safe_float(r.get("breno"))
    except Exception:
        pass
    return serie

def carregar_ecoclim_mensal(ano):
    """Calcula a linha ECOCLIM a partir de servicos_andamento (mesmo banco do
    Ecoclim, tela Gestão de Serviços): no mês ATUAL = Lucro Líquido Estimado
    (Em Andamento/Aguardando Pagamento/Aguardando Peças) + Lucro Líquido dos
    Finalizados daquele mês. Em meses já fechados, só o Realizado daquele
    mês (o que estava 'em andamento' virou, ou não, um Finalizado — não soma
    mais junto). Meses futuros = 0."""
    serie = pd.Series(0.0, index=utils.meses_pt)
    supabase = st.session_state.supabase
    try:
        res = supabase.table('servicos_andamento').select("status_projeto, lucro_estimado, data_conclusao").execute()
        df = pd.DataFrame(res.data)
    except Exception:
        return serie
    if df.empty:
        return serie

    df['lucro_estimado'] = pd.to_numeric(df['lucro_estimado'], errors='coerce').fillna(0.0)
    df['data_conclusao'] = pd.to_datetime(df['data_conclusao'], errors='coerce')

    status_andamento = ["Em Andamento", "Aguardando Pagamento", "Aguardando Peças"]
    status_finalizado = ["Concluído PIX", "Concluído CARTÃO"]

    total_andamento = df.loc[df['status_projeto'].isin(status_andamento), 'lucro_estimado'].sum()

    df_fin = df[df['status_projeto'].isin(status_finalizado) & df['data_conclusao'].notna()].copy()
    df_fin['Ano'] = df_fin['data_conclusao'].dt.year
    df_fin['Mes_idx'] = df_fin['data_conclusao'].dt.month

    for i, m in enumerate(utils.meses_pt):
        mes_idx = i + 1
        if _eh_mes_futuro(ano, mes_idx):
            continue
        fin_mes = df_fin.loc[(df_fin['Ano'] == ano) & (df_fin['Mes_idx'] == mes_idx), 'lucro_estimado'].sum()
        eh_mes_atual = (ano == utils.ano_atual) and (mes_idx == utils.mes_hoje_idx)
        serie[m] = fin_mes + (total_andamento if eh_mes_atual else 0.0)
    return serie

def carregar_airnb_breno_mensal(ano):
    """Calcula a linha AIRNB (parte do sócio BRENO) mês a mês, do mesmo banco
    do módulo AirBnb: líquido do mês = soma(airnb_entradas) − soma(airnb_saidas),
    e BRENO fica com 50% desse líquido (o outro 50% é da Eunice). Meses futuros
    ficam em 0. Nunca quebra a tela se as tabelas não existirem ainda."""
    serie = pd.Series(0.0, index=utils.meses_pt)
    try:
        contas_ent = ['AIRNB', 'LOCAÇÕES POR FORA']
        contas_sai = ['LIMPEZA', 'LUZ', 'ÁGUA', 'INTERNET', 'PISCINEIRO', 'PRODUTOS DE LIMPEZA', 'OUTROS']
        df_ent = utils.load_year_data('airnb_entradas', contas_ent, ano)
        df_sai = utils.load_year_data('airnb_saidas', contas_sai, ano)
        for i, m in enumerate(utils.meses_pt):
            if _eh_mes_futuro(ano, i + 1):
                continue
            ent = pd.to_numeric(df_ent[m], errors='coerce').fillna(0).sum() if m in df_ent.columns else 0.0
            sai = pd.to_numeric(df_sai[m], errors='coerce').fillna(0).sum() if m in df_sai.columns else 0.0
            serie[m] = (float(ent) - float(sai)) * 0.5
    except Exception:
        pass
    return serie

def carregar_manual_legado_mensal(ano, conta):
    """Lê o valor antigo digitado à mão em fin_entradas para uma conta que
    deixou de ser editável (ECOCLIM/CONS INVESTIMENTOS). Usado só como
    fallback nos meses em que o cálculo automático ainda não tem dado (0) —
    ex.: meses passados que o ERP Consorbens ainda não publicou, ou que não
    têm registro em servicos_andamento. Some sozinho assim que o valor
    calculado deixar de ser 0 para aquele mês."""
    serie = pd.Series(0.0, index=utils.meses_pt)
    supabase = st.session_state.supabase
    try:
        res = supabase.table('fin_entradas').select("*").eq("ano", ano).eq("meses", conta).limit(1).execute()
        if res.data:
            linha = res.data[0]
            mapeamento = {"marco": "MARÇO"}
            for m in utils.meses_pt:
                if m != "MARÇO": mapeamento[m.lower()] = m
            for col_db, col_pt in mapeamento.items():
                serie[col_pt] = utils.safe_float(linha.get(col_db))
    except Exception:
        pass
    return serie

def aplicar_fallback_legado(serie_calculada, serie_legado, ano):
    """Nos meses (passados/atual) em que o valor calculado ainda é 0, usa o
    valor antigo digitado à mão em vez de mostrar zero. Nunca mexe em meses
    futuros (continuam 0, como o resto da tela)."""
    for i, m in enumerate(utils.meses_pt):
        if _eh_mes_futuro(ano, i + 1):
            continue
        if serie_calculada[m] == 0 and serie_legado[m] != 0:
            serie_calculada[m] = serie_legado[m]
    return serie_calculada

# =============================================================================
# MOTORES DE EXPORTAÇÃO E IMPORTAÇÃO GLOBAL BLINDADA CONTRA NAN
# =============================================================================
def exportar_base_completa_excel():
    supabase = st.session_state.supabase
    try:
        res_p = supabase.table('fin_patrimonio').select("*").order("ano", desc=False).execute()
        res_e = supabase.table('fin_entradas').select("*").order("ano", desc=False).execute()
        
        df_p_raw = pd.DataFrame(res_p.data)
        df_e_raw = pd.DataFrame(res_e.data)
        
        mapeamento = {"ano": "ANO", "meses": "MESES", "marco": "MARÇO"}
        for m in utils.meses_pt:
            if m != "MARÇO": mapeamento[m.lower()] = m
            
        colunas_finais = ["ANO", "MESES"] + utils.meses_pt
        
        if not df_p_raw.empty:
            df_p_raw = df_p_raw.rename(columns=mapeamento)
            df_p_final = df_p_raw[[c for c in colunas_finais if c in df_p_raw.columns]]
        else:
            df_p_final = pd.DataFrame(columns=colunas_finais)
            
        if not df_e_raw.empty:
            df_e_raw = df_e_raw.rename(columns=mapeamento)
            df_e_final = df_e_raw[[c for c in colunas_finais if c in df_e_raw.columns]]
        else:
            df_e_final = pd.DataFrame(columns=colunas_finais)
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_p_final.to_excel(writer, sheet_name='PATRIMONIO', index=False)
            df_e_final.to_excel(writer, sheet_name='RECEBIMENTOS', index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"Erro ao gerar exportação global: {e}")
        return None

def importar_base_completa_excel(file_buffer):
    supabase = st.session_state.supabase
    try:
        xls = pd.ExcelFile(file_buffer)
        if 'PATRIMONIO' not in xls.sheet_names or 'RECEBIMENTOS' not in xls.sheet_names:
            st.error("Arquivo inválido! O Excel precisa conter as abas 'PATRIMONIO' e 'RECEBIMENTOS'.")
            return False
            
        df_p_xls = pd.read_excel(xls, 'PATRIMONIO')
        df_e_xls = pd.read_excel(xls, 'RECEBIMENTOS')
        
        def processar_aba(df, nome_tabela_banco):
            df.columns = df.columns.str.strip().str.upper()
            
            if 'ANO' not in df.columns or 'MESES' not in df.columns: return
            df = df.dropna(subset=['ANO', 'MESES'])
            
            for col in utils.meses_pt:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                else:
                    df[col] = 0.0
                    
            dados_finais = []
            anos_presentes = set()
            
            for _, linha in df.iterrows():
                try: ano_linha = int(linha["ANO"])
                except: continue
                
                anos_presentes.add(ano_linha)
                
                registro = {
                    "ano": ano_linha,
                    "meses": str(linha["MESES"]).strip(),
                    "janeiro": float(linha["JANEIRO"]),
                    "fevereiro": float(linha["FEVEREIRO"]),
                    "marco": float(linha["MARÇO"]),
                    "abril": float(linha["ABRIL"]),
                    "maio": float(linha["MAIO"]),
                    "junho": float(linha["JUNHO"]),
                    "julho": float(linha["JULHO"]),
                    "agosto": float(linha["AGOSTO"]),
                    "setembro": float(linha["SETEMBRO"]),
                    "outubro": float(linha["OUTUBRO"]),
                    "novembro": float(linha["NOVEMBRO"]),
                    "dezembro": float(linha["DEZEMBRO"])
                }
                dados_finais.append(registro)
                
            for a in anos_presentes:
                supabase.table(nome_tabela_banco).delete().eq("ano", a).execute()
                
            if dados_finais:
                supabase.table(nome_tabela_banco).insert(dados_finais).execute()
                
        processar_aba(df_p_xls, 'fin_patrimonio')
        processar_aba(df_e_xls, 'fin_entradas')
        return True
    except Exception as e:
        st.error(f"Erro crítico durante a importação do Excel: {e}")
        return False

# =============================================================================
# RENDERIZAÇÃO PRINCIPAL DA TELA
# =============================================================================
def renderizar():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    
    # CSS RESPONSIVO INJETADO AQUI
    st.markdown("""
        <style>
        @media screen and (max-width: 768px) {
            .financeiro div[data-testid="stDataFrame"], .financeiro div[data-testid="stDataEditor"] {
                overflow-x: auto !important;
            }
            .financeiro div[data-testid="column"] {
                width: 100% !important;
                min-width: 100% !important;
                display: block !important;
                margin-bottom: 1rem !important;
            }
            .financeiro h4 {
                font-size: 1.1rem !important;
                margin-bottom: 0.5rem !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)
    
    if "salvar_fin_clicado" not in st.session_state:
        st.session_state.salvar_fin_clicado = False
        
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        
        st.write("---")
        if st.button("💾 SALVAR DADOS AGORA", type="primary", use_container_width=True, key="btn_salvar_lateral"):
            st.session_state.salvar_fin_clicado = True
        st.write("---")
        
        st.markdown("### 👁️ Linha do Tempo")
        
        # --- NOVO MOTOR: BOTÕES RÁPIDOS DE FILTRO PARA CELULAR / PC ---
        c_btn1, c_btn2 = st.columns(2)
        if c_btn1.button("📱 3 Meses", help="Mês Passado, Atual e Próximo", use_container_width=True):
            hoje_idx = datetime.date.today().month - 1
            idx_ini = max(0, hoje_idx - 1)
            idx_fim = min(11, hoje_idx + 1)
            salvar_periodo_visivel(utils.meses_pt[idx_ini], utils.meses_pt[idx_fim])
            st.rerun()
            
        if c_btn2.button("💻 12 Meses", help="Mostrar Todo o Ano", use_container_width=True):
            salvar_periodo_visivel("JANEIRO", "DEZEMBRO")
            st.rerun()
        # -------------------------------------------------------------
        
        pref_ini, pref_fim = carregar_periodo_visivel()
        m_ini, m_fim = st.select_slider("Período Visível:", options=utils.meses_pt, value=(pref_ini, pref_fim))
        
        if (m_ini, m_fim) != (pref_ini, pref_fim):
            salvar_periodo_visivel(m_ini, m_fim)
            st.rerun()
            
        colunas_visiveis = ["MESES"] + utils.meses_pt[utils.meses_pt.index(m_ini):utils.meses_pt.index(m_fim) + 1]

        if st.button("🔄 Recarregar Banco", use_container_width=True):
            st.session_state.pop('ano_dados_atual', None)
            st.session_state.pop('db_df_p', None)
            st.session_state.pop('db_df_e', None)
            st.session_state.pop('db_df_ap_itens', None)
            st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'INVESTIMENTO INTER', 'INVESTIMENTO ITAU', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    # ECOCLIM, CONS INVESTIMENTOS e AIRNB deixaram de ser digitadas à mão — são
    # calculadas ao vivo (carregar_ecoclim_mensal / carregar_breno_mensal /
    # carregar_airnb_breno_mensal). Só MAGGI CONSORCIOS continua manual/gravada
    # em fin_entradas (vários recebimentos por mês).
    contas_e = ['MAGGI CONSORCIOS']

    if ('db_df_p' not in st.session_state or
        'db_df_e' not in st.session_state or
        'db_df_ap_itens' not in st.session_state or
        'ano_dados_atual' not in st.session_state or
        st.session_state.ano_dados_atual != ano_selecionado or
        st.session_state.get('forcar_reload_fin', False)):

        st.session_state.db_df_p = limpar_e_garantir_linhas(carregar_dados_fin('fin_patrimonio', contas_p, ano_selecionado), contas_p)
        st.session_state.db_df_e = limpar_e_garantir_linhas(carregar_dados_fin('fin_entradas', contas_e, ano_selecionado), contas_e)
        st.session_state.db_df_ap_itens = carregar_aportes_itens(ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado
        st.session_state.forcar_reload_fin = False

    df_p_prev = carregar_dados_fin('fin_patrimonio', contas_p, ano_selecionado - 1).set_index('MESES')
    pat_liq_prev_dec = df_p_prev.loc[df_p_prev.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'INVESTIMENTO INTER', 'INVESTIMENTO ITAU', 'INVESTIMENTO XP', 'FGTS']), 'DEZEMBRO'].sum()
    pat_tot_prev_dec = pat_liq_prev_dec + df_p_prev.loc[df_p_prev.index.isin(['IMÓVEIS', 'VEÍCULOS']), 'DEZEMBRO'].sum()
    xp_prev_dec = df_p_prev.loc['INVESTIMENTO XP', 'DEZEMBRO'] if 'INVESTIMENTO XP' in df_p_prev.index else 0
    inter_prev_dec = df_p_prev.loc['INVESTIMENTO INTER', 'DEZEMBRO'] if 'INVESTIMENTO INTER' in df_p_prev.index else 0
    itau_prev_dec = df_p_prev.loc['INVESTIMENTO ITAU', 'DEZEMBRO'] if 'INVESTIMENTO ITAU' in df_p_prev.index else 0

    cfg_edit = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    cfg_text = {"MESES": st.column_config.TextColumn("CONTA", width=220, disabled=True)}
    for m in utils.meses_pt: 
        cfg_edit[m] = st.column_config.TextColumn(m, width=100)
        cfg_text[m] = st.column_config.TextColumn(m, width=100)

    tabs = st.tabs(["📊 Resumo", "📝 Lançamentos", "📈 Gráficos"])

    # =====================================================================
    # ABA LANÇAMENTOS — renderiza os editores primeiro (produz os dados)
    # =====================================================================
    with tabs[1]:
        c_exp, c_imp = st.columns([1, 1.4])
        with c_exp:
            arquivo_completo_excel = exportar_base_completa_excel()
            if arquivo_completo_excel:
                st.download_button(
                    label="📤 Exportar toda a base", data=arquivo_completo_excel,
                    file_name="ERP_ECOCLIM_FINANCEIRO.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="btn_exportar_total_global")
        with c_imp:
            excel_subido_global = st.file_uploader("Importar base completa", type=["xlsx"], label_visibility="collapsed", key="file_uploader_global_fin")
            if excel_subido_global is not None:
                if st.button("🚀 Confirmar importação", use_container_width=True, type="secondary", key="btn_executar_importacao_global"):
                    with st.spinner("Substituindo dados..."):
                        if importar_base_completa_excel(excel_subido_global):
                            st.success("✅ Importação com sucesso!")
                            st.session_state.forcar_reload_fin = True
                            st.rerun()

        st.markdown(f"##### 🏛️ Patrimônio e Investimentos ({ano_selecionado})")
        df_p_view = st.session_state.db_df_p[colunas_visiveis].copy()
        for m in colunas_visiveis:
            if m != "MESES":
                df_p_view[m] = df_p_view[m].apply(lambda x: utils.to_br_currency(x))
        df_p_ed = st.data_editor(df_p_view, hide_index=True, column_config=cfg_edit, use_container_width=True, height=320, key=f"ed_p_fin_estavel_v12_{ano_selecionado}")
        df_p_trabalho = st.session_state.db_df_p.copy()
        for c in colunas_visiveis:
            if c != "MESES": df_p_trabalho[c] = df_p_ed[c].apply(parse_br_currency)

        st.markdown("##### 💵 Aportes de Capital (Investimentos)")
        with st.expander("Registrar depósitos (pode haver vários no mesmo mês)", expanded=False):
            st.caption("Lance cada DEPÓSITO feito. O sistema soma por mês/conta e desconta do rendimento e do Limite de Gasto — não é juros. Registre só no mês em que o dinheiro entrou.")
            st.caption("**Origem**: use *Reinvestimento de renda* quando o dinheiro veio de um recebimento já lançado (ex.: salário Maggi) — assim fica claro que não é dinheiro novo. Não muda nenhum número; só o cálculo de juros usa o valor.")
            st.caption("**Data** é opcional — só ajuda a diferenciar dois depósitos na mesma conta no mesmo mês (ex.: dois recebimentos da Maggi). Quem decide o mês pro cálculo continua sendo a coluna **Mês**, não a Data.")
            cfg_ap = {
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", width="small"),
                "Mês": st.column_config.SelectboxColumn("Mês", options=utils.meses_pt, width="small", required=True),
                "Conta": st.column_config.SelectboxColumn("Conta", options=["XP", "INTER", "ITAU"], width="small", required=True),
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0, width="small"),
                "Origem": st.column_config.SelectboxColumn("Origem", options=["Capital externo", "Reinvestimento de renda"], width="medium"),
                "Obs": st.column_config.TextColumn("Obs (opcional)"),
            }
            df_ap_itens_ed = st.data_editor(
                st.session_state.db_df_ap_itens, column_config=cfg_ap, num_rows="dynamic",
                hide_index=True, use_container_width=True, key=f"ed_ap_itens_{ano_selecionado}")
            if not df_ap_itens_ed.empty:
                _vals = pd.to_numeric(df_ap_itens_ed.get("Valor"), errors="coerce").fillna(0)
                _orig = df_ap_itens_ed.get("Origem")
                _reinv = float(_vals[_orig == "Reinvestimento de renda"].sum()) if _orig is not None else 0.0
                _ext = float(_vals.sum()) - _reinv
                if (_reinv + _ext) > 0:
                    st.caption(f"💰 Capital externo (dinheiro novo): **{utils.to_br_currency_md(_ext)}**  ·  ♻️ Reinvestimento de renda: **{utils.to_br_currency_md(_reinv)}**")
        ap_xp, ap_it, ap_itau = agregar_aportes(df_ap_itens_ed)

        st.markdown(f"##### 💰 Recebimentos e Pró-labore ({ano_selecionado})")
        serie_ecoclim = carregar_ecoclim_mensal(ano_selecionado)
        serie_breno = carregar_breno_mensal(ano_selecionado)
        serie_airnb = carregar_airnb_breno_mensal(ano_selecionado)
        serie_ecoclim = aplicar_fallback_legado(serie_ecoclim, carregar_manual_legado_mensal(ano_selecionado, 'ECOCLIM'), ano_selecionado)
        serie_breno = aplicar_fallback_legado(serie_breno, carregar_manual_legado_mensal(ano_selecionado, 'CONS INVESTIMENTOS'), ano_selecionado)
        st.caption("🔄 Calculadas automaticamente: **ECOCLIM** (Gestão de Serviços), **CONS INVESTIMENTOS** (resultado do Breno via ERP Consorbens) e **AIRNB** (50% do Breno no líquido do módulo AirBnb). Só a **Maggi** é digitada. Meses sem dado ainda mostram o último valor digitado à mão.")
        dict_auto_e = {'MESES': ['ECOCLIM', 'CONS INVESTIMENTOS', 'AIRNB (Breno 50%)']}
        for m in utils.meses_pt:
            dict_auto_e[m] = [utils.to_br_currency(serie_ecoclim[m]), utils.to_br_currency(serie_breno[m]), utils.to_br_currency(serie_airnb[m])]
        st.dataframe(pd.DataFrame(dict_auto_e)[colunas_visiveis].style.set_properties(**{'background-color': '#E2F0D9', 'color': 'black', 'font-weight': 'bold'}), hide_index=True, column_config=cfg_text, use_container_width=True)
        _default_mes_idx = (utils.mes_hoje_idx - 1) if ano_selecionado == utils.ano_atual else 0
        st.caption("✏️ Editáveis — uma linha por conta. Para vários pagamentos no mês (ex.: **Maggi**), use o **➕ Adicionar recebimento** abaixo (ele SOMA ao mês).")
        df_e_view = st.session_state.db_df_e[colunas_visiveis].copy()
        for m in colunas_visiveis:
            if m != "MESES":
                df_e_view[m] = df_e_view[m].apply(lambda x: utils.to_br_currency(x))
        df_e_ed = st.data_editor(df_e_view, hide_index=True, column_config=cfg_edit, use_container_width=True, height=115, key=f"ed_e_fin_v14_{ano_selecionado}")
        df_e_trabalho = st.session_state.db_df_e.copy()
        for c in colunas_visiveis:
            if c != "MESES": df_e_trabalho[c] = df_e_ed[c].apply(parse_br_currency)
        st.session_state.db_df_e = df_e_trabalho  # sincroniza p/ o somador operar no valor atual

        with st.expander("➕ Adicionar recebimento (soma ao mês selecionado)"):
            qa1, qa2, qa3 = st.columns(3)
            _conta_add = qa1.selectbox("Conta", ['MAGGI CONSORCIOS'], key=f"add_rec_conta_{ano_selecionado}")
            _mes_add = qa2.selectbox("Mês", utils.meses_pt, index=_default_mes_idx, key=f"add_rec_mes_{ano_selecionado}")
            _val_add = qa3.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", key=f"add_rec_val_{ano_selecionado}")
            if st.button("➕ Adicionar ao mês", use_container_width=True, key=f"add_rec_btn_{ano_selecionado}"):
                if _val_add and _val_add > 0:
                    _dfx = st.session_state.db_df_e.copy().set_index('MESES')
                    if _conta_add in _dfx.index:
                        _dfx.loc[_conta_add, _mes_add] = utils.safe_float(_dfx.loc[_conta_add, _mes_add]) + _val_add
                        st.session_state.db_df_e = _dfx.reset_index()
                        _ek = f"ed_e_fin_v14_{ano_selecionado}"
                        if _ek in st.session_state:
                            del st.session_state[_ek]
                        st.success(f"+{utils.to_br_currency(_val_add)} em {_conta_add} · {_mes_add.title()}. Clique em GRAVAR para salvar.")
                        st.rerun()
                else:
                    st.warning("Informe um valor maior que zero.")

        tot_e = df_e_trabalho.set_index('MESES').sum() + serie_ecoclim + serie_breno + serie_airnb
        dict_res_e = {'MESES': ['TOTAL RECEBIMENTOS']}
        for i, m in enumerate(utils.meses_pt):
            is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
            dict_res_e[m] = [utils.to_br_currency(0 if is_futuro else tot_e[m])]
        st.dataframe(pd.DataFrame(dict_res_e)[colunas_visiveis].style.set_properties(**{'background-color': '#9BC2E6', 'color': 'black', 'font-weight': 'bold'}), hide_index=True, column_config=cfg_text, use_container_width=True)

        st.divider()
        _cesp, _cbtn = st.columns([3, 1])
        if _cbtn.button("💾 GRAVAR ALTERAÇÕES", type="primary", use_container_width=True, key="btn_gravar_rodape"):
            st.session_state.salvar_fin_clicado = True
        if st.session_state.salvar_fin_clicado:
            with st.spinner("Gravando no Supabase..."):
                st.session_state.db_df_p = df_p_trabalho
                st.session_state.db_df_ap_itens = df_ap_itens_ed
                st.session_state.db_df_e = df_e_trabalho
                salvar_dados_fin('fin_patrimonio', st.session_state.db_df_p, ano_selecionado)
                salvar_aportes_itens(ano_selecionado, df_ap_itens_ed)
                salvar_dados_fin('fin_entradas', st.session_state.db_df_e, ano_selecionado)
            st.session_state.salvar_fin_clicado = False
            st.success("✅ Alterações gravadas!")

    # =====================================================================
    # CÁLCULOS (usam os DataFrames produzidos na aba Lançamentos)
    # =====================================================================
    df_n = df_p_trabalho.set_index('MESES')
    pat_liq = df_n.loc[df_n.index.isin(['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'INVESTIMENTO INTER', 'INVESTIMENTO ITAU', 'INVESTIMENTO XP', 'FGTS'])].sum()
    pat_tot = pat_liq + df_n.loc[df_n.index.isin(['IMÓVEIS', 'VEÍCULOS'])].sum()

    var_abs = pat_tot.copy()
    var_pct = pat_tot.copy()
    for i, m in enumerate(utils.meses_pt):
        val_prev = pat_tot[utils.meses_pt[i-1]] if i > 0 else pat_tot_prev_dec
        var_abs[m] = pat_tot[m] - val_prev
        var_pct[m] = (var_abs[m] / val_prev * 100) if val_prev != 0 else 0.0
    # Alerta de gasto: ignora a CAPITAL DE GIRO (ML) — é o giro da Ecoclim e
    # flutua naturalmente (ora sobe, ora desce). Só considera as demais contas.
    _contas_alerta = ['CAPITAL DE GIRO CONSOR (ITAU)', 'INVESTIMENTO INTER', 'INVESTIMENTO ITAU', 'INVESTIMENTO XP', 'FGTS']
    _pl_alerta = df_n.loc[df_n.index.isin(_contas_alerta)].sum()
    _pl_alerta_prev_dec = df_p_prev.loc[df_p_prev.index.isin(_contas_alerta), 'DEZEMBRO'].sum()
    var_liq = _pl_alerta - _pl_alerta.shift(1).fillna(_pl_alerta_prev_dec)

    xp_v = df_n.loc['INVESTIMENTO XP'] if 'INVESTIMENTO XP' in df_n.index else pd.Series(0.0, index=utils.meses_pt)
    it_v = df_n.loc['INVESTIMENTO INTER'] if 'INVESTIMENTO INTER' in df_n.index else pd.Series(0.0, index=utils.meses_pt)
    itau_v = df_n.loc['INVESTIMENTO ITAU'] if 'INVESTIMENTO ITAU' in df_n.index else pd.Series(0.0, index=utils.meses_pt)

    meses_calc = utils.meses_pt[:utils.mes_hoje_idx] if ano_selecionado == utils.ano_atual else utils.meses_pt
    media_ent = tot_e[meses_calc].mean() if not tot_e.empty else 0

    xp_var_full = xp_v - xp_v.shift(1).fillna(xp_prev_dec)
    it_var_full = it_v - it_v.shift(1).fillna(inter_prev_dec)
    itau_var_full = itau_v - itau_v.shift(1).fillna(itau_prev_dec)
    rend_tot_full = (xp_var_full - ap_xp) + (it_var_full - ap_it) + (itau_var_full - ap_itau)
    var_total_full = xp_var_full + it_var_full + itau_var_full
    media_rend_r = rend_tot_full[meses_calc].mean()

    prev_bal_full = (xp_v + it_v + itau_v).shift(1).fillna(xp_prev_dec + inter_prev_dec + itau_prev_dec)
    pb_safe = prev_bal_full[meses_calc].replace(0, np.nan)
    media_rend_p = (rend_tot_full[meses_calc] / pb_safe).mean() * 100
    pat_atual = pat_tot[utils.mes_atual_nome] if ano_selecionado == utils.ano_atual else pat_tot['DEZEMBRO']

    # Tabela de rendimento (juros = variação − aporte)
    dict_rend = {'MESES': ['RESULTADO XP (juros)', 'RESULTADO INTER (juros)', 'RESULTADO ITAU (juros)',
                           'APORTES DO MÊS', 'RENDIMENTO (JUROS)', 'VARIAÇÃO TOTAL (juros+aportes)',
                           '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']}
    for i, m in enumerate(utils.meses_pt):
        is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
        if is_futuro:
            dict_rend[m] = ["R$ 0,00", "R$ 0,00", "R$ 0,00", "R$ 0,00", "R$ 0,00", "R$ 0,00", "0,00%", "R$ 0,00"]
        else:
            d_xp = xp_v[m] - (xp_v[utils.meses_pt[i-1]] if i > 0 else xp_prev_dec)
            d_it = it_v[m] - (it_v[utils.meses_pt[i-1]] if i > 0 else inter_prev_dec)
            d_itau = itau_v[m] - (itau_v[utils.meses_pt[i-1]] if i > 0 else itau_prev_dec)
            j_xp = d_xp - ap_xp[m]; j_it = d_it - ap_it[m]; j_itau = d_itau - ap_itau[m]
            j_tot = j_xp + j_it + j_itau
            a_tot = ap_xp[m] + ap_it[m] + ap_itau[m]
            var_tot = j_tot + a_tot
            p_bal = (xp_v[utils.meses_pt[i-1]] + it_v[utils.meses_pt[i-1]] + itau_v[utils.meses_pt[i-1]]) if i > 0 else (xp_prev_dec + inter_prev_dec + itau_prev_dec)
            pct = (j_tot / p_bal * 100) if p_bal > 0 else 0.0
            dict_rend[m] = [utils.to_br_currency(j_xp), utils.to_br_currency(j_it), utils.to_br_currency(j_itau),
                            utils.to_br_currency(a_tot), utils.to_br_currency(j_tot), utils.to_br_currency(var_tot),
                            f"{pct:.2f}%".replace('.', ','), utils.to_br_currency(tot_e[m] + j_tot)]

    # Tabela de patrimônio detalhado
    dict_res_p = {'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VAR. MENSAL (R$)', 'VAR. MENSAL (%)']}
    for i, m in enumerate(utils.meses_pt):
        is_futuro = (ano_selecionado > utils.ano_atual) or (ano_selecionado == utils.ano_atual and i > (utils.mes_hoje_idx - 1))
        if is_futuro:
            dict_res_p[m] = ["R$ 0,00", "R$ 0,00", "R$ 0,00", "0,00%"]
        else:
            dict_res_p[m] = [utils.to_br_currency(pat_liq[m]), utils.to_br_currency(pat_tot[m]), utils.to_br_currency(var_abs[m]), f"{var_pct[m]:.2f}%".replace('.', ',')]

    meta = carregar_meta_patrimonio()
    rend_acum = float(rend_tot_full[meses_calc].sum())
    try:
        rend_acum_prev = total_juros_ano(ano_selecionado - 1, meses_calc)
    except Exception:
        rend_acum_prev = 0.0

    # =====================================================================
    # ABA RESUMO
    # =====================================================================
    with tabs[0]:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🏛️ Patrimônio Atual", utils.to_br_currency(pat_atual))
        k2.metric("🎯 Limite de Gasto", utils.to_br_currency(media_rend_r), help="Média dos juros mensais (sem aportes) — quanto dá para gastar sem encolher o patrimônio.")
        k3.metric("💰 Média de Entradas", utils.to_br_currency(media_ent))
        k4.metric("📈 Retorno Médio", f"{media_rend_p:.2f}%".replace(".", ","))

        st.markdown("##### 🎯 Meta de Patrimônio")
        cm1, cm2 = st.columns([3, 1])
        with cm2:
            nova_meta = st.number_input("Definir meta (R$)", min_value=0.0, value=float(meta), step=10000.0, format="%.2f", key="in_meta_patrimonio")
            if abs(nova_meta - meta) > 0.001:
                salvar_meta_patrimonio(nova_meta)
                meta = nova_meta
        with cm1:
            if meta > 0:
                prog = max(min(pat_atual / meta, 1.0), 0.0) if meta > 0 else 0.0
                st.progress(prog, text=f"{utils.to_br_currency_md(pat_atual)} de {utils.to_br_currency_md(meta)}  ({prog*100:.1f}%)")
                falta = max(meta - pat_atual, 0.0)
                if falta <= 0:
                    st.success("🎉 Meta atingida!")
                elif media_rend_r > 0:
                    st.caption(f"Faltam {utils.to_br_currency_md(falta)} — no ritmo atual de juros (~{utils.to_br_currency_md(media_rend_r)}/mês), cerca de **{falta/media_rend_r:.0f} meses** para a meta.")
                else:
                    st.caption(f"Faltam {utils.to_br_currency_md(falta)} para a meta.")
            else:
                st.caption("Defina uma meta ao lado para acompanhar o progresso. ➡️")

        if ano_selecionado <= utils.ano_atual:
            _meses_fech = meses_calc[:-1] if ano_selecionado == utils.ano_atual else meses_calc
            _quedas = [(m, var_liq[m]) for m in _meses_fech if var_liq[m] < 0]
        else:
            _quedas = []
        if _quedas:
            _um, _uv = _quedas[-1]
            _outros = ", ".join(mm.title() for mm, _ in _quedas[:-1])
            st.warning(f"⚠️ **Alerta de gasto:** em **{_um.title()}** seu patrimônio líquido caiu **{utils.to_br_currency(abs(_uv))}** — você gastou mais do que entrou/rendeu." + (f" (também caiu em: {_outros})" if _outros else ""))
        else:
            st.success("✅ Patrimônio líquido crescendo no período — gastos dentro do limite.")

        _md = utils.mes_atual_nome if ano_selecionado == utils.ano_atual else 'DEZEMBRO'
        st.markdown(f"##### 🗓️ Destaque de {_md.title()}")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Rendimento (juros)", utils.to_br_currency(rend_tot_full[_md]))
        d2.metric("Aportes do mês", utils.to_br_currency(ap_xp[_md] + ap_it[_md] + ap_itau[_md]))
        _pb = prev_bal_full[_md]
        d3.metric("% Retorno", f"{(rend_tot_full[_md] / _pb * 100) if _pb > 0 else 0:.2f}%".replace(".", ","))
        d4.metric("Var. patrimônio", utils.to_br_currency(var_abs[_md]))

        st.markdown("##### 📈 Rendimento Mensal (Investimentos)")
        st.dataframe(pd.DataFrame(dict_rend)[colunas_visiveis].style.apply(lambda r: [f'background-color: {"#FF9900" if r["MESES"] == "RENDIMENTO (JUROS)" else "#FCE4D6" if "VARIAÇÃO" in r["MESES"] else "#E2EFDA" if "APORTES" in r["MESES"] else "#FFF2CC" if "%" in r["MESES"] else "#9BC2E6" if "SALÁRIO" in r["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1), hide_index=True, column_config=cfg_text, use_container_width=True)
        with st.expander("🏛️ Ver patrimônio detalhado por mês"):
            st.dataframe(pd.DataFrame(dict_res_p)[colunas_visiveis].style.apply(lambda r: [f'background-color: {"#FF9900" if r["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in r["MESES"] else "white"}; color: black; font-weight: bold' for _ in colunas_visiveis], axis=1), hide_index=True, column_config=cfg_text, use_container_width=True)

        st.markdown("##### 🔮 Projeção (no ritmo atual de juros)")
        pr1, pr2, pr3 = st.columns(3)
        pr1.metric("Em 6 meses", utils.to_br_currency(pat_atual + media_rend_r * 6))
        pr2.metric("Em 12 meses", utils.to_br_currency(pat_atual + media_rend_r * 12))
        pr3.metric("Em 24 meses", utils.to_br_currency(pat_atual + media_rend_r * 24))
        st.caption(f"Projeção somando ~{utils.to_br_currency(media_rend_r)}/mês de juros ao patrimônio atual (não inclui novos aportes).")

        st.markdown("##### 📅 Comparativo Ano a Ano")
        ca1, ca2 = st.columns(2)
        _cresc_pat = pat_atual - pat_tot_prev_dec
        _pct_pat = (_cresc_pat / pat_tot_prev_dec * 100) if pat_tot_prev_dec else 0.0
        ca1.metric(f"Patrimônio (vs Dez/{ano_selecionado-1})", utils.to_br_currency(pat_atual), delta=f"{utils.to_br_currency(_cresc_pat)}  ({_pct_pat:.1f}%)")
        ca2.metric(f"Rendimento acum. {ano_selecionado}", utils.to_br_currency(rend_acum), delta=f"{utils.to_br_currency(rend_acum - rend_acum_prev)} vs {ano_selecionado-1}")
        st.caption(f"Juros acumulados no mesmo período — {ano_selecionado}: {utils.to_br_currency_md(rend_acum)} · {ano_selecionado-1}: {utils.to_br_currency_md(rend_acum_prev)}.")

    # =====================================================================
    # ABA GRÁFICOS
    # =====================================================================
    with tabs[2]:
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                st.markdown("##### 📈 Evolução Patrimonial")
                st.altair_chart(grafico_area(pat_tot, "#0f9d58"), use_container_width=True)
            with st.container(border=True):
                st.markdown("##### 📊 Rendimento (juros) mensal")
                st.altair_chart(grafico_barra(rend_tot_full, "#0f9d58"), use_container_width=True)
        with g2:
            with st.container(border=True):
                st.markdown("##### 💵 Salário + Rendimento")
                st.altair_chart(grafico_area(tot_e + rend_tot_full, "#2563eb"), use_container_width=True)
            with st.container(border=True):
                st.markdown("##### ☀️ Faturamento Ecoclim")
                st.altair_chart(grafico_linha(serie_ecoclim, "#d97706"), use_container_width=True)
