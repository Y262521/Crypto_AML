/**
 * EntityLink Component
 * 
 * Reusable component to make addresses and clusters clickable.
 * Shows analysis menu when clicked.
 */

const EntityLink = ({ 
    entityId, 
    entityType = 'address', // 'address' or 'cluster'
    displayText,
    onShowAnalysisMenu, // New: shows analysis menu
    onClick, // Legacy: direct click handler
    style = {},
    className = ''
}) => {
    const defaultStyle = {
        color: '#C9A84C',
        cursor: 'pointer',
        textDecoration: 'underline',
        textUnderlineOffset: '2px',
        fontFamily: 'monospace',
        fontSize: '12px',
        background: 'none',
        border: 'none',
        padding: 0,
        transition: 'color 0.2s',
        ...style
    };

    const handleClick = (e) => {
        e.stopPropagation();
        
        // Prefer analysis menu if available
        if (onShowAnalysisMenu) {
            onShowAnalysisMenu(entityId, entityType, e);
        } else if (onClick) {
            onClick(entityId, entityType);
        }
    };

    const truncateAddress = (addr) => {
        if (!addr) return '—';
        if (addr.length <= 20) return addr;
        return `${addr.slice(0, 10)}...${addr.slice(-8)}`;
    };

    return (
        <button
            type="button"
            onClick={handleClick}
            style={defaultStyle}
            className={className}
            title={`Analyze ${entityType}: ${entityId}`}
            onMouseEnter={(e) => {
                e.currentTarget.style.color = '#E2D9C8';
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.color = '#C9A84C';
            }}
        >
            {displayText || truncateAddress(entityId)}
        </button>
    );
};

export default EntityLink;
