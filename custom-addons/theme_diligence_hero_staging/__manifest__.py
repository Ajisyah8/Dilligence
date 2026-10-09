{
    "name": "Diligence Hero Presentation (Staging)",
    "summary": "Staging-only presentation for the Diligence hero tutor card",
    "version": "19.0.1.0.0",
    "category": "Theme/Education",
    "author": "Project ADS",
    "license": "LGPL-3",
    "depends": ["theme_diligence_modern", "website"],
    "data": [
        "views/login.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "theme_diligence_hero_staging/static/src/scss/hero_tutor.scss",
            "theme_diligence_hero_staging/static/src/scss/login.scss",
        ],
    },
    "installable": True,
    "application": False,
}
