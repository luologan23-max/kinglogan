<?php
/** 换号接口测试：/wp-json/aurora/v1/whatsapp 读写插件设置里的 WhatsApp 号码。php tests/whatsapp_route_test.php */
require __DIR__ . '/wp_stubs.php';
function aur6_card_open() {}
function get_transient( $k ) { return false; }
function set_transient( $k, $v, $t = 0 ) { return true; }
function delete_transient( $k ) { return true; }
function current_user_can( $cap ) { return ! empty( $GLOBALS['can_edit'] ); }
function get_post_meta( $id, $key = '', $single = false ) { return ''; }
function register_setting( ...$a ) {}
function register_rest_field( ...$a ) {}
function wp_generate_password( $n = 12 ) { return str_repeat( 'k', $n ); }
function register_rest_route( $ns, $route, $handlers ) { $GLOBALS['routes'][ "$ns$route" ] = $handlers; }
class WP_Error {
	public $code;
	function __construct( $code, $msg = '', $data = array() ) { $this->code = $code; }
}
class Fake_WPDB {
	public $prefix = 'wp_';
	function prepare( $q, ...$a ) { return $q; }
	function get_var( $q ) { return null; }
	function get_col( $q ) { return array(); }
}
$GLOBALS['wpdb']    = new Fake_WPDB();
$GLOBALS['product'] = new Fake_Product( false );
require dirname( __DIR__ ) . '/plugin/aurora-core/aurora-core.php';

$fail = 0;
function check( $name, $ok ) { global $fail; echo ( $ok ? 'PASS ' : 'FAIL ' ) . $name . "\n"; $fail += $ok ? 0 : 1; }

do_action( 'rest_api_init' );
$handlers = $GLOBALS['routes']['aurora/v1/whatsapp'] ?? array();
list( $get, $post ) = $handlers + array( null, null );
check( '注册了换号接口', $get && $post && 'GET' === $get['methods'] && 'POST' === $post['methods'] );

$GLOBALS['can_edit'] = false;
check( '没有店铺管理权限不能读写', ! $get['permission_callback']() && ! $post['permission_callback']() );
$GLOBALS['can_edit'] = true;
check( '店铺管理员可以读写', $get['permission_callback']() && $post['permission_callback']() );

$GLOBALS['options']['aurora_core'] = array( 'email' => 'a@b.c' );
check( '没存过号码时读到默认号码', '971585598868' === $get['callback']()['whatsapp'] );
$out = $post['callback']( array( 'whatsapp' => '+971 58 571 1167' ) );
check( '保存时只留数字', '971585711167' === $out['whatsapp'] && '971585711167' === aurora_opt( 'whatsapp' ) );
check( '其他设置不受影响', 'a@b.c' === $GLOBALS['options']['aurora_core']['email'] );
check( '位数不对的号码拒绝保存', $post['callback']( array( 'whatsapp' => '123' ) ) instanceof WP_Error
	&& '971585711167' === aurora_opt( 'whatsapp' ) );

echo $fail ? "\n$fail 项失败\n" : "\n全部通过\n";
exit( $fail ? 1 : 0 );
