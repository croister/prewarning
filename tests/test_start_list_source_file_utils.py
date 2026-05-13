from xml.etree import ElementTree


# _get_data from startlistsources/start_list_source_file.py
def _get_data(element, selector, ns):
    data = element.find(selector, ns)
    if data is not None:
        return data.text
    else:
        return None


class TestGetData:
    def test_finds_element_and_returns_text(self):
        xml = '<root xmlns:ns="http://example.com"><ns:item>hello</ns:item></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://example.com"}
        result = _get_data(root, "ns:item", ns)
        assert result == "hello"

    def test_returns_none_when_element_missing(self):
        xml = '<root xmlns:ns="http://example.com"><ns:other>val</ns:other></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://example.com"}
        result = _get_data(root, "ns:item", ns)
        assert result is None

    def test_returns_none_for_empty_text(self):
        xml = '<root xmlns:ns="http://example.com"><ns:item></ns:item></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://example.com"}
        result = _get_data(root, "ns:item", ns)
        assert result is None

    def test_multiple_namespace_prefixes(self):
        xml = '<root xmlns:a="http://a.com" xmlns:b="http://b.com"><a:x>1</a:x><b:y>2</b:y></root>'
        root = ElementTree.fromstring(xml)
        ns = {"a": "http://a.com", "b": "http://b.com"}
        assert _get_data(root, "a:x", ns) == "1"
        assert _get_data(root, "b:y", ns) == "2"

    def test_nested_elements(self):
        xml = '<root xmlns:ns="http://x.com"><ns:parent><ns:child>deep</ns:child></ns:parent></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://x.com"}
        result = _get_data(root, "ns:parent/ns:child", ns)
        assert result == "deep"

    def test_attribute_not_confused_with_text(self):
        xml = '<root xmlns:ns="http://x.com"><ns:item attr="val">text</ns:item></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://x.com"}
        result = _get_data(root, "ns:item", ns)
        assert result == "text"

    def test_cdata(self):
        xml = '<root xmlns:ns="http://x.com"><ns:item><![CDATA[cdata text]]></ns:item></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://x.com"}
        result = _get_data(root, "ns:item", ns)
        assert result == "cdata text"

    def test_unicode_text(self):
        xml = (
            '<root xmlns:ns="http://x.com"><ns:item>\u00e9\u00e0\u00fc</ns:item></root>'
        )
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://x.com"}
        result = _get_data(root, "ns:item", ns)
        assert result == "\u00e9\u00e0\u00fc"

    def test_whitespace_preserved(self):
        xml = '<root xmlns:ns="http://x.com"><ns:item>  spaced  </ns:item></root>'
        root = ElementTree.fromstring(xml)
        ns = {"ns": "http://x.com"}
        result = _get_data(root, "ns:item", ns)
        assert result == "  spaced  "

    def test_element_with_no_namespace(self):
        xml = "<root><item>no ns</item></root>"
        root = ElementTree.fromstring(xml)
        result = _get_data(root, "item", {})
        assert result == "no ns"
