/**
 * Stable React keys for list items whose display id changes while editing (e.g. field rename).
 */

import { useCallback, useRef } from "react";

export function useStableEntityKeys() {
  const mapRef = useRef(new Map<string, string>());
  const seqRef = useRef(0);

  const keyFor = useCallback((entityId: string, prefix: string) => {
    let k = mapRef.current.get(entityId);
    if (!k) {
      k = `${prefix}-${seqRef.current++}`;
      mapRef.current.set(entityId, k);
    }
    return k;
  }, []);

  const transferKey = useCallback((fromId: string, toId: string) => {
    const k = mapRef.current.get(fromId);
    if (!k) return;
    mapRef.current.delete(fromId);
    mapRef.current.set(toId, k);
  }, []);

  const removeKey = useCallback((entityId: string) => {
    mapRef.current.delete(entityId);
  }, []);

  return { keyFor, transferKey, removeKey };
}
