#!/usr/bin/env bash
# 实拍图上传（在你自己的 Mac 上运行）：按文件名把照片配到对应的产品
#   更新插件 → 下架重复型号 → 列出照片和产品的对照（桌面上同时生成对照表）→ 输入 y 确认后上传
# 用法：bash run_photos.sh [照片文件夹]   不写文件夹时，会提示把文件夹拖进终端窗口
set -euo pipefail
DIR="${1:-}"
[ -n "$DIR" ] && [ -d "$DIR" ] && DIR="$(cd "$DIR" && pwd)"
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

# 把文件夹拖进终端时，路径末尾会多一个空格，空格等字符前会加反斜杠
while [ -z "$DIR" ] || [ ! -d "$DIR" ]; do
	read -r -p "把放照片的文件夹拖进这个窗口，然后按回车：" DIR
	DIR="$(printf '%s' "$DIR" | sed -e 's/[[:space:]]*$//' -e "s/^'\(.*\)'$/\1/" -e 's/\\\(.\)/\1/g')"
	[ -d "$DIR" ] || echo "✗ 找不到这个文件夹：$DIR"
done

run() { echo; echo "━━ $1"; shift; python3 aurora_setup.py "$@"; }
run "1/4 检查连接"     check
run "2/4 更新插件"     install-plugin
run "3/4 下架重复型号" dedupe
run "4/4 照片对照"     images --photos "$DIR" --dry-run
echo
read -r -p "按上面的对照上传照片吗？确认请输入 y 然后按回车（其他键取消）：" OK
if [ "$OK" = "y" ] || [ "$OK" = "Y" ]; then
	python3 aurora_setup.py images --photos "$DIR"
	echo
	echo "✓ 完成。请把终端截图和桌面上的「aurora-实拍图对照表.csv」发给 Claude。"
else
	echo "已取消，没有上传任何照片。对照表在桌面「aurora-实拍图对照表.csv」，可以发给 Claude 看看哪些没对上。"
fi
