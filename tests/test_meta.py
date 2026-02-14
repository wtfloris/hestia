from hestia_utils.meta import escape_markdownv2


class TestEscapeMarkdownV2:
    def test_escapes_dot(self):
        assert escape_markdownv2("hello.world") == r"hello\.world"

    def test_escapes_exclamation(self):
        assert escape_markdownv2("hello!") == r"hello\!"

    def test_escapes_plus(self):
        assert escape_markdownv2("a+b") == r"a\+b"

    def test_escapes_minus(self):
        assert escape_markdownv2("a-b") == r"a\-b"

    def test_escapes_asterisk(self):
        assert escape_markdownv2("bold*text") == r"bold\*text"

    def test_escapes_pipe(self):
        assert escape_markdownv2("a|b") == r"a\|b"

    def test_escapes_parentheses(self):
        assert escape_markdownv2("(test)") == r"\(test\)"

    def test_preserves_normal_chars(self):
        assert escape_markdownv2("hello world 123") == "hello world 123"

    def test_multiple_special_chars(self):
        result = escape_markdownv2("Price: €1.500 (per month!)")
        assert result == r"Price: €1\.500 \(per month\!\)"

    def test_empty_string(self):
        assert escape_markdownv2("") == ""
