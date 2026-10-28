<?php
/**
 * 一次性安装器（Code Snippets 片段模板）。
 * aurora_setup.py install-plugin 会把插件 zip 以 base64 填进下面 base64_decode() 的占位符，
 * 去掉第一行 <?php 后通过 Code Snippets 的 REST 接口创建并启用这个片段，
 * 调用一次 /aurora-install/v1/run 安装并启用 aurora-core，随后删除片段。
 * 路由只允许有安装、启用插件权限的管理员调用。
 */

add_action( 'rest_api_init', function () {
	register_rest_route( 'aurora-install/v1', '/run', array(
		'methods'             => 'POST',
		'permission_callback' => function () {
			return current_user_can( 'install_plugins' ) && current_user_can( 'activate_plugins' );
		},
		'callback'            => function () {
			require_once ABSPATH . 'wp-admin/includes/file.php';
			require_once ABSPATH . 'wp-admin/includes/misc.php';
			require_once ABSPATH . 'wp-admin/includes/plugin.php';
			require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';

			$tmp = wp_tempnam( 'aurora-core.zip' );
			file_put_contents( $tmp, base64_decode( '__AURORA_ZIP_BASE64__' ) );

			$skin     = new WP_Ajax_Upgrader_Skin();
			$upgrader = new Plugin_Upgrader( $skin );
			$result   = $upgrader->install( $tmp, array( 'overwrite_package' => true ) );
			if ( file_exists( $tmp ) ) {
				unlink( $tmp );
			}

			if ( is_wp_error( $result ) ) {
				return $result;
			}
			if ( ! $result ) {
				$errors = $skin->get_errors();
				$message = $errors->has_errors() ? $errors->get_error_message() : '插件安装失败（可能是文件系统没有写权限）';
				return new WP_Error( 'aurora_install_failed', $message, array( 'status' => 500 ) );
			}

			wp_clean_plugins_cache();
			$activated = activate_plugin( 'aurora-core/aurora-core.php' );
			if ( is_wp_error( $activated ) ) {
				return $activated;
			}
			return array(
				'installed' => true,
				'active'    => is_plugin_active( 'aurora-core/aurora-core.php' ),
			);
		},
	) );
} );
