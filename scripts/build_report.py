"""Gera reports/relatorio.pdf a partir dos resultados em reports/results e reports/figures.

Uso: python scripts/build_report.py   (rodar depois de run_all.py e scripts/screenshots.py)
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
RES = REP / "results"
FIG = REP / "figures"
SHOT = REP / "screenshots"
AUTHORS = "Gabriel Roggia"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceBefore=10, spaceAfter=6,
                    textColor=colors.HexColor("#1F3A5F"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
H1.keepWithNext = H2.keepWithNext = 1
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=5)
CAP = ParagraphStyle("cap", parent=P, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"),
                     alignment=1, spaceAfter=10)
CODE = ParagraphStyle("code", parent=P, fontName="Courier", fontSize=8.5, leading=11, alignment=0,
                      backColor=colors.HexColor("#F3F3F3"), borderPadding=4)
BUL = ParagraphStyle("bul", parent=P, leftIndent=12, bulletIndent=2)

story = []


def h1(t): story.append(Paragraph(t, H1))
def h2(t): story.append(Paragraph(t, H2))
def p(t): story.append(Paragraph(t, P))
def bullets(items):
    for it in items:
        story.append(Paragraph(it, BUL, bulletText="•"))


def fig(path, caption, width=16):
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    w = width * cm
    h = w * ratio
    if h > 21 * cm:
        h = 21 * cm; w = h / ratio
    img.drawWidth, img.drawHeight = w, h
    story.append(KeepTogether([img, Paragraph(caption, CAP)]))


def table(df, caption=None, col_widths=None, font=8.5):
    data = [list(map(str, df.columns))] + [[str(v) for v in row] for row in df.itertuples(index=False)]
    data = [[Paragraph(c, ParagraphStyle("t", parent=P, fontSize=font, leading=font + 2, alignment=0))
             for c in row] for row in data]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BBBBBB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    items = [t]
    if caption:
        items.append(Paragraph(caption, CAP))
    story.append(KeepTogether(items))


def fmt(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


# ------------------------------------------------------------------ dados
eda = pd.read_csv(RES / "eda_por_documento.csv")
qual = pd.read_csv(RES / "eda_qualidade.csv", index_col=0)["valor"]
cmp_ = pd.read_csv(RES / "clf_comparacao.csv")
rep = pd.read_csv(RES / "clf_report_teste.csv", index_col=0)
ood = json.load(open(RES / "clf_perguntas_ood.json"))
top = json.load(open(RES / "clf_top_termos.json", encoding="utf-8"))
ret = pd.read_csv(RES / "retrieval_metricas.csv")
esc = json.load(open(RES / "escopo.json"))
perq = pd.read_csv(RES / "retrieval_por_pergunta.csv")
qa = pd.read_json(ROOT / "data/eval/qa_gold.jsonl", lines=True)
best = cmp_.iloc[1:].sort_values("f1_macro_cv", ascending=False).iloc[0]
hy = ret.iloc[0]
n_chunks = int(eda["chunks_rag"].sum())

# ------------------------------------------------------------------ capa
story += [Spacer(1, 3 * cm),
          Paragraph("Faculdade Antonio Meneghetti — Sistemas de Informação", ParagraphStyle("c0", parent=P, alignment=1)),
          Paragraph("Trabalho 1 — Inteligência Artificial II (2026/02)", ParagraphStyle("c1", parent=P, alignment=1)),
          Spacer(1, 1.5 * cm),
          Paragraph("Assistente de consulta à LGPD com recuperação híbrida e classificador de fontes",
                    ParagraphStyle("t", parent=ss["Title"], fontSize=20, leading=26)),
          Spacer(1, .5 * cm),
          Paragraph("Recuperação de trechos legais com BM25 e embeddings fundidos por RRF; classificação "
                    "supervisionada da fonte normativa; detector de perguntas fora de escopo.",
                    ParagraphStyle("st", parent=P, alignment=1)),
          Spacer(1, 2 * cm),
          Paragraph(f"Autor(es): {AUTHORS}", ParagraphStyle("a", parent=P, alignment=1)),
          Paragraph(f"Gerado em {date.today().strftime('%d/%m/%Y')}", ParagraphStyle("a2", parent=P, alignment=1)),
          PageBreak()]

# ------------------------------------------------------------------ 1. Dataset
h1("1. Dataset")
p("O corpus foi montado a partir de sete documentos oficiais e públicos sobre proteção de dados pessoais no Brasil: "
  "quatro normas em HTML (portal da legislação do Planalto) e três guias orientativos da Autoridade Nacional de "
  "Proteção de Dados (ANPD) em PDF. Os arquivos brutos ficam em <font face='Courier'>data/raw/</font> e o README "
  "traz os comandos de download.")
links = pd.DataFrame([
    ["lgpd", "Lei 13.709/2018 (LGPD)", "planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/L13709.htm"],
    ["marco_civil", "Lei 12.965/2014 (Marco Civil da Internet)", "planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm"],
    ["decreto_8771", "Decreto 8.771/2016", "planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8771.htm"],
    ["cdc", "Lei 8.078/1990 (CDC, compilado)", "planalto.gov.br/ccivil_03/leis/l8078compilado.htm"],
    ["anpd_agentes", "Guia de Agentes de Tratamento e Encarregado (ANPD)", "gov.br/anpd → Segunda_Versao_do_Guia_de_Agentes_de_Tratamento_retificada.pdf"],
    ["anpd_seguranca", "Guia de Segurança da Informação p/ ATPP (ANPD)", "gov.br/anpd → guia-vf.pdf"],
    ["anpd_encarregado", "Guia Orientativo — Atuação do Encarregado (ANPD)", "ba.gov.br (cópia pública do guia da ANPD)"],
], columns=["id", "documento", "origem"])
table(links, "Tabela 1 — Documentos do corpus e origem.", [2.8 * cm, 6 * cm, 8 * cm])
p(f"A partir desses documentos foram derivados três conjuntos: (i) <b>unidades</b> — um registro por artigo de lei "
  "ou página de guia (358); (ii) <b>trechos do RAG</b> — unidades divididas em janelas de até 220 palavras com 50 de "
  "sobreposição ({n_chunks}); e (iii) <b>janelas rotuladas para o classificador</b> — blocos de 60 palavras sem sobreposição, "
  f"cada um rotulado com o documento de origem ({int(qual['janelas_classificador'])}). Para avaliação foi anotado "
  f"manualmente um <i>gold set</i> com {len(qa)} perguntas em linguagem natural, cada uma com o documento e o(s) artigo(s) "
  "(ou palavras-chave, no caso dos guias) que a respondem, além de 25 perguntas fora do domínio.")
p("<b>Justificativa.</b> São textos oficiais, gratuitos e estáveis, com estrutura (artigos, capítulos, páginas) que "
  "fornece rótulos e referências sem custo de anotação. A sobreposição temática entre eles (todos tratam de dados, "
  "consumidor e internet) torna a recuperação e a classificação não triviais, o que é adequado para avaliar "
  "técnicas de ML.")

# ------------------------------------------------------------------ 2. Problema
h1("2. Problema e objetivo")
p("Leigos e profissionais têm dificuldade de localizar <i>onde</i> a legislação trata de uma dúvida concreta "
  "(\"preciso avisar a ANPD de um vazamento?\"). O objetivo é construir um assistente que, dada uma pergunta, "
  "recupere os trechos normativos relevantes e os mostre com a fonte (artigo ou página), sem gerar texto novo.")
p("O projeto combina três tarefas de ML:")
bullets([
    f"<b>Recuperação de informação (ranking)</b> — ordenar os {n_chunks} trechos por relevância, combinando BM25 "
    "(correspondência de termos) e embeddings densos (multilingual-E5-small) por <i>Reciprocal Rank Fusion</i>.",
    "<b>Classificação supervisionada multiclasse (7 classes)</b> — prever de qual documento vem um trecho ou uma "
    "pergunta. É o modelo treinado do projeto; na interface ele indica a norma provável e explica a decisão.",
    "<b>Detecção de fora de escopo (classificação binária por limiar)</b> — decidir se a pergunta pertence ao domínio "
    "a partir da similaridade do melhor trecho, avaliada com curva ROC.",
])

# ------------------------------------------------------------------ 3. EDA
h1("3. Exploração e preparação dos dados")
h2("3.1 Principais achados da EDA")
e = eda.rename(columns={"doc_id": "documento", "media_palavras": "média", "maximo": "máx.",
                        "janelas_clf": "janelas", "chunks_rag": "trechos"})
table(e, "Tabela 2 — Estatísticas por documento (tamanho em palavras por unidade).")
bullets([
    f"<b>Qualidade:</b> {int(qual['textos_vazios_unidades'])} unidades vazias e {int(qual['duplicados_exatos_janelas'])} "
    f"janelas duplicadas após a limpeza; {int(qual['paginas_pdf_quase_vazias(<30 palavras)'])} páginas de PDF quase "
    "vazias (capas, sumários, páginas de título) foram mantidas no RAG mas pouco aparecem no topo do ranking.",
    f"<b>Outliers:</b> {int(qual['outliers_tamanho_unidade(IQR)'])} unidades acima de Q3 + 1,5·IQR — artigos longos "
    "(ex.: LGPD art. 55-J, com 940 palavras). Não foram removidos: o fatiamento em janelas de 220 palavras resolve o "
    "problema para o RAG.",
    "<b>Desbalanceamento:</b> o CDC e a LGPD têm ~2,5× mais janelas que Decreto e Marco Civil (Figura 1). Tratado com "
    "<i>class_weight='balanced'</i> e métrica F1-macro.",
    "<b>Sobreposição de vocabulário</b> (Jaccard, Figura 3): os três guias da ANPD e a LGPD compartilham muito "
    "vocabulário; Marco Civil e Decreto 8.771 também. São esses os pares que o classificador mais confunde.",
])
fig(FIG / "eda_classes.png", "Figura 1 — Distribuição de classes no dataset do classificador.", 12)
fig(FIG / "eda_tamanho_unidades.png", "Figura 2 — Tamanho das unidades por documento (escala log).", 13)
fig(FIG / "eda_jaccard.png", "Figura 3 — Similaridade de vocabulário entre documentos (Jaccard).", 10)
fig(FIG / "eda_top_termos.png", "Figura 4 — Termos mais frequentes por documento, sem stopwords.", 16)

h2("3.2 Problemas encontrados e preparação")
p("A EDA revelou ruídos de extração que foram corrigidos na ingestão (<font face='Courier'>src/lgpd_rag/ingest.py</font>):")
bullets([
    "<b>Texto revogado:</b> no HTML do Planalto, redações antigas aparecem riscadas (<i>&lt;strike&gt;</i>); esse "
    "conteúdo é removido para não indexar dispositivos revogados. Anotações como \"(Incluído pela Lei…)\" e "
    "\"(Vigência)\" também são removidas.",
    "<b>Números partidos em tags:</b> \"Art. 5<i>&lt;span&gt;</i>7\" virava \"Art. 5 7\" e o art. 57 (vetado) "
    "sobrescrevia o art. 5º (definições). Corrigido juntando os dígitos e descartando dispositivos só \"(VETADO)\".",
    "<b>MP rejeitada no Marco Civil:</b> na primeira execução da EDA, \"rejeitada\" era o termo mais frequente do "
    "documento, por causa de anotações \"(Rejeitada)\" e incisos duplicados. As anotações passaram a ser removidas e "
    "linhas repetidas dentro do artigo são descartadas (a Figura 4 já mostra o resultado corrigido).",
    "<b>PDFs:</b> hifenização de fim de linha desfeita e pontilhados de sumário (\"Título ........ 12\") removidos.",
    "<b>Normalização para os modelos esparsos:</b> minúsculas, remoção de acentos, remoção de números isolados "
    "(números de artigos/incisos são um atalho para a fonte) e stopwords em português para o BM25.",
    "<b>Representação:</b> TF-IDF com <i>sublinear_tf</i>, <i>min_df=2</i>, <i>max_df=0,9</i> (classificador); "
    "embeddings E5 normalizados (norma L2 = 1), o que equivale a padronizar a escala para o produto interno virar "
    "cosseno. A fusão híbrida normaliza scores por min-max.",
])

# ------------------------------------------------------------------ 4. Estratégia
h1("4. Estratégia experimental")
bullets([
    "<b>Classificador:</b> divisão treino/teste 80/20 com <i>GroupShuffleSplit</i>, em que o grupo é o artigo/página "
    "de origem. Janelas do mesmo artigo nunca ficam dos dois lados — um split aleatório comum vazaria trechos quase "
    "idênticos e inflaria o resultado. Proporção efetiva: cerca de 77% das janelas no treino e 23% no teste "
    "(282 e 71 grupos), já que os grupos têm tamanhos diferentes.",
    "<b>Seleção de hiperparâmetros:</b> <i>GridSearchCV</i> com <i>StratifiedGroupKFold</i> (5 dobras) apenas no "
    "treino, otimizando F1-macro. O teste só é usado uma vez, no final.",
    f"<b>Teste fora da distribuição:</b> o classificador treinado em trechos de lei também é avaliado nas {len(qa)} "
    "perguntas do gold set, que têm estilo bem diferente (curtas, coloquiais).",
    "<b>Recuperação:</b> não há treino supervisionado (BM25 é estatístico e o modelo de embeddings é pré-treinado), "
    "e nenhum parâmetro foi ajustado nas perguntas de avaliação, então todo o gold set é usado como teste.",
    "<b>Fora de escopo:</b> 46 perguntas do domínio × 25 de fora (incluindo 5 perguntas jurídicas de outras áreas, "
    "mais difíceis). Limiar escolhido pelo índice de Youden na curva ROC.",
    "Semente fixa (42) em todos os splits e modelos; <font face='Courier'>python run_all.py</font> reproduz tudo.",
])

# ------------------------------------------------------------------ 5. Modelagem
h1("5. Modelagem")
h2("5.1 Classificador de fonte")
p("Foram comparados três modelos lineares sobre TF-IDF, adequados a texto esparso e com poucos milhares de "
  "amostras, além de um baseline de classe majoritária:")
bullets([
    "<b>ComplementNB</b> — variante do Naive Bayes robusta a classes desbalanceadas; grade: α ∈ {0,1; 0,3; 1}, "
    "n-gramas (1,1) ou (1,2).",
    "<b>Regressão Logística</b> — probabilidades bem calibradas; grade: C ∈ {1; 10; 30}, n-gramas.",
    "<b>LinearSVC</b> — margem máxima, forte em texto; grade: C ∈ {0,1; 0,5; 1}, n-gramas. Como não produz "
    "probabilidades, caso seja o escolhido, o modelo final é calibrado com <i>CalibratedClassifierCV</i> (sigmoide).",
])
c = cmp_.copy()
c["melhores_params"] = c["melhores_params"].str.replace('"', "").str.replace("clf__", "").str.replace("tfidf__", "")
c = c.rename(columns={"melhores_params": "melhores hiperparâmetros", "f1_macro_cv": "F1 CV",
                      "acc_treino": "acc treino", "acc_teste": "acc teste", "f1_macro_treino": "F1 treino",
                      "f1_macro_teste": "F1 teste"}).astype(object).fillna("-")
table(c, "Tabela 3 — Comparação dos classificadores (F1 = F1-macro).",
      [3.6 * cm, 4.4 * cm, 1.6 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm], font=8)
p(f"O modelo escolhido pela validação cruzada foi <b>{best.modelo}</b> (F1-macro CV = {fmt(best.f1_macro_cv)}). "
  "As três famílias ficaram próximas (diferença &lt; 0,03), um sinal de que o limite está mais na representação "
  "(bag-of-words) do que no classificador.")

h2("5.2 Recuperação híbrida")
p("A busca combina dois rankings, porque eles erram de formas diferentes:")
bullets([
    "<b>BM25 (Okapi)</b>, k1=1,5 e b=0,75 (padrão do <i>rank-bm25</i>): pontua a correspondência de termos, "
    "satura a frequência e penaliza trechos longos. É forte em termos jurídicos exatos (\"encarregado\", "
    "\"portabilidade\"), mas não reconhece sinônimos.",
    "<b>Embeddings densos</b> com <i>intfloat/multilingual-e5-small</i> (118M parâmetros, 384 dimensões), escolhido "
    "por ser multilíngue e rodar em CPU, com os prefixos \"query:\"/\"passage:\" recomendados pelo modelo. Mede a "
    "semelhança de significado por cosseno, então \"desistir de uma compra\" encontra \"direito de arrependimento\".",
    "<b>Fusão por <i>Reciprocal Rank Fusion</i></b> (k = 60): cada trecho recebe a soma de 1/(60 + posição) nos dois "
    "rankings. Um trecho bem colocado em qualquer um deles sobe, sem precisar calibrar as escalas dos dois scores.",
])

# ------------------------------------------------------------------ 6. Avaliação
h1("6. Avaliação")
h2("6.1 Classificador")
r = rep.round(3).reset_index().rename(columns={"index": "classe", "f1-score": "F1", "support": "n"})
r["n"] = r["n"].astype(int).astype(str)
table(r, f"Tabela 4 — Relatório por classe no conjunto de teste ({best.modelo}{' calibrado' if best.modelo == 'LinearSVC' else ''}).")
fig(FIG / "clf_confusao_teste.png", "Figura 5 — Matriz de confusão normalizada no teste.", 12)
p(f"No teste, acurácia de {fmt(rep.loc['accuracy','precision'])} e F1-macro de {fmt(rep.loc['macro avg','f1-score'])}, "
  f"contra {fmt(cmp_.iloc[0].f1_macro_teste)} do baseline. As confusões seguem o que a EDA antecipou: Decreto 8.771 → "
  "Marco Civil (o decreto regulamenta o Marco Civil) e Guia de Agentes ↔ Guia do Encarregado (ambos sobre papéis "
  f"definidos na LGPD). Nas perguntas do gold set (fora da distribuição) a acurácia cai para {fmt(ood['acc_perguntas'])} "
  f"(F1-macro {fmt(ood['f1_macro_perguntas'])}).")
fig(FIG / "clf_confusao_perguntas.png", "Figura 6 — Matriz de confusão nas perguntas do gold set.", 11)

h2("6.2 Recuperação")
rt = pd.DataFrame([{k: (str(int(v)) if k == "n" else fmt(v, 0) if k == "ms/consulta" else fmt(v, 3)) for k, v in hy.items()}]).rename(
    columns={"ms/consulta": "ms por consulta", "n": "perguntas"})
table(rt, f"Tabela 5 — Métricas da recuperação híbrida no gold set ({len(qa)} perguntas). Recall@k = fração das "
      "perguntas com ao menos um trecho relevante entre os k primeiros; MRR@10 = média do inverso da posição do "
      "primeiro trecho relevante.")
fig(FIG / "retrieval_metricas.png", "Figura 7 — Métricas da recuperação híbrida.", 13)
p(f"Em {fmt(hy['Recall@5'] * 100, 0)}% das perguntas um trecho correto aparece entre os 5 primeiros e em "
  f"{fmt(hy['Recall@10'] * 100, 0)}% entre os 10 primeiros. O MRR@10 de {fmt(hy['MRR@10'], 2)} indica que o primeiro "
  "trecho correto costuma estar entre a 1ª e a 2ª posição. Com o modelo em memória, cada consulta leva cerca de "
  f"{fmt(hy['ms/consulta'], 0)} ms em CPU.")

h2("6.3 Detector de fora de escopo")
fig(FIG / "escopo_roc.png", "Figura 8 — Curva ROC e distribuição da similaridade do melhor trecho.", 15)
p(f"A similaridade de cosseno do melhor trecho separa quase perfeitamente as perguntas do domínio das demais "
  f"(AUC = {fmt(esc['auc'])}). O limiar de Youden foi {fmt(esc['limiar_youden'])} (TPR = {fmt(esc['tpr'])}, "
  f"FPR = {fmt(esc['fpr'])}); no sistema foi usado 0,85, um pouco abaixo, para priorizar não recusar perguntas "
  "legítimas.")

# ------------------------------------------------------------------ 7. Análise
h1("7. Análise dos resultados")
h2("7.1 Interpretação do classificador")
p("Como os modelos são lineares, a contribuição de cada termo é exata: valor TF-IDF × coeficiente da classe (o mesmo "
  "que o SHAP daria para um modelo linear com features independentes). A interface mostra essa explicação local "
  "para cada pergunta. Termos de maior peso por classe:")
tt = pd.DataFrame([[k, ", ".join(v[:10])] for k, v in top.items()], columns=["classe", "termos de maior peso"])
table(tt, "Tabela 6 — Termos com maior coeficiente por classe.", [3.2 * cm, 13.3 * cm])
p("Boa parte dos termos é temática (\"consumidor\", \"encarregado\", \"senhas\", \"registros\", \"conexao\"), mas "
  "aparecem <b>atalhos de formato</b>: \"abril\" no Guia de Agentes vem do cabeçalho de página (data da versão), "
  "\"vetado\" e \"nº\" refletem a forma de escrita das leis, \"desta/deste\" é típico de texto normativo. O modelo "
  "aprende em parte o <i>estilo</i> de cada documento, o que explica a queda nas perguntas, onde esse estilo não "
  "existe.")
h2("7.2 Underfitting × overfitting")
fig(FIG / "clf_treino_teste.png", "Figura 9 — F1-macro em treino, validação cruzada e teste.", 13)
svc = cmp_.set_index("modelo").loc["LinearSVC"]
p(f"Para o modelo escolhido ({best.modelo}), o F1-macro é {fmt(best.f1_macro_treino, 2)} no treino, "
  f"{fmt(best.f1_macro_cv, 2)} na validação cruzada e {fmt(best.f1_macro_teste, 2)} no teste: há <b>overfitting "
  "moderado</b> (o modelo quase decora o treino), mas CV e teste concordam, então a estimativa de generalização é "
  "confiável para trechos dos documentos. Não há sinal de underfitting: todos os modelos superam o baseline por "
  "larga margem. O LinearSVC com bigramas ajusta ainda mais o treino "
  f"(F1 {fmt(svc.f1_macro_treino, 2)}) e teve F1 de teste maior ({fmt(svc.f1_macro_teste, 2)}), mas empatou na CV; "
  "a escolha foi feita pela CV, e não pelo teste, para não usar o teste na seleção de modelo. O que mais preocupa é "
  f"a mudança de distribuição para perguntas (acurácia {fmt(ood['acc_perguntas'])}): é uma limitação dos dados de "
  "treino, que só têm trechos de lei e guia e nenhuma pergunta, e não se resolve com regularização.")
h2("7.3 Análise de erros da recuperação")
miss = perq[perq["recall@5"] == 0].merge(qa, on="id")
p(f"A busca não encontra trecho relevante no top-5 em {len(miss)} perguntas, quase todas sobre artigos da LGPD "
  "(bases legais, transferência internacional, comunicação de incidente, competências da ANPD). O motivo é que os "
  "guias da ANPD <b>parafraseiam e citam</b> esses artigos, com vocabulário mais próximo ao da pergunta, e ocupam o "
  "topo. Do ponto de vista do usuário isso não é grave (o guia cita o artigo), mas penaliza a métrica. Há também "
  "<b>descompasso de vocabulário</b>: a pergunta fala em \"vazamento\" e a lei, em \"incidente de segurança\" "
  "(Figura 12).")
mt = miss[["id", "doc_id", "question"]].rename(columns={"doc_id": "doc esperado", "question": "pergunta"})
table(mt, "Tabela 7 — Perguntas sem trecho relevante no top-5.", [1.2 * cm, 2.8 * cm, 12.5 * cm], font=8)
h2("7.4 Limitações")
bullets([
    f"Gold set pequeno ({len(qa)} perguntas) e anotado por uma única pessoa; intervalos de confiança largos "
    "(cerca de ±0,10 no Recall@5 com 95% de confiança, aproximação binomial).",
    "Relevância definida por artigo/palavra-chave: um trecho de guia que responde corretamente, mas não é o artigo "
    "anotado, conta como erro — a métrica é conservadora.",
    "O detector de escopo foi testado com perguntas claramente fora do tema; perguntas jurídicas próximas (ex.: "
    "direito do trabalho sobre dados de empregados) são mais difíceis e não foram medidas.",
    "Leis compiladas mudam; o corpus é um retrato da data de download.",
    "O sistema mostra os trechos, mas não redige uma resposta: o usuário ainda precisa ler o artigo.",
    "O sistema é informativo e não substitui orientação jurídica.",
])

# ------------------------------------------------------------------ 8. Demonstração
WEBSHOT = SHOT / "web"
h1("8. Demonstração de funcionamento")
p("A solução é usada por uma interface web, a <b>LexDados</b>: uma API em FastAPI "
  "(<font face='Courier'>app/api.py</font>) expõe o recuperador, o classificador e o detector de escopo, e um "
  "frontend em HTML, CSS e JavaScript (<font face='Courier'>web/</font>) consome essa API. Para subir: "
  "<font face='Courier'>uvicorn app.api:app --port 8000</font> e abrir http://localhost:8000. As capturas foram "
  "feitas com <font face='Courier'>scripts/screenshots_web.py</font> (Playwright).")
p("Na página <b>Consulta</b>, cada pergunta mostra: se está dentro do escopo, a similaridade do melhor trecho, o "
  "tempo e o número de trechos; a resposta, com os três trechos mais relevantes e sua fonte; a lista de trechos "
  "recuperados, com os termos da pergunta destacados; e o classificador de fonte, com a probabilidade de cada "
  "documento e os termos que mais pesaram na decisão.")
for f, cap, w in [
    ("01_consulta_titular", "Figura 10 — Consulta sobre os direitos do titular: LGPD art. 18 em 1º e 2º lugar, e o "
                            "classificador indica a LGPD.", 15),
    ("02_consulta_cdc", "Figura 11 — Direito de arrependimento: a busca traz o CDC art. 49 em 1º lugar, mas o "
                        "classificador erra (prevê o Marco Civil por causa de \"internet\").", 15),
    ("03_consulta_falha", "Figura 12 — Caso de falha: \"vazamento\" recupera os guias da ANPD e não traz a LGPD "
                          "art. 48 entre os 5 primeiros.", 15),
    ("04_fora_de_escopo", "Figura 13 — Pergunta fora do domínio bloqueada pelo detector de escopo.", 15),
    ("06_avaliacao_erros", "Figura 14 — Página Avaliação filtrada pelas perguntas sem acerto no top-5; cada linha "
                           "pode ser executada na Consulta.", 16),
    ("05_painel", "Figura 15 — Página Painel com as métricas da recuperação, dos classificadores e do detector de "
                  "escopo.", 16),
    ("07_mobile_claro", "Figura 16 — A mesma interface no celular (390 px), no tema claro.", 6.5),
]:
    if (WEBSHOT / f"{f}.png").exists():
        fig(WEBSHOT / f"{f}.png", cap, w)

# ------------------------------------------------------------------ 9. Extensão
h1("9. Extensão opcional: interface gráfica")
p("A interface web tem três páginas: <b>Consulta</b>, <b>Painel</b> (métricas do sistema) e <b>Avaliação</b> "
  "(resultado da busca pergunta a pergunta e métricas por classe do classificador). Tem tema claro e escuro e se "
  "adapta a telas de 375 px a 1440 px. Os endpoints da API são <font face='Courier'>/api/ask</font>, "
  "<font face='Courier'>/api/overview</font> e <font face='Courier'>/api/evaluation</font>. Não foram usados "
  "modelos de IA generativa, workflows nem agentes, que o enunciado deixa como opcionais.")

# ------------------------------------------------------------------ 10. Reprodução
h1("10. Reprodutibilidade")
for cmd in ["python -m venv .venv &amp;&amp; .venv\\Scripts\\activate   (Linux/Mac: source .venv/bin/activate)",
            "pip install -r requirements.txt",
            "python run_all.py            # ingestão → EDA → classificador → avaliação",
            "pytest -q tests",
            "uvicorn app.api:app --port 8000   # interface web em http://localhost:8000",
            "python scripts/screenshots_web.py &amp;&amp; python scripts/build_report.py   # com a API rodando"]:
    story.append(Paragraph(cmd, CODE)); story.append(Spacer(1, 3))
p("Todas as tabelas e figuras deste relatório são geradas pelos scripts a partir de "
  "<font face='Courier'>reports/results/</font> e <font face='Courier'>reports/figures/</font>.")


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    if doc.page > 1:
        canvas.drawString(2 * cm, 1.2 * cm, "Trabalho 1 — IA II — Assistente LGPD com RAG")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    canvas.restoreState()


out = REP / "relatorio.pdf"
SimpleDocTemplate(str(out), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                  bottomMargin=1.8 * cm, title="Assistente LGPD com RAG", author=AUTHORS).build(
    story, onFirstPage=on_page, onLaterPages=on_page)
print("relatório:", out)
