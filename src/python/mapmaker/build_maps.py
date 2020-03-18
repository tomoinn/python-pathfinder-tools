import logging
from argparse import ArgumentParser
from os import makedirs, scandir
from os.path import abspath, isfile
from pathlib import Path

from PIL import Image

import mapmaker

mapmaker.WAIFU2X_LUA_PATH = '/home/tom/git/waifu2x/waifu2x.lua'
mapmaker.TORCH_PATH = '/home/tom/torch/install/bin/th'
# mapmaker.WAIFU2X_MACOS_PATH = '/Users/tom/waifu2x-mac-cli/waifu2x'

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_argument('input_dir', type=str, help='search INPUT_DIR for map images of form name_WWxHH.png')
parser.add_argument('output_dir', nargs='?', type=str, help='write images to OUTPUT_DIR, will be created if not found',
                    default=None)
parser.add_argument('-p', '--padding', type=float, help='padding per output page in mm, default 5mm', default=5)
parser.add_argument('-o', '--overlap', type=float, help='overlap on bottom right edges in mm, default 3mm', default=3)
parser.add_argument('-c', '--colour', type=float, help='saturation, 0.0-2.0, default 1.0')
parser.add_argument('-s', '--sharpen', type=float, help='sharpen, 0.0-2.0, default 1.1', default=1.1)
parser.add_argument('-b', '--brighten', type=float, help='brighten, 0.0-2.0, default 1.2', default=1.2)
parser.add_argument('-a', '--paper_size', type=str, help='Paper size, either A0..A4 or "exact" for no tiling',
                    default='A4')
parser.add_argument('-x', '--preset', type=str, help='preset, overrides all settings, currently [library]',
                    default=None)


def main():
    options = parser.parse_args()

    input_dir = abspath(options.input_dir)
    if options.output_dir is None:
        output_dir = input_dir
    else:
        output_dir = abspath(options.output_dir)
    page_border = options.padding
    saturation = options.colour
    sharpen = options.sharpen
    brighten = options.brighten
    overlap = options.overlap
    try:
        paper_size = mapmaker.Paper[options.paper_size.upper()]
    except KeyError:
        paper_size = None

    if options.preset is not None:
        # Ely library A3 colour printer settings
        if options.preset.lower() == 'library':
            page_border = 10
            saturation = 1.0
            sharpen = 1.1
            brighten = 1.0
            paper_size = mapmaker.Paper.A3

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
            logging.info(f'Processing {name}, width={width}, height={height}')
            if paper_size is not None:
                pdf_filename = f'{output_dir}/{name}_{paper_size.name}_p{page_border}c{saturation}s{sharpen}b{brighten}o{overlap}.pdf'
            else:
                pdf_filename = f'{output_dir}/{name}_exact_p{page_border}c{saturation}s{sharpen}b{brighten}.pdf'
            if not isfile(pdf_filename):
                image = Image.open(filename)
                image = mapmaker.run_waifu2x(image, scale=True, noise=2)
                image = mapmaker.run_waifu2x(image, scale=True, noise=None)
                if paper_size is not None:
                    split = mapmaker.split_image(im=image, squares_wide=width, squares_high=height,
                                                 border_north=page_border, border_east=page_border,
                                                 border_south=page_border,
                                                 border_west=page_border,
                                                 brighten=brighten, sharpen=sharpen, saturation=saturation,
                                                 overlap_east=overlap,
                                                 overlap_south=overlap, paper=paper_size)
                    mapmaker.make_pdf(split, pdf_filename)
                else:
                    image_spec = mapmaker.process_image_with_border(im=image, squares_wide=width, squares_high=height,
                                                                    border_north=page_border, border_east=page_border,
                                                                    border_south=page_border,
                                                                    border_west=page_border,
                                                                    brighten=brighten, sharpen=sharpen,
                                                                    saturation=saturation)
                    mapmaker.make_single_page_pdf(image_spec, pdf_filename)
            else:
                logging.info(f'File {pdf_filename} already exists, skipping.')
        except ValueError:
            logging.debug('Unable to parse details from {}, skipping'.format(entry.name))
