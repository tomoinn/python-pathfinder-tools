from PIL import Image
from guizero import App, Picture
from pathlib import Path
import logging
from pathfinder.mapmaker import ImageGrid
from argparse import ArgumentParser
from os import scandir
from os.path import abspath, isfile
from pathfinder.utils import ensure_dir, Config
import logging

logging.basicConfig(level=logging.INFO)
parser = ArgumentParser()

parser.add_argument('input_dir', type=str, help='search INPUT_DIR for map images of form NAME.png')
parser.add_argument('output_dir', nargs='?', type=str,
                    help='write images to OUTPUT_DIR, will be created if not found. ' +
                         'If not supplied, will use INPUT_DIR',
                    default=None)


def main():
    options = parser.parse_args()
    input_dir = abspath(options.input_dir)
    if options.output_dir is None:
        output_dir = input_dir
    else:
        output_dir = abspath(options.output_dir)
    # Check and build input and output directories as needed
    if not ensure_dir(input_dir, create=False):
        exit(1)
    if not ensure_dir(output_dir):
        exit(1)

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    for input_file in input_path.iterdir():
        ImageGrid.show_and_crop(input_file, output_path)
