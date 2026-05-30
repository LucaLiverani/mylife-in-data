/// <reference types="vite/client" />

// App-specific build-time env vars (inlined by Vite into the client bundle).
interface ImportMetaEnv {
  // Umami web analytics — see src/main.tsx. Both unset → tracking disabled.
  readonly VITE_UMAMI_SRC?: string;
  readonly VITE_UMAMI_WEBSITE_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
