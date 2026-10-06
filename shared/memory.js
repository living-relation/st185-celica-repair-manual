// Each tab remembers its own recent sections, pins, and last place.
// The other tab keeps a separate list.
"use strict";
(function (root) {
  const Lib = root.Lib = root.Lib || {};

  function key(app, kind) { return "celica." + app + "." + kind; }

  function readList(app, kind) {
    try { return JSON.parse(localStorage.getItem(key(app, kind)) || "[]"); }
    catch (e) { return []; }
  }

  function same(a, b) {
    return a.id === b.id && (a.page || null) === (b.page || null);
  }

  const Memory = {
    recent(app) { return readList(app, "recent"); },
    pins(app) { return readList(app, "pins"); },
    pushRecent(app, item) {
      const next = readList(app, "recent").filter(function (x) { return !same(x, item); });
      next.unshift({id: item.id, title: item.title, page: item.page || null, at: Date.now()});
      localStorage.setItem(key(app, "recent"), JSON.stringify(next.slice(0, 12)));
    },
    isPinned(app, id, page) {
      const item = {id: id, page: page || null};
      return readList(app, "pins").some(function (x) { return same(x, item); });
    },
    togglePin(app, item) {
      const list = readList(app, "pins");
      const i = list.findIndex(function (x) { return same(x, item); });
      if (i >= 0) list.splice(i, 1);
      else list.unshift({id: item.id, title: item.title, page: item.page || null, at: Date.now()});
      localStorage.setItem(key(app, "pins"), JSON.stringify(list.slice(0, 30)));
      return i < 0;
    },
    place(app) {
      try { return JSON.parse(localStorage.getItem(key(app, "place")) || "null"); }
      catch (e) { return null; }
    },
    savePlace(app, place) {
      try { localStorage.setItem(key(app, "place"), JSON.stringify(place)); }
      catch (e) {}
    },
    flag(app, name, fallback) {
      const v = localStorage.getItem(key(app, name));
      return v == null ? fallback : v;
    },
    setFlag(app, name, value) {
      try { localStorage.setItem(key(app, name), value); }
      catch (e) {}
    },
  };

  root.Memory = Memory;
  Lib.Memory = Memory;
})(typeof window !== "undefined" ? window : globalThis);
