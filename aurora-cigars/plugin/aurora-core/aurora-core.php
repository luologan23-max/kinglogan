<?php
/**
 * Plugin Name: Aurora Core
 * Description: Aurora Cigars 专用功能：目录模式（关闭购物车/结账）、WhatsApp 询价、多款询价清单、21 岁年龄验证、品牌设计样式与短代码。
 * Version: 1.2.3
 * Author: Aurora Global Tobacco Trading FZCO
 * Requires Plugins: woocommerce
 * Text Domain: aurora-core
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'AURORA_CORE_VERSION', '1.2.3' );
define( 'AURORA_CORE_URL', plugin_dir_url( __FILE__ ) );

/* -------------------------------------------------------------------------
 * 设置项
 * ---------------------------------------------------------------------- */

function aurora_defaults() {
	return array(
		'whatsapp'      => '971585598868',
		'email'         => 'luologan23@gmail.com',
		'min_age'       => 21,
		'age_days'      => 30,
		'no_ship'       => '美国、澳大利亚、新加坡、巴西、印度',
		'no_ship_en'    => 'USA, Australia, Singapore, Brazil, India',
		'shipping_note' => 'DHL Express 全球直发，15–20 个工作日送达，EXW 条款。货物发出后不接受退货。',
		'trust_line'    => '中东授权经销商直供 · 每盒可查防伪',
		'private_mode'  => 1,
		'integrate'     => 'auto',
	);
}

function aurora_opt( $key ) {
	$saved    = get_option( 'aurora_core', array() );
	$defaults = aurora_defaults();
	if ( isset( $saved[ $key ] ) && '' !== $saved[ $key ] ) {
		return $saved[ $key ];
	}
	return isset( $defaults[ $key ] ) ? $defaults[ $key ] : '';
}

add_action( 'admin_menu', function () {
	add_submenu_page( 'woocommerce', 'Aurora 设置', 'Aurora 设置', 'manage_woocommerce', 'aurora-core', 'aurora_settings_page' );
} );

add_action( 'admin_init', function () {
	register_setting( 'aurora_core', 'aurora_core', array(
		'type'              => 'array',
		'sanitize_callback' => function ( $input ) {
			$clean = array();
			foreach ( aurora_defaults() as $key => $default ) {
				$value         = isset( $input[ $key ] ) ? $input[ $key ] : '';
				$clean[ $key ] = is_int( $default ) ? absint( $value ) : sanitize_text_field( $value );
			}
			$clean['whatsapp'] = preg_replace( '/\D/', '', $clean['whatsapp'] );
			return $clean;
		},
	) );
} );

function aurora_settings_page() {
	$labels = array(
		'whatsapp'      => 'WhatsApp 号码（国家码+号码，不带 +）',
		'email'         => '联系邮箱',
		'min_age'       => '最低年龄',
		'age_days'      => '年龄确认记住天数',
		'no_ship'       => '不发货地区（中文）',
		'no_ship_en'    => '不发货地区（English）',
		'shipping_note' => '物流说明',
		'trust_line'    => '信任背书文案',
		'private_mode'  => '内部预览模式（1 = 开启，0 = 关闭，正式上线时改成 0）',
		'integrate'     => '整合模式（auto = 检测到站点自有店面代码时自动开启；on / off 强制开关）',
	);
	echo '<div class="wrap"><h1>Aurora 设置</h1><form method="post" action="options.php">';
	settings_fields( 'aurora_core' );
	echo '<table class="form-table">';
	foreach ( $labels as $key => $label ) {
		printf(
			'<tr><th><label for="aurora_%1$s">%2$s</label></th><td><input class="regular-text" id="aurora_%1$s" name="aurora_core[%1$s]" value="%3$s"></td></tr>',
			esc_attr( $key ),
			esc_html( $label ),
			esc_attr( aurora_opt( $key ) )
		);
	}
	echo '</table>';
	printf(
		'<p><strong>预览分享链接</strong>（内部预览模式下，没有后台账号的人用这个链接也能看网站）：<br><code>%s</code></p>',
		esc_html( add_query_arg( 'aurora_preview', aurora_preview_key(), home_url( '/' ) ) )
	);
	submit_button();
	echo '</form></div>';
}

/* -------------------------------------------------------------------------
 * 内部预览模式：未登录访客只看到「即将上线」，搜索引擎不收录
 * ---------------------------------------------------------------------- */

function aurora_preview_key() {
	$key = get_option( 'aurora_preview_key' );
	if ( ! $key ) {
		$key = wp_generate_password( 16, false );
		update_option( 'aurora_preview_key', $key, false );
	}
	return $key;
}

// 预览密钥对管理员开放到 REST（/wp/v2/settings），便于自动化截图
add_action( 'rest_api_init', function () {
	aurora_preview_key();
	register_setting( 'general', 'aurora_preview_key', array(
		'type'         => 'string',
		'show_in_rest' => true,
	) );
} );

function aurora_private_mode() {
	return 1 === absint( aurora_opt( 'private_mode' ) );
}

function aurora_can_preview() {
	if ( is_user_logged_in() ) {
		return true;
	}
	$key = aurora_preview_key();
	if ( isset( $_GET['aurora_preview'] ) && hash_equals( $key, (string) wp_unslash( $_GET['aurora_preview'] ) ) ) {
		setcookie( 'aurora_preview', $key, time() + 30 * DAY_IN_SECONDS, COOKIEPATH ?: '/', COOKIE_DOMAIN, is_ssl(), true );
		return true;
	}
	return isset( $_COOKIE['aurora_preview'] ) && hash_equals( $key, (string) wp_unslash( $_COOKIE['aurora_preview'] ) );
}

add_action( 'template_redirect', function () {
	if ( ! aurora_private_mode() || aurora_can_preview() ) {
		return;
	}
	status_header( 503 );
	header( 'Retry-After: 86400' );
	header( 'X-Robots-Tag: noindex, nofollow' );
	nocache_headers();
	?><!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Aurora Cigars</title>
	<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0e0d0b;color:#bfb6a6;font-family:Georgia,"Songti SC",serif;text-align:center;padding:16px;box-sizing:border-box}h1{margin:0 0 .6em;color:#b08d57;font-weight:400;letter-spacing:.4em;font-size:28px}p{margin:.3em 0}</style></head>
	<body><div><h1>AURORA</h1><p>网站即将上线</p><p style="font-style:italic">Coming soon</p></div></body></html><?php
	exit;
}, 0 );

// 预览模式下整站 noindex（包括已登录时看到的页面）
add_filter( 'wp_robots', function ( $robots ) {
	if ( aurora_private_mode() ) {
		$robots['noindex']  = true;
		$robots['nofollow'] = true;
	}
	return $robots;
} );

/* -------------------------------------------------------------------------
 * 整合模式：站点已有自己的店面代码片段（v6 商品卡、产品页 v4、全局导航页脚）时，
 * 本插件不再输出自己的商品卡、产品页区块、页脚、悬浮按钮和询价清单，
 * 只保留目录模式、内部预览、年龄验证，并修补站点设计的两处问题（见下）。
 * ---------------------------------------------------------------------- */

function aurora_defer_ui() {
	$mode = aurora_opt( 'integrate' );
	if ( 'on' === $mode || 'off' === $mode ) {
		return 'on' === $mode;
	}
	// 片段由 Code Snippets 在 plugins_loaded 时执行，这里的调用都发生在之后
	return function_exists( 'aur6_card_open' ) || function_exists( 'aurora_bom_footer' );
}

// Code Snippets 目前没有在前台输出「站点 CSS」类片段，站点设计系统（Design System v6 等）因此整份失效。
// 整合模式下由本插件直接从片段表读取已启用的站点 CSS 并输出；即使以后 Code Snippets 恢复输出，重复一份也不影响效果。
add_action( 'wp_head', function () {
	if ( ! aurora_defer_ui() ) {
		return;
	}
	global $wpdb;
	$table = $wpdb->prefix . 'snippets';
	if ( $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $table ) ) !== $table ) {
		return;
	}
	$styles = $wpdb->get_col( "SELECT code FROM {$table} WHERE active = 1 AND scope = 'site-css' ORDER BY priority, id" );
	foreach ( $styles as $i => $css ) {
		printf( "<style id=\"aurora-site-css-%d\">\n%s\n</style>\n", $i + 1, str_ireplace( '</style', '', $css ) ); // phpcs:ignore WordPress.Security.EscapeOutput
	}
}, 30 );

// 站点的商品卡/产品页按钮把询价清单存成数组，需求单页面却按 {items:[…]} 读取。
// 在任何站点脚本读取之前，把旧的数组格式转换过来（新的写入由 aurora-integrate.js 统一格式）。
add_action( 'wp_head', function () {
	if ( ! aurora_defer_ui() ) {
		return;
	}
	?>
	<script>try{var k='aurora_request_list',v=JSON.parse(localStorage.getItem(k)||'null');if(Array.isArray(v)){localStorage.setItem(k,JSON.stringify({items:v.map(function(i){return{sku:'P'+i.id,name:i.name,brand:i.brand||'',stockStatus:'in_stock',quantity:1};}),lastUpdated:null}));}}catch(e){}</script>
	<?php
}, 1 );

/* -------------------------------------------------------------------------
 * 站点原有的手写页面（首页「HOMEPAGE v4」、关于、腓尼基限量等）
 * 这类页面是整段手写 HTML（自带 <style> 或 div/section 区块），不是区块编辑器内容。
 * WordPress 显示时的自动分段会在里面插满 <p> 和 <br>，把卡片链接拆散、网格错位；
 * 排版美化（wptexturize）又把页内多语言脚本里的 && 改成 &#038;&#038;，脚本直接报错。
 * 首页和按钮（aurora-hero、aurora-btn-primary 等）的样式在站点里也已经丢失。
 * ---------------------------------------------------------------------- */

function aurora_is_handbuilt( $content ) {
	if ( false !== strpos( $content, '<!-- wp:' ) || false !== strpos( $content, '<!-- aurora:managed -->' ) ) {
		return false; // 区块编辑器内容、本插件建的页面照常处理
	}
	$start = ltrim( preg_replace( '/^(?:\s*<!--.*?-->)+/s', '', $content ) ); // 跳过开头的注释
	return 1 === preg_match( '/^<(?:style|div|section)\b/i', $start );
}

function aurora_handbuilt_page() {
	if ( is_admin() || ! is_page() ) {
		return false;
	}
	$post = get_queried_object();
	return isset( $post->post_content ) && aurora_is_handbuilt( $post->post_content );
}

// 只对当前这一页跳过自动分段和排版美化，其他页面照常
add_action( 'wp', function () {
	if ( aurora_handbuilt_page() ) {
		remove_filter( 'the_content', 'wpautop' );
		remove_filter( 'the_content', 'wptexturize' );
	}
} );

// 「年度限量」页里粘贴了一段 PHP 模板（查询限量分类下的产品）。页面内容里的 PHP 不会执行，
// 浏览器把它显示成乱码。这里照原意输出：分类下有产品时列出产品，没有时显示页面原来的「配额已关闭」提示。
function aurora_render_embedded_php( $content ) {
	if ( false === strpos( $content, '<?php' ) ) {
		return $content;
	}
	$content = preg_replace_callback(
		'/<\?php\s*\$args\s*=.*?[\'"]terms[\'"]\s*=>\s*(\d+).*?if\s*\(\s*\$q->have_posts\(\)\s*\)\s*:\s*\?>.*?<\?php\s*else\s*:\s*\?>(.*?)<\?php\s*endif;?\s*\?>/s',
		function ( $m ) {
			$term = get_term( (int) $m[1], 'product_cat' );
			if ( $term && ! is_wp_error( $term ) && $term->count > 0 ) {
				return do_shortcode( sprintf( '[products category="%s" limit="12" columns="4"]', esc_attr( $term->slug ) ) );
			}
			return $m[2];
		},
		$content
	);
	return preg_replace( '/<\?php.*?\?>/s', '', $content ); // 其余执行不了的 PHP 片段直接去掉
}

add_filter( 'the_content', function ( $content ) {
	return aurora_handbuilt_page() ? aurora_render_embedded_php( $content ) : $content;
}, 1 );

// 「Request a Quote」页只有一个 YITH 询价插件的短代码。该插件已停用（询价清单用站点自己的需求单页），
// 页面上只剩一行短代码文字，旧链接转到需求单页面。
function aurora_quote_redirect_target() {
	if ( ! is_page() || shortcode_exists( 'yith_ywraq_request_quote' ) ) {
		return null;
	}
	$post = get_queried_object();
	if ( ! isset( $post->post_content ) || false === strpos( $post->post_content, '[yith_ywraq_request_quote' ) ) {
		return null;
	}
	$list = get_page_by_path( 'my-request' );
	return $list ? get_permalink( $list ) : home_url( '/' );
}

add_action( 'template_redirect', function () {
	$target = aurora_quote_redirect_target();
	if ( $target ) {
		wp_safe_redirect( $target, 302 );
		exit;
	}
} );

// 拿不准官方名称的产品（meta aurora_review 有内容）：前台名称标红并注明「名称待核对」，后台产品列表也标出来。
// 只在内部预览模式下或管理员登录时显示，正式对外后访客看不到。核对完清空 aurora_review 即可。
function aurora_review_ids() {
	$ids = get_transient( 'aurora_review_ids' );
	if ( false === $ids ) {
		$ids = get_posts( array(
			'post_type'   => 'product',
			'post_status' => 'any',
			'fields'      => 'ids',
			'numberposts' => -1,
			'meta_query'  => array( array( 'key' => 'aurora_review', 'value' => '', 'compare' => '!=' ) ),
		) );
		set_transient( 'aurora_review_ids', $ids, HOUR_IN_SECONDS );
	}
	return array_map( 'intval', (array) $ids );
}

foreach ( array( 'added_post_meta', 'updated_post_meta', 'deleted_post_meta' ) as $aurora_hook ) {
	add_action( $aurora_hook, function ( $mid, $pid, $key ) {
		if ( 'aurora_review' === $key ) {
			delete_transient( 'aurora_review_ids' );
		}
	}, 10, 3 );
}

add_action( 'wp_head', function () {
	if ( ! aurora_private_mode() && ! current_user_can( 'edit_products' ) ) {
		return;
	}
	$names = $tags = array();
	foreach ( aurora_review_ids() as $id ) {
		// 商品卡（站点 v6 卡片 / Astra 默认标题）和产品页（站点产品页 v4 / WooCommerce 默认标题）
		$names[] = "li.product.post-$id .aur-card-name, li.product.post-$id .woocommerce-loop-product__title";
		$names[] = "body.postid-$id .aur-product-name-cn, body.postid-$id .aur-product-name-en, body.postid-$id .aur-mi-name-cn, body.postid-$id .product_title";
		$tags[]  = "li.product.post-$id .aur-card-name::after, body.postid-$id .aur-product-name-cn::after, body.postid-$id .product_title::after";
	}
	if ( ! $names ) {
		return;
	}
	printf(
		"<style id=\"aurora-review-css\">%s{color:#C62828!important}%s{content:\" · 名称待核对\";font:500 11px/1.4 var(--sans,sans-serif);letter-spacing:.06em;color:#C62828;vertical-align:middle}</style>\n",
		implode( ',', $names ),
		implode( ',', $tags )
	); // phpcs:ignore WordPress.Security.EscapeOutput
}, 40 );

add_filter( 'display_post_states', function ( $states, $post ) {
	if ( 'product' === $post->post_type && get_post_meta( $post->ID, 'aurora_review', true ) ) {
		$states['aurora_review'] = '<span style="color:#C62828">名称待核对</span>';
	}
	return $states;
}, 10, 2 );

// 站点片段把产品中文名存在 _name_cn 里，WooCommerce 接口默认不返回下划线开头的字段。
// 实拍图按中文文件名配图时需要它，这里只读地加到产品接口里。
add_action( 'rest_api_init', function () {
	register_rest_field( 'product', 'aurora_name_cn', array(
		'get_callback' => function ( $p ) {
			return (string) get_post_meta( $p['id'], '_name_cn', true );
		},
		'schema'       => array( 'type' => 'string', 'context' => array( 'view', 'edit' ), 'readonly' => true ),
	) );
} );

/* -------------------------------------------------------------------------
 * 目录模式：关闭购物车与结账
 * ---------------------------------------------------------------------- */

add_filter( 'woocommerce_is_purchasable', '__return_false' );
add_filter( 'woocommerce_add_to_cart_validation', '__return_false' );

// 购物车、结账、我的账户页面一律跳回商店
add_action( 'template_redirect', function () {
	if ( function_exists( 'is_cart' ) && ( is_cart() || is_checkout() ) ) {
		wp_safe_redirect( wc_get_page_permalink( 'shop' ) );
		exit;
	}
} );

// 商店列表页：把“加入购物车”换成“查看 / 询价”
add_filter( 'woocommerce_loop_add_to_cart_link', function ( $html, $product ) {
	if ( aurora_defer_ui() ) {
		return $html;
	}
	return sprintf(
		'<a class="aurora-btn aurora-btn--ghost" href="%s">查看详情 · 询价</a>',
		esc_url( $product->get_permalink() )
	);
}, 10, 2 );

// 没填价格的产品显示「价格请询价」
add_filter( 'woocommerce_empty_price_html', function () {
	return '<span class="aurora-por">价格请询价 · Price on request</span>';
} );

// 去掉 Astra/WooCommerce 头部的购物车图标与迷你购物车
add_filter( 'astra_header_cart_enabled', '__return_false' );
add_filter( 'woocommerce_widget_cart_is_hidden', '__return_true' );

/* -------------------------------------------------------------------------
 * 产品数据（导入脚本写入的 meta 字段）
 * ---------------------------------------------------------------------- */

function aurora_meta( $product, $key ) {
	return trim( (string) $product->get_meta( 'aurora_' . $key ) );
}

function aurora_is_yes( $value ) {
	return in_array( strtolower( trim( (string) $value ) ), array( '1', 'yes', 'y', 'true', '是', '限量' ), true );
}

function aurora_brand( $product ) {
	$brand = aurora_meta( $product, 'brand' );
	if ( '' !== $brand ) {
		return $brand;
	}
	$terms = get_the_terms( $product->get_id(), 'product_cat' );
	return ( $terms && ! is_wp_error( $terms ) ) ? $terms[0]->name : '';
}

// 规格串：「Robusto · 124mm × 50 · 25 支/盒」
function aurora_spec_line( $product ) {
	$parts  = array();
	$vitola = aurora_meta( $product, 'vitola' );
	$length = aurora_meta( $product, 'length' );
	$ring   = aurora_meta( $product, 'ring' );
	$count  = aurora_meta( $product, 'box_count' );
	if ( $vitola ) {
		$parts[] = $vitola;
	}
	if ( $length || $ring ) {
		$parts[] = trim( ( $length ? $length . 'mm' : '' ) . ( $length && $ring ? ' × ' : '' ) . ( $ring ? $ring : '' ) );
	}
	if ( $count ) {
		$parts[] = $count . ' 支/盒';
	}
	return implode( ' · ', $parts );
}

function aurora_inquiry_message( $product ) {
	$name = $product->get_name();
	if ( aurora_is_yes( aurora_meta( $product, 'limited' ) ) ) {
		return sprintf( '您好，我对 %s 感兴趣，请确认库存与价格。', $name );
	}
	$spec  = aurora_spec_line( $product );
	$price = $product->get_price();
	if ( '' === (string) $price ) {
		return trim( sprintf( '您好，我想询价：%s %s，请告知价格与库存。', $name, $spec ) );
	}
	return trim( sprintf(
		'您好，我想询价：%s %s，USD %s/盒，请确认库存。',
		$name,
		$spec,
		wc_format_localized_price( $price )
	) );
}

function aurora_wa_link( $text = '' ) {
	$url = 'https://wa.me/' . aurora_opt( 'whatsapp' );
	return $text ? $url . '?text=' . rawurlencode( $text ) : $url;
}

/* -------------------------------------------------------------------------
 * 产品详情页：手机首屏顺序 图片 → 品牌/名称 → 标签 → 价格 → 盒数 → WhatsApp
 * ---------------------------------------------------------------------- */

add_action( 'wp', function () {
	if ( aurora_defer_ui() || ! function_exists( 'is_product' ) || ! is_product() ) {
		return;
	}
	remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_rating', 10 );
	remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_excerpt', 20 );
	remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_add_to_cart', 30 );
	remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_meta', 40 );
	remove_action( 'woocommerce_single_product_summary', 'woocommerce_template_single_sharing', 50 );
} );

add_action( 'woocommerce_single_product_summary', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	global $product;
	$brand = aurora_brand( $product );
	if ( $brand ) {
		printf( '<p class="aurora-brand">%s</p>', esc_html( $brand ) );
	}
}, 4 );

add_action( 'woocommerce_single_product_summary', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	global $product;
	$en = aurora_meta( $product, 'name_en' );
	if ( $en && $en !== $product->get_name() ) {
		printf( '<p class="aurora-name-en">%s</p>', esc_html( $en ) );
	}
	echo '<div class="aurora-tags">';
	if ( $product->is_in_stock() ) {
		echo '<span class="aurora-tag aurora-tag--stock">现货 In Stock</span>';
	} else {
		echo '<span class="aurora-tag aurora-tag--out">需确认库存</span>';
	}
	if ( aurora_is_yes( aurora_meta( $product, 'limited' ) ) ) {
		echo '<span class="aurora-tag aurora-tag--limited">限量版 Limited</span>';
	}
	if ( '' === aurora_meta( $product, 'verify' ) || aurora_is_yes( aurora_meta( $product, 'verify' ) ) ) {
		echo '<span class="aurora-tag">防伪可查 Verified</span>';
	}
	echo '</div>';
}, 7 );

add_action( 'woocommerce_single_product_summary', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	global $product;
	$spec = aurora_spec_line( $product );
	?>
	<div class="aurora-inquiry"
		data-id="<?php echo esc_attr( $product->get_id() ); ?>"
		data-name="<?php echo esc_attr( $product->get_name() ); ?>"
		data-spec="<?php echo esc_attr( $spec ); ?>"
		data-price="<?php echo esc_attr( $product->get_price() ); ?>"
		data-url="<?php echo esc_url( $product->get_permalink() ); ?>"
		data-limited="<?php echo aurora_is_yes( aurora_meta( $product, 'limited' ) ) ? '1' : '0'; ?>"
		data-message="<?php echo esc_attr( aurora_inquiry_message( $product ) ); ?>">
		<?php if ( $spec ) : ?>
			<p class="aurora-spec-line"><?php echo esc_html( $spec ); ?></p>
		<?php endif; ?>
		<div class="aurora-qty" role="group" aria-label="选择盒数">
			<span class="aurora-qty__label">盒数 Boxes</span>
			<button type="button" class="aurora-qty__btn" data-step="-1" aria-label="减少">−</button>
			<input type="number" class="aurora-qty__input" value="1" min="1" max="99" inputmode="numeric" aria-label="盒数">
			<button type="button" class="aurora-qty__btn" data-step="1" aria-label="增加">+</button>
		</div>
		<a class="aurora-btn aurora-btn--wa aurora-wa-single" href="<?php echo esc_url( aurora_wa_link( aurora_inquiry_message( $product ) ) ); ?>" target="_blank" rel="noopener">
			<?php echo aurora_wa_icon(); // phpcs:ignore WordPress.Security.EscapeOutput ?>
			<span>WhatsApp 一键询价</span>
		</a>
		<button type="button" class="aurora-btn aurora-btn--ghost aurora-add-list">＋ 加入询价清单</button>
		<p class="aurora-trust"><?php echo esc_html( aurora_opt( 'trust_line' ) ); ?></p>
	</div>
	<?php
}, 30 );

// 长篇规格、品鉴与物流后移到详情区
add_filter( 'woocommerce_product_tabs', function ( $tabs ) {
	if ( aurora_defer_ui() ) {
		return $tabs;
	}
	unset( $tabs['reviews'], $tabs['additional_information'] );
	$tabs['aurora_spec'] = array(
		'title'    => '规格参数 Specs',
		'priority' => 5,
		'callback' => 'aurora_spec_table',
	);
	$tabs['aurora_shipping'] = array(
		'title'    => '配送与说明 Shipping',
		'priority' => 40,
		'callback' => function () {
			printf(
				'<p>%s</p><p>以下地区暂不发货：%s<br><small>We do not ship to: %s</small></p><p>仅向年满 %d 岁的成年人销售。</p>',
				esc_html( aurora_opt( 'shipping_note' ) ),
				esc_html( aurora_opt( 'no_ship' ) ),
				esc_html( aurora_opt( 'no_ship_en' ) ),
				absint( aurora_opt( 'min_age' ) )
			);
		},
	);
	if ( isset( $tabs['description'] ) ) {
		$tabs['description']['title'] = '品鉴描述 Tasting';
	}
	return $tabs;
} );

function aurora_spec_table() {
	global $product;
	$rows = array(
		'brand'     => '品牌 Brand',
		'name_en'   => '英文名 Name',
		'vitola'    => '型号 Vitola',
		'length'    => '长度 Length (mm)',
		'ring'      => '环径 Ring Gauge',
		'box_count' => '每盒支数 Per Box',
		'strength'  => '浓度 Strength',
		'wrapper'   => '茄衣 Wrapper',
		'origin'    => '产地 Origin',
	);
	echo '<table class="aurora-spec-table"><tbody>';
	foreach ( $rows as $key => $label ) {
		$value = 'brand' === $key ? aurora_brand( $product ) : aurora_meta( $product, $key );
		if ( '' === $value ) {
			continue;
		}
		printf( '<tr><th>%s</th><td>%s</td></tr>', esc_html( $label ), esc_html( $value ) );
	}
	if ( $product->get_sku() ) {
		printf( '<tr><th>编号 SKU</th><td>%s</td></tr>', esc_html( $product->get_sku() ) );
	}
	echo '</tbody></table>';
}

/* -------------------------------------------------------------------------
 * 前端资源、悬浮按钮、询价清单、年龄验证
 * ---------------------------------------------------------------------- */

function aurora_wa_icon() {
	return '<svg class="aurora-wa-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21c5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2Zm5.8 14.13c-.24.68-1.42 1.3-1.95 1.35-.5.05-.97.23-3.28-.68-2.78-1.1-4.54-3.95-4.68-4.13-.14-.18-1.12-1.49-1.12-2.84s.71-2.02.96-2.29c.25-.27.55-.34.73-.34l.52.01c.17 0 .39-.06.61.47.24.56.79 1.92.86 2.06.07.14.11.3.02.48-.09.18-.14.3-.27.46-.14.16-.29.36-.41.48-.14.14-.28.29-.12.56.16.27.71 1.17 1.52 1.9 1.05.93 1.93 1.22 2.2 1.36.27.14.43.11.59-.07.16-.18.68-.79.86-1.06.18-.27.36-.23.61-.14.25.09 1.59.75 1.86.89.27.14.45.2.52.32.07.11.07.66-.17 1.34Z"/></svg>';
}

add_action( 'wp_enqueue_scripts', function () {
	$defer = aurora_defer_ui();
	if ( ! $defer ) { // 整合模式下站点的全局片段已加载同一组字体
		wp_enqueue_style(
			'aurora-fonts',
			'https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,400..700&family=EB+Garamond:ital,wght@0,400..600;1,400&family=Jost:wght@300..600&display=swap',
			array(),
			null
		);
	}
	wp_enqueue_style( 'aurora-base', AURORA_CORE_URL . 'assets/aurora-base.css', array(), AURORA_CORE_VERSION );
	if ( $defer ) {
		wp_enqueue_style( 'aurora-integrate', AURORA_CORE_URL . 'assets/aurora-integrate.css', array( 'aurora-base' ), AURORA_CORE_VERSION );
		wp_enqueue_script( 'aurora-integrate', AURORA_CORE_URL . 'assets/aurora-integrate.js', array(), AURORA_CORE_VERSION, true );
	} else {
		wp_enqueue_style( 'aurora-store', AURORA_CORE_URL . 'assets/aurora-store.css', array( 'aurora-base' ), AURORA_CORE_VERSION );
	}
	if ( aurora_handbuilt_page() ) {
		wp_enqueue_style( 'aurora-pages', AURORA_CORE_URL . 'assets/aurora-pages.css', array( 'aurora-base' ), AURORA_CORE_VERSION );
	}
	wp_enqueue_script( 'aurora-core', AURORA_CORE_URL . 'assets/aurora.js', array(), AURORA_CORE_VERSION, true );
	wp_localize_script( 'aurora-core', 'AURORA', array(
		'wa'      => aurora_opt( 'whatsapp' ),
		'minAge'  => absint( aurora_opt( 'min_age' ) ),
		'ageDays' => absint( aurora_opt( 'age_days' ) ),
	) );
}, 20 );

add_action( 'wp_footer', function () {
	if ( is_admin() || aurora_defer_ui() ) {
		return;
	}
	?>
	<a class="aurora-wa-float" href="<?php echo esc_url( aurora_wa_link( '您好，我想咨询雪茄。' ) ); ?>" target="_blank" rel="noopener" aria-label="WhatsApp 咨询">
		<?php echo aurora_wa_icon(); // phpcs:ignore WordPress.Security.EscapeOutput ?>
	</a>
	<button type="button" class="aurora-list-float" hidden aria-label="打开询价清单">
		询价清单 <span class="aurora-list-count">0</span>
	</button>
	<div class="aurora-drawer" hidden role="dialog" aria-modal="true" aria-labelledby="aurora-drawer-title">
		<div class="aurora-drawer__panel">
			<header class="aurora-drawer__head">
				<h2 id="aurora-drawer-title">询价清单 Inquiry List</h2>
				<button type="button" class="aurora-drawer__close" aria-label="关闭">×</button>
			</header>
			<ul class="aurora-drawer__items"></ul>
			<p class="aurora-drawer__empty">清单还是空的，去挑选几款吧。</p>
			<footer class="aurora-drawer__foot">
				<button type="button" class="aurora-btn aurora-btn--wa aurora-send-list">
					<?php echo aurora_wa_icon(); // phpcs:ignore WordPress.Security.EscapeOutput ?>
					<span>整单发送到 WhatsApp</span>
				</button>
				<button type="button" class="aurora-link aurora-clear-list">清空清单</button>
			</footer>
		</div>
	</div>
	<?php
} );

// 年龄验证在两种模式下都输出
add_action( 'wp_footer', function () {
	if ( is_admin() ) {
		return;
	}
	?>
	<?php if ( empty( $_COOKIE['aurora_age_ok'] ) ) : ?>
	<div class="aurora-age" role="dialog" aria-modal="true" aria-labelledby="aurora-age-title">
		<div class="aurora-age__box">
			<p class="aurora-age__mark">AURORA</p>
			<h2 id="aurora-age-title">您是否已年满 <?php echo absint( aurora_opt( 'min_age' ) ); ?> 岁？</h2>
			<p class="aurora-age__en">Are you <?php echo absint( aurora_opt( 'min_age' ) ); ?> years of age or older?</p>
			<div class="aurora-age__actions">
				<button type="button" class="aurora-btn aurora-btn--gold aurora-age-yes">是，进入网站 · Enter</button>
				<a class="aurora-btn aurora-btn--ghost" href="https://www.google.com" rel="nofollow">否 · Leave</a>
			</div>
			<p class="aurora-age__note">本网站仅面向法定吸烟年龄的成年人。以下地区暂不发货：<?php echo esc_html( aurora_opt( 'no_ship' ) ); ?>。</p>
		</div>
	</div>
	<?php endif; ?>
	<?php
} );

/* -------------------------------------------------------------------------
 * 商店列表：卡片显示品牌与规格；顶部品牌导航；无图时用品牌占位图
 * ---------------------------------------------------------------------- */

add_action( 'woocommerce_shop_loop_item_title', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	global $product;
	$brand = aurora_brand( $product );
	if ( $brand ) {
		printf( '<p class="aurora-brand aurora-brand--loop">%s</p>', esc_html( $brand ) );
	}
}, 5 );

add_action( 'woocommerce_after_shop_loop_item_title', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	global $product;
	$spec = aurora_spec_line( $product );
	if ( $spec ) {
		printf( '<p class="aurora-spec-line aurora-spec-line--loop">%s</p>', esc_html( $spec ) );
	}
}, 5 );

add_action( 'woocommerce_before_shop_loop', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	echo do_shortcode( '[aurora_brand_nav]' );
}, 5 );

add_filter( 'woocommerce_placeholder_img_src', function () {
	return AURORA_CORE_URL . 'assets/placeholder.jpg';
} );

/* -------------------------------------------------------------------------
 * 页脚：公司信息、联系方式、年龄与发货限制（Astra 页脚之前输出）
 * ---------------------------------------------------------------------- */

function aurora_footer_html() {
	$wa = aurora_opt( 'whatsapp' );
	return sprintf(
		'<footer class="aurora-footer"><div class="aurora-footer__inner">
			<div><p class="aurora-footer__mark">AURORA</p><p>Aurora Global Tobacco Trading FZCO<br>Jebel Ali Free Zone (JAFZA), Dubai, UAE</p></div>
			<div><p class="aurora-footer__head">联系 Contact</p><p><a href="%1$s" target="_blank" rel="noopener">WhatsApp +%2$s</a><br><a href="mailto:%3$s">%3$s</a></p></div>
			<div><p class="aurora-footer__head">服务 Service</p><p><a href="/verify/">防伪查验</a> · <a href="/faq/">常见问题</a><br><a href="/shipping/">配送与条款</a> · <a href="/wholesale/">批发合作</a></p></div>
		</div>
		<p class="aurora-footer__legal">仅向年满 %4$d 岁的成年人销售 · Sold only to adults aged %4$d+ · 暂不发货：%5$s<br>© %6$s Aurora Global Tobacco Trading FZCO</p></footer>',
		esc_url( aurora_wa_link() ),
		esc_html( $wa ),
		esc_html( aurora_opt( 'email' ) ),
		absint( aurora_opt( 'min_age' ) ),
		esc_html( aurora_opt( 'no_ship' ) ),
		esc_html( gmdate( 'Y' ) )
	);
}

add_action( 'astra_footer_before', function () {
	if ( aurora_defer_ui() ) {
		return;
	}
	echo aurora_footer_html(); // phpcs:ignore WordPress.Security.EscapeOutput
} );

/* -------------------------------------------------------------------------
 * 短代码：首页与 Elementor 中使用
 * ---------------------------------------------------------------------- */

// [aurora_footer] 不用 Astra 时可手动放置页脚
add_shortcode( 'aurora_footer', 'aurora_footer_html' );

// [aurora_brand_nav] 商店顶部品牌筛选条
add_shortcode( 'aurora_brand_nav', function () {
	$terms = get_terms( array(
		'taxonomy'   => 'product_cat',
		'parent'     => 0,
		'hide_empty' => true,
		'orderby'    => 'menu_order',
		'exclude'    => array( (int) get_option( 'default_product_cat' ) ),
	) );
	if ( empty( $terms ) || is_wp_error( $terms ) ) {
		return '';
	}
	$current = function_exists( 'is_product_category' ) && is_product_category() ? get_queried_object_id() : 0;
	$out     = sprintf(
		'<nav class="aurora-brand-nav" aria-label="品牌"><a href="%s"%s>全部 All</a>',
		esc_url( wc_get_page_permalink( 'shop' ) ),
		$current ? '' : ' aria-current="page"'
	);
	foreach ( $terms as $term ) {
		$out .= sprintf(
			'<a href="%s"%s>%s</a>',
			esc_url( get_term_link( $term ) ),
			$current === $term->term_id ? ' aria-current="page"' : '',
			esc_html( $term->name )
		);
	}
	return $out . '</nav>';
} );

// [aurora_products limit="8" brand="cohiba"] 精选产品（brand 为分类别名）
add_shortcode( 'aurora_products', function ( $atts ) {
	$atts = shortcode_atts( array( 'limit' => 8, 'brand' => '' ), $atts );
	$sc   = sprintf( '[products limit="%d" columns="4" orderby="menu_order"', absint( $atts['limit'] ) );
	if ( $atts['brand'] ) {
		$sc .= sprintf( ' category="%s"', esc_attr( $atts['brand'] ) );
	}
	return do_shortcode( $sc . ']' );
} );

// [aurora_brands limit="6"] 品牌宫格：取顶级产品分类，按 menu_order 排
add_shortcode( 'aurora_brands', function ( $atts ) {
	$atts  = shortcode_atts( array( 'limit' => 6 ), $atts );
	$terms = get_terms( array(
		'taxonomy'   => 'product_cat',
		'parent'     => 0,
		'hide_empty' => true,
		'number'     => absint( $atts['limit'] ),
		'orderby'    => 'menu_order',
		'exclude'    => array( (int) get_option( 'default_product_cat' ) ),
	) );
	if ( empty( $terms ) || is_wp_error( $terms ) ) {
		return '';
	}
	$out = '<div class="aurora-brands">';
	foreach ( $terms as $term ) {
		$thumb = get_term_meta( $term->term_id, 'thumbnail_id', true );
		$img   = $thumb ? wp_get_attachment_image( $thumb, 'medium_large', false, array( 'class' => 'aurora-brands__img' ) ) : '';
		$out  .= sprintf(
			'<a class="aurora-brands__item" href="%s">%s<span class="aurora-brands__name">%s</span><span class="aurora-brands__count">%d 款</span></a>',
			esc_url( get_term_link( $term ) ),
			$img,
			esc_html( $term->name ),
			absint( $term->count )
		);
	}
	return $out . '</div>';
} );

// [aurora_whatsapp text="WhatsApp 咨询" message="您好"]
add_shortcode( 'aurora_whatsapp', function ( $atts ) {
	$atts = shortcode_atts( array(
		'text'    => 'WhatsApp 咨询',
		'message' => '您好，我想咨询雪茄。',
	), $atts );
	return sprintf(
		'<a class="aurora-btn aurora-btn--wa" href="%s" target="_blank" rel="noopener">%s<span>%s</span></a>',
		esc_url( aurora_wa_link( $atts['message'] ) ),
		aurora_wa_icon(),
		esc_html( $atts['text'] )
	);
} );

// [aurora_shipping] 配送与限制说明
add_shortcode( 'aurora_shipping', function () {
	return sprintf(
		'<div class="aurora-shipping"><p>%s</p><p>暂不发货地区：%s<br><small>We do not ship to: %s</small></p></div>',
		esc_html( aurora_opt( 'shipping_note' ) ),
		esc_html( aurora_opt( 'no_ship' ) ),
		esc_html( aurora_opt( 'no_ship_en' ) )
	);
} );
