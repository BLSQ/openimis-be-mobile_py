from django.apps import AppConfig

MODULE_NAME = "mobile"

DEFAULT_CFG = {
    "gql_mutation_create_families_perms": ['101002'],
    "gql_mutation_update_families_perms": ['101003'],
    "gql_mutation_create_insurees_perms": ["101102"],
    "gql_mutation_update_insurees_perms": ["101103"],
    "gql_mutation_create_policies_perms": ['101202'],
    "gql_mutation_edit_policies_perms": ['101203'],
    "gql_mutation_create_premiums_perms": ["101302"],
    "gql_mutation_update_premiums_perms": ["101303"],
}


class MobileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = MODULE_NAME

    gql_mutation_create_families_perms = []
    gql_mutation_update_families_perms = []
    gql_mutation_create_insurees_perms = []
    gql_mutation_update_insurees_perms = []
    gql_mutation_create_policies_perms = []
    gql_mutation_edit_policies_perms = []
    gql_mutation_create_premiums_perms = []
    gql_mutation_update_premiums_perms = []

    def _configure_permissions(self, cfg):
        MobileConfig.gql_mutation_create_families_perms = cfg["gql_mutation_create_families_perms"]
        MobileConfig.gql_mutation_update_families_perms = cfg["gql_mutation_update_families_perms"]
        MobileConfig.gql_mutation_create_insurees_perms = cfg["gql_mutation_create_insurees_perms"]
        MobileConfig.gql_mutation_update_insurees_perms = cfg["gql_mutation_update_insurees_perms"]
        MobileConfig.gql_mutation_create_policies_perms = cfg["gql_mutation_create_policies_perms"]
        MobileConfig.gql_mutation_edit_policies_perms = cfg["gql_mutation_edit_policies_perms"]
        MobileConfig.gql_mutation_create_premiums_perms = cfg["gql_mutation_create_premiums_perms"]
        MobileConfig.gql_mutation_update_premiums_perms = cfg["gql_mutation_update_premiums_perms"]

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self._configure_permissions(cfg)
