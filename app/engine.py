### File: `app/engine.py`

````python
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
````

---

### File: `app/workbench.py`

````python
"""Locked model adapter, bounded controls, diagnostics and reproducible outputs.
No external packages or network calls. Dollar figures and shares in millions.
"""
import copy
import json
import math
from pathlib import Path
import engine

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {
 'capex_multiplier': dict(label='Remaining construction cost', base=1., low=.8, high=1.3, step=.01, unit='x', basis='Analyst stress around $5,208.636m; $8–10m/MW Lake guidance does not verify remaining spend. +/-20–30% tests allocation/overrun risk.', challenge='Opening CIP may belong to multiple sites; tenant-funded fit-out may reduce net costs.', evidence='Project budgets reconciled to paid invoices, CIP, unpaid commitments and tenant contributions.'),
 'rent_multiplier': dict(label='Contract rent realization', base=1., low=.9, high=1.1, step=.01, unit='x', basis='Analyst +/-10% around inferred first-year rent, not an option to rewrite signed leases.', challenge='Lifetime lease headline may include escalators, phased delivery or reimbursed costs.', evidence='Executed rent schedule and tenant acceptance/payment evidence.'),
 'mature_margin': dict(label='Mature site cash margin', base=.8, low=.7, high=.85, step=.01, unit='fraction', basis='70–85% of rent only; 85% prior site NOI indication is an upper bound, not consolidated margin guidance.', challenge='Cooling, maintenance and customer concentration may prevent target margins.', evidence='At least two quarters of site cost reporting excluding power pass-through.'),
 'delay_years': dict(label='Delivery delay', base=0, low=0, high=1, step=1, unit='years', basis='Discrete on-time versus one-year slip; construction spending is not deferred with rent.', challenge='A smaller delay is possible; this coarse stress is not a probability forecast.', evidence='Commissioning reports, customer acceptance and first cash rent.'),
 'overhead_annual': dict(label='Annual cash overhead', base=120., low=100., high=160., step=5., unit='$m', basis='$120m anchor includes $20m future compensation; $100–160m analyst operating-scale stress.', challenge='Public company costs may persist despite mining exit.', evidence='Cash SG&A bridge separating old awards from recurring future compensation.'),
 'maintenance_fraction': dict(label='Maintenance / operating PP&E', base=.04, low=.03, high=.06, step=.005, unit='fraction', basis='3–6% annual declining-net-book proxy; terminal separately replaces D&A.', challenge='Replacement cost may rise while accounting net book value falls.', evidence='Engineering lifecycle plan and recurring cash replacement history.'),
 'receivable_days': dict(label='Collection period', base=30., low=15., high=60., step=5., unit='days', basis='15–60 day analyst monthly-billing stress; not a historical confidence interval.', challenge='Tenant acceptance or billing disputes can delay cash despite reported revenue.', evidence='Aging schedule and realized cash collections.'),
 'project_debt_limit': dict(label='Assumed new debt availability', base=3500., low=0., high=4500., step=100., unit='$m', basis='Hypothetical incremental facility; zero explicitly tests no financing. $4.5bn ceiling is a stress, not capacity confirmed by lenders.', challenge='An assumed facility is not committed financing; lender security and covenants matter.', evidence='Signed facilities, draw conditions and covenant headroom.'),
 'new_debt_rate': dict(label='New debt / refinancing rate', base=.085, low=.07, high=.12, step=.005, unit='fraction', basis='7–12% analyst credit stress around 8.5%; WACC is separately controlled.', challenge='Financing cost and WACC are linked economically; OAT deliberately isolates one channel.', evidence='Executable financing terms and refinancing evidence.'),
 'wacc': dict(label='WACC', base=.10, low=.08, high=.14, step=.005, unit='fraction', basis='8–14% judgment band; 40% equity x 15.44% + 60% debt x 8.5% x (1–25%) = 10%. Not an observed market capital structure.', challenge='No immediate tax shields, development risk or equity-heavy funding warrant higher WACC.', evidence='Financeable capital mix, current yields and sector beta/ERP review.'),
 'terminal_growth': dict(label='Terminal nominal growth', base=.02, low=0., high=.02, step=.005, unit='fraction', basis='0–2% nominal growth bounded by assumed lease inflation; no free real expansion.', challenge='Long leases expire; renewal, re-letting and replacement capex remain uncertain.', evidence='Renewal spreads, competitive rents and asset replacement estimates.'),
}
DEFAULTS = {k:v['base'] for k,v in CONTROLS.items()}

def inputs(changes=None):
    supplied = changes or {}
    if set(supplied)-set(CONTROLS):
        raise ValueError('Unknown controls: ' + ', '.join(set(supplied)-set(CONTROLS)))
    p = dict(DEFAULTS, **supplied)
    for k,v in p.items():
        c=CONTROLS[k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not c['low'] <= v <= c['high']:
            raise ValueError(f'{k} outside approved bounds [{c["low"]}, {c["high"]}]')
    if p['delay_years'] not in (0,1):
        raise ValueError('Delivery delay must be zero or one year')
    a=copy.deepcopy(engine.BASE)
    a.update({k:v for k,v in p.items() if k!='mature_margin'})
    a['delay_years']=int(a['delay_years'])
    a['site_margins']=(.60,.75)+tuple([p['mature_margin']]*4)
    return p,a

def evaluate(changes=None):
    p,a=inputs(changes)
    # Diagnostic path retains cash deficits; never replaces funding with a plug.
    rows=engine.forecast(a, strict=False)
    checks=[]
    for r in rows:
        for key in ('balance_gap','cash_flow_gap'):
            checks.append(dict(period=r['period'],name=key,value=r['checks'][key],passed=abs(r['checks'][key])<1e-6))
        checks.append(dict(period=r['period'],name='funding_gap',value=r['drivers']['funding_gap'],passed=r['drivers']['funding_gap']<1e-6))
        checks.append(dict(period=r['period'],name='cash_buffer',value=r['balance']['cash']-a['minimum_cash'],passed=r['balance']['cash']>=a['minimum_cash']-1e-6))
    valid=all(c['passed'] for c in checks)
    v=engine.value(rows,a) if valid else None
    return dict(inputs=p,valid=valid,valuation=v,statements=rows,checks=checks,
                peak_borrowing=max(r['drivers']['project_debt'] for r in rows),
                max_funding_gap=max(r['drivers']['funding_gap'] for r in rows),
                cumulative_fcff=sum(r['cash_flow']['fcff'] for r in rows),
                final_ebit=rows[-1]['income']['operating_income'],final_fcff=rows[-1]['cash_flow']['fcff'],
                warning='CONDITIONAL: uncommitted financing and unverified remaining capex. June 30, 2026 retrospective valuation; October 19 evidence review. Not an October spot fair-value estimate.')

def scenarios():
    return {name:evaluate(changes) for name,changes in {
      'Low / construction stress':dict(capex_multiplier=1.2,rent_multiplier=.95,mature_margin=.75,wacc=.12),
      'Base':{},
      'High / execution success':dict(capex_multiplier=.9,rent_multiplier=1.05,mature_margin=.85,wacc=.08),
      'One-year delivery delay':dict(delay_years=1),
      'No new financing':dict(project_debt_limit=0),
    }.items()}

def sensitivities():
    # Defined before execution; two range sets reveal sensitivity to range choice.
    broad={'capex_multiplier':(.9,1.1),'rent_multiplier':(.95,1.05),'mature_margin':(.75,.85),
           'overhead_annual':(100,140),'maintenance_fraction':(.03,.05),'receivable_days':(15,45),
           'wacc':(.08,.12),'new_debt_rate':(.07,.10)}
    narrow={'capex_multiplier':(.98,1.02),'rent_multiplier':(.99,1.01),'mature_margin':(.79,.81),
           'overhead_annual':(115,125),'maintenance_fraction':(.035,.045),'receivable_days':(25,35),
           'wacc':(.095,.105),'new_debt_rate':(.08,.09)}
    output={}
    for band,ranges in [('Broad',broad),('Narrow',narrow)]:
        runs=[]
        for driver,(lo,hi) in ranges.items():
            l,h=evaluate({driver:lo}),evaluate({driver:hi})
            both=l['valid'] and h['valid']
            runs.append(dict(driver=driver,low=lo,high=hi,both_feasible=both,
                low_valid=l['valid'],high_valid=h['valid'],
                ebit_span=abs(h['final_ebit']-l['final_ebit']),
                fcff_span=abs(h['cumulative_fcff']-l['cumulative_fcff']),
                value_span=abs(h['valuation']['equity_value']-l['valuation']['equity_value']) if both else None,
                low_equity=l['valuation']['equity_value'] if l['valid'] else None,
                high_equity=h['valuation']['equity_value'] if h['valid'] else None))
        output[band]=runs
    return output

def reverse_dcf(price=11.68):
    """Dated market-price hurdle, not a same-date market-implied expectation.
    September/October capital structure is not observed; explicitly retain anchor.
    """
    b=evaluate(); v=b['valuation']; a=engine.BASE
    claims=500/8.48*max(0,price-12.8)+1000/12.43*max(0,price-18.76)+1025/19.94*max(0,price-19.94)
    target_equity=price*v['diluted_shares']+claims
    target_ev=target_equity-engine.OPENING['cash']+a['minimum_cash']-v['sale_proceeds_pv']+engine.OPENING['debt_principal']+v['minority_claim_pv']+v['acquisition_claim_pv']
    required_terminal=(target_ev-v['pv_explicit_fcff'])*(1+a['wacc'])**5.5*(a['wacc']-a['terminal_growth'])
    return dict(price=price,price_date='2026-10-16 close',required_terminal_fcff=required_terminal,
                base_terminal_fcff=v['terminal_fcff'],ratio=required_terminal/v['terminal_fcff'],
                label='Reverse valuation hurdle at a dated $11.68 price; mismatched dates, NOT a contemporaneous market-implied forecast.')

def all_results():
    return dict(base=evaluate(),scenarios=scenarios(),sensitivities=sensitivities(),reverse=reverse_dcf(),
        grid=[dict(wacc=w,growth=g,**evaluate({'wacc':w,'terminal_growth':g})['valuation']) for w in (.08,.09,.10,.11,.12,.14) for g in (0.,.01,.02)])

if __name__=='__main__':
    (ROOT/'outputs/results.json').write_text(json.dumps(all_results(),indent=2,allow_nan=False),encoding='utf-8')
    print('Wrote outputs/results.json')
````

---

### File: `app/comps.py`

````python
"""Same-date price / lagged-balance peer diagnostics. No vendor EV shortcuts."""
DATA=[
 dict(ticker='WULF',price=11.68,shares=498.932431,cash=2619.191,debt=5213.112,finance_leases=.290,warrant_liability=1816.690,nci=.244,investments=424.062,book_equity=147.284,revenue=168.455+78.779-82.041),
 dict(ticker='CIFR',price=8.98,shares=414.253564,cash=831.829,debt=94.484+5446.866,finance_leases=4.475+.795,warrant_liability=632.060,nci=25.679,investments=0.,book_equity=562.057,revenue=223.942+59.675-92.524),
 dict(ticker='IREN',price=26.99,shares=380.193608,cash=5895.6,debt=169.4+7423.6,finance_leases=125.3+118.5,warrant_liability=0.,nci=0.,investments=0.,book_equity=4185.613,revenue=707.007),
]

def calculate():
    rows=[]
    for d in DATA:
        mc=d['price']*d['shares']
        claims=d['debt']+d['finance_leases']+d['warrant_liability']+d['nci']-d['cash']-d['investments']
        rows.append(dict(d,market_cap=mc,net_claims=claims,enterprise_value=mc+claims,
                         ev_revenue=(mc+claims)/d['revenue'],price_book=mc/d['book_equity']))
    target=rows[0]
    for p in rows[1:]:
        p['wulf_ev_revenue_price_unfloored']=(p['ev_revenue']*target['revenue']-target['net_claims'])/target['shares']
        p['wulf_price_book_price']=p['price_book']*target['book_equity']/target['shares']
    return rows
````

---

### File: `app/server.py`

````python
"""Local-only workbench. python app/server.py; visit http://127.0.0.1:8765."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import workbench

class Handler(BaseHTTPRequestHandler):
    def respond(self,obj,status=200):
        body=json.dumps(obj,allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/config':
            self.respond(dict(controls=workbench.CONTROLS,base=workbench.evaluate(),analysis=workbench.all_results()))
        elif self.path in ('/','/index.html'):
            body=Path(__file__).with_name('index.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body)
        else:
            self.send_error(404)
    def do_POST(self):
        if self.path!='/api/evaluate': self.send_error(404); return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<10000: raise ValueError('Invalid request size')
            self.respond(workbench.evaluate(json.loads(self.rfile.read(n))))
        except (ValueError,TypeError,AssertionError,ArithmeticError) as e:
            self.respond({'error':str(e)},400)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765)
    port=parser.parse_args().port
    print(f'TeraWulf workbench: http://127.0.0.1:{port} - Ctrl+C to stop',flush=True)
    HTTPServer(('127.0.0.1',port),Handler).serve_forever()
````

---

### File: `app/validate.py`

````python
"""Executable checks; failures raise and produce nonzero exit status."""
import copy, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import engine, workbench, comps

ROOT=Path(__file__).resolve().parents[1]

def run():
    out=[]
    def passed(name,detail): out.append(dict(test=name,status='PASS',detail=detail))
    engine.self_test()
    passed('Legacy regression','Original engine self-test passes, including deliberate statement/cash failures.')
    a,l=engine.totals(engine.OPENING)
    assert abs(a-8048.395)<1e-6 and abs(l-7900.867)<1e-6
    assert abs(a-l-147.528)<1e-6
    assert abs(engine.OPENING['cash']+engine.OPENING['restricted_cash']-3028.608)<1e-6
    assert abs(engine.OPENING['debt_principal']-engine.OPENING['debt_discount']-5213.112)<1e-6
    passed('Independent opening filing reconciliation','10-Q totals: assets 8048.395; liabilities 7900.867; total equity 147.528; total cash 3028.608; debt book 5213.112. USD m.')
    # Published annual statement arithmetic, distinct from the forecast.
    assert abs(151.556+16.899-168.455)<1e-9
    assert abs(-123.180-1368.945+4940.835-3448.710)<1e-8
    assert abs(274.065+3448.710-3722.775)<1e-8
    assert abs(6558.182-6417.737-140.445)<1e-8
    passed('FY2025 base-year filing reconciliation','Revenue segments; FY2025 assets = liabilities + equity; CFO + CFI + CFF = cash change; beginning + change = total unrestricted/restricted cash.')
    # Independent perpetuity identity: 100 each year forever at 10% = 1000 EV.
    cf=[100.]*5; w=.1; g=0.
    ev=sum(c/(1+w)**(i+1) for i,c in enumerate(cf))+(100/(w-g))/(1+w)**5
    assert abs(ev-1000)<1e-9
    assert abs((ev+50-300)/50-15)<1e-9
    passed('Synthetic known-answer DCF','Level $100 FCFF perpetuity at 10% => EV 1000; +50 cash -300 debt /50 shares => $15. This is NOT the missing published course training answer.')
    base=workbench.evaluate(); rows=base['statements']; v=base['valuation']
    assert base['valid']
    for r in rows:
        cf=r['cash_flow']; inc=r['income']
        expected=cf['operating_cash_flow']+inc['cash_interest']+inc['taxes']-max(0,inc['operating_income']+inc['existing_award_expense'])*.25+cf['growth_capex']+cf['maintenance_capex']+cf['opening_construction_bills']
        assert abs(expected-cf['fcff'])<1e-7
    passed('Three statements and independent FCFF bridge','All six periods articulate; FCFF reconciles from CFO after removing financing effects.')
    bridge=v['enterprise_value']+engine.OPENING['cash']-100+v['sale_proceeds_pv']-5725-v['minority_claim_pv']-v['acquisition_claim_pv']
    assert abs(bridge-v['equity_value'])<1e-8
    assert abs(v['diluted_shares']-612.856576)<1e-8
    passed('Enterprise/equity and share bridge','Opening principal deducted once; future debt is not deducted after capex; warrants represented in shares, not liability twice.')
    for g in [0,.005,.01,.015,.02]:
        vs=[engine.value(rows,engine.BASE,wacc=w,growth=g)['equity_value'] for w in [.08,.09,.1,.11,.12,.14]]
        assert all(x>y for x,y in zip(vs,vs[1:]))
    for w in [.08,.1,.12,.14]:
        vs=[engine.value(rows,engine.BASE,wacc=w,growth=g)['equity_value'] for g in [0,.005,.01,.015,.02]]
        assert all(x<y for x,y in zip(vs,vs[1:]))
    try: engine.value(rows,engine.BASE,wacc=.02,growth=.02)
    except ValueError: pass
    else: raise AssertionError('WACC <= growth accepted')
    passed('DCF boundary / monotonicity','Full approved WACC/g grid: value falls as WACC rises; rises as g rises; w<=g rejected.')
    pred=ROOT/'validation/AI_DIRECTIONAL_PRECOMMIT.md'
    digest=hashlib.sha256(pred.read_bytes()).hexdigest()
    changed=workbench.evaluate({'capex_multiplier':1.01})
    assert changed['valuation']['equity_value']<v['equity_value']
    assert changed['cumulative_fcff']<base['cumulative_fcff']
    assert changed['peak_borrowing']>base['peak_borrowing']
    passed('AI-authored directional precommit',dict(prediction_sha256=digest,old=1.,new=1.01,units='remaining capex multiple',old_equity=v['equity_value'],new_equity=changed['valuation']['equity_value'],old_fcff=base['cumulative_fcff'],new_fcff=changed['cumulative_fcff'],decision_effect='watch/defer unchanged',floor_reason='Both negative residuals display $0.'))
    for change in [{'project_debt_limit':0},{'delay_years':1}]:
        r=workbench.evaluate(change)
        assert not r['valid'] and r['valuation'] is None and r['max_funding_gap']>0
    assert workbench.evaluate()==base
    for bad in [{'wacc':float('nan')},{'mature_margin':.95},{'delay_years':.5},{'unknown':3}]:
        try: workbench.evaluate(bad)
        except ValueError: pass
        else: raise AssertionError(f'Bad input accepted: {bad}')
    passed('Highest-risk funding failure / recovery / bounds','No financing and delayed rent fail loudly; no artificial financing plug; base reset reproduces original exactly; invalid controls rejected.')
    peers=comps.calculate()
    assert len({r['ticker'] for r in peers})==3
    assert all(r['book_equity']>0 and r['revenue']>0 and r['shares']>0 for r in peers)
    assert abs(peers[0]['revenue']-165.193)<1e-8 and abs(peers[1]['revenue']-191.093)<1e-8
    for p in peers:
        assert abs(p['ev_revenue']*p['revenue']-p['enterprise_value'])<1e-7
        assert abs(p['price_book']*p['book_equity']-p['market_cap'])<1e-7
    passed('Peer definitions','Identical Oct16 close; June30 basic shares and balances; common-equity P/B; TTM June30 revenue; carrying debt and finance leases, operating leases excluded, restricted cash not netted.')
    for p in workbench.sensitivities().values():
        assert all(r['value_span'] is None if not r['both_feasible'] else r['value_span']>=0 for r in p)
    passed('Sensitivity feasibility','Infeasible endpoints receive no value ranking. Broad and narrow ranges independently rerun the model.')
    result=dict(executed_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,checks=out,
                pending=['Published weekly-starter known-answer comparison','Human AI-off locked changed-input record / precommit','Named partner feedback','Edition A checkpoint receipt','Recorded videos and corrected transcripts'])
    (ROOT/'validation/test_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__': run()
````

---

### File: `app/build.py`

````python
"""Generate reviewable tables directly from the model, without notebook execution."""
from pathlib import Path
import csv, html, json, hashlib
from datetime import datetime,timezone
import engine,workbench,comps
ROOT=Path(__file__).resolve().parents[1]
def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
def n(x): return f'{x:,.2f}' if x is not None else 'WITHHELD'
def render_md(text):
    # Portable static rendering, no third-party JavaScript/fonts/CDNs.
    import re
    def inline(x):
        x=html.escape(x)
        x=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',x)
        return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',x)
    parts=[]; in_table=False
    for l in text.splitlines():
        if l.startswith('|'):
            if not in_table: parts.append('<div class="scroll"><table>'); in_table=True
            if re.match(r'^\|[\s:|\-]+$',l): continue
            parts.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in l.strip('|').split('|'))+'</tr>')
        else:
            if in_table:parts.append('</table></div>');in_table=False
            if l.startswith('#'):
                level=len(l)-len(l.lstrip('#'));parts.append(f'<h{level}>'+inline(l[level:].strip())+f'</h{level}>')
            elif l:parts.append('<p>'+inline(l)+'</p>')
    if in_table:parts.append('</table></div>')
    return '<!doctype html><meta charset="utf-8"><title>TeraWulf — visible model output</title><style>body{font:14px system-ui;color:#172d3a;max-width:1250px;margin:35px auto;padding:20px}h1,h2{color:#125f70}h2{margin-top:35px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}td{border-bottom:1px solid #dce3e8;padding:7px;white-space:nowrap}tr:first-child{background:#e5f0f3;font-weight:bold}a{color:#076e85}p{line-height:1.55}</style>'+''.join(parts)

def build():
    d=workbench.all_results(); b=d['base'];v=b['valuation'];p=comps.calculate()
    (ROOT/'outputs/results.json').write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf-8')
    (ROOT/'outputs/peer_results.json').write_text(json.dumps(p,indent=2),encoding='utf-8')
    parts=['# TeraWulf — frozen visible output','',
    'Generated from the locked engine. USD millions unless per share, MW or percentages. Retrospective valuation anchor June 30, 2026; information reviewed October 19, 2026. This is not a contemporaneous June backtest or an October spot valuation.',
    '## Decision and causal cases',
    'WATCH / DEFER; 0% allocation. Contracted-footprint conditional common-equity range approximately $0–$2.75/share. Low case funding fails and is not a financeable valuation. No probabilistic or total-company confidence interval is claimed.',
    table(['Case','Feasible under assumed debt?','Common $/share','Uncapped equity $m','Peak new debt $m','Max funding deficit $m'],[[k,r['valid'],n(r['valuation']['value_per_share']) if r['valid'] else 'WITHHELD',n(r['valuation']['equity_value']) if r['valid'] else 'WITHHELD',n(r['peak_borrowing']),n(r['max_funding_gap'])] for k,r in d['scenarios'].items()]),
    'High: 10% cheaper remaining capex, 5% higher rent realization, 85% mature site margin, 8% WACC. Base: 80% mature margin, 10% WACC. Low: 20% cost overrun, 5% lower rent, 75% mature margin, 12% WACC. Early ramp margins remain 60% / 75% in every case. This explains the difference from the older $2.80 high case.',
    '## Enterprise-to-equity bridge',table(['Component','USD m / indicated units'],[[k,n(x*100)+'%' if k=='terminal_share_ev' else n(x)] for k,x in v.items()]),
    'Cash add-back is $2,619.191 less $100 operating reserve; restricted cash $409.417 is excluded. Debt uses $5,725 principal, not $5,213.112 carrying amount. Future debt is not deducted a second time. Base shares: 612.856576m. Equity is floored only for the displayed common-share claim; negative residual remains visible.',
    '## WACC–growth sensitivity',table(['WACC','g 0%','g 1%','g 2%'],[[f'{w:.0%}']+[n(next(x for x in d['grid'] if x['wacc']==w and x['growth']==g)['uncapped_equity_per_share']) for g in (0,.01,.02)] for w in (.08,.09,.10,.11,.12,.14)]),
    'Cells are UNFLOORED equity per diluted share. The floor would obscure every base-grid change. Terminal value is '+n(v['terminal_share_ev']*100)+'% of net operating EV because negative explicit FCFF offsets terminal PV; it is not a probability or percentage of common equity.',
    '## Reverse-DCF price hurdle',
    f"At an illustrative $11.68/share hurdle (observed October 16 close), holding the June capital bridge and explicit forecast fixed requires terminal FCFF of ${d['reverse']['required_terminal_fcff']:,.1f}m versus ${v['terminal_fcff']:,.1f}m base, or {d['reverse']['ratio']:.2f}x. This is a reverse valuation exercise, NOT a contemporaneous market-implied forecast: the quote and balance-sheet dates differ. It cannot be called the market's required MW without modeling the incremental capex and financing.",
    '## One-at-a-time sensitivities']
    for band,rs in d['sensitivities'].items():
        parts += ['### '+band+' ranges',table(['Driver','Low','High','Both feasible','2031 EBIT span','Cumulative FCFF span','Uncapped equity span'],[[r['driver'],r['low'],r['high'],r['both_feasible'],n(r['ebit_span']),n(r['fcff_span']),n(r['value_span'])] for r in rs])]
    parts += ['Broad valid value ranking: WACC, mature margin, rent, overhead, collection days, financing rate. Broad capex and maintenance upper endpoints fail funding, so excluding them is a feasibility result, not evidence of low importance. In narrow feasible ranges the value ranking becomes WACC, maintenance, capex, margin, rent, overhead, collections, financing rate. Ranking therefore depends on the chosen ranges.',
    'Mature site margin leads 2031 operating-profit sensitivity in both ranges. Construction dominates broad cumulative-FCFF span ($1,167.7m) but includes an infeasible endpoint; maintenance leads the fully feasible narrow FCFF span ($330.2m). Rent/margin affect recurring profit, taxes and terminal cash. Capex uses immediate cash and drives future depreciation/maintenance. Working capital affects cash without changing EBIT. WACC changes present value, not the statements. New debt rate changes levered profit and liquidity but not FCFF at fixed WACC; that isolation is intentional, not a claim that financing risk has no value effect.',
    '## Comparable-company diagnostic',table(['Name','Oct16 price','Jun30 basic shares m','TTM revenue','EV proxy','EV/revenue','P/book'],[[r['ticker'],n(r['price']),n(r['shares']),n(r['revenue']),n(r['enterprise_value']),n(r['ev_revenue']),n(r['price_book'])] for r in p]),
    table(['Peer applied to WULF','EV/revenue implied $/basic share, unfloored','P/book implied $/basic share'],[[r['ticker'],n(r['wulf_ev_revenue_price_unfloored']),n(r['wulf_price_book_price'])] for r in p[1:]]),
    'Prices share October 16, 2026 close. Financial balances/share counts are June 30; revenue is TTM through June 30. Basic market cap plus book debt, finance leases, warrant liabilities and NCI, less unrestricted cash and equity-method investments. No operating-lease capitalization; no restricted-cash netting. P/B uses common book equity, not total equity. These lagged-balance diagnostics are not fully diluted spot EVs. See PEER_POLICY.md for limitations and source definitions.',
    '## Complete pro-forma statements']
    for s in ['income','balance','cash_flow','drivers','checks']:
        parts+=['### '+s.replace('_',' ').title(),table(['USD m / stated units']+[r['period'] for r in b['statements']],[[k]+[n(r[s][k]) for r in b['statements']] for k in b['statements'][0][s]])]
    text='\n\n'.join(parts)+'\n'
    (ROOT/'outputs/VISIBLE_OUTPUT.md').write_text(text,encoding='utf-8')
    (ROOT/'outputs/VISIBLE_OUTPUT.html').write_text(render_md(text),encoding='utf-8')
    with (ROOT/'outputs/statements.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['section','line','units']+[r['period'] for r in b['statements']])
        for s in ['income','balance','cash_flow','drivers','checks']:
            for k in b['statements'][0][s]:writer.writerow([s,k,'USD m except capacity MW']+[r[s][k] for r in b['statements']])
    audit=['# Assumption challenge record','', 'Value · basis · challenge · evidence that would change it. Final AI-assisted review, October 19, 2026. No named human partner feedback was found; the earlier skeptical-colleague section is AI-generated and is credited to AI, not a classmate.',table(['Exposed driver','Base / allowed bounds','Basis','Challenge','Evidence that would change it'],[[c['label'],f"{c['base']} [{c['low']}, {c['high']}] {c['unit']}",c['basis'],c['challenge'],c['evidence']] for c in workbench.CONTROLS.values()])]
    audit+=['## Locked model assumptions requiring analyst review','These are not editable in the teammate panel. Locked does not mean proven. A documented code/input revision and rerun is required to change them.',table(['Parameter','Value','Basis','Challenge','Reversal evidence'],[[k,str(x),'Prior September24 forecast; see terawulf_assumption_table.md and SOURCE_REGISTER.md','Simplified economic proxy; may differ from executed contract, accounting schedule or funding plan','New filing / executed schedule reconciled to this exact parameter'] for k,x in engine.BASE.items() if k not in workbench.CONTROLS and k!='site_margins']),
    '## Architecture assumptions outside the parameter dictionary',table(['Driver','Value / basis','Challenge','Evidence that changes it'],[
    ['Lake remaining cost','357 MW × $10m − $2,371.364m CIP = $1,198.636m','All CIP assigned to Lake; unverified allocation','Site-level paid/committed-cost rollforward'],
    ['Justified cost','401 MW × $10m = $4,010m','Lake cost per MW is transferred to Kentucky; may not apply','Fixed-price budget and tenant funding agreement'],
    ['Commissioning','Lake 270/438 end2026/27 MW; Justified100/401 end2027/28','Exact dates are judgments within guidance, not accepted deliveries','Tenant acceptance and actual rent commencement'],
    ['Capex timing','Lake70%/30%; Justified20%/65%/15% in H226/27/28','Monthly cash troughs can exceed annual model deficits','Monthly draw and construction schedules'],
    ['Mining','25 H226,20 FY27,zero later; zero cash margin','Residual business could have positive or negative value','Disposition terms / persistent operating cash margin'],
    ['Old awards','110 H226 and176.8 FY27, added back; RSUs dilute','Expense timing and forfeiture assumptions simplified','Award-by-award vesting schedule'],
    ['Acquisition obligations','50 FY27;90 FY29; remediation13.1/3.4 H226/27','Timing and contingent milestones uncertain','Settlement receipts and milestones'],
    ['Existing debt','3200 at7.75%;500 at2.75%;1000 at1%;1025 at0%','Refinancing assumed; amortization approximate','Note10 schedule, debt covenants and committed refinancing'],
    ['Debt principal repayment','45.359 H226;100 annually;2030/31 refinance','Cash sweeps and acceleration rights simplified','Amortization table and binding refinancings'],
    ['Terminal','D&A replacement;0–2% inflation-like growth;perpetuity','Lease expiration/reletting, future costs and obsolescence','Renewal evidence and replacement engineering'],
    ['Warrants/converts','2030 warrant exercise;$0.10 proxy;intrinsic convert claims','Option time value, settlement choice and capped calls simplified','Instrument-by-instrument valuation and latest issuance register'],
    ['Lease treatment','Operating lease cash costs embedded in site costs/overhead; static ROU balances','Simplified schedules; no separately modeled lease amortization','Lease-level cash/rent schedule'],
    ['NCI','100% site cash flow less150 buyout in2029','Fixed redemption price undisclosed; no ongoing NCI income split','Executed redemption formula and contractual allocation'],
    ['Minimum cash','100 retained;restricted cash409.417 not distributed','Restricted balances could fund eligible construction; could overstate funding need','Legal release conditions and project-specific uses'],
    ['Growth options','No revenue/capex for unsigned Muskie and future deals','Understates possible platform option value','Signed customers, economics, approvals and financing'],
    ]),
    '## Challenge disposition',
    'AI skeptical review (prior wulf_peer_pe_comparison.md): remaining construction spend is weakest evidence. ACCEPTED as a material limitation; replaced the older $5.9bn estimate with an explicit $5,208.636m derivation, but qualification remains because site allocation is unverified.',
    'AI fresh-eyes final review: the earlier sensitivity report withheld all valuation; the final product permits conditional value only for funding-feasible cases and displays uncapped residuals. ACCEPTED. Human challenger name/date and exact challenge remain pending; do not attribute these observations to a classmate.']
    (ROOT/'evidence/ASSUMPTION_CHALLENGE_RECORD.md').write_text('\n\n'.join(audit),encoding='utf-8')
    print('Built visible output, statement CSV, peer results and assumption record.')

if __name__=='__main__': build()
````

---

### File: `app/cold_run.py`

````python
"""Fresh-venv, copied-bundle test, including live local HTTP behavior."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    started=datetime.now(timezone.utc).isoformat()
    testroot=Path(tempfile.mkdtemp(prefix='wulf_cold_',dir=ROOT.parent))
    bundle=testroot/'bundle';bundle.mkdir()
    shutil.copytree(ROOT/'app',bundle/'app',ignore=shutil.ignore_patterns('__pycache__'))
    for d in ['evidence','validation','outputs']:(bundle/d).mkdir()
    shutil.copy2(ROOT/'validation/AI_DIRECTIONAL_PRECOMMIT.md',bundle/'validation/AI_DIRECTIONAL_PRECOMMIT.md')
    env=dict(os.environ);env.pop('PYTHONPATH',None);env['PYTHONUTF8']='1'
    commands=[]
    def execute(args):
        proc=subprocess.run(args,cwd=bundle,env=env,capture_output=True,text=True,encoding='utf-8')
        commands.append(dict(command=args,exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
        if proc.returncode:raise RuntimeError(proc.stdout+proc.stderr)
    execute([sys.executable,'-m','venv','--without-pip',str(testroot/'venv')])
    python=testroot/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    execute([str(python),'-sE','app/validate.py'])
    execute([str(python),'-sE','app/build.py'])
    execute([str(python),'-sE','-c','import sys; print("Fresh venv:",sys.prefix != sys.base_prefix); assert sys.prefix != sys.base_prefix'])
    log=(testroot/'server.log').open('w',encoding='utf-8')
    proc=subprocess.Popen([str(python),'-sE','app/server.py','--port','8766'],cwd=bundle,env=env,stdout=log,stderr=log)
    root='http://127.0.0.1:8766';http=[]
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(root+'/api/config',timeout=2) as response: config=json.load(response)
                break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server did not start')
        with urllib.request.urlopen(root,timeout=3) as response: page=response.read().decode()
        assert 'Demonstrate funding failure' in page and 'Reset base' in page
        http.append('GET / and /api/config: 200; driver panel and base present.')
        def post(data):
            req=urllib.request.Request(root+'/api/evaluate',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
        b=post({});changed=post({'capex_multiplier':1.01});fail=post({'project_debt_limit':0});restored=post({})
        assert b['valid'] and changed['valuation']['equity_value']<b['valuation']['equity_value']
        assert not fail['valid'] and fail['valuation'] is None and restored==b
        http.append('POST base / changed capex / no funding / restored base: correct output; failure withholds valuation; reset identical.')
        try:post({'wacc':.99})
        except urllib.error.HTTPError as e:assert e.code==400
        else:raise AssertionError('Bounds endpoint did not reject')
        http.append('Out-of-bounds request returns HTTP400; raw client cannot bypass bounded controls.')
        hashes={name:hashlib.sha256((bundle/'outputs'/name).read_bytes()).hexdigest() for name in ['results.json','peer_results.json','statements.csv','VISIBLE_OUTPUT.md']}
        for name,h in hashes.items():assert hashlib.sha256((ROOT/'outputs'/name).read_bytes()).hexdigest()==h
        http.append('Generated finance outputs match main bundle byte-for-byte.')
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()
    result=dict(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),fresh_environment=str(testroot),commands=commands,http_checks=http,hashes=hashes,
                visual_status='NOT VERIFIED: no browser or in-app browser surface available in this session. HTTP behavior and delivered HTML checked; on-camera browser rehearsal still required.')
    (ROOT/'validation/cold_run_details.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Cold-run log','',f"Started UTC: {started}",f"Finished UTC: {result['finished_utc']}",f'Fresh environment: {testroot}',
           'A new venv without pip was created and an independent copy of the app was used. No imports from the original coursework directory; no external packages or online data.',
           '## Executed commands']
    lines += [f"- `{subprocess.list2cmdline(c['command'])}` — exit {c['exit_code']}" for c in commands]
    lines += ['## Results']+['- '+x for x in http]+['','## Visual verification limitation',result['visual_status'],
        '','Full actual stdout, stderr and hashes: cold_run_details.json. This is an AI-executed clean run, not a claim that the student personally performed it.']
    (ROOT/'validation/COLD_RUN_LOG.md').write_text('\n\n'.join(lines),encoding='utf-8')
    print('PASS: fresh venv; finance checks; build; HTTP base/change/failure/reset/bounds; output hashes. Browser visual QA unavailable.')

if __name__=='__main__':main()
````

---

### File: `app/freeze.py`

````python
"""Hash delivered files; verify frozen contents with --verify."""
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
def included(p):return p.is_file() and '__pycache__' not in p.parts and p.name not in ('MANIFEST.sha256',)
if '--verify' in sys.argv:
    for line in (ROOT/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        digest,relative=line.split('  ',1)
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
    print('PASS: all manifest hashes match.')
else:
    files=sorted(p for p in ROOT.rglob('*') if included(p))
    (ROOT/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files),encoding='utf-8')
    print(f'Frozen {len(files)} artifacts.')
    if '--package' in sys.argv:
        import zipfile
        with zipfile.ZipFile(ROOT.parent/'Project1_Final.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for p in files+[ROOT/'MANIFEST.sha256']:
                archive.write(p,Path(ROOT.name)/p.relative_to(ROOT))
        print('Created Project1_Final.zip')
````

---

### File: `app/prepare_documents.py`

````python
"""Prepare readable Markdown and a two-page print-layout memo, no packages."""
from pathlib import Path
import re
from build import render_md
ROOT=Path(__file__).resolve().parents[1]
OWN=['README.md','02_Edition_B.md','06_Decision_Memo.md','07_AI_USE_AND_VALIDATION.md','VIDEO_RECORDING_GUIDE.md',
     'evidence/SOURCE_REGISTER.md','evidence/PEER_POLICY.md','evidence/NORMALIZATION_AND_CONTAMINATION.md']
for name in OWN:
    p=ROOT/name;t=p.read_text(encoding='utf-8')
    t=re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Project|Video|Week)(?=\d)',r'\1 ',t)
    t=re.sub(r'(?<=[a-zA-Z])(?=\$\d)',' ',t)
    t=re.sub(r'(?<=\d),(?=20\d{2}\b)',', ',t)
    t=re.sub(r'(?<=\w)(?=\b(?:zero|net)\b)',' ',t)
    p.write_text(t,encoding='utf-8')
memo=(ROOT/'06_Decision_Memo.md').read_text(encoding='utf-8')
split=memo.index('**Value and principal sensitivities.')
def body(md):return render_md(md).split('</style>',1)[1]
pages=[memo[:split],memo[split:]]
css='''@page{size:letter;margin:0.65in}*{box-sizing:border-box}body{font:11pt Georgia,serif;color:#172e3c;margin:0;background:#e7edf0}.page{width:7.2in;min-height:9.65in;background:white;padding:0.2in;margin:20px auto;position:relative;break-after:page}.page:last-child{break-after:auto}h1{font:24pt Arial,sans-serif;color:#125e70;margin:0 0 18px}p{line-height:1.4;margin:0 0 12px}a{color:#125e70;text-decoration:none}footer{font:9pt Arial,sans-serif;color:#547080;margin-top:24px;border-top:1px solid #b8cbd1;padding-top:8px}.toolbar{text-align:center;font:14px Arial;padding:14px}@media print{body{background:white}.page{width:auto;min-height:0;margin:0;padding:0}.toolbar{display:none}}'''
out='<!doctype html><html lang="en"><meta charset="utf-8"><title>WULF committee memo — two-page print layout</title><style>'+css+'</style><div class="toolbar">Two-page memo print layout · Print / Save as PDF using Letter, default100% scale. Browser pagination has not been visually verified in this session.</div>'
for i,p in enumerate(pages,1):out+='<section class="page">'+body(p)+f'<footer>Mason Smith · TeraWulf · October19,2026 · {i}/2</footer></section>'
out+='</html>'
(ROOT/'06_Decision_Memo.html').write_text(out,encoding='utf-8')
print('Prepared Markdown and two-page memo HTML; Edition A and supplied evidence unchanged.')
````

---

### File: `app/index.html`

````html
<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TeraWulf | Committee Workbench</title>
<style>
:root{font:15px system-ui;color:#172a3a;background:#f3f5f7}*{box-sizing:border-box}body{margin:0}header{background:#102c3c;color:white;padding:25px 32px}h1{margin:4px 0;font-size:29px}h2{font-size:20px}h3{font-size:16px}small{line-height:1.5}main{display:grid;grid-template-columns:330px 1fr;gap:22px;padding:24px}aside,section{background:white;padding:20px;border:1px solid #dce2e7;border-radius:9px;margin-bottom:18px}aside{align-self:start}label{display:block;font-weight:650;margin-top:18px}input{width:100%;accent-color:#087f8c}output{float:right;color:#087f8c}button{padding:10px 13px;margin:4px;border:1px solid #9aaeb8;border-radius:5px;cursor:pointer;background:#eef5f6}button:hover{background:#d5e9eb}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{padding:18px;background:#edf4f6}.big{font-size:25px;font-weight:700}.pass{background:#e5f4ec;color:#185c39;padding:14px}.fail{background:#ffe1e2;color:#9e1525;padding:18px;font-weight:700}.warn{background:#fff3d8;color:#6b4b08;padding:14px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:right;padding:8px;border-bottom:1px solid #e0e5e9;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#edf2f5}details{margin:9px 0}summary{cursor:pointer}.muted{color:#516775}.bar{background:#118393;height:13px;min-width:1px}a{color:#087785}@media(max-width:900px){main{grid-template-columns:1fr}.cards{grid-template-columns:1fr}} </style>
<header><small>MASON SMITH · PROJECT 1 · CORPORATE FINANCE</small><h1>TeraWulf investment workbench</h1><p>Committee action: WATCH / DEFER · No position initiated</p><small>USD millions unless per share. Retrospective valuation anchor: June 30, 2026. Evidence reviewed October 19, 2026. Five years: 2027–2031 plus H2 2026 bridge.</small></header>
<main><aside><h2>Bounded driver panel</h2><p>Change a driver, then run. Accounting, sources and checks are locked.</p><button id="run">Run inputs</button><button id="reset">Reset base</button><button id="failure">Demonstrate funding failure</button><div id="controls"></div></aside><article>
<div id="status" class="warn" role="status">Loading local model…</div><section><h2>Value and liquidity</h2><div class="cards" id="cards"></div><p id="delta"></p><p class="warn">The $0 display is a limited-liability floor, not proof that traded equity is worthless. No positive residual may coexist with unmodeled growth options. Financing is assumed, not committed.</p></section>
<section><h2>Causal scenarios</h2><div id="scenarios" class="scroll"></div></section>
<section><h2>Checks that can fail</h2><p>Green means arithmetic and assumed liquidity pass; it does not verify financing availability or construction estimates.</p><div id="checks" class="scroll"></div></section>
<section><h2>Linked statements</h2><p>All changes are measured from a fresh base. Mining history is not extrapolated into HPC margins.</p><div id="statements"></div></section>
<section><h2>Enterprise → common equity</h2><div id="bridge"></div></section>
<section><h2>One-at-a-time sensitivity</h2><p>Base held constant. Bars measure absolute change in uncapped equity ($m). Infeasible endpoints are excluded from value ranking. Compare broad and narrow ranges.</p><div id="sensitivity"></div></section>
<section><h2>WACC × terminal growth</h2><p>Uncapped equity / diluted share, USD. Negative residuals remain visible.</p><div id="grid"></div></section>
<section><h2>Evidence and scope</h2><p>Primary anchor: <a href="https://investors.terawulf.com/sec-filings/all-sec-filings/content/0001083301-26-000166/wulf-20260630.htm">June 2026 10-Q</a>. Forecast lease evidence includes later announcements, so this is explicitly an ex-post valuation, not a June investment backtest. No October mark-to-market is asserted.</p><p>612.856576m valuation shares = 498.932431m basic + 77.704450m warrants + 36.219695m RSUs. Convertible principal remains debt with incremental intrinsic claims above capped-call thresholds. Restricted cash is excluded. Unsigned expansion, positive mining franchise value and tax-loss benefits are excluded.</p><p>See 02_Edition_B.md, evidence/SOURCE_REGISTER.md and 07_AI_USE_AND_VALIDATION.md for the complete review record.</p></section>
</article></main>
<script>
let config,base;const $=id=>document.getElementById(id),fmt=(x,n=1)=>x==null?'N/A':Number(x).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
function table(headers,rows){return '<table><thead><tr>'+headers.map(x=>'<th>'+x+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
function draw(r){let v=r.valuation;$('status').className=r.valid?'pass':'fail';$('status').textContent=r.valid?'CHECKS PASS — conditional on assumed funding. Historical-band warning: mature HPC margin is above the mining-era margin band.':'FAIL — funding or accounting checks broken. Valuation withheld. Funding deficit: $'+fmt(r.max_funding_gap)+'m. Reset base to recover.';
$('cards').innerHTML=[['Common share value',v?'$'+fmt(v.value_per_share,2):'WITHHELD'],['Uncapped equity',v?'$'+fmt(v.equity_value)+'m':'WITHHELD'],['Peak new borrowing','$'+fmt(r.peak_borrowing)+'m']].map(([a,b])=>'<div class="card">'+a+'<div class="big">'+b+'</div></div>').join('');
$('delta').textContent='Change versus restored base: 2031 operating profit $'+fmt(r.final_ebit-base.final_ebit)+'m; cumulative FCFF $'+fmt(r.cumulative_fcff-base.cumulative_fcff)+'m; uncapped equity '+(v?'$'+fmt(v.equity_value-base.valuation.equity_value)+'m':'not valued')+'.';
$('checks').innerHTML=table(['Period','Check','Gap / headroom','Result'],r.checks.map(c=>[c.period,c.name,fmt(c.value,6),c.passed?'PASS':'🔴 FAIL']));
$('statements').innerHTML=['income','balance','cash_flow','drivers'].map(s=>'<details '+(s==='income'?'open':'')+'><summary>'+s.replaceAll('_',' ').toUpperCase()+'</summary><div class="scroll">'+table(['USD m / stated units',...r.statements.map(x=>x.period)],Object.keys(r.statements[0][s]).map(k=>[k.replaceAll('_',' '),...r.statements.map(x=>fmt(x[s][k]))]))+'</div></details>').join('');
$('bridge').innerHTML=v?table(['Component','Value'],Object.entries(v).map(([k,x])=>[k.replaceAll('_',' '),k==='terminal_share_ev'?fmt(x*100)+'%':fmt(x,2)])):'Withheld until all checks pass.';}
async function run(){try{let p={};for(let k in config.controls)p[k]=Number($('input_'+k).value);let response=await fetch('/api/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}),r=await response.json();if(!response.ok)throw Error(r.error);draw(r)}catch(e){$('status').className='fail';$('status').textContent=e.message}}
function reset(){for(let [k,c] of Object.entries(config.controls)){$('input_'+k).value=c.base;$('out_'+k).textContent=c.base+' '+c.unit}draw(base)}
async function init(){config=await(await fetch('/api/config')).json();base=config.base;$('controls').innerHTML=Object.entries(config.controls).map(([k,c])=>'<label for="input_'+k+'">'+c.label+'<output id="out_'+k+'">'+c.base+' '+c.unit+'</output></label><input type="range" id="input_'+k+'" min="'+c.low+'" max="'+c.high+'" step="'+c.step+'" value="'+c.base+'"><small>'+c.low+'–'+c.high+' '+c.unit+'</small><details><summary>Basis · challenge · evidence</summary><small>'+c.basis+'<p>Challenge: '+c.challenge+'</p>Would change on: '+c.evidence+'</small></details>').join('');
for(let [k,c] of Object.entries(config.controls))$('input_'+k).oninput=()=>{$('out_'+k).textContent=$('input_'+k).value+' '+c.unit;$('status').
