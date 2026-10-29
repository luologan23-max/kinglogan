#!/usr/bin/env bash
# 网站设计相关的两个常用操作（在你自己的 Mac 上运行）：
#   bash run_site.sh audit     只读：导出诊断包（页面 HTML、样式、产品和图片检查）→ 桌面「aurora-audit.zip」发给 Claude
#   bash run_site.sh update    更新 aurora-core 插件到最新版，然后导出诊断包 →「aurora-audit-更新后.zip」
set -euo pipefail
MODE="${1:-audit}"
cd "$(dirname "$0")"

if ! python3 -c 'print()' >/dev/null 2>&1; then
	echo "✗ 这台 Mac 还没有 python3。请在弹出的窗口里点「安装」命令行开发者工具，装完后重新运行同一条命令。"
	exit 1
fi
export AURORA_USER="${AURORA_USER:-luologan23@gmail.com}"
while [ -z "${AURORA_APP_PASSWORD:-}" ]; do
	read -r -s -p "请粘贴 Application Password（⌘V），然后按回车（输入时不显示）：" AURORA_APP_PASSWORD
	echo
	[ -z "$AURORA_APP_PASSWORD" ] && echo "✗ 没有收到密码，请重新粘贴后按回车。"
done
export AURORA_APP_PASSWORD

run() { echo; echo "━━ $1"; shift; python3 aurora_setup.py "$@"; }

case "$MODE" in
audit)
	run "1/2 检查连接" check
	run "2/2 导出诊断包（只读，不改网站）" audit --out ~/Desktop/aurora-audit.zip
	echo
	echo "✓ 完成。请把桌面上的「aurora-audit.zip」发给 Claude。"
	;;
update)
	run "1/3 检查连接" check
	run "2/3 更新插件" install-plugin
	run "3/3 导出诊断包" audit --out ~/Desktop/aurora-audit-更新后.zip
	echo
	echo "✓ 完成。请把桌面上的「aurora-audit-更新后.zip」和终端截图发给 Claude。"
	;;
*)
	echo "用法：bash run_site.sh [audit | update]"
	exit 1
	;;
esac
