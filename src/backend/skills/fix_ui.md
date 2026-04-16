# SKILL: FIX_UI

## Stack
React 18 + TypeScript 5 + Tailwind + React Query v5 + Zustand + Vite + react-grid-layout

## Common Error Patterns

### TS2881 Nullish coalescing on non-nullable
```typescript
// BAD
const val = market.yes_percentage ?? 0 ?? fallback;

// GOOD
const val = market.yes_percentage ?? fallback;
// Or if chaining different types:
const val = (market.yes_percentage ?? 0) || fallback;
```

### Pydantic model_config in API responses
The backend uses Pydantic v2. API responses use camelCase from aliases.
Always check: does the frontend field name match the API alias?
```typescript
// Backend: yes_percentage (snake_case)
// Frontend fetch: market.yes_percentage ✓
// NOT: market.yesPercentage (unless alias set)
```

### WebSocket first-message auth pattern
```typescript
// POLYGOD pattern — token in first message, NOT in URL
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "auth",
    token: import.meta.env.VITE_INTERNAL_API_KEY
  }));
};
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === "auth_ok") { /* now connected */ }
};
```

### SSE streaming pattern
```typescript
const response = await fetch(`/api/debate/${marketId}/stream`, { method: "POST" });
const reader = response.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  for (const line of text.split('\n')) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      // handle data
    }
  }
}
```

### react-grid-layout missing CSS (widgets won't resize)
```typescript
// Must be in the component file or main.tsx
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
```

## Component Locations
- Market list: src/frontend/src/components/MarketList.tsx
- Debate floor: src/frontend/src/components/DebateFloor.tsx
- Live trades: src/frontend/src/components/LiveTradesFeed.tsx
- Settings: src/frontend/src/components/SettingsScreen.tsx
- System status: src/frontend/src/components/SystemStatusPanel.tsx
- Agent widget: src/frontend/src/components/AgentWidget.tsx
- Stores: src/frontend/src/stores/marketStore.ts, editModeStore.ts
- WS hooks: src/frontend/src/hooks/usePolyGodWS.ts, useLiveTradesWS.ts
