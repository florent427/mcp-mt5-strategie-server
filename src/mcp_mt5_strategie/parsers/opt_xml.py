"""
Parser for MT5 Strategy Tester optimization report (XML).

Optimization reports contain N "passes" — one row per parameter combination tested.
Each pass has its own params and resulting stats.

Structure typical:
    <OptimizationResult>
        <Header>...</Header>
        <Pass id="1">
            <Inputs>
                <Input name="Lookback" value="20"/>
                ...
            </Inputs>
            <Stats>
                <NetProfit>5234</NetProfit>
                <ProfitFactor>1.45</ProfitFactor>
                ...
            </Stats>
        </Pass>
        <Pass id="2">...</Pass>
        ...
    </OptimizationResult>
"""
from pathlib import Path

from lxml import etree

from ._io import load_xml_root
from .report_xml import _extract_inputs, _extract_stats


def parse_optimization_report(path: Path | str) -> dict:
    """Parse a MT5 optimization report.

    Returns:
        {
            passes: [
                {pass_id: int, params: {...}, stats: {...}},
                ...
            ],
            header: {symbol, period, expert, dates, ...},
            total_passes: int,
        }
    """
    path = Path(path)
    if not path.exists():
        return {"error": f"Report not found: {path}", "passes": []}

    try:
        root = load_xml_root(path)
    except etree.XMLSyntaxError:
        # Probably HTML — fall back below
        passes = _parse_html_optimization(path)
        return {"passes": passes, "total_passes": len(passes)}

    passes = []

    # XML <Pass> elements
    for p in root.findall(".//Pass"):
        pass_id = p.get("id") or p.get("Id")
        try:
            pass_id = int(pass_id) if pass_id else None
        except ValueError:
            pass_id = None
        params = _extract_inputs(p)
        stats = _extract_stats(p)
        if params or stats:
            passes.append({
                "pass_id": pass_id,
                "params": params,
                "stats": stats,
            })

    # Fallback : table-style HTML optimizer report
    if not passes:
        passes = _parse_html_optimization(path)

    return {
        "passes": passes,
        "total_passes": len(passes),
    }


def _parse_html_optimization(path: Path) -> list[dict]:
    """Parse HTML optimization report (fallback)."""
    from bs4 import BeautifulSoup

    raw = path.read_text(encoding="utf-16", errors="replace")
    if "<html" not in raw.lower():
        raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")

    passes = []
    # Optimization HTML has table with columns : Pass | Result | Profit | ... | Inputs
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        if "pass" not in headers and "result" not in headers:
            continue
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 2:
                continue
            entry = dict(zip(headers, cells))
            # Split stats vs inputs heuristically
            stats = {}
            params = {}
            for k, v in entry.items():
                if k in ("pass", "result", "profit", "expected payoff",
                         "profit factor", "recovery factor", "sharpe ratio",
                         "trades", "balance drawdown"):
                    try:
                        stats[k.replace(" ", "_")] = float(v.replace(" ", "").replace(",", ""))
                    except ValueError:
                        stats[k.replace(" ", "_")] = v
                else:
                    # Try parse as param
                    if "=" in v:
                        try:
                            pname, pval = v.split("=", 1)
                            params[pname.strip()] = float(pval) if pval.replace(".", "").lstrip("-").isdigit() else pval
                        except ValueError:
                            pass
            passes.append({"params": params, "stats": stats})
        break
    return passes
