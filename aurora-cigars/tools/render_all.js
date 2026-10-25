// 渲染品牌产品图：node tools/render_all.js  → content/images/<slug>.jpg
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const WRAPPERS = {
	cohiba: 'colorado', montecristo: 'colorado', 'romeo-y-julieta': 'claro', partagas: 'maduro',
	'h-upmann': 'claro', trinidad: 'colorado', 'hoyo-de-monterrey': 'claro', bolivar: 'maduro',
	punch: 'colorado', davidoff: 'claro',
};
const root = path.resolve(__dirname, '..');
const brands = JSON.parse(fs.readFileSync(path.join(root, 'content/brands.json'), 'utf8'));
const jobs = brands.map((b, i) => ({
	slug: b.slug, brand: b.name, wrapper: WRAPPERS[b.slug] || 'colorado',
	sub: b.slug === 'davidoff' ? 'REPÚBLICA DOMINICANA' : 'HABANA · CUBA',
	angle: (-0.42 + ((i % 3) - 1) * 0.06).toFixed(3), seed: 11 + i * 7,
}));
jobs.push({ slug: 'aurora', brand: 'Aurora', wrapper: 'colorado', sub: 'CIGARS · DUBAI', angle: '-0.42', seed: 5 });

(async () => {
	const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined;
	const browser = await chromium.launch({ proxy });
	const page = await browser.newPage({ viewport: { width: 1600, height: 1600 } });
	for (const j of jobs) {
		const qs = new URLSearchParams({ brand: j.brand, sub: j.sub, wrapper: j.wrapper, angle: j.angle, seed: j.seed, size: 1600 });
		await page.goto('file://' + path.join(root, 'tools/render_cigar.html') + '?' + qs);
		await page.waitForFunction(() => document.title === 'ready', null, { timeout: 30000 });
		const out = path.join(root, 'content/images', j.slug + '.jpg');
		await page.locator('canvas').screenshot({ path: out, type: 'jpeg', quality: 88 });
		console.log('✓', out, Math.round(fs.statSync(out).size / 1024) + 'KB');
	}
	await browser.close();
})();
