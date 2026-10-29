# 组件与选择器速查

从 2026-10-29 的诊断包（`aurora-audit-配图后.zip`）量出来的线上样式。要改某个组件时，先在最新诊断包里搜同名选择器确认现值，
这里的数字可能已经过时。

## 由谁输出

| 部分 | 来源 | 备注 |
|---|---|---|
| 设计变量、商品卡、列表页 | Code Snippets #11「Design System v5 (Boutique Cream CSS)」（site-css 片段） | 插件把它作为 `aurora-site-css-1` 输出到页面 |
| 产品页布局、手机底部操作条 | Code Snippets #14「BOM — Product Page v4 (Sticky Image + Fixed Bar)」 | PHP 片段，输出 `.aur-product-wrap` 那一整套 |
| 导航、滚动信息条、页脚、语言切换、全局 CSS | Code Snippets #15「BOM — Global CSS + Nav + Ticker + Footer + Lang」 | 第二套 `:root` 变量也在这里（`--gold-light` 值不同） |
| 询价清单 | Code Snippets #13「Request List JS (via wp_footer)」 | localStorage 清单，插件做了格式兼容 |
| 整合补丁 | 插件 `plugin/aurora-core/assets/aurora-integrate.css` / `.js` | 去主题重复元素、去圆角阴影、触屏显示卡片按钮、修复失效的 onclick |
| 手写页面（首页、关于、FAQ、批发、限量等） | WordPress 页面内容本身（HTML + 内嵌 style），插件给这些页面加 `aurora-pages.css` | 插件会跳过 wpautop / wptexturize |
| 主题 | Astra 4.13（Elementor 已安装但这些页面没用它） | 断点 921px / 544px |

#16–#22 是以前插件安装器留下的片段，全部停用，可以在后台删掉。

## 关键选择器和现值

**导航** `#aurora-nav`：`padding:18px 48px; border-bottom:.5px solid var(--border); background:var(--cream); position:sticky; top:0; z-index:400`。
语言按钮 `.aurora-lang-btn`（10–13px，手机上点按区只有 18–21px 高，偏小）。WhatsApp 图标 `.aurora-nav-wa-icon` 38×38。
滚动条 `.aurora-ticker` / `.aurora-ticker-item`（9px 字）。

**列表页**：`.aur-page-header` / `.aur-page-title` / `.aur-page-subtitle`；品牌标签 `.aur-brand-tabs` > `.aur-brand-tab`（11px 大写，选中下划线 1.5px）；
筛选 `.aur-filters-bar` > `.aur-filter-btn`（11px，.5px 边框）；分页 `.aur-pagination`。

**商品卡** `li.product .aur-card`：
- `.aur-card-link` > `.aur-card-img-wrap`（220px 高，手机 160px，底色 `#EDEAE4`，悬停 `#E8E4DC`）> `img.aur-card-img`（`object-fit:cover`）
- `.aur-badge`（左上角 9px 大写标签，如「可调货」`aur-badge-request`）
- `.aur-card-actions` > `.aur-action-btn`（「＋」加入清单；触屏常显，鼠标设备悬停显示）
- `.aur-card-info`（`padding:18px 20px 20px`）> `.aur-card-brand`（9px 金色大写）> `.aur-card-name`（17px serif）> `.aur-card-spec`
- `.aur-card-footer`（`border-top:.5px`）> `.aur-card-price`（19px serif）/「联系询价」+ `.aur-wa-small`

**产品页** `.aur-product-wrap`：
- 左 `.aur-img-col`（`--bg-warm` 底，sticky，`height:calc(100vh - 57px)`）> `.aur-img-frame`（正方形，最大 320px，`#EAE6DE` 底，`#CCC7BC` 边框，内缩 10px 的第二道细线）> `.aur-product-main-img`（cover）；
  `.aur-img-thumbs` > `.aur-thumb`（56×56）
- 右 `.aur-info-col`：`.aur-product-breadcrumb`、`.aur-product-name-cn`（38px）、`.aur-product-name-en`（19px 斜体 `#5A5A56`）、
  `.aur-status-row`（`.aur-status-item`、`.aur-sealed-pill`）、`.aur-price-block` / `.aur-price-ask-block`、
  `.aur-cta-group` > `.aur-btn-wa`（黑底白字 11px 大写）+ `.aur-btn-enquiry`（描边）、
  `.aur-policy-grid`（4 列，`.aur-policy-cell` > `.aur-pc-icon/.aur-pc-label/.aur-pc-sub`）、
  `.aur-specs-section` > `.aur-spec-grid`（2 列，1px 间隙做分隔线，`.aur-sg-lbl/.aur-sg-val`，`.aur-sg-wide` 跨两列）、`.aur-tasting-section`
- 手机：`.aur-mobile-identity`（品牌、中英文名）、`.aur-bottom-bar`（固定底部，`--ink` 底；`.aur-bb-qty-row` 数量、`.aur-bb-btn` 绿色 WhatsApp `#25D366`、`.aur-bb-list` 加入清单）

**浮动**：`.aur-enquiry-float`（右下 28px，内含 `.aur-wa-float` 48×48 绿色方块、`.aur-enquiry-count`）。
有底部操作条时插件会隐藏重复的 `.aurora-wa-float`。

**首页（手写页面，类名前缀 `aurora-`）**：`aurora-hero`（eyebrow / title / sub / actions / stats / 右侧图片框）、
`aurora-hvb` 横幅、`aurora-hvm` 品牌介绍块、`aurora-brand-grid` > `aurora-brand-card`、`aurora-products-section` > `aurora-product-card`、
`aurora-limited-banner` / `aurora-limited-section`、`aurora-trust` > `aurora-trust-item`。样式由页面内嵌 style + `aurora-pages.css`（`--ap-*` 变量映射到上面的配色）。

## 已知的不一致和问题（改设计时顺手处理）

- 两套 `:root`：#11 和 #15 各定义一次变量，`--gold-light` 一个是 `#F0E6D0` 一个是 `#F5EDD8`。
- 小字：滚动条、角标、品牌小标题都是 9px，中文 9px 在手机上难读。
- 对比度：`--ink-light`、`--gold` 在奶油底上约 2.6:1，用在小字上不达标。
- 点按区：手机上语言按钮、面包屑链接、品牌标签高度不到 40px。
- 图片风格：实拍图（白底横放）和品牌渲染图（深色斜放）混排。
- 「询价」页（request-quote）是旧 YITH 插件留下的页面，插件把它转到「我的需求单」。
