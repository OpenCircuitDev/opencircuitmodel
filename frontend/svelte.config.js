import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// adapter-static produces a fully static HTML/JS/CSS bundle. Tauri
		// serves these from the build/ directory at runtime — no Node server
		// needed, no API routes shipped client-side. The actual API lives in
		// the Rust daemon at http://localhost:7300.
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html',
			precompress: false,
			strict: true
		})
	}
};

export default config;
