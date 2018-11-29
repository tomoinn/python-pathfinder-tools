import logging
from argparse import ArgumentParser
from os import makedirs
from os.path import abspath
from pathlib import Path

from mapmaker import extract_images_from_pdf

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_argument('input_pdf', type=str, help='search INPUT_PDF for map images')
parser.add_argument('output_dir', type=str, help='write images to OUTPUT_DIR, will be created if not found')

options = parser.parse_args()

pdf_filename = abspath(options.input_pdf)
output_dir = abspath(options.output_dir)

if not Path(pdf_filename).is_file():
    logging.error('Input file {} not found, aborting'.format(pdf_filename))
    exit(1)

if not Path(output_dir).exists():
    logging.info('Creating new output directory {}'.format(output_dir))
    makedirs(output_dir)
elif not Path(output_dir).is_dir():
    logging.error('Output directory exists and is a file, aborting')
    exit(1)
else:
    logging.info('Using existing output directory {}'.format(output_dir))

for index, image in enumerate(extract_images_from_pdf(pdf_filename=pdf_filename,
                                                      min_height=100,
                                                      min_width=100,
                                                      min_file_size=1024 * 100)):
    image.save('{}/image-{}.png'.format(output_dir, index))

print("""Done - images written to {}. 

You should now remove any non-map images, and rename map images to match IMAGENAME_WWWxHHH.png
where WWW and HHH are the number of 1 inch squares across the width and height of the map 
respectively. For example, you might end up with a file 'canyon_12x8.png' for a map 12 tiles 
across and 8 high.
""".format(output_dir))
