// Messaging between the workshop-library shell (/index.html) and the apps it
// hosts in iframes. Apps stay separate: they only exchange "open" requests.
//   Shell.open(app, id, page)  ask the shell to switch to `app` and open `id`
//   Shell.onOpen(fn)           fn(id, page) when the shell (or a #open= URL)
//                              asks this app to open a record
"use strict";
(function(){
  const APP_PATHS = {repair:"celica-manual/index.html", electrical:"electrical/index.html"};
  const embedded = window.parent !== window;
  if(embedded) document.documentElement.classList.add("embedded");
  document.addEventListener("DOMContentLoaded",()=>{
    if(embedded) document.body.classList.add("embedded");
  });
  if(embedded) document.addEventListener("keydown", e=>{
    if((e.ctrlKey||e.metaKey) && (e.key==="1"||e.key==="2")){
      e.preventDefault();
      window.parent.postMessage({type:"key", key:e.key}, location.origin);
    }
  });

  function parseOpenHash(){
    const m = /(?:^#|&)open=([^&]+)(?:&page=(\d+))?/.exec(location.hash);
    return m ? {id:decodeURIComponent(m[1]), page:m[2]?parseInt(m[2],10):null} : null;
  }

  window.Shell = {
    embedded: embedded,
    open(app, id, page){
      if(embedded){
        window.parent.postMessage({type:"open", app:app, id:id, page:page||null},
                                  location.origin);
        return;
      }
      const url = new URL("../"+APP_PATHS[app], location.href);
      url.hash = "open="+encodeURIComponent(id)+(page?"&page="+page:"");
      window.open(url.href, "_blank");
    },
    onOpen(fn){
      window.addEventListener("message", e=>{
        if(e.origin!==location.origin || !e.data || e.data.type!=="open") return;
        fn(e.data.id, e.data.page||null);
      });
      const h = parseOpenHash();
      if(h) fn(h.id, h.page);
    },
  };
})();
