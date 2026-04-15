import { useMemo } from 'react';

interface DiffLine {
  type: 'removed' | 'added' | 'unchanged';
  content: string;
  lineNum: number;
}

interface DiffViewerProps {
  oldCode: string;
  newCode: string;
  filename: string;
}

export default function DiffViewer({ oldCode, newCode, filename }: DiffViewerProps) {
  const lines = useMemo(() => {
    const oldLines = oldCode.split('\n');
    const newLines = newCode.split('\n');
    const result: DiffLine[] = [];

    // Simple LCS-based diff (good enough for small patches)
    const maxOld = oldLines.length;
    const maxNew = newLines.length;

    // Build LCS table
    const lcs: number[][] = Array.from({ length: maxOld + 1 }, () => new Array(maxNew + 1).fill(0));
    for (let i = 1; i <= maxOld; i++) {
      for (let j = 1; j <= maxNew; j++) {
        lcs[i][j] =
          oldLines[i - 1] === newLines[j - 1]
            ? lcs[i - 1][j - 1] + 1
            : Math.max(lcs[i - 1][j], lcs[i][j - 1]);
      }
    }

    // Backtrack
    let i = maxOld,
      j = maxNew;
    const ops: Array<{ type: 'removed' | 'added' | 'unchanged'; content: string }> = [];
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
        ops.unshift({ type: 'unchanged', content: oldLines[i - 1] });
        i--;
        j--;
      } else if (j > 0 && (i === 0 || lcs[i][j - 1] >= lcs[i - 1][j])) {
        ops.unshift({ type: 'added', content: newLines[j - 1] });
        j--;
      } else {
        ops.unshift({ type: 'removed', content: oldLines[i - 1] });
        i--;
      }
    }

    let lineNum = 1;
    ops.forEach((op) => {
      result.push({ ...op, lineNum: lineNum });
      if (op.type !== 'removed') lineNum++;
    });

    return result;
  }, [oldCode, newCode]);

  const addedCount = lines.filter((l) => l.type === 'added').length;
  const removedCount = lines.filter((l) => l.type === 'removed').length;

  return (
    <div
      style={{
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: '8px',
        overflow: 'hidden',
        fontSize: '11px',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div
        style={{
          padding: '6px 10px',
          background: 'var(--color-background-secondary)',
          borderBottom: '0.5px solid var(--color-border-tertiary)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}>{filename}</span>
        <span style={{ fontSize: '11px' }}>
          <span style={{ color: '#1D9E75', marginRight: '8px' }}>+{addedCount}</span>
          <span style={{ color: '#D85A30' }}>-{removedCount}</span>
        </span>
      </div>
      <div style={{ overflowX: 'auto', maxHeight: '240px', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {lines.map((line, idx) => (
              <tr
                key={idx}
                style={{
                  background:
                    line.type === 'added'
                      ? 'rgba(29, 158, 117, 0.08)'
                      : line.type === 'removed'
                        ? 'rgba(216, 90, 48, 0.08)'
                        : 'transparent',
                }}
              >
                <td
                  style={{
                    padding: '1px 8px',
                    color: 'var(--color-text-tertiary)',
                    userSelect: 'none',
                    width: '32px',
                    textAlign: 'right',
                    borderRight: '0.5px solid var(--color-border-tertiary)',
                  }}
                >
                  {line.type !== 'removed' ? line.lineNum : ''}
                </td>
                <td
                  style={{
                    padding: '1px 4px 1px 8px',
                    width: '16px',
                    color:
                      line.type === 'added'
                        ? '#1D9E75'
                        : line.type === 'removed'
                          ? '#D85A30'
                          : 'var(--color-text-tertiary)',
                    userSelect: 'none',
                  }}
                >
                  {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                </td>
                <td
                  style={{
                    padding: '1px 8px',
                    color:
                      line.type === 'added'
                        ? '#085041'
                        : line.type === 'removed'
                          ? '#712B13'
                          : 'var(--color-text-primary)',
                    whiteSpace: 'pre',
                  }}
                >
                  {line.content}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
