// Checks the shared garage and search helpers without a browser.
"use strict";
const fs = require("fs");
const path = require("path");
const store = {};
global.localStorage = {
  getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
  removeItem(k) { delete store[k]; },
};
function load(rel) {
  eval(fs.readFileSync(path.join(__dirname, "..", rel), "utf8"));
}
load("shared/search.js");
load("shared/garage.js");

let failed = 0;
function check(name, cond) {
  if (!cond) { failed += 1; console.error("FAIL", name); }
  else console.log("ok", name);
}

const hit = Lib.findHit(
  "intro\n===== PAGE 4 of 9 =====\nTorque the head bolts to 54 N-m",
  ["head", "bolts"]);
check("search finds the catalog page", hit.page === 4 && hit.snippet.includes("head"));
check("search misses cleanly", Lib.findHit("nope", ["zz"]).page === null);
const clustered = Lib.findHit(
  "===== PAGE 2 of 9 =====\nblock only\n===== PAGE 8 of 9 =====\ncylinder block main journal bore",
  ["cylinder", "block", "journal"]);
check("search prefers words that sit together", clustered.page === 8);
let earlyNoise = "===== PAGE 1 of 2 =====\n";
for (let i = 0; i < 40; i++) earlyNoise += "turbocharger of the case ";
earlyNoise += "\n===== PAGE 2 of 2 =====\nREMOVAL OF TURBOCHARGER\n";
const later = Lib.findHit(earlyNoise, ["removal", "of", "turbocharger"]);
check("search still finds a heading later in a long book", later.page === 2);

const st185 = {id: "a", name: "All-Trac", year: 1993, model: "ST185", trans: "M/T",
  body: "LIFTBACK", market: "USA", ac: "auto", blower: "dial"};
const st184 = {id: "b", name: "GT-S", year: 1992, model: "ST184", trans: "A/T",
  body: "LIFTBACK", market: "USA", ac: "manual", blower: ""};
Garage.saveCar(st185);
Garage.saveCar(st184);
Garage.select("repair", "a");
Garage.select("electrical", "b");
check("tabs keep different cars",
  Garage.selected("repair").id === "a" && Garage.selected("electrical").id === "b");

const recs = [
  {id: "em93", system: "Engine Mechanical", engine: "3sgte", edition: ""},
  {id: "em90", system: "Engine Mechanical", engine: "3sgte", edition: "1990"},
  {id: "ge", system: "Engine Mechanical", engine: "3sge", edition: ""},
  {id: "fe", system: "Fuel / EFI (MFI-SFI)", engine: "5sfe", edition: ""},
  {id: "br", system: "Brakes", engine: "na", edition: ""},
  {id: "cl90", system: "Clutch", engine: "na", edition: "1990"},
];
const car = Garage.selected("repair");
check("3S-GTE section fits the All-Trac", Garage.repairFits(recs[0], recs, car));
check("3S-GE section stays out", !Garage.repairFits(recs[2], recs, car));
check("5S-FE section stays out", !Garage.repairFits(recs[3], recs, car));
check("shared brakes stay", Garage.repairFits(recs[4], recs, car));
check("1990 engine pages hide when 1993 has that system", !Garage.repairFits(recs[1], recs, car));
check("1990 clutch stays when that year is the only copy", Garage.repairFits(recs[5], recs, car));
const side = {id: "gebook", system: "Engine Mechanical", engine: "na", edition: "3sge"};
check("a side book is not treated as the 1993 shelf", Garage.repairFits(side, recs.concat([side]), car));
const whole = {id: "rm266", system: "Fuel / EFI (MFI-SFI)", engine: "3sgte", edition: "1991",
  own_codes: ["FI-1", "EM-10", "CO-2", "IG-3"]};
const efi93 = {id: "efi93", system: "Fuel / EFI (MFI-SFI)", engine: "3sgte", edition: ""};
check("a whole older manual stays when this year has one of its systems",
  Garage.repairFits(whole, recs.concat([whole, efi93]), car));
const y94 = {id: "rm398", system: "Engine Mechanical", engine: "3sgte", edition: "1994",
  own_codes: ["EG-4", "EG-10"]};
check("1994 supplement stays visible for a 1993 car",
  Garage.repairFits(y94, recs.concat([y94]), car));
const feCar = {id: "c", name: "GT", year: 1993, model: "ST184", trans: "M/T",
  body: "LIFTBACK", market: "USA", ac: "auto", blower: "dial"};
check("1994 3S-GTE supplement stays off a 5S-FE car",
  !Garage.repairFits(y94, recs.concat([y94]), feCar));

const circuit = {applies: {engines: ["5S-FE"], drive: ["2WD"]}, option: ""};
check("wiring circuit fits the other tab's car",
  Garage.misfit(circuit, Garage.selected("electrical")).length === 0);
check("same circuit does not fit the All-Trac",
  Garage.misfit(circuit, Garage.selected("repair")).length > 0);

Garage.remove("a");
check("deleting a car clears only that pick",
  !Garage.selected("repair") && Garage.selected("electrical").id === "b");

if (failed) {
  console.error(failed + " failed");
  process.exit(1);
}
console.log("all checks passed");
