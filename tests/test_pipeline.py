"""Testes da montagem da resposta, da guarda de escopo e do parser de leis.  Rodar:  pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lgpd_rag.answer import OUT_OF_SCOPE_THRESHOLD, answer, in_scope  # noqa: E402
from lgpd_rag.ingest import law_to_articles  # noqa: E402
from lgpd_rag.retrieval import Hit, _rrf  # noqa: E402

import numpy as np  # noqa: E402


def _hits(n=3):
    return [Hit(i, 1.0, f"c{i}", "lgpd", "LGPD", str(i), None, f"texto {i}") for i in range(1, n + 1)]


def test_fora_de_escopo_bloqueia():
    a = answer(_hits(), top_similarity=0.1)
    assert not a.in_scope and a.citations == []


def test_dentro_do_escopo_cita_os_trechos():
    a = answer(_hits(), top_similarity=0.99)
    assert a.in_scope and a.citations == [1, 2, 3] and "LGPD, Art. 1" in a.text


def test_limiar_de_escopo():
    assert in_scope(OUT_OF_SCOPE_THRESHOLD) and not in_scope(OUT_OF_SCOPE_THRESHOLD - 1e-6)


def test_rrf_favorece_quem_vai_bem_nos_dois_rankings():
    bm25 = np.array([3.0, 2.0, 1.0])
    dense = np.array([0.1, 0.9, 0.5])
    fused = _rrf(bm25, dense)
    assert fused.argmax() == 1  # 2º no BM25 e 1º no denso


def test_parser_artigos_com_letra():
    lines = ["CAPÍTULO I", "Art. 1º Esta Lei dispõe sobre tratamento.", "Parágrafo único. Texto.",
             "Art. 55-J. Compete à ANPD: zelar pela proteção.", "Art. 10. O legítimo interesse do controlador."]
    arts = law_to_articles("lgpd", lines)
    assert [a["article"] for a in arts] == ["1", "55-J", "10"]
    assert "Parágrafo único" in arts[0]["text"]


def test_parser_mantem_ultima_redacao_do_inciso():
    lines = ["Art. 5º Para os fins desta Lei, considera-se:", "VIII - encarregado: redação antiga;",
             "VIII - encarregado: redação vigente;", "IX - agentes de tratamento."]
    text = law_to_articles("lgpd", lines)[0]["text"]
    assert "redação vigente" in text and "redação antiga" not in text
