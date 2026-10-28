<?php
/** 测试用的最小 WordPress / WooCommerce 桩函数。 */

define( 'ABSPATH', __DIR__ );
$GLOBALS['hooks']      = array();
$GLOBALS['shortcodes'] = array();
$GLOBALS['removed']    = array();
$GLOBALS['cookies']    = $_COOKIE;

function add_action( $tag, $cb, $prio = 10, $args = 1 ) { $GLOBALS['hooks'][ $tag ][ $prio ][] = $cb; }
function add_filter( $tag, $cb, $prio = 10, $args = 1 ) { add_action( $tag, $cb, $prio, $args ); }
function remove_action( $tag, $cb, $prio = 10 ) { $GLOBALS['removed'][] = "$tag:$cb:$prio"; }
function remove_filter( $tag, $cb, $prio = 10 ) { remove_action( $tag, $cb, $prio ); }
function is_page() { return ! empty( $GLOBALS['is_page'] ); }
function get_queried_object() { return $GLOBALS['queried'] ?? null; }
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
$GLOBALS['options'] = array( 'default_product_cat' => 15 );
function get_option( $k, $d = false ) { return array_key_exists( $k, $GLOBALS['options'] ) ? $GLOBALS['options'][ $k ] : $d; }
function update_option( $k, $v ) { $GLOBALS['options'][ $k ] = $v; return true; }
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

