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
    return {
      renamedWidgets: savedNames ? JSON.parse(savedNames) : {},
      widgetStyles: savedStyles ? JSON.parse(savedStyles) : {},
      widgetHidden: savedHidden ? JSON.parse(savedHidden) : {},
    };
  } catch {
    return { renamedWidgets: {}, widgetStyles: {}, widgetHidden: {} };
  }
};

export const useEditModeStore = create<EditModeState>((set) => ({
  isEditMode: false,
  selectedComponent: null,
  gridLayout: [] as any[],
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
  setGridLayout: (layout) => set({ gridLayout: layout }),
  setJiggleMode: (enabled) => set({ jiggleMode: enabled }),
  setWidgetStyle: (id, partial) => {
    set((state) => {
      const newStyles = { ...state.widgetStyles };
      newStyles[id] = { ...newStyles[id], ...partial };
      localStorage.setItem('pg-widget-styles', JSON.stringify(newStyles));
      return { widgetStyles: newStyles };
    });
  },
  resetWidgetStyle: (id) => {
    set((state) => {
      const newStyles = { ...state.widgetStyles };
      delete newStyles[id];
      localStorage.setItem('pg-widget-styles', JSON.stringify(newStyles));
      return { widgetStyles: newStyles };
    });
  },
  renameWidget: (id, name) => {
    set((state) => {
      const newNames = { ...state.renamedWidgets, [id]: name };
      localStorage.setItem('pg-widget-names', JSON.stringify(newNames));
      return { renamedWidgets: newNames };
    });
  },
  setWidgetHidden: (id, hidden) => {
    set((state) => {
      const newHidden = { ...state.widgetHidden, [id]: hidden };
      localStorage.setItem('pg-widget-hidden', JSON.stringify(newHidden));
      return { widgetHidden: newHidden };
    });
  },
  setFocusMode: (enabled) => {
    set((state) => {
      if (enabled) {
        // Enter focus mode - hide all widgets except selected
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
        // Exit focus mode - restore previous state
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
    set({
      isEditMode: false,
      selectedComponent: null,
      gridLayout: [] as any[],
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
    localStorage.removeItem('pg-widget-names');
    localStorage.removeItem('pg-widget-styles');
    localStorage.removeItem('pg-widget-hidden');
  },
}));
