# This code is taken from https://github.com/yu45020/Waifu2x under GPL v3
# Many thanks to the author!

import copy
from contextlib import contextmanager
from math import sqrt, log

import torch
import torch.nn as nn
from PIL import Image
from torchvision.transforms.functional import to_tensor


class tofp16(nn.Module):
    def __init__(self):
        super(tofp16, self).__init__()

    def forward(self, input):
        if input.is_cuda:
            return input.half()
        else:  # PyTorch 1.0 doesn't support fp16 in CPU
            return input.float()


def BN_convert_float(module):
    if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
        module.float()
    for child in module.children():
        BN_convert_float(child)
    return module


def network_to_half(network):
    return nn.Sequential(tofp16(), BN_convert_float(network.half()))


class BaseModule(nn.Module):
    def __init__(self):
        self.act_fn = None
        super(BaseModule, self).__init__()

    def selu_init_params(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d) and m.weight.requires_grad:
                m.weight.data.normal_(0.0, 1.0 / sqrt(m.weight.numel()))
                if m.bias is not None:
                    m.bias.data.fill_(0)
            elif isinstance(m, nn.BatchNorm2d) and m.weight.requires_grad:
                m.weight.data.fill_(1)
                m.bias.data.zero_()

            elif isinstance(m, nn.Linear) and m.weight.requires_grad:
                m.weight.data.normal_(0, 1.0 / sqrt(m.weight.numel()))
                m.bias.data.zero_()

    def initialize_weights_xavier_uniform(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d) and m.weight.requires_grad:
                # nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='leaky_relu')
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d) and m.weight.requires_grad:
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def load_state_dict(self, state_dict, strict=True, self_state=False):
        own_state = self_state if self_state else self.state_dict()
        for name, param in state_dict.items():
            if name in own_state:
                try:
                    own_state[name].copy_(param.data)
                except Exception as e:
                    print("Parameter {} fails to load.".format(name))
                    print("-----------------------------------------")
                    print(e)
            else:
                print("Parameter {} is not in the model. ".format(name))

    @contextmanager
    def set_activation_inplace(self):
        if hasattr(self, 'act_fn') and hasattr(self.act_fn, 'inplace'):
            # save memory
            self.act_fn.inplace = True
            yield
            self.act_fn.inplace = False
        else:
            yield

    def total_parameters(self):
        total = sum([i.numel() for i in self.parameters()])
        trainable = sum([i.numel() for i in self.parameters() if i.requires_grad])
        print("Total parameters : {}. Trainable parameters : {}".format(total, trainable))
        return total

    def forward(self, *x):
        raise NotImplementedError


class CARN_Block(BaseModule):
    def __init__(self, channels, kernel_size=3, padding=1, dilation=1,
                 groups=1, activation=nn.SELU(), repeat=3,
                 SEBlock=False, conv=nn.Conv2d,
                 single_conv_size=1, single_conv_group=1):
        super(CARN_Block, self).__init__()
        m = []
        for i in range(repeat):
            m.append(ResidualFixBlock(channels, channels, kernel_size=kernel_size, padding=padding, dilation=dilation,
                                      groups=groups, activation=activation, conv=conv))
            if SEBlock:
                m.append(SpatialChannelSqueezeExcitation(channels, reduction=channels))
        self.blocks = nn.Sequential(*m)
        self.singles = nn.Sequential(
            *[ConvBlock(channels * (i + 2), channels, kernel_size=single_conv_size,
                        padding=(single_conv_size - 1) // 2, groups=single_conv_group,
                        activation=activation, conv=conv)
              for i in range(repeat)])

    def forward(self, x):
        c0 = x
        for block, single in zip(self.blocks, self.singles):
            b = block(x)
            c0 = c = torch.cat([c0, b], dim=1)
            x = single(c)

        return x


class CARN(BaseModule):
    # Fast, Accurate, and Lightweight Super-Resolution with Cascading Residual Network
    # https://github.com/nmhkahn/CARN-pytorch
    def __init__(self,
                 color_channels=3,
                 mid_channels=64,
                 scale=2,
                 activation=nn.SELU(),
                 num_blocks=3,
                 conv=nn.Conv2d):
        super(CARN, self).__init__()

        self.color_channels = color_channels
        self.mid_channels = mid_channels
        self.scale = scale

        self.entry_block = ConvBlock(color_channels, mid_channels, kernel_size=3, padding=1, activation=activation,
                                     conv=conv)
        self.blocks = nn.Sequential(
            *[CARN_Block(mid_channels, kernel_size=3, padding=1, activation=activation, conv=conv,
                         single_conv_size=1, single_conv_group=1)
              for _ in range(num_blocks)])
        self.singles = nn.Sequential(
            *[ConvBlock(mid_channels * (i + 2), mid_channels, kernel_size=1, padding=0,
                        activation=activation, conv=conv)
              for i in range(num_blocks)])

        self.upsampler = UpSampleBlock(mid_channels, scale=scale, activation=activation, conv=conv)
        self.exit_conv = conv(mid_channels, color_channels, kernel_size=3, padding=1)

    def forward(self, x):
        x = self.entry_block(x)
        c0 = x
        for block, single in zip(self.blocks, self.singles):
            b = block(x)
            c0 = c = torch.cat([c0, b], dim=1)
            x = single(c)
        x = self.upsampler(x)
        out = self.exit_conv(x)
        return out


class ConvBlock(BaseModule):
    def __init__(self, in_channels, out_channels, kernel_size=3, padding=1, dilation=1, groups=1,
                 activation=nn.SELU(), conv=nn.Conv2d):
        super(ConvBlock, self).__init__()
        self.m = nn.Sequential(conv(in_channels, out_channels, kernel_size, padding=padding,
                                    dilation=dilation, groups=groups),
                               activation)

    def forward(self, x):
        return self.m(x)


class ResidualFixBlock(BaseModule):
    def __init__(self, in_channels, out_channels, kernel_size=3, padding=1, dilation=1,
                 groups=1, activation=nn.SELU(), conv=nn.Conv2d):
        super(ResidualFixBlock, self).__init__()
        self.act_fn = activation
        self.m = nn.Sequential(
            conv(in_channels, out_channels, kernel_size, padding=padding, dilation=dilation, groups=groups),
            activation,
            # conv(out_channels, out_channels, kernel_size, padding=(kernel_size - 1) // 2, dilation=1, groups=groups),
            conv(in_channels, out_channels, kernel_size, padding=padding, dilation=dilation, groups=groups),
        )

    def forward(self, x):
        out = self.m(x)
        return self.act_fn(out + x)


class UpSampleBlock(BaseModule):
    def __init__(self, channels, scale, activation, atrous_rate=1, conv=nn.Conv2d):
        assert scale in [2, 4, 8], "Currently UpSampleBlock supports 2, 4, 8 scaling"
        super(UpSampleBlock, self).__init__()
        m = nn.Sequential(
            conv(channels, 4 * channels, kernel_size=3, padding=atrous_rate, dilation=atrous_rate),
            activation,
            nn.PixelShuffle(2)
        )
        self.m = nn.Sequential(*[m for _ in range(int(log(scale, 2)))])

    def forward(self, x):
        return self.m(x)


class SpatialChannelSqueezeExcitation(BaseModule):
    # https://arxiv.org/abs/1709.01507
    # https://arxiv.org/pdf/1803.02579v1.pdf
    def __init__(self, in_channel, reduction=16, activation=nn.ReLU()):
        super(SpatialChannelSqueezeExcitation, self).__init__()
        linear_nodes = max(in_channel // reduction, 4)  # avoid only 1 node case
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.channel_excite = nn.Sequential(
            # check the paper for the number 16 in reduction. It is selected by experiment.
            nn.Linear(in_channel, linear_nodes),
            activation,
            nn.Linear(linear_nodes, in_channel),
            nn.Sigmoid()
        )
        self.spatial_excite = nn.Sequential(
            nn.Conv2d(in_channel, 1, kernel_size=1, stride=1, padding=0, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, h, w = x.size()
        #
        channel = self.avg_pool(x).view(b, c)
        # channel = F.avg_pool2d(x, kernel_size=(h,w)).view(b,c) # used for porting to other frameworks
        cSE = self.channel_excite(channel).view(b, c, 1, 1)
        x_cSE = torch.mul(x, cSE)

        # spatial
        sSE = self.spatial_excite(x)
        x_sSE = torch.mul(x, sSE)
        # return x_sSE
        return torch.add(x_cSE, x_sSE)


class CARN_V2(CARN):
    def __init__(self, color_channels=3, mid_channels=64,
                 scale=2, activation=nn.LeakyReLU(0.1),
                 SEBlock=True, conv=nn.Conv2d,
                 atrous=(1, 1, 1), repeat_blocks=3,
                 single_conv_size=3, single_conv_group=1):
        super(CARN_V2, self).__init__(color_channels=color_channels, mid_channels=mid_channels, scale=scale,
                                      activation=activation, conv=conv)

        num_blocks = len(atrous)
        m = []
        for i in range(num_blocks):
            m.append(CARN_Block(mid_channels, kernel_size=3, padding=1, dilation=1,
                                activation=activation, SEBlock=SEBlock, conv=conv, repeat=repeat_blocks,
                                single_conv_size=single_conv_size, single_conv_group=single_conv_group))

        self.blocks = nn.Sequential(*m)

        self.singles = nn.Sequential(
            *[ConvBlock(mid_channels * (i + 2), mid_channels, kernel_size=single_conv_size,
                        padding=(single_conv_size - 1) // 2, groups=single_conv_group,
                        activation=activation, conv=conv)
              for i in range(num_blocks)])

    def forward(self, x):
        x = self.entry_block(x)
        c0 = x
        res = x
        for block, single in zip(self.blocks, self.singles):
            b = block(x)
            c0 = c = torch.cat([c0, b], dim=1)
            x = single(c)
        x = x + res
        x = self.upsampler(x)
        out = self.exit_conv(x)
        return out


class ImageSplitter:
    # key points:
    # Boarder padding and over-lapping img splitting to avoid the instability of edge value
    # Thanks Waifu2x's autorh nagadomi for suggestions (https://github.com/nagadomi/waifu2x/issues/238)

    def __init__(self, seg_size=48, scale_factor=2, boarder_pad_size=3):
        self.seg_size = seg_size
        self.scale_factor = scale_factor
        self.pad_size = boarder_pad_size
        self.height = 0
        self.width = 0
        self.upsampler = nn.Upsample(scale_factor=scale_factor, mode='bilinear')

    def split_img_tensor(self, pil_img, scale_method=Image.BILINEAR, img_pad=0):
        # resize image and convert them into tensor
        img_tensor = to_tensor(pil_img).unsqueeze(0)
        img_tensor = nn.ReplicationPad2d(self.pad_size)(img_tensor)
        batch, channel, height, width = img_tensor.size()
        self.height = height
        self.width = width

        if scale_method is not None:
            img_up = pil_img.resize((2 * pil_img.size[0], 2 * pil_img.size[1]), scale_method)
            img_up = to_tensor(img_up).unsqueeze(0)
            img_up = nn.ReplicationPad2d(self.pad_size * self.scale_factor)(img_up)

        patch_box = []
        # avoid the residual part is smaller than the padded size
        if height % self.seg_size < self.pad_size or width % self.seg_size < self.pad_size:
            self.seg_size += self.scale_factor * self.pad_size

        # split image into over-lapping pieces
        for i in range(self.pad_size, height, self.seg_size):
            for j in range(self.pad_size, width, self.seg_size):
                part = img_tensor[:, :,
                       (i - self.pad_size):min(i + self.pad_size + self.seg_size, height),
                       (j - self.pad_size):min(j + self.pad_size + self.seg_size, width)]
                if img_pad > 0:
                    part = nn.ZeroPad2d(img_pad)(part)
                if scale_method is not None:
                    # part_up = self.upsampler(part)
                    part_up = img_up[:, :,
                              self.scale_factor * (i - self.pad_size):min(i + self.pad_size + self.seg_size,
                                                                          height) * self.scale_factor,
                              self.scale_factor * (j - self.pad_size):min(j + self.pad_size + self.seg_size,
                                                                          width) * self.scale_factor]

                    patch_box.append((part, part_up))
                else:
                    patch_box.append(part)
        return patch_box

    def merge_img_tensor(self, list_img_tensor):
        out = torch.zeros((1, 3, self.height * self.scale_factor, self.width * self.scale_factor))
        img_tensors = copy.copy(list_img_tensor)
        rem = self.pad_size * 2

        pad_size = self.scale_factor * self.pad_size
        seg_size = self.scale_factor * self.seg_size
        height = self.scale_factor * self.height
        width = self.scale_factor * self.width
        for i in range(pad_size, height, seg_size):
            for j in range(pad_size, width, seg_size):
                part = img_tensors.pop(0)
                part = part[:, :, rem:-rem, rem:-rem]
                # might have error
                if len(part.size()) > 3:
                    _, _, p_h, p_w = part.size()
                    out[:, :, i:i + p_h, j:j + p_w] = part
                # out[:,:,
                # self.scale_factor*i:self.scale_factor*i+p_h,
                # self.scale_factor*j:self.scale_factor*j+p_w] = part
        out = out[:, :, rem:-rem, rem:-rem]
        return out
