<?php
/** 整合模式测试：模拟站点已有 v6 店面片段（aur6_card_open）时插件的输出。php tests/integrate_mode_test.php */
require __DIR__ . '/wp_stubs.php';
function aur6_card_open() {} // 站点片段 14 定义的函数
function is_product() { return true; }
function home_url( $p = '/' ) { return 'https://example.com' . $p; }
// 模拟 Code Snippets 片段表：一条启用的站点 CSS、一条停用的
class Fake_WPDB {
	public $prefix = 'wp_';
	function prepare( $q, ...$a ) { return vsprintf( str_replace( '%s', "'%s'", $q ), $a ); }
	function get_var( $q ) { return 'wp_snippets'; }
	function get_col( $q ) { return false !== strpos( $q, "active = 1 AND scope = 'site-css'" ) ? array( ':root{--cream:#FAFAF8} .aur-card{border:1px solid red}</style><script>x</script>' ) : array(); }
}
$GLOBALS['wpdb'] = new Fake_WPDB();
$GLOBALS['product'] = new Fake_Product( false );
require dirname( __DIR__ ) . '/plugin/aurora-core/aurora-core.php';

$fail = 0;
function check( $name, $ok ) { global $fail; echo ( $ok ? 'PASS ' : 'FAIL ' ) . $name . "\n"; $fail += $ok ? 0 : 1; }
function capture( $hook ) { ob_start(); do_action( $hook ); return ob_get_clean(); }

check( '整合模式已开启', aurora_defer_ui() );
check( '产品页不再输出插件区块', '' === trim( capture( 'woocommerce_single_product_summary' ) ) );
check( '商品卡不再追加品牌/规格', '' === trim( capture( 'woocommerce_shop_loop_item_title' ) . capture( 'woocommerce_after_shop_loop_item_title' ) ) );
check( '不再输出品牌筛选条', '' === trim( capture( 'woocommerce_before_shop_loop' ) ) );
check( '不再输出插件页脚', '' === trim( capture( 'astra_footer_before' ) ) );
$footer = capture( 'wp_footer' );
check( '不再输出悬浮按钮/询价清单', false === strpos( $footer, 'aurora-wa-float' ) && false === strpos( $footer, 'aurora-drawer' ) );
check( '年龄验证仍然输出', false !== strpos( $footer, 'aurora-age' ) );
check( '列表按钮保持站点原样', '<a>原按钮</a>' === apply_filters( 'woocommerce_loop_add_to_cart_link', '<a>原按钮</a>', $GLOBALS['product'] ) );
check( '产品标签页保持原样', array( 'x' => 1 ) === apply_filters( 'woocommerce_product_tabs', array( 'x' => 1 ) ) );
$head = capture( 'wp_head' );
check( '输出启用的站点 CSS 片段', false !== strpos( $head, '<style id="aurora-site-css-1">' ) && false !== strpos( $head, '.aur-card{border:1px solid red}' ) );
check( '站点 CSS 中的 </style 被去除，无法跳出样式块', 1 === substr_count( $head, '</style' ) - 0 && false === strpos( $head, '</style><script>' ) );
check( '输出询价清单格式修复脚本', false !== strpos( $head, "aurora_request_list" ) );
$GLOBALS['enqueued'] = array();
do_action( 'wp_enqueue_scripts' );
$assets = implode( ' ', $GLOBALS['enqueued'] );
check( '加载 base + integrate，不加载 store 和重复字体', false !== strpos( $assets, 'aurora-base.css' ) && false !== strpos( $assets, 'aurora-integrate.css' ) && false !== strpos( $assets, 'aurora-integrate.js' ) && false === strpos( $assets, 'aurora-store.css' ) && false === strpos( $assets, 'fonts.googleapis' ) );

// 站点原有的手写页面：跳过自动分段和排版美化，并加载 aurora-pages.css
$home  = "<!-- HOMEPAGE v4 -->\n<!-- Trust Ticker -->\n<div class=\"aurora-ticker\">x</div>\n<div class=\"aurora-hero\">…</div>";
$about = "<style>\n.about-hero{display:grid}\n</style>\n\n<div class=\"about-hero\">…</div>";
check( '识别手写首页（开头是注释再接 div）', aurora_is_handbuilt( $home ) );
check( '识别自带 <style> 的手写页面', aurora_is_handbuilt( $about ) );
check( '区块编辑器内容不算', ! aurora_is_handbuilt( "<!-- wp:paragraph -->\n<p>Hi</p>\n<!-- /wp:paragraph -->" ) );
check( '本插件建的页面不算', ! aurora_is_handbuilt( "<!-- aurora:managed -->\n<div class=\"aurora-hero\">x</div>" ) );
check( '普通文字页面不算', ! aurora_is_handbuilt( "常见问题\n\n怎么下单？" ) );

$GLOBALS['is_page'] = true;
$GLOBALS['queried'] = (object) array( 'post_content' => $home );
$GLOBALS['removed'] = array();
do_action( 'wp' );
check( '手写页面跳过 wpautop 和 wptexturize', in_array( 'the_content:wpautop:10', $GLOBALS['removed'], true ) && in_array( 'the_content:wptexturize:10', $GLOBALS['removed'], true ) );
$GLOBALS['enqueued'] = array();
do_action( 'wp_enqueue_scripts' );
check( '手写页面加载 aurora-pages.css', false !== strpos( implode( ' ', $GLOBALS['enqueued'] ), 'aurora-pages.css' ) );

$GLOBALS['queried'] = (object) array( 'post_content' => "<!-- wp:paragraph -->\n<p>Hi</p>\n<!-- /wp:paragraph -->" );
$GLOBALS['removed'] = array();
do_action( 'wp' );
$GLOBALS['enqueued'] = array();
do_action( 'wp_enqueue_scripts' );
check( '其他页面照常分段、不加载 aurora-pages.css', array() === $GLOBALS['removed'] && false === strpos( implode( ' ', $GLOBALS['enqueued'] ), 'aurora-pages.css' ) );
$GLOBALS['is_page'] = false;
$GLOBALS['queried'] = (object) array( 'post_content' => $home );
check( '商品等非页面不受影响', ! aurora_handbuilt_page() );

exit( $fail ? 1 : 0 );
