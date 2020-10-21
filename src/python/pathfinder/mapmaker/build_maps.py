import logging
from argparse import ArgumentParser
from os import scandir
from os.path import abspath, isfile
from pathfinder.utils import ensure_dir, Config
from pathfinder.mapmaker.waifu2x_pytorch import Waifu2x
from PIL import Image

from pathfinder import mapmaker

logging.basicConfig(level=logging.INFO)

conf = Config()

parser = ArgumentParser()
parser.add_argument('input_dir', type=str, help='search INPUT_DIR for map images of form name_WWxHH.png')
parser.add_argument('output_dir', nargs='?', type=str,
                    help='write images to OUTPUT_DIR, will be created if not found. ' + 'If not supplied, will use input_dir.',
                    default=None)

parser.add_argument('-c', '--colour', type=float, help=f'saturation, 0.0-2.0, default {conf.map_default_colour}',
                    default=conf.map_default_colour)
parser.add_argument('-s', '--sharpen', type=float, help=f'sharpen, 0.0-2.0, default {conf.map_default_sharpen}',
                    default=conf.map_default_sharpen)
parser.add_argument('-b', '--brighten', type=float, help=f'brighten, 0.0-2.0, default {conf.map_default_brighten}',
                    default=conf.map_default_brighten)
parser.add_argument('-g', '--gridsize', type=int,
                    help=f'target grid size in pixels, images will be scaled up until this is exceeded, default {conf.map_default_gridsize}',
                    default=conf.map_default_gridsize)
parser.add_argument('-p', '--padding', type=float,
                    help=f'tiled mode only - padding per output page in mm, default {conf.map_default_padding}',
                    default=conf.map_default_padding)
parser.add_argument('-o', '--overlap', type=float,
                    help=f'tiled and single modes only - overlap on bottom right edges in mm, default {conf.map_default_overlap}',
                    default=conf.map_default_overlap)
parser.add_argument('-a', '--paper_size', type=str,
                    help=f'tiled mode only - paper size from [{"|".join([p.name for p in mapmaker.Paper])}], default {conf.map_default_paper}',
                    default=conf.map_default_paper)
parser.add_argument('-m', '--mode', type=str,
                    help=f'mode, from [tiled|single|png], default {conf.map_default_mode}. Tiled mode produces a multi-page PDF with pages ' +
                         'of the requested size. Single mode produces a single PDF exactly fitting the map, and PNG mode produces a lower size PNG ' +
                         'image suitable for virtual tabletops such as Roll20',
                    default=conf.map_default_mode)
parser.add_argument('-x', '--preset', type=str,
                    help=f'preset, overrides settings from presets within the config file, available presets are [{"|".join(conf.map_presets.keys())}]',
                    default=None)


def main():
    options = parser.parse_args()

    waifu2x = Waifu2x()

    # Get directories - if the output DIR isn't specified we use the same as the input
    input_dir = abspath(options.input_dir)
    if options.output_dir is None:
        output_dir = input_dir
    else:
        output_dir = abspath(options.output_dir)
    # Check and build input / output directories
    if not ensure_dir(input_dir, create=False):
        exit(1)
    if not ensure_dir(output_dir):
        exit(1)

    # Get values from command line parser
    page_border = options.padding
    saturation = options.colour
    sharpen = options.sharpen
    brighten = options.brighten
    overlap = options.overlap
    mode = options.mode
    specified_paper_size = options.paper_size
    gridsize = options.gridsize

    # Load from presets if specified
    if options.preset is not None:
        p = f'map_presets_{options.preset}_'
        page_border = conf.get(p + 'border', default=page_border)
        saturation = conf.get(p + 'saturation', default=saturation)
        sharpen = conf.get(p + 'sharpen', default=sharpen)
        brighten = conf.get(p + 'brighten', default=brighten)
        overlap = conf.get(p + 'overlap', default=overlap)
        specified_paper_size = conf.get(p + 'paper', default=specified_paper_size)
        mode = conf.get(p + 'mode', default=mode)
        gridsize = conf.get(p + 'gridsize', default=gridsize)

    # Try to parse out paper size
    try:
        paper_size = mapmaker.Paper[specified_paper_size.upper()]
    except KeyError:
        logging.info(f'Paper size {options.paper_size} not found.')
        paper_size = None

    # Fail if we're in tiled mode and there's no paper size defined
    if paper_size is None and mode.upper() == 'TILED':
        logging.error('Tiled mode requires a valid paper size, aborting')
        exit(0)

    def run_waifu2x(i: Image) -> Image:
        # Scale up until we have the right gridsize
        while (i.size[0] < width * gridsize):
            i = waifu2x.scale(i)
        # Then scale the image back down to the target size
        return i.resize((int(width * gridsize), int(height * gridsize)), resample=Image.LANCZOS)

    for entry in scandir(path=input_dir):
        try:
            logging.info(f'entry = {entry}')
            filename, _, name, width, height = mapmaker.parse_filename(abspath(input_dir + '/' + entry.name))
            logging.info(f'Processing {name}, width={width}, height={height}, mode={mode}')

            if mode.upper() == 'PNG':
                png_filename = f'{output_dir}/{name}_c{saturation}s{sharpen}b{brighten}_{width}x{height}.png'
                if not isfile(png_filename):
                    image = Image.open(filename)
                    image = run_waifu2x(image)
                    image = mapmaker.basic_image_ops(image, brighten, sharpen, saturation)
                    image.save(fp=png_filename, format='PNG')
                else:
                    logging.info(f'File {png_filename} already exists, skipping.')

            elif mode.upper() == 'SINGLE':
                pdf_filename = f'{output_dir}/{name}_exact_p{page_border}c{saturation}s{sharpen}b{brighten}.pdf'
                if not isfile(pdf_filename):
                    image = Image.open(filename)
                    image = run_waifu2x(image)
                    image_spec = mapmaker.process_image_with_border(im=image, squares_wide=width,
                                                                    squares_high=height,
                                                                    border_north=page_border,
                                                                    border_east=page_border,
                                                                    border_south=page_border,
                                                                    border_west=page_border,
                                                                    brighten=brighten, sharpen=sharpen,
                                                                    saturation=saturation)
                    mapmaker.make_single_page_pdf(image_spec, pdf_filename)
                else:
                    logging.info(f'File {pdf_filename} already exists, skipping.')

            elif mode.upper() == 'TILED':
                pdf_filename = f'{output_dir}/{name}_{paper_size.name}_p{page_border}c{saturation}s{sharpen}b{brighten}o{overlap}.pdf'
                if not isfile(pdf_filename):
                    image = Image.open(filename)
                    image = run_waifu2x(image)
                    split = mapmaker.split_image(im=image, squares_wide=width, squares_high=height,
                                                 border_north=page_border, border_east=page_border,
                                                 border_south=page_border,
                                                 border_west=page_border,
                                                 brighten=brighten, sharpen=sharpen, saturation=saturation,
                                                 overlap_east=overlap,
                                                 overlap_south=overlap, paper=paper_size)
                    mapmaker.make_pdf(split, pdf_filename)
                else:
                    logging.info(f'File {pdf_filename} already exists, skipping.')

        except ValueError:
            logging.debug('Unable to parse details from {}, skipping'.format(entry.name))
