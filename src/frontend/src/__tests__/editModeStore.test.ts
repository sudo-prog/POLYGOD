import { describe, it, expect, beforeEach } from 'vitest';
import { useEditModeStore } from '../stores/editModeStore';

describe('editModeStore', () => {
  beforeEach(() => useEditModeStore.setState({ isEditMode: false }));

  it('toggleEditMode adds/removes body class', () => {
    useEditModeStore.getState().toggleEditMode();
    expect(document.body.classList.contains('edit-mode-active')).toBe(true);
    useEditModeStore.getState().toggleEditMode();
    expect(document.body.classList.contains('edit-mode-active')).toBe(false);
  });

  it('updateLayout persists to localStorage', () => {
    const layout = [{ i: 'test', x: 0, y: 0, w: 3, h: 4 }];
    useEditModeStore.getState().setGridLayout(layout);
    const saved = JSON.parse(localStorage.getItem('pg-layout') ?? '[]');
    expect(saved[0].i).toBe('test');
  });
});
