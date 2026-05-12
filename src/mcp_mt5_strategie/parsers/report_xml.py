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
    """Parse an HTML report — MT5 writes these as UTF-16-LE with BOM."""
    from bs4 import BeautifulSoup

    data = path.read_bytes()
    if data.startswith(b"\xff\xfe"):
        raw = data[2:].decode("utf-16-le", errors="replace")
    elif data.startswith(b"\xfe\xff"):
        raw = data[2:].decode("utf-16-be", errors="replace")
    elif data.startswith(b"\xef\xbb\xbf"):
        raw = data[3:].decode("utf-8", errors="replace")
    else:
        try:
            raw = data.decode("utf-16-le")
            if "<html" not in raw.lower():
                raise UnicodeDecodeError("utf-16-le", b"", 0, 0, "no html tag")
        except (UnicodeDecodeError, LookupError):
            raw = data.decode("utf-8", errors="replace")

    soup = BeautifulSoup(raw, "html.parser")

    header, inputs = _extract_html_header_inputs(soup)
    return {
        "header": header,
        "inputs": inputs,
        "stats": _extract_html_stats(soup),
        "trades": _extract_html_trades(soup),
        "equity_curve": [],  # rarely in HTML
    }


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

# Stat labels in English + French (MT5's locale follows the broker's server).
# Each entry maps a normalized (lowercase, no trailing colon, no accents-loss)
# label to our canonical key. Values are extracted from MT5's table rows
# which interleave label and value cells: [label1, val1, label2, val2, ...].
_HTML_STAT_LABELS = {
    # net profit
    "total net profit": "net_profit",
    "profit total net": "net_profit",
    # gross
    "gross profit": "gross_profit",
    "profit brut": "gross_profit",
    "gross loss": "gross_loss",
    "perte brut": "gross_loss",
    "perte brute": "gross_loss",
    # profit factor
    "profit factor": "profit_factor",
    "facteur de profit": "profit_factor",
    # expected payoff
    "expected payoff": "expected_payoff",
    "remboursement attendu": "expected_payoff",
    # recovery factor
    "recovery factor": "recovery_factor",
    "facteur de recuperation": "recovery_factor",
    # sharpe
    "sharpe ratio": "sharpe_ratio",
    "ratio de sharpe": "sharpe_ratio",
    # drawdown
    "balance drawdown maximal": "max_drawdown",
    "solde drawdown maximal": "max_drawdown",
    "balance drawdown absolute": "absolute_drawdown",
    "solde drawdown absolu": "absolute_drawdown",
    # trades count
    "total trades": "trades",
    "nb trades": "trades",
    "total deals": "total_deals",
    "operations au total": "total_deals",
    # winners / losers
    "profit trades": "win_trades",
    "loss trades": "loss_trades",
    # extremes
    "largest profit trade": "largest_win",
    "plus large position gagnante": "largest_win",
    "largest loss trade": "largest_loss",
    "plus large position perdante": "largest_loss",
    # averages
    "average profit trade": "avg_win",
    "moyenne position gagnante": "avg_win",
    "average loss trade": "avg_loss",
    "moyenne position perdante": "avg_loss",
}


def _strip_accents(s: str) -> str:
    """Best-effort accent stripping so French labels match the lookup map."""
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _parse_number(raw: str) -> float | str:
    """Parse a MT5 numeric cell.

    MT5 uses non-breaking spaces as thousand separators ("1 234.56") and may
    embed a percentage in parentheses ("1 234.56 (1.23%)"). We take the first
    numeric token.
    """
    cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".")
    # Drop trailing "(x.yz%)" or similar
    if "(" in cleaned:
        cleaned = cleaned.split("(", 1)[0]
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return raw


def _extract_html_stats(soup) -> dict:
    """Extract stats from MT5's HTML report (locale-aware)."""
    stats: dict = {}
    for row in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        # Walk cells in (label, value) pairs — MT5 rows interleave them
        i = 0
        while i + 1 < len(cells):
            label = _strip_accents(cells[i]).lower().rstrip(":").strip()
            value = cells[i + 1]
            if label in _HTML_STAT_LABELS and value:
                stats[_HTML_STAT_LABELS[label]] = _parse_number(value)
            i += 2
    return stats


def _extract_html_header_inputs(soup) -> tuple[dict, dict]:
    """Extract symbol/period/expert/dates header and EA inputs from MT5 HTML.

    EA inputs appear under the "Placement:" / "Inputs:" label as one
    "name=value" pair per cell.
    """
    header: dict[str, str] = {}
    inputs: dict[str, float | str] = {}
    header_label_map = {
        "expert": "expert",
        "symbol": "symbol",
        "symbole": "symbol",
        "period": "period",
        "periode": "period",
        "broker": "broker",
        "courtier": "broker",
        "currency": "currency",
        "devise": "currency",
        "initial deposit": "deposit",
        "depot initial": "deposit",
        "leverage": "leverage",
        "levier": "leverage",
    }
    in_inputs = False
    for row in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if not cells:
            continue
        first = _strip_accents(cells[0]).lower().rstrip(":").strip()
        if first in ("inputs", "placement"):
            in_inputs = True
            # Inputs may start on the same row after the label cell
            for c in cells[1:]:
                if "=" in c:
                    k, v = c.split("=", 1)
                    inputs[k.strip()] = _parse_number(v.strip())
            continue
        if in_inputs:
            # We stay in input mode only for rows that look like name=value
            # in their first non-label cell. Any row whose first cell is a
            # known header label (Courtier:/Broker:/Devise:/...) or section
            # header ("Resultats"/"Results") exits input mode.
            if first in header_label_map or first in ("results", "resultats"):
                in_inputs = False
                # fall through to header-pair handling below
            else:
                # Treat as input if any cell has "=", otherwise skip
                if any("=" in c for c in cells):
                    for c in cells:
                        if "=" in c:
                            k, v = c.split("=", 1)
                            inputs[k.strip()] = _parse_number(v.strip())
                    continue
                # otherwise drop through
        # Header pairs
        i = 0
        while i + 1 < len(cells):
            label = _strip_accents(cells[i]).lower().rstrip(":").strip()
            if label in header_label_map and cells[i + 1]:
                header[header_label_map[label]] = cells[i + 1]
            i += 2
    return header, inputs


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
