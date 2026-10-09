{
    "name": "Diligence Next (Staging)",
    "summary": "Editable modern visual layer for Diligence staging",
    "version": "19.0.1.0.0",
    "category": "Theme/Education",
    "author": "Project ADS",
    "license": "LGPL-3",
    "depends": ["theme_diligence_modern", "website"],
    "assets": {
        "web.assets_frontend": [
            "theme_diligence_next/static/src/scss/diligence_next.scss",
        ],
        "website.assets_wysiwyg": [
            "theme_diligence_next/static/src/builder/diligence_style_option.xml",
            "theme_diligence_next/static/src/builder/diligence_style_option.js",
        ],
    },
    "installable": True,
    "application": False,
}
