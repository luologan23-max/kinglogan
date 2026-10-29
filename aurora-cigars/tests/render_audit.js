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
// AURORA_LOCAL_PLUGIN=1：插件自己的文件用本地工作副本（看即将部署的效果），本地没有的仍用诊断包里的
const pluginDir = path.resolve(__dirname, '..', 'plugin', 'aurora-core');
function localPlugin(p) {
	const m = process.env.AURORA_LOCAL_PLUGIN && p.match(/\/wp-content\/plugins\/aurora-core\/(assets\/[^?]+)$/);
	const f = m && path.join(pluginDir, m[1]);
	return f && fs.existsSync(f) ? f : null;
}

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
	const local = localPlugin(p);
	if (local) return route.fulfill({ path: local, contentType: local.endsWith('.css') ? 'text/css' : local.endsWith('.jpg') ? 'image/jpeg' : 'application/octet-stream' });
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

// 在页面里运行：横向溢出、过小的字（中文 < 12px、其他 < 10px）、手机上过小的点按区（< 40px）、
// 文字与背景对比度不足（WCAG：小字 < 4.5，18px 以上或 14px 粗体以上 < 3）。每类给出数量和前 12 个例子。
function measure(mobile) {
	const visible = (el) => {
		const r = el.getBoundingClientRect(), s = getComputedStyle(el);
		return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05;
	};
	const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
		[...el.classList].slice(0, 2).map((c) => '.' + c).join('');
	const text = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
	const rgb = (c) => (c.match(/[\d.]+/g) || []).map(Number);
	const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
		.reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
	const bgOf = (el) => {
		for (let e = el; e; e = e.parentElement) {
			const c = rgb(getComputedStyle(e).backgroundColor);
			if (c.length >= 3 && (c.length < 4 || c[3] > 0.5)) return c;
			if (getComputedStyle(e).backgroundImage !== 'none') return null; // 背景是图片，算不准，跳过
		}
		return [255, 255, 255];
	};
	const list = () => ({ count: 0, examples: [] });
	const add = (bucket, item) => { bucket.count++; if (bucket.examples.length < 12) bucket.examples.push(item); };
	const out = { overflow: document.documentElement.scrollWidth - window.innerWidth,
		smallText: list(), smallTargets: list(), lowContrast: list() };
	for (const el of document.body.querySelectorAll('*')) {
		if (!visible(el)) continue;
		const t = text(el);
		if (t) {
			const s = getComputedStyle(el), size = parseFloat(s.fontSize), cjk = /[㐀-鿿]/.test(t);
			if (size < (cjk ? 12 : 10)) add(out.smallText, { el: name(el), size, text: t.slice(0, 30) });
			const bg = bgOf(el), fg = rgb(s.color);
			if (bg && fg.length >= 3) {
				const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x), ratio = (a + 0.05) / (b + 0.05);
				const large = size >= 18 || (size >= 14 && parseInt(s.fontWeight, 10) >= 700);
				if (ratio < (large ? 3 : 4.5)) add(out.lowContrast, { el: name(el), ratio: +ratio.toFixed(2), size, color: s.color, text: t.slice(0, 30) });
			}
		}
		if (mobile && el.matches('a[href], button, [role="button"], input:not([type="hidden"]), select, summary')
			&& !el.matches('.screen-reader-text, .skip-link')) {  // 读屏专用的隐藏链接不算
			const r = el.getBoundingClientRect();
			if (r.width < 40 || r.height < 40) add(out.smallTargets, { el: name(el), w: Math.round(r.width), h: Math.round(r.height), text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 20) });
		}
	}
	return out;
}

(async () => {
	fs.mkdirSync(outDir, { recursive: true });
	const browser = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined });
	for (const [w, h, tag] of [[1440, 900, 'desktop'], [390, 844, 'mobile']]) {
		const mobile = tag === 'mobile';  // 手机按触屏模拟（没有悬停）
		const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: mobile ? 2 : 1, hasTouch: mobile, isMobile: mobile });
		await ctx.addCookies([{ name: 'aurora_age_ok', value: '1', domain: site.host, path: '/' }]);
		await ctx.route('**/*', serve);
		for (const [label, info] of Object.entries(report.pages_html)) {
			if (!info.file || (process.env.AURORA_ONLY && !process.env.AURORA_ONLY.split(',').includes(label))) continue; // AURORA_ONLY=home,shop 只渲染这几页
			const html = fs.readFileSync(path.join(auditDir, info.file), 'utf8');
			const page = await ctx.newPage();
			await page.route(info.url.split('?')[0] + '*', (r) => r.request().resourceType() === 'document'
				? r.fulfill({ body: html, contentType: 'text/html; charset=utf-8' }) : serve(r));
			await page.goto(info.url, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
			if (removeSel) await page.evaluate((sel) => document.querySelectorAll(sel).forEach((e) => e.remove()), removeSel);
			if (injectCss) await page.addStyleTag({ content: fs.readFileSync(injectCss, 'utf8') });
			// 整页截图时 Chromium 会临时丢掉触屏模拟（hover:none 不再成立），把只在触屏生效的规则复制成普通规则
			if (mobile) await page.evaluate(() => {
				const css = [];
				for (const sh of document.styleSheets) {
					let rules;
					try { rules = sh.cssRules; } catch (e) { continue; }
					for (const r of rules) if (r.media && /hover:\s*none/.test(r.media.mediaText)) for (const x of r.cssRules) css.push(x.cssText);
				}
				const st = document.createElement('style');
				st.textContent = css.join('\n');
				document.head.appendChild(st);
			});
			await page.waitForTimeout(800);
			// AURORA_PROBE=1：截图前量一遍可量化的设计问题，存成同名 .json（设计审查用）
			if (process.env.AURORA_PROBE) {
				const probe = await page.evaluate(measure, mobile);
				fs.writeFileSync(path.join(outDir, `${label}-${tag}.json`), JSON.stringify(probe, null, 1));
				console.log(`  ${label}-${tag}: 横向溢出 ${probe.overflow}px，字太小 ${probe.smallText.count}，点按区太小 ${probe.smallTargets.count}，对比度不足 ${probe.lowContrast.count}`);
			}
			const out = path.join(outDir, `${label}-${tag}.png`);
			await page.screenshot({ path: out, fullPage: true });
			console.log('✓', out);
			await page.close();
		}
		await ctx.close();
	}
	await browser.close();
})();
