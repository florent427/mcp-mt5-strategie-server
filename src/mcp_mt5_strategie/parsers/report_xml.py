"""
Parser for MT5 Strategy Tester backtest report (XML format).

MT5 generates XML reports in <terminal_data>/Tester/Reports/ when
'Report=name' is set in tester.ini.

The XML structure (typical):
    <Report>
        <Title>Strategy Tester Report</Title>
        <Header>
            <Symbol>BTCUSD</Symbol>
            <Period>H4</Period>
            <Expert>MyEA</Expert>
            <FromDate>2024.01.01</FromDate>
            <ToDate>2025.12.31</ToDate>
        </Header>
        <Inputs>
            <Input name="Lookback" value="20" />
            ...
        </Inputs>
        <Stats>
            <NetProfit>5234.50</NetProfit>
            <ProfitFactor>1.45</ProfitFactor>
            <MaxDrawdown>1250.00</MaxDrawdown>
            <Trades>187</Trades>
            ...
        </Stats>
        <Deals>
            <Deal time="..." symbol="..." type="..." price="..." profit="..."/>
            ...
        </Deals>
        <Equity>
            <Point time="..." balance="..." equity="..."/>
            ...
        </Equity>
    </Report>

Some MT5 versions output a different XML/HTML hybrid structure;
this parser handles both with best-effort.
"""
from pathlib import Path
from typing import Any

from lxml import etree

from ._io import load_xml_root


def parse_backtest_report(path: Path | str) -> dict[str, Any]:
    """Parse a single backtest report.

    Returns:
        {
            stats: {net_profit, profit_factor, max_drawdown, trades, ...},
            trades: [{...}, ...],
            equity_curve: [{time, balance, equity}, ...],
            header: {symbol, period, expert, ...},
            inputs: {param_name: value},
        }
    """
    path = Path(path)
    if not path.exists():
        return {"error": f"Report not found: {path}"}

    # Try parsing as XML first
    try:
        return _parse_xml(path)
    except (etree.XMLSyntaxError, etree.ParseError):
        # Fallback : MT5 sometimes outputs HTML even when "report" expected
        return _parse_html(path)


def _parse_xml(path: Path) -> dict[str, Any]:
    """Parse a clean XML report. Raises XMLSyntaxError on HTML/bad content."""
    root = load_xml_root(path)
    return {
        "header": _extract_header(root),
        "inputs": _extract_inputs(root),
        "stats": _extract_stats(root),
        "trades": _extract_trades(root),
        "equity_curve": _extract_equity(root),
    }


def _parse_html(path: Path) -> dict[str, Any]:
    """Parse an HTML report (fallback)."""
    from bs4 import BeautifulSoup

    raw = path.read_text(encoding="utf-16", errors="replace")
    if "<html" not in raw.lower():
        raw = path.read_text(encoding="utf-8", errors="replace")

    soup = BeautifulSoup(raw, "html.parser")

    # MT5 HTML reports have tables for stats and trades.
    # Stats table is typically the first one.
    result = {
        "header": {},
        "inputs": {},
        "stats": _extract_html_stats(soup),
        "trades": _extract_html_trades(soup),
        "equity_curve": [],  # rarely in HTML
    }
    return result


# ============================================================
# XML extractors
# ============================================================

def _extract_header(root) -> dict:
    """Pull symbol/period/expert/dates from <Header> or attributes."""
    header = {}
    for tag in ["Symbol", "Period", "Expert", "FromDate", "ToDate",
                "Deposit", "Currency", "Leverage", "Spread"]:
        node = root.find(f".//{tag}")
        if node is not None and node.text:
            header[tag.lower()] = node.text.strip()
    return header


def _extract_inputs(root) -> dict:
    """Extract <Input name=... value=.../> elements."""
    inputs = {}
    for node in root.findall(".//Input"):
        name = node.get("name") or node.get("Name")
        value = node.get("value") or node.get("Value")
        if name:
            try:
                inputs[name] = float(value) if value else None
            except (TypeError, ValueError):
                inputs[name] = value
    return inputs


def _extract_stats(root) -> dict:
    """Extract performance statistics."""
    stats_map = {
        "NetProfit": "net_profit",
        "GrossProfit": "gross_profit",
        "GrossLoss": "gross_loss",
        "ProfitFactor": "profit_factor",
        "ExpectedPayoff": "expected_payoff",
        "RecoveryFactor": "recovery_factor",
        "SharpeRatio": "sharpe_ratio",
        "MaxDrawdown": "max_drawdown",
        "MaxDrawdownPercent": "max_drawdown_pct",
        "RelativeDrawdown": "relative_drawdown",
        "Trades": "trades",
        "WinTrades": "win_trades",
        "LossTrades": "loss_trades",
        "WinRate": "winrate",
        "AverageWin": "avg_win",
        "AverageLoss": "avg_loss",
        "LargestWin": "largest_win",
        "LargestLoss": "largest_loss",
        "MaxConsecutiveWins": "max_consec_wins",
        "MaxConsecutiveLosses": "max_consec_losses",
    }
    stats = {}
    for xml_tag, key in stats_map.items():
        node = root.find(f".//{xml_tag}")
        if node is not None and node.text:
            try:
                stats[key] = float(node.text.strip().replace(",", ""))
            except ValueError:
                stats[key] = node.text.strip()
    return stats


def _extract_trades(root) -> list[dict]:
    """Extract individual deal records."""
    trades = []
    for deal in root.findall(".//Deal"):
        trade = {}
        for attr in ["time", "symbol", "type", "volume", "price", "profit",
                     "commission", "swap", "comment", "ticket"]:
            v = deal.get(attr) or deal.get(attr.capitalize())
            if v:
                trade[attr] = v
        if trade:
            trades.append(trade)
    return trades


def _extract_equity(root) -> list[dict]:
    """Extract equity curve points."""
    points = []
    for pt in root.findall(".//Point"):
        p = {}
        for attr in ["time", "balance", "equity"]:
            v = pt.get(attr) or pt.get(attr.capitalize())
            if v:
                try:
                    p[attr] = float(v) if attr != "time" else v
                except ValueError:
                    p[attr] = v
        if p:
            points.append(p)
    return points


# ============================================================
# HTML extractors (fallback)
# ============================================================

def _extract_html_stats(soup) -> dict:
    """Extract stats from MT5's HTML report."""
    stats = {}
    # MT5 HTML has rows like : <tr><td>Total Net Profit:</td><td>5234.50</td></tr>
    label_map = {
        "total net profit": "net_profit",
        "gross profit": "gross_profit",
        "gross loss": "gross_loss",
        "profit factor": "profit_factor",
        "expected payoff": "expected_payoff",
        "recovery factor": "recovery_factor",
        "sharpe ratio": "sharpe_ratio",
        "balance drawdown maximal": "max_drawdown",
        "balance drawdown maximal %": "max_drawdown_pct",
        "total trades": "trades",
        "profit trades": "win_trades",
        "loss trades": "loss_trades",
    }
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).lower().rstrip(":")
        value = cells[1].get_text(strip=True)
        if label in label_map:
            try:
                stats[label_map[label]] = float(value.replace(" ", "").replace(",", ""))
            except ValueError:
                stats[label_map[label]] = value
    return stats


def _extract_html_trades(soup) -> list[dict]:
    """Best-effort extraction of trades table from HTML."""
    # MT5 HTML trade table has header row with "Time", "Type", "Symbol", etc.
    trades = []
    # Find table containing "Time" header
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not headers and table.find_all("tr"):
            # Sometimes headers in <td> of first row
            first_row = table.find("tr")
            headers = [td.get_text(strip=True).lower() for td in first_row.find_all("td")]
        if "time" in headers and ("type" in headers or "symbol" in headers):
            for row in table.find_all("tr")[1:]:  # skip header
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= len(headers):
                    trades.append(dict(zip(headers, cells)))
            break
    return trades
