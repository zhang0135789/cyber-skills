#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""terminal_value.py — 十年折现估值纪律工具（纯 stdlib，精确 decimal）。

复刻自 ai-berkshire tools/terminal_value.py 核心（MIT）。
三输入纪律：r（资本成本）、ROIC（稳态增量回报）、g（终值年之后永续增速）。
终值 PE 唯一合法来源：永续增长模型 PE = (1 - g/ROIC) / (r - g)，禁止同业类比。

子命令：
  audit  三条硬约束检查（C1 同币种 / C2 分母≥5pct / C3 离散风险不塞 r）
  pe     计算终值 PE（展开算式）
  irr    从终值利润/市值/退出PE 算十年 IRR
"""
import argparse
import sys
from decimal import Decimal

D = Decimal

R_CN = (Decimal("0.06"), Decimal("0.09"))      # 人民币口径 r
R_USD = (Decimal("0.09"), Decimal("0.115"))    # 美元/港元口径 r
G_CN_MAX = Decimal("0.02")                     # 人民币 g 上限
G_USD_MAX = Decimal("0.04")                    # 美元 g 上限


def dec(x):
    return D(str(x))


def cmd_audit(args):
    r, roic = dec(args.r), dec(args.roic)
    gs = [dec(x) for x in args.g.split(",")]
    if len(gs) != 3:
        print("--g 需三个值: 悲观,基准,乐观"); sys.exit(1)
    r_min, r_max = R_CN if args.currency == "CNY" else R_USD
    g_max = G_CN_MAX if args.currency == "CNY" else G_USD_MAX
    issues = []
    print(f"audit 币种={args.currency}  r={r}  ROIC={roic}  g={gs}  无风险利率={args.rf}\n")
    # C1 同币种
    if not (r_min <= r <= r_max):
        issues.append(f"C1 ❌ r={r} 不在 {args.currency} 区间 [{r_min},{r_max}]（币种错配？）")
    else:
        print(f"C1 ✅ r={r} 在 {args.currency} 区间")
    base_g = gs[1]
    if base_g > g_max:
        issues.append(f"C1 ❌ 基准 g={base_g} 超过 {args.currency} 上限 {g_max}（g 是终值年之后到永远）")
    else:
        print(f"C1 ✅ 基准 g={base_g} ≤ {args.currency} 上限 {g_max}")
    # C2 分母 ≥5pct
    worst = min(r - g for g in gs)
    if worst <= 0:
        issues.append(f"C2 ❌ 分母 r-g ≤ 0（模型失效）")
    elif worst < Decimal("0.05"):
        issues.append(f"C2 ⚠️ 最窄分母 r-g = {worst} < 5pct（仅作情景参考）")
    else:
        print(f"C2 ✅ 最窄分母 r-g = {worst} ≥ 5pct")
    # C3 离散风险归属
    if args.discrete_risks:
        bad = [x.strip() for x in args.discrete_risks.split(",")
               if any(k in x for k in ("折现率", "r=", "beta"))]
        if bad:
            issues.append(f"C3 ❌ 离散风险不得进 r/β: {bad}（应归情景/尾部档）")
        else:
            print(f"C3 ✅ 离散风险均归情景/尾部档")
    else:
        print("C3 ⚠️ 未提供 --discrete-risks，若有退市/VIE/监管等风险请显式归属")
    print()
    if issues:
        for i in issues:
            print(i)
        print("\n【打回】修正后重跑，直到准出")
        sys.exit(1)
    print("【准出】三条纪律通过")


def cmd_pe(args):
    roic, g, r = dec(args.roic), dec(args.g), dec(args.r)
    if r <= g:
        print(f"❌ r({r}) ≤ g({g})，模型失效"); sys.exit(1)
    pe = (D(1) - g / roic) / (r - g)
    print(f"PE = (1 - g/ROIC) / (r - g)")
    print(f"   = (1 - {g}/{roic}) / ({r} - {g})")
    print(f"   = {format(D(1) - g/roic, '.4f')} / {format(r - g, '.4f')}")
    print(f"   = {format(pe, '.2f')} 倍")


def cmd_irr(args):
    profit, mcap, pe = dec(args.profit), dec(args.mcap), dec(args.pe)
    years = int(args.years)
    payout = dec(args.payout) if args.payout else D(0)
    terminal = profit * pe
    total = terminal * (D(1) - payout) ** years + mcap * 0  # 简化：终值利润已含留存再投
    r = (total / mcap) ** (D(1) / years) - 1 if mcap else D(0)
    print(f"十年 IRR 估算:")
    print(f"  终值年利润 {profit} × 退出PE {pe} = 终值市值 {format(terminal, ',.2f')}")
    print(f"  今日市值 {mcap}  年数 {years}")
    print(f"  年化 = (终值/今日)^(1/{years}) - 1 = {format(r * 100, '.2f')}%")
    print("  注：IRR 前必须 audit 通过；r/g/ROIC 取值与理由须写入报告")


def main():
    ap = argparse.ArgumentParser(description="十年折现估值纪律工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--currency", choices=["CNY", "USD", "HKD"], required=True)
    a.add_argument("--r", required=True); a.add_argument("--roic", required=True)
    a.add_argument("--g", required=True); a.add_argument("--rf", default="")
    a.add_argument("--discrete-risks", default="")
    p = sub.add_parser("pe")
    p.add_argument("--roic", required=True); p.add_argument("--g", required=True); p.add_argument("--r", required=True)
    i = sub.add_parser("irr")
    i.add_argument("--profit", required=True); i.add_argument("--mcap", required=True)
    i.add_argument("--pe", required=True); i.add_argument("--years", default=10)
    i.add_argument("--payout", default="")
    args = ap.parse_args()
    {"audit": cmd_audit, "pe": cmd_pe, "irr": cmd_irr}[args.cmd](args)


if __name__ == "__main__":
    main()
