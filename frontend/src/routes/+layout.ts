// SvelteKit layout config. Tauri serves a static bundle, so:
//   - SSR is disabled (no Node server in Tauri runtime)
//   - prerender is enabled for the index page
//   - trailingSlash uses 'always' so adapter-static emits index.html
//     under each route directory, matching Tauri's file:// resolution.
export const ssr = false;
export const prerender = true;
export const trailingSlash = 'always';
