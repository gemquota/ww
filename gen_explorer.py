#!/usr/bin/env python3
"""Generate self-contained architecture-explorer.html"""
import json

MODS = [
  {"id":"gemini_bridge_py","file":"gemini_bridge.py","dir":"/","layer":"entry","desc":"Thin root entry. Delegates to src/.","how":"Parses CLI args (--demo, --health, --auth, --verbose).","conn":["src_gemini_bridge","demo_conversation"]},
  {"id":"src_gemini_bridge","file":"gemini_bridge.py","dir":"src/","layer":"entry","desc":"Main orchestrator: REPL loop, init, signal handling, lifecycle.","how":"Loads config, inits Gemini, sets up memory/telemetry/checkpoints, runs REPL.","conn":["tui","ui_adapter","ui_utils","commands","command_tables","bridge_context","config_py","tool_executor","memory_core","context_manager","smart_context","telemetry","web_client","ww_client","validation_utils","plugin_system","mascot_gfx","file_watcher","demo_conversation","agent_hierarchy","prompt_templates","agents_loader"]},
  {"id":"tui","file":"tui.py","dir":"src/","layer":"ui","desc":"Terminal UI: header, colors, layout helpers.","how":"get_header() renders ASCII art. Builds keybindings.","conn":["src_gemini_bridge"]},
  {"id":"ui_adapter","file":"ui_adapter.py","dir":"src/","layer":"ui","desc":"UIAdapter protocol: Terminal and Silent implementations.","how":"Abstract interface for user interaction.","conn":["src_gemini_bridge"]},
  {"id":"ui_utils","file":"ui_utils.py","dir":"src/","layer":"ui","desc":"Theme, Spinner, MessageLevel, folding, render_box.","how":"MessageLevel drives formatting. ProgressSpinner daemon thread.","conn":["src_gemini_bridge"]},
  {"id":"commands","file":"commands.py","dir":"src/","layer":"orchest","desc":"Slash command dispatch (17 commands).","how":"COMMAND_TABLE dict maps /cmd to async handler.","conn":["src_gemini_bridge","bridge_context"]},
  {"id":"command_tables","file":"command_tables.py","dir":"src/","layer":"orchest","desc":"V4: /task and /plan commands.","how":"/task manages scopes. /plan shows render_box() preview.","conn":["commands"]},
  {"id":"bridge_context","file":"context.py","dir":"src/","layer":"orchest","desc":"BridgeContext: centralized shared state.","how":"Holds all module instances at startup. Eliminates singletons.","conn":["src_gemini_bridge","commands","tool_executor"]},
  {"id":"config_py","file":"config.py","dir":"src/","layer":"orchest","desc":"Pydantic-settings config loader (YAML+env).","how":"Settings tree + get_settings() cache.","conn":["src_gemini_bridge"]},
  {"id":"agent_hierarchy","file":"agents/*.md","dir":"agents/","layer":"agent","desc":"3-tier agent: Communicator>Overseer>Specialists.","how":"Communicator runs REPL. Overseer chains specialists.","conn":["src_gemini_bridge","tool_executor","prompt_templates","agents_loader"]},
  {"id":"prompt_templates","file":"prompt_templates.py","dir":"src/","layer":"agent","desc":"Versioned prompt templates with hash verification.","how":"PromptTemplate + Registry. SHA-256 logged per use.","conn":["agent_hierarchy","profile_manifest","bridge_context"]},
  {"id":"agents_loader","file":"agents_loader.py","dir":"src/","layer":"agent","desc":"Hierarchical AGENTS.md loader.","how":"Finds git root, loads files with precedence.","conn":["agent_hierarchy"]},
  {"id":"tool_executor","file":"tool_executor.py","dir":"src/","layer":"tool","desc":"Tool dispatch + agent delegation.","how":"execute() resolves DAG, dispatches, handles delegation.","conn":["src_gemini_bridge","tool_registry","system_tools","bridge_context","decision_tracer","agent_hierarchy"]},
  {"id":"tool_registry","file":"registry.py","dir":"src/tools/","layer":"tool","desc":"ToolRegistry with DAG dependency resolution.","how":"register() builds DAG. resolve_deps() sorts.","conn":["tool_executor","system_tools","plugin_system"]},
  {"id":"system_tools","file":"system_tools.py","dir":"src/tools/","layer":"tool","desc":"11 tool implementations.","how":"Each tool has Pydantic ArgsModel. Sandbox enforced.","conn":["tool_registry","tool_executor","permissions","diff_engine","checkpoint"]},
  {"id":"diff_engine","file":"diff_engine.py","dir":"src/","layer":"tool","desc":"Fuzzy SEARCH/REPLACE with ambiguity detection.","how":"apply_patch() finds best match. Reports ambiguous.","conn":["system_tools"]},
  {"id":"checkpoint","file":"checkpoint.py","dir":"src/","layer":"memory","desc":"Git checkpoint manager for /undo.","how":"snapshot() commits. undo() reverts. list_checkpoints().","conn":["system_tools","memory_core"]},
  {"id":"memory_core","file":"memory.py","dir":"src/core/","layer":"memory","desc":"3-tier SQLite memory: Hot/Facts/Summary + PCG.","how":"MemoryManager with SessionDatabase. WAL mode.","conn":["src_gemini_bridge","context_manager","checkpoint","dashboard_api","telemetry"]},
  {"id":"context_manager","file":"context_manager.py","dir":"src/","layer":"memory","desc":"ConversationHistory + RepoMapper + TokenCounter.","how":"tiktoken counting, ring buffer, workspace tree.","conn":["src_gemini_bridge","memory_core","smart_context"]},
  {"id":"smart_context","file":"smart_context.py","dir":"src/","layer":"memory","desc":"Git-aware workspace context.","how":".gitignore filtering, binary detection, surgical reads.","conn":["src_gemini_bridge","context_manager"]},
  {"id":"telemetry","file":"telemetry.py","dir":"src/","layer":"memory","desc":"Session telemetry: SQLite + JSONL.","how":"TelemetryManager with crash-safe commits.","conn":["src_gemini_bridge","dashboard_api","memory_core"]},
  {"id":"permissions","file":"permissions.py","dir":"src/","layer":"orchest","desc":"5-level approval + sandbox path enforcement.","how":"ApprovalPolicy + Sandbox class.","conn":["system_tools","tool_executor","src_gemini_bridge"]},
  {"id":"event_bus","file":"event_bus.py","dir":"src/bridge/","layer":"bridge","desc":"EventBus singleton for decoupled pub/sub.","how":"emit() / subscribe() / unsubscribe().","conn":["tool_executor","src_gemini_bridge","plugin_system"]},
  {"id":"fault_injector","file":"fault_injector.py","dir":"src/bridge/","layer":"bridge","desc":"Testing fault injection utility.","how":"FaultInjector context manager simulates failures.","conn":["tool_executor"]},
  {"id":"decision_tracer","file":"decision_tracer.py","dir":"src/bridge/","layer":"bridge","desc":"Decision tracing reasoning chain.","how":"start_trace() -> commit() -> JSONL.","conn":["tool_executor"]},
  {"id":"capability_registry","file":"capability_registry.py","dir":"src/bridge/","layer":"bridge","desc":"Capability registry with provider backends.","how":"register_provider() / get_providers().","conn":["tool_registry"]},
  {"id":"profile_manifest","file":"profile_manifest.py","dir":"src/bridge/","layer":"bridge","desc":"AgentProfileManifest for reproducibility.","how":"compute_fingerprint() hashes config+plugins.","conn":["prompt_templates"]},
  {"id":"plugin_system","file":"ww_plugin.py","dir":"src/plugins/","layer":"plugin","desc":"Plugin lifecycle + capability permissions.","how":"PluginScanner + state machine + permissions.","conn":["src_gemini_bridge","tool_registry","event_bus"]},
  {"id":"dashboard_api","file":"app.py","dir":"src/dashboard/","layer":"api","desc":"FastAPI REST API with Bearer auth.","how":"/api/v1/health, /chat, /sessions, /stats.","conn":["memory_core","telemetry","web_client"]},
  {"id":"ww_client","file":"ww_client.py","dir":"src/","layer":"api","desc":"Python SDK async client.","how":"async with WWClient(api_key) as bridge.","conn":["web_client"]},
  {"id":"web_client","file":"web_client.py","dir":"src/utils/","layer":"api","desc":"Dual-auth Gemini + CircuitBreaker + rate limit.","how":"API key or cookie. 3-state breaker, 30s recovery.","conn":["src_gemini_bridge","ww_client","dashboard_api"]},
  {"id":"validation_utils","file":"validation.py","dir":"src/utils/","layer":"api","desc":"Tool call extraction + error classification.","how":"extract_tool_call() / classify_error() / format_error().","conn":["src_gemini_bridge","tool_executor"]},
  {"id":"mascot_gfx","file":"mascot_tui.py","dir":"src/gfx/","layer":"ext","desc":"Animated ASCII mascot.","how":"Mascot class with thinking/success/error states.","conn":["src_gemini_bridge"]},
  {"id":"file_watcher","file":"file_watcher.py","dir":"src/","layer":"ext","desc":"Workspace change detector.","how":"asyncio task polls filesystem mtimes every 3s.","conn":["src_gemini_bridge","event_bus"]},
  {"id":"demo_conversation","file":"conversation.py","dir":"src/demo/","layer":"ext","desc":"Canned 5-turn demo conversation.","how":"--demo flag bypasses credentials.","conn":["src_gemini_bridge"]},
]

LAYERS = {
  "entry": {"bg":"#58a6ff","fg":"#fff","label":"Entry"},
  "ui": {"bg":"#3fb950","fg":"#fff","label":"UI & Shell"},
  "orchest": {"bg":"#d29922","fg":"#000","label":"Orchestration"},
  "agent": {"bg":"#a371f7","fg":"#fff","label":"Agent System"},
  "tool": {"bg":"#f78166","fg":"#fff","label":"Tool Execution"},
  "memory": {"bg":"#db6d28","fg":"#fff","label":"Memory & Data"},
  "bridge": {"bg":"#56d4dd","fg":"#000","label":"Abstractions"},
  "plugin": {"bg":"#ff7b72","fg":"#fff","label":"Plugin System"},
  "api": {"bg":"#7ee787","fg":"#000","label":"API & SDK"},
  "ext": {"bg":"#e3b341","fg":"#000","label":"External"},
}

# Build edges
mod_ids = {m["id"] for m in MODS}
EDGES = []
for m in MODS:
  for c in m.get("conn", []):
    if c in mod_ids:
      EDGES.append({"src": m["id"], "tgt": c})

mods_json = json.dumps(MODS)
layers_json = json.dumps(LAYERS)
edges_json = json.dumps(EDGES)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WW Bridge — Architecture Explorer</title>
<script src="vendor/cytoscape.min.js"></script>
<script src="vendor/cytoscape-dagre.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif;height:100vh;overflow:hidden}}
#topbar{{background:#161b22;border-bottom:1px solid #30363d;padding:5px 10px;display:flex;align-items:center;gap:4px;flex-wrap:wrap;min-height:38px}}
#topbar .brand{{color:#58a6ff;font-weight:700;font-size:11px;margin-right:4px;white-space:nowrap}}
#topbar .tab{{background:transparent;border:1px solid #30363d;color:#8b949e;padding:2px 8px;border-radius:12px;cursor:pointer;font-size:9px;white-space:nowrap;transition:all .1s}}
#topbar .tab:hover{{background:#21262d;color:#c9d1d9}}
#topbar .tab.active{{background:#1f6feb44;border-color:#1f6feb;color:#58a6ff;font-weight:600}}
#topbar .spacer{{flex:1}}
#main{{display:flex;flex:1;overflow:hidden;height:calc(100vh - 38px)}}
#graph-panel{{flex:1;position:relative;min-width:0}}
#cy{{width:100%;height:100%}}
#side{{width:320px;background:#161b22;border-left:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}}
#side-header{{padding:8px 10px 4px;border-bottom:1px solid #21262d}}
#side-header h2{{color:#f0f6fc;font-size:12px;font-weight:600}}
#side-header .sub{{color:#8b949e;font-size:9px}}
#side-content{{flex:1;overflow-y:auto;padding:6px 10px;font-size:11px;line-height:1.5}}
#side-content .section{{margin-bottom:8px}}
#side-content .section h3{{color:#58a6ff;font-size:11px;margin-bottom:2px;font-weight:600}}
#side-content .section p{{color:#8b949e;font-size:10px;line-height:1.4}}
#side-content .card{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:8px;margin-bottom:6px}}
#side-content .card .fn{{color:#58a6ff;font-weight:600;font-size:12px;font-family:monospace}}
#side-content .card .dn{{color:#484f58;font-size:8px;font-family:monospace;margin:1px 0 2px}}
#side-content .card .ds{{color:#c9d1d9;font-size:10px;line-height:1.4}}
#side-content .card .hw{{color:#8b949e;font-size:9px;margin-top:3px;padding-top:3px;border-top:1px solid #21262d}}
#side-content .card .rl{{color:#8b949e;font-size:8px;margin-top:2px}}
#side-content .card .rl span{{color:#58a6ff}}
#tooltip{{position:absolute;background:#1c2333;border:1px solid #30363d;border-radius:6px;z-index:100;display:none;max-width:350px;pointer-events:none;box-shadow:0 8px 24px #0006;padding:6px 8px}}
#tooltip .fn{{color:#58a6ff;font-weight:600;font-size:11px;font-family:monospace}}
#tooltip .dn{{color:#484f58;font-size:8px;font-family:monospace}}
#tooltip .ds{{color:#c9d1d9;font-size:9px;margin-top:2px}}
#tooltip .cn{{color:#8b949e;font-size:8px;margin-top:1px}}
#status{{position:absolute;bottom:6px;right:6px;background:#161b22ee;border:1px solid #30363d;border-radius:4px;padding:2px 5px;font-size:7px;color:#484f58;z-index:10}}
#legend{{position:absolute;bottom:6px;left:6px;background:#161b22ee;border:1px solid #30363d;border-radius:5px;padding:4px 7px;z-index:10;max-height:130px;overflow-y:auto}}
#legend .row{{display:flex;align-items:center;gap:2px;margin:1px 0;font-size:7px;color:#8b949e}}
#legend .dot{{width:5px;height:5px;border-radius:50%;flex-shrink:0}}
#legend .tl{{color:#8b949e;font-weight:600;margin-bottom:1px;font-size:7px}}
@media(max-width:700px){{#side{{display:none}}}}
</style>
</head>
<body>
<div id="topbar">
<span class="brand">&#9889; WW</span>
<button class="tab active" data-view="intro">Intro</button>
<button class="tab" data-view="venn">Venn</button>
<button class="tab" data-view="flow">Flow</button>
<button class="tab" data-view="layers">Layers</button>
<button class="tab" data-view="hubs">Hubs</button>
<button class="tab" data-view="grid">Grid</button>
<button class="tab" data-view="agents">Agents</button>
<button class="tab" data-view="tree">Tree</button>
<button class="tab" data-view="radial">Radial</button>
<span class="spacer"></span>
</div>
<div id="main">
<div id="graph-panel"><div id="cy"></div><div id="tooltip"></div><div id="status">loading...</div><div id="legend"></div></div>
<div id="side"><div id="side-header"><h2 id="st">WW Bridge</h2><div class="sub" id="ss">Click a module</div></div><div id="sc"><div class="section" style="padding:10px"><p>Select a view above to explore the architecture. Click any node for details.</p></div></div></div>
</div>
<script>
var MODS = {mods_json};
var LAYERS = {layers_json};
var EDGES = {edges_json};
var MOD_MAP = {{}};
for(var i=0;i<MODS.length;i++){{MOD_MAP[MODS[i].id]=MODS[i];}}

function label(m){{return m.file+'\\n'+m.dir+'\\n'+m.desc;}}
function lc(m){{return LAYERS[m.layer]||{{bg:'#888',fg:'#fff',label:'Other'}};}}
function ns(fs){{return {{'font-size':fs||10,'text-wrap':'wrap','text-max-width':170,'text-valign':'center','text-halign':'center','line-height':1.2,'min-zoomed-font-size':5,'font-family':'system-ui,sans-serif'}};}}

var CY=null;
function safeLayout(opts){{
  var names=[opts.name||'dagre','dagre','breadthfirst','cose','concentric','circle','grid','random'];
  for(var i=0;i<names.length;i++){{try{{return CY.layout(Object.assign({{}},opts,{{name:names[i]}})).run();}}catch(e){{}}}}
}}
function status(s){{document.getElementById('status').textContent=s;}}
function buildEls(ids,ues){{
  var s={{}},nodes=[],edges2=[];
  for(var i=0;i<ids.length;i++){{s[ids[i]]=true;}}
  for(var i=0;i<ids.length;i++){{
    var m=MOD_MAP[ids[i]];if(!m)continue;
    var l=lc(m);
    nodes.push({{data:{{id:m.id,label:label(m),file:m.file,dir:m.dir,desc:m.desc,how:m.how,layer:m.layer,lb:l.label,bg:l.bg,fg:l.fg,conn:m.conn}}}});
  }}
  var el=ues||EDGES;
  for(var i=0;i<el.length;i++){{if(s[el[i].src]&&s[el[i].tgt])edges2.push({{data:{{source:el[i].src,target:el[i].tgt}}}});}}
  return {{nodes:nodes,edges:edges2}};
}}

function baseStyle(){{
  CY.style().reset()
    .selector('node').style(Object.assign(ns(10),{{'background-color':'data(bg)','color':'data(fg)','shape':'ellipse','width':76,'height':76,'border-width':1,'border-color':'#fff3','overlay-opacity':0.15,'overlay-color':'#58a6ff'}}))
    .selector('node:selected').style({{'border-color':'#58a6ff','border-width':2,'shadow-blur':10,'shadow-color':'#58a6ff44','shadow-offset-x':0,'shadow-offset-y':0,'shadow-opacity':1}})
    .selector('edge').style({{'width':0.7,'line-color':'#30363d','target-arrow-color':'#30363d','target-arrow-shape':'triangle-backcurve','arrow-scale':0.5,'curve-style':'unbundled-bezier','opacity':0.45}})
    .selector('edge:selected').style({{'width':1.5,'line-color':'#58a6ff','target-arrow-color':'#58a6ff','opacity':0.9}}).update();
}}

function showLegend(){{
  var h='<div class="tl">LAYERS</div>';
  var keys=Object.keys(LAYERS);
  for(var i=0;i<keys.length;i++){{var l=LAYERS[keys[i]];h+='<div class="row"><span class="dot" style="background:'+l.bg+'"></span>'+l.label+'</div>';}}
  document.getElementById('legend').innerHTML=h;
}}

function bindUI(){{
  CY.off();
  CY.on('mouseover','node',function(e){{
    var d=e.target.data();if(d._g)return;
    var tip=document.getElementById('tooltip');
    tip.innerHTML='<div class="fn">'+(d.file||d.id)+'</div><div class="dn">'+(d.dir||'')+'</div><div class="ds">'+(d.desc||'')+'</div><div class="cn">'+(d.conn?d.conn.length+' connections':'')+' &#183; '+(d.lb||'')+'</div>';
    tip.style.display='block';
  }});
  CY.on('mouseout','node',function(){{document.getElementById('tooltip').style.display='none';}});
  CY.on('mousemove',function(e){{
    var tip=document.getElementById('tooltip'),p=e.originalEvent||e;
    var x=p.clientX+12,y=p.clientY+12;
    if(x+350>window.innerWidth)x=p.clientX-350;
    tip.style.left=x+'px';tip.style.top=y+'px';
  }});
  CY.on('tap','node',function(e){{
    var d=e.target.data();if(d._g)return;
    var m=MOD_MAP[d.id];if(!m)return;
    var conns=[];for(var i=0;i<(m.conn||[]).length;i++){{var c=MOD_MAP[m.conn[i]];if(c)conns.push(c);}}
    document.getElementById('sc').innerHTML=
      '<div class="card"><div class="fn">'+m.file+'</div><div class="dn">'+m.dir+'</div><div class="ds">'+m.desc+'</div><div class="hw">'+m.how+'</div><div class="rl">Layer: <span>'+(LAYERS[m.layer]?LAYERS[m.layer].label:m.layer)+'</span>'+(conns.length?' &#183; <span>'+conns.length+' connections</span>':'')+'</div></div>';
  }});
}}

var AE=[['communicator','overseer'],['communicator','coder'],['communicator','researcher'],['communicator','tester'],['communicator','security'],['communicator','architect'],['overseer','coder'],['overseer','researcher'],['overseer','tester'],['overseer','security'],['overseer','architect'],['coder','tester'],['researcher','architect'],['researcher','coder'],['tester','security'],['architect','coder'],['coder','overseer'],['researcher','overseer'],['tester','overseer'],['security','overseer'],['architect','overseer']];
var LO=['entry','ui','orchest','agent','tool','memory','bridge','plugin','api','ext'];

// INTRO
function viewIntro(){{
  var ids=['src_gemini_bridge','tool_executor','memory_core','web_client','commands','agent_hierarchy','config_py'];
  var el=buildEls(ids);CY.elements().remove();CY.add(el.nodes);
  var ex=[['src_gemini_bridge','tool_executor'],['src_gemini_bridge','memory_core'],['src_gemini_bridge','commands'],['src_gemini_bridge','web_client'],['src_gemini_bridge','agent_hierarchy'],['src_gemini_bridge','config_py'],['tool_executor','agent_hierarchy'],['memory_core','context_manager'],['agent_hierarchy','prompt_templates']];
  for(var i=0;i<ex.length;i++){{CY.add({{data:{{source:ex[i][0],target:ex[i][1]}}}});}}
  CY.style().reset()
    .selector('node').style(Object.assign(ns(11),{{'background-color':'data(bg)','color':'data(fg)','shape':'round-rectangle','width':'label','height':'label','padding':10,'border-width':1,'border-color':'data(bg)','border-opacity':0.5,'overlay-opacity':0.15,'overlay-color':'#58a6ff'}}))
    .selector('edge').style({{'width':0.9,'line-color':'#58a6ff','target-arrow-color':'#58a6ff','target-arrow-shape':'triangle-backcurve','arrow-scale':0.5,'curve-style':'unbundled-bezier','opacity':0.5}}).update();
  safeLayout({{name:'dagre','rank-dir':'LR','node-sep':50,'rank-sep':70,fit:true,padding:60}});
  document.getElementById('st').textContent='Intro';document.getElementById('ss').textContent='7 core modules';
  document.getElementById('sc').innerHTML='<div class="section"><h3>WW Bridge</h3><p>Python CLI harness for Gemini-powered multi-agent coding. 35+ modules, 254 tests.</p></div><div class="section"><h3>Views</h3><p><b>Venn</b> - semantic groups<br><b>Flow</b> - data pipeline<br><b>Layers</b> - 10 layers<br><b>Hubs</b> - deps<br><b>Grid</b> - distribution<br><b>Agents</b> - hierarchy<br><b>Tree</b> - modules<br><b>Radial</b> - radial</p></div>';
  status('7M | 9E');showLegend();bindUI();
}}

// VENN
function viewVenn(){{
  var ids=[];for(var i=0;i<MODS.length;i++)ids.push(MODS[i].id);
  var el=buildEls(ids);CY.elements().remove();CY.add(el.nodes);CY.add(el.edges);
  CY.style().reset()
    .selector('node').style(Object.assign(ns(9),{{'background-color':'data(bg)','color':'data(fg)','shape':'ellipse','width':68,'height':68,'border-width':2,'border-color':'#fff3','border-opacity':0.4,'overlay-opacity':0.15,'overlay-color':'#58a6ff'}}))
    .selector('edge').style({{'width':0.3,'line-color':'#30363d','target-arrow-shape':'triangle-backcurve','arrow-scale':0.2,'curve-style':'haystack','haystack-radius':0.5,'opacity':0.18}}).update();
  safeLayout({{name:'cose-bilkent',fit:true,padding:80,'node-repulsion':8000,'ideal-edge-length':85,gravity:0.25,'num-iter':600}});
  document.getElementById('st').textContent='Venn';document.getElementById('ss').textContent='Semantic groups';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Venn Groups</h3><p>Modules colored by layer. Cose-bilkent layout reveals natural clusters.</p></div>';
  status(MODS.length+'M | '+EDGES.length+'E');showLegend();bindUI();
}}

// FLOW
function viewFlow(){{
  var ids=['gemini_bridge_py','src_gemini_bridge','context_manager','memory_core','smart_context','web_client','tool_executor','tool_registry','system_tools','permissions','diff_engine','checkpoint','telemetry','commands','bridge_context','validation_utils'];
  var el=buildEls(ids);CY.elements().remove();CY.add(el.nodes);CY.add(el.edges);
  baseStyle();
  safeLayout({{name:'dagre','rank-dir':'LR','node-sep':35,'rank-sep':55,fit:true,padding:60}});
  document.getElementById('st').textContent='Flow';document.getElementById('ss').textContent='Data pipeline';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Data Flow</h3><p>Input -> REPL -> Context+Memory -> Gemini -> Parse -> Execute -> Log -> Respond</p></div>';
  status('16M');showLegend();bindUI();
}}

// LAYERS
function viewLayers(){{
  var items=[{{id:'entry',label:'Entry Points',c:2,bg:'#58a6ff'}},{{id:'ui',label:'UI & Shell',c:4,bg:'#3fb950'}},{{id:'orchest',label:'Orchestration',c:4,bg:'#d29922'}},{{id:'agent',label:'Agent System',c:3,bg:'#a371f7'}},{{id:'tool',label:'Tool Execution',c:4,bg:'#f78166'}},{{id:'memory',label:'Memory & Data',c:5,bg:'#db6d28'}},{{id:'bridge',label:'Abstractions',c:5,bg:'#56d4dd'}},{{id:'plugin',label:'Plugins',c:1,bg:'#ff7b72'}},{{id:'api',label:'API & SDK',c:4,bg:'#7ee787'}},{{id:'ext',label:'External',c:3,bg:'#e3b341'}}];
  var les=[['entry','ui','renders'],['entry','orchest','configures'],['entry','agent','delegates'],['orchest','agent','directs'],['agent','tool','executes'],['tool','memory','persists'],['agent','memory','reads'],['bridge','agent','abstracts'],['bridge','tool','wraps'],['bridge','plugin','manages'],['plugin','tool','hooks'],['api','memory','queries'],['api','ext','exposes']];
  CY.elements().remove();
  for(var i=0;i<items.length;i++){{CY.add({{data:{{id:items[i].id,label:items[i].label+' ('+items[i].c+')',bg:items[i].bg,count:items[i].c,_g:true}}}});}}
  for(var i=0;i<les.length;i++){{CY.add({{data:{{source:les[i][0],target:les[i][1],lb:les[i][2]}}}});}}
  CY.style().reset()
    .selector('node').style({{'background-color':'data(bg)','color':'#fff','shape':'round-rectangle','width':function(n){{return 55+n.data('count')*18;}},'height':40,'font-size':11,'font-weight':600,'text-valign':'center','text-halign':'center','border-width':1,'border-color':'#fff2','min-zoomed-font-size':7}})
    .selector('edge').style({{'width':0.7,'line-color':'#30363d','target-arrow-color':'#30363d','target-arrow-shape':'triangle-backcurve','arrow-scale':0.4,'curve-style':'unbundled-bezier','opacity':0.4,'label':'data(lb)','font-size':6,'color':'#484f58','text-background-color':'#0d1117','text-background-opacity':0.7,'text-background-padding':2}}).update();
  safeLayout({{name:'dagre','rank-dir':'TB','node-sep':40,'rank-sep':55,fit:true,padding:70}});
  document.getElementById('st').textContent='Layers';document.getElementById('ss').textContent='10 architectural layers';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Layer Architecture</h3><p>10 layers, top-to-bottom.</p></div>';
  status('10L | 13E');showLegend();
  CY.on('tap','node',function(e){{
    var d=e.target.data();if(!d._g)return;
    var h='<div class="section"><h3>'+d.label+'</h3></div>';
    for(var i=0;i<MODS.length;i++){{var m=MODS[i];if(m.layer===d.id||(d.id==='ext'&&m.layer==='ext')){{h+='<div class="card"><div class="fn">'+m.file+'</div><div class="dn">'+m.dir+'</div><div class="ds">'+m.desc+'</div></div>';}}}}
    document.getElementById('sc').innerHTML=h;
  }});
}}

// HUBS
function viewHubs(){{
  var ids=[];for(var i=0;i<MODS.length;i++)ids.push(MODS[i].id);
  var el=buildEls(ids);CY.elements().remove();CY.add(el.nodes);CY.add(el.edges);
  baseStyle();
  safeLayout({{name:'concentric',concentric:function(n){{return n.connectedEdges().length;}},'level-width':function(){{return 2;}},fit:true,padding:60,'min-node-spacing':35}});
  document.getElementById('st').textContent='Hubs';document.getElementById('ss').textContent='Dependency hubs';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Dependency Hubs</h3><p>High-degree modules at center. gemini_bridge.py (~24 conns) and tool_executor.py (~10) are the hubs.</p></div>';
  status(MODS.length+'M | '+EDGES.length+'E');showLegend();bindUI();
}}

// GRID
function viewGrid(){{
  var ids=[];for(var i=0;i<MODS.length;i++)ids.push(MODS[i].id);
  var el=buildEls(ids);CY.elements().remove();CY.add(el.nodes);CY.add(el.edges);
  CY.nodes().positions(function(n){{
    var m=MOD_MAP[n.id()];if(!m)return{{x:0,y:0}};
    var col=LO.indexOf(m.layer);if(col<0)col=5;
    var same=[];for(var i=0;i<MODS.length;i++){{if(MODS[i].layer===m.layer)same.push(MODS[i]);}}
    var idx=same.indexOf(m);var t=same.length;
    return{{x:col*110+55,y:t>1?(idx/(t-1))*280-140:0}};
  }});
  CY.style().reset()
    .selector('node').style(Object.assign(ns(8),{{'background-color':'data(bg)','color':'data(fg)','shape':'ellipse','width':70,'height':70,'border-width':1,'border-color':'#fff3','overlay-opacity':0.15,'overlay-color':'#58a6ff'}}))
    .selector('edge').style({{'width':0.4,'line-color':'#30363d','target-arrow-color':'#30363d','target-arrow-shape':'triangle-backcurve','arrow-scale':0.25,'curve-style':'haystack','haystack-radius':0.5,'opacity':0.15}}).update();
  try{{CY.fit(undefined,60);}}catch(e){{}}
  document.getElementById('st').textContent='Grid';document.getElementById('ss').textContent='Layer distribution';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Space Distribution</h3><p>Columns = layers (Entry left -> External right). Rows spread modules within each layer.</p></div>';
  status(MODS.length+'M | '+EDGES.length+'E');showLegend();bindUI();
}}

// AGENTS
function viewAgents(){{
  var ag=[{{id:'communicator',label:'Communicator\\nEntry / UI',bg:'#58a6ff',lv:0}},{{id:'overseer',label:'Overseer\\nTech Lead',bg:'#a371f7',lv:1}},{{id:'coder',label:'Coder\\nImplementation',bg:'#3fb950',lv:2}},{{id:'researcher',label:'Researcher\\nInvestigation',bg:'#d29922',lv:2}},{{id:'tester',label:'Tester\\nVerification',bg:'#f78166',lv:2}},{{id:'security',label:'Security\\nSafety',bg:'#ff7b72',lv:2}},{{id:'architect',label:'Architect\\nDesign',bg:'#56d4dd',lv:2}}];
  CY.elements().remove();
  for(var i=0;i<ag.length;i++){{CY.add({{data:{{id:ag[i].id,label:ag[i].label,bg:ag[i].bg,lv:ag[i].lv,_g:true}}}});}}
  for(var i=0;i<AE.length;i++){{CY.add({{data:{{source:AE[i][0],target:AE[i][1]}}}});}}
  CY.style().reset()
    .selector('node').style({{'background-color':'data(bg)','color':'#fff',
      'shape':function(n){{var l=n.data('lv');return l===0?'triangle':l===1?'diamond':'ellipse';}},
      'width':function(n){{var l=n.data('lv');return l===0?85:l===1?78:64;}},
      'height':function(n){{var l=n.data('lv');return l===0?85:l===1?78:64;}},
      'font-size':function(n){{var l=n.data('lv');return l===0?12:l===1?10:8;}},
      'font-weight':function(n){{var l=n.data('lv');return l===0?700:l===1?600:500;}},
      'text-wrap':'wrap','text-valign':'center','text-halign':'center','border-width':1,'border-color':'#fff3','min-zoomed-font-size':5}})
    .selector('edge').style({{'width':0.6,'line-color':'#30363d','target-arrow-color':'#30363d','target-arrow-shape':'triangle-backcurve','arrow-scale':0.4,'curve-style':'unbundled-bezier','opacity':0.4}}).update();
  safeLayout({{name:'breadthfirst',directed:true,fit:true,padding:70,'spacing-factor':1.6}});
  document.getElementById('st').textContent='Agents';document.getElementById('ss').textContent='3-tier hierarchy';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Agent Hierarchy</h3><p>3-tier: Communicator -> Overseer -> Specialists</p></div><div class="section"><h3>Patterns</h3><p>Communicator pass-through to ALL<br>Overseer pipelines + chains<br>Specialists call each other laterally<br>Results flow up</p></div>';
  status('7A | '+AE.length+'E');bindUI();
}}

// TREE
function viewTree(){{
  var items=[{{id:'ww',label:'WW Bridge',bg:'#58a6ff',lv:0}}];
  var grps=[{{id:'ge',label:'Entry',bg:'#58a6ff88',lv:1}},{{id:'go',label:'Orch.',bg:'#d2992288',lv:1}},{{id:'gu',label:'UI',bg:'#3fb95088',lv:1}},{{id:'ga',label:'Agent',bg:'#a371f788',lv:1}},{{id:'gt',label:'Tool',bg:'#f7816688',lv:1}},{{id:'gm',label:'Memory',bg:'#db6d2888',lv:1}},{{id:'gb',label:'Abstr.',bg:'#56d4dd88',lv:1}},{{id:'gx',label:'API+Ext',bg:'#7ee78788',lv:1}}];
  var lg={{}};lg['entry']='ge';lg['orchest']='go';lg['ui']='gu';lg['agent']='ga';lg['tool']='gt';lg['memory']='gm';lg['bridge']='gb';lg['api']='gx';lg['ext']='gx';lg['plugin']='gx';
  for(var i=0;i<grps.length;i++){{grps[i].parent='ww';items.push(grps[i]);}}
  for(var i=0;i<MODS.length;i++){{items.push({{id:MODS[i].id,label:MODS[i].file,bg:lc(MODS[i]).bg,lv:2,parent:lg[MODS[i].layer]||'gx'}});}}
  CY.elements().remove();
  for(var i=0;i<items.length;i++){{CY.add({{data:{{id:items[i].id,label:items[i].label,bg:items[i].bg,lv:items[i].lv,parent:items[i].parent||undefined,_g:true}}}});}}
  for(var i=0;i<items.length;i++){{if(items[i].parent)CY.add({{data:{{source:items[i].parent,target:items[i].id}}}});}}
  CY.style().reset()
    .selector('node[lv=0]').style({{'background-color':'data(bg)','color':'#fff','shape':'round-rectangle','width':'label','height':'label','padding':10,'font-size':14,'font-weight':700,'border-width':2,'border-color':'#58a6ff','text-wrap':'wrap','text-valign':'center','text-halign':'center'}})
    .selector('node[lv=1]').style({{'background-color':'data(bg)','color':'#fff','shape':'round-rectangle','width':'label','height':'label','padding':10,'font-size':9,'font-weight':600,'border-width':1,'border-color':'#fff2','text-wrap':'wrap','text-valign':'top','text-halign':'left','text-margin-x':3,'text-margin-y':2}})
    .selector('node[lv=2]').style({{'background-color':'data(bg)','color':'#fff','shape':'ellipse','width':48,'height':48,'font-size':6,'font-weight':400,'text-wrap':'wrap','text-valign':'center','text-halign':'center','border-width':1,'border-color':'#fff2','min-zoomed-font-size':3}})
    .selector('edge').style({{'width':0.4,'line-color':'#30363d','target-arrow-shape':'none','curve-style':'bezier','opacity':0.25}}).update();
  safeLayout({{name:'breadthfirst',directed:true,fit:true,padding:50,'spacing-factor':1.2}});
  document.getElementById('st').textContent='Tree';document.getElementById('ss').textContent='Module hierarchy';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Module Tree</h3><p>Root -> 8 groups -> 35 modules</p></div>';
  status(items.length+'N');bindUI();
}}

// RADIAL
function viewRadial(){{
  var ids=[];for(var i=0;i<MODS.length;i++)ids.push(MODS[i].id);
  var el=buildEls(ids);CY.elements().remove();CY.add(el.nodes);CY.add(el.edges);
  baseStyle();
  safeLayout({{name:'concentric',
    concentric:function(n){{var m=MOD_MAP[n.id()];return m?(10-LO.indexOf(m.layer)):0;}},
    'level-width':function(){{return 1;}},
    fit:true,padding:70,'min-node-spacing':50,'start-angle':0,sweep:Math.PI*2
  }});
  document.getElementById('st').textContent='Radial';document.getElementById('ss').textContent='Layers radiating outward';
  document.getElementById('sc').innerHTML='<div class="section"><h3>Radial Layout</h3><p>Entry at center, layers radiate outward. Each ring = one layer.</p></div>';
  status(MODS.length+'M | '+EDGES.length+'E');showLegend();bindUI();
}}

var VIEWS={{intro:viewIntro,venn:viewVenn,flow:viewFlow,layers:viewLayers,hubs:viewHubs,grid:viewGrid,agents:viewAgents,tree:viewTree,radial:viewRadial}};

function showView(name,btn){{
  if(btn){{
    var tabs=document.querySelectorAll('.tab');
    for(var i=0;i<tabs.length;i++)tabs[i].classList.remove('active');
    btn.classList.add('active');
  }}
  var fn=VIEWS[name];
  if(fn){{try{{fn();}}catch(e){{status('Error: '+e.message);}}}}
}}

document.addEventListener('DOMContentLoaded',function(){{
  try{{
    CY=cytoscape({{container:document.getElementById('cy'),style:[],elements:[],pixelRatio:window.devicePixelRatio||1}});
  }}catch(e){{status('Init failed');return;}}
  var tabs=document.querySelectorAll('.tab');
  for(var i=0;i<tabs.length;i++){{
    tabs[i].addEventListener('click',function(){{showView(this.dataset.view,this);}});
  }}
  showView('intro',tabs[0]);
  status('Ready');
}});
</script>
</body>
</html>"""

with open('docs/architecture-explorer.html', 'w') as f:
    f.write(HTML)
print(f"OK: wrote {len(HTML)} bytes, {HTML.count(chr(10))} lines")
print(f"Self-contained: {'fetch' not in HTML and 'arch_data' not in HTML}")
print(f"9 views present: {all(v in HTML for v in ['viewIntro','viewVenn','viewFlow','viewLayers','viewHubs','viewGrid','viewAgents','viewTree','viewRadial'])}")
