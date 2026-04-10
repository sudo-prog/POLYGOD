// src/__tests__/editModeStore.test.ts
//
// Changes vs previous version:
//   - FIXED M2: The test "updateLayout persists to localStorage" was permanently
//               failing because setGridLayout() never wrote to localStorage.
//               Fixed by either:
//               (a) Making setGridLayout() persist to localStorage (PREFERRED), OR
//               (b) Removing the false assertion.
//               We implement option (a) — see the corresponding fix in editModeStore.ts.
//
//   - Added a reset() call in afterEach to prevent state leakage between tests.

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useEditModeStore } from '../stores/editModeStore';

describe('editModeStore', () => {
  beforeEach(() => {
    // Reset to a clean state before each test
    useEditModeStore.getState().reset();
    localStorage.clear();
  });

  afterEach(() => {
    useEditModeStore.getState().reset();
    localStorage.clear();
  });

  it('toggleEditMode adds body class when entering edit mode', () => {
    useEditModeStore.getState().toggleEditMode();
    expect(document.body.classList.contains('edit-mode-active')).toBe(true);
  });

  it('toggleEditMode removes body class when exiting edit mode', () => {
    // Enter then exit
    useEditModeStore.getState().toggleEditMode();
    useEditModeStore.getState().toggleEditMode();
    expect(document.body.classList.contains('edit-mode-active')).toBe(false);
  });

  it('setGridLayout persists layout to localStorage', () => {
    // FIXED M2: This test previously asserted 'pg-layout' key but setGridLayout
    // never wrote to localStorage. The store is now fixed to persist this.
    const layout = [{ i: 'test', x: 0, y: 0, w: 3, h: 4 }];
    useEditModeStore.getState().setGridLayout(layout);
    const saved = JSON.parse(localStorage.getItem('pg-layout') ?? '[]');
    expect(saved).toHaveLength(1);
    expect(saved[0].i).toBe('test');
  });

  it('renameWidget persists to localStorage under pg-widget-names', () => {
    useEditModeStore.getState().renameWidget('marketList', 'My Markets');
    const saved = JSON.parse(localStorage.getItem('pg-widget-names') ?? '{}');
    expect(saved['marketList']).toBe('My Markets');
  });

  it('setWidgetHidden persists to localStorage under pg-widget-hidden', () => {
    useEditModeStore.getState().setWidgetHidden('priceChart', true);
    const saved = JSON.parse(localStorage.getItem('pg-widget-hidden') ?? '{}');
    expect(saved['priceChart']).toBe(true);
  });

  it('resetWidgetStyle removes the widget from widgetStyles', () => {
    useEditModeStore.getState().setWidgetStyle('marketList', { padding: 24 } as any);
    useEditModeStore.getState().resetWidgetStyle('marketList');
    const styles = useEditModeStore.getState().widgetStyles;
    expect(styles['marketList']).toBeUndefined();
  });

  it('reset() clears all state and localStorage keys', () => {
    useEditModeStore.getState().setGridLayout([{ i: 'a', x: 0, y: 0, w: 1, h: 1 }]);
    useEditModeStore.getState().renameWidget('foo', 'bar');
    useEditModeStore.getState().reset();
    expect(localStorage.getItem('pg-layout')).toBeNull();
    expect(localStorage.getItem('pg-widget-names')).toBeNull();
    expect(useEditModeStore.getState().gridLayout).toHaveLength(0);
  });
});
