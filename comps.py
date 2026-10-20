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
