# Assistente de consulta à LGPD (recuperação híbrida + classificador de fontes)

Trabalho 1 de Inteligência Artificial II (AMF, 2026/02). O relatório completo está em [reports/relatorio.pdf](reports/relatorio.pdf).

Dada uma pergunta sobre proteção de dados, o sistema recupera os trechos relevantes da LGPD, do Marco Civil da Internet, do Decreto 8.771/2016, do CDC e de três guias da ANPD, e os mostra com o artigo ou a página de origem.

## Componentes de ML

| Tarefa | Técnica | Resultado |
|---|---|---|
| Recuperação de trechos | BM25 + embeddings E5, fundidos por Reciprocal Rank Fusion | Recall@5 0,85 · Recall@10 0,91 · MRR@10 0,70 (46 perguntas anotadas) |
| Classificação da fonte (7 classes) | TF-IDF + ComplementNB / Regressão Logística / LinearSVC, GridSearch com StratifiedGroupKFold | F1-macro no teste 0,82 (baseline 0,03) |
| Detecção de fora de escopo | limiar na similaridade do melhor trecho, escolhido pela curva ROC | ROC AUC 0,998 |

Os números saem de `reports/results/` e mudam se o corpus for baixado de novo, porque as leis compiladas são atualizadas.

## Estrutura

```
data/raw/            documentos originais (HTML do Planalto, PDFs da ANPD)
data/processed/      unidades, trechos indexados, janelas rotuladas (gerados)
data/eval/           gold set: 46 perguntas anotadas + 25 fora de escopo
src/lgpd_rag/        ingest · eda · classifier · retrieval · answer · evaluate
app/api.py           API (FastAPI) que serve a interface
web/                 interface web (HTML/CSS/JS)
scripts/             download dos dados, screenshots, geração do relatório PDF
tests/               testes da resposta, da guarda de escopo, da fusão e do parser
reports/             relatorio.pdf, figures/, results/, screenshots/
```

## Como reproduzir

Requer Python 3.10 ou superior. Os comandos abaixo são para Windows; no Linux/Mac, ative o ambiente com `source .venv/bin/activate`.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Os dados já estão em `data/raw/`. Para baixá-los de novo:

```bash
bash scripts/download_data.sh
```

Para rodar o experimento completo (ingestão, EDA, classificador e avaliação):

```bash
python run_all.py
```

```bash
pytest -q tests
```

### Interface web (LexDados)

```bash
uvicorn app.api:app --port 8000
```

Depois abra http://localhost:8000. A primeira inicialização leva alguns segundos, porque carrega o modelo de embeddings. A interface tem três páginas:

- **Consulta:** pergunta, trechos recuperados com a fonte e os termos destacados, e o classificador de fonte com a explicação da decisão.
- **Painel:** métricas da recuperação, dos classificadores e do detector de escopo.
- **Avaliação:** resultado da busca pergunta a pergunta (clique para executar) e métricas por classe do classificador.

Tem tema claro e escuro e se adapta ao celular. Endpoints da API: `/api/ask` (POST), `/api/overview` e `/api/evaluation`.

Para regenerar os screenshots e o relatório, deixe a API rodando e execute os comandos abaixo. Os screenshots usam o Playwright com o Microsoft Edge instalado; para usar o Chromium, rode `playwright install chromium` e remova `channel="msedge"`.

```bash
python scripts/screenshots_web.py
```

```bash
python scripts/build_report.py
```

> Ferramenta informativa. Não substitui orientação jurídica.
