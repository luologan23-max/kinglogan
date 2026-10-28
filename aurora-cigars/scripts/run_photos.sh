#!/usr/bin/env bash
# 产品实拍图（在你自己的 Mac 上运行），分两步，第一步不改任何东西：
#   bash run_photos.sh                 第 1 步：清点照片（只读）→ 桌面生成「aurora-图片清单.zip」发给 Claude 核对
#   bash run_photos.sh apply           第 2 步：按 Claude 整理、你确认过的对照表（content/photo-mapping.csv）上传
#   bash run_photos.sh auto            一次做完：清点备份 → 修正写错的名称 → 合并同名重复 → 重复型号改草稿 → 拿不准的名称标红 → 按文件名自动配图上传（不确定的不传）
#   bash run_photos.sh restore 备份.json  撤销：把产品图片和上架状态恢复成备份时的样子
set -euo pipefail
MODE="${1:-inventory}"
ARG="${2:-}"
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

ask_folder() {
	DIR=""
	# 把文件夹拖进终端时，路径末尾会多一个空格，空格等字符前会加反斜杠
	while [ -z "$DIR" ] || [ ! -d "$DIR" ]; do
		read -r -p "把放照片的文件夹拖进这个窗口，然后按回车：" DIR
		DIR="$(printf '%s' "$DIR" | sed -e 's/[[:space:]]*$//' -e "s/^'\(.*\)'$/\1/" -e 's/\\\(.\)/\1/g')"
		[ -d "$DIR" ] || echo "✗ 找不到这个文件夹：$DIR"
	done
}

run() { echo; echo "━━ $1"; shift; python3 aurora_setup.py "$@"; }

case "$MODE" in
inventory)
	ask_folder
	run "1/2 检查连接" check
	run "2/2 清点照片（只读，不改网站，不改原图）" photo-inventory --photos "$DIR"
	echo
	echo "✓ 完成。请把桌面上的「aurora-图片清单.zip」发给 Claude。"
	;;
apply)
	MAP="../content/photo-mapping.csv"
	[ -f "$MAP" ] || { echo "✗ 还没有核对好的对照表（content/photo-mapping.csv），请先完成第 1 步并等 Claude 整理。"; exit 1; }
	ask_folder
	run "1/4 检查连接" check
	run "2/4 上传计划（只显示，不上传）" photo-apply --photos "$DIR" --mapping "$MAP" --dry-run
	echo
	read -r -p "按上面的计划上传吗？确认请输入 y 然后按回车（其他键取消）：" OK
	if [ "$OK" != "y" ] && [ "$OK" != "Y" ]; then
		echo "已取消，网站没有任何改动。"
		exit 0
	fi
	run "3/4 上传并关联图片" photo-apply --photos "$DIR" --mapping "$MAP"
	run "4/4 导出诊断包" audit --out ~/Desktop/aurora-audit-配图后.zip
	echo
	echo "✓ 完成。请把终端截图和桌面上的「aurora-audit-配图后.zip」发给 Claude 检查。"
	;;
auto)
	# 一次做完：清点备份 → 更新插件 → 修正名称 → 合并同名重复 → 重复型号改草稿 → 名称标红 → 自动配图上传（不确定的不传）→ 诊断包
	ask_folder
	run "1/9 检查连接" check
	run "2/9 清点照片并备份（只读）" photo-inventory --photos "$DIR"
	run "3/9 更新插件" install-plugin
	run "4/9 修正写错的产品名称" rename
	run "5/9 合并同名重复的产品" merge
	run "6/9 标准目录里的重复型号改为草稿" dedupe
	run "7/9 拿不准的官方名称标红" mark-review
	run "8/9 按文件名配图并上传" photo-auto --photos "$DIR"
	run "9/9 导出诊断包" audit --out ~/Desktop/aurora-audit-配图后.zip
	echo
	echo "✓ 完成。请把桌面上的「aurora-图片清单.zip」「aurora-audit-配图后.zip」和终端截图发给 Claude。"
	;;
restore)
	[ -f "$ARG" ] || { echo "✗ 用法：bash run_photos.sh restore 桌面上的备份文件.json"; exit 1; }
	run "恢复产品图片" photo-restore --backup "$ARG"
	;;
*)
	echo "用法：bash run_photos.sh [apply | auto | restore 备份.json]"
	exit 1
	;;
esac
