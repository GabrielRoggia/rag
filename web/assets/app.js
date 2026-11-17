/* LexDados — frontend do assistente LGPD. Usa ds.js (window.DS), Lucide e ApexCharts. */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 2) => Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v) => `${Math.round(v * 100)}%`;
  const cssVar = (n) => getComputedStyle(document.body).getPropertyValue(n).trim();
  const store = {
    get(k, f) { try { return JSON.parse(localStorage.getItem(k)) ?? f; } catch (e) { return f; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* modo privado */ } },
  };

  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let msg = `Erro ${res.status}`;
      try { const j = await res.json(); msg = j.detail?.[0]?.msg || j.detail || msg; } catch (e) { /* sem corpo */ }
      throw new Error(msg);
    }
    return res.json();
  }

  const EXAMPLES = [
    "Quais direitos o titular pode exigir do controlador?",
    "O que a LGPD considera dado pessoal sensível?",
    "Qual o prazo para desistir de uma compra feita pela internet?",
    "O encarregado pode ter conflito de interesse com outras funções?",
    "Por quanto tempo o provedor deve guardar os registros de conexão?",
    "Quais cuidados uma pequena empresa deve ter com backups?",
  ];

  /* ------------------------------------------------------------------ Rotas */
  const ROUTES = {
    consulta: { title: "Consulta", crumb: "Perguntar à legislação", icon: "message-square-text" },
    painel: { title: "Painel", crumb: "Métricas do sistema", icon: "gauge" },
    avaliacao: { title: "Avaliação", crumb: "Gold set e classificador", icon: "chart-pie" },
  };
  const loaded = {};

  function route() {
    const name = ROUTES[location.hash.slice(1)] ? location.hash.slice(1) : "consulta";
    const r = ROUTES[name];
    $$(".page-section").forEach((s) => { s.hidden = s.dataset.page !== name; });
    $$(".ek-side-item[data-route]").forEach((a) => a.classList.toggle("is-active", a.dataset.route === name));
    $("#page-title").textContent = r.title;
    $("#page-crumb").textContent = r.crumb;
    $("#page-crumb").setAttribute("href", `#${name}`);
    $(".ek-page-island-icon").innerHTML = `<i data-lucide="${r.icon}"></i>`;
    DS.icons();
    if (matchMedia("(max-width: 899.98px)").matches) DS.toggleSide(false);
    document.title = `${r.title} · LexDados`;
    if (!loaded[name]) { loaded[name] = true; LOADERS[name]?.(); }
    window.scrollTo({ top: 0 });
  }

  /* ------------------------------------------------------------------ Consulta */
  let clfChart = null;

  function renderExamples() {
    $("#examples").innerHTML = EXAMPLES.map((q) => `<button type="button" class="ek-chip" data-q="${esc(q)}"><i data-lucide="sparkle" style="width:13px;height:13px"></i>${esc(q)}</button>`).join("");
    DS.icons();
  }

  function setBusy(busy) {
    const b = $("#btn-ask");
    b.disabled = busy;
    b.innerHTML = busy ? `<i data-lucide="loader-circle" class="spin"></i>Buscando…` : `<i data-lucide="send"></i>Perguntar`;
    DS.icons();
  }

  function showResult(show) {
    ["#r-stats", "#r-answer", "#r-clf", "#r-hits"].forEach((s) => { $(s).hidden = !show; });
    $("#result-empty").hidden = show;
  }

  function skeleton() {
    showResult(true);
    $("#answer").innerHTML = [96, 88, 92, 60].map((w) => `<span class="ek-skel" style="display:block;height:12px;margin:8px 0;width:${w}%"></span>`).join("");
    $("#hits").innerHTML = Array.from({ length: 3 }, () => `<div class="ek-tile"><span class="ek-skel" style="display:block;height:14px;width:45%"></span><span class="ek-skel" style="display:block;height:10px;margin-top:10px"></span><span class="ek-skel" style="display:block;height:10px;margin-top:6px;width:80%"></span></div>`).join("");
    $("#terms").innerHTML = "";
  }

  // Markdown mínimo: **negrito**, parágrafos e citações [n] clicáveis
  function renderAnswer(text) {
    return esc(text).split(/\n{2,}/).map((p) => `<p>${p
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/\n/g, "<br>")
      .replace(/\[(\d+)\]/g, '<button type="button" class="cite" data-cite="$1">$1</button>')}</p>`).join("");
  }

  const fold = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  function highlight(text, question) {
    const words = new Set(fold(question).match(/[a-z]{5,}/g) || []);
    return esc(text).replace(/[A-Za-zÀ-ÿ]{5,}/g, (w) => (words.has(fold(w)) ? `<mark>${w}</mark>` : w));
  }

  function renderHits(hits, question) {
    const max = Math.max(...hits.map((h) => h.score), 1e-9);
    $("#hits-count").textContent = hits.length;
    $("#hits").innerHTML = hits.map((h) => `
      <button type="button" class="ek-tile hit" id="hit-${h.rank}">
        <div class="hit-top">
          <span class="hit-rank">${h.rank}</span>
          <span class="hit-ref" title="${esc(h.ref)}">${esc(h.ref)}</span>
          <span class="ek-tag ${h.doc.kind === "lei" ? "is-info" : "is-none"}">${h.doc.kind === "lei" ? "Lei" : "Guia ANPD"}</span>
          <span class="hit-score"><span class="bar"><span style="width:${Math.max(4, (h.score / max) * 100)}%"></span></span>${num(h.score, 3)}</span>
        </div>
        <div class="hit-text">${highlight(h.text, question)}</div>
      </button>`).join("");
  }

  function renderClassifier(c) {
    const data = c.proba.slice().reverse();
    $("#clf-tag").textContent = c.predicted.short;
    $("#clf-tag").title = c.predicted.name;
    const xmax = Math.min(100, Math.ceil(Math.max(...data.map((d) => d.p * 100)) / 10) * 10 + 10);
    clfChart?.destroy();
    clfChart = DS.chart($("#chart-clf-q"), {
      chart: { type: "bar", height: 230 },
      series: [{ name: "Probabilidade", data: data.map((d) => +(d.p * 100).toFixed(1)) }],
      plotOptions: { bar: { horizontal: true, barHeight: "62%", borderRadius: 5, distributed: true } },
      colors: data.map((d) => (d.doc.id === c.predicted.id ? cssVar("--accent") : cssVar("--chart-2"))),
      xaxis: { categories: data.map((d) => d.doc.short), min: 0, max: xmax, tickAmount: xmax / 10 > 5 ? xmax / 20 : xmax / 10,
        labels: { formatter: (v) => `${Math.round(v)}%` } },
      yaxis: { labels: { maxWidth: 120 } },
      tooltip: { y: { formatter: (v) => `${num(v, 1)}%` } },
      grid: { xaxis: { lines: { show: true } }, yaxis: { lines: { show: false } } },
    });
    const maxW = Math.max(...c.terms.map((t) => Math.abs(t.weight)), 1e-9);
    $("#terms").innerHTML = c.terms.map((t) => `
      <div class="term"><span class="term-name">${esc(t.term)}</span>
        <span class="bar ${t.weight < 0 ? "is-neg" : ""}"><span style="width:${(Math.abs(t.weight) / maxW) * 100}%"></span></span>
        <span class="term-val">${num(t.weight, 3)}</span></div>`).join("");
  }

  async function ask(question) {
    question = (question ?? $("#q").value).trim();
    if (question.length < 3) { DS.toast("Escreva uma pergunta", { bad: true }); return; }
    $("#q").value = question;
    setBusy(true); skeleton();
    try {
      const r = await api("/api/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, k: +$("#k").value }),
      });
      const a = r.answer;
      const sc = $("#s-scope");
      sc.textContent = a.in_scope ? "Dentro" : "Fora";
      sc.style.color = a.in_scope ? "" : cssVar("--danger-text");
      $("#s-sim").textContent = num(r.top_similarity, 3);
      $("#s-time").textContent = r.elapsed_ms < 1000 ? `${Math.round(r.elapsed_ms)} ms` : `${num(r.elapsed_ms / 1000, 1)} s`;
      $("#s-k").textContent = r.hits.length;
      $("#answer-meta").textContent = a.in_scope
        ? "Trechos mais relevantes (busca híbrida BM25 + embeddings)"
        : `Similaridade abaixo do limiar de ${num(r.scope_threshold, 2)}: pergunta fora do domínio`;
      $("#answer").innerHTML = renderAnswer(a.text);
      $("#r-hits").hidden = !a.in_scope; $("#r-clf").hidden = !a.in_scope;
      if (a.in_scope) { renderHits(r.hits, question); renderClassifier(r.classifier); }
      pushHistory(question);
      DS.icons();
    } catch (e) {
      showResult(false);
      DS.toast(`Falha na consulta: ${e.message}`, { bad: true });
    } finally { setBusy(false); }
  }

  function pushHistory(q) {
    const h = [q, ...store.get("lexdados-hist", []).filter((x) => x !== q)].slice(0, 8);
    store.set("lexdados-hist", h); renderHistory();
  }
  function renderHistory() {
    const h = store.get("lexdados-hist", []);
    $("#r-history").hidden = h.length === 0;
    $("#history").innerHTML = h.map((q) => `<button type="button" class="ek-tile hist-item" data-q="${esc(q)}" title="${esc(q)}">${esc(q)}</button>`).join("");
  }

  function initConsulta() {
    renderExamples(); renderHistory();
    $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); ask(); });
    $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });
    $("#q").addEventListener("input", (e) => { e.target.style.height = "auto"; e.target.style.height = `${Math.min(e.target.scrollHeight + 2, 200)}px`; });
    $("#btn-new").addEventListener("click", () => { $("#q").value = ""; showResult(false); $("#q").focus(); });
    $("#clear-history").addEventListener("click", () => { store.set("lexdados-hist", []); renderHistory(); DS.toast("Histórico limpo"); });
    document.addEventListener("click", (e) => {
      const ex = e.target.closest("[data-q]");
      if (ex) { if (location.hash && location.hash !== "#consulta") location.hash = "consulta"; ask(ex.dataset.q); return; }
      const c = e.target.closest(".cite");
      if (c) {
        const el = $(`#hit-${c.dataset.cite}`);
        if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("is-flash", "is-open"); setTimeout(() => el.classList.remove("is-flash"), 1200); }
        return;
      }
      const hit = e.target.closest(".hit");
      if (hit) hit.classList.toggle("is-open");
    });
    const q = new URLSearchParams(location.search).get("q");
    if (q) ask(q);
  }

  /* ------------------------------------------------------------------ Painel */
  let OVERVIEW = null;
  async function getOverview() { return OVERVIEW ??= await api("/api/overview"); }

  async function loadPainel() {
    let o;
    try { o = await getOverview(); } catch (e) { DS.toast(`Falha ao carregar métricas: ${e.message}`, { bad: true }); return; }
    const r = o.retrieval;
    $("#o-docs").textContent = o.documents.length;
    $("#o-chunks").textContent = o.n_chunks;
    $("#o-qa").textContent = o.n_questions;
    $("#o-f1").textContent = num(o.clf_test_f1, 2);
    $("#o-mrr").textContent = num(r["MRR@10"], 2);
    $("#o-r5").innerHTML = `${Math.round(r["Recall@5"] * 100)}<small>%</small>`;
    $("#o-clf-tag").innerHTML = `<span class="ek-dot"></span>Teste ${num(o.clf_test_f1, 2)}`;
    $("#o-auc").innerHTML = `<span class="ek-dot"></span>AUC ${num(o.scope.auc, 3)}`;

    const ks = ["Recall@1", "Recall@3", "Recall@5", "Recall@10", "MRR@10", "nDCG@10"];
    DS.chart($("#chart-retrieval"), {
      chart: { type: "bar", height: 280 },
      series: [{ name: "Híbrido", data: ks.map((k) => +(r[k] * 100).toFixed(1)) }],
      colors: [cssVar("--accent")],
      xaxis: { categories: ks },
      yaxis: { max: 100, labels: { formatter: (v) => `${Math.round(v)}%` } },
      dataLabels: { enabled: true, formatter: (v) => `${Math.round(v)}%`, offsetY: -18, style: { fontSize: "11px", colors: [cssVar("--text-2")] } },
      plotOptions: { bar: { columnWidth: "45%", borderRadius: 6, dataLabels: { position: "top" } } },
      tooltip: { y: { formatter: (v) => `${num(v, 1)}%` } },
    });
    DS.chart($("#chart-docs"), {
      chart: { type: "donut", height: 300 },
      labels: o.documents.map((d) => d.short), series: o.documents.map((d) => d.chunks),
      legend: { show: true, position: "bottom" },
      plotOptions: { pie: { donut: { labels: { total: { label: "Trechos" } } } } },
    });
    const clfs = o.classifiers.filter((c) => !c.modelo.startsWith("Baseline"));
    DS.chart($("#chart-clf"), {
      chart: { type: "bar" },
      series: [
        { name: "Treino", data: clfs.map((c) => +(c.f1_macro_treino * 100).toFixed(1)) },
        { name: "Validação cruzada", data: clfs.map((c) => +(c.f1_macro_cv * 100).toFixed(1)) },
        { name: "Teste", data: clfs.map((c) => +(c.f1_macro_teste * 100).toFixed(1)) },
      ],
      xaxis: { categories: clfs.map((c) => c.modelo) },
      yaxis: { min: 50, max: 100, labels: { formatter: (v) => `${Math.round(v)}%` } },
      legend: { show: true, position: "bottom" },
      tooltip: { y: { formatter: (v) => `${num(v, 1)}%` } },
    });
    const sc = o.scope;
    const kv = [
      ["ROC AUC", num(sc.auc, 3)], ["Limiar de Youden", num(sc.limiar_youden, 3)],
      ["Limiar em uso", num(o.scope_threshold, 2)], ["Verdadeiros positivos", pct(sc.tpr)],
      ["Falsos positivos", pct(sc.fpr)], ["Perguntas", `${sc.n_in} + ${sc.n_out}`],
    ];
    $("#scope-kv").innerHTML = kv.map(([k, v]) => `<div class="ek-tile"><div class="ek-readout"><span class="ek-readout-label">${k}</span><span class="ek-readout-value">${v}</span></div></div>`).join("");
    DS.icons();
  }

  /* ------------------------------------------------------------------ Avaliação */
  let EVAL = [];
  const mark = (v) => (v ? '<span class="ok-ico" aria-label="acerto"><i data-lucide="circle-check"></i></span>'
    : '<span class="bad-ico" aria-label="erro"><i data-lucide="circle-x"></i></span>');

  function renderEval() {
    const f = $("#ev-filter").value, q = $("#ev-search").value.trim().toLowerCase();
    const rows = EVAL.filter((r) => (!f || (f === "miss" ? !r.hit5 : r.hit5))
      && (!q || `${r.id} ${r.question} ${r.doc.name} ${r.target}`.toLowerCase().includes(q)));
    $("#ev-body").innerHTML = rows.length ? rows.map((r) => `
      <tr class="is-click" data-q="${esc(r.question)}">
        <td class="mono">${esc(r.id)}</td><td style="min-width:260px">${esc(r.question)}</td>
        <td><span class="ek-tag ${r.doc.kind === "lei" ? "is-info" : "is-none"}">${esc(r.doc.short)}</span></td>
        <td>${esc(r.target)}</td><td>${mark(r.hit5)}</td>
        <td style="text-align:right" class="mono">${r.first ?? "—"}</td>
        <td style="text-align:right" class="mono">${num(r.rr, 2)}</td></tr>`).join("")
      : `<tr><td colspan="7"><div class="ek-empty"><i data-lucide="search-x"></i>Nenhuma pergunta encontrada</div></td></tr>`;
    $("#ev-count").textContent = `Mostrando ${rows.length} resultados · ${rows.filter((r) => r.hit5).length} com acerto no top-5`;
    DS.icons();
  }

  async function loadAvaliacao() {
    $("#ev-body").innerHTML = Array.from({ length: 6 }, () => `<tr>${'<td><span class="ek-skel"></span></td>'.repeat(7)}</tr>`).join("");
    try {
      const [ev, o] = await Promise.all([api("/api/evaluation"), getOverview()]);
      EVAL = ev; renderEval();
      $("#clf-body").innerHTML = o.clf_per_class.map((c) => `<tr><td>${esc(c.doc.name)}</td><td class="mono">${num(c.precision, 3)}</td><td class="mono">${num(c.recall, 3)}</td>
        <td><span class="ek-tag ${c.f1 >= 0.85 ? "is-ok" : c.f1 >= 0.75 ? "is-warn" : "is-bad"}">${num(c.f1, 3)}</span></td><td style="text-align:right" class="mono">${c.support}</td></tr>`).join("");
      $("#clf-count").textContent = `F1-macro ${num(o.clf_test_f1, 3)} · acurácia ${num(o.clf_test_acc, 3)} · nas perguntas do gold set: acurácia ${num(o.clf_ood.acc_perguntas, 3)}`;
    } catch (e) { DS.toast(`Falha ao carregar a avaliação: ${e.message}`, { bad: true }); }
    $("#ev-filter").addEventListener("change", renderEval);
    $("#ev-search").addEventListener("input", renderEval);
  }

  const LOADERS = { painel: loadPainel, avaliacao: loadAvaliacao };

  /* ------------------------------------------------------------------ Início */
  document.addEventListener("DOMContentLoaded", () => {
    initConsulta();
    window.addEventListener("hashchange", route);
    route();
  });
})();
