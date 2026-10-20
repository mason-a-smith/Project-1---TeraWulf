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
    'The three staged favorable cases share 10% lower remaining capex, 5% higher rent realization and 85% mature site margin. They hold WACC at 10%, 9% and 8%, respectively; each remains conditional, not probability-weighted. Base: 80% mature margin and 10% WACC. Low: 20% cost overrun, 5% lower rent, 75% mature margin and 12% WACC. Early ramp margins remain 60% / 75% in every case. This explains the difference from the older $2.80 high case.',
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
