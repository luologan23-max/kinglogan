#!/usr/bin/env bash
# Aurora 一键上线（在你自己的 Mac 上运行）：
#   安装插件 → WooCommerce 设置 → 停用多余插件 → 导入 80 款 → 配图 → 页面 → 导航 → 输出预览链接
# 用法：AURORA_APP_PASSWORD='xxxx xxxx …' bash run_all.sh
set -euo pipefail
cd "$(dirname "$0")"

if ! python3 -c 'print()' >/dev/null 2>&1; then
	echo "✗ 这台 Mac 还没有 python3。请在弹出的窗口里点「安装」命令行开发者工具，装完后重新运行同一条命令。"
	exit 1
fi
export AURORA_USER="${AURORA_USER:-luologan23@gmail.com}"
# 没收到密码（例如直接按了回车）就重新问，不往下跑
while [ -z "${AURORA_APP_PASSWORD:-}" ]; do
	read -r -s -p "请粘贴 Application Password（⌘V），然后按回车（输入时不显示）：" AURORA_APP_PASSWORD
	echo
	[ -z "$AURORA_APP_PASSWORD" ] && echo "✗ 没有收到密码，请重新粘贴后按回车。"
done
export AURORA_APP_PASSWORD

run() { echo; echo "━━ $1"; shift; python3 aurora_setup.py "$@"; }
run "1/8 检查连接"            check
run "2/8 安装并启用插件"      install-plugin
run "3/8 店铺设置"            configure
run "4/8 停用多余插件"        cleanup
run "5/8 导入 80 款标准型号"   import ../content/catalog.csv
run "6/8 配品牌图"            images
run "7/8 建页面"              pages
run "8/8 建导航"              menu
echo
python3 aurora_setup.py preview-link
echo
echo "✓ 全部完成。把这个窗口的内容截图发给 Claude 检查。"
