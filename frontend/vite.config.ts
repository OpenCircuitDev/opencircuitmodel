import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		// Tauri's dev URL is set to localhost:5173 in tauri.conf.json.
		port: 5173,
		strictPort: true,
		// Proxy /v1/* requests to the OCM daemon during dev so we don't have
		// to deal with CORS in development. In Tauri prod, the daemon and the
		// webview share the localhost origin, so direct fetches work.
		proxy: {
			'/v1': {
				target: 'http://127.0.0.1:7300',
				changeOrigin: false
			}
		}
	}
});
