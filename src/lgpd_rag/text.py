"""Pré-processamento de texto compartilhado (classificador, BM25, TF-IDF)."""
import re
import unicodedata

# Stopwords PT-BR básicas (lista enxuta para não depender de NLTK)
STOPWORDS = set("""
a à ao aos as às até com como da das de dela dele deles demais do dos e é ela elas ele eles em
entre era essa essas esse esses esta está estas este estes eu foi for há isso isto já la lhe
lo mais mas me mesmo meu minha na nas nem no nos nós num numa o os ou para pela pelas pelo
pelos por qual quando que quem se sem ser seu seus si só sua suas também te tem têm um uma
umas uns vos será serão sobre sob após caso cada onde pode podem deve devem deverá deverão
""".split())


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[str]:
    text = strip_accents(text.lower())
    toks = re.findall(r"[a-z0-9]+", text)
    stop = {strip_accents(w) for w in STOPWORDS}
    return [t for t in toks if t not in stop and len(t) > 1]


def clean_for_vectorizer(text: str) -> str:
    """Normalização usada pelo TfidfVectorizer: minúsculas, sem acento, sem dígitos isolados."""
    text = strip_accents(text.lower())
    text = re.sub(r"\b\d+\b", " ", text)  # números de artigos/incisos são 'atalhos' da fonte
    return text
