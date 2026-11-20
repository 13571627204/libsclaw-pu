/**
 * 极简 debounce（trailing edge）。
 * 用于替代 lodash 的 debounce，避免为单个函数引入整库（约 70KB）。
 */
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  wait = 300,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, wait);
  };
}
