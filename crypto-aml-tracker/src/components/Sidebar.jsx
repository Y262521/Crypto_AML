import React from 'react';

const navItems = [
    { id: 'feed', label: 'Transaction Table', icon: '▦' },
    // { id: 'analytics', label: 'Analytics', icon: '◉' },
    { id: 'placement', label: 'Placement Alerts', icon: '⟁' },
    { id: 'layering', label: 'Layering Alerts', icon: '⧉' },
    { id: 'clusters', label: 'Wallet Clusters', icon: '⬡' },
    { id: 'graph', label: 'Transaction Network', icon: '❋' },
];

const Sidebar = ({ activePage, onNavigate }) => {
    return (
        <div style={{
            width: '220px',
            minWidth: '220px',
            height: '100vh',
            background: '#0d1b2e',
            display: 'flex',
            flexDirection: 'column',
            borderRight: '1px solid #1e2d45',
            flexShrink: 0,
        }}>
            {/* Logo */}
            <div style={{
                padding: '20px 16px',
                borderBottom: '1px solid #1e2d45',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '10px',
            }}>
                <img
                    src="/logo.png"
                    alt="Logo"
                    style={{ width: '200px', height: '200px', objectFit: 'contain' }}
                    onError={e => { e.target.style.display = 'none'; }}
                />
                <div style={{ color: '#f7fff5ff', fontSize: '20px', textAlign: 'center', lineHeight: 1.4 }}>
                    Wallet Cluster Tracker
                </div>
            </div>

            {/* Nav */}
            <nav style={{ padding: '16px 10px', flex: 1 }}>
                {navItems.map(item => (
                    <button
                        key={item.id}
                        onClick={() => onNavigate(item.id)}
                        style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            padding: '12px 14px',
                            marginBottom: '6px',
                            background: activePage === item.id ? '#1d4ed8' : 'transparent',
                            color: activePage === item.id ? '#fff' : '#f7fff5ff',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontSize: '13px',
                            fontWeight: activePage === item.id ? '600' : '400',
                            textAlign: 'left',
                        }}
                        onMouseEnter={e => { if (activePage !== item.id) e.currentTarget.style.background = '#1e2d45'; }}
                        onMouseLeave={e => { if (activePage !== item.id) e.currentTarget.style.background = 'transparent'; }}
                    >
                        <span style={{ fontSize: '16px' }}>{item.icon}</span>
                        {item.label}
                    </button>
                ))}
            </nav>

            <div style={{ padding: '14px 16px', borderTop: '1px solid #1e2d45', color: '#334155', fontSize: '11px' }}>
                Ethereum Mainnet
            </div>
        </div>
    );
};

export default Sidebar;
