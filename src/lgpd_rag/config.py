"""Configurações centrais do projeto (caminhos, documentos, hiperparâmetros)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
EVAL_DIR = ROOT / "data" / "eval"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
RESULTS_DIR = REPORTS_DIR / "results"

SEED = 42

# Corpus: id -> (arquivo, tipo, nome legível)
DOCUMENTS = {
    "lgpd": ("lgpd.html", "lei", "Lei 13.709/2018 (LGPD)"),
    "marco_civil": ("marco_civil.html", "lei", "Lei 12.965/2014 (Marco Civil da Internet)"),
    "decreto_8771": ("decreto_8771.html", "lei", "Decreto 8.771/2016 (regulamenta o Marco Civil)"),
    "cdc": ("cdc.html", "lei", "Lei 8.078/1990 (Código de Defesa do Consumidor)"),
    "anpd_agentes": ("anpd_agentes.pdf", "guia", "ANPD - Guia de Agentes de Tratamento e Encarregado"),
    "anpd_seguranca": ("anpd_seguranca.pdf", "guia", "ANPD - Guia de Segurança da Informação para ATPP"),
    "anpd_encarregado": ("anpd_encarregado.pdf", "guia", "ANPD - Guia Orientativo sobre o Encarregado"),
}

# Chunking para o RAG (palavras)
RAG_CHUNK_WORDS = 220
RAG_CHUNK_OVERLAP = 50

# Janelas menores para o dataset do classificador (palavras)
CLF_WINDOW_WORDS = 60

# Modelo de embeddings (multilíngue, pequeno o bastante para CPU)
EMBED_MODEL = "intfloat/multilingual-e5-small"

# Arquivo do classificador de fonte treinado
CLASSIFIER_FILE = "classificador_fonte.joblib"

for d in (PROCESSED_DIR, EVAL_DIR, MODELS_DIR, FIG_DIR, RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
