#!/usr/bin/env bash
# Aurora 设计修复（在你自己的 Mac 上运行）：
#   插件更新到整合版 → 删除遗留安装片段 → 恢复站点原有页面 → 重复型号改草稿 → 导出诊断包
# 用法：AURORA_APP_PASSWORD='xxxx xxxx …' bash run_fix.sh
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
run "1/6 检查连接"                 check
run "2/6 更新插件"                 install-plugin
run "3/6 清理遗留安装片段和多余插件" cleanup
run "4/6 恢复原有页面"             restore-pages
run "5/6 重复型号改为草稿"          dedupe
run "6/6 导出诊断包"               audit --out ~/Desktop/aurora-audit-修复后.zip
echo
echo "✓ 完成。请把桌面上的 aurora-audit-修复后.zip 发给 Claude 检查效果。"
