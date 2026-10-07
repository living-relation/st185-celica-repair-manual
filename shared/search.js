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

  // Tiny words show up on every page. They stay in the search only when
  // the person typed nothing else.
  const STOP = {a: 1, an: 1, and: 1, the: 1, of: 1, to: 1, for: 1, in: 1, on: 1, at: 1, by: 1, or: 1};

  function usefulTerms(terms) {
    const kept = terms.filter(function (word) { return word && !STOP[word]; });
    return kept.length ? kept : terms.filter(Boolean);
  }

  function positionsOf(low, word) {
    const found = [];
    let from = 0;
    while (found.length < 400) {
      const at = low.indexOf(word, from);
      if (at < 0) break;
      found.push(at);
      from = at + Math.max(1, word.length);
    }
    return found;
  }

  function pageRegions(low) {
    const marks = [];
    const re = /===== page (\d+) of \d+ =====/g;
    let mark;
    while ((mark = re.exec(low))) {
      marks.push({
        page: parseInt(mark[1], 10),
        at: mark.index,
        from: mark.index + mark[0].length,
      });
    }
    if (!marks.length) return [{page: null, from: 0, to: low.length}];
    const regions = [];
    if (marks[0].at > 0) regions.push({page: null, from: 0, to: marks[0].at});
    for (let i = 0; i < marks.length; i++) {
      regions.push({
        page: marks[i].page,
        from: marks[i].from,
        to: i + 1 < marks.length ? marks[i + 1].at : low.length,
      });
    }
    return regions;
  }

  // Prefer the page where the most search words sit together, then the
  // tightest group, then the earliest page. Each page is scored on its own
  // so a heading near the end of a long book is not skipped.
  Lib.findHit = function (text, terms) {
    const empty = {page: null, snippet: ""};
    if (!text || !terms || !terms.length) return empty;
    const use = usefulTerms(terms);
    const low = text.toLowerCase();
    let best = null;
    pageRegions(low).forEach(function (region) {
      const body = low.slice(region.from, region.to);
      const lists = use.map(function (word) { return positionsOf(body, word); })
        .filter(function (list) { return list.length; });
      if (!lists.length) return;
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
          const abs = region.from + at;
          if (!best || score > best.score ||
              (score === best.score && span < best.span) ||
              (score === best.score && span === best.span && abs < best.at))
            best = {score: score, span: span, at: abs, page: region.page};
        });
      });
    });
    if (!best) return empty;
    const at = best.at;
    let page = null;
    const head = low.lastIndexOf("===== page ", at);
    if (best.page) page = best.page;
    else if (head >= 0) {
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
