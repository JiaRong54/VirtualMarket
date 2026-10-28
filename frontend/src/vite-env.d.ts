// Settings read from .env files. See README "Where data plugs in".
interface ImportMetaEnv {
  readonly VITE_PRICES_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
