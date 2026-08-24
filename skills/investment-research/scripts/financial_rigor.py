#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""financial_rigor.py — 金融严谨性工具（纯 stdlib，精确 decimal）。

复刻自 ai-berkshire tools/financial_rigor.py 核心命令（MIT），去除第三方依赖。
禁止 LLM 心算：关键财务数据一律经本工具验算。

子命令：
  verify-market-cap  市值验算 = 股价 × 总股本
  verify-valuation   估值指标验算（PE/PB/FCF Yield/股息率）
  cross-validate     多源交叉验证
  calc               精确四则运算
  benford            Benford 定律首位数字检测
"""
import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

D = Decimal


def dec(x):
    return D(str(x)) if not isinstance(x, D) else x


def fmt(x):
    return format(x, ",.4f")


def cmd_market_cap(args):
    price, shares, reported = dec(args.price), dec(args.shares), dec(args.reported)
    calc = price * shares
    diff = (calc - reported).copy_abs()
    pct_diff = diff / reported * 100 if reported else D(0)
    ok = pct_diff <= dec(args.tolerance)
    print(f"市值验算: 股价 {fmt(price)} × 总股本 {fmt(shares)} = {fmt(calc)}")
    print(f"报告市值: {fmt(reported)} {args.currency}")
    print(f"偏差: {format(pct_diff, '.2f')}%   容差: {args.tolerance}%")
    print("✅ 通过" if ok else "❌ 偏差过大：排查币种/单位/口径（亿 vs 万、美元 vs 港元）")
    sys.exit(0 if ok else 1)


def cmd_valuation(args):
    price = dec(args.price)
    print(f"股价: {fmt(price)}  {args.currency}\n")
    if args.eps:
        pe = price / dec(args.eps)
        print(f"PE   = 价格/EPS = {fmt(price)}/{fmt(dec(args.eps))} = {format(pe, '.2f')}")
    if args.bvps:
        pb = price / dec(args.bvps)
        print(f"PB   = 价格/BVPS = {format(pb, '.2f')}")
    if args.fcf_per_share:
        fy = dec(args.fcf_per_share) / price
        print(f"FCF Yield = 每股FCF/价格 = {format(fy * 100, '.2f')}%")
    if args.dividend:
        dy = dec(args.dividend) / price
        print(f"股息率 = 每股股息/价格 = {format(dy * 100, '.2f')}%")
    if not (args.eps or args.bvps or args.fcf_per_share or args.dividend):
        print("(至少给一个指标: --eps/--bvps/--fcf-per-share/--dividend)")


def cmd_cross(args):
    values = json.loads(args.values)
    if not values or len(values) < 2:
        print("需要至少 2 个来源"); sys.exit(1)
    first_name, first_val = next(iter(values.items()))
    first = dec(first_val)
    print(f"多源交叉验证 [{args.field}]  单位: {args.unit or '-'}  容差: {args.tolerance}%\n")
    bad = False
    for name, v in values.items():
        d = dec(v)
        diff = (d - first).copy_abs() / first * 100 if first else D(0)
        ok = diff <= dec(args.tolerance)
        print(f"  {name}: {fmt(d)}  (vs {first_name} 偏差 {format(diff, '.2f')}%) {'✅' if ok else '❌'}")
        if not ok:
            bad = True
    print("\n✅ 各源一致" if not bad else "\n❌ 存在超差来源，优先采信年报/交易所，注明差异")
    sys.exit(1 if bad else 0)


def cmd_calc(args):
    a, b = dec(args.a), dec(args.b)
    ops = {"add": lambda: a + b, "sub": lambda: a - b,
           "mul": lambda: a * b, "div": lambda: a / b}
    r = ops[args.op]()
    print(f"{fmt(a)} {args.op} {fmt(b)} = {fmt(r)}")


def cmd_benford(args):
    vals = [dec(x) for x in json.loads(args.values)]
    if not vals:
        print("空列表"); return
    from collections import Counter
    cnt = Counter()
    for v in vals:
        s = format(v, "f").lstrip("-").lstrip("0").lstrip(".")
        if s and s[0].isdigit():
            cnt[int(s[0])] += 1
    n = sum(cnt.values())
    print(f"Benford 定律检测（{n} 个数值的首位数字分布）：")
    for d in range(1, 10):
        expected = 100 * (D(d + 1).ln() - D(d).ln()) / D(10).ln()
        actual = 100 * cnt.get(d, 0) / n if n else 0
        flag = "" if abs(actual - float(expected)) <= 5 else "  ⚠️"
        print(f"  首位 {d}: 实测 {actual:.1f}%  期望 {float(expected):.1f}%{flag}")


def main():
    ap = argparse.ArgumentParser(description="金融严谨性工具（精确 decimal，禁止心算）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mc = sub.add_parser("verify-market-cap", help="市值验算")
    mc.add_argument("--price", required=True); mc.add_argument("--shares", required=True)
    mc.add_argument("--reported", required=True); mc.add_argument("--currency", default="")
    mc.add_argument("--tolerance", default=2.0)
    va = sub.add_parser("verify-valuation", help="估值指标验算")
    va.add_argument("--price", required=True); va.add_argument("--eps")
    va.add_argument("--bvps"); va.add_argument("--fcf-per-share"); va.add_argument("--dividend")
    va.add_argument("--currency", default="")
    cv = sub.add_parser("cross-validate", help="多源交叉验证")
    cv.add_argument("--field", required=True); cv.add_argument("--values", required=True)
    cv.add_argument("--unit", default=""); cv.add_argument("--tolerance", default=2.0)
    ca = sub.add_parser("calc", help="精确四则运算")
    ca.add_argument("--a", required=True); ca.add_argument("--b", required=True)
    ca.add_argument("--op", choices=["add", "sub", "mul", "div"], default="mul")
    bf = sub.add_parser("benford", help="Benford 定律检测")
    bf.add_argument("--values", required=True)
    args = ap.parse_args()
    {"verify-market-cap": cmd_market_cap, "verify-valuation": cmd_valuation,
     "cross-validate": cmd_cross, "calc": cmd_calc, "benford": cmd_benford}[args.cmd](args)


if __name__ == "__main__":
    main()
