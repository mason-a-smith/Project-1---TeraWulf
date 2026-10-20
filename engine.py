"""TeraWulf: standard-library-only, normalized three-statement forecast + FCFF DCF.

Run: uv run --no-project wulf_three_statement.py
Research cutoff: 2026-09-24. Balance-sheet valuation anchor: 2026-06-30.
H2 2026 bridge followed by five full calendar years, 2027-2031.
See wulf_valuation_assumptions.md for sources, judgments and limitations.
Amounts USD millions; shares millions; capacity critical IT MW.
This is a simplified economic forecast, NOT a prediction of GAAP reporting.
"""
from copy import deepcopy
from math import isfinite

SOURCES = {
    '10Q': 'https://investors.terawulf.com/sec-filings/all-sec-filings/content/0001083301-26-000166/wulf-20260630.htm',
    'Q2': 'https://investors.terawulf.com/news-events/press-releases/detail/144/terawulf-reports-second-quarter-2026-results',
    'Fluidstack': 'https://investors.terawulf.com/news-events/press-releases/detail/114/terawulf-announces-fluidstack-expansion-with-160-mw-cb-5-lease-at-lake-mariner',
    'Anthropic': 'https://www.sec.gov/Archives/edgar/data/1083301/000110465926080583/tm2619468d1_ex99-1.htm',
    'NOI': 'https://investors.terawulf.com/sec-filings/all-sec-filings/content/0001104659-25-078086/tm2523008d1_ex99-3.htm',
}

# Reported June 30, 2026 balances. Accounts aggregated, not used as balance plugs.
OPENING = dict(
    cash=2619.191, restricted_cash=142.938 + 266.479,
    receivables=13.202, other_current_assets=0.133 + 18.314 + 12.726,
    ppe=3600.191, investee=424.062, sale_receivable=0.0,
    deferred_charges=572.599,
    other_assets=55.457 + 101.754 + 117.814 + 20.607 + 82.928,
    payables=197.812, construction_payables=287.461,
    deferred_rent=49.682 + 0.944,
    other_liabilities=57.292 + 159.472 + 0.664 + 23.322 + 0.290 + 0.132 + 93.994,
    warrants=1816.690, debt_principal=5725.0,
    debt_discount=89.947 + 9.054 + 388.970 + 23.917,
    equity=147.528,
)
BASE = dict(
    escalation=0.02, terminal_growth=0.02, wacc=0.10, tax_rate=0.25,
    annual_core_rent=90.0, fluid_contract=6700.0, anthropic_contract=19000.0,
    site_margins=(0.60, 0.75, 0.80, 0.80, 0.80, 0.80),
    overhead_annual=120.0, overhead_growth=0.03,
    # 45 USD/MWh * 90% use * 1.2 PUE * 8760 hours, per IT MW.
    power_revenue_per_mw=45 * 0.90 * 1.2 * 8760 / 1e6,
    receivable_days=30.0, payable_days=30.0, minimum_cash=100.0,
    asset_life=25.0, maintenance_life=10.0, maintenance_fraction=0.04,
    new_debt_rate=0.085, project_debt_limit=3500.0,
    capex_multiplier=1.0, rent_multiplier=1.0, delay_years=0,
    # Gross sale 530; 30 provision for transaction/tax leakage, judgment.
    net_sale=500.0, minority_buyout=150.0,
    basic_shares=498.932431, warrant_shares=77.704450, rsu_shares=36.219695,
)
PERIODS = ('2026 H2', '2027', '2028', '2029', '2030', '2031')
DURATIONS = (0.5, 1., 1., 1., 1., 1.)
# Delivery assumptions: CB4 Oct 2026; CB5 Apr 2027; Justified 100 MW Oct
# 2027 and 301 MW Apr 2028. These dates are analyst judgments within/near guidance.
LAKE_AVG = (186., 396., 438., 438., 438., 438.)
JUST_AVG = (0., 25., 325.75, 401., 401., 401.)
LAKE_END = (270., 438., 438., 438., 438., 438.)
JUST_END = (0., 100., 401., 401., 401., 401.)
# All opening CIP assigned to remaining Lake Mariner capacity: explicit estimate.
# Remaining Lake cost = 357 MW * $10m - opening CIP $2371.364m.
LAKE_REMAINING = 357 * 10.0 - 2371.364
JUST_REMAINING = 401 * 10.0
GROWTH_CAPEX = (LAKE_REMAINING * .70 + JUST_REMAINING * .20,
                LAKE_REMAINING * .30 + JUST_REMAINING * .65,
                JUST_REMAINING * .15, 0., 0., 0.)


def totals(b):
    assets = sum(b[k] for k in ('cash', 'restricted_cash', 'receivables',
                 'other_current_assets', 'ppe', 'investee', 'sale_receivable',
                 'deferred_charges', 'other_assets'))
    liabilities = sum(b[k] for k in ('payables', 'construction_payables',
                      'deferred_rent', 'other_liabilities', 'warrants',
                      'debt_principal')) - b['debt_discount']
    return assets, liabilities


def assert_balanced(rows, minimum_cash=100., tolerance=1e-6):
    for r in rows:
        for key in ('balance_gap', 'cash_flow_gap'):
            gap = r['checks'][key]
            if not isfinite(gap) or abs(gap) > tolerance:
                raise AssertionError(f"{r['period']}: {key} = {gap:.9f}")
        gap = r['balance']['cash'] - minimum_cash
        if not isfinite(gap) or gap < -tolerance:
            raise AssertionError(f"{r['period']}: minimum cash gap = {gap:.9f}")
        if r['drivers']['funding_gap'] > tolerance:
            raise AssertionError(f"{r['period']}: unfunded gap = {r['drivers']['funding_gap']:.9f}")


def annual_rent(total, years, escalation):
    """Infer first-year rent from lifetime rent; do not use lifetime average."""
    return total / sum((1 + escalation) ** n for n in range(years))


def forecast(a=None, strict=True):
    a = deepcopy(BASE if a is None else a)
    b = deepcopy(OPENING)
    assets, liabilities = totals(b)
    assert abs(assets - liabilities - b['equity']) < 1e-6
    fluid_start = annual_rent(a['fluid_contract'], 10, a['escalation'])
    just_start = annual_rent(a['anthropic_contract'], 20, a['escalation'])
    # Debt tranches: principal, cash coupon, remaining discount, annual amortization.
    debt = {
        'secured': [3200., .0775, 89.947, 89.947 / 4.25],
        '2030': [500., .0275, 9.054, 9.054 / (43 / 12)],
        '2031': [1000., .01, 388.970, 388.970 / (62 / 12)],
        '2032': [1025., 0., 23.917, 23.917 / (70 / 12)],
        'project': [0., a['new_debt_rate'], 0., 0.],
        'refinance': [0., a['new_debt_rate'], 0., 0.],
    }
    cip = 2371.364
    operating_ppe = b['ppe'] - cip - 331.384
    maintenance_book = 0.
    previous_lake, previous_just = 81., 0.
    rows = []
    for i, (period, dt) in enumerate(zip(PERIODS, DURATIONS)):
        p = deepcopy(b)
        idx = max(0, i - a['delay_years'])
        lake_avg, just_avg = LAKE_AVG[idx], JUST_AVG[idx]
        lake_end, just_end = LAKE_END[idx], JUST_END[idx]
        if a['delay_years'] and i == 0:
            lake_avg = lake_end = 102.
        core = a['annual_core_rent'] * (1 + a['escalation']) ** i * dt
        fluid = fluid_start * max(0., lake_avg - 60) / 378 * (1 + a['escalation']) ** i * dt
        justified = just_start * just_avg / 401 * (1 + a['escalation']) ** max(0, i - 2) * dt
        rent = (core + fluid + justified) * a['rent_multiplier']
        power = (lake_avg + just_avg) * a['power_revenue_per_mw'] * dt
        mining = (25., 20., 0., 0., 0., 0.)[i]
        revenue = rent + power + mining
        site_cost = rent * (1 - a['site_margins'][i]) + power + mining
        gross_profit = revenue - site_cost
        overhead = a['overhead_annual'] * (1 + a['overhead_growth']) ** i * dt
        old_sbc = (110., 176.8, 0., 0., 0., 0.)[i]
        ebitda = gross_profit - overhead - old_sbc
        growth_capex = GROWTH_CAPEX[i] * a['capex_multiplier']
        # Asset transfers follow delivery, not cash spend; residual CIP transferred
        # on final delivery. Depreciation is not charged on construction in process.
        transfers = min(cip + growth_capex,
                        max(0., lake_end - previous_lake) * 10 * a['capex_multiplier']
                        + max(0., just_end - previous_just) * 10 * a['capex_multiplier'])
        if lake_end == 438 and just_end == 401:
            transfers = cip + growth_capex
        maintenance = max(0., operating_ppe + .5 * transfers) * a['maintenance_fraction'] * dt
        depreciation = ((operating_ppe + .5 * transfers) / a['asset_life'] * dt
                        + (maintenance_book + .5 * maintenance) / a['maintenance_life'] * dt)
        depreciation = min(depreciation, operating_ppe + transfers + maintenance_book + maintenance)
        # Separate pools: 4% of operating net book value and 10% of maintenance
        # net book value. These are declining-balance approximations, not GAAP
        # straight-line useful-life schedules.
        dep_main = min(maintenance_book + maintenance,
                       (maintenance_book + .5 * maintenance) / a['maintenance_life'] * dt)
        operating_ppe += transfers - (depreciation - dep_main)
        maintenance_book += maintenance - dep_main
        cip += growth_capex - transfers
        amortization = min(b['deferred_charges'], 572.599 / 10 * lake_avg / 438 * dt)
        ebit = ebitda - depreciation - amortization
        b['deferred_charges'] -= amortization
        b['ppe'] += growth_capex + maintenance - depreciation
        b['receivables'] = revenue / dt * a['receivable_days'] / 365
        b['payables'] = site_cost / dt * a['payable_days'] / 365
        wc_investment = b['receivables'] - p['receivables'] - (b['payables'] - p['payables'])
        rent_release = min(b['deferred_rent'], (30., 20.626, 0., 0., 0., 0.)[i])
        b['deferred_rent'] -= rent_release
        construction_settlement = b['construction_payables'] if i == 0 else 0.
        b['construction_payables'] -= construction_settlement
        # Muskie acquisition liabilities are already in opening assets/liabilities.
        # Pay $50m in May 2027 and assume the $90m power milestone in 2029.
        acquisition_payment = 50. if i == 1 else (90. if i == 3 else 0.)
        remediation_payment = 13.1 if i == 0 else (3.4 if i == 1 else 0.)
        b['other_liabilities'] -= acquisition_payment + remediation_payment
        sale_gain = a['net_sale'] - b['investee'] if i == 0 else 0.
        if i == 0:
            b['investee'] = 0.
            b['sale_receivable'] = a['net_sale']
        sale_receipt = a['net_sale'] / 2 if i in (0, 1) else 0.
        b['sale_receivable'] -= sale_receipt
        minority = a['minority_buyout'] if i == 3 else 0.
        warrant_exercise = a['warrant_shares'] * .10 if i == 4 else 0.
        warrant_reclass = b['warrants'] if i == 4 else 0.
        b['warrants'] -= warrant_reclass
        # Existing debt refinanced at par in maturity years. This is an assumption,
        # not a committed facility. Interest uses opening coupon for the full year.
        cash_interest_base = sum(v[0] * v[1] * dt for v in debt.values())
        discount_amort = 0.
        for name, v in debt.items():
            expense = min(v[2], v[3] * dt)
            if (name == 'secured' or name == '2030') and i == 4:
                expense = v[2]
            if name == '2031' and i == 5:
                expense = v[2]
            v[2] -= expense
            discount_amort += expense
        repayment = min(debt['secured'][0], 45.359 if i == 0 else 100.)
        debt['secured'][0] -= repayment
        refinance = 0.
        for name in (('secured', '2030') if i == 4 else (('2031',) if i == 5 else ())):
            refinance += debt[name][0]
            debt[name][0] = 0.
        debt['refinance'][0] += refinance
        # Iterate only the half-year interest on new construction financing.
        draw = 0.
        for _ in range(100):
            cash_interest = cash_interest_base + .5 * draw * a['new_debt_rate'] * dt
            pretax = ebit - cash_interest - discount_amort + sale_gain
            # No NOL credit; sale proceeds already net of tax/fees.
            tax = max(0., pretax - sale_gain + old_sbc) * a['tax_rate']
            net_income = pretax - tax
            cfo = (net_income + depreciation + amortization + discount_amort
                   + old_sbc - sale_gain - wc_investment - rent_release - remediation_payment)
            cfi = -growth_capex - maintenance - construction_settlement + sale_receipt - acquisition_payment
            cash_before_funding = p['cash'] + cfo + cfi - repayment - minority + warrant_exercise
            need = max(0., a['minimum_cash'] - cash_before_funding)
            new_draw = min(need, max(0., a['project_debt_limit'] - debt['project'][0]))
            if abs(new_draw - draw) < 1e-10:
                draw = new_draw
                break
            draw = new_draw
        else:
            raise ArithmeticError(f'{period}: financing iteration did not converge')
        funding_gap = max(0., need - draw)
        debt['project'][0] += draw
        sweep = min(debt['project'][0], max(0., cash_before_funding + draw - a['minimum_cash']))
        debt['project'][0] -= sweep
        cff = draw - repayment - sweep - minority + warrant_exercise
        b['cash'] = p['cash'] + cfo + cfi + cff
        b['debt_principal'] = sum(v[0] for v in debt.values())
        b['debt_discount'] = sum(v[2] for v in debt.values())
        b['equity'] += net_income + old_sbc - minority + warrant_exercise + warrant_reclass
        # Unlevered taxes: no interest shield in FCFF; old awards are already
        # included in diluted shares and therefore added back. Future awards are
        # represented by cash-equivalent compensation within overhead.
        economic_ebit = ebit + old_sbc
        unlevered_tax = max(0., economic_ebit) * a['tax_rate']
        fcff = (economic_ebit - unlevered_tax + depreciation + amortization
                - growth_capex - maintenance - wc_investment - rent_release
                - construction_settlement - remediation_payment)
        assets, liabilities = totals(b)
        balance = dict(b, total_assets=assets, total_liabilities=liabilities,
                       liabilities_and_equity=liabilities + b['equity'])
        income = dict(rent=rent, power_reimbursement=power, mining=mining,
                      revenue=revenue, site_cash_cost=site_cost, gross_profit=gross_profit,
                      cash_overhead=overhead, existing_award_expense=old_sbc,
                      ebitda=ebitda, depreciation=depreciation, amortization=amortization,
                      operating_income=ebit, cash_interest=cash_interest,
                      debt_discount_amortization=discount_amort, sale_gain=sale_gain,
                      pretax=pretax, taxes=tax, net_income=net_income)
        flow = dict(net_income=net_income, depreciation=depreciation,
                    amortization=amortization, debt_discount_amortization=discount_amort,
                    existing_awards=old_sbc, remove_sale_gain=-sale_gain,
                    working_capital=-wc_investment, prepaid_rent_release=-rent_release,
                    remediation_payment=-remediation_payment,
                    operating_cash_flow=cfo, growth_capex=-growth_capex,
                    maintenance_capex=-maintenance, opening_construction_bills=-construction_settlement,
                    sale_receipts=sale_receipt, acquisition_payment=-acquisition_payment,
                    investing_cash_flow=cfi,
                    construction_borrowing=draw, scheduled_repayment=-repayment,
                    refinancing_proceeds=refinance, refinanced_maturities=-refinance,
                    debt_cash_sweep=-sweep, minority_purchase=-minority,
                    warrant_proceeds=warrant_exercise, financing_cash_flow=cff,
                    cash_change=cfo + cfi + cff, opening_cash=p['cash'], closing_cash=b['cash'],
                    fcff=fcff)
        rows.append(dict(period=period, income=income, balance=balance, cash_flow=flow,
                         drivers=dict(lake_average_mw=lake_avg, justified_average_mw=just_avg,
                                      ending_mw=lake_end + just_end, cip=cip,
                                      project_debt=debt['project'][0], funding_gap=funding_gap),
                         checks=dict(balance_gap=assets - liabilities - b['equity'],
                                     cash_flow_gap=b['cash'] - p['cash'] - cfo - cfi - cff,
                                     cash_headroom=b['cash'] - a['minimum_cash'])))
        previous_lake, previous_just = lake_end, just_end
    if strict:
        assert_balanced(rows, a['minimum_cash'])
    return rows


def value(rows, a, wacc=None, growth=None):
    w = a['wacc'] if wacc is None else wacc
    g = a['terminal_growth'] if growth is None else growth
    if w <= g:
        raise ValueError('WACC must exceed terminal growth')
    times = (.5, 1.5, 2.5, 3.5, 4.5, 5.5)
    pv_flows = sum(r['cash_flow']['fcff'] / (1 + w) ** t for r, t in zip(rows, times))
    last = rows[-1]
    # Terminal: sustain all cash operating costs; replace depreciation AND
    # amortizing contract costs, and fund real growth above assumed price inflation.
    cash_profit = last['income']['gross_profit'] - last['income']['cash_overhead']
    da = last['income']['depreciation'] + last['income']['amortization']
    real_growth = max(0., g - a['escalation'])
    extra_capex = real_growth * last['income']['rent'] / .20
    terminal_wc = g * (last['balance']['receivables'] - last['balance']['payables'])
    terminal_cf = ((cash_profit - da) * (1 - a['tax_rate']) * (1 + g)
                   - extra_capex - terminal_wc)
    pv_terminal = terminal_cf / (w - g) / (1 + w) ** times[-1]
    ev = pv_flows + pv_terminal
    sale_pv = sum(r['cash_flow']['sale_receipts'] / (1 + w) ** t for r, t in zip(rows, times))
    minority_pv = sum(-r['cash_flow']['minority_purchase'] / (1 + w) ** t for r, t in zip(rows, times))
    acquisition_pv = sum(-r['cash_flow']['acquisition_payment'] / (1 + w) ** t for r, t in zip(rows, times))
    # Restricted cash not distributed; minimum operating cash excluded as well.
    equity = (ev + OPENING['cash'] - a['minimum_cash'] + sale_pv
              - OPENING['debt_principal'] - minority_pv - acquisition_pv)
    shares = a['basic_shares'] + a['warrant_shares'] + a['rsu_shares']
    # Retain convertible principal as debt. Charge only intrinsic value ABOVE
    # capped calls, avoiding counting full conversion shares plus full debt.
    def residual(price):
        extra_claim = (500 / 8.48 * max(0., price - 12.80)
                       + 1000 / 12.43 * max(0., price - 18.76)
                       + 1025 / 19.94 * max(0., price - 19.94))
        return price * shares + extra_claim - equity
    lo, hi = 0., max(1., equity / shares)
    if equity > 0:
        for _ in range(100):
            mid = (lo + hi) / 2
            if residual(mid) > 0:
                hi = mid
            else:
                lo = mid
        price = (lo + hi) / 2
    else:
        price = 0.
    return dict(pv_explicit_fcff=pv_flows, terminal_fcff=terminal_cf,
                pv_terminal=pv_terminal, enterprise_value=ev,
                sale_proceeds_pv=sale_pv, minority_claim_pv=minority_pv,
                acquisition_claim_pv=acquisition_pv,
                equity_value=equity, diluted_shares=shares,
                uncapped_equity_per_share=equity / shares, value_per_share=price,
                terminal_share_ev=pv_terminal / ev if ev else float('nan'))


def print_table(title, rows, section):
    print('\n' + title + ' (USD millions, except MW)')
    print(f'{"Item":<32}' + ''.join(f'{r["period"]:>13}' for r in rows))
    for key in rows[0][section]:
        print(f'{key.replace("_", " "):<32}' + ''.join(
            f'{0. if abs(r[section][key]) < .05 else r[section][key]:>13,.1f}' for r in rows))


def main():
    rows = forecast()
    for title, section in [('Capacity and funding', 'drivers'), ('Income statement', 'income'),
                           ('Balance sheet', 'balance'), ('Cash flow statement', 'cash_flow'),
                           ('Annual checks', 'checks')]:
        print_table(title, rows, section)
    assert_balanced(rows)
    print('\nAll balance, cash-flow, minimum-cash and funding checks passed.')
    print('\nDCF: June 30, 2026 balance-sheet anchor; September 24 information set')
    for key, number in value(rows, BASE).items():
        print(f'{key}: {number:,.2%}' if key == 'terminal_share_ev' else f'{key}: {number:,.2f}')
    print('\nWACC sensitivity; terminal growth = 2%')
    for rate in (.08, .09, .10, .11, .12):
        v = value(rows, BASE, wacc=rate)
        print(f'{rate:.0%}: ${v["value_per_share"]:.2f}; uncapped equity {v["equity_value"]:,.1f}')
    print('\nOperating scenarios (same existing contracted footprint)')
    for name, changes in (
        ('Downside', dict(capex_multiplier=1.20, rent_multiplier=.95,
                          site_margins=(.50, .65, .70, .75, .75, .75), wacc=.12)),
        ('Base', {}),
        ('Upside', dict(capex_multiplier=.90, rent_multiplier=1.05,
                        site_margins=(.65, .80, .85, .85, .85, .85), wacc=.08)),
        ('One-year delivery delay', dict(delay_years=1)),
    ):
        a = dict(BASE, **changes)
        try:
            scenario = forecast(a)
            v = value(scenario, a)
            print(f'{name}: ${v["value_per_share"]:.2f}; equity {v["equity_value"]:,.1f}; '
                  f'peak project borrowing {max(r["drivers"]["project_debt"] for r in scenario):,.1f}')
        except AssertionError as error:
            print(f'{name}: FINANCING FAILURE: {error}')


def self_test():
    rows = forecast()
    assert_balanced(rows)
    # Independent cash/earnings bridge to unlevered cash flow.
    for r in rows:
        inc, cf = r['income'], r['cash_flow']
        unlevered_tax = max(0., inc['operating_income'] + inc['existing_award_expense']) * BASE['tax_rate']
        expected = (cf['operating_cash_flow'] + inc['cash_interest'] + inc['taxes']
                    - unlevered_tax + cf['growth_capex'] + cf['maintenance_capex']
                    + cf['opening_construction_bills'])
        assert abs(expected - cf['fcff']) < 1e-7
    for key in ('balance_gap', 'cash_flow_gap'):
        broken = deepcopy(rows)
        broken[1]['checks'][key] = 1.
        try:
            assert_balanced(broken)
        except AssertionError as error:
            assert '2027' in str(error) and key in str(error)
        else:
            raise AssertionError(f'Failed to detect {key}')
    try:
        forecast(dict(BASE, project_debt_limit=0.))
    except AssertionError as error:
        assert 'minimum cash gap' in str(error)
    else:
        raise AssertionError('Failed to detect unavailable financing')
    baseline = value(rows, BASE)
    assert value(rows, BASE, wacc=.12)['equity_value'] < baseline['equity_value']
    a = dict(BASE, capex_multiplier=1.01)
    assert value(forecast(a), a)['equity_value'] < baseline['equity_value']
    assert abs(sum(r['cash_flow']['sale_receipts'] for r in rows) - BASE['net_sale']) < 1e-7
    assert abs(sum(-r['cash_flow']['growth_capex'] for r in rows)
               - LAKE_REMAINING - JUST_REMAINING) < 1e-7
    print('PASS: statements, independent FCFF bridge, deliberate failures, financing cap, sensitivities, sale and capex totals')


if __name__ == '__main__':
    import sys
    self_test() if '--self-test' in sys.argv else main()
