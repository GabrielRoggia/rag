"""Ingestão: lê leis (HTML do Planalto) e guias da ANPD (PDF) e gera dois datasets.

1. ``chunks.csv``      -> trechos usados pelo RAG (artigos de lei / janelas dos guias)
2. ``clf_windows.csv`` -> janelas curtas rotuladas pela fonte, usadas no classificador

Uso: python -m lgpd_rag.ingest
"""
from __future__ import annotations

import re
import unicodedata

import pymupdf as fitz
import pandas as pd
from bs4 import BeautifulSoup

from .config import (CLF_WINDOW_WORDS, DOCUMENTS, PROCESSED_DIR, RAG_CHUNK_OVERLAP,
                     RAG_CHUNK_WORDS, RAW_DIR)

# Captura "Art. 7º", "Art. 10.", "Art. 55-J." -> ("7", None), ("55", "J")
ART_RE = re.compile(r"^Art\.\s*(\d+)\s*(?:º|o|°)?\s*(?:-\s*([A-Z])\b)?", re.UNICODE)
# Início de dispositivo: inciso romano ("VIII -"), parágrafo ("§ 2º") ou alínea ("a)")
DISP_RE = re.compile(r"^((?:[IVXLC]+\s*[-–])|(?:§\s*\d+)|(?:[a-z]\)))")
CAP_RE = re.compile(r"^CAP[ÍI]TULO\s+([IVXLC]+)", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# --------------------------------------------------------------------------- leis
def read_html_law(path) -> list[str]:
    raw = path.read_bytes()
    # Páginas do Planalto são windows-1252; tenta utf-8 antes.
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("windows-1252", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    # Texto revogado/alterado aparece riscado: remove para não indexar dispositivos revogados.
    for tag in soup.find_all(["strike", "s", "del", "script", "style"]):
        tag.decompose()
    lines = []
    for p in soup.find_all(["p", "h1", "h2", "h3", "h4"]):
        t = normalize(p.get_text(" "))
        if t:
            lines.append(t)
    return lines


def law_to_articles(doc_id: str, lines: list[str]) -> list[dict]:
    """Agrupa as linhas em artigos (caput + parágrafos + incisos)."""
    articles, cur, chapter = [], None, None
    for line in lines:
        # No HTML do Planalto alguns números vêm partidos em tags ("Art. 5<span>7</span>")
        line = re.sub(r"^(Art\.\s*\d+)\s+(\d+)", r"\1\2", line)
        m_cap = CAP_RE.match(line)
        if m_cap:
            chapter = m_cap.group(1)
            continue
        m = ART_RE.match(line)
        if m:
            if cur:
                articles.append(cur)
            label = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
            cur = {"doc_id": doc_id, "article": label, "chapter": chapter, "lines": [line]}
        elif cur is not None:
            # ignora rodapé de assinatura/publicação
            if line.startswith("Este texto não substitui"):
                break
            # anotações de MP rejeitada e linhas repetidas (redação antiga x nova) no Marco Civil
            line = re.sub(r"\((?:Rejeitad[oa]|Promulgação[^)]*)\)", "", line).strip()
            if not line or line in cur["lines"]:
                continue
            # Redações sucessivas do mesmo dispositivo em sequência (ex.: "VIII - ..." 4x no art. 5º
            # da LGPD): mantém só a última, que é a vigente.
            key = DISP_RE.match(line)
            prev = DISP_RE.match(cur["lines"][-1]) if len(cur["lines"]) > 1 else None
            if key and prev and key.group(1) == prev.group(1):
                cur["lines"][-1] = line
            else:
                cur["lines"].append(line)
    if cur:
        articles.append(cur)
    # Em leis compiladas um mesmo número pode reaparecer; mantém a versão mais completa
    # e descarta dispositivos apenas vetados/revogados.
    best: dict[str, dict] = {}
    for a in articles:
        text = " ".join(a["lines"])
        text = re.sub(r"\((?:Incluíd|Redação dada|Vide|Revogad|Vigência|Produção)[^)]*\)", "", text)
        text = re.sub(r"\b(?:Vigência|Produção de efeitos?)\b", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        body = re.sub(r"^Art\.\s*\S+\s*", "", text)
        if len(text.split()) < 4 or re.fullmatch(r"[\s\.\-–]*\((?:VETADO|Revogad[oa])\)[\s\.]*", body, re.I):
            continue
        if a["article"] not in best or len(text) > len(best[a["article"]]["text"]):
            best[a["article"]] = {"doc_id": a["doc_id"], "article": a["article"], "chapter": a["chapter"],
                                  "page": None, "text": text}
    return list(best.values())


# --------------------------------------------------------------------------- PDFs
def read_pdf_pages(path) -> list[tuple[int, str]]:
    pages = []
    with fitz.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            t = page.get_text("text")
            t = re.sub(r"-\n(\w)", r"\1", t)  # hifenização de quebra de linha
            t = re.sub(r"(?:\s?\.){4,}\s*\d*", " ", t)  # pontilhado de sumário ("Título ........ 12")
            t = normalize(re.sub(r"\s*\n\s*", " ", t))
            pages.append((i, t))
    return pages


def windows(words: list[str], size: int, overlap: int) -> list[list[str]]:
    if len(words) <= size:
        return [words]
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        out.append(words[start:start + size])
        if start + size >= len(words):
            break
    return out


# --------------------------------------------------------------------------- build
def build_units() -> pd.DataFrame:
    """Unidades 'naturais': artigos (leis) e páginas (guias)."""
    rows = []
    for doc_id, (fname, kind, _name) in DOCUMENTS.items():
        path = RAW_DIR / fname
        if kind == "lei":
            rows += law_to_articles(doc_id, read_html_law(path))
        else:
            for pg, text in read_pdf_pages(path):
                rows.append({"doc_id": doc_id, "article": None, "chapter": None, "page": pg, "text": text})
    df = pd.DataFrame(rows)
    df["kind"] = df["doc_id"].map(lambda d: DOCUMENTS[d][1])
    df["unit_id"] = df.apply(
        lambda r: f"{r.doc_id}:art{r.article}" if pd.notna(r.article) else f"{r.doc_id}:p{int(r.page)}", axis=1)
    return df


def build_rag_chunks(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for u in units.itertuples():
        for j, w in enumerate(windows(u.text.split(), RAG_CHUNK_WORDS, RAG_CHUNK_OVERLAP)):
            text = " ".join(w)
            if len(w) < 8:
                continue
            rows.append({"chunk_id": f"{u.unit_id}#{j}", "unit_id": u.unit_id, "doc_id": u.doc_id,
                         "kind": u.kind, "article": u.article, "chapter": u.chapter, "page": u.page,
                         "text": text})
    return pd.DataFrame(rows)


def build_clf_windows(units: pd.DataFrame) -> pd.DataFrame:
    """Janelas curtas SEM sobreposição; 'group' = unidade de origem (evita vazamento no split)."""
    rows = []
    for u in units.itertuples():
        ws = windows(u.text.split(), CLF_WINDOW_WORDS, 0)
        for w in ws:
            if len(w) < 15:  # fragmentos muito curtos não carregam sinal
                continue
            rows.append({"group": u.unit_id, "doc_id": u.doc_id, "kind": u.kind, "text": " ".join(w)})
    return pd.DataFrame(rows)


def main():
    units = build_units()
    units.to_csv(PROCESSED_DIR / "units.csv", index=False)
    chunks = build_rag_chunks(units)
    chunks.to_csv(PROCESSED_DIR / "chunks.csv", index=False)
    clf = build_clf_windows(units)
    clf.to_csv(PROCESSED_DIR / "clf_windows.csv", index=False)
    print(f"unidades: {len(units)} | chunks RAG: {len(chunks)} | janelas classificador: {len(clf)}")
    print(units.groupby("doc_id").size().rename("unidades"))
    print(clf.groupby("doc_id").size().rename("janelas"))


if __name__ == "__main__":
    main()
