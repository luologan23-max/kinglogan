<?php
/**
 * 无需 WordPress 的冒烟测试：用最小桩函数加载插件，执行产品页与页脚钩子，
 * 输出一个可在浏览器里测试的完整 HTML 页面。
 * 用法：php tests/render_harness.php [limited] > out.html
 */

define( 'ABSPATH', __DIR__ );
$GLOBALS['hooks']      = array();
$GLOBALS['shortcodes'] = array();
$GLOBALS['removed']    = array();
$GLOBALS['cookies']    = $_COOKIE;

function add_action( $tag, $cb, $prio = 10, $args = 1 ) { $GLOBALS['hooks'][ $tag ][ $prio ][] = $cb; }
function add_filter( $tag, $cb, $prio = 10, $args = 1 ) { add_action( $tag, $cb, $prio, $args ); }
function remove_action( $tag, $cb, $prio = 10 ) { $GLOBALS['removed'][] = "$tag:$cb:$prio"; }
function do_action( $tag ) {
	if ( empty( $GLOBALS['hooks'][ $tag ] ) ) return;
	ksort( $GLOBALS['hooks'][ $tag ] );
	foreach ( $GLOBALS['hooks'][ $tag ] as $cbs ) foreach ( $cbs as $cb ) $cb();
}
function apply_filters( $tag, $value, ...$args ) {
	if ( empty( $GLOBALS['hooks'][ $tag ] ) ) return $value;
	ksort( $GLOBALS['hooks'][ $tag ] );
	foreach ( $GLOBALS['hooks'][ $tag ] as $cbs ) foreach ( $cbs as $cb ) $value = is_string( $cb ) && '__return_false' === $cb ? false : ( '__return_true' === $cb ? true : $cb( $value, ...$args ) );
	return $value;
}
function add_shortcode( $tag, $cb ) { $GLOBALS['shortcodes'][ $tag ] = $cb; }
function shortcode_atts( $pairs, $atts ) { return array_merge( $pairs, (array) $atts ); }
function plugin_dir_url( $f ) { return './'; }
function get_option( $k, $d = false ) { return 'default_product_cat' === $k ? 15 : $d; }
function esc_html( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES ); }
function esc_attr( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES ); }
function esc_url( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES ); }
function absint( $n ) { return abs( (int) $n ); }
function sanitize_text_field( $s ) { return trim( strip_tags( (string) $s ) ); }
function is_admin() { return false; }
function is_wp_error( $x ) { return false; }
function wc_format_localized_price( $p ) { return $p; }
function get_the_terms( $id, $tax ) { return array( (object) array( 'name' => 'Cohiba' ) ); }
function get_terms( $args ) {
	return array(
		(object) array( 'term_id' => 1, 'name' => 'Cohiba', 'count' => 18 ),
		(object) array( 'term_id' => 2, 'name' => 'Montecristo', 'count' => 12 ),
		(object) array( 'term_id' => 3, 'name' => 'Romeo y Julieta', 'count' => 9 ),
		(object) array( 'term_id' => 4, 'name' => 'Partagás', 'count' => 11 ),
		(object) array( 'term_id' => 5, 'name' => 'H. Upmann', 'count' => 7 ),
		(object) array( 'term_id' => 6, 'name' => 'Trinidad', 'count' => 5 ),
	);
}
function get_term_meta() { return ''; }
function get_term_link( $t ) { return '#brand-' . $t->term_id; }
function wp_get_attachment_image() { return ''; }
$GLOBALS['enqueued'] = array();
function wp_enqueue_style( $h, $src = '' ) { $GLOBALS['enqueued'][] = $src; }
function wp_enqueue_script( $h, $src = '' ) { $GLOBALS['enqueued'][] = $src; }
function wp_localize_script( $h, $name, $data ) { $GLOBALS['localized'] = array( $name, $data ); }

class Fake_Product {
	public $meta;
	public $limited;
	function __construct( $limited ) {
		$this->limited = $limited;
		$this->meta    = array(
			'aurora_brand'     => 'Cohiba',
			'aurora_name_en'   => $limited ? 'Cohiba Talismán Edición Limitada 2017' : 'Cohiba Robustos',
			'aurora_vitola'    => 'Robusto',
			'aurora_length'    => '124',
			'aurora_ring'      => '50',
			'aurora_box_count' => '25',
			'aurora_strength'  => '中等至浓郁',
			'aurora_origin'    => 'Cuba',
			'aurora_limited'   => $limited ? '是' : '',
		);
	}
	function get_meta( $k ) { return isset( $this->meta[ $k ] ) ? $this->meta[ $k ] : ''; }
	function get_id() { return $this->limited ? 102 : 101; }
	function get_name() { return $this->limited ? '高希霸 护身符 限量版' : '高希霸 罗布图'; }
	function get_price() { return $this->limited ? '' : '1280'; }
	function get_permalink() { return '#product-' . $this->get_id(); }
	function get_sku() { return 'COH-ROB-25'; }
	function is_in_stock() { return true; }
}

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
