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
    'Favorable / operating execution (10% WACC)':dict(capex_multiplier=.9,rent_multiplier=1.05,mature_margin=.85,wacc=.10),
    'Favorable / improved financing (9% WACC)':dict(capex_multiplier=.9,rent_multiplier=1.05,mature_margin=.85,wacc=.09),
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
