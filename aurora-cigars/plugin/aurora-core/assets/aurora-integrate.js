/* Aurora 整合模式：让站点自有的「加入询价清单」按钮真正可用，并接到站点需求单（window.AuroraRL）。
   站点片段里有两个问题：
   1. 商品卡「＋」、产品页「加入询价清单」、底栏清单按钮的 onclick 把 json_encode 的产品名
      （带双引号）直接放进了双引号属性里，属性被截断，点击时脚本语法错误，按钮从未生效。
   2. 这些按钮写入的是 […] 数组，而需求单页面按 {items:[…]} 读取。
   这里移除坏掉的 onclick，改为从页面读取产品信息，统一按 {items:[…]} 写入；
   旧的数组数据由页头的内联脚本先行转换。 */
(function () {
	'use strict';

	function count() {
		try {
			var data = window.AuroraRL ? window.AuroraRL.getList() : null;
			return data && data.items ? data.items.length : 0;
		} catch (e) {
			return 0;
		}
	}

	// 「询价清单 N 款」悬浮按钮
	function refreshFloat() {
		var n = count();
		var num = document.getElementById('aurEnquiryNum');
		var box = document.getElementById('aurEnquiryCount');
		if (num) num.textContent = n;
		if (box) box.style.display = n > 0 ? 'flex' : 'none';
	}

	function text(root, sel) {
		var el = root && root.querySelector(sel);
		return el ? el.textContent.trim() : '';
	}

	function add(item) {
		if (!window.AuroraRL || !item.pid) return;
		window.AuroraRL.add({
			sku: 'P' + item.pid,
			name: item.name,
			brand: item.brand || '',
			image: item.image || '',
			stockStatus: item.inStock ? 'in_stock' : 'sourcing',
			quantity: item.qty || 1
		});
		refreshFloat();
	}

	function flash(el) {
		if (!el) return;
		el.classList.add('is-added');
		setTimeout(function () { el.classList.remove('is-added'); }, 1600);
	}

	// 商品卡：产品 ID 取自 li 的 post-N 类名
	function fromCard(li) {
		var id = (li.className.match(/\bpost-(\d+)\b/) || [])[1];
		var img = li.querySelector('.aur-card-img, img');
		return {
			pid: id,
			name: text(li, '.aur-card-name'),
			brand: text(li, '.aur-card-brand'),
			image: img ? img.currentSrc || img.src : '',
			inStock: !li.classList.contains('outofstock'),
			qty: 1
		};
	}

	// 产品页：产品 ID 取自 body 的 postid-N，盒数取自底栏
	function fromProduct() {
		var id = (document.body.className.match(/\bpostid-(\d+)\b/) || [])[1];
		var wrap = document.getElementById('product-' + id) || document;
		var img = document.getElementById('aurMainImg');
		var qty = document.getElementById('aurBbQty');
		return {
			pid: id,
			name: text(document, '.aur-product-name-en') || text(document, '.aur-product-name-cn'),
			brand: '',
			image: img ? img.currentSrc || img.src : '',
			inStock: !(wrap.classList && wrap.classList.contains('outofstock')),
			qty: qty ? parseInt(qty.textContent, 10) || 1 : 1
		};
	}

	var CARD_BTN = 'li.product .aur-action-btn[title="加入询价清单"]';
	var PRODUCT_BTN = '.aur-btn-enquiry, .aur-bb-list';

	function bind() {
		document.querySelectorAll(CARD_BTN + ', ' + PRODUCT_BTN).forEach(function (btn) {
			btn.removeAttribute('onclick');
		});
		refreshFloat();
	}

	// 捕获阶段统一处理，阻止外层卡片链接跳转
	document.addEventListener('click', function (e) {
		var card = e.target.closest && e.target.closest(CARD_BTN);
		var single = !card && e.target.closest && e.target.closest(PRODUCT_BTN);
		if (!card && !single) return;
		e.preventDefault();
		e.stopPropagation();
		add(card ? fromCard(card.closest('li.product')) : fromProduct());
		flash(card || single);
	}, true);

	// 点击已由上面的捕获阶段处理；站点以后若修好 onclick，旧的全局函数改为空操作，避免重复加入
	window.aurAddToEnquiry = function (e) {
		if (e) { e.preventDefault(); e.stopPropagation(); }
	};
	window.aurAddToListSingle = function () {};

	window.addEventListener('aurora:listUpdated', refreshFloat);
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', bind);
	} else {
		bind();
	}
})();
