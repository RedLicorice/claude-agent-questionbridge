from dynaconf import Dynaconf

settings = Dynaconf(
    settings_files=["settings.yaml", "settings.local.yaml"],
    environments=True,
    env="default",
    load_dotenv=False,
)
