import React from 'react';

const Loader = () => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
    <div style={{
      width: '48px', height: '48px', border: '4px solid #e2e8f0',
      borderTop: '4px solid #2563eb', borderRadius: '50%',
      animation: 'spin 0.8s linear infinite',
    }} />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    <p style={{ marginTop: '16px', color: '#64748b', fontWeight: '500', fontSize: '14px' }}>
      Loading blockchain data...
    </p>
  </div>
);

export default Loader;
