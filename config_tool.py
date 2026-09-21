# -*- coding: utf-8 -*-
"""PubMed AI 检索 · 配置设置程序：打印配置、交互修改、严格校验、安全写回"""

import sys
import config_common as cc

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def prompt(label, current, validator):
    while True:
        raw = input(f"    {label}（当前：{current or '(空)'}，回车保留）：").strip()
        if raw == "":
            return current
        err = validator(raw)
        if err:
            print(f"      [错误] {err}，请重新输入")
        else:
            return raw


def show(cfg):
    key = cfg["deepseek_api_key"]
    key_show = (key[:8] + "..." + key[-4:]) if key else "(未填)"
    print("=" * 50)
    print("   当前配置")
    print("=" * 50)
    print(f"  [1]  email              = {cfg['email'] or '(未填)'}")
    print(f"  [2]  deepseek_api_key   = {key_show}")
    print(f"  [3]  api_base           = {cfg['api_base']}")
    print(f"  [4]  model              = {cfg['model']}")
    print(f"  [5]  max_results        = {cfg['max_results']}")
    print(f"  [6]  summary_limit      = {cfg['summary_limit']}")
    print(f"  [7]  sort               = {cfg['sort']}")
    print(f"  [8]  download_fulltext  = {'true' if cfg['download_fulltext'] else 'false'}")
    print(f"  [9]  confirm_query      = {'true' if cfg['confirm_query'] else 'false'}")
    print(f"  [10] output_dir         = {cfg['output_dir'] or '(空=同文件夹)'}")
    print(f"  [11] ncbi_api_key       = {cfg['ncbi_api_key'] or '(空)'}")
    print("  [0]  保存并退出")
    print("-" * 50)


def main():
    cc.print_banner("PubMed AI 检索 · 配置设置")
    cfg = cc.load_config()
    if cfg is None:
        print("  检测到还没有有效配置，已按默认值初始化。")
        cfg = cc.default_config()

    while True:
        show(cfg)
        choice = input("  输入要修改的编号，或 0 保存退出：").strip()
        if choice == "0":
            break
        elif choice == "1":
            cfg["email"] = prompt("邮箱", cfg["email"], cc.validate_email)
        elif choice == "2":
            cfg["deepseek_api_key"] = prompt("DeepSeek Key", cfg["deepseek_api_key"], cc.validate_key)
        elif choice == "3":
            cfg["api_base"] = prompt("API 地址", cfg["api_base"], cc.validate_url)
        elif choice == "4":
            cfg["model"] = prompt("模型", cfg["model"], cc.validate_model)
        elif choice == "5":
            v = prompt("每次下载篇数", str(cfg["max_results"]), lambda x: cc.validate_int_range(x, 1, 1000))
            cfg["max_results"] = int(v)
        elif choice == "6":
            v = prompt("汇总篇数", str(cfg["summary_limit"]), lambda x: cc.validate_int_range(x, 1, 20000))
            cfg["summary_limit"] = int(v)
        elif choice == "7":
            v = prompt("排序(relevance/date)", cfg["sort"], cc.validate_sort)
            cfg["sort"] = v.strip().lower()
        elif choice == "8":
            v = prompt("下载全文(y/n)", "y" if cfg["download_fulltext"] else "n", cc.validate_bool)
            cfg["download_fulltext"] = v.strip().lower() in ("y", "true", "1", "yes")
        elif choice == "9":
            v = prompt("确认检索式(y/n)", "y" if cfg["confirm_query"] else "n", cc.validate_bool)
            cfg["confirm_query"] = v.strip().lower() in ("y", "true", "1", "yes")
        elif choice == "10":
            cfg["output_dir"] = prompt("输出目录", cfg["output_dir"], cc.validate_output_dir)
        elif choice == "11":
            cfg["ncbi_api_key"] = prompt("NCBI Key", cfg["ncbi_api_key"], cc.validate_ncbi_key)
        else:
            print("  输入无效，请输入 0~11 之间的编号。")

    path = cc.save_config(cfg)
    print(f"\n  配置已保存到 {path}")
    print("  若有旧配置，已自动备份为 config.ini.bak")
    input("\n  按回车键关闭...")


if __name__ == "__main__":
    main()
