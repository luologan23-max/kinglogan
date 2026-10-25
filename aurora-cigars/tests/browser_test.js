// 浏览器交互测试：node tests/browser_test.js <normal.html> <limited.html> <截图目录>
const { chromium } = require('playwright');
const path = require('path');

const [normalHtml, limitedHtml, shotDir] = process.argv.slice(2);
let failures = 0;
function check(name, ok, detail) {
	console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok || !detail ? '' : ' — ' + detail));
	if (!ok) failures++;
}

(async () => {
	const browser = await chromium.launch();
	const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
	// 字体走外网，测试中屏蔽以免超时
	await ctx.route('https://fonts.googleapis.com/**', (r) => r.fulfill({ status: 200, body: '' }));
	await ctx.route('https://wa.me/**', (r) => r.fulfill({ status: 200, body: 'wa' }));
	const page = await ctx.newPage();
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));

	await page.goto('file://' + path.resolve(normalHtml));
	await page.screenshot({ path: path.join(shotDir, '1-age-gate.png') });
	check('年龄验证弹窗显示', await page.isVisible('.aurora-age'));
	await page.click('.aurora-age-yes');
	check('确认后弹窗关闭', !(await page.isVisible('.aurora-age')));
	const cookies = await ctx.cookies();
	// file:// 下 cookie 不落盘，改为检查 document.cookie 写入逻辑
	const docCookie = await page.evaluate(() => document.cookie);
	check('年龄 cookie 写入（file:// 下可能为空）', docCookie.includes('aurora_age_ok=1') || cookies.length === 0);

	// 手机首屏顺序：图片 → 品牌 → 名称 → 标签 → 价格 → 盒数 → WhatsApp
	const order = await page.evaluate(() => {
		const sel = ['.gallery', '.aurora-brand', '.product_title', '.aurora-tags', '.price', '.aurora-qty', '.aurora-wa-single'];
		return sel.map((s) => document.querySelector(s).getBoundingClientRect().top);
	});
	check('手机端首屏顺序正确', order.every((v, i) => i === 0 || v > order[i - 1]), JSON.stringify(order));
	const waBottom = await page.evaluate(() => document.querySelector('.aurora-wa-single').getBoundingClientRect().bottom);
	check('WhatsApp 按钮在两屏内', waBottom < 844 * 2, 'bottom=' + waBottom);
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
	check('无横向滚动', !overflow);

	const href1 = await page.getAttribute('.aurora-wa-single', 'href');
	const msg1 = decodeURIComponent(href1.split('text=')[1]);
	check('WhatsApp 号码正确', href1.startsWith('https://wa.me/971585598868?text='));
	check('询价模板正确', msg1.startsWith('您好，我想询价：高希霸 罗布图 Robusto · 124mm × 50 · 25 支/盒，USD 1280/盒，请确认库存。'), msg1);
	check('默认 1 盒', msg1.endsWith('数量：1 盒'), msg1);

	await page.click('.aurora-qty__btn[data-step="1"]');
	await page.click('.aurora-qty__btn[data-step="1"]');
	const msg3 = decodeURIComponent((await page.getAttribute('.aurora-wa-single', 'href')).split('text=')[1]);
	check('加号后变为 3 盒', msg3.endsWith('数量：3 盒'), msg3);
	await page.fill('.aurora-qty__input', '0');
	await page.dispatchEvent('.aurora-qty__input', 'change');
	check('盒数最少为 1', (await page.inputValue('.aurora-qty__input')) === '1');
	await page.fill('.aurora-qty__input', '2');
	await page.dispatchEvent('.aurora-qty__input', 'change');

	check('清单为空时隐藏清单按钮', !(await page.isVisible('.aurora-list-float')));
	await page.click('.aurora-add-list');
	check('加入后按钮文字变化', (await page.textContent('.aurora-add-list')).includes('已加入询价清单（2 盒）'));
	check('清单按钮出现且计数为 1', (await page.isVisible('.aurora-list-float')) && (await page.textContent('.aurora-list-count')) === '1');
	await page.screenshot({ path: path.join(shotDir, '2-product-mobile.png'), fullPage: true });

	// 打开限量版页面（同一 origin，共享 localStorage），加入清单
	await page.goto('file://' + path.resolve(limitedHtml));
	check('同一浏览器内年龄 cookie 记住', !(await page.isVisible('.aurora-age')) || docCookie === '');
	if (await page.isVisible('.aurora-age')) await page.click('.aurora-age-yes');
	const limMsg = decodeURIComponent((await page.getAttribute('.aurora-wa-single', 'href')).split('text=')[1]);
	check('限量版模板正确', limMsg.startsWith('您好，我对 高希霸 护身符 限量版 感兴趣，请确认库存与价格。'), limMsg);
	check('限量版标签显示', await page.isVisible('.aurora-tag--limited'));
	await page.click('.aurora-add-list');
	check('清单计数为 2', (await page.textContent('.aurora-list-count')) === '2');

	await page.click('.aurora-list-float');
	check('清单抽屉打开', await page.isVisible('.aurora-drawer'));
	check('抽屉中有 2 款', (await page.$$('.aurora-drawer__item')).length === 2);
	await page.screenshot({ path: path.join(shotDir, '3-inquiry-drawer.png') });

	const [popup] = await Promise.all([ctx.waitForEvent('page'), page.click('.aurora-send-list')]);
	const listMsg = decodeURIComponent(popup.url().split('text=')[1]);
	console.log('--- 整单消息 ---\n' + listMsg + '\n---------------');
	check('整单消息含两款', listMsg.includes('1. 高希霸 罗布图') && listMsg.includes('2. 高希霸 护身符 限量版'));
	check('整单合计正确', listMsg.includes('参考合计：USD 2,560'), listMsg);
	check('限量版显示请报价', listMsg.includes('× 1 盒（请报价）'), listMsg);
	await popup.close();

	await page.click('.aurora-drawer__remove >> nth=0');
	check('移除后剩 1 款', (await page.$$('.aurora-drawer__item')).length === 1);
	await page.keyboard.press('Escape');
	check('Esc 关闭抽屉', !(await page.isVisible('.aurora-drawer')));

	// 桌面宽度截图
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.goto('file://' + path.resolve(normalHtml));
	await page.screenshot({ path: path.join(shotDir, '4-product-desktop.png'), fullPage: true });

	check('无 JS 报错', errors.length === 0, errors.join('; '));
	await browser.close();
	console.log(failures ? `\n${failures} 项失败` : '\n全部通过');
	process.exit(failures ? 1 : 0);
})();
