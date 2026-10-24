# Where money is moving → sectors → stocks (19 Oct 2026)

Research starting point, not advice. Prices: Yahoo, 19 Oct 2026 (`analysis/market_sector_momentum.csv`).
Stock health: Fortress-rule screen (`analysis/us_scan_screen.csv`, `us_scan_in_screen.csv`), today's numbers, not backtested.

## What I checked vs what I'm assuming
- CHECKED: price trend vs world (ACWI) for 10 markets, 11 US sectors, 7 themes, 4 India sector indices.
- CHECKED (secondary sources, not NSDL/TIC directly): India FPI selling; US Sept sector ETF flows.
- NOT AVAILABLE: ETF share-count flows (Yahoo returned none); 6 India sector indices (Auto, FMCG, Energy,
  Metal, Realty, FinSvcs); Oct 12-19 market headlines; Europe/Japan/Taiwan investor-flow data.
- Stock level now covers: US (S&P 1500), India (Nifty 500), Taiwan (Taiwan 50), Japan (JPX-Nikkei 400),
  Europe (Euro Stoxx 50 + FTSE 100 + DAX + CAC 40, 195 names). Large caps only for TW/JP/EU.
  NOT covered at stock level: Korea, China, Malaysia (ETF level only).
- Japan list is quality-screened by the index (ROE), so it is biased toward healthy names. Taiwan 50 and the
  European lists are current members only (survivorship bias).

## Markets (3-month return vs world, above 200-day average?)
| Market | 3m vs world | Trend |
|---|---|---|
| Taiwan EWT | +8.7 | up |
| Japan EWJ / DXJ | +2.8 / +2.2 | up |
| US SPY | +1.0 | up |
| Europe VGK | -2.3 | up (weak) |
| Emerging EEM | -3.2 | down |
| India INDA | -3.9 | down |
| Malaysia EWM | -7.1 | down |
| China MCHI | -7.4 | down |
| S.Korea EWY | -9.7 (1m: -17.5%) | down |

## Flow evidence
- India: FPIs sold ~₹3.08T in first 9 months of 2026 (Angel One); Sept -₹35,861 cr (newsonair);
  Oct headline >₹47,000 cr (body not read). DIIs buying 36 months in a row. Sept FPI selling: financials,
  oil & gas, autos; buying: consumer services, services, healthcare (Finnovate blog, secondary).
- US Sept sector ETF inflows (FactSet): Utilities, Financials, Comm Svcs. Outflows: Energy, Industrials,
  Staples, Materials. No dollar amounts read.
- Drivers named in sources: US-Iran conflict, crude ~$100+, US 10Y ~5%.

## Where price and flow agree
| Area | Price | Flow | Read |
|---|---|---|---|
| India IT | +8% 1m, above 200d | n/a | Strong; DII/price led |
| India Healthcare/Pharma | +14% 6m, above 200d | FPI buying (Sept) | Agrees |
| India Banks/Nifty | down, below 200d | FPI selling | Agrees: avoid for now |
| US Health Care | +9.3 vs world 3m | n/a | Strong |
| US Energy | +16.4 vs world 3m | ETF OUTFLOWS Sept | DISAGREES: oil-shock price move, flows leaving |
| US Tech | +2.4 3m, +13.9 6m | Sept weekly inflows | Agrees, but 1m -2.3% |
| US Utilities | -7.5 3m | Sept inflows | Disagrees: flows in, price weak |
| Gold GLD | 3m +1.8, 6m -19.5, BELOW 200d | CB buying (WGC) | Flow yes, price trend NO |
| Gold miners GDX | 3m +21.9, 1m -7.5, below 200d | CB buying | Mixed |
| Semis SMH | above 200d, 3m -5.5 vs world | AI earnings | Mixed |
| Smart grid GRID | below 200d, 6m -12 vs world | n/a | Price gate FAILS |

Gemini graded GLD and GRID "Grade A / price trend pass". Yahoo data shows both below their 200-day average.

## Stocks to research (health score 4-5, uptrend) in sectors where price and flow agree
US Health Care: EXEL (5), REGN (5), RMD (4), MEDP (4, P/E 36), CRVL (4)
US Tech: MSFT (4, P/E 29), CRM (4, P/E 22), CTSH (4, P/E 14)
India IT: PERSISTENT (4, P/E 51), MPHASIS (4, P/E 25), TECHM (3)
India Healthcare: none passed the buy flag in this screen
US Energy (price strong, flows leaving, oil-shock risk): EOG, COP, INSW, VLO, APA, PBF
Taiwan: TSM (from Gemini file; not screened here)

## Taiwan, Japan, Europe screens (same health rules, uptrend required; run 19 Oct 2026)
Company names added from memory from the tickers; check before use.
- Taiwan (24 of 50 pass; Taiwan is the strongest market on price, +8.7 vs world 3m):
  2615 Wan Hai (5), 3017 AVC (4, P/E 45), 2379 Realtek (4), 3034 Novatek (4), 3008 Largan (4), 2603 Evergreen (4).
  Mix of tech and shipping. TSMC (2330) scores 5/5 on health but is NOT in an uptrend, so it fails the buy flag (consistent with Gemini's "wait for confirmation").
- Japan (125 of 400 pass; Japan up on price, DXJ hedged is the cleaner route):
  4194 Visional (5), 4021 Nissan Chemical (5), 4503 Astellas (5), 9766 Konami (5), 2914 JT (5), 4578 Otsuka (5),
  7740 Tamron (5), 6448 Brother (5). Passers lean Industrials (39) and Technology (25).
- Europe (46 of 195 pass; Europe lags the world on price, -2.3 vs world 3m, so lowest priority):
  EXPN Experian (4), G24 Scout24 (4), DPLM Diploma (4, P/E 55), DSY Dassault (4), TTE TotalEnergies (4),
  SHEL Shell (4). Energy and Industrials lead.
Full lists: `analysis/us_scan_tw_screen.csv`, `us_scan_jp_screen.csv`, `us_scan_eu_screen.csv`.

## Flow verification (19 Oct 2026)
| Claim | Result |
|---|---|
| TIC Aug 2026: total net inflow $199.8B | VERIFIED, Treasury sb0662 (16 Oct 2026) |
| Foreign net buying US equities $153.9B (private 131.9 + official 22.0); 12M $1,009.6B | VERIFIED, same release |
| Official T-bill sales -$42.2B (all foreigners -$47.8B) | VERIFIED |
| Net long-term inflow $300.7B (Gemini) | DIFFERS: Treasury shows $279.2B "after adjustments". $300.7B not found. |
| Gold Aug 2026 +39t, YTD +170t | VERIFIED, WGC (6 Oct 2026). Aug buyers: China 20t, Uzbekistan 8t, Poland 8t, Kazakhstan 7t. |
| Gemini "Poland +98t, China +80t YTD" | NOT CHECKED (only August split read) |
| India FPI Sept -₹35,861 cr | Arithmetic checks (45,537 sold on exchanges - 9,676 primary). Source is news citing "depository data", NSDL not named. NOT primary-verified. |
| India FPI Oct 1-12: -₹47,417 cr; 2026 YTD -₹3.08T (₹3.64T secondary-market sales per NSDL, less ₹56,485 cr primary inflows) | Consistent with each other; secondary source (Angel One). NOT primary-verified. |
| NSDL site | Could not connect (connection reset, two URLs). Check fpi.nsdl.co.in by hand. |
Overall: the US/gold flow numbers hold up. India flow numbers look right but rest on news reports.
One Gemini number is off ($300.7B) and one is unchecked (Poland/China YTD).

## Malaysia: data centres, chips, power (hand-picked 24 Bursa names, 19 Oct 2026)
Story evidence: Tenaga reports power deals for 59 data centres (~8.3GW, 68% in Johor, 5-year take-or-pay) per analyst
notes, not Tenaga filings. One report claims ~28% Johor vacancy and stalled projects (conflicts; weak source).
Stock evidence (health score, uptrend flag, price change 3m/6m):
- Only 1 of 24 passes health + uptrend: Pentamaster 7160 (score 2, +12% / +58%).
- Chips: price very strong 6m (ViTrox +128%, Inari +77%, Pentamaster +58%, Unisem +41%, MPI +33%) but fundamentals
  weak or expensive (P/E 42-104; Inari revenue -6%, Greatech revenue -10%). Frontken best health (4) but below trend.
- Power: Tenaga score 2, below trend, -7% 3m (price NOT confirming the data-centre story). YTL Power +25% 3m
  and Solarvest +34% 3m but health 1 (Solarvest P/E 44). Petronas Gas 3, flat.
- Infra: Gamuda in uptrend (+15% 3m) but health 1. Press Metal health 5 but falling (-16% 3m).
- Telco/DC: TM and TIME dotCom health 4 but not in uptrend.
Read: strong story, but most stocks are expensive or not trending. Malaysia ETF (EWM) is below its 200-day average
and foreigners are net sellers of Bursa. Ticker 5336 resolved to "CKI", not the company I intended; ignore it.
Company names come from Yahoo; the list was hand-picked, so it can miss names. `analysis/us_scan_my_screen.csv`.

## Next steps
1. Open fpi.nsdl.co.in yourself (it blocked my fetch) to confirm the India FPI figures.
2. Add stock universes for Taiwan/Japan/Europe if those markets stay on top.
3. Add flows data (ETF share counts) via a source that works; Yahoo returned none.
