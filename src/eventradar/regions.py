"""Countries the radar knows, with their Google country codes and land neighbours."""

from __future__ import annotations

from eventradar.models import Country

COUNTRY_CODES = {
    "Angola": "ao",
    "Botswana": "bw",
    "Burundi": "bi",
    "DR Congo": "cd",
    "Eswatini": "sz",
    "Kenya": "ke",
    "Lesotho": "ls",
    "Malawi": "mw",
    "Mozambique": "mz",
    "Namibia": "na",
    "Rwanda": "rw",
    "South Africa": "za",
    "Tanzania": "tz",
    "Uganda": "ug",
    "Zambia": "zm",
    "Zimbabwe": "zw",
}

# Names that tie a web page to a country when the country itself is not named.
LOCAL_NAMES = {
    "Angola": ("Luanda",),
    "Botswana": ("Gaborone",),
    "Burundi": ("Bujumbura", "Gitega"),
    "DR Congo": ("Congo", "Kinshasa", "Lubumbashi", "Goma"),
    "Eswatini": ("Swaziland", "Mbabane", "Manzini"),
    "Kenya": ("Nairobi", "Mombasa", "Kisumu"),
    "Lesotho": ("Maseru",),
    "Malawi": ("Lilongwe", "Blantyre"),
    "Mozambique": ("Moçambique", "Mocambique", "Maputo", "Beira"),
    "Namibia": ("Windhoek",),
    "Rwanda": ("Kigali",),
    "South Africa": ("PyConZA", "Johannesburg", "Joburg", "Cape Town", "Durban", "Pretoria"),
    "Tanzania": ("Dar es Salaam", "Dodoma", "Arusha", "Zanzibar"),
    "Uganda": ("Kampala",),
    "Zambia": ("Lusaka",),
    "Zimbabwe": ("Harare", "Bulawayo"),
}

# Land neighbours, limited to the countries above. Order is roughly north to south.
NEIGHBOURS = {
    "Angola": ["DR Congo", "Zambia", "Namibia"],
    "Botswana": ["Zambia", "Zimbabwe", "Namibia", "South Africa"],
    "Burundi": ["Rwanda", "DR Congo", "Tanzania"],
    "DR Congo": ["Uganda", "Rwanda", "Burundi", "Tanzania", "Zambia", "Angola"],
    "Eswatini": ["Mozambique", "South Africa"],
    "Kenya": ["Uganda", "Tanzania"],
    "Lesotho": ["South Africa"],
    "Malawi": ["Tanzania", "Zambia", "Mozambique"],
    "Mozambique": ["Tanzania", "Malawi", "Zambia", "Zimbabwe", "South Africa", "Eswatini"],
    "Namibia": ["Angola", "Zambia", "Botswana", "South Africa"],
    "Rwanda": ["Uganda", "DR Congo", "Tanzania", "Burundi"],
    "South Africa": ["Zimbabwe", "Botswana", "Mozambique", "Namibia", "Eswatini", "Lesotho"],
    "Tanzania": [
        "Kenya",
        "Uganda",
        "Rwanda",
        "Burundi",
        "DR Congo",
        "Zambia",
        "Malawi",
        "Mozambique",
    ],
    "Uganda": ["Kenya", "DR Congo", "Rwanda", "Tanzania"],
    "Zambia": [
        "DR Congo",
        "Tanzania",
        "Malawi",
        "Mozambique",
        "Zimbabwe",
        "Botswana",
        "Namibia",
        "Angola",
    ],
    "Zimbabwe": ["Zambia", "Mozambique", "South Africa", "Botswana"],
}

ALIASES = {
    "drc": "DR Congo",
    "congo": "DR Congo",
    "democratic republic of the congo": "DR Congo",
    "rsa": "South Africa",
    "sa": "South Africa",
    "swaziland": "Eswatini",
    "moz": "Mozambique",
    "mocambique": "Mozambique",
    "moçambique": "Mozambique",
}


class UnknownCountry(ValueError):
    def __init__(self, name: str) -> None:
        known = ", ".join(COUNTRY_CODES)
        super().__init__(f'"{name}" is not a country the radar knows. Known countries: {known}.')


def find_country(name: str) -> Country:
    """A known country, or the name as typed (searched without a country code)."""
    cleaned = " ".join(name.split())
    canonical = _canonical_name(cleaned)
    if canonical:
        return _known(canonical)
    if not cleaned:
        raise ValueError("A country name is required.")
    return Country(cleaned)


def country_and_neighbours(name: str) -> list[Country]:
    canonical = _canonical_name(" ".join(name.split()))
    if not canonical:
        raise UnknownCountry(name)
    return [_known(n) for n in [canonical, *NEIGHBOURS[canonical]]]


def _known(name: str) -> Country:
    return Country(name, COUNTRY_CODES[name], LOCAL_NAMES.get(name, ()))


def _canonical_name(name: str) -> str | None:
    key = name.lower()
    if key in ALIASES:
        return ALIASES[key]
    return next((known for known in COUNTRY_CODES if known.lower() == key), None)
