"""Tarefa supervisionada: classificar um trecho/pergunta na FONTE normativa (7 classes).

Na interface, o classificador indica de qual norma a pergunta trata e explica a decisão
termo a termo (contribuição TF-IDF × coeficiente).

Estratégia experimental
- Split treino/teste 80/20 por GRUPO (artigo/página de origem) -> janelas do mesmo
  artigo nunca ficam dos dois lados, evitando vazamento.
- Seleção de modelo/hiperparâmetros com GridSearchCV + StratifiedGroupKFold(5) só no treino.
- Avaliação final no teste + teste "fora de distribuição" com as perguntas do gold set.

Uso: python -m lgpd_rag.classifier
"""
import json

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score)
from sklearn.model_selection import GridSearchCV, GroupShuffleSplit, StratifiedGroupKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .config import CLASSIFIER_FILE, EVAL_DIR, FIG_DIR, MODELS_DIR, PROCESSED_DIR, RESULTS_DIR, SEED
from .text import clean_for_vectorizer


def make_pipeline(clf):
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=clean_for_vectorizer, sublinear_tf=True,
                                  min_df=2, max_df=0.9)),
        ("clf", clf),
    ])


SEARCH_SPACE = {
    "ComplementNB": (ComplementNB(), {
        "tfidf__ngram_range": [(1, 1), (1, 2)],
        "clf__alpha": [0.1, 0.3, 1.0],
    }),
    "LogisticRegression": (LogisticRegression(max_iter=3000, class_weight="balanced", random_state=SEED), {
        "tfidf__ngram_range": [(1, 1), (1, 2)],
        "clf__C": [1, 10, 30],
    }),
    "LinearSVC": (LinearSVC(class_weight="balanced", random_state=SEED), {
        "tfidf__ngram_range": [(1, 1), (1, 2)],
        "clf__C": [0.1, 0.5, 1.0],
    }),
}


def split(df):
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    tr, te = next(gss.split(df, df.doc_id, groups=df.group))
    return df.iloc[tr].reset_index(drop=True), df.iloc[te].reset_index(drop=True)


def plot_cm(y_true, y_pred, labels, title, path):
    cm = confusion_matrix(y_true, y_pred, labels=labels, normalize="true")
    fig, ax = plt.subplots(figsize=(8, 6.5))
    sns.heatmap(cm, annot=True, fmt=".2f", cmap="Blues", xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_xlabel("previsto"); ax.set_ylabel("real"); ax.set_title(title)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def top_features(pipe, k=12):
    """Interpretação: maiores coeficientes por classe (modelo linear => contribuição exata)."""
    vec, clf = pipe.named_steps["tfidf"], pipe.named_steps["clf"]
    est = clf
    if isinstance(clf, CalibratedClassifierCV):
        est = clf.calibrated_classifiers_[0].estimator
    coefs = est.feature_log_prob_ if hasattr(est, "feature_log_prob_") else est.coef_
    names = np.array(vec.get_feature_names_out())
    out = {}
    for i, c in enumerate(est.classes_):
        out[c] = names[np.argsort(coefs[i])[::-1][:k]].tolist()
    return out


def explain(pipe, text, k=8):
    """Contribuição de cada termo (tf-idf * coef) para a classe prevista — explicação local."""
    vec = pipe.named_steps["tfidf"]
    clf = pipe.named_steps["clf"]
    est = clf.calibrated_classifiers_[0].estimator if isinstance(clf, CalibratedClassifierCV) else clf
    x = vec.transform([text])
    pred = pipe.predict([text])[0]
    ci = list(est.classes_).index(pred)
    coefs = est.feature_log_prob_[ci] if hasattr(est, "feature_log_prob_") else est.coef_[ci]
    names = vec.get_feature_names_out()
    contrib = {names[j]: float(x[0, j] * coefs[j]) for j in x.nonzero()[1]}
    return pred, sorted(contrib.items(), key=lambda kv: -kv[1])[:k]


def main():
    df = pd.read_csv(PROCESSED_DIR / "clf_windows.csv")
    train, test = split(df)
    print(f"treino: {len(train)} janelas ({train.group.nunique()} grupos) | "
          f"teste: {len(test)} janelas ({test.group.nunique()} grupos)")
    labels = sorted(df.doc_id.unique())

    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    rows, best = [], None
    # baseline
    dummy = DummyClassifier(strategy="most_frequent").fit(train.text, train.doc_id)
    rows.append({"modelo": "Baseline (classe majoritária)", "melhores_params": "-", "f1_macro_cv": np.nan,
                 "acc_treino": accuracy_score(train.doc_id, dummy.predict(train.text)),
                 "acc_teste": accuracy_score(test.doc_id, dummy.predict(test.text)),
                 "f1_macro_treino": f1_score(train.doc_id, dummy.predict(train.text), average="macro"),
                 "f1_macro_teste": f1_score(test.doc_id, dummy.predict(test.text), average="macro")})

    for name, (est, grid) in SEARCH_SPACE.items():
        gs = GridSearchCV(make_pipeline(est), grid, cv=cv, scoring="f1_macro", n_jobs=-1)
        gs.fit(train.text, train.doc_id, groups=train.group)
        m = gs.best_estimator_
        ptr, pte = m.predict(train.text), m.predict(test.text)
        row = {"modelo": name, "melhores_params": json.dumps(gs.best_params_), "f1_macro_cv": gs.best_score_,
               "acc_treino": accuracy_score(train.doc_id, ptr), "acc_teste": accuracy_score(test.doc_id, pte),
               "f1_macro_treino": f1_score(train.doc_id, ptr, average="macro"),
               "f1_macro_teste": f1_score(test.doc_id, pte, average="macro")}
        rows.append(row)
        print(f"{name:20s} cv={gs.best_score_:.3f} teste={row['f1_macro_teste']:.3f} {gs.best_params_}")
        if best is None or gs.best_score_ > best[1]:
            best = (name, gs.best_score_, gs.best_params_)

    res = pd.DataFrame(rows).round(4)
    res.to_csv(RESULTS_DIR / "clf_comparacao.csv", index=False)

    # modelo final: melhor configuração re-treinada no treino; LinearSVC é calibrado p/ ter probabilidades
    name, _, params = best
    est = SEARCH_SPACE[name][0]
    final = make_pipeline(est).set_params(**params)
    if not hasattr(est, "predict_proba"):
        final.set_params(clf=CalibratedClassifierCV(est.set_params(**{k[5:]: v for k, v in params.items()
                                                                       if k.startswith("clf__")}),
                                                    cv=3, method="sigmoid"))
    final.fit(train.text, train.doc_id)
    pte = final.predict(test.text)
    report = classification_report(test.doc_id, pte, digits=3, output_dict=True)
    pd.DataFrame(report).T.round(3).to_csv(RESULTS_DIR / "clf_report_teste.csv")
    print(classification_report(test.doc_id, pte, digits=3))
    plot_cm(test.doc_id, pte, labels, f"Matriz de confusão (teste) — {name}", FIG_DIR / "clf_confusao_teste.png")

    # train x test (diagnóstico de over/underfitting)
    fig, ax = plt.subplots(figsize=(8, 4))
    r = res.set_index("modelo")[["f1_macro_treino", "f1_macro_cv", "f1_macro_teste"]]
    r.plot.bar(ax=ax, rot=15); ax.set_ylim(0, 1.05); ax.set_title("F1-macro: treino x validação cruzada x teste")
    fig.tight_layout(); fig.savefig(FIG_DIR / "clf_treino_teste.png", dpi=150); plt.close(fig)

    # teste fora da distribuição: perguntas reais do gold set (rótulo = documento esperado)
    qa_path = EVAL_DIR / "qa_gold.jsonl"
    if qa_path.exists():
        qa = pd.read_json(qa_path, lines=True)
        pq = final.predict(qa.question)
        ood = {"acc_perguntas": accuracy_score(qa.doc_id, pq),
               "f1_macro_perguntas": f1_score(qa.doc_id, pq, average="macro", labels=labels, zero_division=0),
               "n": len(qa)}
        print("perguntas (OOD):", ood)
        json.dump(ood, open(RESULTS_DIR / "clf_perguntas_ood.json", "w"), indent=2)
        plot_cm(qa.doc_id, pq, labels, "Matriz de confusão — perguntas do gold set",
                FIG_DIR / "clf_confusao_perguntas.png")

    feats = top_features(final)
    json.dump(feats, open(RESULTS_DIR / "clf_top_termos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # re-treina com TODOS os dados para uso no app (avaliação já foi feita acima)
    final.fit(df.text, df.doc_id)
    joblib.dump({"pipeline": final, "model_name": name, "params": params}, MODELS_DIR / CLASSIFIER_FILE)
    print("modelo salvo:", MODELS_DIR / CLASSIFIER_FILE)


if __name__ == "__main__":
    main()
