// "+ Add manuals" panel shared by both apps: upload with conflict check,
// single-page replacement and library rebuild, all against the local app
// server's /api endpoints for one app (repair | electrical).
//
//   const panel = AddManuals.create({
//     app: "electrical",                      // X-App target
//     files: () => [{title, file, pages}],    // manuals offered for page replacement
//     overlapNoun: "circuit pages",           // what "overlap" counts in conflicts
//     checkHint: "...", rebuildHint: "...",
//   });
//   container.innerHTML = panel.html(); panel.wire(container);
"use strict";
window.AddManuals = (function(){
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
  function fmtSize(n){
    if(n>=1048576) return (n/1048576).toFixed(1)+" MB";
    if(n>=1024) return (n/1024).toFixed(0)+" KB";
    return n+" B";
  }
  function fstClass(st){
    if(!st||st==="…") return "";
    if(st==="conflict") return "warn";
    if(st==="added"||st==="overwritten"||st==="aborted"||st.startsWith("kept as ")) return "ok";
    return "err";
  }

  function create(cfg){
    const ADD={files:[],uploading:false,building:false,doneOk:false,poll:null,api:null};
    const RP={rec:null,file:null};
    const H={"X-App":cfg.app};
    const q="?app="+encodeURIComponent(cfg.app);
    const $=id=>document.getElementById(id);

    function html(){
      let h='<div class="cbar"><span class="ttl">Add manuals</span>'+
        '<span class="sub">'+esc(cfg.subtitle||"Drop in extra PDF sections and rebuild the library")+'</span></div>'+
        '<div class="addwrap">';
      h+='<div class="card" id="apinote" style="display:none"><h3>Heads up</h3><div class="inner">'+
        '<p class="note">Adding manuals needs the app server. Close this window and run '+
        '<b>CelicaManual.exe</b>, then open “+ Add manuals” again.</p></div></div>';
      h+='<div class="card"><h3>1 · Add PDFs</h3><div class="inner">'+
        '<div class="dropzone" id="drop">Drag &amp; drop PDF files here<br>or <b>click to browse</b></div>'+
        '<input type="file" id="fpick" accept=".pdf,application/pdf" multiple style="display:none">'+
        '<ul class="flist" id="flist"></ul>'+
        '<div class="btnrow">'+
          '<button class="btn" id="upbtn" disabled>Upload &amp; check</button>'+
          '<button class="btn ghost" id="clrbtn" disabled>Clear list</button>'+
          '<span class="sub" id="upmsg"></span>'+
        '</div>'+
        '<div id="conflicts"></div>'+
        '<p class="hint" style="margin:10px 0 0">'+esc(cfg.checkHint)+'</p>'+
        '</div></div>';
      h+='<div class="card"><h3>2 · Replace a single page (optional)</h3><div class="inner">'+
        '<p class="hint">Fix one bad scan without re-uploading the whole manual: pick the manual, '+
        'the page number, and a one-page replacement PDF.</p>'+
        '<div class="rp-row">'+
          '<div class="rpsearchwrap">'+
            '<input type="text" id="rpsearch" placeholder="Search manuals by title or filename…" autocomplete="off">'+
            '<div class="rplist" id="rplist"></div>'+
          '</div>'+
          '<input type="number" id="rppage" min="1" placeholder="Page #" style="width:92px" disabled>'+
          '<button class="btn ghost" id="rppick">Choose PDF…</button>'+
          '<input type="file" id="rpfile" accept=".pdf,application/pdf" style="display:none">'+
          '<button class="btn" id="rpgo" disabled>Replace page</button>'+
        '</div>'+
        '<div class="sub" id="rpsel" style="margin-top:8px"></div>'+
        '<div class="sub" id="rpmsg" style="margin-top:6px"></div>'+
        '</div></div>';
      h+='<div class="card"><h3>3 · Rebuild library</h3><div class="inner">'+
        '<p class="hint">'+esc(cfg.rebuildHint)+'</p>'+
        '<div class="btnrow">'+
          '<button class="btn" id="rbbtn">Rebuild library</button>'+
          '<button class="btn" id="rlbtn" style="display:none;background:var(--accent2)">Reload app</button>'+
          '<span class="sub" id="rbmsg"></span>'+
        '</div>'+
        '<div class="buildlog" id="blog" style="display:none"></div>'+
        '</div></div>';
      return h+'</div>';
    }

    function addFiles(list){
      for(const f of list){
        if(!/\.pdf$/i.test(f.name)) continue;
        if(ADD.files.some(x=>x.file.name===f.name)) continue;
        ADD.files.push({file:f,status:""});
      }
      drawFlist();
    }
    function drawFlist(){
      const ul=$("flist"); if(!ul) return;
      ul.innerHTML=ADD.files.map(x=>
        '<li><span class="fname">'+esc(x.file.name)+'</span>'+
        '<span class="fsize">'+fmtSize(x.file.size)+'</span>'+
        (x.status?'<span class="fst '+fstClass(x.status)+'">'+esc(x.status)+'</span>':'')+
        '</li>').join("");
      const pending=ADD.files.some(x=>!x.status);
      $("upbtn").disabled=ADD.api===false||!ADD.files.length||!pending||ADD.uploading;
      $("clrbtn").disabled=!ADD.files.length||ADD.uploading;
    }
    async function commitFile(name,action){
      const res=await fetch("/api/commit",{method:"POST",
        headers:Object.assign({"Content-Type":"application/json"},H),
        body:JSON.stringify({files:[{name:name,action:action}]})});
      const j=await res.json();
      return {r:(j.results&&j.results[0])||{ok:false,error:"no result"},count:j.count};
    }
    async function uploadAll(){
      ADD.uploading=true; drawFlist();
      const msg=$("upmsg");
      let okCount=0,nconf=0,total=null;
      for(const x of ADD.files){
        if(x.status) continue;                       // only fresh files
        x.status="…"; drawFlist();
        try{
          const res=await fetch("/api/upload",{method:"POST",
            headers:Object.assign({"X-Filename":x.file.name,"Content-Type":"application/pdf"},H),
            body:x.file});
          const j=await res.json();
          if(!j.ok){x.status=j.error||"failed";}
          else if(j.conflict){x.status="conflict"; x.conflict=j.conflict; nconf++;}
          else{
            const c=await commitFile(x.file.name,"add");
            if(c.r.ok){x.status="added"; okCount++; total=c.count;}
            else x.status=c.r.error||"failed";
          }
        }catch(e){x.status="failed — is CelicaManual.exe running?";}
        drawFlist(); drawConflicts();
      }
      ADD.uploading=false; drawFlist();
      msg.textContent=(okCount?okCount+" added":"")+
        (nconf?(okCount?", ":"")+nconf+" conflict"+(nconf!==1?"s":"")+" — decide below":"")+
        (total?" — library now has "+total+" PDFs":"");
    }
    function verdictLine(cf){
      if(cf.verdict==="more_complete")
        return {cls:"good",txt:"Existing: "+cf.existing_pages+" pages"+
          (cf.existing_range?" ("+cf.existing_range+")":"")+
          " · Your upload: "+cf.incoming_pages+" pages"+
          (cf.incoming_range?" ("+cf.incoming_range+")":"")+
          " → MORE complete (+"+(cf.incoming_pages-cf.existing_pages)+" pages)"};
      if(cf.verdict==="less_complete")
        return {cls:"bad",txt:"Your upload has "+cf.incoming_pages+" page"+
          (cf.incoming_pages!==1?"s":"")+"; "+cf.pages_lost_if_overwrite+
          " existing page"+(cf.pages_lost_if_overwrite!==1?"s":"")+
          " would be LOST if you overwrite"};
      return {cls:"warn",txt:"Similar coverage — "+cf.incoming_pages+" vs "+
        cf.existing_pages+" pages, "+cf.overlap+" overlapping "+cfg.overlapNoun};
    }
    function drawConflicts(){
      const box=$("conflicts"); if(!box) return;
      const items=ADD.files.filter(x=>x.status==="conflict");
      box.innerHTML=items.map(x=>{
        const cf=x.conflict, v=verdictLine(cf);
        const lose=cf.pages_lost_if_overwrite;
        return '<div class="conflict" data-name="'+esc(x.file.name)+'">'+
          '<div class="cf-name">⚠ <b>'+esc(x.file.name)+'</b> conflicts with <b>'+esc(cf.existing)+'</b>'+
            (cf.type==="content"?' (overlapping '+esc(cfg.overlapNoun)+')':' (same filename)')+'</div>'+
          '<div class="cf-nums">existing: '+cf.existing_pages+'p'+
            (cf.existing_range?' · '+esc(cf.existing_range):'')+' · '+cf.existing_codes+' '+esc(cfg.overlapNoun)+
            ' &nbsp;|&nbsp; upload: '+cf.incoming_pages+'p'+
            (cf.incoming_range?' · '+esc(cf.incoming_range):'')+' · '+cf.incoming_codes+' '+esc(cfg.overlapNoun)+
            ' &nbsp;|&nbsp; overlap: '+cf.overlap+'</div>'+
          '<div class="cf-verdict '+v.cls+'">'+esc(v.txt)+'</div>'+
          '<div class="btnrow">'+
            '<button class="btn ghost" data-act="abort">Abort</button>'+
            '<button class="btn" data-act="overwrite">Overwrite'+
              (lose?' — lose '+lose+' page'+(lose!==1?'s':''):'')+'</button>'+
            '<button class="btn ghost" data-act="keep_both">Keep both</button>'+
          '</div></div>';
      }).join("");
      box.querySelectorAll(".conflict").forEach(el=>{
        el.querySelectorAll("[data-act]").forEach(b=>b.onclick=()=>
          resolveConflict(el.dataset.name,b.dataset.act));
      });
    }
    async function resolveConflict(name,action){
      const x=ADD.files.find(f=>f.file.name===name); if(!x) return;
      try{
        const c=await commitFile(name,action);
        if(c.r.ok){
          x.conflict=null;
          x.status=action==="abort"?"aborted":
            action==="keep_both"?("kept as "+c.r.final):"overwritten";
          $("upmsg").textContent="Library now has "+c.count+" PDFs. Rebuild below when you're done.";
        } else x.status=c.r.error||"failed";
      }catch(e){x.status="failed";}
      drawFlist(); drawConflicts();
    }
    function pollStatus(){
      fetch("/api/status"+q).then(r=>r.json()).then(s=>{
        const log=$("blog"), msg=$("rbmsg");
        if(!log) {clearInterval(ADD.poll); ADD.poll=null; return;}
        log.style.display="block";
        log.textContent=(s.log||[]).join("\n")||"Starting…";
        log.scrollTop=log.scrollHeight;
        if(s.done){
          clearInterval(ADD.poll); ADD.poll=null; ADD.building=false;
          const rb=$("rbbtn");
          rb.disabled=false; rb.textContent="Rebuild library";
          if(s.error){ msg.textContent="Build failed — see log"; log.textContent+="\n"+s.error; }
          else{
            ADD.doneOk=true;
            msg.textContent="Done! Reload to see the new sections.";
            $("rlbtn").style.display="";
          }
        }
      }).catch(()=>{});
    }
    function startRebuild(){
      const rb=$("rbbtn"), msg=$("rbmsg");
      fetch("/api/rebuild"+q,{method:"POST",headers:H}).then(r=>r.json()).then(j=>{
        ADD.building=true; ADD.doneOk=false;
        rb.disabled=true; rb.innerHTML='<span class="spin"></span>Rebuilding…';
        msg.textContent=j.started?"":"A rebuild was already running — showing its progress.";
        $("rlbtn").style.display="none";
        if(ADD.poll) clearInterval(ADD.poll);
        ADD.poll=setInterval(pollStatus,1500); pollStatus();
      }).catch(()=>{msg.textContent="Could not reach the app server.";});
    }

    function drawRp(){
      const sel=$("rpsel"), pg=$("rppage"), go=$("rpgo");
      if(!sel) return;
      sel.textContent=(RP.rec?"Selected: "+RP.rec.file+" · "+RP.rec.pages+" pages":"")+
        (RP.file?(RP.rec?"  —  ":"")+"replacement: "+RP.file.name+" ("+fmtSize(RP.file.size)+")":"");
      pg.disabled=!RP.rec; if(RP.rec) pg.max=RP.rec.pages;
      const n=parseInt(pg.value,10);
      go.disabled=ADD.api===false||!RP.rec||!RP.file||!(n>=1&&RP.rec&&n<=RP.rec.pages);
    }
    async function replacePage(){
      const pg=$("rppage"), msg=$("rpmsg");
      const n=parseInt(pg.value,10);
      msg.style.color=""; msg.textContent="Replacing…";
      try{
        const res=await fetch("/api/replace-page",{method:"POST",
          headers:Object.assign({"X-Target":RP.rec.file,"X-Page":String(n),
                                 "Content-Type":"application/pdf"},H),
          body:RP.file});
        const j=await res.json();
        if(j.ok){
          msg.style.color="var(--accent2)";
          msg.textContent="Replaced page "+n+" of "+RP.rec.file+" — page count unchanged ("+
            j.pages+"). Rebuild the library below to refresh search and previews.";
          RP.file=null; drawRp();
        }else{
          msg.style.color="var(--accent)";
          msg.textContent=j.error||"Replace failed.";
        }
      }catch(e){
        msg.style.color="var(--accent)";
        msg.textContent="Could not reach the app server — is CelicaManual.exe running?";
      }
    }
    function wireRp(c){
      const rs=c.querySelector("#rpsearch"), rl=c.querySelector("#rplist"),
            pg=c.querySelector("#rppage"), pick=c.querySelector("#rppick"),
            rf=c.querySelector("#rpfile");
      let hits=[];
      rs.oninput=()=>{
        const s=rs.value.toLowerCase().trim();
        if(!s){rl.style.display="none"; return;}
        hits=cfg.files().filter(r=>(r.title+" "+r.file).toLowerCase().includes(s)).slice(0,8);
        rl.innerHTML=hits.length?hits.map((r,i)=>
          '<div data-i="'+i+'">'+esc(r.title)+
          ' <span class="rpfile">'+esc(r.file)+' · '+r.pages+'p</span></div>').join("")
          :'<div style="color:var(--muted);cursor:default">No match</div>';
        rl.style.display="block";
        rl.querySelectorAll("[data-i]").forEach(el=>el.onclick=()=>{
          RP.rec=hits[+el.dataset.i]; rs.value=RP.rec.title;
          rl.style.display="none"; pg.value=""; drawRp();
        });
      };
      rs.addEventListener("blur",()=>setTimeout(()=>{rl.style.display="none";},200));
      pg.oninput=drawRp;
      pick.onclick=()=>rf.click();
      rf.onchange=()=>{
        const f=rf.files[0]; rf.value="";
        if(f&&/\.pdf$/i.test(f.name)){RP.file=f;} drawRp();
      };
      c.querySelector("#rpgo").onclick=replacePage;
    }

    function wire(c){
      // detect the API (only available under CelicaManual.exe / app.py server)
      fetch("/api/status"+q).then(r=>r.json()).then(()=>{ADD.api=true;})
        .catch(()=>{ADD.api=false;
          const n=c.querySelector("#apinote"); if(n)n.style.display="";
          ["upbtn","rbbtn","rpgo","rppick"].forEach(id=>{
            const b=c.querySelector("#"+id); if(b)b.disabled=true;});
        });
      const drop=c.querySelector("#drop"), pick=c.querySelector("#fpick");
      drop.onclick=()=>pick.click();
      pick.onchange=()=>{addFiles(pick.files); pick.value="";};
      drop.ondragover=e=>{e.preventDefault(); drop.classList.add("drag");};
      drop.ondragleave=()=>drop.classList.remove("drag");
      drop.ondrop=e=>{e.preventDefault(); drop.classList.remove("drag"); addFiles(e.dataTransfer.files);};
      c.querySelector("#upbtn").onclick=uploadAll;
      c.querySelector("#clrbtn").onclick=()=>{ADD.files=[]; drawFlist(); drawConflicts();
        $("upmsg").textContent="";};
      c.querySelector("#rbbtn").onclick=startRebuild;
      c.querySelector("#rlbtn").onclick=()=>location.reload();
      wireRp(c);
      drawFlist(); drawConflicts(); drawRp();
      if(ADD.building){
        const rb=c.querySelector("#rbbtn");
        rb.disabled=true; rb.innerHTML='<span class="spin"></span>Rebuilding…';
        if(!ADD.poll) ADD.poll=setInterval(pollStatus,1500);
        pollStatus();
      } else if(ADD.doneOk){
        c.querySelector("#rlbtn").style.display="";
        c.querySelector("#rbmsg").textContent="Done! Reload to see the new sections.";
      }
    }

    return {html:html, wire:wire};
  }
  return {create:create};
})();
