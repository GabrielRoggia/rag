"""API HTTP do assistente (FastAPI) + frontend estático em web/.

Rodar:  uvicorn app.api:app --port 8000      e abrir http://localhost:8000
"""
import json
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lgpd_rag.answer import OUT_OF_SCOPE_THRESHOLD, answer  # noqa: E402
from lgpd_rag.classifier import explain  # noqa: E402
from lgpd_rag.config import CLASSIFIER_FILE, DOCUMENTS, EVAL_DIR, MODELS_DIR, RESULTS_DIR  # noqa: E402
from lgpd_rag.retrieval import Retriever  # noqa: E402

app = FastAPI(title="LexDados API", version="1.0")
STATE: dict = {}


@app.on_event("startup")
def _load():
    r = Retriever.load()
    _ = r.emb, r.encoder  # embeddings e modelo carregados uma vez
    STATE["retriever"] = r
    STATE["classifier"] = joblib.load(MODELS_DIR / CLASSIFIER_FILE)["pipeline"]


def _doc(doc_id: str) -> dict:
    _fname, kind, name = DOCUMENTS[doc_id]
    return {"id": doc_id, "name": name, "short": name.split(" (")[0].replace("ANPD - ", "ANPD · "), "kind": kind}


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    k: int = Field(5, ge=1, le=10)


@app.post("/api/ask")
def ask(body: AskIn):
    r, clf = STATE["retriever"], STATE["classifier"]
    t0 = time.perf_counter()
    hits, top_sim = r.search(body.question, k=body.k)
    ans = answer(hits, top_sim)
    proba = dict(zip(clf.classes_, clf.predict_proba([body.question])[0]))
    pred, contrib = explain(clf, body.question)
    return {
        "question": body.question,
        "answer": {"text": ans.text, "in_scope": ans.in_scope, "citations": ans.citations},
        "top_similarity": top_sim,
        "scope_threshold": OUT_OF_SCOPE_THRESHOLD,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "hits": [{"rank": h.rank, "score": h.score, "ref": h.ref, "doc": _doc(h.doc_id), "text": h.text}
                 for h in hits] if ans.in_scope else [],
        "classifier": {"predicted": _doc(pred),
                       "proba": sorted([{"doc": _doc(d), "p": float(p)} for d, p in proba.items()],
                                       key=lambda x: -x["p"]),
                       "terms": [{"term": t, "weight": w} for t, w in contrib]},
    }


@app.get("/api/overview")
def overview():
    chunks = STATE["retriever"].chunks
    per_doc = chunks.groupby("doc_id").size()
    ret = pd.read_csv(RESULTS_DIR / "retrieval_metricas.csv").iloc[0].to_dict()
    cmp_ = pd.read_csv(RESULTS_DIR / "clf_comparacao.csv")
    rep = pd.read_csv(RESULTS_DIR / "clf_report_teste.csv", index_col=0)
    return {
        "documents": [{**_doc(d), "chunks": int(per_doc.get(d, 0))} for d in DOCUMENTS],
        "n_chunks": len(chunks),
        "n_questions": int(ret["n"]),
        "retrieval": ret,
        "classifiers": cmp_.fillna(0).to_dict(orient="records"),
        "scope": json.load(open(RESULTS_DIR / "escopo.json")),
        "scope_threshold": OUT_OF_SCOPE_THRESHOLD,
        "clf_ood": json.load(open(RESULTS_DIR / "clf_perguntas_ood.json")),
        "clf_per_class": [{"doc": _doc(i), "precision": row.precision, "recall": row.recall, "f1": row["f1-score"],
                           "support": int(row.support)} for i, row in rep.iterrows() if i in DOCUMENTS],
        "clf_test_f1": float(rep.loc["macro avg", "f1-score"]),
        "clf_test_acc": float(rep.loc["accuracy", "precision"]),
    }


@app.get("/api/evaluation")
def evaluation():
    qa = pd.read_json(EVAL_DIR / "qa_gold.jsonl", lines=True)
    per = pd.read_csv(RESULTS_DIR / "retrieval_por_pergunta.csv")
    out = []
    for row in qa.merge(per, on="id").to_dict(orient="records"):
        arts, kws = row.get("articles"), row.get("keywords")
        out.append({"id": row["id"], "question": row["question"], "doc": _doc(row["doc_id"]),
                    "target": (", ".join(f"Art. {a}" for a in arts) if isinstance(arts, list)
                               else ", ".join(kws) if isinstance(kws, list) else ""),
                    "hit5": bool(row["recall@5"]), "hit10": bool(row["recall@10"]), "rr": float(row["rr"]),
                    "first": None if pd.isna(row["primeiro_relevante"]) else int(row["primeiro_relevante"])})
    return out


WEB = ROOT / "web"
app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
app.mount("/reports", StaticFiles(directory=ROOT / "reports"), name="reports")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
