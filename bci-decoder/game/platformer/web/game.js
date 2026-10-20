(() => {
  const canvas = document.querySelector('#game');
  const ctx = canvas.getContext('2d');
  const shell = document.querySelector('.shell');
  const ui = {
    screen: document.querySelector('#screen'), title: document.querySelector('#title'),
    message: document.querySelector('#message'), start: document.querySelector('#start'),
    mode: document.querySelector('#mode'), source: document.querySelector('#source'),
    action: document.querySelector('#action'), coins: document.querySelector('#coins'),
    fullscreen: document.querySelector('#fullscreen'),
  };
  const C = { navy:'#111f40', sky:'#1e3660', brick:'#9b603a', grass:'#5aaa58',
    gold:'#f7c339', cream:'#ffebba', white:'#f7f4de', pink:'#eb7066' };
  const LEVEL_W=960, GROUND_Y=144, UPPER_Y=96, PLAYER_W=16, PLAYER_H=16;
  const GRAVITY=500, JUMP_SPEED=-250, RUN_SPEED=72, JUMP_CARRY=104, CARRY_DECAY=34;
  const coinSpots=[[80,132],[300,132],[720,132],[150,84],[205,84],[505,84]];
  const obstacles=[[335,128,16,16],[555,128,16,16],[690,80,16,16]];
  const platforms=[[0,GROUND_Y,LEVEL_W],[112,UPPER_Y,158],[452,UPPER_Y,168]];
  let player, collected, previousIntent, finished, started, camera, frame, seq;
  let prevD=false, lastW=false, jumpPending=false, mode='keyboard', replay=[], replayIndex=0, replayNext=0;
  let input={intent:'NONE',source:'keyboard',receivedAt:performance.now()/1000}, lastTime=0;
  const keys=new Set();

  function reset(){
    player={x:28,y:GROUND_Y-PLAYER_H,vx:0,vy:0,grounded:true,cooldown:0,jumpCarry:0};
    collected=new Set();previousIntent='NONE';finished=false;camera=0;frame=0;seq=0;
    prevD=false;lastW=false;jumpPending=false;replayIndex=0;replayNext=0;started=false;
    input={intent:'NONE',source:mode==='keyboard'?'keyboard':'replay',receivedAt:performance.now()/1000};
    ui.screen.classList.remove('hidden');ui.title.textContent='准备好出发了吗？';
    ui.message.textContent='W 持续前进 · D 按下跳跃 · 收集金币后抵达终点';ui.start.textContent='开始游戏 ↗';
  }
  function decision(d,now){
    if(d.version!==1||!Number.isInteger(d.sequence)||!['LEFT_HAND','RIGHT_HAND','NONE'].includes(d.intent)||!['keyboard','replay','device'].includes(d.source)||d.sequence<seq)return;
    seq=d.sequence+1;input={intent:d.intent,source:d.source,receivedAt:now};
  }
  async function loadReplay(){
    try{
      const res=await fetch('/replay_demo.jsonl');if(!res.ok)throw Error('HTTP '+res.status);
      replay=(await res.text()).split(/\r?\n/).filter(x=>x.trim()).map(x=>JSON.parse(x));
      if(!replay.every(d=>d.source==='replay'))throw Error('source must be replay');
    }catch(e){ui.message.textContent='无法读取回放示例：'+e.message;}
  }
  function keyboard(now){
    const w=keys.has('KeyW'),d=keys.has('KeyD');
    // Preserve even a short D tap that begins and ends between animation frames.
    // A single event is consumed by the same decision/controller path as other input.
    if(jumpPending){jumpPending=false;decision({version:1,sequence:seq,intent:'RIGHT_HAND',source:'keyboard',timestamp:now},now);lastW=!w;return;}
    const state=w?'LEFT_HAND':'NONE';
    if(state!==(lastW?'LEFT_HAND':'NONE'))decision({version:1,sequence:seq,intent:state,source:'keyboard',timestamp:now},now);
    prevD=d;lastW=w;
  }
  function currentIntent(now){
    if(['replay','device'].includes(input.source)&&input.intent!=='NONE'&&now-input.receivedAt>1.5)return'NONE';
    return input.intent;
  }

  // Shared browser physics follows the same intent, jump-edge, carry and collision rules as Python.
  function update(intent,dt){
    const p=player;dt=Math.min(Math.max(dt,0),.05);p.cooldown=Math.max(0,p.cooldown-dt);
    if(intent==='RIGHT_HAND'&&previousIntent!=='RIGHT_HAND'&&p.grounded&&p.cooldown===0){
      p.vy=JUMP_SPEED;p.jumpCarry=JUMP_CARRY;p.grounded=false;p.cooldown=.24;
    }
    const oldX=p.x,oldY=p.y;
    p.vx=intent==='LEFT_HAND'?RUN_SPEED:p.jumpCarry;
    if(intent!=='LEFT_HAND')p.jumpCarry=Math.max(0,p.jumpCarry-CARRY_DECAY*dt);
    p.x+=p.vx*dt;
    // Obstacle faces stop a low jump; falling onto their top is a valid landing.
    for(const [x,y,w,h] of obstacles){
      const hit=p.x+PLAYER_W>x&&p.x<x+w&&p.y+PLAYER_H>y&&p.y<y+h;
      if(hit&&oldX+PLAYER_W<=x&&p.vx>0){
        p.x=x-PLAYER_W;
        // Keep forward intent/carry while braced against the wall; spend it after takeoff.
      }
    }
    p.vy+=GRAVITY*dt;p.y+=p.vy*dt;p.grounded=false;
    const surfaces=[...platforms,...obstacles.map(([x,y,w])=>[x,y,w])];
    for(const [left,top,width] of surfaces){
      const overlap=p.x+PLAYER_W>left&&p.x<left+width;
      const crossed=oldY+PLAYER_H<=top&&p.y+PLAYER_H>=top;
      if(p.vy>=0&&crossed&&overlap){p.y=top-PLAYER_H;p.vy=0;p.grounded=true;break;}
    }
    p.y=Math.min(p.y,200);if(p.grounded)p.jumpCarry=0;
    coinSpots.forEach(([x,y],i)=>{if(!collected.has(i)&&Math.abs(p.x+8-x)<11&&Math.abs(p.y+8-y)<13)collected.add(i);});
    if(p.x>=LEVEL_W-27)finished=true;previousIntent=intent;
    camera=Math.max(0,Math.min(LEVEL_W-320,p.x-88));
  }
  function rect(color,x,y,w,h){ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),Math.max(1,Math.round(w)),Math.max(1,Math.round(h)));}
  function tile(x,y){rect(C.brick,x,y,16,16);rect(C.grass,x,y,16,3);rect('#6b3d2d',x+1,y+8,14,1);rect('#b37446',x+3,y+4,2,3);rect('#b37446',x+10,y+11,3,3);}
  function draw(){
    ctx.fillStyle=C.sky;ctx.fillRect(0,0,320,180);
    for(let i=0;i<4;i++){const x=(48+i*93-Math.floor(camera/3)+370)%370-25,y=28+(i%2)*17;rect('#516c8e',x,y,23,4);rect('#516c8e',x+6,y-4,12,4);}
    for(const [x,y,w]of platforms)for(let tx=Math.floor(x/16)*16;tx<x+w;tx+=16)if(tx-camera>-16&&tx-camera<320)tile(tx-camera,y);
    for(const [x,color]of [[24,C.grass],[930,C.gold]])if(x-camera>-12&&x-camera<320){rect(C.cream,x-camera,110,2,34);rect(color,x-camera+2,110,13,8);}
    for(const [x,y,w,h]of obstacles){const sx=x-camera;if(sx>-20&&sx<320){rect('#4b302f',sx,y+2,w,h-2);rect('#bd5244',sx+2,y,w-4,6);rect('#f39766',sx+4,y+3,3,2);}}
    coinSpots.forEach(([x,y],i)=>{if(collected.has(i))return;const cx=Math.round(x-camera),r=frame%4<2?5:3;rect('#c77924',cx-r,y-4,2*r,8);rect(C.gold,cx-r,y-4,2*r,8);rect('#ffe679',cx-1,y-2,2,5);});
    const x=Math.round(player.x-camera),y=Math.round(player.y);
    rect('#2d2334',x+4,y+13,9,3);rect(C.pink,x+4,y+1,9,7);rect('#ffb597',x+6,y,5,2);rect('#ffcea8',x+6,y+3,6,4);rect(C.navy,x+10,y+3,2,2);rect('#66b4d7',x+3,y+8,10,6);rect('#4f84b8',x+5,y+9,6,4);rect('#f5bf4f',x+4,y+14,4,2);rect('#f5bf4f',x+10,y+14,4,2);
    const intent=currentIntent(performance.now()/1000);if(intent==='RIGHT_HAND'){rect(C.white,x+2,y+7,2,2);rect(C.white,x+13,y+6,2,2);}else if(intent==='LEFT_HAND'){const s=frame%2;rect('#f5bf4f',x+2+s,y+14,3,2);rect('#f5bf4f',x+10-s,y+14,3,2);}
    ui.coins.textContent=`金币 ${collected.size}/6`;ui.action.textContent={LEFT_HAND:'前进',RIGHT_HAND:'跳跃',NONE:'待机'}[intent];ui.source.textContent=mode==='keyboard'?'键盘模拟':'数据回放';
  }
  function begin(){if(started)return;started=true;ui.screen.classList.add('hidden');lastTime=performance.now();}
  async function toggleFullscreen(){try{if(!document.fullscreenElement)await shell.requestFullscreen();else await document.exitFullscreen();}catch(e){ui.message.textContent='浏览器未允许全屏，请按 F11 使用浏览器全屏。';}}
  addEventListener('keydown',e=>{if(['KeyW','KeyD','KeyR','KeyF','Enter','Space'].includes(e.code))e.preventDefault();if(e.repeat&&e.code==='KeyD')return;keys.add(e.code);if(e.code==='KeyD'&&!e.repeat){prevD=true;if(started&&!finished)jumpPending=true;}if(e.code==='KeyF')toggleFullscreen();if(e.code==='Enter'&&!started)begin();if(e.code==='KeyR'&&(finished||!started))reset();});
  addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',()=>keys.clear());
  ui.fullscreen.addEventListener('click',toggleFullscreen);canvas.addEventListener('dblclick',toggleFullscreen);ui.start.addEventListener('click',begin);
  ui.mode.addEventListener('change',async()=>{mode=ui.mode.value;if(mode==='replay')await loadReplay();reset();});
  function loop(nowMs){const now=nowMs/1000;if(started&&!finished){const dt=lastTime?(nowMs-lastTime)/1000:0;if(mode==='keyboard')keyboard(now);else if(replayIndex<replay.length&&now>=replayNext){decision(replay[replayIndex++],now);replayNext=now+.75;}update(currentIntent(now),dt);lastTime=nowMs;}draw();if(finished){ui.screen.classList.remove('hidden');ui.title.textContent='第一关通关！';ui.message.textContent=`收集金币 ${collected.size}/6 · 金币不是通关条件`;ui.start.textContent='再玩一次 ↗';}frame++;requestAnimationFrame(loop);}
  reset();requestAnimationFrame(loop);
})();
