// Turn a page inside the PDF viewer that is already open.
// Loading the viewer again is slow, so a new page in the same file
// just tells the open viewer where to go.
"use strict";
(function (root) {
  const Lib = root.Lib = root.Lib || {};

  function fileParam(viewerUrl) {
    const m = /[?&]file=([^#&]+)/.exec(viewerUrl || "");
    if (!m) return "";
    try { return decodeURIComponent(m[1]); }
    catch (e) { return m[1]; }
  }

  function sameFile(appUrl, want) {
    if (!appUrl || !want) return false;
    if (appUrl === want) return true;
    try { return decodeURIComponent(appUrl) === want; }
    catch (e) { return false; }
  }

  Lib.showPdfPage = function (iframe, viewerUrl, page) {
    const want = fileParam(viewerUrl);
    const dest = page || 1;
    let app = null;
    try { app = iframe.contentWindow && iframe.contentWindow.PDFViewerApplication; }
    catch (e) { app = null; }
    if (app && app.pdfViewer && sameFile(app.url, want)) {
      const go = function () {
        if (app.page !== dest) app.page = dest;
      };
      if (app.initializedPromise && app.initializedPromise.then) app.initializedPromise.then(go);
      else go();
      return;
    }
    iframe.src = viewerUrl;
  };
})(typeof window !== "undefined" ? window : globalThis);
