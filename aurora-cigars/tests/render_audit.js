// 用 audit 诊断包在本地还原线上页面并截图（离线，不访问站点）。
// 用法：node tests/render_audit.js <解压后的诊断包目录> <vendor 目录> <输出目录> [注入的 CSS 文件] [要移除的选择器,逗号分隔]
//   vendor 目录里需有 npm pack 解开的 jquery-3.7.1 / jquery-migrate-3.4.1 / tabler-icons-webfont-3.19.0
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [auditDir, vendorDir, outDir, injectCss, removeSel] = process.argv.slice(2);
const report = JSON.parse(fs.readFileSync(path.join(auditDir, 'report.json'), 'utf8'));
const brandDir = path.resolve(__dirname, '..', 'content', 'images');
const site = new URL(report.site.url || report.pages_html.home.url);
const blank = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=', 'base64');

// 线上 CSS 地址（去掉查询串）→ 本地文件
const cssByPath = {};
for (const [url, file] of Object.entries(report.css_map || {})) {
	if (file.startsWith('css/')) cssByPath[new URL(url).pathname] = path.join(auditDir, file);
}

function vendor(...p) { return path.join(vendorDir, ...p); }

async function serve(route) {
	const u = new URL(route.request().url());
	if (u.host === 'fonts.googleapis.com' || u.host === 'fonts.gstatic.com') return route.continue();
	if (u.host === 'cdn.jsdelivr.net' && u.pathname.includes('tabler')) {
		const base = vendor('tabler-icons-webfont-3.19.0', 'package', 'dist');
		if (u.pathname.endsWith('.css')) return route.fulfill({ path: path.join(base, 'tabler-icons.min.css'), contentType: 'text/css' });
		const font = path.join(base, 'fonts', path.basename(u.pathname));
		return fs.existsSync(font) ? route.fulfill({ path: font }) : route.abort();
	}
	if (u.host !== site.host) return route.abort();

	const p = decodeURIComponent(u.pathname);
	if (cssByPath[u.pathname]) return route.fulfill({ path: cssByPath[u.pathname], contentType: 'text/css' });
	if (p.endsWith('/jquery.min.js')) return route.fulfill({ path: vendor('jquery-3.7.1', 'package', 'dist', 'jquery.min.js'), contentType: 'application/javascript' });
	if (p.endsWith('/jquery-migrate.min.js')) return route.fulfill({ path: vendor('jquery-migrate-3.4.1', 'package', 'dist', 'jquery-migrate.min.js'), contentType: 'application/javascript' });
	const brand = p.match(/aurora-brand-([a-z0-9-]+?)(?:-\d+x\d+)?\.jpg$/);
	if (brand) {
		const f = path.join(brandDir, brand[1] + '.jpg');
		return route.fulfill({ path: fs.existsSync(f) ? f : path.join(brandDir, 'aurora.jpg'), contentType: 'image/jpeg' });
	}
	if (/\.(png|jpe?g|gif|webp|svg)$/i.test(p)) return route.fulfill({ body: blank, contentType: 'image/png' });
	if (p.endsWith('.js')) return route.fulfill({ body: '', contentType: 'application/javascript' });
	return route.abort();
}

(async () => {
	fs.mkdirSync(outDir, { recursive: true });
	const browser = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined });
	for (const [w, h, tag] of [[1440, 900, 'desktop'], [390, 844, 'mobile']]) {
		const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: tag === 'mobile' ? 2 : 1 });
		await ctx.addCookies([{ name: 'aurora_age_ok', value: '1', domain: site.host, path: '/' }]);
		await ctx.route('**/*', serve);
		for (const [label, info] of Object.entries(report.pages_html)) {
			if (!info.file) continue;
			const html = fs.readFileSync(path.join(auditDir, info.file), 'utf8');
			const page = await ctx.newPage();
			await page.route(info.url.split('?')[0] + '*', (r) => r.request().resourceType() === 'document'
				? r.fulfill({ body: html, contentType: 'text/html; charset=utf-8' }) : serve(r));
			await page.goto(info.url, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
			if (removeSel) await page.evaluate((sel) => document.querySelectorAll(sel).forEach((e) => e.remove()), removeSel);
			if (injectCss) await page.addStyleTag({ content: fs.readFileSync(injectCss, 'utf8') });
			await page.waitForTimeout(800);
			const out = path.join(outDir, `${label}-${tag}.png`);
			await page.screenshot({ path: out, fullPage: true });
			console.log('✓', out);
			await page.close();
		}
		await ctx.close();
	}
	await browser.close();
})();
