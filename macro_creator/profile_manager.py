import json
from .variable_config import VariableConfig

class ProfileManager:
    @staticmethod
    def saveVariables(filepath, variables: dict[str, VariableConfig]):
        data = {}
        for key_str, var_config in variables.items():
            data[key_str] = var_config.toDict()

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def loadVariables(filepath) -> dict[str, VariableConfig]:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}

        loaded_vars = {}
        for key_str, var_data in data.items():
            loaded_vars[key_str] = VariableConfig.fromDict(var_data)

        return loaded_vars
