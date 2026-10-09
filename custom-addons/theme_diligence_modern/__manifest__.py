{
    "name": "Diligence Modern (Cobalt)",
    "summary": "Modern Diligence visual layer based on the official Odoo Cobalt theme",
    "version": "19.0.1.0.0",
    "category": "Theme/Education",
    "author": "Project ADS",
    "license": "LGPL-3",
    "depends": ["theme_cobalt", "diligence_learning"],
    "data": [
        "views/layout.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "theme_diligence_modern/static/src/scss/diligence_modern.scss",
        ],
    },
    "installable": True,
    "application": False,
}
