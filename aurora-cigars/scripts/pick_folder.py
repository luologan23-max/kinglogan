"""把拖进终端窗口的内容整理成一个照片目录（run_photos.sh 用）。

拖进来的可能是一个文件夹、多个文件夹、一堆照片文件，或者同一个文件夹拖了两次；
路径里的空格前会带反斜杠。拖的是文件时取它所在的文件夹。
只有一个文件夹时直接用它；有多个时在 ~/aurora-照片汇总 里为每个文件夹建一个快捷方式（符号链接），
用这个汇总目录统一处理。原文件夹和照片都不动。找不到任何文件夹时退出码为 1。
"""
import os
import shlex
import sys


def main():
    text = sys.stdin.read().strip()
    try:
        parts = shlex.split(text)
    except ValueError:  # 引号没配对之类，退回按空格切
        parts = text.split()
    dirs = []
    for p in parts:
        p = os.path.abspath(os.path.expanduser(p))
        d = p if os.path.isdir(p) else os.path.dirname(p) if os.path.isfile(p) else None
        if d and d not in dirs:
            dirs.append(d)
    if not dirs:
        sys.exit(1)
    if len(dirs) == 1:
        print(dirs[0])
        return
    hub = os.path.expanduser("~/aurora-照片汇总")
    os.makedirs(hub, exist_ok=True)
    for name in os.listdir(hub):  # 只清掉上次留下的快捷方式
        if os.path.islink(os.path.join(hub, name)):
            os.unlink(os.path.join(hub, name))
    used = set()
    for d in dirs:
        name, n = os.path.basename(d) or "照片", 2
        while name in used:
            name, n = f"{os.path.basename(d)}-{n}", n + 1
        used.add(name)
        os.symlink(d, os.path.join(hub, name))
    print(hub)


if __name__ == "__main__":
    main()
