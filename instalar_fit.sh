#!/usr/bin/env bash
# Liga a IA (Google Gemini) do app Evolua na API da Ecoclim SEM atualizar o
# código da Ecoclim que já roda no servidor.
# Uso (terminal da VPS):  bash <(curl -fsSL https://raw.githubusercontent.com/forevernithland-bit/ecoclim/main/instalar_fit.sh)
#
# O que faz:
#  1. Confere o servidor (e para se houver algo inesperado).
#  2. Backup do api.py e do .streamlit/secrets.toml.
#  3. Pede a chave do Gemini (não aparece na tela) e grava na 1ª linha do secrets.toml.
#  4. ACRESCENTA o arquivo fit_api.py (novo) e 6 linhas no api.py do servidor —
#     nenhuma linha existente é alterada. NÃO faz git pull.
#  5. Reinicia só o ecoclim-api e testa. Se falhar, desfaz tudo e volta como estava.
# Não toca em n8n, Evolution, crons, nginx nem em outros arquivos da Ecoclim.

set -u
PASTA=/root/ecoclim-bot/ecoclim
SEGREDOS="$PASTA/.streamlit/secrets.toml"
SERVICO=ecoclim-api
RAW=https://raw.githubusercontent.com/forevernithland-bit/ecoclim/main

verde() { printf "\033[32m%s\033[0m\n" "$*"; }
vermelho() { printf "\033[31m%s\033[0m\n" "$*"; }

cd "$PASTA" 2>/dev/null || { vermelho "Pasta $PASTA não encontrada. Nada foi alterado."; exit 1; }

echo "1/5  Conferindo o servidor..."
if ! systemctl is-active --quiet "$SERVICO"; then
  vermelho "O serviço $SERVICO já estava parado antes de começar. Parei — NADA foi alterado."
  exit 1
fi
if [ ! -f api.py ] || ! grep -q 'allow_headers=\["\*"\],' api.py; then
  vermelho "O api.py não está no formato esperado. Parei — NADA foi alterado. Mande o print para o Claude."
  exit 1
fi
verde "     OK"

echo "2/5  Fazendo backup..."
CARIMBO=$(date +%Y%m%d-%H%M%S)
mkdir -p "$PASTA/.streamlit"
cp -p api.py "api.py.bak-$CARIMBO"
[ -f "$SEGREDOS" ] && cp -p "$SEGREDOS" "$SEGREDOS.bak-$CARIMBO"
TINHA_FIT=0; [ -f fit_api.py ] && { TINHA_FIT=1; cp -p fit_api.py "fit_api.py.bak-$CARIMBO"; }
verde "     OK (api.py.bak-$CARIMBO e secrets.toml.bak-$CARIMBO)"

desfazer() {
  vermelho "Algo deu errado — desfazendo tudo..."
  cp -p "api.py.bak-$CARIMBO" api.py
  [ -f "$SEGREDOS.bak-$CARIMBO" ] && cp -p "$SEGREDOS.bak-$CARIMBO" "$SEGREDOS"
  if [ "$TINHA_FIT" = 1 ]; then cp -p "fit_api.py.bak-$CARIMBO" fit_api.py; else rm -f fit_api.py; fi
  systemctl restart "$SERVICO"; sleep 4
  if systemctl is-active --quiet "$SERVICO"; then
    verde "Servidor voltou exatamente como estava. Mande o print para o Claude."
  else
    vermelho "ATENÇÃO: o serviço não voltou. Mande o print para o Claude."
  fi
  exit 1
}

echo "3/5  Chave do Gemini"
read -rsp "     Cole a chave e aperte Enter (ela não aparece na tela): " CHAVE < /dev/tty
echo
CHAVE=$(printf "%s" "$CHAVE" | tr -d '[:space:]"')
if [ ${#CHAVE} -lt 20 ]; then
  vermelho "Chave vazia ou curta demais. Parei — NADA foi alterado."
  rm -f "api.py.bak-$CARIMBO" "fit_api.py.bak-$CARIMBO"
  exit 1
fi
CHAVE="$CHAVE" python3 - "$SEGREDOS" <<'PY' || desfazer
import os, sys
caminho = sys.argv[1]
linhas = open(caminho, encoding="utf-8").read().splitlines() if os.path.exists(caminho) else []
linhas = [l for l in linhas if not l.strip().startswith("GEMINI_API_KEY")]
linhas.insert(0, 'GEMINI_API_KEY = "%s"' % os.environ["CHAVE"])
open(caminho, "w", encoding="utf-8").write("\n".join(linhas) + "\n")
PY
unset CHAVE
verde "     OK (gravada na 1ª linha do secrets.toml)"

echo "4/5  Acrescentando o app fitness (sem mexer no resto)..."
curl -fsSL "$RAW/fit_api.py" -o fit_api.py.novo || desfazer
python3 -c "import ast,sys; ast.parse(open('fit_api.py.novo',encoding='utf-8').read())" || { rm -f fit_api.py.novo; desfazer; }
mv fit_api.py.novo fit_api.py
python3 - <<'PY' || desfazer
p = "api.py"
s = open(p, encoding="utf-8", newline="").read()
if "import fit_api" in s:
    print("     api.py já tinha as linhas do app fitness")
else:
    nl = "\r\n" if "\r\n" in s else "\n"
    marca = 'allow_headers=["*"],' + nl + ")" + nl
    i = s.find(marca)
    if i < 0:
        raise SystemExit("marca não encontrada")
    bloco = nl.join([
        "",
        "# App Evolua (fitness) - rotas /fit/*. Se der erro, a API da Ecoclim segue normal.",
        "try:",
        "    import fit_api",
        "    app.include_router(fit_api.router)",
        "except Exception as e:",
        "    print(f\"[fit] rotas do app fitness desligadas: {e}\")",
        "",
    ])
    j = i + len(marca)
    s = s[:j] + bloco + s[j:]
    open(p, "w", encoding="utf-8", newline="").write(s)
    print("     6 linhas acrescentadas no api.py")
PY
python3 -c "import ast; ast.parse(open('api.py',encoding='utf-8').read())" || desfazer
verde "     OK"

echo "5/5  Reiniciando só a API da Ecoclim e testando..."
systemctl restart "$SERVICO"
# A API leva alguns segundos pra carregar (pandas, Supabase...): espera até 40 s.
DOCS=000
for i in $(seq 1 40); do
  sleep 1
  DOCS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs)
  [ "$DOCS" = "200" ] && break
done
systemctl is-active --quiet "$SERVICO" || desfazer
[ "$DOCS" = "200" ] || desfazer
echo "     API respondeu em ${i}s"
SAUDE=$(curl -s http://127.0.0.1:8000/fit/saude)
verde "     API da Ecoclim no ar ✅"
echo "     App fitness: $SAUDE"
echo
verde "Pronto! O código da Ecoclim não foi atualizado — só foi acrescentado o app fitness."
