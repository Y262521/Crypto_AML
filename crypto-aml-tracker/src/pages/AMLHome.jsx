import { useEffect, useRef, useState } from 'react';

const CSS = `
  @keyframes aml-spin   { to { transform: rotate(360deg); } }
  @keyframes aml-spinR  { to { transform: rotate(-360deg); } }
  @keyframes aml-pulse  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.85;transform:scale(1.03)} }
  @keyframes aml-fadeUp { from{opacity:0;transform:translateY(18px)} to{opacity:1;transform:translateY(0)} }
  @keyframes aml-float  { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
  @keyframes aml-glow   { 0%,100%{opacity:.5} 50%{opacity:1} }
  @keyframes aml-bar    { from{width:0} to{width:var(--w)} }
  @keyframes aml-ring   { 0%,100%{opacity:.35;transform:scale(1)} 50%{opacity:.7;transform:scale(1.04)} }
  @keyframes aml-scan   { 0%{top:0;opacity:0} 10%{opacity:1} 90%{opacity:1} 100%{top:100%;opacity:0} }

  .aml-home {
    min-height: 100vh;
    background: linear-gradient(165deg,#080E1C 0%,#0A1220 30%,#0D1830 60%,#070C18 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: 'Inter','Segoe UI',system-ui,sans-serif;
    padding: 40px 24px;
    position: relative;
    overflow: hidden;
    box-sizing: border-box;
  }

  .aml-content {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    max-width: 1000px;
    gap: 48px;
  }

  .aml-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    text-align: center;
  }

  .aml-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    background: rgba(201,168,76,0.08);
    border: 1px solid rgba(201,168,76,0.22);
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    color: #C9A84C;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    animation: aml-fadeUp .6s ease .1s both;
  }

  .aml-title {
    font-size: clamp(28px, 5vw, 48px);
    font-weight: 800;
    color: #E2D9C8;
    line-height: 1.15;
    letter-spacing: -0.02em;
    animation: aml-fadeUp .6s ease .2s both;
  }

  .aml-title span {
    background: linear-gradient(135deg, #C9A84C, #E2C97E, #B8963E);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .aml-subtitle {
    font-size: 15px;
    color: #6B7E94;
    max-width: 560px;
    line-height: 1.7;
    animation: aml-fadeUp .6s ease .3s both;
  }

  .aml-cta-row {
    display: flex;
    gap: 14px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
    animation: aml-fadeUp .6s ease .4s both;
  }

  .aml-btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 14px 32px;
    background: linear-gradient(135deg, rgba(201,168,76,0.18), rgba(201,168,76,0.10));
    border: 1px solid rgba(201,168,76,0.45);
    border-radius: 12px;
    color: #E2C97E;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.04em;
    transition: all .25s ease;
    box-shadow: 0 0 24px rgba(201,168,76,0.08);
    position: relative;
    overflow: hidden;
  }
  .aml-btn-primary::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(201,168,76,0.12), transparent);
    opacity: 0;
    transition: opacity .25s;
  }
  .aml-btn-primary:hover {
    border-color: rgba(201,168,76,0.7);
    box-shadow: 0 0 40px rgba(201,168,76,0.18), 0 8px 32px rgba(0,0,0,0.3);
    transform: translateY(-2px);
  }
  .aml-btn-primary:hover::before { opacity: 1; }

  .aml-btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 14px 24px;
    background: transparent;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    color: #8A9DB5;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all .2s ease;
  }
  .aml-btn-secondary:hover {
    border-color: rgba(255,255,255,0.16);
    color: #C8B98A;
    background: rgba(255,255,255,0.03);
  }

  .aml-stats {
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    justify-content: center;
    animation: aml-fadeUp .6s ease .5s both;
  }

  .aml-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }
  .aml-stat-num {
    font-size: 22px;
    font-weight: 800;
    color: #C9A84C;
  }
  .aml-stat-label {
    font-size: 11px;
    color: #4B5E72;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .aml-stat-divider {
    width: 1px;
    height: 36px;
    background: rgba(201,168,76,0.12);
    align-self: center;
  }

  .aml-features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    width: 100%;
    animation: aml-fadeUp .6s ease .55s both;
  }

  .aml-feature-card {
    background: linear-gradient(145deg, rgba(13,22,40,0.95), rgba(10,16,28,0.98));
    border: 1px solid rgba(201,168,76,0.10);
    border-radius: 16px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: all .25s ease;
    position: relative;
    overflow: hidden;
  }
  .aml-feature-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(201,168,76,0.2), transparent);
    opacity: 0;
    transition: opacity .25s;
  }
  .aml-feature-card:hover {
    border-color: rgba(201,168,76,0.25);
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.4), 0 0 20px rgba(201,168,76,0.05);
  }
  .aml-feature-card:hover::before { opacity: 1; }

  .aml-feature-icon {
    width: 42px;
    height: 42px;
    border-radius: 10px;
    background: rgba(201,168,76,0.08);
    border: 1px solid rgba(201,168,76,0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
  }

  .aml-feature-title {
    font-size: 14px;
    font-weight: 700;
    color: #C8B98A;
  }

  .aml-feature-desc {
    font-size: 12px;
    color: #5A7080;
    line-height: 1.65;
  }

  .aml-feature-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 4px;
  }

  .aml-tag {
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(201,168,76,0.07);
    color: #8A6E2A;
    border: 1px solid rgba(201,168,76,0.14);
    font-weight: 600;
  }

  .aml-pipeline {
    display: flex;
    align-items: center;
    gap: 0;
    flex-wrap: wrap;
    justify-content: center;
    width: 100%;
    animation: aml-fadeUp .6s ease .6s both;
  }

  .aml-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 16px 24px;
    background: linear-gradient(145deg, rgba(13,22,40,0.95), rgba(10,16,28,0.98));
    border: 1px solid rgba(201,168,76,0.10);
    border-radius: 14px;
    min-width: 140px;
    transition: all .2s;
  }
  .aml-stage:hover {
    border-color: rgba(201,168,76,0.28);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  }

  .aml-stage-num {
    font-size: 10px;
    font-weight: 700;
    color: #4B5E72;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .aml-stage-icon { font-size: 22px; }

  .aml-stage-name {
    font-size: 13px;
    font-weight: 700;
    color: #C8B98A;
  }

  .aml-stage-desc {
    font-size: 10px;
    color: #4B5E72;
    text-align: center;
    line-height: 1.5;
  }

  .aml-arrow {
    font-size: 18px;
    color: rgba(201,168,76,0.3);
    padding: 0 8px;
    flex-shrink: 0;
  }

  .aml-footer {
    font-size: 11px;
    color: #1A2535;
    letter-spacing: 0.05em;
    text-align: center;
    animation: aml-fadeUp .6s ease .7s both;
  }

  @media (max-width: 640px) {
    .aml-features { grid-template-columns: 1fr; }
    .aml-pipeline { flex-direction: column; }
    .aml-arrow { transform: rotate(90deg); }
    .aml-stats { gap: 20px; }
    .aml-stat-divider { display: none; }
  }
`;

function BgCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext('2d'); let id;
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize();
    window.addEventListener('resize', resize);
    const nodes = Array.from({ length: 50 }, () => ({
      x: Math.random() * c.width, y: Math.random() * c.height,
      vx: (Math.random() - .5) * .14, vy: (Math.random() - .5) * .14,
      r: Math.random() * 1.4 + .5,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > c.width) n.vx *= -1;
        if (n.y < 0 || n.y > c.height) n.vy *= -1;
      });
      for (let i = 0; i < nodes.length; i++)
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 110) {
            ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(201,168,76,${.05 * (1 - d / 110)})`; ctx.lineWidth = .5; ctx.stroke();
          }
        }
      nodes.forEach(n => { ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fillStyle = 'rgba(201,168,76,0.18)'; ctx.fill(); });
      id = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(id); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={ref} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: .6 }} />;
}

const FEATURES = [
  {
    icon: '🛡',
    title: 'Placement Detection',
    desc: 'Identify structuring, smurfing, and micro-funding patterns at the point of entry into the financial system.',
    tags: ['Structuring', 'Smurfing', 'Micro-funding'],
  },
  {
    icon: '⧉',
    title: 'Layering Analysis',
    desc: 'Trace complex transaction chains, bridge hops, mixing interactions, and shell wallet networks.',
    tags: ['Chain Hopping', 'Bridge Detection', 'Shell Wallets'],
  },
  {
    icon: '💰',
    title: 'Integration Alerts',
    desc: 'Detect convergence, dormancy breaks, terminal exits, and reaggregation at the final stage.',
    tags: ['Convergence', 'Dormancy', 'Terminal Nodes'],
  },
  {
    icon: '⬡',
    title: 'Wallet Clustering',
    desc: 'Group wallets controlled by the same entity using 10 parallel heuristic algorithms.',
    tags: ['Union-Find', 'Heuristics', 'Owner Registry'],
  },
  {
    icon: '🕸',
    title: 'Graph Intelligence',
    desc: 'Visualize transaction networks, investigate addresses, and trace fund flows in real time.',
    tags: ['Neo4j', 'ReactFlow', 'Live Graph'],
  },
  {
    icon: '🔗',
    title: 'Chain of Custody',
    desc: 'Full audit trail from placement origin through layering hops to final integration exit point.',
    tags: ['Audit Trail', 'Feedback Loop', 'Risk Score'],
  },
];

const STAGES = [
  { num: 'Stage 01', icon: '🛡', name: 'Placement', desc: 'Entry point detection' },
  { num: 'Stage 02', icon: '⧉', name: 'Layering', desc: 'Obfuscation tracing' },
  { num: 'Stage 03', icon: '💰', name: 'Integration', desc: 'Exit point analysis' },
];

export default function AMLHome({ onEnterDashboard, onBack }) {
  const [entering, setEntering] = useState(false);

  const handleEnter = () => {
    setEntering(true);
    setTimeout(() => onEnterDashboard(), 1200);
  };

  return (
    <div className="aml-home">
      <style>{CSS}</style>
      <BgCanvas />

      {/* Ambient glows */}
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 100% 60% at 50% 0%,rgba(201,168,76,0.05) 0%,transparent 60%)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 50% 40% at 20% 80%,rgba(96,165,250,0.03) 0%,transparent 50%)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(90deg,transparent,rgba(201,168,76,0.3),transparent)', zIndex: 2 }} />

      {/* Back button — removed */}

      {/* Loading overlay */}
      {entering && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: '#080E1C', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '24px' }}>
          <div style={{ position: 'relative', width: '100px', height: '100px' }}>
            <div style={{ position: 'absolute', inset: 0, border: '1.5px solid rgba(201,168,76,0.2)', borderTopColor: '#C9A84C', borderRadius: '50%', animation: 'aml-spin 1.2s linear infinite' }} />
            <div style={{ position: 'absolute', inset: '14px', border: '1px solid rgba(201,168,76,0.1)', borderBottomColor: 'rgba(201,168,76,0.5)', borderRadius: '50%', animation: 'aml-spinR 1.8s linear infinite' }} />
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <img src="/logo.png" alt="NBE" style={{ width: '48px', height: '48px', objectFit: 'contain', animation: 'aml-pulse 2s ease-in-out infinite' }} />
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: '#C9A84C', fontWeight: '700', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Loading AML Dashboard</div>
            <div style={{ fontSize: '12px', color: '#2D3F52', marginTop: '4px' }}>National Bank of Ethiopia</div>
          </div>
        </div>
      )}

      <div className="aml-content">

        {/* ── HERO ── */}
        <div className="aml-hero">
          {/* Logo — LandingPage style */}
          <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', animation: 'aml-float 5.5s ease-in-out infinite' }}>
            <div style={{ position: 'absolute', width: '280px', height: '280px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(201,168,76,0.08) 0%,transparent 70%)', pointerEvents: 'none', animation: 'aml-glow 4s ease-in-out infinite' }} />
            <div style={{ width: '200px', height: '200px', position: 'relative' }}>
              <div style={{ position: 'absolute', inset: '-18px', borderRadius: '50%', border: '1px solid rgba(201,168,76,0.08)', animation: 'aml-ring 3.5s ease-in-out infinite', pointerEvents: 'none' }} />
              <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '1.5px solid rgba(201,168,76,0.30)', boxShadow: '0 0 40px rgba(201,168,76,0.10),inset 0 0 30px rgba(201,168,76,0.04)' }} />
              <div style={{ position: 'absolute', inset: '10px', borderRadius: '50%', border: '1px solid rgba(201,168,76,0.10)' }} />
              <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'linear-gradient(145deg,rgba(201,168,76,0.07) 0%,rgba(8,14,28,0.9) 100%)', backdropFilter: 'blur(10px)' }} />
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '18px' }}>
                <img src="/logo.png" alt="National Bank of Ethiopia" style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: '50%' }} />
              </div>
            </div>
          </div>

          {/* NBE name */}
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '15px', fontWeight: '700', color: '#C9A84C', letterSpacing: '.1em', textTransform: 'uppercase' }}>National Bank of Ethiopia</div>
            <div style={{ fontSize: '10px', color: '#2D3F52', letterSpacing: '.1em', textTransform: 'uppercase', marginTop: '3px' }}>Blockchain Intelligence Division</div>
          </div>

          <h1 className="aml-title">
            <span>AML Investigation</span>
          </h1>

          <p className="aml-subtitle">
            A real-time blockchain intelligence platform for detecting, tracing, and investigating
            money laundering across all three stages — Placement, Layering, and Integration.
          </p>

          <div className="aml-cta-row">
            <button className="aml-btn-primary" onClick={handleEnter}>
              <span style={{ fontSize: '16px' }}>⚡</span>
              Go to Dashboard
              <span style={{ fontSize: '14px', opacity: 0.7 }}>→</span>
            </button>
          </div>

        </div>

        {/* ── FEATURES ── */}
        <div style={{ width: '100%' }}>
          <div style={{ textAlign: 'center', marginBottom: '20px', animation: 'aml-fadeUp .6s ease .55s both' }}>
            <div style={{ fontSize: '10px', fontWeight: '700', color: '#4B5E72', letterSpacing: '0.12em', textTransform: 'uppercase' }}>System Capabilities</div>
          </div>
          <div className="aml-features">
            {FEATURES.map((f) => (
              <div key={f.title} className="aml-feature-card">
                <div className="aml-feature-icon">{f.icon}</div>
                <div className="aml-feature-title">{f.title}</div>
                <div className="aml-feature-desc">{f.desc}</div>
                <div className="aml-feature-tags">
                  {f.tags.map(t => <span key={t} className="aml-tag">{t}</span>)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── FOOTER ── */}
        <div className="aml-footer">
          © {new Date().getFullYear()} National Bank of Ethiopia &nbsp;·&nbsp; AML Investigation System &nbsp;·&nbsp; Classified Intelligence Platform
        </div>

      </div>

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(90deg,transparent,rgba(201,168,76,0.15),transparent)', zIndex: 2 }} />
    </div>
  );
}
