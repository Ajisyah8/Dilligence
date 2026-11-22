import importlib.util
import os


def migrate(cr, version):
    # Reuse the language maps and homepage/footer targeting from the previous
    # migration. Version 1.0.60 fixes XML-translated terms that include markup
    # (for example <span>...</span>) and teacher-name tails after <br/> nodes.
    migration_path = os.path.join(
        os.path.dirname(__file__), '..', '1.0.59', 'post-migrate.py',
    )
    spec = importlib.util.spec_from_file_location(
        'diligence_learning_homepage_localization_1059', migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.migrate(cr, version)
