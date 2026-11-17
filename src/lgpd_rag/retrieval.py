"""Recuperação híbrida de trechos: BM25 (léxico) + embeddings E5 (semântico), fundidos por RRF.

Uso programático:
    r = Retriever.load()
    hits, similaridade = r.search("Quais são as bases legais?", k=5)
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

from .config import DOCUMENTS, EMBED_MODEL, MODELS_DIR, PROCESSED_DIR
from .text import tokenize

RRF_K = 60  # constante padrão do Reciprocal Rank Fusion


def _minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = x.min(), x.max()
    return np.zeros_like(x) if hi - lo < 1e-12 else (x - lo) / (hi - lo)


def _rrf(*score_lists: np.ndarray) -> np.ndarray:
    """Reciprocal Rank Fusion: soma 1 / (k + posição) de cada ranking."""
    fused = np.zeros(len(score_lists[0]))
    for s in score_lists:
        order = np.argsort(-s)
        ranks = np.empty_like(order); ranks[order] = np.arange(len(order))
        fused += 1.0 / (RRF_K + ranks + 1)
    return _minmax(fused)


@dataclass
class Hit:
    rank: int
    score: float
    chunk_id: str
    doc_id: str
    doc_name: str
    article: str | None
    page: int | None
    text: str

    @property
    def ref(self) -> str:
        if self.article and str(self.article) != "nan":
            return f"{self.doc_name}, Art. {self.article}"
        return f"{self.doc_name}, p. {self.page}"


class Retriever:
    def __init__(self, chunks: pd.DataFrame):
        self.chunks = chunks.reset_index(drop=True)
        self.texts = self.chunks.text.tolist()
        self.bm25 = BM25Okapi([tokenize(t) for t in self.texts])

    @classmethod
    def load(cls) -> "Retriever":
        return cls(pd.read_csv(PROCESSED_DIR / "chunks.csv", dtype={"article": str}))

    @cached_property
    def encoder(self):
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(EMBED_MODEL)

    @cached_property
    def emb(self) -> np.ndarray:
        cache = MODELS_DIR / "chunk_embeddings.npy"
        ids_cache = MODELS_DIR / "chunk_embeddings_ids.txt"
        ids = "\n".join(self.chunks.chunk_id)
        if cache.exists() and ids_cache.exists() and ids_cache.read_text(encoding="utf-8") == ids:
            return np.load(cache)
        # modelos E5 esperam o prefixo "passage: " / "query: "
        e = self.encoder.encode([f"passage: {t}" for t in self.texts], batch_size=32,
                                normalize_embeddings=True, show_progress_bar=True)
        np.save(cache, e); ids_cache.write_text(ids, encoding="utf-8")
        return e

    def dense_scores(self, query: str) -> np.ndarray:
        """Similaridade de cosseno entre a pergunta e cada trecho (vetores normalizados)."""
        q = self.encoder.encode([f"query: {query}"], normalize_embeddings=True)[0]
        return self.emb @ q

    def scores(self, query: str) -> tuple[np.ndarray, np.ndarray]:
        """Retorna (score híbrido, similaridade densa) para todos os trechos."""
        dense = self.dense_scores(query)
        bm25 = self.bm25.get_scores(tokenize(query))
        return _rrf(bm25, dense), dense

    def search(self, query: str, k: int = 5) -> tuple[list[Hit], float]:
        """Os k trechos mais relevantes e a similaridade do melhor trecho (usada na guarda de escopo)."""
        s, dense = self.scores(query)
        out = []
        for r, i in enumerate(np.argsort(-s)[:k], start=1):
            c = self.chunks.iloc[i]
            out.append(Hit(rank=r, score=float(s[i]), chunk_id=c.chunk_id, doc_id=c.doc_id,
                           doc_name=DOCUMENTS[c.doc_id][2],
                           article=None if pd.isna(c.article) else str(c.article),
                           page=None if pd.isna(c.page) else int(c.page), text=c.text))
        return out, float(dense.max())
