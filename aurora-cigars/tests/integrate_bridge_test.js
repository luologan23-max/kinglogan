// 整合模式「询价清单」桥接测试（用 audit 诊断包里的真实分类页 + 站点自己的片段脚本）。
// 用法：node tests/integrate_bridge_test.js <诊断包目录> <vendor 目录>
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const [auditDir, vendorDir] = process.argv.slice(2);
const report = JSON.parse(fs.readFileSync(path.join(auditDir, 'report.json')));
const assets = path.resolve(__dirname, '..', 'plugin', 'aurora-core', 'assets');
// 与插件 wp_head 里输出的格式修复脚本保持一致
const php = fs.readFileSync(path.resolve(__dirname, '..', 'plugin', 'aurora-core', 'aurora-core.php'), 'utf8');
const normalizer = php.match(/<script>(try\{var k='aurora_request_list'.*?)<\/script>/)[1];
// 整合模式下页面上的样式：站点同站 CSS + 启用的 site-css 片段（插件在页头输出）+ 插件 base / integrate
const cssByPath = {};
for (const [u, f] of Object.entries(report.css_map || {})) if (f.startsWith('css/')) cssByPath[new URL(u).pathname] = path.join(auditDir, f);
const pluginCss = report.snippets.filter((x) => x.active && x.scope === 'site-css').map((x) => x.code)
	.concat(['aurora-base.css', 'aurora-integrate.css'].map((f) => fs.readFileSync(path.join(assets, f), 'utf8'))).join('\n');

let failures = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok || detail === undefined ? '' : ' — ' + detail)); if (!ok) failures++; };

(async () => {
	const b = await chromium.launch();
	const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
	async function open(label, c = ctx) {
		const info = report.pages_html[label];
		const html = fs.readFileSync(path.join(auditDir, info.file), 'utf8');
		const page = await c.newPage();
		page.setDefaultTimeout(3000);
		page.errors = [];
		page.on('pageerror', (e) => page.errors.push(e.message));
		await page.route('**/*', (r) => {
			const u = r.request().url();
			if (r.request().resourceType() === 'document') return r.fulfill({ body: html, contentType: 'text/html' });
			if (u.includes('jquery.min.js')) return r.fulfill({ path: path.join(vendorDir, 'jquery-3.7.1/package/dist/jquery.min.js') });
			const css = cssByPath[new URL(u).pathname];
			if (css) return r.fulfill({ path: css, contentType: 'text/css' });
			return r.abort();
		});
		await page.goto(info.url, { waitUntil: 'load' }).catch(() => {});
		// 诊断包抓的是 1.0 的页面：去掉 1.0 店面模式才有的样式和年龄弹窗，换成整合模式的样式
		await page.evaluate(() => document.querySelectorAll('#aurora-core-css, #aurora-fonts-css, .aurora-age, a.aurora-wa-float[aria-label], .aurora-list-float, .aurora-drawer').forEach((e) => e.remove()));
		await page.addStyleTag({ content: pluginCss });
		await page.addScriptTag({ path: path.join(assets, 'aurora-integrate.js') });
		await page.waitForTimeout(300);
		return page;
	}
	// 老访客：本地已有片段 14 写入的数组格式
	await ctx.addInitScript(() => {
		// 只在第一次打开时种入（localStorage 在同一上下文的各标签页间共享，sessionStorage 不共享）
		if (!localStorage.getItem('aurora_request_list')) {
			localStorage.setItem('aurora_request_list', JSON.stringify([{ id: 999, name: 'Old Item' }]));
		}
	});
	await ctx.addInitScript({ content: normalizer });

	const page = await open('category');
	const stored = (p) => p.evaluate(() => JSON.parse(localStorage.getItem('aurora_request_list')));
	let s = await stored(page);
	check('旧数组格式已转换为 {items}', s && Array.isArray(s.items) && s.items[0].name === 'Old Item', JSON.stringify(s));
	check('站点需求单 API 可读取', await page.evaluate(() => window.AuroraRL.getList().items.length === 1));
	check('坏掉的 onclick 已移除', await page.evaluate(() => !document.querySelector('.aur-action-btn[title="加入询价清单"][onclick]')));

	const btn = 'li.product .aur-action-btn[title="加入询价清单"] >> nth=0';
	const urlBefore = page.url();
	await page.hover('li.product >> nth=0');
	await page.waitForTimeout(300);
	const plus = await page.locator(btn).evaluate((e) => {
		const r = e.getBoundingClientRect();
		return { w: Math.round(r.width), h: Math.round(r.height), op: getComputedStyle(e.parentElement.closest('.aur-card-actions')).opacity };
	});
	check('悬停时「＋」可见且保持 32×32', plus.w === 32 && plus.h === 32 && plus.op === '1', JSON.stringify(plus));
	await page.click(btn);
	s = await stored(page);
	check('商品卡「＋」写入 {items} 格式', s.items.length === 2 && /^P\d+$/.test(s.items[1].sku) && s.items[1].quantity === 1, JSON.stringify(s));
	check('名称、品牌、图片都取到了', s.items[1].name === 'Bolívar Belicosos Finos' && s.items[1].brand === 'Bolívar' && !!s.items[1].image, JSON.stringify(s.items[1]));
	check('缺货商品记为求购', s.items[1].stockStatus === 'sourcing', s.items[1].stockStatus);
	check('点击「＋」不跳转到产品页', page.url() === urlBefore, page.url());
	await page.click(btn);
	s = await stored(page);
	check('重复加入只增加数量', s.items.length === 2 && s.items[1].quantity === 2, JSON.stringify(s.items));
	check('悬浮计数同步', (await page.textContent('#aurEnquiryNum')) === '2');
	const msg = await page.evaluate(() => window.AuroraRL.buildMsg('Logan', 'UAE', '+971', ''));
	check('需求单 WhatsApp 消息包含新加入的商品', msg.includes('Bolívar Belicosos Finos × 2'), msg);
	const floats = await page.evaluate(() => [...document.querySelectorAll('.aurora-wa-float, .aur-wa-float')].filter((e) => e.getBoundingClientRect().width > 0).length);
	check('分类页只有一个悬浮 WhatsApp', floats === 1, floats);
	check('分类页无脚本报错', page.errors.length === 0, page.errors.join(' | '));

	// 手机（触屏，没有悬停）：「＋」常显，图片上的 WhatsApp 不重复显示
	const touch = await b.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
	const mob = await open('category', touch);
	const m = await mob.evaluate(() => {
		const a = document.querySelector('li.product .aur-card-actions'), plus = a.querySelector('[title="加入询价清单"]');
		const wa = a.querySelector(':scope > a.aur-action-btn');
		return { hover: matchMedia('(hover: none)').matches, op: getComputedStyle(a).opacity, plus: Math.round(plus.getBoundingClientRect().width), wa: wa ? getComputedStyle(wa).display : 'none' };
	});
	check('触屏上「＋」常显', m.hover && m.op === '1' && m.plus === 32, JSON.stringify(m));
	check('触屏上图片角的 WhatsApp 不重复显示', m.wa === 'none', JSON.stringify(m));
	await touch.close();

	// 产品页：先在底栏把盒数调到 3，再点「加入询价清单」
	const prod = await open('product_existing');
	const qbtn = await prod.evaluate(() => [...document.querySelectorAll('.aur-bb-qty-btn')].map((e) => { const r = e.getBoundingClientRect(); return `${Math.round(r.width)}x${Math.round(r.height)} r=${getComputedStyle(e).borderRadius}`; }));
	check('底栏「− / +」保持 26×26 直角', qbtn.length === 2 && qbtn.every((x) => x === '26x26 r=0px'), JSON.stringify(qbtn));
	const pfloats = await prod.evaluate(() => [...document.querySelectorAll('.aurora-wa-float, .aur-wa-float')].filter((e) => e.getBoundingClientRect().width > 0).length);
	check('产品页没有悬浮按钮压住底栏', pfloats === 0, pfloats);
	await prod.click('.aur-bb-qty-btn >> nth=1');
	await prod.click('.aur-bb-qty-btn >> nth=1');
	await prod.click('.aur-btn-enquiry');
	s = await stored(prod);
	const last = s.items[s.items.length - 1];
	check('产品页按钮写入，带上底栏盒数', s.items.length === 3 && last.name === 'La Flor de Cano Preferidos' && last.quantity === 3 && last.sku === 'P192', JSON.stringify(last));
	await prod.click('.aur-bb-list');
	s = await stored(prod);
	check('底栏清单按钮同样可用（同款累加）', s.items.length === 3 && s.items[2].quantity === 4, JSON.stringify(s.items[2]));
	check('产品页无脚本报错', prod.errors.length === 0, prod.errors.join(' | '));

	// 规格表：单数项时落单的那一项占满一行（W = 通栏的品牌 / 口感强度，数字 = 普通项）
	const grid = await ctx.newPage();
	const cases = { '1 W': '1', 'W 1 2 W': '', 'W 1 2 3': '3', 'W 1 W': '1', '1 2 3 W': '3', '1 2': '', 'W 1 2 3 W': '3', '1': '1' };
	await grid.setContent('<style>' + pluginCss + '</style>' + Object.keys(cases).map((c) => '<div class="aur-spec-grid" style="width:400px">' +
		c.split(' ').map((x) => x === 'W' ? '<div class="aur-sg aur-sg-wide">W</div>' : `<div class="aur-sg" data-n="${x}">${x}</div>`).join('') + '</div>').join(''));
	const spans = await grid.evaluate(() => [...document.querySelectorAll('.aur-spec-grid')].map((g) =>
		[...g.querySelectorAll('[data-n]')].filter((c) => c.getBoundingClientRect().width > 300).map((c) => c.dataset.n).join(',')));
	const want = Object.values(cases);
	check('规格表落单项占满一行', spans.every((x, i) => x === want[i]), JSON.stringify(Object.keys(cases).map((k, i) => `${k} → ${spans[i]}（应为 ${want[i]}）`)));
	await b.close();
	console.log(failures ? `\n${failures} 项失败` : '\n全部通过');
	process.exit(failures ? 1 : 0);
})();
