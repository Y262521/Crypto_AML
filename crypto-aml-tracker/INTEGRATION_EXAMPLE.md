# Entity Intelligence Workspace Integration Example

## Quick Integration Guide

### Step 1: Add the Prop to Your Page Component

Your page component should accept an `onOpenEntityWorkspace` prop:

```jsx
export default function YourPage({ onOpenEntityWorkspace }) {
  // Your existing code...
}
```

### Step 2: Make Addresses/Clusters Clickable

#### Option A: Using EntityLink Component (Recommended)

```jsx
import EntityLink from '../components/common/EntityLink';

// In your render:
<EntityLink
  entityId={address}
  entityType="address"
  onClick={onOpenEntityWorkspace}
/>

// For clusters:
<EntityLink
  entityId={clusterId}
  entityType="cluster"
  onClick={onOpenEntityWorkspace}
  displayText="View Cluster"
/>
```

#### Option B: Direct Button/Link

```jsx
<button 
  onClick={() => onOpenEntityWorkspace(entityId, 'cluster')}
  style={{ 
    color: '#C9A84C', 
    cursor: 'pointer',
    textDecoration: 'underline' 
  }}
>
  {entityId}
</button>
```

### Step 3: Update App.jsx (Already Done)

The App.jsx already passes `onOpenEntityWorkspace` to all pages:

```jsx
<Placement 
  onNavigateToGraph={(address) => navigate('graph', { address })} 
  onOpenEntityWorkspace={(entityId, entityType) => 
    openEntityWorkspace(entityId, entityType, 'Placement')
  } 
/>
```

## Complete Example: Adding to a Table Row

```jsx
import EntityLink from '../components/common/EntityLink';

export default function MyAMLPage({ onOpenEntityWorkspace }) {
  const [alerts, setAlerts] = useState([]);

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Entity</th>
            <th>Type</th>
            <th>Risk Score</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map(alert => (
            <tr key={alert.entity_id}>
              <td>
                {/* Clickable entity - opens intelligence workspace */}
                <EntityLink
                  entityId={alert.entity_id}
                  entityType={alert.entity_type}
                  onClick={onOpenEntityWorkspace}
                />
              </td>
              <td>{alert.entity_type}</td>
              <td>{alert.risk_score}</td>
              <td>
                <button 
                  onClick={() => onOpenEntityWorkspace(
                    alert.entity_id, 
                    alert.entity_type
                  )}
                >
                  🔍 Investigate
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

## Example: Adding to Placement Page

Here's how to add intelligence workspace links to the Placement page:

```jsx
// In the entity column of your alert table:
<div style={{ minWidth: 0 }}>
  <div style={{ fontSize: '10px', fontWeight: '700', color: '#4B5E72' }}>
    {isCluster ? '🔗 Cluster' : '💼 Address'}
  </div>
  
  {/* Entity name */}
  <div style={{ fontSize: '13px', fontWeight: '700', color: '#E2D9C8' }}>
    {alert.entity_name || 'Unknown'}
  </div>
  
  {/* Clickable entity ID - opens intelligence workspace */}
  <EntityLink
    entityId={alert.entity_id}
    entityType={alert.entity_type}
    onClick={onOpenEntityWorkspace}
    style={{ fontSize: '11px' }}
  />
  
  {/* Additional action button */}
  <button
    onClick={() => onOpenEntityWorkspace(alert.entity_id, alert.entity_type)}
    style={{
      marginTop: '8px',
      padding: '4px 10px',
      background: 'rgba(201,168,76,0.1)',
      border: '1px solid rgba(201,168,76,0.2)',
      borderRadius: '6px',
      color: '#C9A84C',
      fontSize: '11px',
      cursor: 'pointer'
    }}
  >
    📊 View Portfolio
  </button>
</div>
```

## Example: Adding to Cluster Details Modal

```jsx
function ClusterDetailsModal({ cluster, onOpenEntityWorkspace }) {
  return (
    <div className="modal">
      <h2>Cluster Details</h2>
      
      {/* Cluster ID with intelligence link */}
      <div>
        <label>Cluster ID:</label>
        <EntityLink
          entityId={cluster.cluster_id}
          entityType="cluster"
          onClick={onOpenEntityWorkspace}
        />
      </div>
      
      {/* Member addresses */}
      <div>
        <label>Member Addresses:</label>
        <ul>
          {cluster.addresses.map(addr => (
            <li key={addr}>
              <EntityLink
                entityId={addr}
                entityType="address"
                onClick={onOpenEntityWorkspace}
              />
            </li>
          ))}
        </ul>
      </div>
      
      {/* Action button */}
      <button 
        onClick={() => onOpenEntityWorkspace(cluster.cluster_id, 'cluster')}
      >
        🔍 Open Intelligence Workspace
      </button>
    </div>
  );
}
```

## Styling Tips

### Professional AML Look

```jsx
const entityLinkStyle = {
  color: '#C9A84C',
  fontFamily: 'monospace',
  fontSize: '12px',
  cursor: 'pointer',
  textDecoration: 'underline',
  textUnderlineOffset: '2px',
  background: 'none',
  border: 'none',
  padding: 0,
  transition: 'color 0.2s',
};

const entityLinkHoverStyle = {
  color: '#E2D9C8',
};
```

### Intelligence Button

```jsx
const intelligenceButtonStyle = {
  padding: '6px 14px',
  background: 'rgba(201,168,76,0.08)',
  border: '1px solid rgba(201,168,76,0.2)',
  borderRadius: '8px',
  color: '#C9A84C',
  fontSize: '12px',
  fontWeight: '600',
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  transition: 'all 0.2s',
};
```

## Testing Your Integration

1. **Click an entity** - Should open the right-side drawer
2. **Navigate to Market Value tab** - Should show portfolio data
3. **Close the workspace** - Should return to your page without navigation
4. **Click another entity** - Should update the workspace content

## Common Patterns

### Pattern 1: Inline Entity Link
```jsx
<span>
  Suspicious activity detected from{' '}
  <EntityLink 
    entityId={address} 
    entityType="address" 
    onClick={onOpenEntityWorkspace} 
  />
</span>
```

### Pattern 2: Entity Badge with Intelligence
```jsx
<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
  <span style={{ 
    padding: '4px 8px', 
    background: '#1a1a2e', 
    borderRadius: '6px',
    fontFamily: 'monospace',
    fontSize: '11px'
  }}>
    {truncateAddress(entityId)}
  </span>
  <button 
    onClick={() => onOpenEntityWorkspace(entityId, 'address')}
    style={{ fontSize: '16px', cursor: 'pointer', border: 'none', background: 'none' }}
    title="Open Intelligence Workspace"
  >
    🔍
  </button>
</div>
```

### Pattern 3: Context Menu
```jsx
<div 
  onContextMenu={(e) => {
    e.preventDefault();
    onOpenEntityWorkspace(entityId, entityType);
  }}
  style={{ cursor: 'context-menu' }}
>
  {entityId}
</div>
```

## Troubleshooting

### Workspace Not Opening
- Check that `onOpenEntityWorkspace` prop is passed to your component
- Verify the prop is called with correct parameters: `(entityId, entityType)`
- Check browser console for errors

### Wrong Entity Type
- Ensure you're passing `'address'` or `'cluster'` as the second parameter
- Check that entity IDs are correctly identified

### Styling Issues
- The workspace uses fixed positioning and high z-index (1000)
- Ensure your page doesn't have conflicting z-index values
- The workspace is 85% width, max 1400px

## Next Steps

After integrating the Entity Intelligence Workspace:

1. Test with real addresses and clusters
2. Populate balance data using the update script
3. Customize the EntityLink styling to match your page
4. Add intelligence buttons to key investigation points
5. Consider adding keyboard shortcuts (e.g., Ctrl+I to open workspace)

## Questions?

See `MVA_IMPLEMENTATION.md` for full technical documentation.
