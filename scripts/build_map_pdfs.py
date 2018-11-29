import logging
from argparse import ArgumentParser
from os import makedirs, scandir
from os.path import abspath
from pathlib import Path

from PIL import Image

import mapmaker

mapmaker.WAIFU2X_LUA_PATH = '/home/tom/git/waifu2x/waifu2x.lua'
mapmaker.TORCH_PATH = '/home/tom/torch/install/bin/th'
# mapmaker.WAIFU2X_MACOS_PATH = '/Users/tom/waifu2x-mac-cli/waifu2x'

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_argument('input_dir', type=str, help='search INPUT_DIR for map images of form name_WWxHH.png')
parser.add_argument('output_dir', type=str, help='write images to OUTPUT_DIR, will be created if not found')
parser.add_argument('-p', '--padding', type=float, help='padding per output page in mm, default 5mm', default=5)
parser.add_argument('-c', '--colour', type=float, help='saturation, 0.0-2.0, default 1.0')
parser.add_argument('-s', '--sharpen', type=float, help='sharpen, 0.0-2.0, default 1.1', default=1.1)
parser.add_argument('-b', '--brighten', type=float, help='brighten, 0.0-2.0, default 1.2', default=1.2)

options = parser.parse_args()

input_dir = abspath(options.input_dir)
output_dir = abspath(options.output_dir)
page_border = options.padding
saturation = options.colour
sharpen = options.sharpen
brighten = options.brighten

if not Path(input_dir).is_dir():
    logging.error('Input directory {} not found, aborting'.format(input_dir))
    exit(1)

if not Path(output_dir).exists():
    logging.info('Creating new output directory {}'.format(output_dir))
    makedirs(output_dir)
elif not Path(output_dir).is_dir():
    logging.error('Output directory exists and is a file, aborting')
    exit(1)
else:
    logging.info('Using existing output directory {}'.format(output_dir))

for entry in scandir(path=input_dir):
    try:
        filename, _, name, width, height = mapmaker.parse_filename(abspath(input_dir + '/' + entry.name))
        pdf_filename = '{}/{}.pdf'.format(output_dir, name)
        image = Image.open(filename)
        image = mapmaker.run_waifu2x(image, scale=True, noise=2)
        image = mapmaker.run_waifu2x(image, scale=True, noise=None)
        split = mapmaker.split_image(im=image, squares_wide=width, squares_high=height,
                                     border=page_border, brighten=brighten, sharpen=sharpen, saturation=saturation)
        mapmaker.make_pdf(split, pdf_filename)
    except ValueError:
        logging.warning('Unable to parse details from {}, skipping'.format(entry.name))
