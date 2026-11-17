/*
 * Design system behaviours, framework free. Include after ds.css, Lucide and
 * (for charts) ApexCharts. Everything is wired through data attributes:
 *
 *   data-ek-theme-toggle          switches light/dark (body.dark), remembered per browser
 *   data-ek-side-toggle           expands/collapses the sidebar (desktop) or opens it (mobile)
 *   data-ek-group                 a sidebar group whose .ek-side-item toggles .is-open
 *   data-ek-menu="id"             toggles the .ek-menu with that id; closes on outside click/Escape
 *   data-ek-open="id"             opens a drawer/dialog (and the backdrop); data-ek-close closes it
 *   .ek-seg                       segmented control: the active button moves the thumb
 *   .ek-tabs[data-ek-tabs]        tabs that show [data-ek-panel="name"] for button[data-ek-tab="name"]
 *
 * API: DS.chart(el, options), DS.toast(text, {bad}), DS.setTheme(dark).
 */
(function () {
  "use strict";

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const css = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();

  /* Theme ------------------------------------------------------------------------------------ */

  const charts = new Set();

  function setTheme(dark) {
    document.body.classList.toggle("dark", dark);
    store.set("ek-theme", dark ? "dark" : "light");
    $$("[data-ek-theme-toggle]").forEach((b) => {
      b.innerHTML = `<i data-lucide="${dark ? "sun" : "moon"}"></i>`;
      b.setAttribute("aria-label", dark ? "Tema claro" : "Tema escuro");
    });
    icons();
    charts.forEach((c) => c.updateOptions(themeOptions(), false, false));
  }

  function initialTheme() {
    const saved = store.get("ek-theme");
    if (saved) return saved === "dark";
    if (document.body.classList.contains("dark")) return true;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  }

  /* Icons ------------------------------------------------------------------------------------ */

  function icons() {
    if (window.lucide) lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
  }

  /* Sidebar ---------------------------------------------------------------------------------- */

  const mobile = () => matchMedia("(max-width: 899.98px)").matches;

  function toggleSide(force) {
    const side = $(".ek-side");
    if (!side) return;
    if (mobile()) {
      const open = force ?? !side.classList.contains("is-mobile-open");
      side.classList.toggle("is-mobile-open", open);
      $(".ek-scrim")?.classList.toggle("is-open", open);
    } else {
      const open = force ?? !side.classList.contains("is-expanded");
      side.classList.toggle("is-expanded", open);
      store.set("ek-side", open ? "1" : "0");
    }
  }

  /* Menus, drawers, dialogs ------------------------------------------------------------------ */

  function closeMenus(except) {
    $$(".ek-menu.is-open").forEach((m) => {
      if (m !== except) {
        m.classList.remove("is-open");
        $(`[data-ek-menu="${m.id}"]`)?.classList.remove("is-open");
      }
    });
  }

  function openOverlay(id, open) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("is-open", open);
    let backdrop = $(".ek-backdrop");
    if (!backdrop) {
      backdrop = document.createElement("div");
      backdrop.className = "ek-backdrop";
      backdrop.addEventListener("click", () => $$(".ek-drawer.is-open, .ek-dialog.is-open").forEach((o) => openOverlay(o.id, false)));
      document.body.appendChild(backdrop);
    }
    const anyOpen = $$(".ek-drawer.is-open, .ek-dialog.is-open").length > 0;
    backdrop.classList.toggle("is-open", anyOpen);
    document.body.style.overflow = anyOpen ? "hidden" : "";
    if (open) setTimeout(() => $("input, select, textarea, button:not(.ek-close)", el)?.focus({ preventScroll: true }), 300);
  }

  /* Segmented controls ------------------------------------------------------------------------ */

  function initSeg(seg) {
    const buttons = $$("button", seg);
    seg.style.setProperty("--count", buttons.length);
    let thumb = $(".ek-seg-thumb", seg);
    if (!thumb) {
      thumb = document.createElement("span");
      thumb.className = "ek-seg-thumb";
      seg.prepend(thumb);
    }
    const move = () => {
      const i = Math.max(0, buttons.findIndex((b) => b.classList.contains("is-active")));
      thumb.style.transform = `translateX(calc(${i} * (100% + 2px)))`;
    };
    buttons.forEach((b) => b.addEventListener("click", () => {
      buttons.forEach((x) => x.classList.toggle("is-active", x === b));
      move();
      seg.dispatchEvent(new CustomEvent("ek-change", { detail: b.dataset.value ?? b.textContent.trim() }));
    }));
    move();
  }

  /* Tabs ------------------------------------------------------------------------------------- */

  function initTabs(tabs) {
    const buttons = $$("[data-ek-tab]", tabs);
    const show = (name) => {
      buttons.forEach((b) => b.classList.toggle("is-active", b.dataset.ekTab === name));
      $$("[data-ek-panel]").forEach((p) => { if (buttons.some((b) => b.dataset.ekTab === p.dataset.ekPanel)) p.hidden = p.dataset.ekPanel !== name; });
    };
    buttons.forEach((b) => b.addEventListener("click", () => show(b.dataset.ekTab)));
    show((buttons.find((b) => b.classList.contains("is-active")) || buttons[0])?.dataset.ekTab);
  }

  /* Charts (ApexCharts) ---------------------------------------------------------------------- */

  function palette() {
    return [1, 2, 3, 4, 5, 6, 7, 8].map((i) => css(`--chart-${i}`));
  }

  // The console's chart look: no toolbar, dashed hairline grid, muted 10 px labels, area series
  // with a soft vertical gradient and a 1.5 px line, glass tooltip.
  function themeOptions() {
    const dark = document.body.classList.contains("dark");
    const text = css("--text-3"), line = css("--line");
    return {
      chart: { foreColor: text, background: "transparent" },
      theme: { mode: dark ? "dark" : "light" },
      grid: { borderColor: line },
      legend: { labels: { colors: css("--text-2") }, fontFamily: "Poppins, sans-serif", fontSize: "12px", markers: { radius: 3 } },
      tooltip: { theme: dark ? "dark" : "light" },
      xaxis: { labels: { style: { colors: text } }, axisBorder: { color: line }, axisTicks: { color: line } },
      yaxis: { labels: { style: { colors: text } } },
    };
  }

  function deepMerge(base, extra) {
    const out = Array.isArray(base) ? base.slice() : { ...base };
    for (const [k, v] of Object.entries(extra || {})) {
      out[k] = v && typeof v === "object" && !Array.isArray(v) && base && typeof base[k] === "object" ? deepMerge(base[k], v) : v;
    }
    return out;
  }

  function chart(el, options) {
    if (!window.ApexCharts) throw new Error("ApexCharts is not loaded");
    const type = options?.chart?.type || "area";
    const defaults = {
      chart: {
        type, height: 220, fontFamily: "Poppins, sans-serif", toolbar: { show: false }, zoom: { enabled: false },
        animations: { enabled: true, easing: "easeinout", speed: 500 }, parentHeightOffset: 0,
      },
      colors: palette(),
      dataLabels: { enabled: false },
      stroke: { curve: "smooth", width: type === "bar" ? 0 : type === "donut" || type === "pie" ? 2 : 1.5, colors: type === "donut" || type === "pie" ? [css("--surface")] : undefined },
      fill: type === "area"
        ? { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: .45, opacityTo: .05, stops: [0, 90, 100] } }
        : { opacity: 1 },
      grid: { strokeDashArray: 4, padding: { left: 8, right: 8 }, xaxis: { lines: { show: false } } },
      legend: { show: false },
      markers: { size: 0, hover: { size: 4 } },
      plotOptions: {
        bar: { borderRadius: 6, columnWidth: "55%" },
        pie: { donut: { size: "72%", labels: { show: true, total: { show: true, color: css("--text-3"), fontSize: "12px" }, value: { color: css("--text-1"), fontSize: "22px", fontWeight: 700 } } } },
      },
      xaxis: { labels: { style: { fontSize: "10px" } }, tooltip: { enabled: false } },
      yaxis: { labels: { style: { fontSize: "10px" } } },
      states: { hover: { filter: { type: "lighten", value: .04 } } },
    };
    const instance = new ApexCharts(el, deepMerge(deepMerge(defaults, themeOptions()), options));
    instance.render();
    charts.add(instance);
    const destroy = instance.destroy.bind(instance);
    instance.destroy = () => { charts.delete(instance); return destroy(); };  // não atualizar gráficos destruídos
    return instance;
  }

  /* Toasts ----------------------------------------------------------------------------------- */

  function toast(text, opts = {}) {
    let host = $(".ek-toasts");
    if (!host) { host = document.createElement("div"); host.className = "ek-toasts"; document.body.appendChild(host); }
    const t = document.createElement("div");
    t.className = "ek-toast" + (opts.bad ? " is-bad" : "");
    t.innerHTML = `<i data-lucide="${opts.bad ? "circle-alert" : "circle-check"}"></i><span></span>`;
    t.querySelector("span").textContent = text;
    host.appendChild(t);
    icons();
    setTimeout(() => t.remove(), opts.timeout || 3500);
  }

  /* Wiring ----------------------------------------------------------------------------------- */

  function init() {
    setTheme(initialTheme());
    if (store.get("ek-side") === "1" && !mobile()) $(".ek-side")?.classList.add("is-expanded");

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (t.closest("[data-ek-theme-toggle]")) return setTheme(!document.body.classList.contains("dark"));
      if (t.closest("[data-ek-side-toggle]")) { e.preventDefault(); return toggleSide(); }
      if (t.closest(".ek-scrim")) return toggleSide(false);
      const groupItem = t.closest("[data-ek-group] > .ek-side-item");
      if (groupItem) { e.preventDefault(); groupItem.parentElement.classList.toggle("is-open"); if (!mobile()) toggleSide(true); return; }
      const menuBtn = t.closest("[data-ek-menu]");
      if (menuBtn) {
        const menu = document.getElementById(menuBtn.dataset.ekMenu);
        const open = !menu.classList.contains("is-open");
        closeMenus(menu);
        menu.classList.toggle("is-open", open);
        menuBtn.classList.toggle("is-open", open);
        return;
      }
      if (!t.closest(".ek-menu")) closeMenus();
      const opener = t.closest("[data-ek-open]");
      if (opener) return openOverlay(opener.dataset.ekOpen, true);
      const closer = t.closest("[data-ek-close]");
      if (closer) return openOverlay(closer.closest(".ek-drawer, .ek-dialog").id, false);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      closeMenus();
      $$(".ek-drawer.is-open, .ek-dialog.is-open").forEach((o) => openOverlay(o.id, false));
      if (mobile()) toggleSide(false);
    });

    matchMedia("(max-width: 899.98px)").addEventListener("change", () => {
      $(".ek-side")?.classList.remove("is-mobile-open");
      $(".ek-scrim")?.classList.remove("is-open");
    });

    $$(".ek-seg").forEach(initSeg);
    $$(".ek-tabs[data-ek-tabs]").forEach(initTabs);
    icons();
  }

  window.DS = { chart, toast, setTheme, toggleSide, openOverlay, icons };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
