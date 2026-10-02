#!/usr/bin/env bash
# Atualiza SÓ o arquivo fit_api.py (app Evolua) na VPS da Ecoclim.
# Uso (terminal da VPS):  bash <(curl -fsSL https://raw.githubusercontent.com/forevernithland-bit/ecoclim/main/atualizar_fit.sh)
#
# O que faz:
#  1. Confere o servidor (e para se houver algo inesperado).
#  2. Backup do fit_api.py atual.
#  3. Baixa o fit_api.py novo do GitHub e confere a sintaxe.
#  4. Reinicia só o ecoclim-api e testa. Se falhar, volta o arquivo antigo.
# Não mexe no api.py, no secrets.toml, em n8n, Evolution, crons, nginx nem em
# nenhum outro arquivo da Ecoclim. Não faz git pull.

set -u
PASTA=/root/ecoclim-bot/ecoclim
SERVICO=ecoclim-api
RAW=https://raw.githubusercontent.com/forevernithland-bit/ecoclim/main

verde() { printf "\033[32m%s\033[0m\n" "$*"; }
vermelho() { printf "\033[31m%s\033[0m\n" "$*"; }
amarelo() { printf "\033[33m%s\033[0m\n" "$*"; }

cd "$PASTA" 2>/dev/null || { vermelho "Pasta $PASTA não encontrada. Nada foi alterado."; exit 1; }

echo "1/4  Conferindo o servidor..."
systemctl is-active --quiet "$SERVICO" || { vermelho "O $SERVICO já estava parado. Parei — NADA foi alterado."; exit 1; }
[ -f fit_api.py ] || { vermelho "fit_api.py não existe aqui (rode o instalar_fit.sh antes). NADA foi alterado."; exit 1; }
grep -q "import fit_api" api.py || { vermelho "O api.py não carrega o app fitness. NADA foi alterado. Mande o print para o Claude."; exit 1; }
python3 -c "import tomllib" 2>/dev/null || { vermelho "Python sem tomllib (precisa 3.11+). NADA foi alterado. Mande o print para o Claude."; exit 1; }
if grep -q "^\[google_oauth\]" .streamlit/secrets.toml 2>/dev/null; then
  verde "     OK (login do Google Drive do ERP encontrado)"
else
  amarelo "     Atenção: não achei [google_oauth] no secrets.toml — a IA continua, mas as fotos ficam só no celular."
fi

echo "2/4  Backup..."
CARIMBO=$(date +%Y%m%d-%H%M%S)
cp -p fit_api.py "fit_api.py.bak-$CARIMBO"
verde "     OK (fit_api.py.bak-$CARIMBO)"

desfazer() {
  vermelho "Algo deu errado — voltando o arquivo antigo..."
  cp -p "fit_api.py.bak-$CARIMBO" fit_api.py
  systemctl restart "$SERVICO"; sleep 6
  if systemctl is-active --quiet "$SERVICO"; then verde "Servidor voltou exatamente como estava. Mande o print para o Claude."
  else vermelho "ATENÇÃO: o serviço não voltou. Mande o print para o Claude."; fi
  exit 1
}

echo "3/4  Baixando a versão nova..."
curl -fsSL "$RAW/fit_api.py?$(date +%s)" -o fit_api.py.novo || { rm -f fit_api.py.novo; vermelho "Não consegui baixar. NADA foi alterado."; exit 1; }
python3 -c "import ast; ast.parse(open('fit_api.py.novo',encoding='utf-8').read())" || { rm -f fit_api.py.novo; vermelho "Arquivo baixado com erro. NADA foi alterado."; exit 1; }
mv fit_api.py.novo fit_api.py
verde "     OK"

echo "4/4  Reiniciando só a API da Ecoclim e testando..."
systemctl restart "$SERVICO"
DOCS=000
for i in $(seq 1 40); do
  sleep 1
  DOCS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs)
  [ "$DOCS" = "200" ] && break
done
systemctl is-active --quiet "$SERVICO" || desfazer
[ "$DOCS" = "200" ] || desfazer
SAUDE=$(curl -s http://127.0.0.1:8000/fit/saude)
echo "$SAUDE" | grep -q '"ok":true' || desfazer
verde "     API da Ecoclim no ar ✅ (respondeu em ${i}s)"
echo "     App fitness: $SAUDE"
if echo "$SAUDE" | grep -q '"fotos_drive":true'; then
  verde "Pronto! Fotos do Evolua agora vão pro Google Drive (pasta do ERP) e as de prato se apagam sozinhas após 60 dias."
else
  amarelo "Pronto, mas o Drive não está ligado (fotos_drive=false). Mande o print para o Claude."
fi
