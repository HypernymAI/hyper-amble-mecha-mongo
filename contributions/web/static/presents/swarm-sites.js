// Local Presents architecture, added before the original district is validated.
export const WORKPLACES = Object.freeze({
  healthcare: {x:-14,z:18,title:'Clinic'},
  finance: {x:0,z:18,title:'Ledger office'},
  construction: {x:-18,z:-3.3,title:'Construction site'},
});

export function withWorkplaces(original) {
  const district=JSON.parse(JSON.stringify(original));
  const shell=(accent,label)=>[
    [0,.16,0,9,.32,6,'stone'],[0,1.7,0,8,3,4.8,'pale'],
    [0,3.3,0,8.8,.3,5.4,accent],[0,2.5,2.45,7,.8,.15,'ink'],
    {text:label,x:0,y:2.5,z:2.56,cell:.14,color:'pale',face:'front'},
    [0,.9,2.45,1.1,1.6,.18,'ink'],[-2.4,1.25,2.45,1.8,1,.18,'glass'],
    [2.4,1.25,2.45,1.8,1,.18,'glass'],[0,.42,3,2.4,.25,1,'stone'],
  ];
  district.recipes['swarm-clinic']={parts:[...shell('teal','CLINIC'),
    [0,3.9,0,1.5,.45,.5,'teal'],[0,3.9,0,.45,1.5,.5,'teal']]};
  district.recipes['swarm-ledger']={parts:[...shell('gold','LEDGER'),
    ...[-3.3,-1.7,1.7,3.3].map(x=>[x,1.25,2.9,.3,2.1,.4,'gold'])]};
  district.recipes['swarm-yard']={parts:[
    [0,.12,0,9.5,.24,6.5,'stone'],[-3,1.2,0,2.8,2.2,3.8,'violet'],
    [-3,2.45,0,3.2,.3,4.2,'ink'],[-3,1.5,2,2.5,.7,.15,'ink'],
    {text:'WORKS',x:-3,y:1.5,z:2.15,cell:.1,color:'pale',face:'front'},
    [3.4,2.8,-1,.45,5.6,.45,'gold'],[.9,5.3,-1,5.4,.35,.5,'gold'],
    [-1.3,4.2,-1,.06,2,.06,'ink'],[-1.3,3.2,-1,.4,.3,.4,'gold'],
    [1,.5,1,2,.8,1.4,'coral'],[1,1.05,1,1.5,.3,1.2,'pale'],
    [-1,.5,2.4,.2,1,.2,'gold'],[3.8,.5,2.4,.2,1,.2,'gold'],
    [1.4,.85,2.4,5,.2,.2,'gold'],[1.4,.4,2.4,5,.2,.2,'ink'],
  ]};
  // In swarm mode the existing corner-store lot becomes the arm worksite.
  const store=district.world.objects.find(object=>object.id==='store');
  if(store)store.kind='swarm-yard';
  const kinds={healthcare:'swarm-clinic',finance:'swarm-ledger',construction:'swarm-yard'};
  for(const [role,place] of Object.entries(WORKPLACES)){
    if(role==='construction')continue;
    district.world.objects.push({id:'swarm-workplace-'+role,kind:kinds[role],x:place.x,y:0,z:place.z});
  }
  for(const x of [-11.9,11.9])district.world.objects.push({id:'swarm-work-avenue-'+(x<0?'west':'east'),kind:'avenue',x,y:0,z:14});
  district.bounds={x:Math.max(36,district.bounds.x),z:Math.max(25,district.bounds.z)};
  return district;
}
