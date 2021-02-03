import os
from os.path import abspath
import logging
from pathlib import Path
from importlib.resources import open_text
import yaml

logging.basicConfig(level=logging.INFO)


def ensure_dir(path, create=True):
    """
    Check that the given path exists, optionally creating it if not

    :param path: path to check
    :param create: create directories if not present
    :return: False if the path didn't exist and we didn't create it, or it existed already and was a file
    """
    if not Path(path).exists():
        if create:
            logging.info(f'Creating new path {path}')
            os.makedirs(path)
            return True
        else:
            logging.info(f'Path {path} does not exist, and create=False!')
            return False
    elif not Path(path).is_dir():
        logging.error(f'Path {path} exists but is a file!')
        return False
    else:
        logging.info(f'Path {path} already exists')
        return True


class Config:
    """
    Simple YAML based configuration
    """

    def __init__(self, separator='_'):
        """
        Config object, loads YAML utils from ~/.pathfinder/utils.yaml, creating directory
        and default configuration if not already present when invoked. Config values can be
        accessed through properties, using the supplied separator to indicate map traversal.

        :param separator: separator used when retrieving properties, defaults to '_'
        """
        # Create the ~/.pathfinder dir if it doesn't exist
        config_dir = os.path.expanduser('~/.pathfinder')
        if not Path(config_dir).exists():
            logging.info(f'Creating pathfinder config dir {config_dir}')
            os.makedirs(config_dir)
        config_file = f'{config_dir}/config.yaml'
        if not Path(config_file).exists():
            logging.info(f'No config file found, creating {config_file}')
            with open_text('pathfinder.utils', 'default_config.yaml') as default_config:
                config = yaml.load(default_config, Loader=yaml.FullLoader)
                with open(config_file, 'w') as config_file_obj:
                    yaml.dump(config, config_file_obj)
        with open(config_file, 'r') as file:
            self._config = yaml.load(file, Loader=yaml.FullLoader)
        self._separator = separator

    @property
    def dir(self):
        return os.path.expanduser('~/.pathfinder')

    def get(self, path, default=None):
        """
        Get a value from the utils, with a default to use if that key isn't found
        """
        try:
            return self.__getattr__(path)
        except AttributeError:
            return default

    def __getattr__(self, path):
        try:
            _item = self._config
            for name in path.split(self._separator):
                _item = _item[name]
            return _item
        except:
            raise AttributeError(f'No key \'{path}\' found in utils!')
