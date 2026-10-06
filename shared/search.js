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

  function positionsOf(low, word) {
    const found = [];
    let from = 0;
    while (found.length < 30) {
      const at = low.indexOf(word, from);
      if (at < 0) break;
      found.push(at);
      from = at + Math.max(1, word.length);
    }
    return found;
  }

  // Prefer the spot where the most search words sit together, then the
  // earliest such spot. A lone early word should not beat a real sentence.
  Lib.findHit = function (text, terms) {
    const empty = {page: null, snippet: ""};
    if (!text || !terms || !terms.length) return empty;
    const low = text.toLowerCase();
    const lists = terms.map(function (word) { return positionsOf(low, word); })
      .filter(function (list) { return list.length; });
    if (!lists.length) return empty;
    let best = null;
    lists.forEach(function (list) {
      list.forEach(function (at) {
        const end = at + 500;
        let score = 0;
        let far = at;
        for (let i = 0; i < lists.length; i++) {
          const hit = lists[i].find(function (p) { return p >= at && p <= end; });
          if (hit != null) {
            score++;
            if (hit > far) far = hit;
          }
        }
        const span = far - at;
        if (!best || score > best.score ||
            (score === best.score && span < best.span) ||
            (score === best.score && span === best.span && at < best.at))
          best = {score: score, span: span, at: at};
      });
    });
    const at = best.at;
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
