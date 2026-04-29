import { lazy, type ComponentType } from "react";

const reloadMarkerPrefix = "crypto-scanner:dynamic-import-reload";
const reloadMarkerTtlMs = 60_000;

const dynamicImportErrorPatterns = [
  "Failed to fetch dynamically imported module",
  "Importing a module script failed",
  "error loading dynamically imported module",
  "Loading chunk",
  "ChunkLoadError"
];

export function isDynamicImportError(error: unknown) {
  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
  return dynamicImportErrorPatterns.some((pattern) => message.toLowerCase().includes(pattern.toLowerCase()));
}

function reloadMarkerKey() {
  return `${reloadMarkerPrefix}:${window.location.pathname}${window.location.search}`;
}

function markReloadAttempt() {
  try {
    const key = reloadMarkerKey();
    const lastAttempt = Number(window.sessionStorage.getItem(key) ?? "0");
    const now = Date.now();

    if (Number.isFinite(lastAttempt) && now - lastAttempt < reloadMarkerTtlMs) {
      return false;
    }

    window.sessionStorage.setItem(key, String(now));
    return true;
  } catch {
    return false;
  }
}

export async function loadRouteModule<TKey extends string, TModule extends Record<TKey, ComponentType>>(
  importer: () => Promise<TModule>,
  key: TKey,
  reloadPage = () => window.location.reload()
) {
  try {
    const module = await importer();
    return { default: module[key] };
  } catch (error) {
    if (typeof window !== "undefined" && isDynamicImportError(error) && markReloadAttempt()) {
      reloadPage();
      return new Promise<{ default: TModule[TKey] }>(() => {});
    }

    throw error;
  }
}

export function lazyRoute<TKey extends string, TModule extends Record<TKey, ComponentType>>(
  importer: () => Promise<TModule>,
  key: TKey
) {
  return lazy(() => loadRouteModule(importer, key));
}
