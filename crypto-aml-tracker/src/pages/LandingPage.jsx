import { useEffect, useRef, useState } from 'react';

function LoadingOverlay({ workspace }) {
  return (
    <div style={{ position:'fixed', inset:0, zIndex:9999, background:'#0A1020', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:'28px' }}>
      <style>{`@keyframes lp-spin{to{transform:rotate(360deg)}}@keyframes lp-spinR{to{transform:rotate(-360deg)}}@keyframes lp-pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.8;transform:scale(1.04)}}`}</style>
      <div style={{ position:'relative', width:'130px', height:'130px' }}>
        <div style={{ position:'absolute', inset:0, border:'1.5px solid rgba(201,168,76,0.2)', borderTopColor:'#C9A84C', borderRadius:'50%', animation:'lp-spin 1.4s linear infinite' }} />
        <div style={{ position:'absolute', inset:'14px', border:'1px solid rgba(201,168,76,0.1)', borderBottomColor:'rgba(201,168,76,0.5)', borderRadius:'50%', animation:'lp-spinR 2s linear infinite' }} />
        <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center' }}>
          <img src="/logo.png" alt="NBE" style={{ width:'64px', height:'64px', objectFit:'contain', animation:'lp-pulse 2s ease-in-out infinite' }} />
        </div>
      </div>
      <div style={{ textAlign:'center' }}>
        <div style={{ fontSize:'11px', color:'#C9A84C', fontWeight:'700', letterSpacing:'0.14em', textTransform:'uppercase', marginBottom:'6px' }}>{workspace === 'aml' ? 'Activating AML Workspace' : 'Loading Workspace'}</div>
        <div style={{ fontSize:'12px', color:'#4B5563' }}>National Bank of Ethiopia</div>
      </div>
    </div>
  );
}

function BgCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext('2d'); let id;
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize(); window.addEventListener('resize', resize);
    const nodes = Array.from({ length: 40 }, () => ({ x:Math.random()*c.width, y:Math.random()*c.height, vx:(Math.random()-.5)*.16, vy:(Math.random()-.5)*.16, r:Math.random()*1.6+.7 }));
    const draw = () => {
      ctx.clearRect(0,0,c.width,c.height);
      nodes.forEach(n => { n.x+=n.vx; n.y+=n.vy; if(n.x<0||n.x>c.width)n.vx*=-1; if(n.y<0||n.y>c.height)n.vy*=-1; });
      for(let i=0;i<nodes.length;i++) for(let j=i+1;j<nodes.length;j++) { const dx=nodes[i].x-nodes[j].x,dy=nodes[i].y-nodes[j].y,d=Math.sqrt(dx*dx+dy*dy); if(d<125){ctx.beginPath();ctx.moveTo(nodes[i].x,nodes[i].y);ctx.lineTo(nodes[j].x,nodes[j].y);ctx.strokeStyle=`rgba(201,168,76,${.06*(1-d/125)})`;ctx.lineWidth=.5;ctx.stroke();} }
      nodes.forEach(n=>{ctx.beginPath();ctx.arc(n.x,n.y,n.r,0,Math.PI*2);ctx.fillStyle='rgba(201,168,76,0.2)';ctx.fill();});
      id=requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(id); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={ref} style={{ position:'absolute', inset:0, width:'100%', height:'100%', pointerEvents:'none', opacity:.55 }} />;
}

function Card({ icon, title, subtitle, features, disabled, buttonLabel, onLaunch, delay }) {
  const [h, setH] = useState(false);
  return (
    <div onMouseEnter={()=>!disabled&&setH(true)} onMouseLeave={()=>setH(false)} style={{ flex:'1 1 300px', maxWidth:'340px', background:h?'linear-gradient(145deg,rgba(201,168,76,0.08),rgba(12,18,32,.97))':'rgba(11,17,30,.72)', border:`1px solid ${h&&!disabled?'rgba(201,168,76,.42)':disabled?'rgba(71,85,105,.2)':'rgba(201,168,76,.16)'}`, borderRadius:'18px', padding:'32px 28px', backdropFilter:'blur(16px)', transition:'all .3s ease', transform:h&&!disabled?'translateY(-5px) scale(1.01)':'translateY(0) scale(1)', boxShadow:h&&!disabled?'0 16px 48px rgba(201,168,76,0.1)':'0 4px 24px rgba(0,0,0,.3)', opacity:disabled?.48:1, cursor:disabled?'default':'pointer', animation:`lp-cardIn .55s ease ${delay}ms both` }}>
      <div style={{ width:'46px', height:'46px', borderRadius:'12px', background:disabled?'rgba(71,85,105,.08)':'rgba(201,168,76,0.09)', border:`1px solid ${disabled?'rgba(71,85,105,.15)':'rgba(201,168,76,.18)'}`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:'21px', marginBottom:'18px' }}>{icon}</div>
      <div style={{ fontSize:'16px', fontWeight:'700', color:disabled?'#4B5563':'#C8B98A', marginBottom:'8px', letterSpacing:'-.01em' }}>{title}</div>
      <div style={{ fontSize:'13px', color:'#3D4F63', lineHeight:1.7, marginBottom:'20px' }}>{subtitle}</div>
      <div style={{ display:'flex', flexDirection:'column', gap:'7px', marginBottom:'26px' }}>
        {features.map(f=>(
          <div key={f} style={{ display:'flex', alignItems:'center', gap:'9px' }}>
            <div style={{ width:'4px', height:'4px', borderRadius:'50%', background:disabled?'#2D3748':'rgba(201,168,76,.45)', flexShrink:0 }} />
            <span style={{ fontSize:'12px', color:disabled?'#2D3748':'#556070' }}>{f}</span>
          </div>
        ))}
      </div>
      <button onClick={disabled?undefined:onLaunch} disabled={disabled} style={{ width:'100%', padding:'12px', borderRadius:'9px', border:`1px solid ${disabled?'rgba(71,85,105,.15)':h?'rgba(201,168,76,.5)':'rgba(201,168,76,.22)'}`, background:disabled?'transparent':h?'rgba(201,168,76,.14)':'rgba(201,168,76,.06)', color:disabled?'#2D3748':h?'#E2C97E':'#B8963E', fontSize:'13px', fontWeight:'700', cursor:disabled?'not-allowed':'pointer', transition:'all .2s ease', letterSpacing:'.05em' }}>{buttonLabel}</button>
    </div>
  );
}

export default function LandingPage({ onEnterAML, onEnterCluster }) {
  const [launching, setLaunching] = useState(null);
  const go = (type, cb) => { setLaunching(type); setTimeout(cb, 1800); };

  return (
    <div style={{ minHeight:'100vh', height:'100vh', background:'linear-gradient(165deg,#0E1828 0%,#111F35 30%,#132240 60%,#0C1525 100%)', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', fontFamily:"'Inter','Segoe UI',system-ui,sans-serif", padding:'0 24px', position:'relative', overflow:'hidden' }}>
      <style>{`@keyframes lp-cardIn{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:translateY(0)}}@keyframes lp-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}@keyframes lp-ring{0%,100%{opacity:.4;transform:scale(1)}50%{opacity:.85;transform:scale(1.06)}}@keyframes lp-glow{0%,100%{opacity:.55}50%{opacity:1}}`}</style>

      <BgCanvas />

      {/* Full-page golden ambient lighting layers */}
      <div style={{ position:'absolute', inset:0, background:'radial-gradient(ellipse 120% 80% at 50% 30%,rgba(201,168,76,0.06) 0%,transparent 60%)', pointerEvents:'none' }} />
      <div style={{ position:'absolute', inset:0, background:'radial-gradient(ellipse 80% 60% at 20% 80%,rgba(201,168,76,0.03) 0%,transparent 55%)', pointerEvents:'none' }} />
      <div style={{ position:'absolute', inset:0, background:'radial-gradient(ellipse 80% 60% at 80% 80%,rgba(201,168,76,0.03) 0%,transparent 55%)', pointerEvents:'none' }} />
      <div style={{ position:'absolute', inset:0, background:'radial-gradient(ellipse 60% 40% at 50% 50%,rgba(201,168,76,0.04) 0%,transparent 50%)', pointerEvents:'none', animation:'lp-glow 5s ease-in-out infinite' }} />
      <div style={{ position:'absolute', bottom:0, left:0, right:0, height:'35%', background:'linear-gradient(to top,rgba(8,12,22,0.5),transparent)', pointerEvents:'none' }} />

      {launching && <LoadingOverlay workspace={launching} />}

      <div style={{ position:'absolute', top:0, left:0, right:0, height:'1px', background:'linear-gradient(90deg,transparent,rgba(201,168,76,0.25),transparent)', zIndex:2 }} />

      {/* MAIN CONTENT */}
      <div style={{ position:'relative', zIndex:2, display:'flex', flexDirection:'column', alignItems:'center', width:'100%', maxWidth:'820px' }}>

        {/* LOGO — overflow visible, no clipping */}
        <div style={{ textAlign:'center', marginBottom:'48px', animation:'lp-cardIn .6s ease' }}>
          <div style={{ position:'relative', display:'inline-flex', alignItems:'center', justifyContent:'center', padding:'24px' }}>
            {/* Full-page logo glow */}
            <div style={{ position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%)', width:'300px', height:'300px', borderRadius:'50%', background:'radial-gradient(circle,rgba(201,168,76,0.1) 0%,rgba(201,168,76,0.03) 45%,transparent 70%)', pointerEvents:'none', animation:'lp-glow 4s ease-in-out infinite' }} />
            {/* Logo container — overflow visible */}
            <div style={{ position:'relative', width:'160px', height:'160px', animation:'lp-float 5.5s ease-in-out infinite', flexShrink:0 }}>
              {/* Outer pulse ring — outside the container */}
              <div style={{ position:'absolute', inset:'-20px', borderRadius:'50%', border:'1px solid rgba(201,168,76,0.08)', animation:'lp-ring 3.5s ease-in-out infinite', pointerEvents:'none' }} />
              {/* Main gold border */}
              <div style={{ position:'absolute', inset:0, borderRadius:'50%', border:'1.5px solid rgba(201,168,76,0.3)', boxShadow:'0 0 40px rgba(201,168,76,0.1),0 0 80px rgba(201,168,76,0.04),inset 0 0 30px rgba(201,168,76,0.04)' }} />
              {/* Inner ring */}
              <div style={{ position:'absolute', inset:'10px', borderRadius:'50%', border:'1px solid rgba(201,168,76,0.1)' }} />
              {/* Glass fill */}
              <div style={{ position:'absolute', inset:0, borderRadius:'50%', background:'linear-gradient(145deg,rgba(201,168,76,0.07) 0%,rgba(10,16,28,0.9) 100%)', backdropFilter:'blur(10px)' }} />
              {/* Logo image — padded to prevent clipping */}
              <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center', padding:'20px' }}>
                <img src="/logo.png" alt="National Bank of Ethiopia" style={{ width:'100%', height:'100%', objectFit:'contain' }} />
              </div>
            </div>
          </div>

          <div style={{ marginTop:'8px' }}>
            <div style={{ fontSize:'16px', fontWeight:'700', color:'#C9A84C', letterSpacing:'.1em', textTransform:'uppercase', marginBottom:'5px' }}>National Bank of Ethiopia</div>
            <div style={{ fontSize:'10px', color:'#2D3F52', letterSpacing:'.1em', textTransform:'uppercase' }}>Blockchain Intelligence Division</div>
          </div>
        </div>

        {/* WORKSPACE SELECTION */}
        <div style={{ width:'100%', background:'rgba(9,14,24,0.62)', border:'1px solid rgba(201,168,76,0.12)', borderRadius:'22px', padding:'40px 40px 44px', backdropFilter:'blur(20px)', boxShadow:'0 24px 80px rgba(0,0,0,0.4),inset 0 1px 0 rgba(201,168,76,0.07)', animation:'lp-cardIn .6s ease .15s both' }}>
          <div style={{ textAlign:'center', marginBottom:'34px' }}>
            <div style={{ display:'inline-flex', alignItems:'center', gap:'10px', marginBottom:'14px' }}>
              <div style={{ width:'36px', height:'1px', background:'linear-gradient(90deg,transparent,rgba(201,168,76,0.3))' }} />
              <span style={{ fontSize:'10px', color:'#5A4A1E', fontWeight:'700', letterSpacing:'.12em', textTransform:'uppercase' }}>Intelligence Gateway</span>
              <div style={{ width:'36px', height:'1px', background:'linear-gradient(90deg,rgba(201,168,76,0.3),transparent)' }} />
            </div>
            <div style={{ fontSize:'21px', fontWeight:'700', color:'#C4B48A', marginBottom:'9px', letterSpacing:'-.02em', lineHeight:1.3 }}>Unified Blockchain Intelligence Ecosystem</div>
            <div style={{ fontSize:'13px', color:'#3A4D60', letterSpacing:'.04em' }}>Select an operational workspace to continue</div>
          </div>
          <div style={{ display:'flex', gap:'22px', flexWrap:'wrap', justifyContent:'center' }}>
            <Card icon="🛡" title="AML Investigation Workspace" subtitle="Financial crime monitoring, placement & layering detection, integration analysis and real-time risk intelligence." features={['Transaction Table','Wallet Clusters','Placement Alerts','Layering Alerts','Integration Alerts']} buttonLabel="Enter Workspace →" onLaunch={()=>go('aml',onEnterAML)} delay={250} />
            <Card icon="⬡" title="Wallet Analysis Workspace" subtitle="Graph intelligence, wallet clustering, ownership registry and entity investigation platform." features={['Wallet Clustering','Ownership Registry','Transaction Mapping','Graph Intelligence']} disabled buttonLabel="Awaiting Integration" delay={350} />
          </div>
        </div>

        <div style={{ marginTop:'28px', fontSize:'11px', color:'#1A2535', letterSpacing:'.05em', textAlign:'center', animation:'lp-cardIn .6s ease .4s both' }}>
          © {new Date().getFullYear()} National Bank of Ethiopia &nbsp;·&nbsp; Classified Intelligence System &nbsp;·&nbsp; All Rights Reserved
        </div>
      </div>

      <div style={{ position:'absolute', bottom:0, left:0, right:0, height:'1px', background:'linear-gradient(90deg,transparent,rgba(201,168,76,0.12),transparent)', zIndex:2 }} />
    </div>
  );
}
