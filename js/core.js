/* Pure, dependency-free helpers for Earth Jukebox.
 *
 * These functions have no DOM, Web Audio, or global-state dependencies, so
 * they can be unit-tested in isolation (see test/runner.html). index.html
 * imports them from here instead of defining its own copies.
 */

// Pitch / note helpers
export const NOTE_NAMES=["C","C♯","D","D♯","E","F","F♯","G","G♯","A","A♯","B"];
export const mtof=m=>440*Math.pow(2,(m-69)/12);
export const noteName=m=>NOTE_NAMES[((m%12)+12)%12]+(Math.floor(m/12)-1);

// Generic math
export const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
export const lerp=(a,b,t)=>a+(b-a)*t;

// Sound level labels
export const lvl=n=>n<.33?"low":n<.66?"moderate":"high";

// ---- colour ----

export function rgb2hsv(r,g,b){
  r/=255;g/=255;b/=255;const mx=Math.max(r,g,b),mn=Math.min(r,g,b),d=mx-mn;let h=0;
  if(d>0){if(mx===r)h=((g-b)/d)%6;else if(mx===g)h=(b-r)/d+2;else h=(r-g)/d+4;h*=60;if(h<0)h+=360}
  return [h,mx===0?0:d/mx,mx];
}

export function colorName(h,s,v){
  if(v<.2)return "dark";
  if(s<.18)return v>.75?"white":"grey";
  if(h<15||h>=345)return "red";if(h<45)return "orange";if(h<70)return "yellow";
  if(h<160)return "green";if(h<195)return "teal";if(h<255)return "blue";if(h<290)return "purple";return "pink";
}

export function analyze(px,w,h){
  const n=w*h,V=new Float32Array(n),S=new Float32Array(n),L=new Float32Array(n),H=new Float32Array(n);
  let hx=0,hy=0,ws=0,sumS=0,sumV=0,dark=0,warm=0,cool=0;const cnt={};
  const quad=[0,0,0,0];
  for(let i=0;i<n;i++){
    const r=px[4*i],g=px[4*i+1],b=px[4*i+2],[hh,ss,vv]=rgb2hsv(r,g,b);
    H[i]=hh;S[i]=ss;V[i]=vv;L[i]=(.2126*r+.7152*g+.0722*b)/255;
    const wg=vv<.15?0:ss*vv;hx+=Math.cos(hh*Math.PI/180)*wg;hy+=Math.sin(hh*Math.PI/180)*wg;ws+=wg;
    sumS+=ss;sumV+=vv;if(vv<.15)dark++;
    if(ss>.2&&vv>.2){if(hh<70||hh>=330)warm+=wg;else if(hh>=160&&hh<=270)cool+=wg}
    const nm=colorName(hh,ss,vv);cnt[nm]=(cnt[nm]||0)+1;
    const x=i%w,y=(i/w)|0;quad[(y>=h/2?2:0)+(x>=w/2?1:0)]+=vv;
  }
  const E=new Float32Array(n);let eSum=0;
  for(let y=1;y<h-1;y++)for(let x=1;x<w-1;x++){const i=y*w+x,gx=L[i+1]-L[i-1],gy=L[i+w]-L[i-w];
    const e=clamp(Math.hypot(gx,gy)*4);E[i]=e;eSum+=e;}
  const hue=ws>1e-6?((Math.atan2(hy,hx)*180/Math.PI)+360)%360:0;
  const names=Object.entries(cnt).filter(([k])=>k!=="dark").sort((a,b)=>b[1]-a[1]).map(([k,c])=>[k,c/n]);
  const qn=["top left","top right","bottom left","bottom right"];
  const g={hue,sat:sumS/n,val:sumV/n,warmth:(warm-cool)/(warm+cool+1e-6),edge:eSum/n,darkFrac:dark/n,
           names,bright:qn[quad.indexOf(Math.max(...quad))]};
  const cols=[];
  for(let k=0;k<64;k++){
    const x0=Math.floor(k*w/64),x1=Math.max(x0+1,Math.floor((k+1)*w/64));
    let sv=0,ss=0,se=0,sd=0,cx=0,cy=0,cw=0,c=0,peak=0;const row=new Float32Array(h),rowE=new Float32Array(h);
    const nc=Math.max(1,Math.min(x1,w)-x0);
    for(let x=x0;x<x1&&x<w;x++)for(let y=0;y<h;y++){const i=y*w+x,vv=V[i],s=S[i];
      sv+=vv;ss+=s;se+=E[i];if(vv<.15)sd++;c++;if(vv>peak)peak=vv;
      const wg=vv<.15?0:s*vv;cx+=Math.cos(H[i]*Math.PI/180)*wg;cy+=Math.sin(H[i]*Math.PI/180)*wg;cw+=wg;
      row[y]+=.5*vv+.5*s*vv;rowE[y]+=E[i];}
    let mean=0;for(let y=0;y<h;y++){row[y]/=nc;rowE[y]/=nc;mean+=row[y]}mean/=h;
    for(let y=0;y<h;y++)row[y]=.35*row[y]+1.2*Math.abs(row[y]-mean)+1.0*rowE[y];
    let best=-1,bi=0;
    for(let y=0;y<h;y++){let a=0,m=0;for(let d=-2;d<=2;d++){const yy=y+d;if(yy>=0&&yy<h){a+=row[yy];m++}}a/=m;if(a>best){best=a;bi=y}}
    const hue2=cw>1e-6?((Math.atan2(cy,cx)*180/Math.PI)+360)%360:hue;
    cols.push({v:sv/c,s:ss/c,e:se/c,dark:sd/c,hue:hue2,peak,row:h>1?bi/(h-1):.5});
  }
  return {g,cols};
}

export function buildKey(g){
  const off=Math.round(g.hue/360*12)%12,minor=g.warmth>.15,iv=minor?[0,3,5,7,10]:[0,2,4,7,9],root=45+off,scale=[];
  for(let o=0;o<2;o++)for(const i of iv)scale.push(root+12+12*o+i);
  return {root,minor,iv,scale,name:NOTE_NAMES[root%12]+(minor?" minor":" major")};
}

export function describeImageGlobal(an,key){
  const g=an.g,tone=g.val>.65?"bright":g.val<.3?"dark":"medium-toned";
  const nm=g.names.slice(0,2).filter(x=>x[1]>.08).map(x=>x[0]);
  const warmth=g.warmth>.3?"warm":g.warmth<-.3?"cool":"a mix of warm and cool";
  const struct=g.edge>.12?"detailed, with many sharp boundaries":g.edge>.04?"with some structure":"smooth, with soft gradients";
  return `A ${tone} image${nm.length?", mostly "+nm.join(" and "):""}, ${warmth} in feel, ${struct}.`+
    (g.darkFrac>.5?" More than half of it is dark.":"")+` The brightest area is the ${g.bright}.`+
    ` It plays in ${key.name}, ${key.minor?"a more tense minor sound":"an open major sound"}.`;
}

// ---- PM2.5 US EPA bands ----

export const PM_BREAKS=[9.1,35.5,55.5,125.5,225.5];
export const PM_NAMES=["good","moderate","unhealthy for sensitive groups","unhealthy","very unhealthy","hazardous"];

export function pmBand(v){let i=0;while(i<PM_BREAKS.length&&v>=PM_BREAKS[i])i++;return i;}
export function pmCat(v){return PM_NAMES[pmBand(v)];}

// ---- time zones (Intl.DateTimeFormat with fixed-offset fallback) ----

// Format an epoch timestamp in a time zone. Returns {t:"Sun 11:30", d:"2025-12-26"} in local time.
// When tz is a valid IANA zone it is used (DST-aware); otherwise offsetMin (minutes
// east of UTC) is applied to a UTC date.
export function formatTime(epochMs,tz,offsetMin){
  if(!Number.isFinite(epochMs))return {t:"",d:""};
  const date=new Date(epochMs);
  let t,d;
  if(tz){
    try{
      const tf=new Intl.DateTimeFormat("en-US",{weekday:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23",timeZone:tz});
      const p=tf.formatToParts(date);const get=(n)=>{const f=p.find(x=>x.type===n);return f?f.value:""};
      t=`${get("weekday")} ${get("hour")}:${get("minute")}`;
      const df=new Intl.DateTimeFormat("en-US",{year:"numeric",month:"2-digit",day:"2-digit",timeZone:tz});
      const dp=df.formatToParts(date);const gp=(n)=>{const f=dp.find(x=>x.type===n);return f?f.value:""};
      d=`${gp("year")}-${gp("month")}-${gp("day")}`;
    }catch(e){tz=null;}
  }
  if(!tz){
    const d0=new Date(epochMs+offsetMin*60000);
    const days=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
    t=`${days[d0.getUTCDay()]} ${String(d0.getUTCHours()).padStart(2,"0")}:${String(d0.getUTCMinutes()).padStart(2,"0")}`;
    d=d0.toISOString().slice(0,10);
  }
  return {t,d};
}
