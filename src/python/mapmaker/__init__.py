import math
import tempfile

from PIL import Image
from fpdf import FPDF

A4_WIDTH = 297  # A4 landscape width in mm
A4_HEIGHT = 210  # A4 landscape height in mm


def split_image(image_file, squares_wide, squares_high, border=5):
    """
    Split an input image into a set of images which will tile across A4 paper, either horizontally or vertically as
    determined by which would take the fewer pages when naively printed. At the moment this doesn't attempt to be
    clever and stack multiple small images on a single page.

    :param image_file:
        The path of the input image file, this should ideally be a PNG
    :param squares_wide:
        The number of 1 inch squares along the width of the input image
    :param squares_high:
        The number of 1 inch squares along the height of the input image
    :param border:
        The border to specify per printed page in mm, this is used to cope with printers not being able to print
        all the way up to the edge of the paper. Unlike some poster making tools, this is not a border for the assembled
        result, it's for each single page. It won't change the size of the output, but it may mean you need more paper
        to allow for that same size once the border is trimmed off. Defaults to 5mm for my LaserJet CP1515n.
    :return:
        A dict of {pixels_per_mm:int, images:{name : image}, orientation:str[L|P], border:int}
    """
    im = Image.open(image_file)
    width_pixels, height_pixels = im.size
    pixels_per_mm = min(width_pixels / (squares_wide * 25.4), height_pixels / (squares_high * 25.4))

    width_mm = width_pixels / pixels_per_mm
    height_mm = height_pixels / pixels_per_mm

    def get_page_size():

        pages_horizontal_l, pages_vertical_l = math.ceil(width_mm / (A4_WIDTH - border * 2)), math.ceil(
            height_mm / (A4_HEIGHT - border * 2))
        pages_horizontal_p, pages_vertical_p = math.ceil(width_mm / (A4_HEIGHT - border * 2)), math.ceil(
            height_mm / (A4_WIDTH - border * 2))

        if pages_horizontal_p * pages_vertical_p > pages_horizontal_l * pages_vertical_l:
            # Use landscape orientation
            return 'L', pages_horizontal_l, pages_vertical_l, A4_WIDTH - border * 2, A4_HEIGHT - border * 2
        else:
            # Use Portrait orientation
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
