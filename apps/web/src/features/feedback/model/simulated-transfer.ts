export function simulateTransfer(signal: AbortSignal, onProgress: (value: number) => void) {
  return new Promise<void>((resolve, reject) => {
    let progress = 0;
    const abort = () => {
      cleanup();
      reject(new DOMException("Cancelled", "AbortError"));
    };
    const timer = window.setInterval(() => {
      progress += 20;
      onProgress(progress);
      if (progress >= 100) {
        cleanup();
        resolve();
      }
    }, 110);
    function cleanup() {
      window.clearInterval(timer);
      signal.removeEventListener("abort", abort);
    }
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}
