"""Montagem da resposta: guarda de escopo + resposta extrativa (trechos mais relevantes com a fonte).

A guarda de escopo é um classificador binário por limiar: se a similaridade do melhor trecho for
menor que o limiar, a pergunta é considerada fora do domínio dos documentos indexados.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .retrieval import Hit

# Similaridade (cosseno E5) mínima do melhor trecho. Limiar de Youden na curva ROC ≈ 0,86
# (reports/results/escopo.json); arredondado para baixo para priorizar não recusar perguntas válidas.
OUT_OF_SCOPE_THRESHOLD = 0.85


@dataclass
class Answer:
    text: str
    in_scope: bool
    citations: list[int] = field(default_factory=list)


def in_scope(top_similarity: float) -> bool:
    return top_similarity >= OUT_OF_SCOPE_THRESHOLD


def answer(hits: list[Hit], top_similarity: float, n: int = 3) -> Answer:
    if not in_scope(top_similarity):
        return Answer("A pergunta parece estar fora do escopo dos documentos indexados "
                      "(LGPD, Marco Civil, Decreto 8.771, CDC e guias da ANPD).", in_scope=False)
    parts = [f"**[{h.rank}] {h.ref}** — {h.text[:600]}{'…' if len(h.text) > 600 else ''}" for h in hits[:n]]
    return Answer("Trechos mais relevantes encontrados:\n\n" + "\n\n".join(parts), in_scope=True,
                  citations=[h.rank for h in hits[:n]])
