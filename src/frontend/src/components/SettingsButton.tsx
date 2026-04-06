import { useState } from 'react';
import { Grid, X } from 'lucide-react';
import { useEditModeStore } from '../stores/editModeStore';

export function SettingsButton() {
  const { isEditMode, setEditMode } = useEditModeStore();
  const [isHovered, setIsHovered] = useState(false);

  return (
    <button
      onClick={() => setEditMode(!isEditMode)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`
        ios-icon-btn
        fixed
        bottom-6
        right-6
        z-50
        transition-all
        ${isHovered ? 'bg-primary-500/20' : 'bg-surface-900/50'}
      `}
    >
      {isEditMode ? (
        <X className="w-5 h-5" />
      ) : (
        <div className="flex flex-col items-center gap-1">
          <Grid className="w-4 h-4" />
          <span className="text-xs text-surface-200">Edit</span>
        </div>
      )}
    </button>
  );
}
