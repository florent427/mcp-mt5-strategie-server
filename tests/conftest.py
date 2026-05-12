"""
Pytest fixtures — synthetic MT5 reports for parser tests.

The XML/HTML formats used here are based on observed MT5 build 4400+ output;
parsers tolerate variations so these only need to be close, not byte-identical.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ============================================================
# XML samples
# ============================================================

BACKTEST_XML_SAMPLE = """<?xml version="1.0" encoding="utf-16"?>
<Report>
  <Header>
    <Symbol>BTCUSD</Symbol>
    <Period>M5</Period>
    <Expert>FibEA</Expert>
    <FromDate>2025.01.01</FromDate>
    <ToDate>2025.06.01</ToDate>
    <Deposit>100000</Deposit>
    <Currency>USD</Currency>
    <Leverage>100</Leverage>
  </Header>
  <Inputs>
    <Input name="Lookback" value="20"/>
    <Input name="FibLevel" value="0.9"/>
    <Input name="LotSize" value="0.1"/>
  </Inputs>
  <Stats>
    <NetProfit>5234.50</NetProfit>
    <GrossProfit>12500.00</GrossProfit>
    <GrossLoss>-7265.50</GrossLoss>
    <ProfitFactor>1.72</ProfitFactor>
    <ExpectedPayoff>27.99</ExpectedPayoff>
    <RecoveryFactor>4.19</RecoveryFactor>
    <SharpeRatio>1.43</SharpeRatio>
    <MaxDrawdown>1250.00</MaxDrawdown>
    <MaxDrawdownPercent>1.25</MaxDrawdownPercent>
    <Trades>187</Trades>
    <WinTrades>102</WinTrades>
    <LossTrades>85</LossTrades>
    <WinRate>54.55</WinRate>
  </Stats>
  <Deals>
    <Deal time="2025.01.02 09:30:00" symbol="BTCUSD" type="buy" volume="0.1" price="42100.50" profit="125.30" ticket="100001"/>
    <Deal time="2025.01.02 14:15:00" symbol="BTCUSD" type="sell" volume="0.1" price="42250.20" profit="0" ticket="100002"/>
    <Deal time="2025.01.03 10:05:00" symbol="BTCUSD" type="buy" volume="0.1" price="42010.00" profit="-45.80" ticket="100003"/>
  </Deals>
  <Equity>
    <Point time="2025.01.01 00:00:00" balance="100000.00" equity="100000.00"/>
    <Point time="2025.01.02 14:15:00" balance="100125.30" equity="100125.30"/>
    <Point time="2025.01.03 10:30:00" balance="100079.50" equity="100079.50"/>
  </Equity>
</Report>
"""

OPTIMIZATION_XML_SAMPLE = """<?xml version="1.0" encoding="utf-16"?>
<OptimizationResult>
  <Header>
    <Symbol>BTCUSD</Symbol>
    <Expert>FibEA</Expert>
  </Header>
  <Pass id="1">
    <Inputs>
      <Input name="Lookback" value="10"/>
      <Input name="FibLevel" value="0.9"/>
    </Inputs>
    <Stats>
      <NetProfit>1200.00</NetProfit>
      <ProfitFactor>1.15</ProfitFactor>
      <SharpeRatio>0.85</SharpeRatio>
      <MaxDrawdown>800.00</MaxDrawdown>
      <Trades>250</Trades>
    </Stats>
  </Pass>
  <Pass id="2">
    <Inputs>
      <Input name="Lookback" value="20"/>
      <Input name="FibLevel" value="0.9"/>
    </Inputs>
    <Stats>
      <NetProfit>5234.50</NetProfit>
      <ProfitFactor>1.72</ProfitFactor>
      <SharpeRatio>1.43</SharpeRatio>
      <MaxDrawdown>1250.00</MaxDrawdown>
      <Trades>187</Trades>
    </Stats>
  </Pass>
  <Pass id="3">
    <Inputs>
      <Input name="Lookback" value="50"/>
      <Input name="FibLevel" value="0.9"/>
    </Inputs>
    <Stats>
      <NetProfit>3100.00</NetProfit>
      <ProfitFactor>1.45</ProfitFactor>
      <SharpeRatio>1.10</SharpeRatio>
      <MaxDrawdown>950.00</MaxDrawdown>
      <Trades>95</Trades>
    </Stats>
  </Pass>
</OptimizationResult>
"""

BACKTEST_HTML_SAMPLE = """<html>
<head><title>Strategy Tester Report</title></head>
<body>
<table>
<tr><td>Total Net Profit:</td><td>5234.50</td></tr>
<tr><td>Gross Profit:</td><td>12500.00</td></tr>
<tr><td>Gross Loss:</td><td>-7265.50</td></tr>
<tr><td>Profit Factor:</td><td>1.72</td></tr>
<tr><td>Expected Payoff:</td><td>27.99</td></tr>
<tr><td>Sharpe Ratio:</td><td>1.43</td></tr>
<tr><td>Balance Drawdown Maximal:</td><td>1250.00</td></tr>
<tr><td>Total Trades:</td><td>187</td></tr>
<tr><td>Profit Trades:</td><td>102</td></tr>
<tr><td>Loss Trades:</td><td>85</td></tr>
</table>
</body>
</html>
"""


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def xml_report(tmp_path: Path) -> Path:
    p = tmp_path / "FibEA_report.xml"
    # MT5 writes UTF-16-LE with BOM
    p.write_bytes(b"\xff\xfe" + BACKTEST_XML_SAMPLE.encode("utf-16-le"))
    return p


@pytest.fixture
def xml_report_utf8(tmp_path: Path) -> Path:
    """Some MT5 builds use UTF-8; parser should handle both."""
    p = tmp_path / "FibEA_report.xml"
    p.write_text(BACKTEST_XML_SAMPLE, encoding="utf-8")
    return p


@pytest.fixture
def opt_report(tmp_path: Path) -> Path:
    p = tmp_path / "FibEA_opt.xml"
    p.write_bytes(b"\xff\xfe" + OPTIMIZATION_XML_SAMPLE.encode("utf-16-le"))
    return p


@pytest.fixture
def html_report(tmp_path: Path) -> Path:
    p = tmp_path / "FibEA_report.html"
    p.write_bytes(b"\xff\xfe" + BACKTEST_HTML_SAMPLE.encode("utf-16-le"))
    return p


@pytest.fixture
def missing_report(tmp_path: Path) -> Path:
    return tmp_path / "does_not_exist.xml"


# MT5 actually writes its HTML reports as UTF-16-LE with BOM and the labels
# are localized per the broker's server. This fixture mirrors the real format
# seen with FTMO (French locale) — multi-cell rows, accented labels,
# non-breaking-space thousand separators, "value (pct%)" inside cells.
FRENCH_HTML_SAMPLE = """<html>
<body>
<table>
<tr><td>Rapport du Testeur de Strategie</td></tr>
<tr><td>FTMO-Server4 (Build 5833)</td></tr>
<tr><td>Reglages</td></tr>
<tr><td>Expert:</td><td>fib_090_ea</td></tr>
<tr><td>Symbole:</td><td>BTCUSD</td></tr>
<tr><td>Periode:</td><td>M5 (2025.01.02 - 2025.01.09)</td></tr>
<tr><td>Placement:</td><td>Lookback=20</td></tr>
<tr><td>FibLevel=0.9</td></tr>
<tr><td>LongOnly=true</td></tr>
<tr><td>Courtier:</td><td>FTMO Global Markets Ltd</td></tr>
<tr><td>Devise:</td><td>USD</td></tr>
<tr><td>Depot initial:</td><td>100 000.00</td></tr>
<tr><td>Resultats</td></tr>
<tr><td>Profit Total Net:</td><td>-1 558.07</td><td>Solde Drawdown Maximal:</td><td>1 748.89 (1.75%)</td></tr>
<tr><td>Profit brut:</td><td>1 529.16</td><td>Perte brut:</td><td>-3 087.23</td></tr>
<tr><td>Facteur de profit:</td><td>0.50</td><td>Remboursement attendu:</td><td>-6.28</td></tr>
<tr><td>Facteur de recuperation:</td><td>-0.88</td><td>Ratio de Sharpe:</td><td>-5.00</td></tr>
<tr><td>Nb trades:</td><td>248</td><td>Operations au Total:</td><td>496</td></tr>
</table>
</body>
</html>
"""


@pytest.fixture
def french_html_report(tmp_path: Path) -> Path:
    p = tmp_path / "fib_090_ea_report.htm"
    p.write_bytes(b"\xff\xfe" + FRENCH_HTML_SAMPLE.encode("utf-16-le"))
    return p
