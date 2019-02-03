import logging
import math
import re
import subprocess
import tempfile
from os import scandir, stat
from os.path import dirname, basename, abspath, isfile
from pathlib import Path

from PIL import Image, ImageEnhance
from fpdf import FPDF
from skimage.restoration import denoise_tv_chambolle as denoise

A4_WIDTH = 297  # A4 landscape width in mm
A4_HEIGHT = 210  # A4 landscape height in mm

TORCH_PATH = None
WAIFU2X_LUA_PATH = None
WAIFU2X_MACOS_PATH = None


def parse_filename(filename):
    """
    Parse a filename of the form name_WWxHH.png, i.e. deep_canyon_10x18.png, into a set of useful properties. Returns
    a tuple containing the canonical filename supplied, the canonical name of the pdf to produce, the plain name with
    the sizes stripped, and the width and height specified.

    :param filename:
        Filename to parse
    :return:
        A tuple of (filename, pdf_name, name, width, height)
    :raise:
        ValueError if the string can't be parsed in this format
    """
    filename = abspath(filename)
    leaf_name = basename(filename)
    m = re.match(r'(^\w+?)_*(\d+(?:\.\d*)?|\.\d+)x(\d+(?:\.\d*)?|\.\d+)\.png',
                 leaf_name)
    if m:
        name = m.groups()[0]
        width = float(m.groups()[1])
        height = float(m.groups()[2])
        pdf_name = dirname(filename) + '/' + name + '.pdf'
        return filename, pdf_name, name, width, height
    else:
        raise ValueError('Filename not of the form name_WxH.png, was {}'.format(leaf_name))


def split_image(im: Image, squares_wide: float, squares_high: float, border=5, brighten=None, sharpen=None,
                saturation=None):
    """
    Split an input image into a set of images which will tile across A4 paper, either horizontally or vertically as
    determined by which would take the fewer pages when naively printed. At the moment this doesn't attempt to be
    clever and stack multiple small images on a single page.

    :param im:
        An Image to process
    :param squares_wide:
        The number of 1 inch squares along the width of the input image
    :param squares_high:
        The number of 1 inch squares along the height of the input image
    :param border:
        The border to specify per printed page in mm, this is used to cope with printers not being able to print
        all the way up to the edge of the paper. Unlike some poster making tools, this is not a border for the assembled
        result, it's for each single page. It won't change the size of the output, but it may mean you need more paper
        to allow for that same size once the border is trimmed off. Defaults to 5mm for my LaserJet CP1515n.
    :param brighten:
        Set to >1.0 to brighten the image before splitting, <1.0 to darken, or leave as None for no effect
    :param sharpen:
        Set to >1.0 to shapen the image before splitting.
    :param saturation:
        Set to >1.0 to enhance colour, <1.0 to remove it, None for no effect
    :return:
        A dict of {pixels_per_mm:int, images:{name : image}, orientation:str[L|P], border:int}
    """

    width_pixels, height_pixels = im.size
    logging.info('split_image: Image is {} x {} pixels'.format(width_pixels, height_pixels))
    pixels_per_mm = min(width_pixels / (squares_wide * 25.4), height_pixels / (squares_high * 25.4))
    logging.info('split_image: Calculated {} pixels per mm'.format(pixels_per_mm))

    # Apply enhancements if required
    if brighten is not None:
        logging.info('split_image: Applying brighten {}'.format(brighten))
        im = ImageEnhance.Brightness(im).enhance(brighten)
    if sharpen is not None:
        logging.info('split_image: Applying sharpen {}'.format(sharpen))
        im = ImageEnhance.Sharpness(im).enhance(sharpen)
    if saturation is not None:
        logging.info('split_image: Applying saturation {}'.format(saturation))
        im = ImageEnhance.Color(im).enhance(saturation)

    width_mm = width_pixels / pixels_per_mm
    height_mm = height_pixels / pixels_per_mm

    def get_page_size():

        pages_horizontal_l, pages_vertical_l = math.ceil(width_mm / (A4_WIDTH - border * 2)), math.ceil(
            height_mm / (A4_HEIGHT - border * 2))
        pages_horizontal_p, pages_vertical_p = math.ceil(width_mm / (A4_HEIGHT - border * 2)), math.ceil(
            height_mm / (A4_WIDTH - border * 2))

        if pages_horizontal_p * pages_vertical_p > pages_horizontal_l * pages_vertical_l:
            # Use landscape orientation
            logging.info(
                'split_image: Using landscape orientation, {} by {} pages'.format(pages_horizontal_l, pages_vertical_l))
            return 'L', pages_horizontal_l, pages_vertical_l, A4_WIDTH - border * 2, A4_HEIGHT - border * 2
        else:
            # Use Portrait orientation
            logging.info(
                'split_image: Using portrait orientation, {} by {} pages'.format(pages_horizontal_p, pages_vertical_p))
            return 'P', pages_horizontal_p, pages_vertical_p, A4_HEIGHT - border * 2, A4_WIDTH - border * 2

    orientation, pages_horizontal, pages_vertical, page_width, page_height = get_page_size()

    pixel_width_page = page_width * pixels_per_mm
    pixel_height_page = page_height * pixels_per_mm

    def crop_for(page_x, page_y):
        return im.crop((page_x * pixel_width_page, page_y * pixel_height_page,
                        min(width_pixels, (page_x + 1) * pixel_width_page),
                        min(height_pixels, (page_y + 1) * pixel_height_page)))

    return {'pixels_per_mm': pixels_per_mm,
            'images': {'{}_{}'.format(x, y): crop_for(x, y) for x in range(pages_horizontal) for y in
                       range(pages_vertical)},
            'orientation': orientation,
            'border': border}


def make_pdf(images, pdf_filename):
    """
    Write a set of images from split_images into a combined A4 PDF file

    :param images:
        The output dict from split_images
    :param pdf_filename:
        Full name of the PDF to write
    """
    logging.info('make_pdf: Building PDF file {} from image data'.format(pdf_filename))
    pdf = FPDF(orientation=images['orientation'], unit='mm', format='A4')
    ppm = images['pixels_per_mm']
    with tempfile.TemporaryDirectory() as dirpath:
        for coords, image in images['images'].items():
            pdf.add_page()
            im_width, im_height = image.size
            image.save('{}/{}.png'.format(dirpath, coords))
            pdf.image('{}/{}.png'.format(dirpath, coords), images['border'], images['border'], im_width / ppm,
                      im_height / ppm)
    pdf.output(pdf_filename, 'F')
    logging.info('make_pdf: Wrote {} images to PDF file {}'.format(len(images['images']), pdf_filename))


def extract_images_from_pdf(pdf_filename: str, page=None, to_page=None, min_width=100, min_height=100,
                            min_file_size=1024 * 500):
    """
    Uses the pdfimages tool from poppler-utils to extract images from a given page of the specified PDF.

    :param pdf_filename:
        Full path of the PDF to use. Specify your pathfinder scenario PDF here.
    :param page:
        Page number to scan, None to scan all pages
    :param to_page:
        Page number up to which to scan, ignored if page is None, if left at the default this is set to whatever value
        page is set to to scan a single page, otherwise a range of pages can be specified from 'page' to 'to_page'
        inclusive
    :param min_width:
        Minimum image width to include in the output iterator, defaults to 100 pixels
    :param min_height:
        Minimum image height to include in the output iterator, defaults to 100 pixels
    :param min_file_size:
        Minimum file size to include in the output iterator, defaults to 100K
    :return:
        A lazy iterator over image objects corresponding to matching images
    """
    with tempfile.TemporaryDirectory() as dir:
        command = ['pdfimages', '-png']
        if page is not None and to_page is None:
            to_page = page
        if page is not None:
            command.extend(['-f', str(page), '-l', str(to_page)])
        command.extend([pdf_filename, dir + '/image'])
        logging.info('extract_images_from_pdf: ' + ' '.join(command))
        subprocess.run(command, shell=False, check=True, capture_output=True)
        logging.info('extract_images_from_pdf: dir={}'.format(dir))
        for entry in scandir(path=dir):
            filesize = stat(dir + '/' + entry.name).st_size
            if entry.name.endswith('png') and not entry.is_dir() and filesize >= min_file_size:
                im = Image.open(dir + '/' + entry.name)
                width, height = im.size
                if width >= min_width and height >= min_height and im.mode == 'RGB':
                    logging.info(
                        'extract_images_from_pdf: found {} - {} by {} with size {} bytes'.format(entry.name, width,
                                                                                                 height, filesize))
                    image_number = int(entry.name[6:9])
                    mask_name = f'image-{image_number + 1:03d}.png'
                    if isfile(dir + '/' + mask_name):
                        mask_im = Image.open(dir + '/' + mask_name)
                        mask_width, mask_height = mask_im.size
                        if mask_width == width and mask_height == height and mask_im.mode == 'L':
                            logging.info(f'Found possible mask, mode is {mask_im.mode}, '
                                         f'filename {mask_name}, combining')
                            mask_command = ['convert', dir + '/' + entry.name, dir + '/' + mask_name, '-compose',
                                            'CopyOpacity', '-composite', dir + '/' + entry.name]
                            subprocess.run(mask_command, shell=False, check=True, capture_output=True)
                            im = Image.open(dir + '/' + entry.name)
                    yield im


def total_variation_denoise(image: Image, weight: int = 10) -> Image:
    return denoise(image, weight=weight, multichannel=True)


def run_waifu2x(image: Image, waifu2x_lua_path=None, torch_path=None, waifu2x_macos_path=None, scale=True, noise=0,
                force_cudnn=True) -> Image:
    """
    Call an existing instance of the waifu2x tool. Requires that this tool is properly installed along with torch,
    CUDA etc. Creates a temporary directory, writes the image file to it, runs waifu2x then reads back the result and
    returns it as an image object. See https://github.com/nagadomi/waifu2x for details on how to build and configure
    the tools.

    :param image:
        An image object to use as input
    :param waifu2x_lua_path:
        The full path to the waifu2x.lua file. If omitted this uses the module level WAIFU2X_LUA_PATH value
    :param torch_path:
        The full path to the 'th' executable. If omitted this uses the module level TORCH_PATH value
    :param waifu2x_macos_path:
        If set, this specifies the location of the command line macos version of waifu2x from
        https://github.com/imxieyi/waifu2x-mac/releases - this has slightly different command line usage so need to be
        handled differently
    :param scale:
        Set to True to scale by 2x, false to leave the size as is
    :param noise:
        Set to non-None to add de-noise
    :param force_cudnn:
        Set to True to force use of the cudnn library, providing a minor speed boost
    :return:
        The enhanced image
    """

    if waifu2x_lua_path is None:
        waifu2x_lua_path = WAIFU2X_LUA_PATH
    if torch_path is None:
        torch_path = TORCH_PATH

    if waifu2x_lua_path is not None:
        if not Path(waifu2x_lua_path).is_file():
            logging.info('run_waifu2x: No waifu2x lua script at {}'.format(waifu2x_lua_path))
            waifu2x_lua_path = None

    if torch_path is not None:
        if not Path(torch_path).is_file():
            logging.info('run_waifu2x: No torch executable at {}'.format(torch_path))
            torch_path = None

    if waifu2x_macos_path is None:
        waifu2x_macos_path = WAIFU2X_MACOS_PATH

    command = []

    if waifu2x_macos_path is None:

        if waifu2x_lua_path is None or torch_path is None or (scale is False and noise is None):
            # If no waifu2x specified, or nothing to do, just return the original image
            logging.info('run_waifu2x: Nothing to do, or tools unavailable, for waifu2x')
            return image

        command.extend([torch_path, waifu2x_lua_path, '-m'])

        if scale:
            if noise is None:
                command.append('scale')
            else:
                command.append('noise_scale')
        else:
            command.append('noise')

        if noise is not None:
            command.extend(['-noise_level', str(noise)])

        if force_cudnn:
            command.extend(['-force_cudnn', '1'])

    else:

        command.append(waifu2x_macos_path)

        if not Path(waifu2x_macos_path).is_file():
            logging.info('run_waifu2x: No waifu2x executable at {}'.format(waifu2x_macos_path))
            return image

        if scale:
            command.extend(['-s', '2'])
        else:
            command.extend(['-s', '1'])

        if noise is None:
            noise = 0

        command.extend(['-n', str(noise)])

    with tempfile.TemporaryDirectory() as dir:
        source = dir + '/source.png'
        dest = dir + '/dest.png'
        command.extend(['-i', source, '-o', dest])
        logging.info('run_waifu2x: Writing original image to {}'.format(source))
        image.save(source)
        logging.info('run_waifu2x: Running waifu2x: {}'.format(' '.join(command)))
        if waifu2x_lua_path is not None:
            subprocess.run(command, shell=False, check=True, cwd=dirname(waifu2x_lua_path), capture_output=True)
        else:
            subprocess.run(command, shell=False, check=True, cwd=dirname(waifu2x_macos_path), capture_output=True)
        logging.info('run_waifu2x: Completed, opening enhanced image from {}'.format(dest))
        return Image.open(dest)
