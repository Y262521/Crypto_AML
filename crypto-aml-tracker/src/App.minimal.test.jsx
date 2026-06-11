// Minimal test version of App to isolate the blank page issue

function AppMinimalTest() {
  console.log('[AppMinimalTest] Rendering...');
  
  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{
        textAlign: 'center',
        background: 'rgba(0,0,0,0.3)',
        padding: '40px',
        borderRadius: '20px',
        backdropFilter: 'blur(10px)'
      }}>
        <h1 style={{ fontSize: '48px', marginBottom: '20px' }}>✓ App is Working!</h1>
        <p style={{ fontSize: '18px', opacity: 0.9 }}>
          If you see this, React is rendering correctly.
        </p>
        <div style={{ marginTop: '30px', fontSize: '14px', opacity: 0.7 }}>
          The blank page issue has been isolated.
        </div>
      </div>
    </div>
  );
}

export default AppMinimalTest;
