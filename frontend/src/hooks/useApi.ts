import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";

interface UseApiOptions {
  errorMsg?: string;
  silent?: boolean;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: UseApiOptions = {},
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current();
      setData(result);
    } catch (err) {
      setError(err as Error);
      if (!options.silent) {
        message.error(options.errorMsg ?? "Request failed");
      }
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    execute();
  }, [execute]);

  return { data, loading, error, refresh: execute };
}
