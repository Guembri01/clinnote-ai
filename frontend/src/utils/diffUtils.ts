/**
 * Diff utilities for ClinNote AI
 * Computes differences between AI-generated notes and physician edits
 */

/** A single diff segment */
export interface DiffSegment {
  type: 'equal' | 'added' | 'removed';
  text: string;
}

/**
 * Compute a word-level diff between two text strings
 * @param original - The AI-generated original text
 * @param edited - The physician-edited text
 * @returns Array of diff segments for rendering
 *
 * @example
 * diffTexts("The patient has fever", "The patient reports fever")
 * // → [
 * //   { type: 'equal', text: 'The patient ' },
 * //   { type: 'removed', text: 'has' },
 * //   { type: 'added', text: 'reports' },
 * //   { type: 'equal', text: ' fever' }
 * // ]
 */
export function diffTexts(original: string, edited: string): DiffSegment[] {
  if (original === edited) {
    return [{ type: 'equal', text: original }];
  }

  const origWords = tokenize(original);
  const editWords = tokenize(edited);

  const lcsMatrix = buildLCSMatrix(origWords, editWords);
  return buildDiff(origWords, editWords, lcsMatrix);
}

/** Tokenize text into words + whitespace tokens */
function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter(Boolean);
}

/** Build Longest Common Subsequence matrix */
function buildLCSMatrix(a: string[], b: string[]): number[][] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  return dp;
}

/** Build diff segments from LCS matrix */
function buildDiff(a: string[], b: string[], dp: number[][]): DiffSegment[] {
  const result: DiffSegment[] = [];
  let i = a.length;
  let j = b.length;
  const ops: Array<{ type: DiffSegment['type']; text: string }> = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      ops.unshift({ type: 'equal', text: a[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.unshift({ type: 'added', text: b[j - 1] });
      j--;
    } else {
      ops.unshift({ type: 'removed', text: a[i - 1] });
      i--;
    }
  }

  // Merge consecutive same-type segments
  for (const op of ops) {
    const last = result[result.length - 1];
    if (last && last.type === op.type) {
      last.text += op.text;
    } else {
      result.push({ ...op });
    }
  }

  return result;
}

/**
 * Calculate edit distance percentage between two texts
 * @returns 0 = identical, 1 = completely different
 */
export function getEditDistance(original: string, edited: string): number {
  if (original === edited) return 0;
  if (original.length === 0 || edited.length === 0) return 1;

  const origWords = original.split(/\s+/).filter(Boolean);
  const editWords = edited.split(/\s+/).filter(Boolean);

  const diff = diffTexts(original, edited);
  const changedWords = diff.filter((d) => d.type !== 'equal').reduce((sum, d) => {
    return sum + d.text.split(/\s+/).filter(Boolean).length;
  }, 0);

  const totalWords = Math.max(origWords.length, editWords.length);
  return totalWords === 0 ? 0 : changedWords / totalWords;
}

/**
 * Check if text has been substantially modified (>10% change)
 */
export function isSubstantiallyEdited(original: string, edited: string): boolean {
  return getEditDistance(original, edited) > 0.1;
}
