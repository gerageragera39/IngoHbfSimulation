import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(process.argv[2] ?? path.join(here, "Ingolstadt_Hbf.pptx"));
const { Presentation, PresentationFile } = await import(process.env.ARTIFACT_TOOL_ENTRY
  ? pathToFileURL(process.env.ARTIFACT_TOOL_ENTRY).href
  : "@oai/artifact-tool");

const W = 1280;
const H = 720;
const L = 64;
const R = 1216;
const c = {
  paper: "#F5F3EF", ink: "#18252B", muted: "#4D5C60", teal: "#0C6265", orange: "#C65C36",
  rust: "#9A4124", line: "#C8CEC9", lane: "#E9E8E1", grey: "#596664",
  mint: "#E0EEEA", pale: "#F6E6DC", white: "#FFFFFF",
};
const urls = {
  equipment: "https://www.dbinfrago.com/web/bahnhoefe/leistungen/stationsnutzung/stationshalt/stationsausstattung/Ingolstadt-Hbf-12671312",
  plan: "https://trassenfinder.de/apn/MIH",
  timetable: "https://www.bahnhof.de/downloads/schedule/Regeltafel_2993.pdf",
  repo: "https://github.com/gerageragera39/IngoHbfSimulation/tree/226917c",
  platformPhoto: "https://commons.wikimedia.org/wiki/File:Neue_Bahnsteige_Ingolstadt_Hauptbahnhof.JPG",
  platformLicense: "https://creativecommons.org/licenses/by-sa/3.0/",
  exteriorPhoto: "https://commons.wikimedia.org/wiki/File:Ingolstadt,_Hauptbahnhof_v_W,_3.jpeg",
  exteriorLicense: "https://creativecommons.org/publicdomain/zero/1.0/",
};
const show = Presentation.create({slideSize: {width: W, height: H}});
const noLine = {fill: "none", width: 0};
const px = (left, top, width, height) => ({left, top, width, height});
const stroke = (fill = c.line, width = 1) => ({style: "solid", fill, width});

function shape(s, name, geometry, position, fill = "none", line = noLine, extra = {}) {
  return s.shapes.add({name, geometry, position, fill, line, ...extra});
}
function box(s, name, x, y, w, h, fill, border = noLine) {
  return shape(s, name, "rect", px(x,y,w,h), fill, border);
}
function setText(o, copy, size, options = {}) {
  o.text = copy;
  o.text.style = {
    typeface: "Arial", fontSize: size, color: options.color ?? c.ink,
    bold: options.bold ?? false, alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "middle", autoFit: "none",
    wrap: options.wrap ?? "none", insets: options.insets ?? 0,
  };
  return o;
}
function txt(s, copy, x, y, w, h, size, options = {}) {
  const o = shape(s, options.name ?? copy.replaceAll("\n", " "), "textbox", px(x,y,w,h));
  setText(o, copy, size, options);
  if (options.link) o.hyperlink = {uri: options.link, isExternal: true};
  return o;
}
function rule(s, y, from = L, to = R, color = c.line) {
  box(s, "Horizontal rule", from, y, to-from, 1, color);
}
function vRule(s, x, from, to, color = c.line) {
  box(s, "Vertical rule", x, from, 1, to-from, color);
}
function note(s, speaker, timing, body, sources = []) {
  s.speakerNotes.text = [speaker ? `${speaker} · ${timing}` : timing, "", ...body,
    ...(sources.length ? ["", "Sources", ...sources] : [])].join("\n");
}
function page(n, title, sub = "") {
  const s = show.slides.add();
  s.background.fill = c.paper;
  box(s, "Title rule", L, 45, 36, 4, c.orange);
  txt(s, title, L, 62, R-L, 65, 49, {bold:true});
  if (sub) txt(s, sub, L, 133, R-L, 31, 23, {color:c.muted});
  rule(s, 657);
  txt(s, "Ingolstadt Hbf", L, 670, 260, 23, 14, {color:c.muted});
  txt(s, String(n).padStart(2,"0"), R-52, 670, 52, 23, 15, {bold:true, color:c.teal, align:"right"});
  return s;
}
async function asset(name) {
  return fs.readFile(path.join(here, "assets", name));
}
function img(s, data, mime, alt, x, y, w, h, fit = "contain") {
  return s.images.add({blob: data, contentType:mime, alt, fit, position:px(x,y,w,h)});
}
function loadCsv(data) {
  const [fields, ...rows] = data.toString("utf8").trim().split(/\r?\n/).map(line => line.split(","));
  return rows.map(row => Object.fromEntries(fields.map((field, i) => [field, row[i]])));
}
function caption(s, copy, x, y, w, link) {
  return txt(s, copy, x, y, w, 22, 15, {color:c.muted, link});
}

const [platformPhoto, exteriorPhoto, plan, matrixFile, dimensionFile] = await Promise.all([
  asset("station_platforms.jpg"), asset("station_exterior.jpeg"), asset("db-passenger-plan.png"),
  asset("platform_matrix.csv"), asset("platform_dimensions.csv"),
]);
const dimensions = loadCsv(dimensionFile).filter(d => d.in_model === "1");
const matrix = loadCsv(matrixFile);

// 1 · Cover
{
  const s = show.slides.add();
  s.background.fill = c.paper;
  box(s, "Title rule", L, 84, 58, 5, c.orange);
  txt(s, "SIMULATIONS COURSE", L, 110, 486, 26, 19, {bold:true, color:c.teal});
  txt(s, "Railway platform", L, 160, 525, 72, 58, {bold:true});
  txt(s, "assignment", L, 226, 525, 72, 58, {bold:true});
  txt(s, "simulation", L, 292, 525, 72, 58, {bold:true});
  txt(s, "A case study of Ingolstadt Hbf", L, 390, 491, 42, 29, {color:c.teal});
  rule(s, 475, L, 510);
  txt(s, "Herman Dihtenko, Liliya Radvar", L, 499, 491, 28, 21);
  txt(s, "and Mohammad Gaber", L, 529, 491, 28, 21);
  txt(s, "27 November 2026", L, 589, 491, 29, 21, {bold:true});
  img(s, platformPhoto, "image/jpeg", "View of platforms 2 and 3 at Ingolstadt Hauptbahnhof", 578, 81, 638, 512, "cover");
  caption(s, "Ingolstadt Hbf, 2013. Thesenbauer, CC BY-SA 3.0 (crop).", 578, 603, 638, urls.platformPhoto);
  note(s, "Herman Dihtenko", "0:25", [
    "When an arriving train is late, its assigned platform can still be occupied when the next train needs it. We are studying whether a different platform assignment can reduce the extra delay at Ingolstadt Hbf.",
    "We will define the problem, compare three dispatching policies, and use event-driven process chains to explain the conceptual process.",
  ], [`Photo: Thesenbauer, 15 June 2013, cropped. ${urls.platformPhoto}`, urls.platformLicense]);
}

// 2 · Problem statement and occupancy example
{
  const s = page(2, "A late train can delay the next one", "An incoming delay can shift platform occupancy into the next train’s slot.");
  txt(s, "Can reassignment\nreduce secondary\ndelay with the same\nfour tracks?", L, 213, 425, 201, 39, {bold:true,color:c.teal});
  txt(s, "Incoming delay builds up before arrival.\nSecondary delay is the extra departure\ndelay caused within the station.", L, 465, 432, 98, 23);
  const x = 577, w = 639, step = w/8;
  const t = k => x + step*k;
  txt(s, "Following train is ready", t(4)-121, 215, 242, 27, 18, {align:"center",bold:true});
  txt(s, "Planned\ntrack", 476, 306, 84, 55, 17, {align:"right",bold:true});
  txt(s, "Eligible\nalternate", 467, 397, 93, 55, 17, {align:"right",bold:true});
  box(s,"Planned track lane",x,307,w,52,c.lane);
  box(s,"Alternate track lane",x,397,w,52,c.lane);
  box(s,"Earlier train's extended occupancy",t(1),307,step*5,52,c.teal);
  txt(s,"Late train still on track",t(1),307,step*3,52,19,{align:"center",bold:true,color:c.white});
  box(s,"Free alternate during conflict",t(4),397,step*2,52,c.mint,stroke(c.teal));
  txt(s,"Free",t(4),397,step*2,52,19,{align:"center",bold:true,color:c.teal});
  for(let y=252;y<460;y+=12) box(s,"Readiness marker",t(4)-1,y,2,6,c.ink);
  for(let y=252;y<460;y+=12) box(s,"Clearance marker",t(6)-1,y,2,6,c.rust);
  box(s,"Waiting interval",t(4),268,step*2,5,c.orange);
  txt(s,"Extra waiting",t(4),274,step*2,25,18,{align:"center",bold:true,color:c.rust});
  txt(s,"Track clears",t(6)+11,223,140,24,17,{bold:true,color:c.rust});
  rule(s, 492, x, x+w, c.grey);
  txt(s,"Time",x,509,w,24,16,{color:c.muted,align:"right"});
  caption(s,"Illustrative occupancy",x,546,w);
  note(s, "Herman Dihtenko", "0:55", [
    "At the point marked by the first vertical line, the following train is ready to enter. The earlier train still occupies its planned track. Under fixed assignments the following train must wait for that track. If the alternate is compatible and free, reassignment may avoid the wait, but it uses capacity another train may need.",
    "For the experiment we measure secondary delay at departure. Compare actual departure with the later of scheduled departure and readiness plus minimum dwell, with a floor of zero. That separates extra congestion delay from the incoming lateness the station cannot recover.",
  ], [urls.repo]);
}

// 3 · Real station evidence and boundaries
{
  const s = page(3, "One station, four platform tracks", "RB16, RE1 and ICE services in both directions at Ingolstadt Hbf");
  img(s, plan, "image/png", "DB InfraGO passenger area plan showing tracks 2, 3, 4 and 5", L, 192, 755, 394.47);
  box(s,"Plan border",L,192,755,394.47,"none",stroke(c.line));
  // Bracket just to the right of the printed track numbers, outside their text.
  const bracketX = L + 706*755/890;
  const bracketTop = 192 + 199*755/890;
  const bracketBottom = 192 + 349*755/890;
  box(s,"Modeled track bracket",bracketX,bracketTop,2,bracketBottom-bracketTop,c.teal);
  box(s,"Bracket cap",bracketX-8,bracketTop,10,2,c.teal);
  box(s,"Bracket cap",bracketX-8,bracketBottom-2,10,2,c.teal);
  caption(s,"DB InfraGO AG, service facilities plan, 19 Oct 2026 (crop). Teal bracket marks tracks 2–5.",L,595,765,urls.plan);
  img(s, exteriorPhoto, "image/jpeg", "Ingolstadt Hauptbahnhof exterior from the west, 2022", 857, 192, 359, 119.67);
  caption(s,"Renardo la vulpo, 2022, CC0.",857,318,359,urls.exteriorPhoto);
  rule(s,355,857,R);
  const dimensionsSummary = `Tracks 2–3: ${dimensions[0].net_construction_length_m} m\nTracks 4–5: ${dimensions[2].net_construction_length_m} m\nPlatform edges: ${dimensions[0].platform_height_cm} cm high`;
  txt(s,dimensionsSummary,857,365,359,93,24,{bold:true,color:c.teal});
  caption(s,"DB InfraGO net construction lengths",857,460,359,urls.equipment);
  txt(s,"Model scope",857,497,359,29,20,{bold:true});
  txt(s,"Arrival, waiting, allocation, dwell\nand departure. Entry and exit\ncapacity are planned extensions.",857,530,359,79,21);
  note(s, "Herman Dihtenko", "1:00", [
    "The study focuses on the four long passenger tracks numbered two through five. The plan crop locates them in the station. DB InfraGO lists the platform edges at 76 centimetres. The lengths are the published net construction lengths. Guaranteed usable train lengths would require a separate check.",
    "In the model, a train becomes ready, waits as needed, occupies an eligible track, dwells and departs. Detailed signalling, the wider network, freight operations and passenger movement are outside the scope. A future timetable-based experiment should include every passenger service that shares these four tracks as background demand.",
    "Handoff to Liliya for the eligibility and dispatch rules.",
  ], [urls.equipment, `DB InfraGO AG, service facilities plan dated 19 October 2026. ${urls.plan}`,
    `Exterior photo: Renardo la vulpo, 29 May 2022. ${urls.exteriorPhoto}`, urls.exteriorLicense]);
}

// 4 · Native PowerPoint table with unchanged eligibility and planned tracks
{
  const s = page(4, "Simplified platform eligibility", "Six service groups share four modeled tracks.");
  const values = [
    ["Service group","Track 2","Track 3","Track 4","Track 5","Planned track"],
    ...matrix.map(row => [
      row.train_group.replace("_S"," southbound").replace("_N"," northbound"),
      ...[2,3,4,5].map(n => row[`gleis_${n}`] === "1" ? "●" : "–"),
      row.representative_planned_track,
    ]),
  ];
  const tab = s.tables.add({
    rows: values.length, columns: values[0].length, left:L, top:192, width:754, height:350,
    columnWidths:[195,101,101,101,101,155], values,
  });
  tab.styleOptions = {headerRow:false, totalRow:false, firstColumn:false, lastColumn:false, bandedRows:false, bandedColumns:false};
  tab.borders.assign(stroke(c.paper,1));
  for(let r=0;r<values.length;r++){
    tab.rows[r].height = 50;
    for(let k=0;k<values[r].length;k++){
      const cell = tab.getCell(r,k);
      const eligible = values[r][k] === "●";
      cell.fill = r === 0 ? c.teal : eligible ? c.mint : k === 5 ? "#E8EBE5" : "#EFEEE9";
      cell.text.style = {
        typeface:"Arial", fontSize:r === 0 ? 16 : eligible ? 20 : 19,
        color:r === 0 ? c.white : eligible || k === 5 ? c.teal : c.ink,
        alignment:k ? "center" : "left", verticalAlignment:"middle", bold:r === 0 || k === 5, wrap:"none",
      };
    }
  }
  txt(s,"●  Eligible",L,558,146,30,18,{bold:true,color:c.teal});
  txt(s,"–  Excluded in model",210,558,248,30,18);
  txt(s,"Planned tracks are synthetic baseline inputs.",L,597,754,28,18,{color:c.muted});
  vRule(s,851,192,625);
  txt(s,"Dispatch constraints",881,194,335,38,24,{bold:true,color:c.teal});
  txt(s,"One train per track\nAssign only to eligible tracks\nRespect dwell and departure times",881,247,335,107,20);
  rule(s,380,881,R);
  txt(s,"Published timetable example",881,399,335,32,20,{bold:true});
  txt(s,"ICE 822 at 05:26 lists track 4\non Saturdays and track 5 on\nweekdays, with date restrictions.",881,442,335,88,19);
  caption(s,"DB departure timetable, PDF p. 3",881,530,335,urls.timetable);
  txt(s,"Operational routing requires\nseparate checks.",881,569,335,55,17,{color:c.muted});
  note(s, "Liliya Radvar", "0:50", [
    "The filled dots show which tracks the simulation allows for each service and direction. The planned track values are synthetic inputs for the fixed baseline. Southbound ICE has a single eligible track in this model.",
    "The timetable shows ICE 822 at 05:26 on track 4 on certain Saturdays and track 5 on certain weekdays. That demonstrates scheduled variation. It gives no live routing permission. The southbound RE1 track 5 assumption is informed by an older timetable observation and needs validation before a real operating-date study.",
  ], [`DB departure timetable valid from 14 December 2025, PDF page 3. ${urls.timetable}`, urls.equipment, `Model matrix: route_catalog.csv at ${urls.repo}`]);
}

// 5 · Native, scaled occupancy timelines
{
  const s = page(5, "Three dispatch strategies", "RB16 arrives at 10:00. Track 2 frees at 10:01. The ICE is expected at 10:02 and can use only track 3.");
  const x=436, dx=80, right=x+8*dx;
  const at = t => x + t*dx;
  txt(s,"TRACK OCCUPANCY",x,180,350,25,15,{bold:true,color:c.teal});
  txt(s,"TOTAL WAIT",1090,180,126,25,15,{bold:true,color:c.teal,align:"center"});
  const schedules = [
    {name:"Fixed", desc:"Wait for the\nplanned track.", wait:1, lanes:[[[0,1,"Busy"],[1,7,"RB16"]],[[2,4,"ICE"]]]},
    {name:"Greedy", desc:"Prefer the planned track.\nUse a free eligible alternate.", wait:4, lanes:[[[0,1,"Busy"]],[[0,6,"RB16"],[6,8,"ICE"]]]},
    {name:"Lookahead", desc:"Forecast the next 60 min.\nAllow a short wait.", wait:1, lanes:[[[0,1,"Busy"],[1,7,"RB16"]],[[2,4,"ICE"]]]},
  ];
  const fills = {Busy:c.grey, RB16:c.teal, ICE:c.rust};
  schedules.forEach((p,i) => {
    const y=216+i*114;
    rule(s,y,L,R);
    txt(s,p.name,L,y+12,253,33,26,{bold:true});
    if(i===2) txt(s,"PLANNED",218,y+15,118,25,14,{bold:true,color:c.rust});
    txt(s,p.desc,L,y+48,277,52,17,{color:c.muted});
    p.lanes.forEach((lane,k) => {
      const yy=y+16+k*40;
      txt(s,`Track ${k+2}`,354,yy,69,33,16,{align:"right"});
      box(s,`Track ${k+2} lane`,x,yy,right-x,33,c.lane);
      for(let j=1;j<8;j++) vRule(s,at(j),yy,yy+33,c.line);
      lane.forEach(([start,end,label]) => {
        box(s,`${label} occupies track ${k+2}`,at(start),yy,(end-start)*dx,33,fills[label]);
        txt(s,label,at(start),yy,(end-start)*dx,33,17,{bold:true,align:"center",color:c.white});
      });
    });
    for(let j=0;j<9;j++) box(s,"ICE readiness marker",at(2)-1,y+13+9*j,2,4,c.orange);
    txt(s,`${p.wait} min`,1090,y+20,126,56,31,{bold:true,align:"center",color:i===1?c.rust:c.teal});
  });
  rule(s,558,L,R);
  for(let t=0;t<=8;t++) txt(s,`10:0${t}`,at(t)-26,570,52,23,14,{align:"center",color:t===2?c.rust:c.muted,bold:t===2});
  caption(s,"Hand-worked example. RB16 occupies a track for 6 min and the ICE for 2 min.",L,616,R-L);
  note(s, "Liliya Radvar", "1:15", [
    "Each row starts with the same conditions. The RB16 is ready at 10:00 and its planned track 2 becomes free at 10:01. The ICE is expected at 10:02 and can use only track 3. RB16 needs six minutes on a track and ICE needs two.",
    "Fixed holds RB16 for one minute, then both trains can enter their respective tracks. Greedy assigns RB16 to free track 3 immediately. That blocks the ICE until 10:06, so total waiting grows to four minutes. Lookahead would preserve track 3 by holding RB16 for one minute. Here it happens to make the same choice as Fixed.",
    "Fixed and Greedy are implemented. Greedy waits when no permitted track is available. The planned Lookahead policy would consider expected arrivals and release times over a rolling 60-minute horizon using information available at the decision. These numbers are waiting times from one constructed example. The experiment will compare secondary departure delays across many scenarios.",
  ], [`Policy status: ${urls.repo}`, "Occupancy timeline reconstructed from the supplied strategy comparison."]);
}

// EPC drawing helpers. Each event, function and connector remains editable.
function epcNode(s, type, copy, x, y, w=256, h=76, accent=false) {
  const fill = type === "event" ? (accent ? c.teal : c.mint) : (accent ? c.pale : c.white);
  const line = type === "event" ? stroke(c.teal,1.35) : stroke(accent?c.rust:c.grey,1.35);
  const geometry = type === "event" ? "hexagon" : "roundRect";
  const node = shape(s,`${type}: ${copy.replaceAll("\n"," ")}`,geometry,px(x,y,w,h),fill,line);
  setText(node,copy,20,{bold:true,align:"center",color:type === "event" && accent ? c.white : c.ink});
  return node;
}
function xor(s, label, x,y) {
  const o=shape(s,label,"ellipse",px(x,y,42,42),c.paper,stroke(c.teal,1.6));
  setText(o,"XOR",12,{bold:true,align:"center",color:c.teal});
  return o;
}
const opposite = {left:"right", right:"left", top:"bottom", bottom:"top"};
function anchor(o,side) {
  const {left,top,width,height}=o.position;
  return {
    left:[left,top+height/2], right:[left+width,top+height/2],
    top:[left+width/2,top], bottom:[left+width/2,top+height],
  }[side];
}
function connect(s,a,b,side) {
  route(s,"Process flow",[anchor(a,side),anchor(b,opposite[side])]);
}
function route(s,name,points,color=c.grey) {
  const [bx,by]=points.at(-1), [ax,ay]=points.at(-2);
  const vx=Math.sign(bx-ax), vy=Math.sign(by-ay);
  const base=[bx-9*vx,by-9*vy];
  const shaft=[...points.slice(0,-1),[base[0]+vx,base[1]+vy]];
  for(let i=1;i<shaft.length;i++){
    const [sx,sy]=shaft[i-1], [ex,ey]=shaft[i], thickness=1.55;
    box(s,name,Math.min(sx,ex)-thickness/2,Math.min(sy,ey)-thickness/2,
      Math.abs(ex-sx)+thickness,Math.abs(ey-sy)+thickness,color);
  }
  const rotation=vx>0?90:vx<0?270:vy>0?180:0;
  const tip=shape(s,`${name} arrow`,"triangle",px(bx-4.5*vx-4.5,by-4.5*vy-4.5,9,9),color);
  tip.rotation=rotation;
}
function serpentine(s,nodes) {
  const columns=[64,360,656,952], rows=[198,326,454];
  const placements=[[0,0],[1,0],[2,0],[3,0],[3,1],[2,1],[1,1],[0,1],[0,2],[1,2],[2,2]];
  const o=nodes.map(([copy,accent],i) => {
    const [col,row]=placements[i];
    return epcNode(s,i%2?"function":"event",copy,columns[col],rows[row],264,76,accent);
  });
  for(let i=1;i<o.length;i++){
    const [a,b]=placements[i-1], [x,y]=placements[i];
    connect(s,o[i-1],o[i],b!==y?"bottom":x>a?"right":"left");
  }
}
function epcLegend(s,captionText,withXor=false) {
  rule(s,572);
  shape(s,"Event key","hexagon",px(L,597,31,22),c.mint,stroke(c.teal));
  txt(s,"Event",104,597,83,22,16,{color:c.muted});
  shape(s,"Function key","roundRect",px(176,597,31,22),c.white,stroke(c.grey));
  txt(s,"Function",216,597,94,22,16,{color:c.muted});
  if(withXor){
    shape(s,"Connector key","ellipse",px(304,597,22,22),c.paper,stroke(c.teal));
    txt(s,"Exclusive connector",333,597,170,22,16,{color:c.muted});
  }
  txt(s,captionText,withXor?515:323,597,withXor?701:893,22,16,{color:c.muted,align:"right"});
}

// 6 · Overall station EPC
{
  const s=page(6,"EPC 1  Overall station process","The event-driven process chain follows a train from scheduled arrival to resource release.");
  serpentine(s,[
    ["Train arrival\nscheduled",true], ["Apply incoming delay\nand advance to readiness"], ["Train ready for\nstation entry"], ["Allocate platform\n(EPC 2)"],
    ["Platform reserved"], ["Authorize entry\nand enter station",true], ["Train at platform"], ["Serve passengers\nand meet minimum dwell"],
    ["Passenger service\ncompleted"], ["Manage departure\n(EPC 3)"], ["Train departed and\nresources released",true],
  ]);
  epcLegend(s,"Conceptual target process. Entry-route authorization is planned.");
  note(s,"Liliya Radvar","0:35",[
    "An EPC alternates events, which describe states, and functions, which describe actions. Start at the upper left and follow the arrows. After incoming delay determines when a train becomes ready, the model allocates a track. It then enters, serves passengers and departs. The entry authorization step represents planned infrastructure constraints.",
    "Handoff to Mohammad for the two subprocesses and the experiment.",
  ],["Conceptual EPC based on the supplied IRIS build specification."]);
}

// 7 · Allocation EPC and explicit return to the XOR join
{
  const s=page(7,"EPC 2  Platform assignment","The policy decides whether to reserve an eligible track now or reevaluate later.");
  const a=epcNode(s,"event","Train ready\nfor allocation",80,183,240,66,true);
  const b=xor(s,"XOR join: arrival or reevaluation",179,272);
  const d=epcNode(s,"function","Evaluate policy and\nfind free eligible tracks",80,337,240,70);
  const e=xor(s,"XOR split: reserve or defer",179,430);
  connect(s,a,b,"bottom"); connect(s,b,d,"bottom"); connect(s,d,e,"bottom");
  txt(s,"Lookahead can defer assignment\neven when an eligible track is free.",414,195,760,74,27,{bold:true,color:c.teal});
  const f=epcNode(s,"event","Suitable track\nselected now",407,306,240,68);
  const g=epcNode(s,"function","Reserve selected\ntrack",687,306,220,68);
  const h=epcNode(s,"event","Platform reserved",947,306,269,68,true);
  const j=epcNode(s,"event","Allocation deferred",407,456,240,68);
  const k=epcNode(s,"function","Wait for a change or\nreevaluation time",687,456,220,68,true);
  const m=epcNode(s,"event","Allocation can\nbe reevaluated",947,456,269,68);
  route(s,"Select now branch",[[221,451],[363,451],[363,340],[407,340]]);
  route(s,"Deferred branch",[[221,451],[363,451],[363,490],[407,490]]);
  connect(s,f,g,"right"); connect(s,g,h,"right");
  connect(s,j,k,"right"); connect(s,k,m,"right");
  route(s,"Return to XOR join",[[1081.5,524],[1081.5,551],[57,551],[57,293],[179,293]],c.rust);
  epcLegend(s,"Reevaluation returns to the same policy decision.",true);
  note(s,"Mohammad Gaber","0:55",[
    "A new train and a train returning from the waiting loop meet at the first exclusive connector. The policy evaluates whether to reserve now. A candidate track must be eligible, free and unreserved. Selection leads to reservation and ends the subprocess.",
    "The deferred branch covers two cases. The required track may be unavailable, or Lookahead may deliberately hold the train while a compatible track is free. Reevaluation can follow a track release, a reopening, changed arrival expectations, or a planned check time. The return path goes back through the join to the same evaluation.",
  ],["Conceptual EPC based on the supplied IRIS build specification."]);
}

// 8 · Departure EPC and distinct release events
{
  const s=page(8,"EPC 3  Train departure","The platform track and exit route become available at separate clearance events.");
  serpentine(s,[
    ["Passenger service\ncompleted",true], ["Wait until scheduled\ndeparture if needed"], ["Train eligible\nfor departure"], ["Request and wait\nfor exit route",true],
    ["Exit route reserved"], ["Depart and clear\nplatform track"], ["Platform track clear"], ["Release platform and\nfinish exit movement"],
    ["Exit route clear"], ["Release exit route and\nrecord completion"], ["Train departed and\nresources released",true],
  ]);
  epcLegend(s,"Conceptual target process including planned exit-route constraints.");
  note(s,"Mohammad Gaber","0:45",[
    "Departure starts only once minimum dwell has finished and the scheduled departure time has arrived. Under the planned extension, a train then requests an exit route and can stay on the platform while it waits for clearance.",
    "Once the train has cleared the platform track, another eligible train can use that track. The exit route remains reserved until that movement clears. Keeping the two releases separate lets the model represent a bottleneck at the exit.",
  ],["Conceptual EPC based on the supplied IRIS build specification."]);
}

// 9 · Experiment design and conclusion
{
  const s=page(9,"Experiment design","Each policy faces the same timetable inputs and incoming delays within each paired run.");
  const columns=[
    {x:L,w:344,title:"Scenarios",items:["Normal operation","Peak traffic","Larger incoming delays","Temporary track closure"]},
    {x:455,w:335,title:"Measures",items:["Mean secondary delay","Waiting time","Track utilization","Reassignments and throughput"]},
    {x:846,w:370,title:"Prototype and extensions",items:["Fixed and Greedy implemented","Paired synthetic runs available","Lookahead, timetable integration\nand route constraints planned"]},
  ];
  for(const col of columns){
    rule(s,211,col.x,col.x+col.w,c.teal);
    txt(s,col.title,col.x,228,col.w,40,25,{bold:true,color:c.teal});
    col.items.forEach((item,i) => txt(s,item,col.x,282+i*44,col.w,item.includes("\n")?68:36,22));
  }
  box(s,"Conclusion band",L,501,R-L,112,c.teal);
  txt(s,"The comparison tests when reassignment helps\nand how route capacity changes the outcome.",88,508,1104,96,34,{bold:true,color:c.white});
  note(s,"Mohammad Gaber","0:50",[
    "We compare policies on identical inputs in each scenario, then repeat across many incoming-delay realizations. Start with normal operation, then increase traffic, increase lateness, or remove one track temporarily. We track mean secondary delay alongside waiting, utilization, platform changes and throughput. These measures help identify what a policy improves and what it trades off.",
    "The repository already contains paired synthetic runs for Fixed and Greedy. Timetable integration, the Lookahead policy and route capacity are extensions. The goal is to identify the conditions in which flexibility helps and the constraints that limit it.",
  ], [urls.repo]);
}

// 10 · Linked reference labels and full source URLs in notes
{
  const s=page(10,"References");
  function ref(x,y,w,title,detail,link,license){
    txt(s,title,x,y,w,33,23,{bold:true,color:c.teal,link});
    txt(s,detail,x,y+39,w,52,18,{color:c.muted});
    if(license) txt(s,license[0],x,y+94,w,24,16,{color:c.teal,link:license[1]});
  }
  rule(s,160,L,610,c.teal); rule(s,160,670,R,c.teal);
  txt(s,"STATION DATA & PROJECT",L,174,546,25,16,{bold:true,color:c.muted});
  txt(s,"PHOTOGRAPHS",670,174,546,25,16,{bold:true,color:c.muted});
  ref(L,218,546,"DB InfraGO station equipment","Ingolstadt Hbf. Platform heights and\nnet construction lengths.",urls.equipment);
  ref(L,311,546,"DB InfraGO service facilities plan","Ingolstadt Hbf (MIH). Document dated 19 Oct 2026.\nPassenger-area crop on slide 3.",urls.plan);
  ref(L,404,546,"Deutsche Bahn departure timetable","Ingolstadt Hbf. Valid from 14 Dec 2025.\nICE 822 example on PDF page 3.",urls.timetable);
  ref(L,497,546,"IngoHbfSimulation repository","Model eligibility, dispatch policies and paired runs.",urls.repo);
  ref(670,218,546,"Ingolstadt Hbf platforms","Thesenbauer, 15 Jun 2013. Cropped on slide 1.",urls.platformPhoto,["CC BY-SA 3.0 license",urls.platformLicense]);
  ref(670,369,546,"Ingolstadt Hbf exterior from the west","Renardo la vulpo, 29 May 2022. Shown on slide 3.",urls.exteriorPhoto,["CC0 1.0 dedication",urls.exteriorLicense]);
  note(s,null,"Untimed reference slide",[
    "The three editable EPCs follow the supplied conceptual IRIS build specification. The eligibility matrix and paired-run status were checked against the repository. The occupancy timelines on slides 2 and 5 illustrate the decision logic.",
  ], Object.values(urls));
}

await fs.mkdir(path.dirname(output), {recursive:true});
const pptx = await PresentationFile.exportPptx(show);
await pptx.save(output);
console.log(`Saved ${show.slides.items.length} slides to ${output}`);
