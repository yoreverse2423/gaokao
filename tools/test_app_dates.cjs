const fs=require('fs'),vm=require('vm'),assert=require('assert'),{spawnSync}=require('child_process');
if(process.env.GAOKAO_DATE_CHILD!=='1'){
  let failed=false;
  for(const tz of ['Asia/Shanghai','UTC','America/New_York']){
    const r=spawnSync(process.execPath,[__filename],{env:{...process.env,TZ:tz,GAOKAO_DATE_CHILD:'1'},encoding:'utf8'});
    if(r.status!==0){failed=true;console.error(tz,r.stdout,r.stderr);}
    else console.log(tz+': '+r.stdout.trim());
  }
  process.exit(failed?1:0);
}
const root=require('path').resolve(__dirname,'..');
function run(storage){const app={innerHTML:'',addEventListener(){}};const cd={};const ctx={window:{PLAN:{calendar:JSON.parse(fs.readFileSync(root+'/data/calendar.json')),subjects:{}}},document:{querySelector:s=>s==='#app'?app:s==='#cd'?cd:null,querySelectorAll:()=>[]},localStorage:storage};vm.createContext(ctx);vm.runInContext(fs.readFileSync(root+'/app.js','utf8'),ctx);return ctx;}
for(const storage of [{getItem:()=>'{bad json',setItem(){}},{getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}},{getItem:()=>null,setItem(){}}]){
 const c=run(storage);
 for(const [time,date,weekday] of [['2026-11-16T03:59:59+08:00','2026-11-15',0],['2026-11-16T04:00:00+08:00','2026-11-16',1],['2026-11-16T12:45:00+08:00','2026-11-16',1],['2027-06-07T03:59:59+08:00','2027-06-06',0],['2027-06-07T04:00:00+08:00','2027-06-07',1]]){
 c.n=Date.parse(time);assert.equal(vm.runInContext('iso(studyDate(n))',c),date);assert.equal(vm.runInContext('studyDate(n).getUTCDay()',c),weekday);
 }
 assert.equal(vm.runInContext('weekOf(studyDate(Date.parse("2026-11-15T12:00:00+08:00")))',c),undefined);
 assert.equal(vm.runInContext('weekOf(studyDate(Date.parse("2027-06-07T12:00:00+08:00")))',c),undefined);
 assert.equal(vm.runInContext('countdown(Date.parse("2027-06-06T23:59:00+08:00"))',c),1);
 assert.equal(vm.runInContext('countdown(Date.parse("2027-06-07T00:00:00+08:00"))',c),0);
 vm.runInContext('V.today();V.week();V.all();V.subj();save()',c);
}
console.log('PASS: Beijing 04:00 boundaries, weekdays, out-of-range, countdown, storage failures, view generation');
