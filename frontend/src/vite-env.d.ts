/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Task 19.4 (M19): set only for hosted builds; absent locally.
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
