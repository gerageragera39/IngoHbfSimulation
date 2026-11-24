import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(process.argv[2] ?? path.join(here, "Ingolstadt_Hbf_revised.pptx"));
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
    "Imagine a train arriving at Ingolstadt and finding its planned platform still occupied. Should it wait, or use another track? That decision is the subject of our study. We’ll show where the conflict comes from, compare three ways to assign tracks, and explain how we plan to test them.",
  ], [`Photo: Thesenbauer, 15 June 2013, cropped. ${urls.platformPhoto}`, urls.platformLicense]);
}

// 2 · Problem statement and occupancy example
{
  const s = page(2, "A late train can delay the next one", "An incoming delay can shift platform occupancy into the next train’s slot.");
  txt(s, "Can reassignment\nreduce secondary\ndelay with the same\nfour tracks?", L, 213, 425, 201, 39, {bold:true,color:c.teal});
  txt(s, "Incoming delay builds up before arrival.\nSecondary delay is the extra departure\ndelay caused within the station.", L, 465, 432, 98, 23);
  const x = 577, w = 639, step = w/8;
  const t = k => x + step*k;
  txt(s, "Following train is ready", t(4)-130, 215, 260, 27, 20, {align:"center",bold:true});
  txt(s, "Planned\ntrack", 471, 306, 89, 55, 19, {align:"right",bold:true});
  txt(s, "Eligible\nalternate", 466, 397, 94, 55, 19, {align:"right",bold:true});
  box(s,"Planned track lane",x,307,w,52,c.lane);
  box(s,"Alternate track lane",x,397,w,52,c.lane);
  box(s,"Earlier train's extended occupancy",t(1),307,step*5,52,c.teal);
  txt(s,"Late train still on track",t(1),307,step*3,52,20,{align:"center",bold:true,color:c.white});
  box(s,"Free alternate during conflict",t(4),397,step*2,52,c.mint,stroke(c.teal));
  txt(s,"Free",t(4),397,step*2,52,21,{align:"center",bold:true,color:c.teal});
  for(let y=252;y<460;y+=12) box(s,"Readiness marker",t(4)-1,y,2,6,c.ink);
  for(let y=252;y<460;y+=12) box(s,"Clearance marker",t(6)-1,y,2,6,c.rust);
  box(s,"Waiting interval",t(4),268,step*2,5,c.orange);
  txt(s,"Extra waiting",t(4),274,step*2,25,20,{align:"center",bold:true,color:c.rust});
  txt(s,"Track clears",t(6)+11,223,140,24,19,{bold:true,color:c.rust});
  rule(s, 492, x, x+w, c.grey);
  txt(s,"Time",x,509,w,24,18,{color:c.muted,align:"right"});
  caption(s,"Illustrative occupancy",x,546,w);
  note(s, "Herman Dihtenko", "0:50", [
    "Read this from left to right. At the first dashed line, the following train is ready to enter. The earlier train is still on the planned track, so the following train has to wait until the second dashed line. The lower track is free at that moment. Moving the train there could save time, but another service might need that same track shortly afterward.",
    "We call the extra delay a train picks up at the station secondary delay. We count it at departure and account separately for the lateness the train brought in.",
  ], [urls.repo]);
}

// 3 · Real station evidence and boundaries
{
  const s = page(3, "One station, four modeled tracks", "RB16, RE1 and ICE services in both directions at Ingolstadt Hbf");
  const planWidth=742, planTop=192, planScale=planWidth/890;
  const planRight=L+planWidth;
  img(s, plan, "image/png", "DB InfraGO passenger area plan showing tracks 2, 3, 4 and 5", L, planTop, planWidth, 465*planScale);
  box(s,"Plan border",L,planTop,planWidth,465*planScale,"none",stroke(c.line));
  // These rows locate the four rails in the unannotated plan crop.
  [208,261,288,341].forEach((row,i) => {
    const y=planTop+row*planScale;
    box(s,`Track ${i+2} highlight`,L+576*planScale,y-1.5,79*planScale,3,c.teal);
    box(s,`Track ${i+2} leader`,planRight,y-1,6,2,c.teal);
    const label=box(s,`Track ${i+2} callout`,planRight+6,y-10,27,20,c.teal);
    setText(label,String(i+2),19,{bold:true,align:"center",color:c.white});
  });
  caption(s,"DB InfraGO AG, service facilities plan, 19 Oct 2026 (crop, annotated).",L,595,765,urls.plan);
  img(s, exteriorPhoto, "image/jpeg", "Ingolstadt Hauptbahnhof exterior from the west, 2022", 857, 192, 359, 119.67);
  caption(s,"Renardo la vulpo, 2022, CC0.",857,318,359,urls.exteriorPhoto);
  rule(s,355,857,R);
  const dimensionsSummary = `Tracks 2–3: ${dimensions[0].net_construction_length_m} m\nTracks 4–5: ${dimensions[2].net_construction_length_m} m\nPlatform edges: ${dimensions[0].platform_height_cm} cm high`;
  txt(s,dimensionsSummary,857,365,359,93,24,{bold:true,color:c.teal});
  caption(s,"DB InfraGO net construction lengths",857,460,359,urls.equipment);
  txt(s,"Model scope",857,497,359,29,20,{bold:true});
  txt(s,"Arrival, waiting, allocation, dwell\nand departure. Entry and exit\ncapacity are planned extensions.",857,530,359,79,21);
  note(s, "Herman Dihtenko", "0:55", [
    "The teal marks pick out tracks two through five on the official station plan. We focus on these four tracks and on RB16, RE1 and ICE services in both directions. The figures are DB InfraGO’s published platform construction lengths. The platform edges are all 76 centimetres high.",
    "We follow a train from arrival through waiting, platform assignment, passenger service and departure. The current scope stops there. Approach and exit capacity are planned extensions. A later timetable-based study would also need to account for other services that use the same tracks.",
    "Liliya will now explain which tracks the model makes available to each service.",
  ], [urls.equipment, `DB InfraGO AG, service facilities plan dated 19 October 2026. ${urls.plan}`,
    `Exterior photo: Renardo la vulpo, 29 May 2022. ${urls.exteriorPhoto}`, urls.exteriorLicense]);
}

// 4 · Native PowerPoint table with unchanged eligibility and planned tracks
{
  const s = page(4, "Simplified platform eligibility", "The matrix defines which tracks each service can use in the model.");
  const values = [
    ["Service group","Track 2","Track 3","Track 4","Track 5","Baseline track"],
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
        typeface:"Arial", fontSize:r === 0 ? 19 : eligible ? 23 : 21,
        color:r === 0 ? c.white : eligible || k === 5 ? c.teal : c.ink,
        alignment:k ? "center" : "left", verticalAlignment:"middle", bold:r === 0 || k === 5, wrap:"none",
      };
    }
  }
  txt(s,"●  Eligible in model",L,554,202,28,20,{bold:true,color:c.teal});
  txt(s,"–  Excluded in model",280,554,248,28,20);
  txt(s,"Baseline tracks are synthetic assignments by service group.\nOperational routing permissions require separate validation.",L,593,754,51,19,{color:c.muted});
  vRule(s,851,192,635);
  txt(s,"Published timetable",881,192,335,38,24,{bold:true,color:c.teal});
  txt(s,"ICE 822 at 05:26",881,247,335,32,23,{bold:true});
  txt(s,"Track 4 on certain Saturdays\nTrack 5 on certain weekdays",881,285,335,57,21);
  caption(s,"DB departure timetable, PDF p. 3",881,352,335,urls.timetable);
  rule(s,399,881,R);
  txt(s,"Dispatch constraints",881,419,335,38,24,{bold:true,color:c.teal});
  txt(s,"One train per track\nAssign only to eligible tracks\nRespect minimum dwell and\nscheduled departure times",881,460,335,111,21);
  note(s, "Liliya Radvar", "0:55", [
    "The dots show the track choices we give each service in the model. Read across southbound RE1, for example. It can use tracks two, three and five. The last column gives the representative track for each service group. We use track three as the baseline for southbound RE1.",
    "The example on the right comes from a published timetable. It shows the same ICE service scheduled on different tracks on different days. That is useful evidence about how the station is used. Before applying our eligibility rules to real operations, we would need to check routing permissions and which tracks are reachable for each train.",
  ], [`DB departure timetable valid from 14 December 2025, PDF page 3. ${urls.timetable}`, urls.equipment, `Model matrix: route_catalog.csv at ${urls.repo}`]);
}

// 5 · Native, scaled occupancy timelines
{
  const s = page(5, "Three dispatch strategies",
    "RE1 southbound arrives at 10:00. Tracks 2, 3 and 5 are eligible. Its planned track 2 frees at 10:01.");
  txt(s,"Tracks 3 and 5 start free. The ICE arrives at 10:02 and requires track 3. Occupancy is 6 min for RE1 and 2 min for the ICE.",
    L,163,R-L,27,21,{color:c.muted});
  const x=388, dx=85, right=x+8*dx;
  const at = t => x + t*dx;
  txt(s,"Track occupancy",x,197,350,26,19,{bold:true,color:c.teal});
  txt(s,"Total wait",1087,197,129,26,19,{bold:true,color:c.teal,align:"center"});
  const tracks = [2,3,5];
  const schedules = [
    {name:"Fixed", desc:"RE1 waits for track 2.", wait:1, lanes:[[[0,1,"Busy"],[1,7,"RE1"]],[[2,4,"ICE"]],[]]},
    {name:"Greedy", desc:"RE1 takes track 3.\nThe ICE waits.", wait:4, lanes:[[[0,1,"Busy"]],[[0,6,"RE1"],[6,8,"ICE"]],[]]},
    {name:"Lookahead", desc:"RE1 takes track 5.\nThe ICE enters on time.", wait:0, lanes:[[[0,1,"Busy"]],[[2,4,"ICE"]],[[0,6,"RE1"]]]},
  ];
  const fills = {Busy:c.grey, RE1:c.teal, ICE:c.rust};
  schedules.forEach((p,i) => {
    const y=228+i*113;
    rule(s,y,L,R);
    txt(s,p.name,L,y+10,253,33,29,{bold:true});
    if(i===2) txt(s,"Planned",230,y+13,101,28,17,{bold:true,color:c.rust});
    txt(s,p.desc,L,y+48,253,54,20,{color:c.muted,valign:"top"});
    p.lanes.forEach((lane,k) => {
      const yy=y+10+k*30;
      const track=tracks[k];
      txt(s,`Track ${track}`,298,yy,77,26,19,{align:"right"});
      box(s,`Track ${track} lane`,x,yy,right-x,26,c.lane);
      for(let j=1;j<8;j++) vRule(s,at(j),yy,yy+26,c.line);
      lane.forEach(([start,end,label]) => {
        box(s,`${label} occupies track ${track}`,at(start),yy,(end-start)*dx,26,fills[label]);
        txt(s,label,at(start),yy,(end-start)*dx,26,20,{bold:true,align:"center",color:c.white});
      });
    });
    for(let j=0;j<10;j++) box(s,"ICE arrival marker",at(2)-1,y+8+9*j,2,5,c.orange);
    txt(s,`${p.wait} min`,1087,y+24,129,52,38,{bold:true,align:"center",color:i===1?c.rust:c.teal});
  });
  rule(s,567,L,R);
  for(let t=0;t<=8;t++) txt(s,`10:0${t}`,at(t)-34,574,68,25,18,{align:"center",color:t===2?c.rust:c.muted,bold:t===2});
  txt(s,"Hand-worked example (no simulation run). Track 2 is this train’s plan. The southbound RE1 baseline uses track 3.",
    L,608,R-L,27,19,{color:c.muted});
  note(s, "Liliya Radvar", "1:20", [
    "Start with the RE1 at ten o’clock. This particular southbound train is planned for track two, which is busy for another minute. The baseline track on the previous slide was a representative input for the service group. Here we give this individual train a different plan. It could also use track three or five. The ICE arrives two minutes later and needs track three.",
    "With Fixed, the RE1 waits one minute for track two. The ICE enters on time. With Greedy, the RE1 takes track three straight away and stays there for six minutes. That leaves the ICE waiting until ten-oh-six, four minutes after it arrives.",
    "With the planned Lookahead strategy, the RE1 would take track five. The ICE could still enter on track three at ten-oh-two, giving zero total waiting. We worked these times out by hand to show how an immediate choice can affect the next train.",
  ], [`Policy status: ${urls.repo}`, "Occupancy timeline uses the hand-worked southbound RE1 scenario supplied for this revision."]);
}

// EPC drawing helpers. Each event, function and connector remains editable.
function epcNode(s, type, copy, x, y, w=256, h=76, accent=false) {
  const fill = type === "event" ? (accent ? c.teal : c.mint) : (accent ? c.pale : c.white);
  const line = type === "event" ? stroke(c.teal,1.35) : stroke(accent?c.rust:c.grey,1.35);
  const geometry = type === "event" ? "hexagon" : "roundRect";
  const node = shape(s,`${type}: ${copy.replaceAll("\n"," ")}`,geometry,px(x,y,w,h),fill,line);
  setText(node,copy,23,{bold:true,align:"center",color:type === "event" && accent ? c.white : c.ink});
  return node;
}
function xor(s, label, x,y) {
  const o=shape(s,label,"ellipse",px(x,y,48,48),c.paper,stroke(c.teal,2));
  setText(o,"XOR",15,{bold:true,align:"center",color:c.teal});
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
  const tipSize=13, thickness=2.45;
  const base=[bx-tipSize*vx,by-tipSize*vy];
  const shaft=[...points.slice(0,-1),[base[0]+vx,base[1]+vy]];
  for(let i=1;i<shaft.length;i++){
    const [sx,sy]=shaft[i-1], [ex,ey]=shaft[i];
    box(s,name,Math.min(sx,ex)-thickness/2,Math.min(sy,ey)-thickness/2,
      Math.abs(ex-sx)+thickness,Math.abs(ey-sy)+thickness,color);
  }
  const rotation=vx>0?90:vx<0?270:vy>0?180:0;
  const tip=shape(s,`${name} arrow`,"triangle",
    px(bx-tipSize*(vx+1)/2,by-tipSize*(vy+1)/2,tipSize,tipSize),color);
  tip.rotation=rotation;
}
function serpentine(s,nodes) {
  const columns=[64,360,656,952], rows=[203,327,451];
  const placements=[[0,0],[1,0],[2,0],[3,0],[3,1],[2,1],[1,1],[0,1],[0,2],[1,2],[2,2]];
  const o=nodes.map(([copy,accent],i) => {
    const [col,row]=placements[i];
    return epcNode(s,i%2?"function":"event",copy,columns[col],rows[row],264,76,accent);
  });
  for(let i=1;i<o.length;i++){
    const [a,b]=placements[i-1], [x,y]=placements[i];
    connect(s,o[i-1],o[i],b!==y?"bottom":x>a?"right":"left");
  }
  txt(s,"Start",columns[0],173,264,24,18,{bold:true,color:c.teal,align:"center"});
  txt(s,"End",columns[2],533,264,24,18,{bold:true,color:c.teal,align:"center"});
}
function epcLegend(s,captionText,withXor=false) {
  rule(s,572);
  shape(s,"Event key","hexagon",px(L,597,31,22),c.mint,stroke(c.teal));
  txt(s,"Event",104,597,83,22,18,{color:c.muted});
  shape(s,"Function key","roundRect",px(176,597,31,22),c.white,stroke(c.grey));
  txt(s,"Function",216,597,94,22,18,{color:c.muted});
  if(withXor){
    shape(s,"Connector key","ellipse",px(304,597,22,22),c.paper,stroke(c.teal));
    txt(s,"Exclusive connector",333,597,178,22,18,{color:c.muted});
  }
  txt(s,captionText,withXor?515:323,597,withXor?701:893,22,18,{color:c.muted,align:"right"});
}

// 6 · Overall station EPC
{
  const s=page(6,"EPC 1  Overall station process","The event-driven process chain follows a train from scheduled arrival to resource release.");
  serpentine(s,[
    ["Train arrival\nscheduled",true], ["Use incoming delay\nto set readiness"], ["Train ready\nfor entry"], ["Allocate platform\n(EPC 2)"],
    ["Platform reserved"], ["Authorize entry\nand enter station",true], ["Train at platform"], ["Serve passengers,\nmeet minimum dwell"],
    ["Passenger service\ncomplete"], ["Manage departure\n(EPC 3)"], ["Train departed and\nresources released",true],
  ]);
  epcLegend(s,"Conceptual target process. Entry-route authorization is planned.");
  note(s,"Liliya Radvar","0:40",[
    "Start at the upper left. A hexagon shows a state, such as a train being ready. A rounded rectangle shows an action, such as assigning a platform. Follow the arrows across the first row, then back along the second. Once the train has a track, it enters, serves passengers and meets its minimum dwell time. Entry authorization represents an extension we plan to study.",
    "Mohammad will take us through the two decisions in more detail.",
  ],["Conceptual EPC based on the supplied IRIS build specification."]);
}

// 7 · Allocation EPC and explicit return to the XOR join
{
  const s=page(7,"EPC 2  Platform assignment","The policy decides whether to reserve an eligible track now or reevaluate later.");
  const a=epcNode(s,"event","Train ready\nfor allocation",80,189,240,64,true);
  const b=xor(s,"XOR join: arrival or reevaluation",176,270);
  const d=epcNode(s,"function","Evaluate policy and\ntrack availability",80,335,240,77);
  const e=xor(s,"XOR split: reserve or defer",176,430);
  connect(s,a,b,"bottom"); connect(s,b,d,"bottom"); connect(s,d,e,"bottom");
  txt(s,"Lookahead can defer assignment\neven when an eligible track is free.",407,193,780,74,27,{bold:true,color:c.teal});
  txt(s,"Reserve now",407,275,240,24,18,{bold:true,color:c.teal});
  txt(s,"Wait and retry",407,422,240,24,18,{bold:true,color:c.rust});
  const f=epcNode(s,"event","Suitable track\nselected",407,304,240,76);
  const g=epcNode(s,"function","Reserve track",687,304,220,76);
  const h=epcNode(s,"event","Platform reserved",947,304,269,76,true);
  const j=epcNode(s,"event","Allocation\ndeferred",407,452,240,76);
  const k=epcNode(s,"function","Wait for change\nor review time",687,452,220,76,true);
  const m=epcNode(s,"event","Ready to\nreevaluate",947,452,269,76);
  route(s,"Select now branch",[[224,454],[364,454],[364,342],[407,342]]);
  route(s,"Deferred branch",[[200,478],[200,490],[407,490]]);
  connect(s,f,g,"right"); connect(s,g,h,"right");
  connect(s,j,k,"right"); connect(s,k,m,"right");
  route(s,"Return to XOR join",[[1081.5,528],[1081.5,554],[57,554],[57,294],[176,294]],c.rust);
  txt(s,"Reevaluate",515,529,246,23,17,{bold:true,color:c.rust,align:"center"});
  epcLegend(s,"The loop returns to the first XOR.",true);
  note(s,"Mohammad Gaber","0:50",[
    "A train can reach this decision for the first time or return after waiting. The first circle brings those two paths together. At the second circle the dispatcher takes one of two routes. The upper route reserves a suitable free track and completes the assignment.",
    "On the lower route the train waits. It may have no track available, or the planned Lookahead policy may choose to hold it for a better option. When a track clears, conditions change or it’s time to check again, follow the orange line back to the same decision.",
  ],["Conceptual EPC based on the supplied IRIS build specification."]);
}

// 8 · Departure EPC and distinct release events
{
  const s=page(8,"EPC 3  Train departure","The platform track and exit route become available at separate clearance events.");
  serpentine(s,[
    ["Passenger service\ncomplete",true], ["Wait until scheduled\ndeparture if needed"], ["Train ready\nto depart"], ["Request exit route\nand wait",true],
    ["Exit route reserved"], ["Depart and clear\nplatform track"], ["Platform track clear"], ["Release track and\nfinish exit movement"],
    ["Exit route clear"], ["Release exit route\nand log departure"], ["Train departed and\nresources released",true],
  ]);
  epcLegend(s,"Conceptual target process including planned exit-route constraints.");
  note(s,"Mohammad Gaber","0:45",[
    "Once passenger service and minimum dwell are complete, the train waits if its scheduled departure time is still ahead. In the planned extension it also needs an exit route. If that route is busy, the train stays at the platform and can hold up the next arrival.",
    "Notice the two clearances. The next train can use the platform track as soon as the departing train is clear of it. The exit route stays reserved until the movement clears that route as well.",
  ],["Conceptual EPC based on the supplied IRIS build specification."]);
}

// 9 · Experiment design and conclusion
{
  const s=page(9,"Experiment design","Paired stochastic experiments replay identical scenarios for each policy.");
  const columns=[
    {x:L,w:344,title:"Scenarios",items:["Normal operation","Peak traffic","Larger incoming delays","Temporary track closure"]},
    {x:455,w:335,title:"Measures",items:["Mean secondary delay","Waiting time","Track utilization","Reassignments and throughput"]},
    {x:846,w:370,title:"Paired comparison",items:["Same schedule and track access","Same draw of incoming delays","Compare the policies","Repeat with fresh delay draws"]},
  ];
  for(const col of columns){
    rule(s,211,col.x,col.x+col.w,c.teal);
    txt(s,col.title,col.x,228,col.w,40,25,{bold:true,color:c.teal});
    col.items.forEach((item,i) => txt(s,item,col.x,282+i*44,col.w,item.includes("\n")?68:36,22));
  }
  box(s,"Conclusion band",L,501,R-L,112,c.teal);
  txt(s,"When is dynamic platform assignment beneficial —\nand when does it create new conflicts?",88,508,1104,96,35,{bold:true,color:c.white});
  note(s,"Mohammad Gaber","0:50",[
    "For each comparison, every policy gets the same schedule, track availability and randomly drawn delays. Then we draw a new set of delays and repeat. That way, a policy doesn’t get credit simply because its trains happened to arrive closer to schedule.",
    "We’ll compare normal operation, peak traffic, larger delays and a track closure. We’ll look at extra departure delay, waiting, track use, platform changes and how many trains get through. Fixed and Greedy are already in the prototype. Lookahead is planned.",
    "The question is: when is dynamic platform assignment beneficial, and when does it create new conflicts?",
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
