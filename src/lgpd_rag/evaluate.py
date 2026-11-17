"""Avaliação do RAG com um gold set de perguntas anotadas manualmente.

- Recuperação híbrida: Recall@k, MRR@10 e nDCG@10
- Detector de fora de escopo: ROC/AUC da similaridade do melhor trecho (perguntas do domínio x de fora)

Relevância: um trecho é relevante se for do documento esperado E (quando anotado) do artigo
esperado E (quando anotado) contiver todas as palavras-chave esperadas.

Uso: python -m lgpd_rag.evaluate
"""
import json
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from .config import EVAL_DIR, FIG_DIR, RESULTS_DIR
from .retrieval import Retriever
from .text import strip_accents

KS = [1, 3, 5, 10]


def is_relevant(chunk, gold) -> bool:
    if chunk.doc_id != gold["doc_id"]:
        return False
    arts = gold.get("articles")
    if arts and str(chunk.article) not in [str(a) for a in arts]:
        return False
    kws = gold.get("keywords")
    if kws:
        t = strip_accents(chunk.text.lower())
        if not all(strip_accents(k.lower()) in t for k in kws):
            return False
    return True


def evaluate_retrieval(r: Retriever, qa: list[dict]) -> tuple[dict, pd.DataFrame, list[float]]:
    rows, sims = [], []
    t0 = time.perf_counter()
    for g in qa:
        rel = np.array([is_relevant(c, g) for c in r.chunks.itertuples()])
        if not rel.any():
            raise ValueError(f"pergunta sem nenhum trecho relevante no corpus: {g['question']}")
        s, dense = r.scores(g["question"])
        sims.append(float(dense.max()))
        hits = rel[np.argsort(-s)[:10]]
        first = np.flatnonzero(hits)
        dcg = sum(1 / np.log2(i + 2) for i in np.flatnonzero(hits))
        idcg = sum(1 / np.log2(i + 2) for i in range(min(10, rel.sum())))
        row = {"id": g["id"], "rr": 1.0 / (first[0] + 1) if len(first) else 0.0, "ndcg10": dcg / idcg,
               "primeiro_relevante": int(first[0] + 1) if len(first) else None}
        row.update({f"recall@{k}": float(hits[:k].any()) for k in KS})
        rows.append(row)
    ms = (time.perf_counter() - t0) / len(qa) * 1000
    d = pd.DataFrame(rows)
    summary = {**{f"Recall@{k}": d[f"recall@{k}"].mean() for k in KS},
               "MRR@10": d.rr.mean(), "nDCG@10": d.ndcg10.mean(), "ms/consulta": ms, "n": len(qa)}
    return summary, d, sims


def evaluate_scope(r: Retriever, sims_in: list[float], oos: list[str]) -> dict:
    sims_out = [float(r.dense_scores(q).max()) for q in oos]
    y = np.r_[np.ones(len(sims_in)), np.zeros(len(sims_out))]
    s = np.r_[sims_in, sims_out]
    auc = roc_auc_score(y, s)
    fpr, tpr, thr = roc_curve(y, s)
    j = np.argmax(tpr - fpr)  # índice de Youden
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(fpr, tpr, label=f"AUC = {auc:.3f}"); axes[0].plot([0, 1], [0, 1], "--", c="gray")
    axes[0].scatter(fpr[j], tpr[j], c="red", zorder=3, label=f"limiar Youden = {thr[j]:.3f}")
    axes[0].set_xlabel("FPR"); axes[0].set_ylabel("TPR"); axes[0].legend(); axes[0].set_title("ROC — detector de fora de escopo")
    axes[1].hist(sims_in, bins=15, alpha=.7, label="perguntas do domínio")
    axes[1].hist(sims_out, bins=15, alpha=.7, label="perguntas fora do domínio")
    axes[1].axvline(thr[j], c="red", ls="--"); axes[1].legend(); axes[1].set_title("Similaridade do melhor trecho")
    fig.tight_layout(); fig.savefig(FIG_DIR / "escopo_roc.png", dpi=150); plt.close(fig)
    out = {"auc": auc, "limiar_youden": float(thr[j]), "tpr": float(tpr[j]), "fpr": float(fpr[j]),
           "n_in": len(sims_in), "n_out": len(sims_out)}
    print("escopo:", out)
    return out


def main():
    qa = [json.loads(l) for l in open(EVAL_DIR / "qa_gold.jsonl", encoding="utf-8")]
    oos = [json.loads(l)["question"] for l in open(EVAL_DIR / "out_of_scope.jsonl", encoding="utf-8")]
    r = Retriever.load()
    _ = r.emb, r.encoder  # pré-computa embeddings e carrega o modelo antes de medir o tempo

    summary, per_q, sims = evaluate_retrieval(r, qa)
    print({k: round(v, 3) for k, v in summary.items()})
    pd.DataFrame([summary]).round(3).to_csv(RESULTS_DIR / "retrieval_metricas.csv", index=False)
    per_q.to_csv(RESULTS_DIR / "retrieval_por_pergunta.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 3.6))
    keys = ["Recall@1", "Recall@3", "Recall@5", "Recall@10", "MRR@10", "nDCG@10"]
    bars = ax.bar(keys, [summary[k] for k in keys], color="#f75500")
    ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    ax.set_ylim(0, 1.08); ax.set_title(f"Recuperação híbrida no gold set ({len(qa)} perguntas)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "retrieval_metricas.png", dpi=150); plt.close(fig)

    json.dump(evaluate_scope(r, sims, oos), open(RESULTS_DIR / "escopo.json", "w"), indent=2)


if __name__ == "__main__":
    main()
