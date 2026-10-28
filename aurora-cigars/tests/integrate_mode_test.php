<?php
/** 整合模式测试：模拟站点已有 v6 店面片段（aur6_card_open）时插件的输出。php tests/integrate_mode_test.php */
require __DIR__ . '/wp_stubs.php';
function aur6_card_open() {} // 站点片段 14 定义的函数
function is_product() { return true; }
function home_url( $p = '/' ) { return 'https://example.com' . $p; }
function get_term( $id, $tax ) { return (object) array( 'term_id' => $id, 'slug' => 'limited-editions', 'count' => $GLOBALS['term_count'] ?? 0 ); }
function do_shortcode( $s ) { return $s; }
function shortcode_exists( $tag ) { return false; }
function get_page_by_path( $path ) { return 'my-request' === $path ? (object) array( 'ID' => 241 ) : null; }
function get_permalink( $p ) { return 'https://example.com/my-request/'; }
function get_transient( $k ) { return 'aurora_review_ids' === $k ? ( $GLOBALS['review_ids'] ?? array() ) : false; }
function set_transient( $k, $v, $t = 0 ) { return true; }
function delete_transient( $k ) { return true; }
function current_user_can( $cap ) { return ! empty( $GLOBALS['can_edit'] ); }
function get_post_meta( $id, $key = '', $single = false ) { return 'aurora_review' === $key ? ( $GLOBALS['meta'][ $id ] ?? '' ) : ''; }
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

// 页面里粘贴的 PHP 模板：没有产品时显示原来的空状态，有产品时改为 [products] 列表，其余 PHP 片段去掉
$php_page = "<div class=\"le-products\">\n<?php\n\$args = array(\n  'post_type' => 'product',\n  'tax_query' => array(array('taxonomy' => 'product_cat', 'field' => 'term_id', 'terms' => 48,)),\n);\n"
	. "\$q = new WP_Query(\$args);\nif (\$q->have_posts()): ?>\n<div class=\"grid\"><?php while(\$q->have_posts()): \$q->the_post(); ?><a href=\"<?php the_permalink(); ?>\">x</a><?php endwhile; ?></div>\n"
	. "<?php else: ?>\n<div class=\"le-empty\">Allocations Currently Closed</div>\n<?php endif; ?>\n</div><p><?php echo 1; ?>tail</p>";
$GLOBALS['term_count'] = 0;
$out = aurora_render_embedded_php( $php_page );
check( '粘贴的 PHP：分类没有产品时显示原来的空状态', false !== strpos( $out, 'le-empty' ) && false === strpos( $out, 'class="grid"' ) && false === strpos( $out, '<?php' ) && false !== strpos( $out, '<p>tail</p>' ) );
$GLOBALS['term_count'] = 3;
$out = aurora_render_embedded_php( $php_page );
check( '粘贴的 PHP：分类有产品时输出产品列表', false !== strpos( $out, '[products category="limited-editions" limit="12" columns="4"]' ) && false === strpos( $out, 'le-empty' ) );
check( '没有 PHP 的页面内容原样返回', $home === aurora_render_embedded_php( $home ) );

// 只剩 YITH 短代码的询价页转到需求单
$GLOBALS['is_page'] = true;
$GLOBALS['queried'] = (object) array( 'post_content' => '[yith_ywraq_request_quote]' );
check( 'YITH 询价页转到需求单页面', 'https://example.com/my-request/' === aurora_quote_redirect_target() );
$GLOBALS['queried'] = (object) array( 'post_content' => $home );
check( '其他页面不跳转', null === aurora_quote_redirect_target() );
$GLOBALS['is_page'] = false;

// 拿不准官方名称的产品：前台标红（只在预览模式或管理员登录时），后台列表标注
$GLOBALS['review_ids'] = array( 60, 137 );
$GLOBALS['options']['aurora_core'] = array( 'private_mode' => 1 );
$head = capture( 'wp_head' );
check( '预览模式下待核对产品名称标红', false !== strpos( $head, 'li.product.post-60 .aur-card-name' ) && false !== strpos( $head, 'body.postid-137 .aur-product-name-cn' ) && false !== strpos( $head, '名称待核对' ) );
$GLOBALS['options']['aurora_core'] = array( 'private_mode' => 0 );
$GLOBALS['can_edit'] = false;
check( '正式对外后访客看不到标红', false === strpos( capture( 'wp_head' ), 'aurora-review-css' ) );
$GLOBALS['can_edit'] = true;
check( '正式对外后管理员仍能看到标红', false !== strpos( capture( 'wp_head' ), 'aurora-review-css' ) );
$GLOBALS['options']['aurora_core'] = array( 'private_mode' => 1 );
$GLOBALS['meta'] = array( 60 => 'x' );
$states = apply_filters( 'display_post_states', array(), (object) array( 'ID' => 60, 'post_type' => 'product' ) );
check( '后台产品列表标注「名称待核对」', isset( $states['aurora_review'] ) && false !== strpos( $states['aurora_review'], '名称待核对' ) );
$states = apply_filters( 'display_post_states', array(), (object) array( 'ID' => 61, 'post_type' => 'product' ) );
check( '其他产品不标注', ! isset( $states['aurora_review'] ) );

exit( $fail ? 1 : 0 );
