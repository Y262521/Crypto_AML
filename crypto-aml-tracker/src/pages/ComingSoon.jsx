export default function ComingSoon({ onBack }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100%', gap:'24px', background:'#0F1829', fontFamily:"'Inter', system-ui, sans-serif" }}>
      <img src="/logo.png" alt="NBE" style={{ width:'72px', height:'72px', objectFit:'contain', opacity:0.85 }} />
      <div style={{ textAlign:'center', maxWidth:'420px' }}>
        <div style={{ display:'inline-block', fontSize:'10px', fontWeight:'700', color:'#C9A84C', letterSpacing:'0.14em', textTransform:'uppercase', background:'rgba(201,168,76,0.08)', border:'1px solid rgba(201,168,76,0.2)', borderRadius:'999px', padding:'4px 14px', marginBottom:'18px' }}>Awaiting Integration</div>
        <h2 style={{ fontSize:'24px', fontWeight:'700', color:'#E2E8F0', marginBottom:'12px' }}>Wallet Analysis Workspace</h2>
        <p style={{ fontSize:'14px', color:'#64748B', lineHeight:1.7, marginBottom:'28px' }}>This workspace is being developed by a separate team and will be integrated in a future release. All AML investigation modules remain fully operational.</p>
        {onBack && <button onClick={onBack} style={{ padding:'10px 24px', borderRadius:'8px', background:'rgba(201,168,76,0.1)', border:'1px solid rgba(201,168,76,0.25)', color:'#C9A84C', fontSize:'13px', fontWeight:'600', cursor:'pointer' }} onMouseEnter={e=>e.currentTarget.style.background='rgba(201,168,76,0.18)'} onMouseLeave={e=>e.currentTarget.style.background='rgba(201,168,76,0.1)'}>← Return to Platform Home</button>}
      </div>
    </div>
  );
}
