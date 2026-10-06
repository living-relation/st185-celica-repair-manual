// Hover preview shared by both tabs. Each page has one #pv box.
"use strict";
(function (root) {
  const Lib = root.Lib = root.Lib || {};

  Lib.hidePreview = function () {
    const pv = document.getElementById("pv");
    if (pv) pv.style.display = "none";
  };

  function movePreview(e) {
    const pv = document.getElementById("pv");
    if (!pv) return;
    const w = 274, h = 380;
    let x = e.clientX + 18, y = e.clientY + 14;
    if (x + w > innerWidth) x = e.clientX - w - 18;
    if (y + h > innerHeight) y = Math.max(8, innerHeight - h - 8);
    pv.style.left = x + "px";
    pv.style.top = y + "px";
  }

  Lib.bindPreviews = function (scope) {
    const pv = document.getElementById("pv");
    if (!pv) return;
    scope.querySelectorAll("[data-pv]").forEach(function (el) {
      el.addEventListener("mouseenter", function (e) {
        const img = pv.querySelector("img");
        img.onerror = Lib.hidePreview;
        img.src = el.dataset.pv;
        pv.querySelector(".cap").textContent = el.dataset.pvcap || "";
        pv.style.display = "block";
        movePreview(e);
      });
      el.addEventListener("mousemove", movePreview);
      el.addEventListener("mouseleave", Lib.hidePreview);
    });
  };
})(typeof window !== "undefined" ? window : globalThis);
