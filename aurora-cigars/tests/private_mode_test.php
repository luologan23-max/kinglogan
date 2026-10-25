<?php
/** 内部预览模式测试：php tests/private_mode_test.php <anon|loggedin|key-good|key-bad|off> */
require __DIR__ . '/wp_stubs.php';
define( 'DAY_IN_SECONDS', 86400 );
define( 'COOKIEPATH', '/' );
define( 'COOKIE_DOMAIN', '' );
$scenario = $argv[1];
$GLOBALS['options']['aurora_preview_key'] = 'secretkey1234567';
if ( 'off' === $scenario ) {
	$GLOBALS['options']['aurora_core'] = array( 'private_mode' => 0 );
}
if ( 'key-good' === $scenario ) {
	$_GET['aurora_preview'] = 'secretkey1234567';
}
if ( 'key-bad' === $scenario ) {
	$_GET['aurora_preview'] = 'wrong';
}
function is_user_logged_in() { return 'loggedin' === $GLOBALS['scenario']; }
$GLOBALS['scenario'] = $scenario;
function wp_unslash( $v ) { return $v; }
function wp_generate_password() { return 'generated'; }
function status_header( $c ) { echo "[status $c]"; }
function nocache_headers() {}
function is_ssl() { return true; }
function is_cart() { return false; }
function is_checkout() { return false; }
require dirname( __DIR__ ) . '/plugin/aurora-core/aurora-core.php';
ob_start();
@do_action( 'template_redirect' );
$out = ob_get_clean();
$robots = apply_filters( 'wp_robots', array() );
echo ( false !== strpos( $out, '即将上线' ) ? 'BLOCKED' : 'ALLOWED' ) . ' noindex=' . ( empty( $robots['noindex'] ) ? 'no' : 'yes' ) . "\n";
