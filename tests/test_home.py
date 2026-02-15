from hestia_utils.parser import Home


class TestHomeConstruction:
    def test_default_values(self):
        home = Home()
        assert home.address == ''
        assert home.city == ''
        assert home.url == ''
        assert home.agency == ''
        assert home.price == -1
        assert home.sqm == -1

    def test_all_fields(self):
        home = Home(address="Kerkstraat 1", city="Amsterdam", url="https://example.com", agency="funda", price=1500, sqm=75)
        assert home.address == "Kerkstraat 1"
        assert home.city == "Amsterdam"
        assert home.url == "https://example.com"
        assert home.agency == "funda"
        assert home.price == 1500
        assert home.sqm == 75


class TestHomeEquality:
    def test_equal_same_case(self):
        a = Home(address="Kerkstraat 1", city="Amsterdam")
        b = Home(address="Kerkstraat 1", city="Amsterdam")
        assert a == b

    def test_equal_case_insensitive(self):
        a = Home(address="kerkstraat 1", city="amsterdam")
        b = Home(address="Kerkstraat 1", city="Amsterdam")
        assert a == b

    def test_not_equal_different_address(self):
        a = Home(address="Kerkstraat 1", city="Amsterdam")
        b = Home(address="Kerkstraat 2", city="Amsterdam")
        assert a != b

    def test_not_equal_different_city(self):
        a = Home(address="Kerkstraat 1", city="Amsterdam")
        b = Home(address="Kerkstraat 1", city="Rotterdam")
        assert a != b

    def test_equal_ignores_price_url_agency(self):
        a = Home(address="Kerkstraat 1", city="Amsterdam", price=1000, url="http://a.com", agency="funda")
        b = Home(address="Kerkstraat 1", city="Amsterdam", price=2000, url="http://b.com", agency="pararius")
        assert a == b


class TestCityNormalization:
    def test_gravenhage_with_apostrophe(self):
        home = Home(city="'s-Gravenhage")
        assert home.city == "Den Haag"

    def test_gravenhage_without_apostrophe(self):
        home = Home(city="s-Gravenhage")
        assert home.city == "Den Haag"

    def test_hertogenbosch_with_apostrophe(self):
        home = Home(city="'s-Hertogenbosch")
        assert home.city == "Den Bosch"

    def test_hertogenbosch_without_apostrophe(self):
        home = Home(city="s-Hertogenbosch")
        assert home.city == "Den Bosch"

    def test_alphen_aan_den_rijn(self):
        home = Home(city="Alphen a/d Rijn")
        assert home.city == "Alphen aan den Rijn"

    def test_alphen_aan_den_rijn_full(self):
        home = Home(city="Alphen aan den Rijn")
        assert home.city == "Alphen aan den Rijn"

    def test_koog_aan_de_zaan(self):
        home = Home(city="Koog a/d Zaan")
        assert home.city == "Koog aan de Zaan"

    def test_capelle_aan_den_ijssel(self):
        home = Home(city="Capelle a/d IJssel")
        assert home.city == "Capelle aan den IJssel"

    def test_berkel_enschot(self):
        home = Home(city="Berkel Enschot")
        assert home.city == "Berkel-Enschot"

    def test_oud_beijerland(self):
        home = Home(city="Oud Beijerland")
        assert home.city == "Oud-Beijerland"

    def test_etten_leur(self):
        home = Home(city="Etten Leur")
        assert home.city == "Etten-Leur"

    def test_nieuw_vennep(self):
        home = Home(city="Nieuw Vennep")
        assert home.city == "Nieuw-Vennep"

    def test_son_en_breugel(self):
        home = Home(city="son en breugel")
        assert home.city == "Son en Breugel"

    def test_bergen_op_zoom(self):
        home = Home(city="bergen op zoom")
        assert home.city == "Bergen op Zoom"

    def test_berkel_en_rodenrijs(self):
        home = Home(city="berkel en rodenrijs")
        assert home.city == "Berkel en Rodenrijs"

    def test_wijk_bij_duurstede(self):
        home = Home(city="wijk bij duurstede")
        assert home.city == "Wijk bij Duurstede"

    def test_hoogvliet_rotterdam(self):
        home = Home(city="hoogvliet rotterdam")
        assert home.city == "Hoogvliet Rotterdam"

    def test_nederhorst_den_berg(self):
        home = Home(city="nederhorst den berg")
        assert home.city == "Nederhorst den Berg"

    def test_huis_ter_heide(self):
        home = Home(city="huis ter heide")
        assert home.city == "Huis ter Heide"

    def test_normal_city_unchanged(self):
        home = Home(city="Amsterdam")
        assert home.city == "Amsterdam"


class TestCityProvinceStripping:
    def test_strips_two_letter_province(self):
        home = Home(city="Amsterdam (NH)")
        assert home.city == "Amsterdam"

    def test_strips_lowercase_province(self):
        home = Home(city="Rotterdam (zh)")
        assert home.city == "Rotterdam"

    def test_no_province_unchanged(self):
        home = Home(city="Amsterdam")
        assert home.city == "Amsterdam"

    def test_province_strip_then_normalize(self):
        home = Home(city="'s-Gravenhage (ZH)")
        assert home.city == "Den Haag"


class TestHomeStringRepresentation:
    def test_str(self):
        home = Home(address="Kerkstraat 1", city="Amsterdam", agency="funda")
        assert str(home) == "Kerkstraat 1, Amsterdam (Funda)"

    def test_repr_equals_str(self):
        home = Home(address="Kerkstraat 1", city="Amsterdam", agency="funda")
        assert repr(home) == str(home)

    def test_str_agency_title_case(self):
        home = Home(address="Hoofdweg 10", city="Rotterdam", agency="woonnet_rijnmond")
        assert str(home) == "Hoofdweg 10, Rotterdam (Woonnet_Rijnmond)"


class TestHomeAddressProperty:
    def test_getter(self):
        home = Home(address="Kerkstraat 1")
        assert home.address == "Kerkstraat 1"

    def test_setter(self):
        home = Home()
        home.address = "Nieuwe Straat 5"
        assert home.address == "Nieuwe Straat 5"
