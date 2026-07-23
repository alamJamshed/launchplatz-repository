import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'
import { ApiError } from '../lib/api'

export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>, dependencies: DependencyList, pollMs?: number) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const mounted = useRef(true)
  // Callers provide the dependencies explicitly, mirroring React's effect APIs.
  const load = useCallback(async (quiet = false) => {
    const controller = new AbortController()
    if (!quiet) setLoading(true)
    try { const result = await loader(controller.signal); if (mounted.current) { setData(result); setError(null) } }
    catch (reason) { if (mounted.current && !(reason instanceof DOMException && reason.name === 'AbortError')) setError(reason instanceof ApiError ? reason : new ApiError('The request failed.', 0)) }
    finally { if (mounted.current) setLoading(false) }
    return () => controller.abort()
  // eslint-disable-next-line react-hooks/use-memo, react-hooks/exhaustive-deps
  }, dependencies)
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false } }, [load])
  useEffect(() => {
    if (!pollMs) return
    const interval = window.setInterval(() => { if (document.visibilityState === 'visible') void load(true) }, pollMs)
    return () => window.clearInterval(interval)
  }, [load, pollMs])
  return { data, loading, error, refetch: () => load() }
}
