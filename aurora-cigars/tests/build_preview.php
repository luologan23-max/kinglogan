<?php
/**
 * 生成整站静态预览（首页 / 商店 / 产品页 / FAQ），用真实插件代码与内容文件渲染。
 * 产品为示例数据。用法：php tests/build_preview.php > preview.html
 */

require __DIR__ . '/wp_stubs.php';

function do_shortcode( $content ) {
	return preg_replace_callback( '/\[(\w+)([^\]]*)\]/', function ( $m ) {
		if ( 'products' === $m[1] ) {
			return aurora_preview_loop( 8 );
		}
		if ( empty( $GLOBALS['shortcodes'][ $m[1] ] ) ) {
			return $m[0];
		}
		preg_match_all( '/(\w+)="([^"]*)"/', $m[2], $pairs, PREG_SET_ORDER );
		$atts = array();
		foreach ( $pairs as $p ) {
			$atts[ $p[1] ] = $p[2];
		}
		return $GLOBALS['shortcodes'][ $m[1] ]( $atts );
	}, $content );
}
function wc_get_page_permalink( $p ) { return '#shop'; }
function is_product_category() { return false; }
function get_queried_object_id() { return 0; }

class Preview_Product {
	public $d;
	function __construct( $d ) { $this->d = $d; }
	function get_meta( $k ) {
		$k = substr( $k, 7 );
		return isset( $this->d[ $k ] ) ? $this->d[ $k ] : '';
	}
	function get_id() { return $this->d['id']; }
	function get_name() { return $this->d['name']; }
	function get_price() { return $this->d['price']; }
	function get_permalink() { return '#product'; }
	function get_sku() { return $this->d['sku']; }
	function is_in_stock() { return true; }
}

// 示例产品：规格为公开参数，价格仅为占位
$GLOBALS['preview_products'] = array_map( function ( $d ) { return new Preview_Product( $d ); }, array(
	array( 'id' => 1, 'sku' => 'COH-ROB-25', 'name' => '高希霸 罗布图', 'name_en' => 'Cohiba Robustos', 'brand' => 'Cohiba', 'vitola' => 'Robusto', 'length' => '124', 'ring' => '50', 'box_count' => '25', 'strength' => '中等至浓郁', 'origin' => 'Cuba', 'price' => '1280' ),
	array( 'id' => 2, 'sku' => 'COH-SIG-25', 'name' => '高希霸 世纪六号', 'name_en' => 'Cohiba Siglo VI', 'brand' => 'Cohiba', 'vitola' => 'Cañonazo', 'length' => '150', 'ring' => '52', 'box_count' => '25', 'strength' => '中等至浓郁', 'origin' => 'Cuba', 'price' => '1850' ),
	array( 'id' => 3, 'sku' => 'MON-4-25', 'name' => '蒙特克里斯托 4号', 'name_en' => 'Montecristo No.4', 'brand' => 'Montecristo', 'vitola' => 'Mareva', 'length' => '129', 'ring' => '42', 'box_count' => '25', 'strength' => '中等', 'origin' => 'Cuba', 'price' => '520' ),
	array( 'id' => 4, 'sku' => 'MON-2-25', 'name' => '蒙特克里斯托 2号', 'name_en' => 'Montecristo No.2', 'brand' => 'Montecristo', 'vitola' => 'Pirámide', 'length' => '156', 'ring' => '52', 'box_count' => '25', 'strength' => '中等至浓郁', 'origin' => 'Cuba', 'price' => '780' ),
	array( 'id' => 5, 'sku' => 'PAR-SD4-25', 'name' => '帕特加斯 D4', 'name_en' => 'Partagás Serie D No.4', 'brand' => 'Partagás', 'vitola' => 'Robusto', 'length' => '124', 'ring' => '50', 'box_count' => '25', 'strength' => '浓郁', 'origin' => 'Cuba', 'price' => '640' ),
	array( 'id' => 6, 'sku' => 'RYJ-WC-25', 'name' => '罗密欧与朱丽叶 宽丘吉尔', 'name_en' => 'Romeo y Julieta Wide Churchills', 'brand' => 'Romeo y Julieta', 'vitola' => 'Montesco', 'length' => '130', 'ring' => '55', 'box_count' => '25', 'strength' => '中等', 'origin' => 'Cuba', 'price' => '690' ),
	array( 'id' => 7, 'sku' => 'HUP-M46-25', 'name' => '乌普曼 Magnum 46', 'name_en' => 'H. Upmann Magnum 46', 'brand' => 'H. Upmann', 'vitola' => 'Corona Gorda', 'length' => '143', 'ring' => '46', 'box_count' => '25', 'strength' => '中等偏淡', 'origin' => 'Cuba', 'price' => '560' ),
	array( 'id' => 8, 'sku' => 'TRI-VIG-12', 'name' => '特立尼达 维希亚', 'name_en' => 'Trinidad Vigía', 'brand' => 'Trinidad', 'vitola' => 'Vigía', 'length' => '110', 'ring' => '54', 'box_count' => '12', 'strength' => '中等至浓郁', 'origin' => 'Cuba', 'price' => '620', 'limited' => '' ),
) );

require dirname( __DIR__ ) . '/plugin/aurora-core/aurora-core.php';

function aurora_preview_loop( $n ) {
	$keep = isset( $GLOBALS['product'] ) ? $GLOBALS['product'] : null;
	$out  = '<div class="woocommerce columns-4"><ul class="products columns-4">';
	foreach ( array_slice( $GLOBALS['preview_products'], 0, $n ) as $p ) {
		$GLOBALS['product'] = $p;
		ob_start();
		do_action( 'woocommerce_shop_loop_item_title' );
		$brand = ob_get_clean();
		ob_start();
		do_action( 'woocommerce_after_shop_loop_item_title' );
		$spec = ob_get_clean();
		$out .= '<li class="product"><a href="#product" class="woocommerce-LoopProduct-link"><img class="aurora-ph" src="placeholder.svg" alt="">'
			. $brand . '<h2 class="woocommerce-loop-product__title">' . esc_html( $p->get_name() ) . '</h2>' . $spec
			. '<span class="price"><span class="woocommerce-Price-amount">$' . number_format( (float) $p->get_price() ) . '</span></span></a>'
			. apply_filters( 'woocommerce_loop_add_to_cart_link', '', $p ) . '</li>';
	}
	$GLOBALS['product'] = $keep;
	return $out . '</ul></div>';
}

$content = dirname( __DIR__ ) . '/content/pages/';
do_action( 'wp_enqueue_scripts' );

// 产品页
$GLOBALS['product'] = $GLOBALS['preview_products'][0];
$GLOBALS['product']->d['description'] = '';
ob_start();
do_action( 'woocommerce_single_product_summary' );
$summary = ob_get_clean();
$tabs = apply_filters( 'woocommerce_product_tabs', array() );
ob_start();
$tabs['aurora_spec']['callback']();
$spec_tab = ob_get_clean();
ob_start();
$tabs['aurora_shipping']['callback']();
$ship_tab = ob_get_clean();

ob_start();
do_action( 'woocommerce_before_shop_loop' );
$brand_nav = ob_get_clean();

ob_start();
do_action( 'astra_footer_before' );
$site_footer = ob_get_clean();
ob_start();
do_action( 'wp_footer' );
$footer = ob_get_clean();

$brands_json = json_decode( file_get_contents( dirname( __DIR__ ) . '/content/brands.json' ), true );
$css = file_get_contents( dirname( __DIR__ ) . '/plugin/aurora-core/assets/aurora.css' );
$js  = file_get_contents( dirname( __DIR__ ) . '/plugin/aurora-core/assets/aurora.js' );
$svg = 'data:image/svg+xml;base64,' . base64_encode( file_get_contents( dirname( __DIR__ ) . '/plugin/aurora-core/assets/placeholder.svg' ) );
$menu = array( '首页' => 'home', '雪茄 Cigars' => 'shop', '产品页示例' => 'product', '常见问题' => 'faq' );
?>
<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurora Cigars 预览</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="<?php echo esc_attr( $GLOBALS['enqueued'][0] ); ?>">
<style>
<?php echo $css; ?>
body { margin: 0; }
.pv-bar { position: sticky; top: 0; z-index: 9980; background: var(--au-paper); border-bottom: 1px solid var(--au-line); }
.pv-bar__inner { display: flex; align-items: center; gap: 24px; max-width: 1120px; margin: 0 auto; padding: 14px 16px; }
.pv-logo { font-family: var(--au-serif-display); font-size: 20px; letter-spacing: .4em; color: var(--au-black); text-decoration: none; }
.pv-nav { display: flex; gap: 18px; overflow-x: auto; scrollbar-width: none; }
.pv-nav a { flex: none; font-family: var(--au-sans); font-size: 13px; letter-spacing: .06em; color: var(--au-ink); text-decoration: none; padding: 4px 0; border-bottom: 1px solid transparent; }
.pv-nav a[aria-current="page"] { border-color: var(--au-gold); color: var(--au-gold-deep); }
.pv-note { margin: 0; padding: 8px 16px; background: var(--au-cream); text-align: center; font-family: var(--au-sans); font-size: 12px; color: var(--au-muted); }
.pv-view { display: none; }
.pv-view.is-active { display: block; }
.woocommerce ul.products { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 32px 24px; margin: 0; padding: 0; list-style: none; }
.woocommerce ul.products a.woocommerce-LoopProduct-link { color: inherit; text-decoration: none; display: block; }
.woocommerce ul.products h2 { margin: 0; line-height: 1.3; }
.aurora-ph { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; }
.pv-product { display: grid; grid-template-columns: 1fr 1fr; gap: 48px; max-width: 1120px; margin: 0 auto; padding: 32px 16px; }
.pv-product .summary { display: flex; flex-direction: column; }
.pv-tabs { max-width: 1120px; margin: 0 auto; padding: 0 16px 64px; display: grid; grid-template-columns: 1fr 1fr; gap: 48px; }
.pv-tabs h3 { font-size: 22px; }
.pv-brandlist { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 32px; }
.pv-brandlist h3 { margin: 0 0 .3em; font-size: 22px; }
.pv-brandlist p { margin: 0; white-space: pre-line; font-size: 15px; color: var(--au-muted); }
@media (max-width: 768px) {
	.woocommerce ul.products { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px 12px; }
	.woocommerce ul.products li.product .woocommerce-loop-product__title { font-size: 16px; }
	.aurora-spec-line--loop { font-size: 12px; }
	.pv-product, .pv-tabs, .pv-brandlist { grid-template-columns: 1fr; gap: 20px; }
	.pv-bar__inner { flex-direction: column; align-items: flex-start; gap: 8px; }
}
</style>
</head>
<body>
<header class="pv-bar"><div class="pv-bar__inner">
	<a class="pv-logo" href="#home">AURORA</a>
	<nav class="pv-nav" aria-label="预览页面">
	<?php foreach ( $menu as $label => $id ) : ?>
		<a href="#<?php echo esc_attr( $id ); ?>" data-view="<?php echo esc_attr( $id ); ?>"><?php echo esc_html( $label ); ?></a>
	<?php endforeach; ?>
	</nav>
</div></header>
<p class="pv-note">预览 · 产品与价格为示例数据，正式上线后替换为您的 142 款产品</p>

<main>
<section class="pv-view" id="view-home">
	<?php echo do_shortcode( file_get_contents( $content . 'home.html' ) ); ?>
</section>

<section class="pv-view woocommerce" id="view-shop">
	<div class="aurora-section">
		<h1 class="aurora-section__title">全部雪茄 · Cigars</h1>
		<?php echo $brand_nav; ?>
		<?php echo aurora_preview_loop( 8 ); ?>
	</div>
	<div class="aurora-section">
		<h2 class="aurora-section__title">品牌故事 · The Houses</h2>
		<div class="pv-brandlist">
		<?php foreach ( $brands_json as $b ) : ?>
			<div><h3><?php echo esc_html( $b['name'] ); ?> <small style="font-family:var(--au-sans);font-size:14px;color:var(--au-muted)"><?php echo esc_html( $b['name_cn'] ); ?></small></h3><p><?php echo esc_html( $b['description'] ); ?></p></div>
		<?php endforeach; ?>
		</div>
	</div>
</section>

<section class="pv-view woocommerce" id="view-product">
	<div class="product pv-product">
		<img class="aurora-ph" src="placeholder.svg" alt="产品图片">
		<div class="summary">
			<h1 class="product_title"><?php echo esc_html( $GLOBALS['product']->get_name() ); ?></h1>
			<p class="price"><span class="woocommerce-Price-amount">$1,280</span></p>
			<?php echo $summary; ?>
		</div>
	</div>
	<div class="pv-tabs">
		<div><h3>规格参数 Specs</h3><?php echo $spec_tab; ?></div>
		<div><h3>配送与说明 Shipping</h3><?php echo $ship_tab; ?></div>
	</div>
</section>

<section class="pv-view" id="view-faq">
	<?php echo do_shortcode( file_get_contents( $content . 'faq.html' ) ); ?>
</section>
</main>

<?php echo $site_footer; ?>
<?php echo $footer; ?>
<script>window.AURORA=<?php echo json_encode( $GLOBALS['localized'][1] ); ?>;</script>
<script><?php echo str_replace( '</script', '<\/script', $js ); ?></script>
<script>
(function () {
	var ph = <?php echo json_encode( $svg ); ?>;
	document.querySelectorAll('img[src="placeholder.svg"]').forEach(function (img) { img.src = ph; });
	function show() {
		var id = (location.hash || '#home').slice(1);
		if (!document.getElementById('view-' + id)) id = 'home';
		document.querySelectorAll('.pv-view').forEach(function (v) { v.classList.toggle('is-active', v.id === 'view-' + id); });
		document.querySelectorAll('.pv-nav a').forEach(function (a) {
			if (a.dataset.view === id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
		});
		document.body.classList.toggle('single-product', id === 'product');
		window.scrollTo(0, 0);
	}
	// 站内链接指向预览视图
	document.querySelectorAll('a[href="/shop/"], a[href="#shop"], a[href^="#brand-"]').forEach(function (a) { a.href = '#shop'; });
	document.querySelectorAll('a[href="/faq/"]').forEach(function (a) { a.href = '#faq'; });
	window.addEventListener('hashchange', show);
	show();
})();
</script>
</body></html>
