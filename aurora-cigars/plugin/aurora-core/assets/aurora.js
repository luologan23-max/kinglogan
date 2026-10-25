/* Aurora Cigars 前端：盒数选择、WhatsApp 询价、询价清单、年龄验证 */
(function () {
	'use strict';

	var cfg = window.AURORA || { wa: '', minAge: 21, ageDays: 30 };
	var STORE_KEY = 'aurora_inquiry_v1';

	function waLink(text) {
		return 'https://wa.me/' + cfg.wa + '?text=' + encodeURIComponent(text);
	}

	function clampQty(v) {
		var n = parseInt(v, 10);
		if (isNaN(n) || n < 1) return 1;
		return Math.min(n, 99);
	}

	/* ---------- 询价清单存储（仅本机浏览器） ---------- */
	function loadList() {
		try {
			var list = JSON.parse(localStorage.getItem(STORE_KEY) || '[]');
			return Array.isArray(list) ? list : [];
		} catch (e) {
			return [];
		}
	}

	function saveList(list) {
		try {
			localStorage.setItem(STORE_KEY, JSON.stringify(list));
		} catch (e) { /* 隐私模式下忽略 */ }
		renderList(list);
	}

	function listMessage(list) {
		var lines = ['您好，我想询价以下雪茄，请确认库存：'];
		var total = 0;
		list.forEach(function (item, i) {
			var price = parseFloat(item.price);
			var line = (i + 1) + '. ' + item.name + (item.spec ? ' ' + item.spec : '') + ' × ' + item.qty + ' 盒';
			if (!isNaN(price) && !item.limited) {
				line += '（USD ' + price.toLocaleString('en-US') + '/盒）';
				total += price * item.qty;
			} else {
				line += '（请报价）';
			}
			lines.push(line);
		});
		if (total > 0) {
			lines.push('参考合计：USD ' + total.toLocaleString('en-US'));
		}
		return lines.join('\n');
	}

	/* ---------- 产品详情页 ---------- */
	function initProduct(box) {
		var input = box.querySelector('.aurora-qty__input');
		var waBtn = box.querySelector('.aurora-wa-single');
		var addBtn = box.querySelector('.aurora-add-list');

		function update() {
			var qty = clampQty(input.value);
			input.value = qty;
			waBtn.href = waLink(box.dataset.message + '\n数量：' + qty + ' 盒');
		}

		box.querySelectorAll('.aurora-qty__btn').forEach(function (btn) {
			btn.addEventListener('click', function () {
				input.value = clampQty(input.value) + parseInt(btn.dataset.step, 10);
				update();
			});
		});
		input.addEventListener('change', update);
		update();

		addBtn.addEventListener('click', function () {
			var list = loadList();
			var qty = clampQty(input.value);
			var found = list.filter(function (i) { return String(i.id) === box.dataset.id; })[0];
			if (found) {
				found.qty = qty;
			} else {
				list.push({
					id: box.dataset.id,
					name: box.dataset.name,
					spec: box.dataset.spec,
					price: box.dataset.price,
					url: box.dataset.url,
					limited: box.dataset.limited === '1',
					qty: qty
				});
			}
			saveList(list);
			addBtn.classList.add('is-added');
			addBtn.textContent = '✓ 已加入询价清单（' + qty + ' 盒）';
		});
	}

	/* ---------- 询价清单抽屉 ---------- */
	var drawer = document.querySelector('.aurora-drawer');
	var floatBtn = document.querySelector('.aurora-list-float');

	function renderList(list) {
		if (!drawer) return;
		var ul = drawer.querySelector('.aurora-drawer__items');
		ul.textContent = '';
		list.forEach(function (item, idx) {
			var li = document.createElement('li');
			li.className = 'aurora-drawer__item';

			var a = document.createElement('a');
			a.className = 'aurora-drawer__name';
			a.href = item.url;
			a.textContent = item.name;

			var meta = document.createElement('span');
			meta.className = 'aurora-drawer__meta';
			meta.textContent = (item.spec ? item.spec + ' · ' : '') +
				(item.price && !item.limited ? 'USD ' + parseFloat(item.price).toLocaleString('en-US') + '/盒' : '请报价');

			var ctrl = document.createElement('span');
			ctrl.className = 'aurora-drawer__ctrl';
			var qty = document.createElement('input');
			qty.type = 'number';
			qty.min = '1';
			qty.max = '99';
			qty.value = item.qty;
			qty.setAttribute('aria-label', item.name + ' 盒数');
			qty.addEventListener('change', function () {
				var l = loadList();
				l[idx].qty = clampQty(qty.value);
				saveList(l);
			});
			var rm = document.createElement('button');
			rm.type = 'button';
			rm.className = 'aurora-drawer__remove';
			rm.setAttribute('aria-label', '移除 ' + item.name);
			rm.textContent = '×';
			rm.addEventListener('click', function () {
				var l = loadList();
				l.splice(idx, 1);
				saveList(l);
			});
			ctrl.appendChild(qty);
			ctrl.appendChild(rm);

			li.appendChild(a);
			li.appendChild(meta);
			li.appendChild(ctrl);
			ul.appendChild(li);
		});

		drawer.querySelector('.aurora-drawer__empty').hidden = list.length > 0;
		drawer.querySelector('.aurora-drawer__foot').hidden = list.length === 0;
		if (floatBtn) {
			floatBtn.hidden = list.length === 0;
			floatBtn.querySelector('.aurora-list-count').textContent = list.length;
		}
	}

	function openDrawer() {
		renderList(loadList());
		drawer.hidden = false;
		drawer.querySelector('.aurora-drawer__close').focus();
	}

	function closeDrawer() {
		drawer.hidden = true;
		if (floatBtn) floatBtn.focus();
	}

	if (drawer) {
		floatBtn && floatBtn.addEventListener('click', openDrawer);
		drawer.querySelector('.aurora-drawer__close').addEventListener('click', closeDrawer);
		drawer.addEventListener('click', function (e) {
			if (e.target === drawer) closeDrawer();
		});
		document.addEventListener('keydown', function (e) {
			if (e.key === 'Escape' && !drawer.hidden) closeDrawer();
		});
		drawer.querySelector('.aurora-send-list').addEventListener('click', function () {
			var list = loadList();
			if (!list.length) return;
			var url = waLink(listMessage(list));
			// 部分手机浏览器会拦截弹窗，拦截时改为当前页跳转
			var win = window.open(url, '_blank');
			if (win) {
				win.opener = null;
			} else {
				window.location.href = url;
			}
		});
		drawer.querySelector('.aurora-clear-list').addEventListener('click', function () {
			saveList([]);
		});
		document.querySelectorAll('[data-aurora-open-list]').forEach(function (el) {
			el.addEventListener('click', function (e) {
				e.preventDefault();
				openDrawer();
			});
		});
		renderList(loadList());
	}

	document.querySelectorAll('.aurora-inquiry').forEach(initProduct);

	/* ---------- 年龄验证（Cookie 记住 N 天） ---------- */
	var gate = document.querySelector('.aurora-age');
	if (gate) {
		if (document.cookie.indexOf('aurora_age_ok=1') !== -1) {
			gate.hidden = true;
		} else {
			document.documentElement.style.overflow = 'hidden';
			gate.querySelector('.aurora-age-yes').addEventListener('click', function () {
				var days = cfg.ageDays || 30;
				document.cookie = 'aurora_age_ok=1; max-age=' + (days * 86400) + '; path=/; SameSite=Lax';
				gate.hidden = true;
				document.documentElement.style.overflow = '';
			});
		}
	}
})();
