import pytest

from eventradar.regions import NEIGHBOURS, UnknownCountry, country_and_neighbours, find_country


def test_mozambique_and_its_neighbours():
    names = [country.name for country in country_and_neighbours("  mozambique ")]

    assert names == [
        "Mozambique",
        "Tanzania",
        "Malawi",
        "Zambia",
        "Zimbabwe",
        "South Africa",
        "Eswatini",
    ]


def test_aliases_and_country_codes():
    assert find_country("RSA").gl == "za"
    assert find_country("Moçambique").name == "Mozambique"


def test_unknown_country_names_are_searched_as_typed():
    nigeria = find_country("Nigeria")

    assert (nigeria.name, nigeria.gl) == ("Nigeria", None)


def test_near_needs_a_known_country():
    with pytest.raises(UnknownCountry, match="Known countries"):
        country_and_neighbours("Atlantis")


def test_neighbours_are_symmetric():
    for country, neighbours in NEIGHBOURS.items():
        for neighbour in neighbours:
            assert country in NEIGHBOURS[neighbour], f"{neighbour} should list {country}"
