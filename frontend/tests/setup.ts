/**
 * Setup global de Vitest.
 *
 * Node.js expone desde hace unas versiones un `localStorage` global nativo
 * (backend por node:sqlite, requiere `--localstorage-file` para funcionar
 * de verdad). Como ya existe en `globalThis` antes de que arranque el
 * entorno jsdom de Vitest, pisa al `localStorage` real de jsdom — y sin la
 * bandera queda un stub roto donde ni `setItem` es una función. Sin esto,
 * cualquier test que toque `localStorage` revienta con
 * "localStorage.clear is not a function" o similar, sin relación alguna
 * con el código que se está probando.
 *
 * Se reemplaza por una implementación mínima en memoria que cumple la Web
 * Storage API, antes de que corra cualquier test.
 */
class MemoryStorage implements Storage {
  private store = new Map<string, string>()

  get length(): number {
    return this.store.size
  }

  clear(): void {
    this.store.clear()
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null
  }

  removeItem(key: string): void {
    this.store.delete(key)
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }
}

for (const target of [globalThis, (globalThis as any).window].filter(Boolean)) {
  Object.defineProperty(target, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  })
  Object.defineProperty(target, 'sessionStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  })
}
