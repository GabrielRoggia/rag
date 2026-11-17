"""Análise exploratória do corpus (gera figuras e tabelas em reports/).

Uso: python -m lgpd_rag.eda
"""
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .config import DOCUMENTS, FIG_DIR, PROCESSED_DIR, RESULTS_DIR
from .text import tokenize

sns.set_theme(style="whitegrid")


def main():
    units = pd.read_csv(PROCESSED_DIR / "units.csv")
    chunks = pd.read_csv(PROCESSED_DIR / "chunks.csv")
    clf = pd.read_csv(PROCESSED_DIR / "clf_windows.csv")

    for df in (units, chunks, clf):
        df["n_words"] = df["text"].str.split().str.len()

    # ---------------- qualidade dos dados
    quality = {
        "unidades": len(units),
        "chunks_rag": len(chunks),
        "janelas_classificador": len(clf),
        "textos_vazios_unidades": int((units["text"].fillna("").str.strip() == "").sum()),
        "duplicados_exatos_unidades": int(units.duplicated("text").sum()),
        "duplicados_exatos_janelas": int(clf.duplicated("text").sum()),
        "paginas_pdf_quase_vazias(<30 palavras)": int(((units.kind == "guia") & (units.n_words < 30)).sum()),
    }
    # outliers por IQR no tamanho das unidades
    q1, q3 = units.n_words.quantile([.25, .75])
    iqr = q3 - q1
    quality["outliers_tamanho_unidade(IQR)"] = int((units.n_words > q3 + 1.5 * iqr).sum())
    pd.Series(quality).to_csv(RESULTS_DIR / "eda_qualidade.csv", header=["valor"])

    # ---------------- estatísticas por documento
    stats = units.groupby("doc_id").agg(unidades=("text", "size"), palavras=("n_words", "sum"),
                                        media_palavras=("n_words", "mean"),
                                        mediana=("n_words", "median"), maximo=("n_words", "max"))
    stats["janelas_clf"] = clf.groupby("doc_id").size()
    stats["chunks_rag"] = chunks.groupby("doc_id").size()
    stats = stats.round(1)
    stats.to_csv(RESULTS_DIR / "eda_por_documento.csv")
    print(stats)
    print(pd.Series(quality))

    # ---------------- figuras
    fig, ax = plt.subplots(figsize=(8, 4))
    clf.doc_id.value_counts().plot.barh(ax=ax, color="#4C72B0")
    ax.set_title("Distribuição de classes (janelas do classificador)")
    ax.set_xlabel("nº de janelas")
    fig.tight_layout(); fig.savefig(FIG_DIR / "eda_classes.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.boxplot(data=units, x="n_words", y="doc_id", ax=ax, showfliers=True)
    ax.set_xscale("log")
    ax.set_title("Tamanho das unidades (artigos / páginas) em palavras — escala log")
    fig.tight_layout(); fig.savefig(FIG_DIR / "eda_tamanho_unidades.png", dpi=150); plt.close(fig)

    # termos mais frequentes por documento
    rows = []
    for doc_id, g in units.groupby("doc_id"):
        c = Counter(t for txt in g.text for t in tokenize(txt) if not t.isdigit())
        for term, n in c.most_common(10):
            rows.append({"doc_id": doc_id, "termo": term, "freq": n})
    top = pd.DataFrame(rows)
    top.to_csv(RESULTS_DIR / "eda_top_termos.csv", index=False)

    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    for ax, (doc_id, g) in zip(axes.ravel(), top.groupby("doc_id")):
        ax.barh(g.termo[::-1], g.freq[::-1], color="#55A868")
        ax.set_title(doc_id, fontsize=10)
    axes.ravel()[-1].axis("off")
    fig.suptitle("Top-10 termos por documento (sem stopwords)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "eda_top_termos.png", dpi=150); plt.close(fig)

    # sobreposição de vocabulário entre documentos (Jaccard) -> indica dificuldade da classificação
    vocab = {d: set(t for txt in g.text for t in tokenize(txt)) for d, g in units.groupby("doc_id")}
    ids = list(DOCUMENTS)
    jac = np.array([[len(vocab[a] & vocab[b]) / len(vocab[a] | vocab[b]) for b in ids] for a in ids])
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(pd.DataFrame(jac, ids, ids), annot=True, fmt=".2f", cmap="Blues", ax=ax)
    ax.set_title("Similaridade de vocabulário (Jaccard)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "eda_jaccard.png", dpi=150); plt.close(fig)
    print("Figuras salvas em", FIG_DIR)


if __name__ == "__main__":
    main()
