// src/stores/editModeStore.ts
//
// Changes vs previous version:
//   - FIXED M2: setGridLayout() now persists the layout to localStorage under
//               'pg-layout'. The test "updateLayout persists to localStorage"
//               was permanently failing because this write was missing.
//   - Added 'pg-layout' to the reset() cleanup so it's cleared consistently.

import { create } from 'zustand';

interface WidgetStyleOverride {
  bgType: 'solid' | 'gradient';
  bgColor: string;
  bgColor2: string;
  bgGradientAngle: number;
  bgOpacity: number;
  borderRadius: number;
  borderShow: boolean;
  borderColor: string;
  borderOpacity: number;
  shadow: boolean;
  shadowIntensity: number;
  widgetOpacity: number;
  padding: number;
  textColor: string;
  titleFont: string;
  titleSize: number;
  bodyFont: string;
  bodySize: number;
  labelSize: number;
  lineHeight: number;
  letterSpacing: number;
  textAlign: 'left' | 'center' | 'right';
  refreshRate: '15s' | '30s' | '1m' | '5m' | 'manual';
}

interface EditModeState {
  isEditMode: boolean;
  selectedComponent: string | null;
  gridLayout: any[];
  jiggleMode: boolean;
  renamedWidgets: Record<string, string>;
  widgetStyles: Record<string, WidgetStyleOverride>;
  widgetHidden: Record<string, boolean>;
  focusMode: boolean;
  preFocusHiddenState: Record<string, boolean>;
  settingsOpen: boolean;
  hamburgerOpen: boolean;
  spotlightOpen: boolean;
  notificationOpen: boolean;
  setEditMode: (enabled: boolean) => void;
  toggleEditMode: () => void;
  setSelectedComponent: (component: string | null) => void;
  /** FIXED M2: now also persists to localStorage under 'pg-layout' */
  setGridLayout: (layout: any[]) => void;
  setJiggleMode: (enabled: boolean) => void;
  setWidgetStyle: (id: string, partial: Partial<WidgetStyleOverride>) => void;
  resetWidgetStyle: (id: string) => void;
  renameWidget: (id: string, name: string) => void;
  setWidgetHidden: (id: string, hidden: boolean) => void;
  setFocusMode: (enabled: boolean) => void;
  toggleSettings: () => void;
  setHamburgerOpen: (open: boolean) => void;
  setSpotlightOpen: (open: boolean) => void;
  setNotificationOpen: (open: boolean) => void;
  reset: () => void;
}

const getPersistedState = () => {
  try {
    const savedNames = localStorage.getItem('pg-widget-names');
    const savedStyles = localStorage.getItem('pg-widget-styles');
    const savedHidden = localStorage.getItem('pg-widget-hidden');
    const savedLayout = localStorage.getItem('pg-layout');
    return {
      renamedWidgets: savedNames ? JSON.parse(savedNames) : {},
      widgetStyles: savedStyles ? JSON.parse(savedStyles) : {},
      widgetHidden: savedHidden ? JSON.parse(savedHidden) : {},
      gridLayout: savedLayout ? JSON.parse(savedLayout) : [],
    };
  } catch {
    return { renamedWidgets: {}, widgetStyles: {}, widgetHidden: {}, gridLayout: [] };
  }
};

export const useEditModeStore = create<EditModeState>((set) => ({
  isEditMode: false,
  selectedComponent: null,
  jiggleMode: false,
  ...getPersistedState(),
  focusMode: false,
  preFocusHiddenState: {},
  settingsOpen: false,
  hamburgerOpen: false,
  spotlightOpen: false,
  notificationOpen: false,

  setEditMode: (enabled) => set({ isEditMode: enabled, jiggleMode: enabled }),

  toggleEditMode: () =>
    set((state) => {
      const newMode = !state.isEditMode;
      if (newMode) {
        document.body.classList.add('edit-mode-active');
      } else {
        document.body.classList.remove('edit-mode-active');
      }
      return { isEditMode: newMode, jiggleMode: newMode };
    }),

  setSelectedComponent: (component) => set({ selectedComponent: component }),

  // FIXED M2: persist to localStorage so the test (and page reloads) work correctly
  setGridLayout: (layout) => {
    try {
      localStorage.setItem('pg-layout', JSON.stringify(layout));
    } catch {
      // localStorage may be full or unavailable — non-fatal
    }
    set({ gridLayout: layout });
  },

  setJiggleMode: (enabled) => set({ jiggleMode: enabled }),

  setWidgetStyle: (id, partial) => {
    set((state) => {
      const newStyles = { ...state.widgetStyles };
      newStyles[id] = { ...newStyles[id], ...partial } as WidgetStyleOverride;
      try {
        localStorage.setItem('pg-widget-styles', JSON.stringify(newStyles));
      } catch {
        /* non-fatal */
      }
      return { widgetStyles: newStyles };
    });
  },

  resetWidgetStyle: (id) => {
    set((state) => {
      const newStyles = { ...state.widgetStyles };
      delete newStyles[id];
      try {
        localStorage.setItem('pg-widget-styles', JSON.stringify(newStyles));
      } catch {
        /* non-fatal */
      }
      return { widgetStyles: newStyles };
    });
  },

  renameWidget: (id, name) => {
    set((state) => {
      const newNames = { ...state.renamedWidgets, [id]: name };
      try {
        localStorage.setItem('pg-widget-names', JSON.stringify(newNames));
      } catch {
        /* non-fatal */
      }
      return { renamedWidgets: newNames };
    });
  },

  setWidgetHidden: (id, hidden) => {
    set((state) => {
      const newHidden = { ...state.widgetHidden, [id]: hidden };
      try {
        localStorage.setItem('pg-widget-hidden', JSON.stringify(newHidden));
      } catch {
        /* non-fatal */
      }
      return { widgetHidden: newHidden };
    });
  },

  setFocusMode: (enabled) => {
    set((state) => {
      if (enabled) {
        const newHidden = { ...state.widgetHidden };
        Object.keys(state.widgetStyles).forEach((id) => {
          if (id !== state.selectedComponent) {
            newHidden[id] = true;
          }
        });
        return {
          focusMode: true,
          preFocusHiddenState: { ...state.widgetHidden },
          widgetHidden: newHidden,
        };
      } else {
        return {
          focusMode: false,
          widgetHidden: { ...state.preFocusHiddenState },
          preFocusHiddenState: {},
        };
      }
    });
  },

  toggleSettings: () => set((state) => ({ settingsOpen: !state.settingsOpen })),
  setHamburgerOpen: (open) => set({ hamburgerOpen: open }),
  setSpotlightOpen: (open) => set({ spotlightOpen: open }),
  setNotificationOpen: (open) => set({ notificationOpen: open }),

  reset: () => {
    // Clear all localStorage keys owned by this store
    ['pg-layout', 'pg-widget-names', 'pg-widget-styles', 'pg-widget-hidden'].forEach((key) => {
      try {
        localStorage.removeItem(key);
      } catch {
        /* non-fatal */
      }
    });
    set({
      isEditMode: false,
      selectedComponent: null,
      gridLayout: [],
      jiggleMode: false,
      renamedWidgets: {},
      widgetStyles: {},
      widgetHidden: {},
      focusMode: false,
      preFocusHiddenState: {},
      settingsOpen: false,
      hamburgerOpen: false,
      spotlightOpen: false,
      notificationOpen: false,
    });
  },
}));
