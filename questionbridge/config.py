from dynaconf import Dynaconf

# Settings files are resolved relative to the current working directory,
# so an installed user places settings.local.yaml next to where they invoke
# the `questionbridge` command.
settings = Dynaconf(
    settings_files=["settings.yaml", "settings.local.yaml"],
    environments=True,
    env="default",
    load_dotenv=False,
)
