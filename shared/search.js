// Shared search helpers. A hit remembers the page number printed in the
// "===== PAGE n of N =====" banners the catalog builders insert.
"use strict";
(function (root) {
  const Lib = root.Lib = root.Lib || {};

  Lib.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c];
    });
  };

  Lib.terms = function (q) {
    return String(q || "").toLowerCase().split(/\s+/).filter(Boolean);
  };

  Lib.hi = function (text, terms) {
    let out = Lib.esc(text);
    (terms || []).forEach(function (w) {
      if (!w) return;
      const re = new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
      out = out.replace(re, "<mark>$1</mark>");
    });
    return out;
  };

  // Find the earliest term in `text` and the catalog page it sits on.
  Lib.findHit = function (text, terms) {
    const empty = {page: null, snippet: ""};
    if (!text || !terms || !terms.length) return empty;
    const low = text.toLowerCase();
    let at = -1;
    for (let i = 0; i < terms.length; i++) {
      const p = low.indexOf(terms[i]);
      if (p >= 0 && (at < 0 || p < at)) at = p;
    }
    if (at < 0) return empty;
    let page = null;
    const head = low.lastIndexOf("===== page ", at);
    if (head >= 0) {
      const m = /^===== page (\d+) of/.exec(low.slice(head, head + 32));
      if (m) page = parseInt(m[1], 10);
    }
    const start = Math.max(0, at - 60);
    const end = Math.min(text.length, at + 110);
    let raw = text.slice(start, end).replace(/=====\s*PAGE\s+\d+\s+of\s+\d+\s*=====/ig, " ");
    raw = raw.replace(/\s+/g, " ").trim();
    const snippet = (start > 0 ? "…" : "") + Lib.hi(raw, terms) + (end < text.length ? "…" : "");
    return {page: page, snippet: snippet};
  };
})(typeof window !== "undefined" ? window : globalThis);
