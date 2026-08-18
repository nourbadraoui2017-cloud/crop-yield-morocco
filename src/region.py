"""
region.py -- Geometrie de la region Rabat-Sale-Kenitra, utilisee par
tous les scripts qui interrogent Earth Engine (pull_ndvi.py,
pull_ndvi_landsat.py) a la place du rectangle approximatif utilise
jusqu'ici.

CE QU'ON A DECOUVERT EN TESTANT (garde ca en tete si on retouche ce
fichier plus tard) : le dataset FAO GAUL "level1" (regions) ne
contient PAS la region "Rabat-Sale-Kenitra" telle qu'elle existe
depuis la reforme administrative de 2015 -- il a encore l'ancien
decoupage en 16 regions, avec "Rabat - Sale - Zemmour - Zaer" (sans
Kenitra ni Sidi Kacem, qui appartenaient a l'epoque a une autre
region, "Gharb - Chrarda - Beni Hssen"). Utiliser cette ancienne
region toute seule aurait exclu Kenitra -- une des zones cerealieres
les plus importantes de la region actuelle. Ca aurait ete PIRE que le
rectangle, en creant un desaccord silencieux entre la zone NDVI et la
zone couverte par les donnees de rendement HCP (qui, elles, sont bien
sur le decoupage actuel).

La solution retenue : le dataset "level2" (provinces/prefectures) est
plus stable dans le temps -- les provinces elles-memes n'ont pas
change, seul leur regroupement en regions a change. Rabat-Sale-Kenitra
actuelle = les provinces/prefectures Rabat, Sale, Skhirate-Temara,
Khemisset, Kenitra, Sidi Kacem, Sidi Slimane. Ce fichier les cherche
une par une (recherche insensible aux accents, car l'orthographe
officielle varie selon les sources : "Sale" vs "Sale", "Kenitra" vs
"Kenitra"...) et prend leur union comme geometrie.

Fallback : si moins de la moitie des provinces attendues sont
trouvees, on retombe sur le rectangle approximatif plutot que
d'utiliser une zone partielle sans le signaler.

Usage :
    from region import get_region_geometry
    GEOM = get_region_geometry()
"""

import unicodedata

import ee

# Les 7 provinces/prefectures qui composent la region Rabat-Sale-Kenitra
# depuis la reforme de 2015.
PROVINCE_KEYWORDS = [
    "rabat",
    "sale",
    "skhirat",  # couvre "Skhirate-Temara" / "Skhirat-Temara"
    "khemisset",
    "kenitra",
    "sidi kacem",
    "sidi slimane",
]


def _normalize(s: str) -> str:
    """Enleve les accents et met en minuscules, pour comparer des noms
    ecrits avec des orthographes/accents differents."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _fallback_bbox() -> ee.Geometry:
    # Rectangle utilise jusqu'ici, garde comme filet de securite. Cree
    # seulement au moment ou on en a besoin (pas au chargement du
    # fichier) car ee.Geometry(...) exige que ee.Initialize() ait deja
    # ete appele, et l'ordre entre "import region" et "ee.Initialize()"
    # varie selon le script appelant.
    return ee.Geometry.Rectangle([-7.0, 33.5, -5.5, 34.9])


def get_region_geometry(verbose: bool = True) -> ee.Geometry:
    admin2 = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
        ee.Filter.eq("ADM0_NAME", "Morocco")
    )
    all_names = admin2.aggregate_array("ADM2_NAME").getInfo()

    matched_names = [
        name
        for name in all_names
        if any(keyword in _normalize(name) for keyword in PROVINCE_KEYWORDS)
    ]

    if verbose:
        print(f"Provinces trouvees pour Rabat-Sale-Kenitra : {matched_names}")

    if len(matched_names) < len(PROVINCE_KEYWORDS) // 2:
        if verbose:
            print(
                f"ATTENTION : seulement {len(matched_names)}/{len(PROVINCE_KEYWORDS)} "
                "provinces attendues trouvees dans FAO/GAUL/2015/level2 -- "
                "trop peu pour faire confiance a cette zone."
            )
            print(f"Toutes les provinces marocaines disponibles : {all_names}")
            print(
                "-> Utilisation du rectangle approximatif de secours "
                "(FALLBACK_BBOX). Regarde la liste ci-dessus et ajuste "
                "PROVINCE_KEYWORDS dans src/region.py si besoin, puis relance."
            )
        return _fallback_bbox()

    region = admin2.filter(ee.Filter.inList("ADM2_NAME", matched_names))
    return region.geometry()
