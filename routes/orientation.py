from flask import request, render_template
from app import app
from config.countries import COUNTRIES
from config.languages import LANGUAGES
from services.country_detection import detect_country, detect_language
from utils.seo_helpers import absolute_url

ORIENTATION_CATEGORIES = [
    {
        "key": "all",
        "label": "All / Tout",
        "title": "All / Tout",
    },
    {
        "key": "apres_bac",
        "label": "Après Bac (Concours Bac)",
        "title": "Après Bac",
    },
    {
        "key": "bac_plus_2",
        "label": "Bac +2 (DEUG, DUT, BTS, CPGE, etc.)",
        "title": "Bac +2",
    },
    {
        "key": "licence_excellence",
        "label": "Licence d'Excellence & Bachelor",
        "title": "Licence d'Excellence",
    },
    {
        "key": "cycles_ingenieurs",
        "label": "Cycles d'Ingénieurs",
        "title": "Cycles d'Ingénieurs",
    },
    {
        "key": "master",
        "label": "Master & Master Spécialisé",
        "title": "Master",
    },
    {
        "key": "doctorat",
        "label": "Doctorat",
        "title": "Doctorat",
    },
]

ORIENTATION_ITEMS = [
    {
        "category": "apres_bac",
        "title": "Concours ENA 2026",
        "institution": "ENA — École Nationale d'Administration",
        "deadline": "15 Octobre 2026",
        "description": "Programme de préparation aux concours de l'administration publique, du management public et des grands services de l'État.",
        "cta": "Read More",
    },
    {
        "category": "apres_bac",
        "title": "Concours de l'Université Mohammed VI Polytechnique",
        "institution": "UM6P — Rabat / Benguerir",
        "deadline": "30 Septembre 2026",
        "description": "Accès aux programmes d'excellence en ingénierie, sciences numériques, gestion et innovation technologique.",
        "cta": "Postuler",
    },
    {
        "category": "bac_plus_2",
        "title": "DUT / BTS / CPGE — Parcours Intégrés",
        "institution": "Université Hassan II / Centres publics",
        "deadline": "20 Novembre 2026",
        "description": "Des formations courtes et professionnalisantes pour consolider votre profil et accéder aux filières techniques ou commerciales.",
        "cta": "Read More",
    },
    {
        "category": "bac_plus_2",
        "title": "BTS Digital Marketing 2026",
        "institution": "IFM / Établissements privés marocains",
        "deadline": "05 Novembre 2026",
        "description": "Préparez-vous à un parcours professionnel en marketing digital, communication, e-commerce et gestion de marque.",
        "cta": "Postuler",
    },
    {
        "category": "licence_excellence",
        "title": "Licence d'Excellence Web Development - FS Rabat",
        "institution": "Faculté des Sciences Rabat",
        "deadline": "12 Octobre 2026",
        "description": "Formation de haut niveau en développement web, architecture logicielle, UX/UI et projets appliqués.",
        "cta": "Read More",
    },
    {
        "category": "licence_excellence",
        "title": "Bachelor in Data Science & AI",
        "institution": "International Business School / Campus Europe",
        "deadline": "01 Novembre 2026",
        "description": "Un bachelor orienté IA, analyse de données, visualisation, machine learning et gestion de projets technologiques.",
        "cta": "Postuler",
    },
    {
        "category": "cycles_ingenieurs",
        "title": "Cycle Ingénieur Électronique et Systèmes Embarqués",
        "institution": "École d'Ingénieurs Mohammed V / Maroc",
        "deadline": "18 Octobre 2026",
        "description": "Accès aux cycles ingénieurs spécialisés en électronique, robotique, IoT et systèmes intelligents.",
        "cta": "Read More",
    },
    {
        "category": "cycles_ingenieurs",
        "title": "Engineering Program - Computer Science",
        "institution": "ENSIAS / Écoles d'ingénieurs partenaires",
        "deadline": "25 Octobre 2026",
        "description": "Parcours intensif en informatique, cybersécurité, cloud, intelligence artificielle et architecture logicielle.",
        "cta": "Postuler",
    },
    {
        "category": "master",
        "title": "Master en Intelligence Artificielle",
        "institution": "Université Mohammed VI / Écoles partenaires",
        "deadline": "30 Novembre 2026",
        "description": "Formation avancée en IA, deep learning, traitement du langage naturel, vision par ordinateur et applications industrielles.",
        "cta": "Read More",
    },
    {
        "category": "master",
        "title": "Master spécialisé en Finance Digitale",
        "institution": "HEC / MBA & grandes écoles",
        "deadline": "15 Novembre 2026",
        "description": "Prépare à la transformation numérique de la finance, data, blockchain et modélisation de risque.",
        "cta": "Postuler",
    },
    {
        "category": "doctorat",
        "title": "Doctorat en Sciences de l'Information",
        "institution": "Université de Rabat / Labos de recherche",
        "deadline": "10 Décembre 2026",
        "description": "Programme doctoral structuré pour les profils de recherche avancée en IA, systèmes d'information et innovation scientifique.",
        "cta": "Read More",
    },
    {
        "category": "doctorat",
        "title": "Doctorat en Génie Civil & Durabilité",
        "institution": "Université Hassan II / Centres de recherche",
        "deadline": "01 Décembre 2026",
        "description": "Recherches appliquées sur les infrastructures durables, l'urbanisme intelligent et les matériaux de demain.",
        "cta": "Postuler",
    },
]


@app.route("/orientation")
def orientation_page():
    country = request.args.get("country")
    if country not in COUNTRIES:
        country = detect_country()

    lang = request.args.get("lang")
    if lang not in LANGUAGES:
        lang = detect_language(country)

    country_info = COUNTRIES.get(country, COUNTRIES["ma"])
    active_category = request.args.get("category", "all")

    filtered_items = [
        item for item in ORIENTATION_ITEMS
        if active_category == "all" or item["category"] == active_category
    ]

    return render_template(
        "orientation.html",
        orientation_items=filtered_items,
        orientation_categories=ORIENTATION_CATEGORIES,
        active_category=active_category,
        countries=COUNTRIES,
        languages=LANGUAGES,
        current_country=country,
        current_language=lang,
        country_name=country_info["name"],
        canonical_url=absolute_url(f"/orientation?country={country}&lang={lang}"),
    )
