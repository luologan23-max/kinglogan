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

let failures = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok || detail === undefined ? '' : ' — ' + detail)); if (!ok) failures++; };

(async () => {
	const b = await chromium.launch();
	const ctx = await b.newContext();
	async function open(label) {
		const info = report.pages_html[label];
		const html = fs.readFileSync(path.join(auditDir, info.file), 'utf8');
		const page = await ctx.newPage();
		page.errors = [];
		page.on('pageerror', (e) => page.errors.push(e.message));
		await page.route('**/*', (r) => {
			const u = r.request().url();
			if (r.request().resourceType() === 'document') return r.fulfill({ body: html, contentType: 'text/html' });
			if (u.includes('jquery.min.js')) return r.fulfill({ path: path.join(vendorDir, 'jquery-3.7.1/package/dist/jquery.min.js') });
			return r.abort();
		});
		await page.goto(info.url).catch(() => {});
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
	await page.click(btn, { force: true });
	s = await stored(page);
	check('商品卡「＋」写入 {items} 格式', s.items.length === 2 && /^P\d+$/.test(s.items[1].sku) && s.items[1].quantity === 1, JSON.stringify(s));
	check('名称、品牌、图片都取到了', s.items[1].name === 'Bolívar Belicosos Finos' && s.items[1].brand === 'Bolívar' && !!s.items[1].image, JSON.stringify(s.items[1]));
	check('缺货商品记为求购', s.items[1].stockStatus === 'sourcing', s.items[1].stockStatus);
	check('点击「＋」不跳转到产品页', page.url() === urlBefore, page.url());
	await page.click(btn, { force: true });
	s = await stored(page);
	check('重复加入只增加数量', s.items.length === 2 && s.items[1].quantity === 2, JSON.stringify(s.items));
	check('悬浮计数同步', (await page.textContent('#aurEnquiryNum')) === '2');
	const msg = await page.evaluate(() => window.AuroraRL.buildMsg('Logan', 'UAE', '+971', ''));
	check('需求单 WhatsApp 消息包含新加入的商品', msg.includes('Bolívar Belicosos Finos × 2'), msg);
	check('分类页无脚本报错', page.errors.length === 0, page.errors.join(' | '));

	// 产品页：先在底栏把盒数调到 3，再点「加入询价清单」
	const prod = await open('product_existing');
	await prod.evaluate(() => { window.aurChgQty(1); window.aurChgQty(1); });
	await prod.click('.aur-btn-enquiry', { force: true });
	s = await stored(prod);
	const last = s.items[s.items.length - 1];
	check('产品页按钮写入，带上底栏盒数', s.items.length === 3 && last.name === 'La Flor de Cano Preferidos' && last.quantity === 3 && last.sku === 'P192', JSON.stringify(last));
	await prod.click('.aur-bb-list', { force: true });
	s = await stored(prod);
	check('底栏清单按钮同样可用（同款累加）', s.items.length === 3 && s.items[2].quantity === 4, JSON.stringify(s.items[2]));
	check('产品页无脚本报错', prod.errors.length === 0, prod.errors.join(' | '));
	await b.close();
	console.log(failures ? `\n${failures} 项失败` : '\n全部通过');
	process.exit(failures ? 1 : 0);
})();
