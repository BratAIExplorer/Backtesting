# Disposition effect and retail trading frequency: academic evidence

Verification key: [V-PDF] = number read directly from the paper PDF text. [V-ABS] = from the paper abstract/author page. [SEC] = secondary source only. Anything not marked or listed under Gaps was not found. Where a table was garbled by PDF extraction, I say so.

## 1. Odean (1998): PGR vs PLR and what happened afterwards

### Takeaway
Retail investors realized gains at about 1.5x the rate they realized losses (PGR 14.8% vs PLR 9.8%), except in December. The winners they sold then beat the losers they kept by about 3.4 percentage points over the next year.

### Cited Findings
- Source: Odean, T. (1998), "Are Investors Reluctant to Realize Their Losses?", Journal of Finance 53(5), 1775-1798. [Paper PDF](https://faculty.haas.berkeley.edu/odean/papers/disposition/disposit.pdf); [abstract page](https://faculty.haas.berkeley.edu/odean/papers/disposition/disposition.html) [V-PDF]
- Data: 10,000 accounts at a large US discount brokerage, trades 1987-1993. Average equity turnover in these accounts is 6.5% per month, about a 15-month holding period (footnote 11). [V-PDF]
- Table I counts, whole year: 13,883 realized gains, 79,658 paper gains, 11,930 realized losses, 110,348 paper losses. [V-PDF]
  - PGR = 13,883 / (13,883 + 79,658) = 0.148. PLR = 11,930 / (11,930 + 110,348) = 0.098. Difference 0.050, t = 35 (hypothesis PGR = PLR rejected). I computed the ratios from the printed counts; they match the 0.148 / 0.098 / 0.050 printed in the garbled table.
  - December counts: 866 realized gains, 7,131 paper gains, 1,555 realized losses, 10,604 paper losses. PGR = 0.108, PLR = 0.128 (computed). The reversal in December is tax-loss selling; difference -0.020, t = 4.3 in magnitude. [V-PDF]
  - Jan-Nov: PGR 0.152, PLR 0.094, difference 0.058, t = 38 (consistent with computing from counts). [V-PDF]
- Account-level test: average account PGR 0.57, average account PLR 0.36, average difference 0.21, t = 19. Note this is a different weighting from the aggregate figures. [V-PDF]
- Ex-post returns, Table VI (excess return over the CRSP value-weighted index; winners sold vs paper losers not sold). The PDF table was garbled, so I reconstructed it from the printed rows and the text. [V-PDF, partly reconstructed]
  - 84 trading days: winners sold +0.47%, losers held -0.56%, difference 1.03% (p = 0.002).
  - 252 trading days (about 1 year): winners sold +2.35%, losers held -1.06%, difference 3.41% (p = 0.001). The text states "3.4 percent". The worked example in the paper says losers held return about 1% below the market and winners sold about 2.4% above it over one year.
  - 504 trading days: printed difference 3.58% (p = 0.014). The signs of the two components are unreadable in my extraction; do not quote the 504-day components.
- Tax cost: the paper's abstract says that for taxable investments the behavior is suboptimal and leads to lower after-tax returns. The paper's worked example assumes a 15% marginal rate and gives up an immediate tax saving of $130 per $1,000 sale. [V-PDF]
- Odean links the winners' persistence to price momentum (Jegadeesh and Titman 1993). [V-PDF]

### Inferences
- Selling winners early cost this sample roughly 3.4 percentage points a year relative to holding the loser instead, before tax. Momentum, which has since weakened in some samples, is the likely reason the sign was this strong.
- The effect is a 1.5x ratio, not "everyone holds losers". About 85% of paper gains were also not realized on any given day.

### Gaps
- I did not verify the 504-day components. I did not reproduce the exact t-stat for 84 days.

## 2. Barber and Odean (2000): active vs inactive households

### Takeaway
The most active quintile earned 11.4% net a year against 18.5% for the least active, with nearly identical gross returns (18.7% vs 18.5%). So the gap was cost and bad timing of trades, not stock-picking alone.

### Cited Findings
- Source: Barber, B. and Odean, T. (2000), "Trading Is Hazardous to Your Wealth: The Common Stock Investment Performance of Individual Investors", Journal of Finance 55(2), 773-806. [Paper PDF](https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf) [V-PDF] (I read the Journal of Finance printed version of the paper; it carries the "VOL. LV, NO. 2, APRIL 2000" header).
- Sample: 66,465 households at a large discount broker (Charles Schwab per an SEC comment letter, [SEC]), 1991-1996. [V-PDF] The abstract also says "Of 66,465 households". An alternate project page says "over 60,000". [SEC]
- Abstract numbers: heaviest traders earned 11.4% a year; the market returned 17.9%; the average household 16.4%. The average household turns over 75% of its portfolio a year. [V-PDF]
- Quintile results (turnover): [V-PDF]
  - Mean monthly turnover by quintile: 0.19%, 1.24%, 2.89%, 5.98%, 21.49% (low to high).
  - Gross annualized return: quintile 1 18.7%, quintile 2 18.5%, so gross differences across quintiles are small.
  - Net annualized geometric return: high-turnover quintile 11.4%, low-turnover quintile 18.5%. Gap about 7.1 percentage points.
  - The text says high turnover costs them 57 basis points a month (6.8% a year) relative to low-turnover households.
  - Raw monthly gross returns by quintile: 1.483, 1.472, 1.489, 1.511, 1.548 (percent), so high-turnover households were slightly higher gross.
- The Berkeley author page summary quotes different average-household figures (15.3% net, 17.7% gross, market 17.1%, top 20% at 10.0%), which conflict with the paper's abstract (16.4% net, market 17.9%, top 20% 11.4%). Use the paper PDF figures only. [conflict noted]
- Criticism: Bonaparte and Cooper (NBER WP 16022) argue a rational model with adjustment costs can mimic these patterns. [NBER](https://www.nber.org/papers/w16022.pdf) [V-PDF]

### Inferences
- The cost gap is large for a retail account but is for a 1991-96 US broker with high commissions. Modern costs are lower, so the gap in that sample overstates modern cost drag; the timing and selection effect may remain.

### Gaps
- The most active households' gross return and the exact cost split per quintile: I did not read these tables fully. The net-minus-gross cost for quintile 5 is not stated in my notes.

## 3. Taiwan day traders: Barber, Lee, Liu, Odean

### Takeaway
Under 1% of Taiwanese day traders could be predicted to earn positive abnormal returns net of fees. In aggregate, day trading lost money in 14 of 15 years studied.

### Cited Findings
- Source A: Barber, B., Lee, Y.-T., Liu, Y.-J., Odean, T. (2014), "The Cross-Section of Speculator Skill: Evidence from Day Trading", Journal of Financial Markets 18, 1-24. [IDEAS](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html); [eScholarship](https://www.escholarship.org/uc/item/7k75v0qx) [SEC] (numbers taken from a search summary of the abstract; I did not open the abstract text itself)
  - "Less than 1%" of the day trader population can predictably and reliably earn positive abnormal returns net of fees. [SEC]
  - Top 500 day traders ranked in one year earned 61.3 bps/day before fees and 37.9 bps/day after fees the next year. Bottom-ranked group: -11.5 bps before fees, -28.9 bps after. [SEC] (Earlier drafts gave different numbers: 49.5/28.1 and -17.5/-34.2; use only the published ones.)
- Source B: Barber, Lee, Liu, Odean, Zhang, "Do Day Traders Rationally Learn About Their Ability?" (October 2017 draft, later retitled "Learning Fast or Slow"). [PDF](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/day%20trading%20and%20learning%20110217.pdf) [V-PDF]
  - Taiwan, 1992-2006, complete market data. Aggregate day-trader performance net of fees is negative in each of the 15 years studied (the same paper's Table 1 text says reliably negative gross and net performance in all years but 1992, so "each of the 15 years" is in the intro and "all years but 1992" is in the results; these two statements are not identical).
  - Average day trader loses 7 bps/day gross (t = -10.2); costs more than triple the loss to 23.9 bps/day net. Net assumes 10 bps round-trip commission and 30 bps transaction tax on sales.
  - More than 75% of all day traders quit within two years.
  - Experienced traders (50+ days) who were previously unprofitable have a 95.3% chance of day trading again in the next 12 months; previously profitable ones 96.4%.
  - Profitable (positive lifetime intraday profit, 10+ days of experience) day traders are consistently about 5% of day traders in 1995-2006; unprofitable day traders account for 72% of day-trading volume overall, about 80% in the last several years.
  - Individuals are over 99% of day traders.
- Older paper (secondary only): about 1% of individual investors account for 50% of day trading volume. [SEC; Barber, Lee, Liu, Odean 2004 working paper, not verified]

### Inferences
- "About 5% are profitable at a point in time" and "under 1% are predictably profitable" are consistent: most of the 5% are luck. Use the 1% figure for persistent skill, and note it is the published abstract.

### Gaps
- I did not open the published 2014 abstract directly; "less than 1%" and the bps figures come via a search summary. The "profitable share persists" sentence in the task was not found as stated in the other draft.

## 4. Indian-market evidence

### Takeaway
There is a small Indian literature confirming the disposition effect, but the evidence I could read is a very small sample. SEBI's own data show most retail F&O traders lose; that is not a disposition-effect study.

### Cited Findings
- Prasad, H. and Mohta, B. (2012), "Are Professional and Individual Investors Equally Prone to Disposition Effect? Evidence from Indian Stock Market", Great Lakes Herald 6(2). [PDF](https://www.greatlakes.edu.in/pdf/Herald/Vol6/sep2012_v6_c5.pdf) [V-PDF]
  - One Indian brokerage, 2011, Nifty-50 stocks only, 295 investors (165 individual, 130 professional), 590 round trips (330 individual, 260 professional).
  - Average losing round trip lasted 89.67 days (individuals) and 70.55 days (professionals); winning round trips lasted 41.28 and 52.07 days. Losers held significantly longer than winners in both groups. Professional investors showed a smaller effect.
  - Weaknesses: tiny sample, one year, one broker, duration test rather than PGR/PLR, and it is a lower-tier outlet. Treat as weak evidence.
- Bharandev and Rao, "Disposition effect at the market level: evidence from Indian stock market", Review of Behavioral Finance (2019/2020). [DOI](https://doi.org/10.1108/rbf-12-2018-0132) [SEC] (abstract summary only)
  - NSE500 stocks; abnormal trading volume rose with the share of winning days but not with losing days.
- Campbell, Ramadorai, Ranish (2014), "Getting Better or Feeling Better? How Equity Investors Respond to Investment Experience", NBER WP 20000. [NBER](https://www.nber.org/papers/w20000) [SEC]
  - Uses a large sample of Indian retail equity accounts (data from NSDL and SEBI); experienced investors show lower turnover and a smaller disposition effect. I did not confirm the data are NSE-specific and did not get a number.
- Arora and Rajendran (2023), Journal of Risk and Financial Management 16(8):349. [IDEAS](https://ideas.repec.org/a/gam/jjrfmx/v16y2023i8p349-d1202405.html) [SEC]: disposition effect and anchoring among Indian individual investors; stronger in volatile markets; associated with lower portfolio performance.
- SEBI, September 2024 study of equity F&O, FY22-FY24: 93% of more than 1 crore individual traders lost money; average loss about Rs 2 lakh each (including costs); aggregate losses over Rs 1.8 lakh crore; only 7.2% made a profit, and 1% made more than Rs 1 lakh. [SEBI press release](https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html) [SEC; page located, full text not opened]. An earlier SEBI report found 89% of individual F&O traders lost in FY22 [SEC].

### Inferences
- Directionally the Indian evidence matches Odean, but I found no Indian PGR/PLR figure from a large NSE/BSE retail dataset. Do not claim an Indian PGR/PLR number.

### Gaps
- No large-sample NSE/BSE PGR vs PLR numbers found. The ISB retail study (Business Standard, 2.02 million investors) returned HTTP 403, so its numbers are unverified.
- SEBI's cash-segment and intraday studies were not retrieved.

## 5. Stop-losses and profit targets: do they help?

### Takeaway
Theory and the one rigorous study I verified say a stop-loss only adds value when returns are positively autocorrelated (momentum); under a random walk it lowers expected return.

### Cited Findings
- Kaminski, K. and Lo, A. (2014), "When Do Stop-Loss Rules Stop Losses?", Journal of Financial Markets 18, 234-254 (online July 2013). [MIT DSpace](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee) [V-ABS]
  - Abstract: "at longer sampling frequencies, certain stop-loss policies can increase expected return while substantially reducing volatility" (tested on a buy-and-hold strategy with daily index futures).
  - Under the random walk hypothesis, simple stop-loss rules always decrease expected return; with momentum they can add value. [SEC, search summary of the paper]
  - A U.S. equity test using monthly returns 1950-2004 with long-term government bonds as the stop-out asset: certain rules add 50-100 bps per month during stop-out periods. [SEC; not verified in the paper]
- No academic source found for profit targets on average. Not located.

### Inferences
- For the Backtesting project: a stop-loss helps only if the strategy has or sits in a momentum regime. Test with and without stops on the same data.

### Gaps
- No verified evidence on profit targets. I could not verify the 50-100 bps figure in the paper itself. Blog claims of a 10% rule were not used.
