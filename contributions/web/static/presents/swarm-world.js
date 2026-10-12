import {WORKPLACES} from './swarm-sites.js';
// The sandbox extends the original Presents district and canonical renderer.
let latest=null,signature='';
const homeZ=index=>index<6?9:27+Math.floor((index-6)/6)*5;
function sync(){
  const door=window.PresentsExperience?.sandboxScene?.();
  if(!latest||!door?.world||!door?.district)return;
  const {scene,world,district}=door;
  const residents=latest.residents||[];
  scene.expandBounds({x:Math.max(26,district.bounds.x),z:Math.max(district.bounds.z,homeZ(Math.max(0,residents.length-1))+4)});
  scene.setResidents?.(residents.map((r,index)=>({...r,home_position:{x:-18+(index%6)*7,z:homeZ(index)+1},workplace:{x:WORKPLACES[r.role]?.x||0,z:(WORKPLACES[r.role]?.z||18)+3.6}})));
  const key=JSON.stringify(residents.map(r=>[r.id,r.color,(r.home?.items||[]).map(i=>i.id)]));
  if(key===signature)return;
  const objects=[...world.objects];
  for(let row=0;row<Math.ceil(residents.length/6);row++){
    for(const x of [-11.9,11.9])objects.push({id:`swarm-walk-${row}-${x}`,kind:'promenade-long',x,y:0,z:homeZ(row*6)-2.5});
  }
  for(const [index,resident] of residents.entries()){
    const x=-18+(index%6)*7,z=homeZ(index);
    objects.push({id:'swarm-home-'+resident.id,kind:'home',x,y:0,z,color:resident.color,yaw:0,scale:.72});
    for(const [i,item] of (resident.home?.items||[]).entries()){
      const kind=item.id.includes('lamp')?'lantern':item.id.includes('plant')?'flower':item.id.includes('chair')||item.id.includes('sofa')?'bench':item.id.includes('book')?'voxel':'stone';
      objects.push({id:'swarm-item-'+resident.id+'-'+item.id,kind,x:x-1.5+(i%4)*.8,y:0,z:z+1.8+Math.floor(i/4)*.9,color:resident.color,yaw:0,scale:.45});
    }
  }
  scene.expandBounds({x:Math.max(26,district.bounds.x),z:Math.max(district.bounds.z,homeZ(Math.max(0,residents.length-1))+4)});
  scene.setWorld({...world,objects},{reset:false});
  signature=key;
}
window.addEventListener('swarm:state',event=>{latest=event.detail;sync();});
const ready=setInterval(()=>{sync();if(signature)clearInterval(ready);},500);
