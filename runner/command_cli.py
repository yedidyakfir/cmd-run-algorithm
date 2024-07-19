import functools
from types import ModuleType
from typing import Callable, List, Optional, Dict, Tuple, Any

import click
from click import MultiCommand, Context, Command, Option

from runner.dynamic_loading import find_subclasses
from runner.parameters_analysis import cli_parameters_for_calling
from runner.run import run
from runner.utils.click import convert_assign_to_pattern
from runner.utils.click import create_assigner_option


class RunCallableCLI(MultiCommand):
    def __init__(
        self,
        callables: Dict[str, Tuple[type, str]],
        command_runner: Callable,
        add_options_from_outside_packages: bool,
        module: ModuleType,
        default_config: Dict[str, Any],
        default_assign_value: Dict[str, Any],
        default_assign_type: Dict[str, Any],
        default_assign_creator: Dict[str, Any],
        default_assign_connection: Dict[str, Any],
        global_settings: Dict[str, Any],
        logger=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.callables = callables
        self.command_runner = command_runner
        self.logger = logger
        self.add_options_from_outside_packages = add_options_from_outside_packages
        self.module = module
        self.default_config = default_config
        self.default_assign_value = default_assign_value
        self.default_assign_type = default_assign_type
        self.default_assign_creator = default_assign_creator
        self.default_assign_connection = default_assign_connection
        self.global_settings = global_settings

    def list_commands(self, ctx: Context) -> List[str]:
        return list(self.callables.keys())

    def get_command(self, ctx: Context, cmd_name: str) -> Optional[Command]:
        if cmd_name in self.callables:
            klass, func_name = self.callables[cmd_name]
            alg_command = functools.partial(
                self.command_runner,
                class_name=cmd_name,
                func_name=func_name,
                base_module=self.module,
                add_options_from_outside_packages=self.add_options_from_outside_packages,
                default_assign_value=self.default_assign_value,
                default_assign_type=self.default_assign_type,
                default_assign_creator=self.default_assign_creator,
                default_assign_connection=self.default_assign_connection,
                default_config=self.default_config,
                global_settings=self.global_settings,
            )

            init_params = cli_parameters_for_calling(
                klass,
                None,
                self.add_options_from_outside_packages,
                self.module,
                logger=self.logger,
            )
            func_params = cli_parameters_for_calling(
                klass,
                func_name,
                self.add_options_from_outside_packages,
                self.module,
                logger=self.logger,
            )
            parameters = init_params + func_params

            params = [
                Option(
                    ["--" + "-".join(param.name.split("."))],
                    type=param.type,
                    multiple=param.multiple,
                    default=param.default,
                    is_flag=param.flag,
                )
                for param in parameters
            ]
            params += [
                create_assigner_option("value"),
                create_assigner_option("type"),
                create_assigner_option("creator"),
                create_assigner_option("connection"),
                Option(
                    ["--use-config"],
                    type=str,
                    multiple=True,
                ),
            ]
            params += self.addtional_params()
            return Command(cmd_name, params=params, callback=alg_command)

    def addtional_params(self):
        params = []
        params += getattr(self.command_runner, "__click_params__", [])
        params += getattr(self.command_runner, "params", [])
        return params


def run_class(*args, callback, **kwargs):
    callback(*args, runner=run, **kwargs)


class RunnerWithCLI(RunCallableCLI):
    def __init__(self, *args, command_runner, **kwargs):
        self.user_func = command_runner
        callback = functools.partial(run_class, callback=command_runner)
        super().__init__(*args, command_runner=callback, **kwargs)

    def addtional_params(self):
        params = super().addtional_params()
        params += getattr(self.user_func, "__click_params__", [])
        params += getattr(self.user_func, "params", [])
        return params


class RunCLIAlgorithm(RunnerWithCLI):
    def __init__(
        self,
        algorithms: Dict[str, type],
        func_name: str,
        *args,
        **kwargs,
    ):
        commands = {name: (alg, func_name) for name, alg in algorithms.items()}
        super().__init__(*args, callables=commands, **kwargs)


class RunCLIAlgorithmFromModule(RunCallableCLI):
    def __init__(self, module: ModuleType, base_type: type, *args, **kwargs):
        algorithms = {klass.__name__: klass for klass in find_subclasses(module, base_type)}
        super().__init__(algorithms, *args, module=module, **kwargs)


class RunCLIClassFunctions(RunnerWithCLI):
    def __init__(self, klass: type, *args, **kwargs):
        callables = {
            name: (klass, name) for name in dir(klass) if callable(getattr(klass, name))
        }
        super().__init__(*args, callables=callables, **kwargs)
