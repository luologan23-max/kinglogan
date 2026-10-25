<?php
/**
 * 无需 WordPress 的冒烟测试：用最小桩函数加载插件，执行产品页与页脚钩子，
 * 输出一个可在浏览器里测试的完整 HTML 页面。
 * 用法：php tests/render_harness.php [limited] > out.html
 */

require __DIR__ . '/wp_stubs.php';
require dirname( __DIR__ ) . '/plugin/aurora-core/aurora-core.php';

// 目录模式断言
$checks = array(
	'is_purchasable=false'  => false === apply_filters( 'woocommerce_is_purchasable', true ),
	'add_to_cart blocked'   => false === apply_filters( 'woocommerce_add_to_cart_validation', true ),
	'cart widget hidden'    => true === apply_filters( 'woocommerce_widget_cart_is_hidden', false ),
);
$GLOBALS['product'] = new Fake_Product( isset( $argv[1] ) && 'limited' === $argv[1] );
$loop = apply_filters( 'woocommerce_loop_add_to_cart_link', '<a>Add to cart</a>', $GLOBALS['product'] );
$checks['loop button replaced'] = false !== strpos( $loop, '询价' );
$tabs = apply_filters( 'woocommerce_product_tabs', array( 'description' => array( 'title' => 'Description' ), 'reviews' => array() ) );
$checks['reviews tab removed'] = ! isset( $tabs['reviews'] ) && isset( $tabs['aurora_spec'], $tabs['aurora_shipping'] );
foreach ( $checks as $name => $ok ) {
	fwrite( STDERR, ( $ok ? 'PASS ' : 'FAIL ' ) . $name . "\n" );
}

do_action( 'wp_enqueue_scripts' );
ob_start();
do_action( 'woocommerce_single_product_summary' );
$summary = ob_get_clean();
ob_start();
$tabs['aurora_spec']['callback']();
$tabs['aurora_shipping']['callback']();
$spec = ob_get_clean();
ob_start();
do_action( 'wp_footer' );
$footer = ob_get_clean();
$brands = $GLOBALS['shortcodes']['aurora_brands']( array() );

$css = file_get_contents( dirname( __DIR__ ) . '/plugin/aurora-core/assets/aurora.css' );
$js  = file_get_contents( dirname( __DIR__ ) . '/plugin/aurora-core/assets/aurora.js' );
$cfg = json_encode( $GLOBALS['localized'][1] );
?>
<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurora harness</title>
<link rel="stylesheet" href="<?php echo esc_attr( $GLOBALS['enqueued'][0] ); ?>">
<style><?php echo $css; ?> body{margin:0} .wrap{max-width:1100px;margin:0 auto;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:40px} .gallery{background:#d9d2c3;aspect-ratio:1} @media(max-width:768px){.wrap{grid-template-columns:1fr}}</style>
</head><body class="single-product">
<div class="woocommerce"><div class="product wrap">
<div class="gallery" aria-label="产品图片"></div>
<div class="summary">
<h1 class="product_title"><?php echo esc_html( $GLOBALS['product']->get_name() ); ?></h1>
<p class="price"><?php echo $GLOBALS['product']->get_price() ? '<span class="woocommerce-Price-amount">$' . $GLOBALS['product']->get_price() . '</span>' : ''; ?></p>
<?php echo $summary; ?>
</div></div></div>
<div class="aurora-section"><?php echo $spec; ?></div>
<div class="aurora-section"><?php echo $brands; ?></div>
<?php echo $footer; ?>
<script>window.AURORA=<?php echo $cfg; ?>;</script>
<script><?php echo $js; ?></script>
</body></html>
