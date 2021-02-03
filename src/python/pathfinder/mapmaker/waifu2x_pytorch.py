import torch
import torch.nn as nn
from PIL import Image
from torchvision.utils import make_grid
import logging
from pathfinder.mapmaker.pytorch import CARN_V2, network_to_half, ImageSplitter
import importlib.resources as resources

LOGGER = logging.getLogger('waifu2x')


class Waifu2x:
    """
    A class which wraps up the necessary calls to pytorch using the models created by
    https://github.com/yu45020/Waifu2x
    """

    @staticmethod
    def tensor_to_image(tensor, nrow=8, padding=2, normalize=False, range=None,
                        scale_each=False, pad_value=0):
        """
        Get a PIL Image from the supplied tensor
        """
        grid = make_grid(tensor, nrow=nrow, padding=padding, pad_value=pad_value,
                         normalize=normalize, range=range, scale_each=scale_each)
        # Add 0.5 after unnormalizing to [0, 255] to round to nearest integer
        ndarr = grid.mul(255).add_(0.5).clamp_(0, 255).permute(1, 2, 0).to('cpu', torch.uint8).numpy()
        return Image.fromarray(ndarr)

    def __init__(self):
        """
        Create the model and load in the checkpoint file. Attempts to check whether CUDA
        is available, using the CPU if not
        """
        LOGGER.info('Creating image scaler')
        checkpoint = resources.open_binary('pathfinder.mapmaker.pytorch',
                                           'CARN_model_checkpoint.pt')
        self.model = CARN_V2(color_channels=3, mid_channels=64, conv=nn.Conv2d,
                             single_conv_size=3, single_conv_group=1,
                             scale=2, activation=nn.LeakyReLU(0.1),
                             SEBlock=True, repeat_blocks=3, atrous=(1, 1, 1))
        self.model = network_to_half(self.model)
        self.model.load_state_dict(torch.load(checkpoint, 'cpu'))
        LOGGER.info(f'Loaded checkpoint from {checkpoint}')
        # Check whether CUDA is available, fall back to CPU otherwise
        self.cuda = torch.cuda.is_available()
        if self.cuda:
            active_device = torch.cuda.current_device()
            LOGGER.info('Available CUDA devices : ' + ','.join(
                [f'{i}={torch.cuda.get_device_name(i)}' for i in
                 range(torch.cuda.device_count())]) + f'; using device {active_device}')
            self.model = self.model.cuda()
        else:
            LOGGER.info('CUDA not available, using CPU for scaling')
            self.model = self.model.float()
        # Create an image splitter, use this to process the source image in tiles
        self.img_splitter = ImageSplitter(seg_size=64, scale_factor=2, boarder_pad_size=3)

    def scale(self, image: Image) -> Image:
        """
        Run a single scaling pass on the supplied image object, returning a scaled image
        """
        img_patches = self.img_splitter.split_img_tensor(image.convert('RGB'),
                                                         scale_method=None,
                                                         img_pad=0)
        with torch.no_grad():
            if self.cuda:
                out = [self.model(i.cuda()) for i in img_patches]
            else:
                out = [self.model(i) for i in img_patches]
        img_upscale = self.img_splitter.merge_img_tensor(out)
        return Waifu2x.tensor_to_image(img_upscale)
