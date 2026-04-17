---
name: fix-ui
description: Fix UI issues in React 18 applications with TypeScript 5, Vite 6, and Tailwind CSS 3. Use when users ask to fix React component errors, resolve TypeScript type issues, debug Vite build problems, or correct Tailwind CSS styling issues.
---

# Fix UI Skill

An expert agent for diagnosing and fixing UI issues in React 18 applications.

## Tech Stack

- **React 18**: Component architecture, hooks, concurrent features
- **TypeScript 5**: Type-safe development, strict mode
- **Vite 6**: Fast builds, HMR, optimized dev experience
- **Tailwind CSS 3**: Utility-first styling, custom configurations

## Capabilities

- **React Component Fixes**: State management, hooks, lifecycle issues
- **TypeScript Error Resolution**: Type inference, generics, strict mode errors
- **Vite Build Debugging**: HMR issues, build errors, plugin problems
- **Tailwind CSS Fixes**: Class names, custom styles, responsive design
- **Performance Optimization**: React.memo, useMemo, useCallback issues
- **SSR/Hydration Fixes**: React 18 concurrent features, streaming SSR

## Common Issues & Fixes

### React 18 Issues

| Issue | Fix |
|-------|-----|
| "Too many re-renders" | Use useCallback/useMemo, fix state setter logic |
| "Hydration mismatch" | Ensure client/server consistency, use suppressHydrationWarning |
| "Cannot update during existing state transition" | Move state updates to useEffect |
| Stale closures | Use useCallback, ref pattern, or functional updates |

### TypeScript 5 Issues

| Issue | Fix |
|-------|-----|
| Type 'X' is not assignable | Use type assertion or fix type definition |
| Generic type inference | Add explicit type parameters |
| 'undefined' is not assignable | Add null check or use optional chaining |
| Module not found | Check tsconfig paths, install types |

### Vite 6 Issues

| Issue | Fix |
|-------|-----|
| HMR not working | Check file extensions, restart dev server |
| Build failed | Clear cache, check vite.config.ts |
| Environment variables | Use VITE_ prefix, check .env file |
| Plugin not found | Install missing dependencies |

### Tailwind CSS 3 Issues

| Issue | Fix |
|-------|-----|
| Classes not applied | Check content paths in tailwind.config.js |
| Custom colors not working | Add to tailwind.config theme |
| Responsive classes | Use correct breakpoints (sm:, md:, lg:) |
| Dark mode | Configure darkMode strategy |

## Workflow

### Step 1: Identify the Issue

1. Read the error message or describe the problem
2. Identify which layer (React, TypeScript, Vite, Tailwind)
3. Locate the affected file(s)

### Step 2: Diagnose

| Layer | Diagnostic Commands |
|-------|-------------------|
| React | Check component tree, review state changes |
| TypeScript | Run `npx tsc --noEmit` |
| Vite | Run `vite build` to see build errors |
| Tailwind | Check browser devtools for styles |

### Step 3: Apply Fix

1. Make targeted fix to the source
2. Ensure TypeScript types are correct
3. Verify Tailwind classes are valid

### Step 4: Validate

1. Run dev server and test
2. Run build to verify no errors
3. Check browser console for runtime errors

## Example Fixes

### Fix React State Loop
```tsx
// Before (causes infinite loop)
useEffect(() => {
  setCount(count + 1);
}, [count]);

// After
useEffect(() => {
  setCount(prev => prev + 1);
}, []);
```

### Fix TypeScript Generic
```tsx
// Before
function fetchData<T>(url: string): T { ... }

// After
function fetchData<T>(url: string): Promise<T> { ... }
```

### Fix Tailwind Content Path
```js
// tailwind.config.js
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
}
```

## Output Format

Provide:
1. Issue category and description
2. Root cause analysis
3. Fix applied with code snippets
4. Commands to validate the fix
