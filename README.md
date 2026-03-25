# Transit Shock Analysis

Interactive visualization exploring how U.S. transit agencies responded to gas price shocks in 2008 and 2022, and what that implies for network resilience during the current crisis.

**[View the chart](https://kavanaraju.github.io/transit_analysis-03252026/transit_shock_analysis.html)**

## Data sources
- [FTA National Transit Database](https://www.transit.dot.gov/ntd/data-product/monthly-module-adjusted-data-release) — Monthly Module, January 2026 release
- [EIA Weekly Retail Gasoline Prices](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPMR_PTE_NUS_DPG&f=W)

## Files
- `transit_analysis.py` — data cleaning, analysis, and Plotly figure generation
- `transit_shock_analysis.html` — interactive output (open in browser)

## Run it
```bash
pip install pandas plotly openpyxl xlrd
python transit_analysis.py
```

Requires `ntd_ridership.xlsx` and `eia_gas_prices.xls` in the same directory — download links above.
