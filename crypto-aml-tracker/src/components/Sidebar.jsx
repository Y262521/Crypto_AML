import React from 'react';
const SECTIONS = [
  { title: 'Overview', items: [{ id:'feed', label:'Transaction Table', icon:'▦' }, { id:'clusters', label:'Wallet Clusters', icon:'⬡' }] },
  { title: 'AML Analysis', items: [{ id:'placement', label:'Placement Alerts', icon:'⟁' }, { id:'layering', label:'Layering Alerts', icon:'⧉' }, { id:'integration', label:'Integration Alerts', icon:'💰' }] },
];
const Sidebar = ({ activePage, onNavigate, onHome }) => (
  <div style={{ width:'220px', minWidth:'220px', height:'100vh', background:'#0F1829', display:'flex', flexDirection:'column', borderRight:'1px solid rgba(201,168,76,0.14)', flexShrink:0 }}>
    <div style={{ padding:'20px 16px 16px', borderBottom:'1px solid rgba(201,168,76,0.14)', display:'flex', flexDirection:'column', alignItems:'center', gap:'10px' }}>
      <img src="/logo.png" alt="NBE" style={{ width:'52px', height:'52px', objectFit:'contain' }} />
      <div style={{ textAlign:'center' }}>
        <div style={{ fontSize:'10px', fontWeight:'700', color:'#C9A84C', letterSpacing:'0.08em', textTransform:'uppercase' }}>AML Investigation</div>
        <div style={{ fontSize:'9px', color:'#64748B', marginTop:'2px' }}>National Bank of Ethiopia</div>
      </div>
    </div>
    {onHome && (
      <div style={{ padding:'12px 12px 4px' }}>
        <button onClick={onHome} style={{ width:'100%', display:'flex', alignItems:'center', gap:'8px', padding:'8px 12px', background:'rgba(201,168,76,0.07)', color:'#C9A84C', border:'1px solid rgba(201,168,76,0.14)', borderRadius:'8px', cursor:'pointer', fontSize:'11px', fontWeight:'600' }} onMouseEnter={e=>e.currentTarget.style.background='rgba(201,168,76,0.14)'} onMouseLeave={e=>e.currentTarget.style.background='rgba(201,168,76,0.07)'}>← Platform Home</button>
      </div>
    )}
    <nav style={{ padding:'8px 10px', flex:1, overflowY:'auto' }}>
      {SECTIONS.map(({ title, items }) => (
        <div key={title} style={{ marginBottom:'4px' }}>
          <div style={{ fontSize:'9px', fontWeight:'700', color:'#64748B', textTransform:'uppercase', letterSpacing:'0.1em', padding:'10px 10px 4px' }}>{title}</div>
          {items.map(item => {
            const active = activePage === item.id;
            return (
              <button key={item.id} onClick={() => onNavigate(item.id)} style={{ width:'100%', display:'flex', alignItems:'center', gap:'9px', padding:'9px 12px', marginBottom:'2px', background: active ? 'rgba(201,168,76,0.12)' : 'transparent', color: active ? '#E2C97E' : '#CBD5E1', border: active ? '1px solid rgba(201,168,76,0.22)' : '1px solid transparent', borderRadius:'8px', cursor:'pointer', fontSize:'12px', fontWeight: active ? '600' : '400', textAlign:'left', transition:'all 0.15s' }} onMouseEnter={e=>{ if(!active) e.currentTarget.style.background='rgba(255,255,255,0.04)'; }} onMouseLeave={e=>{ if(!active) e.currentTarget.style.background='transparent'; }}>
                <span style={{ fontSize:'14px', opacity: active ? 1 : 0.65 }}>{item.icon}</span>
                {item.label}
              </button>
            );
          })}
        </div>
      ))}
    </nav>
    <div style={{ padding:'10px 16px', borderTop:'1px solid rgba(201,168,76,0.14)', display:'flex', alignItems:'center', gap:'6px' }}>
      <div style={{ width:'6px', height:'6px', borderRadius:'50%', background:'#22c55e', boxShadow:'0 0 4px #22c55e' }} />
      <span style={{ fontSize:'10px', color:'#64748B' }}>Ethereum Mainnet</span>
    </div>
  </div>
);
export default Sidebar;
