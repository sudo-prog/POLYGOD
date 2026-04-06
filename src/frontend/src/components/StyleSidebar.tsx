import { useState } from 'react';
import { useEditModeStore } from '../stores/editModeStore';
import { X, Palette, Grid, Layers, Settings, RefreshCw } from 'lucide-react';

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

export function StyleSidebar() {
  const { selectedComponent, setEditMode, widgetStyles, setWidgetStyle } = useEditModeStore();

  const [draftStyle, setDraftStyle] = useState<WidgetStyleOverride | null>(null);

  // Get current widget style or default
  const currentStyle = widgetStyles[selectedComponent || ''] || {
    bgType: 'solid',
    bgColor: '#07080e',
    bgColor2: '#1a1a2e',
    bgGradientAngle: 135,
    bgOpacity: 0.92,
    borderRadius: 24,
    borderShow: false,
    borderColor: '#c9a84c',
    borderOpacity: 0.1,
    shadow: true,
    shadowIntensity: 0.3,
    widgetOpacity: 1,
    padding: 16,
    textColor: '#ffffff',
    titleFont: 'Work Sans',
    titleSize: 16,
    bodyFont: 'Work Sans',
    bodySize: 14,
    labelSize: 12,
    lineHeight: 1.5,
    letterSpacing: 0,
    textAlign: 'left',
    refreshRate: '15s',
  };

  // Initialize draft style when component is selected
  if (selectedComponent && !draftStyle) {
    setDraftStyle({ ...currentStyle });
  }

  // Reset draft when component is deselected
  if (!selectedComponent && draftStyle) {
    setDraftStyle(null);
  }

  const handleApply = () => {
    if (selectedComponent && draftStyle) {
      setWidgetStyle(selectedComponent, draftStyle);
    }
    setEditMode(false);
  };

  const handleCancel = () => {
    setDraftStyle(null);
    setEditMode(false);
  };

  const handleReset = () => {
    if (selectedComponent) {
      setWidgetStyle(selectedComponent, {});
    }
  };

  if (!selectedComponent) {
    return null;
  }

  return (
    <div className="fixed right-6 top-24 z-50 w-96 h-[calc(100vh-48px)] bg-surface-900/50 border border-white/10 rounded-xl p-4">
      <div className="flex items-center gap-3 mb-4">
        <Palette className="w-5 h-5 text-primary-400" />
        <h2 className="font-semibold text-white">Style Editor</h2>
        <button onClick={() => setEditMode(false)} className="ios-icon-btn">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Rename Widget */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Rename Widget</span>
        </div>
        <input
          type="text"
          value={useEditModeStore.getState().renamedWidgets[selectedComponent] || selectedComponent}
          onChange={(e) =>
            useEditModeStore.getState().renameWidget(selectedComponent, e.target.value)
          }
          className="ios-input text-sm w-full"
          placeholder="Enter new name"
        />
      </div>

      {/* Background */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Grid className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Background</span>
        </div>
        <div className="space-y-3">
          <div className="ios-segmented">
            <button
              onClick={() => setDraftStyle((prev) => prev && { ...prev, bgType: 'solid' })}
              className={`ios-seg-item ${
                (draftStyle?.bgType || 'solid') === 'solid' ? 'active' : ''
              }`}
            >
              Solid
            </button>
            <button
              onClick={() => setDraftStyle((prev) => prev && { ...prev, bgType: 'gradient' })}
              className={`ios-seg-item ${
                (draftStyle?.bgType || 'solid') === 'gradient' ? 'active' : ''
              }`}
            >
              Gradient
            </button>
          </div>

          {draftStyle?.bgType === 'solid' && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div
                  className="w-10 h-10 rounded-lg border-2 border-white/20 cursor-pointer"
                  style={{ backgroundColor: draftStyle.bgColor }}
                />
                <input
                  type="color"
                  value={draftStyle.bgColor}
                  onChange={(e) =>
                    setDraftStyle((prev) => prev && { ...prev, bgColor: e.target.value })
                  }
                  className="w-10 h-10 rounded-lg border-2 border-white/20"
                />
                <input
                  type="text"
                  value={draftStyle.bgColor}
                  onChange={(e) =>
                    setDraftStyle((prev) => prev && { ...prev, bgColor: e.target.value })
                  }
                  className="ios-input text-xs w-20"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-300">Opacity</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={draftStyle.bgOpacity}
                  onChange={(e) =>
                    setDraftStyle(
                      (prev) => prev && { ...prev, bgOpacity: parseFloat(e.target.value) }
                    )
                  }
                  className="flex-1"
                />
                <span className="text-xs text-surface-300">
                  {Math.round(draftStyle.bgOpacity * 100)}%
                </span>
              </div>
            </div>
          )}

          {draftStyle?.bgType === 'gradient' && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div
                  className="w-6 h-6 rounded-lg border-2 border-white/20 cursor-pointer"
                  style={{
                    background: `linear-gradient(135deg, ${draftStyle.bgColor} 0%, ${draftStyle.bgColor2} 100%)`,
                  }}
                />
                <input
                  type="color"
                  value={draftStyle.bgColor}
                  onChange={(e) =>
                    setDraftStyle((prev) => prev && { ...prev, bgColor: e.target.value })
                  }
                  className="w-10 h-10 rounded-lg border-2 border-white/20"
                />
                <input
                  type="color"
                  value={draftStyle.bgColor2}
                  onChange={(e) =>
                    setDraftStyle((prev) => prev && { ...prev, bgColor2: e.target.value })
                  }
                  className="w-10 h-10 rounded-lg border-2 border-white/20"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-300">Angle</span>
                <input
                  type="range"
                  min="0"
                  max="360"
                  value={draftStyle.bgGradientAngle}
                  onChange={(e) =>
                    setDraftStyle(
                      (prev) => prev && { ...prev, bgGradientAngle: parseInt(e.target.value) }
                    )
                  }
                  className="flex-1"
                />
                <span className="text-xs text-surface-300">{draftStyle.bgGradientAngle}°</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-300">Opacity</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={draftStyle.bgOpacity}
                  onChange={(e) =>
                    setDraftStyle(
                      (prev) => prev && { ...prev, bgOpacity: parseFloat(e.target.value) }
                    )
                  }
                  className="flex-1"
                />
                <span className="text-xs text-surface-300">
                  {Math.round(draftStyle.bgOpacity * 100)}%
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Border */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Layers className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Border</span>
        </div>
        <div className="space-y-2">
          <button
            onClick={() =>
              setDraftStyle((prev) => prev && { ...prev, borderShow: !prev!.borderShow })
            }
            className={`ios-toggle ${draftStyle?.borderShow ? 'active' : ''}`}
          >
            <span />
          </button>
          {draftStyle?.borderShow && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div
                  className="w-10 h-10 rounded-lg border-2 border-white/20 cursor-pointer"
                  style={{ backgroundColor: draftStyle.borderColor }}
                />
                <input
                  type="color"
                  value={draftStyle.borderColor}
                  onChange={(e) =>
                    setDraftStyle((prev) => prev && { ...prev, borderColor: e.target.value })
                  }
                  className="w-10 h-10 rounded-lg border-2 border-white/20"
                />
                <input
                  type="text"
                  value={draftStyle.borderColor}
                  onChange={(e) =>
                    setDraftStyle((prev) => prev && { ...prev, borderColor: e.target.value })
                  }
                  className="ios-input text-xs w-20"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-300">Opacity</span>
                <input
                  type="range"
                  min="0"
                  max="0.4"
                  step="0.05"
                  value={draftStyle.borderOpacity}
                  onChange={(e) =>
                    setDraftStyle(
                      (prev) => prev && { ...prev, borderOpacity: parseFloat(e.target.value) }
                    )
                  }
                  className="flex-1"
                />
                <span className="text-xs text-surface-300">
                  {Math.round(draftStyle.borderOpacity * 100)}%
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Corner Radius */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <RefreshCw className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Corner Radius</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-300">0px</span>
          <input
            type="range"
            min="0"
            max="32"
            value={draftStyle?.borderRadius || 24}
            onChange={(e) =>
              setDraftStyle((prev) => prev && { ...prev, borderRadius: parseInt(e.target.value) })
            }
            className="flex-1"
          />
          <span className="text-xs text-surface-300">32px</span>
        </div>
      </div>

      {/* Shadow */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Shadow</span>
        </div>
        <button
          onClick={() => setDraftStyle((prev) => prev && { ...prev, shadow: !prev!.shadow })}
          className={`ios-toggle ${draftStyle?.shadow ? 'active' : ''}`}
        >
          <span />
        </button>
        {draftStyle?.shadow && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Intensity</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={draftStyle?.shadowIntensity || 0.3}
              onChange={(e) =>
                setDraftStyle(
                  (prev) => prev && { ...prev, shadowIntensity: parseFloat(e.target.value) }
                )
              }
              className="flex-1"
            />
            <span className="text-xs text-surface-300">
              {Math.round((draftStyle?.shadowIntensity || 0.3) * 100)}%
            </span>
          </div>
        )}
      </div>

      {/* Opacity */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Widget Opacity</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-300">0%</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={draftStyle?.widgetOpacity || 1}
            onChange={(e) =>
              setDraftStyle(
                (prev) => prev && { ...prev, widgetOpacity: parseFloat(e.target.value) }
              )
            }
            className="flex-1"
          />
          <span className="text-xs text-surface-300">100%</span>
        </div>
      </div>

      {/* Padding */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Padding</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-300">4px</span>
          <input
            type="range"
            min="4"
            max="32"
            value={draftStyle?.padding || 16}
            onChange={(e) =>
              setDraftStyle((prev) => prev && { ...prev, padding: parseInt(e.target.value) })
            }
            className="flex-1"
          />
          <span className="text-xs text-surface-300">32px</span>
        </div>
      </div>

      {/* Typography */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Typography</span>
        </div>
        <div className="space-y-2">
          {/* Title Font */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Title Font</span>
            <input
              type="text"
              value={draftStyle?.titleFont || 'Work Sans'}
              onChange={(e) =>
                setDraftStyle((prev) => prev && { ...prev, titleFont: e.target.value })
              }
              className="ios-input text-xs flex-1"
              placeholder="Font family"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Title Size</span>
            <input
              type="range"
              min="10"
              max="32"
              value={draftStyle?.titleSize || 16}
              onChange={(e) =>
                setDraftStyle((prev) => prev && { ...prev, titleSize: parseInt(e.target.value) })
              }
              className="flex-1"
            />
            <span className="text-xs text-surface-300">{draftStyle?.titleSize || 16}px</span>
          </div>

          {/* Body Font */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Body Font</span>
            <input
              type="text"
              value={draftStyle?.bodyFont || 'Work Sans'}
              onChange={(e) =>
                setDraftStyle((prev) => prev && { ...prev, bodyFont: e.target.value })
              }
              className="ios-input text-xs flex-1"
              placeholder="Font family"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Body Size</span>
            <input
              type="range"
              min="10"
              max="20"
              value={draftStyle?.bodySize || 14}
              onChange={(e) =>
                setDraftStyle((prev) => prev && { ...prev, bodySize: parseInt(e.target.value) })
              }
              className="flex-1"
            />
            <span className="text-xs text-surface-300">{draftStyle?.bodySize || 14}px</span>
          </div>

          {/* Label Size */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Label Size</span>
            <input
              type="range"
              min="7"
              max="14"
              value={draftStyle?.labelSize || 12}
              onChange={(e) =>
                setDraftStyle((prev) => prev && { ...prev, labelSize: parseInt(e.target.value) })
              }
              className="flex-1"
            />
            <span className="text-xs text-surface-300">{draftStyle?.labelSize || 12}px</span>
          </div>

          {/* Line Height */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Line Height</span>
            <input
              type="range"
              min="1.0"
              max="2.0"
              step="0.1"
              value={draftStyle?.lineHeight || 1.5}
              onChange={(e) =>
                setDraftStyle((prev) => prev && { ...prev, lineHeight: parseFloat(e.target.value) })
              }
              className="flex-1"
            />
            <span className="text-xs text-surface-300">{draftStyle?.lineHeight || 1.5}</span>
          </div>

          {/* Letter Spacing */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Letter Spacing</span>
            <input
              type="range"
              min="0"
              max="0.2"
              step="0.01"
              value={draftStyle?.letterSpacing || 0}
              onChange={(e) =>
                setDraftStyle(
                  (prev) => prev && { ...prev, letterSpacing: parseFloat(e.target.value) }
                )
              }
              className="flex-1"
            />
            <span className="text-xs text-surface-300">{draftStyle?.letterSpacing || 0}em</span>
          </div>

          {/* Text Align */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-surface-300">Text Align</span>
            <div className="ios-segmented">
              <button
                onClick={() => setDraftStyle((prev) => prev && { ...prev, textAlign: 'left' })}
                className={`ios-seg-item ${
                  (draftStyle?.textAlign || 'left') === 'left' ? 'active' : ''
                }`}
              >
                Left
              </button>
              <button
                onClick={() => setDraftStyle((prev) => prev && { ...prev, textAlign: 'center' })}
                className={`ios-seg-item ${
                  (draftStyle?.textAlign || 'left') === 'center' ? 'active' : ''
                }`}
              >
                Center
              </button>
              <button
                onClick={() => setDraftStyle((prev) => prev && { ...prev, textAlign: 'right' })}
                className={`ios-seg-item ${
                  (draftStyle?.textAlign || 'left') === 'right' ? 'active' : ''
                }`}
              >
                Right
              </button>
            </div>
          </div>

          {/* Text Color */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300">Text Color</span>
            <div className="flex items-center gap-2">
              <div
                className="w-8 h-8 rounded-lg border-2 border-white/20 cursor-pointer"
                style={{ backgroundColor: draftStyle?.textColor || '#ffffff' }}
              />
              <input
                type="color"
                value={draftStyle?.textColor || '#ffffff'}
                onChange={(e) =>
                  setDraftStyle((prev) => prev && { ...prev, textColor: e.target.value })
                }
                className="w-8 h-8 rounded-lg border-2 border-white/20"
              />
              <input
                type="text"
                value={draftStyle?.textColor || '#ffffff'}
                onChange={(e) =>
                  setDraftStyle((prev) => prev && { ...prev, textColor: e.target.value })
                }
                className="ios-input text-xs w-20"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Refresh Rate */}
      <div className="ios-card rounded-2xl p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-white">Refresh Rate</span>
        </div>
        <select
          value={draftStyle?.refreshRate || '15s'}
          onChange={(e) =>
            setDraftStyle((prev) => prev && { ...prev, refreshRate: e.target.value as any })
          }
          className="ios-input text-xs w-full"
        >
          <option value="15s">15 seconds</option>
          <option value="30s">30 seconds</option>
          <option value="1m">1 minute</option>
          <option value="5m">5 minutes</option>
          <option value="manual">Manual</option>
        </select>
      </div>

      {/* Action Bar */}
      <div className="sticky bottom-0 left-0 right-0 bg-surface-900/95 border-t border-white/10 p-4">
        <div className="flex gap-2">
          <button onClick={handleCancel} className="ios-btn text-sm flex-1">
            Cancel
          </button>
          <button onClick={handleReset} className="ios-btn-red text-sm flex-1">
            Reset
          </button>
          <button onClick={handleApply} className="ios-btn-gold text-sm flex-1">
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
