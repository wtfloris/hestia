from hestia_utils.meta import escape_markdownv2, escape_markdownv2_url


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

    def test_escapes_remaining_reserved_chars(self):
        # These were silently passed through before, breaking the whole send.
        for char in "_[]~`>#={}":
            assert escape_markdownv2(f"a{char}b") == f"a\\{char}b", char

    def test_escapes_backslash_without_double_escaping(self):
        assert escape_markdownv2(r"a\b") == r"a\\b"

    def test_escapes_agency_name_with_parentheses(self):
        # The exact name that broke ikwilhuren broadcasts.
        assert escape_markdownv2("MVGM (ikwilhuren.nu)") == r"MVGM \(ikwilhuren\.nu\)"

    def test_address_with_hash(self):
        assert escape_markdownv2("Kerkstraat 12 #3") == r"Kerkstraat 12 \#3"


class TestEscapeMarkdownV2Url:
    def test_escapes_closing_paren(self):
        assert escape_markdownv2_url("https://x.nl/a(b)c") == r"https://x.nl/a(b\)c"

    def test_escapes_backslash(self):
        assert escape_markdownv2_url(r"https://x.nl/a\b") == r"https://x.nl/a\\b"

    def test_leaves_normal_url_untouched(self):
        url = "https://ikwilhuren.nu/object/voorburg-2274ex-167-guido-gezellestraat-3eda6e33/"
        assert escape_markdownv2_url(url) == url

    def test_does_not_escape_dots_or_dashes(self):
        # A URL is not body text: escaping the full special set would corrupt it.
        assert escape_markdownv2_url("https://a-b.nl/x_y") == "https://a-b.nl/x_y"
