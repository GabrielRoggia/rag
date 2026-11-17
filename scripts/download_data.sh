#!/usr/bin/env bash
# Baixa o corpus para data/raw (rodar a partir da raiz do repositório).
# Obs.: os links "…/documentos-e-publicacoes/*.pdf" da ANPD devolvem uma página HTML;
# o arquivo real fica em ".../@@download/file".
set -u
mkdir -p data/raw && cd data/raw
UA="Mozilla/5.0 (X11; Linux x86_64)"
dl() { curl -fL --retry 3 -A "$UA" -o "$1" "$2" && echo "ok   $1" || echo "ERRO $1"; }
ANPD="https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes"

dl lgpd.html            "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/L13709.htm"
dl marco_civil.html     "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm"
dl decreto_8771.html    "https://www.planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8771.htm"
dl cdc.html             "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm"
dl anpd_agentes.pdf     "$ANPD/Segunda_Versao_do_Guia_de_Agentes_de_Tratamento_retificada.pdf/@@download/file"
dl anpd_seguranca.pdf   "$ANPD/guia-vf.pdf/@@download/file"
dl anpd_encarregado.pdf "https://www.ba.gov.br/ssp/sites/site-ssp/files/2026-01/41.%20LGPD-ANPD-%20-guia%20orientativo%20-%20encarregado%20tratamento%20dados%20pessoais.pdf"
ls -lh
