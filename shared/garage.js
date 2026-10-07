// One shared list of cars. Each tab picks its own car from that list.
// Changing the pick in the repair tab leaves the electrical tab alone.
// Editing a car updates the saved car, so a tab that uses it sees the new answers.
"use strict";
(function (root) {
  const GARAGE_KEY = "celica.garage";
  const MIGRATED = "celica.garage.v1";

  const MODELS = {
    ST185: {label: "ST185 GT-Four / All-Trac (3S-GTE turbo)", engine: "3S-GTE", code: "3sgte", drive: "ALL-TRAC/4WD"},
    ST184: {label: "ST184 GT / GT-S (5S-FE)", engine: "5S-FE", code: "5sfe", drive: "2WD"},
    AT180: {label: "AT180 ST (4A-FE)", engine: "4A-FE", code: "4afe", drive: "2WD"},
  };

  const EXAMPLE = {
    name: "1993 All-Trac",
    year: 1993, model: "ST185", trans: "M/T", body: "LIFTBACK", market: "USA",
    ac: "auto", blower: "dial", cd: "", power_seat: "", sunroof: "", cruise: "", abs: "",
  };

  const ENGINE_NAME = {
    "3sgte": "3S-GTE", "5sfe": "5S-FE", "4afe": "4A-FE", "3sge": "3S-GE",
    both: "3S-GTE and 5S-FE", na: "shared",
  };

  let draftId = null;

  function esc(s) {
    return root.Lib && root.Lib.esc ? root.Lib.esc(s) : String(s == null ? "" : s);
  }
  function selKey(app) { return "celica." + app + ".carId"; }
  function uid() {
    return "car-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }
  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(GARAGE_KEY) || '{"cars":[]}');
      if (!data || !Array.isArray(data.cars)) return {cars: []};
      return data;
    } catch (e) { return {cars: []}; }
  }
  function write(data) { localStorage.setItem(GARAGE_KEY, JSON.stringify(data)); }

  function label(car) {
    if (!car) return "No car";
    if (car.name && String(car.name).trim()) return String(car.name).trim();
    const model = MODELS[car.model];
    return String(car.year || "") + " " + (model ? model.engine : (car.model || "Celica"));
  }

  function migrate() {
    if (localStorage.getItem(MIGRATED)) return;
    if (read().cars.length) {
      localStorage.setItem(MIGRATED, "1");
      return;
    }
    const data = {cars: []};
    let electricalId = "";
    try {
      const old = JSON.parse(localStorage.getItem("ewd.profile") || "null");
      if (old && typeof old === "object" && (old.year || old.model)) {
        const car = Object.assign({id: uid()}, EXAMPLE, {
          name: "",
          year: Number(old.year) || 1993,
          model: MODELS[old.model] ? old.model : "ST185",
          trans: old.trans || "",
          body: old.body || "LIFTBACK",
          market: old.market || "USA",
          ac: old.ac || "",
          blower: old.blower || "",
          cd: old.cd || "",
          power_seat: old.power_seat || "",
          sunroof: old.sunroof || "",
          cruise: old.cruise || "",
          abs: old.abs || "",
        });
        car.name = label(car);
        data.cars.push(car);
        if (old.configured) electricalId = car.id;
      }
    } catch (e) { /* keep an empty garage */ }
    write(data);
    localStorage.setItem(MIGRATED, "1");
    if (electricalId) {
      localStorage.setItem(selKey("electrical"), electricalId);
      if (localStorage.getItem("celica.electrical.carOnly") == null)
        localStorage.setItem("celica.electrical.carOnly", "1");
    }
  }

  function cars() { migrate(); return read().cars.slice(); }
  function get(id) { return cars().find(function (c) { return c.id === id; }) || null; }

  function selected(app) {
    migrate();
    return get(localStorage.getItem(selKey(app)) || "");
  }
  function select(app, id) {
    if (id && get(id)) localStorage.setItem(selKey(app), id);
    else localStorage.removeItem(selKey(app));
  }
  function saveCar(car) {
    migrate();
    const data = read();
    const copy = Object.assign({}, car);
    if (!copy.id) copy.id = uid();
    if (!copy.name || !String(copy.name).trim()) copy.name = label(copy);
    const i = data.cars.findIndex(function (c) { return c.id === copy.id; });
    if (i >= 0) data.cars[i] = copy;
    else data.cars.push(copy);
    write(data);
    return copy;
  }
  function remove(id) {
    migrate();
    const data = read();
    data.cars = data.cars.filter(function (c) { return c.id !== id; });
    write(data);
    ["repair", "electrical"].forEach(function (app) {
      if (localStorage.getItem(selKey(app)) === id) localStorage.removeItem(selKey(app));
    });
    if (draftId === id) draftId = null;
  }

  function engineCode(model) { return (MODELS[model] || {}).code || ""; }

  function sectionYear(rec) {
    const edition = String(rec.edition || "");
    // 1994 is the ST205 supplement. A few pages differ from the 1993 book,
    // so it stays in the list instead of being treated as a replacement year.
    if (/^(1990|1991|1992|1993)$/.test(edition)) return Number(edition);
    if (!edition) return 1993;
    return null;
  }

  function engineFits(engine, car) {
    const want = engineCode(car.model);
    if (!want) return true;
    if (!engine || engine === "na") return true;
    if (engine === "both") return want === "3sgte" || want === "5sfe";
    return engine === want;
  }

  function codeFamilies(rec) {
    const seen = {};
    (rec.own_codes || []).forEach(function (code) {
      const prefix = String(code).split("-")[0];
      if (prefix && prefix !== String(code)) seen[prefix] = true;
    });
    return Object.keys(seen);
  }

  function yearFits(rec, records, car) {
    const year = sectionYear(rec);
    const want = Number(car.year);
    if (year == null || !want || year === want) return true;
    // One PDF can hold several systems and still be filed under just one.
    // The 1991 3S-GTE book is filed as fuel, but it also has engine,
    // cooling, and ignition pages. A newer fuel section does not replace it.
    if (codeFamilies(rec).length > 1) return true;
    const covered = (records || []).some(function (other) {
      return other !== rec && other.system === rec.system &&
        sectionYear(other) === want && engineFits(other.engine, car);
    });
    return !covered;
  }

  function repairFits(rec, records, car) {
    if (!car) return true;
    if (!engineFits(rec.engine, car)) return false;
    return yearFits(rec, records, car);
  }

  function repairWhy(rec, records, car) {
    if (!car) return [];
    const why = [];
    if (!engineFits(rec.engine, car))
      why.push((ENGINE_NAME[rec.engine] || "another engine") + " section");
    if (!yearFits(rec, records, car)) why.push(sectionYear(rec) + " edition");
    return why;
  }

  function suggestedBlower(year) {
    year = Number(year);
    if (year <= 1991) return "push";
    if (year >= 1993) return "dial";
    return "";
  }
  function blowerOf(car) {
    if (!car) return "";
    return car.blower || suggestedBlower(car.year);
  }

  // Why a wiring circuit does not fit a car. Empty list means it fits.
  // No car means nothing is ruled out.
  function misfit(c, car) {
    if (!car) return [];
    const a = c.applies || {};
    const model = MODELS[car.model] || MODELS.ST185;
    const why = [];
    if (a.engines && a.engines.length && !a.engines.includes(model.engine))
      why.push(a.engines.join("/") + " engine");
    if (a.drive && !a.drive.includes(model.drive))
      why.push(a.drive.join("/").toLowerCase().replace("all-trac", "All-Trac"));
    if (a.market && car.market && !a.market.includes(car.market))
      why.push(a.market.join("/") + " market");
    if (a.trans && car.trans && !a.trans.includes(car.trans))
      why.push(a.trans.join("/") + " only");
    if (a.body && car.body && !a.body.includes(car.body))
      why.push(a.body.join("/").toLowerCase() + " only");
    const ac = {auto: "AUTO", manual: "MANUAL", none: "NONE"}[car.ac];
    if (a.ac && ac && !a.ac.includes(ac))
      why.push({AUTO: "automatic A/C", MANUAL: "manual A/C", NONE: "no A/C"}[a.ac[0]]);
    const blower = blowerOf(car);
    if (a.blower && a.blower.length && blower && !a.blower.includes(blower.toUpperCase()))
      why.push(a.blower.map(function (b) { return b === "PUSH" ? "push-button" : "dial"; }).join("/") + " blower control");
    if (a.cd !== undefined && car.cd && a.cd !== (car.cd === "yes"))
      why.push(a.cd ? "with CD player" : "without CD player");
    if (c.option && car[c.option] === "no") why.push("option not fitted");
    return why;
  }

  function opt(value, text, current) {
    return '<option value="' + esc(value) + '"' +
      (String(current) === String(value) ? " selected" : "") + ">" + esc(text) + "</option>";
  }
  function tri(id, current) {
    return '<select id="' + id + '">' + opt("", "Not sure / show both", current) +
      opt("yes", "Yes", current) + opt("no", "No", current) + "</select>";
  }

  function formHTML(car) {
    const suggested = suggestedBlower(car.year);
    const hint = suggested === "push" ? "push-button" : suggested === "dial" ? "dial" : "1992: not sure";
    return '<div class="card"><h3>' + (car.id ? "Edit car" : "New car") + '</h3><div class="inner">' +
      '<div class="formgrid">' +
      '<label>Name</label><input id="g_name" value="' + esc(car.name || "") + '" placeholder="Name this car">' +
      '<label>Model year</label><select id="g_year">' +
        [1990, 1991, 1992, 1993].map(function (y) { return opt(y, y, car.year); }).join("") + '</select>' +
      '<label>Model</label><select id="g_model">' +
        Object.keys(MODELS).map(function (k) { return opt(k, MODELS[k].label, car.model); }).join("") + '</select>' +
      '<label>Transmission</label><select id="g_trans">' +
        opt("M/T", "Manual", car.trans) + opt("A/T", "Automatic", car.trans) + opt("", "Not sure", car.trans) + '</select>' +
      '<label>Body</label><select id="g_body">' +
        opt("LIFTBACK", "Liftback", car.body) + opt("COUPE", "Coupe", car.body) +
        opt("CONVERTIBLE", "Convertible", car.body) + '</select>' +
      '<label>Market</label><select id="g_market">' +
        opt("USA", "USA", car.market) + opt("CANADA", "Canada", car.market) + '</select>' +
      '<label>A/C type</label><select id="g_ac">' +
        opt("", "Not sure / show both", car.ac) + opt("auto", "Automatic climate control", car.ac) +
        opt("manual", "Manual A/C", car.ac) + opt("none", "No A/C", car.ac) + '</select>' +
      '<label>Blower control</label><select id="g_blower">' +
        opt("", "Use year default (" + hint + ")", car.blower) +
        opt("push", "Five push buttons", car.blower) +
        opt("dial", "Single dial", car.blower) + '</select>' +
      '<label>CD player</label>' + tri("g_cd", car.cd) +
      '<label>Power seat</label>' + tri("g_power_seat", car.power_seat) +
      '<label>Sun roof</label>' + tri("g_sunroof", car.sunroof) +
      '<label>Cruise control</label>' + tri("g_cruise", car.cruise) +
      '<label>ABS</label>' + tri("g_abs", car.abs) +
      '</div>' +
      '<p class="hint">1990–91 cars use five blower buttons. 1992–93 cars use a dial. Some 1992 cars have either.</p>' +
      '<div class="btnrow"><button class="btn" id="gsave">Save this car</button>' +
      '<button class="btn ghost" id="gcancel">Cancel</button>' +
      '<button class="btn ghost" id="gexample">Fill 1993 All-Trac example</button></div></div></div>';
  }

  function panelHTML(app) {
    const list = cars();
    const current = selected(app);
    let rows = list.map(function (car) {
      const on = current && current.id === car.id;
      return '<div class="carrow' + (on ? " on" : "") + '">' +
        '<div><b>' + esc(label(car)) + '</b><div class="gsub">' + esc(MODELS[car.model] ? MODELS[car.model].label : car.model) +
        (on ? " · used in this tab" : "") + '</div></div>' +
        '<div class="btnrow">' +
        '<button class="btn' + (on ? "" : " ghost") + '" data-use="' + esc(car.id) + '">' +
          (on ? "Using here" : "Use in this tab") + '</button>' +
        '<button class="btn ghost" data-edit="' + esc(car.id) + '">Edit</button>' +
        '<button class="btn ghost" data-del="' + esc(car.id) + '">Delete</button></div></div>';
    }).join("");
    if (!rows) rows = '<p class="hint">No saved cars yet. Add the car you are working on. The other tab can pick a different one.</p>';
    let form = "";
    if (draftId === "new") form = formHTML(Object.assign({id: ""}, EXAMPLE));
    else if (draftId && get(draftId)) form = formHTML(get(draftId));
    return '<div class="cbar"><span class="ttl">Garage</span><span class="sub">Saved cars for both tabs. This tab can use a different car than the other tab.</span></div>' +
      '<div class="addwrap"><div class="card"><h3>Saved cars</h3><div class="inner">' + rows +
      '<div class="btnrow"><button class="btn" id="gadd">Add a car</button></div></div></div>' + form + '</div>';
  }

  function readForm(rootEl, id) {
    function val(name) { return rootEl.querySelector("#g_" + name).value; }
    return {
      id: id || "",
      name: val("name"),
      year: parseInt(val("year"), 10),
      model: val("model"),
      trans: val("trans"),
      body: val("body"),
      market: val("market"),
      ac: val("ac"),
      blower: val("blower"),
      cd: val("cd"),
      power_seat: val("power_seat"),
      sunroof: val("sunroof"),
      cruise: val("cruise"),
      abs: val("abs"),
    };
  }

  function wire(rootEl, app, onChange) {
    const add = rootEl.querySelector("#gadd");
    if (add) add.onclick = function () { draftId = "new"; onChange("edit"); };
    rootEl.querySelectorAll("[data-use]").forEach(function (btn) {
      btn.onclick = function () {
        select(app, btn.dataset.use);
        onChange("use");
      };
    });
    rootEl.querySelectorAll("[data-edit]").forEach(function (btn) {
      btn.onclick = function () { draftId = btn.dataset.edit; onChange("edit"); };
    });
    rootEl.querySelectorAll("[data-del]").forEach(function (btn) {
      btn.onclick = function () {
        remove(btn.dataset.del);
        onChange("delete");
      };
    });
    const save = rootEl.querySelector("#gsave");
    if (save) {
      save.onclick = function () {
        const existing = draftId && draftId !== "new" ? draftId : "";
        const saved = saveCar(readForm(rootEl, existing));
        select(app, saved.id);
        draftId = null;
        onChange("save");
      };
    }
    const cancel = rootEl.querySelector("#gcancel");
    if (cancel) cancel.onclick = function () { draftId = null; onChange("cancel"); };
    const example = rootEl.querySelector("#gexample");
    if (example) example.onclick = function () {
      Object.keys(EXAMPLE).forEach(function (k) {
        const el = rootEl.querySelector("#g_" + k);
        if (el) el.value = EXAMPLE[k];
      });
    };
  }

  function buttonLabel(app) {
    const car = selected(app);
    return car ? label(car) : "Pick a car";
  }

  root.Garage = {
    MODELS: MODELS,
    EXAMPLE: EXAMPLE,
    cars: cars,
    get: get,
    selected: selected,
    select: select,
    saveCar: saveCar,
    remove: remove,
    label: label,
    buttonLabel: buttonLabel,
    engineFits: engineFits,
    repairFits: repairFits,
    repairWhy: repairWhy,
    sectionYear: sectionYear,
    misfit: misfit,
    blowerOf: blowerOf,
    suggestedBlower: suggestedBlower,
    panelHTML: panelHTML,
    wire: wire,
    migrate: migrate,
  };
})(typeof window !== "undefined" ? window : globalThis);
