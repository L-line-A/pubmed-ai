#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 PubMed AI 检索工具的所有使用痕迹"""

import os, sys, glob, shutil
import config_common as cc

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


TRACE_FILES = ["log.txt", "downloaded.txt", "待下载.txt"]
CONFIG_DISPLAY = "config.ini（配置，含你的 Key，位于用户目录）"
CONFIG_BAK_DISPLAY = "config.ini.bak（配置备份，位于用户目录）"
RESULT_PATTERN = "检索结果_*"


def scan():
    """扫描痕迹，返回 [(显示名, 路径, 是否文件夹), ...]"""
    items = []
    base = cc.base_dir()
    # 程序同目录的使用痕迹
    for name in TRACE_FILES:
        p = os.path.join(base, name)
        if os.path.exists(p):
            items.append((name, p, False))
    for d in glob.glob(os.path.join(base, RESULT_PATTERN)):
        items.append((os.path.basename(d) + "（结果文件夹）", d, True))
    # 用户目录下的配置
    cd = cc.config_dir()
    p = os.path.join(cd, "config.ini")
    if os.path.exists(p):
        items.append((CONFIG_DISPLAY, p, False))
    pb = os.path.join(cd, "config.ini.bak")
    if os.path.exists(pb):
        items.append((CONFIG_BAK_DISPLAY, pb, False))
    return items


def main():
    cc.print_banner("清理痕迹")
    items = scan()
    if not items:
        print("\n  没有发现任何痕迹，很干净。")
        input("\n  按回车键关闭...")
        return

    print(f"\n  发现 {len(items)} 项痕迹：")
    for i, (name, _, _) in enumerate(items):
        print(f"    [{i + 1}] {name}")

    print("\n  清理方式：")
    print("    [1] 全部清理（含配置，下次需重新填 Key）")
    print("    [2] 只清理使用痕迹（保留配置，下次免填 Key）")
    print("    [0] 退出，不清理")
    choice = input("\n  请输入 1 / 2 / 0：").strip()

    if choice == "0":
        print("  已取消，未做任何删除。")
        input("\n  按回车键关闭...")
        return
    if choice == "1":
        to_delete = items
    elif choice == "2":
        to_delete = [(n, p, d) for (n, p, d) in items if n != CONFIG_DISPLAY]
    else:
        print("  输入无效。")
        input("\n  按回车键关闭...")
        return

    print(f"\n  即将删除 {len(to_delete)} 项，此操作不可恢复。")
    confirm = input("  确认清理？(y/n)：").strip().lower()
    if confirm not in ("y", "yes", "1"):
        print("  已取消，未做任何删除。")
        input("\n  按回车键关闭...")
        return

    deleted = 0
    for name, p, is_dir in to_delete:
        try:
            if is_dir:
                shutil.rmtree(p)
            else:
                os.remove(p)
            print(f"    [已删除] {name}")
            deleted += 1
        except Exception as e:
            print(f"    [失败] {name}：{e}")

    print(f"\n  清理完成，共删除 {deleted} 项。")
    input("\n  按回车键关闭...")


if __name__ == "__main__":
    main()
