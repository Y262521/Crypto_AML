# Analysis Menu - User Guide

## Overview

The Analysis Menu provides quick access to 5 on-chain intelligence analysis types when clicking any address or cluster in the system.

## 5 Analysis Types

1. **💰 Market Value Analysis** (✅ Implemented)
   - Portfolio value and asset holdings
   - Token balances and USD values
   - Historical value charts
   - Intelligence flags

2. **📈 Profit Ratio Analysis** (🔒 Coming Soon)
   - Realized and unrealized gains
   - Cost basis tracking
   - ROI calculations

3. **🔄 Exchange Net Flow** (🔒 Coming Soon)
   - Deposits to exchanges
   - Withdrawals from exchanges
   - Net flow analysis

4. **🌊 Holder Wave Analysis** (🔒 Coming Soon)
   - Holding patterns
   - Movement frequency
   - Dormancy periods

5. **🕸️ Active Address Edge Network** (🔒 Coming Soon)
   - Network connections
   - Transaction patterns
   - Address relationships

## How to Use

### Step 1: Click an Address or Cluster

From any page (Placement, Layering, Integration, Clusters), click on an address or cluster.

### Step 2: Analysis Menu Appears

A dropdown menu appears showing all 5 analysis options.

### Step 3: Select Analysis Type

Click on "Market Value Analysis" (or any other available option).

### Step 4: View Analysis

The Entity Intelligence Workspace opens on the right side with the selected analysis tab active.

## Usage Examples

### Example 1: From Placement Page

```jsx
// In Placement.jsx
export default function Placement({ onShowAnalysisMenu }) {
  return (
    <div>
      {alerts.map(alert => (
        <div key={alert.entity_id}>
          {/* Clickable address - shows analysis menu */}
          <button 
            onClick={(e) => onShowAnalysisMenu(alert.entity_id, 'address', e)}
            style={{ color: '#C9A84C', cursor: 'pointer' }}
          >
            {alert.entity_id}
          </button>
        </div>
      ))}
    </div>
  );
}
```

### Example 2: Using EntityLink Component

```jsx
import EntityLink from '../components/common/EntityLink';

export default function MyPage({ onShowAnalysisMenu }) {
  return (
    <div>
      {/* Simple usage */}
      <EntityLink
        entityId="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        entityType="address"
        onShowAnalysisMenu={onShowAnalysisMenu}
      />
      
      {/* With custom display text */}
      <EntityLink
        entityId="cluster_123"
        entityType="cluster"
        displayText="View Cluster Analysis"
        onShowAnalysisMenu={onShowAnalysisMenu}
      />
    </div>
  );
}
```

### Example 3: In a Table Row

```jsx
<table>
  <tbody>
    {data.map(row => (
      <tr key={row.id}>
        <td>
          <EntityLink
            entityId={row.address}
            entityType="address"
            onShowAnalysisMenu={onShowAnalysisMenu}
          />
        </td>
        <td>{row.value}</td>
        <td>
          {/* Alternative: Direct button */}
          <button 
            onClick={(e) => onShowAnalysisMenu(row.address, 'address', e)}
          >
            🔍 Analyze
          </button>
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

## Menu Features

### Smart Positioning
- Menu automatically adjusts position to stay on screen
- Appears near the click location
- Avoids going off-screen edges

### Keyboard Support
- **ESC** key closes the menu
- Click outside to dismiss

### Visual Feedback
- Implemented options are highlighted
- Coming Soon options are dimmed
- Hover effects on available options

### Entity Context
- Shows entity type (Address or Cluster)
- Displays entity ID
- Remembers source page

## Integration Checklist

To add analysis menu to a new page:

- [ ] Add `onShowAnalysisMenu` prop to page component
- [ ] Pass prop from App.jsx
- [ ] Make addresses/clusters clickable
- [ ] Call `onShowAnalysisMenu(entityId, entityType, event)` on click
- [ ] Test menu appears and works

## Current Implementation Status

### ✅ Fully Implemented
- Analysis menu component
- Menu positioning logic
- Keyboard shortcuts
- Click-outside-to-close
- Market Value Analysis tab
- Historical value charts
- Asset holdings table
- Intelligence flags

### ✅ Integrated Pages
- Placement
- Layering
- Integration
- Clusters

### 🔒 Coming Soon
- Profit Ratio Analysis
- Exchange Net Flow
- Holder Wave Analysis
- Active Address Edge Network

## Troubleshooting

### Menu doesn't appear
**Check**:
1. `onShowAnalysisMenu` prop is passed to page
2. Event object is passed to the function
3. No JavaScript errors in console

### Menu appears in wrong position
**Solution**: The menu auto-adjusts, but you can modify position logic in `App.jsx`

### Can't select analysis option
**Check**: Only "Market Value Analysis" is currently implemented. Other options show "Coming Soon".

### Workspace doesn't open
**Check**:
1. Analysis option is implemented (green, not dimmed)
2. No console errors
3. Backend is running

## Advanced Usage

### Custom Menu Trigger

```jsx
// Custom button with icon
<button
  onClick={(e) => onShowAnalysisMenu(address, 'address', e)}
  style={{
    padding: '6px 12px',
    background: 'rgba(201,168,76,0.1)',
    border: '1px solid rgba(201,168,76,0.2)',
    borderRadius: '6px',
    cursor: 'pointer'
  }}
>
  🔍 Analyze Address
</button>
```

### Context Menu (Right-Click)

```jsx
<div
  onContextMenu={(e) => {
    e.preventDefault();
    onShowAnalysisMenu(address, 'address', e);
  }}
  style={{ cursor: 'context-menu' }}
>
  {address}
</div>
```

### Inline Analysis Link

```jsx
<span>
  Suspicious activity from{' '}
  <EntityLink
    entityId={address}
    entityType="address"
    onShowAnalysisMenu={onShowAnalysisMenu}
  />
  {' '}detected.
</span>
```

## Best Practices

1. **Always pass the event object** - Needed for positioning
2. **Use EntityLink component** - Consistent styling and behavior
3. **Provide entity type** - 'address' or 'cluster'
4. **Test on different screen sizes** - Menu adjusts automatically
5. **Add hover effects** - Improve user experience

## Future Enhancements

### Planned Features
- [ ] Pin menu to keep it open
- [ ] Recent analysis history
- [ ] Favorite analysis types
- [ ] Keyboard navigation (arrow keys)
- [ ] Quick actions (copy address, export data)
- [ ] Comparison mode (analyze multiple entities)

### Upcoming Analysis Types
- [ ] Profit Ratio Analysis (Q2 2026)
- [ ] Exchange Net Flow (Q2 2026)
- [ ] Holder Wave Analysis (Q3 2026)
- [ ] Address Network (Q3 2026)

## Support

For issues or questions:
1. Check this guide
2. Review `MVA_IMPLEMENTATION.md`
3. Check browser console for errors
4. Verify backend is running
5. Test with known addresses

---

**Quick Reference**:
- Click address → Menu appears → Select analysis → View results
- ESC to close menu
- Click outside to dismiss
- Only Market Value currently available
