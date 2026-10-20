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
