# TODO:
def validate_apps_configured(apps: list[str]) -> None:
    """
    Validate that all apps provided are configured on platform.aci.dev.
    """
    pass


# TODO:
def validate_linked_accounts_exist(apps: list[str], linked_account_owner_id: str) -> None:
    """
    Validate that the linked accounts (identified by the linked_account_owner_id + app name)
    exist on platform.aci.dev.
    """
    pass


def validate_api_key(api_key: str | None) -> None:
    """
    Validate that the API key is valid.
    """
    # TODO: for now only validate that the api key is not the placeholder value because that's
    # most likely the case when the user copy over the example config from the documentation.
    # Technically we can also do a more solid regex but that might not be forward compatible.
    if not api_key or api_key in ["<YOUR_ACI_API_KEY>", "ACI_API_KEY", "<ACI_API_KEY>"]:
        raise ValueError("Invalid API key")
