"""
Shared XML loading helper for MT5 report parsers.

MT5 writes reports in UTF-16-LE with a BOM but declares ``encoding="utf-16"``
in the XML prolog, which trips up lxml's strict parsing. We normalize that:
read the raw bytes, detect/strip the BOM, decode to text, drop the XML
declaration (the encoding claim is now wrong post-decode), then hand a clean
UTF-8 byte string to lxml.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree


def load_xml_root(path: Path):
    """Read an MT5 XML report and return a parsed lxml root element.

    Raises:
        etree.XMLSyntaxError: if the file is HTML or otherwise unparseable
            as XML — caller should fall back to HTML parsing.
    """
    data = path.read_bytes()

    # Strip BOM and decode
    if data.startswith(b"\xff\xfe"):
        text = data[2:].decode("utf-16-le", errors="replace")
    elif data.startswith(b"\xfe\xff"):
        text = data[2:].decode("utf-16-be", errors="replace")
    elif data.startswith(b"\xef\xbb\xbf"):
        text = data[3:].decode("utf-8", errors="replace")
    else:
        # Try UTF-8 first, fall back to UTF-16-LE (MT5 default)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-16-le", errors="replace")

    text = text.lstrip()

    # If the content is actually HTML, abort so callers fall back
    head = text[:500].lower()
    if "<html" in head and "<?xml" not in head:
        raise etree.XMLSyntaxError("Content is HTML, not XML", 0, 0, 0)

    # Drop XML declaration — its encoding hint no longer matches our text
    if text.startswith("<?xml"):
        end = text.find("?>")
        if end != -1:
            text = text[end + 2 :].lstrip()

    parser = etree.XMLParser(recover=True)
    root = etree.fromstring(text.encode("utf-8"), parser)
    if root is None or len(root) == 0 and not root.attrib and not root.text:
        raise etree.XMLSyntaxError("Empty or unparseable XML", 0, 0, 0)
    return root
