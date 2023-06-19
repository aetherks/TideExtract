#Source: https://github.com/milesial/Pytorch-UNet
#also adds a mix pool layer
import torch
import torch.nn as nn
import torch.nn.functional as F

class MixPool2d(nn.Module):

    def __init__(self, planes):
        super(MixPool2d, self).__init__()
        self.avpool = nn.AvgPool2d(2)
        self.maxpool = nn.MaxPool2d(2)
        self.conv1 = nn.Conv2d(2*planes, planes, 1, padding=0, bias=True)

    def forward(self, x):
        x1 = self.avpool(x)
        x2 = self.maxpool(x)
        out = torch.cat([x1, x2],1)
        return self.conv1(out)

class TemporalEncoding(nn.Module):
    
    def __init__(self, n_emb = 100):
        super().__init__()
        
        self.inp = nn.Linear(1, 2*n_emb)
        #self.act = nn.SiLU()
        self.act = torch.sin
        self.out = nn.Linear(2*n_emb, n_emb)
    
    def forward(self, t):
        return self.out(self.act(self.inp(t)))


    
class DoubleConv(nn.Module):
    """(convolution => [BN] => ReLU) * 2"""

    def __init__(self, in_channels, out_channels, mid_channels=None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.double_conv(x)

class DoubleConvTime(nn.Module):
    """(convolution => [BN] => ReLU) * 2"""

    def __init__(self, in_channels, out_channels, mid_channels=None, n_emb = 100):
        super().__init__()
        #super(DoubleConvTime, self).__init__()
        
        if not mid_channels:
            mid_channels = out_channels
        #BxC
        self.time1 = nn.Linear(n_emb, mid_channels)
        self.time2 = nn.Linear(n_emb, out_channels)
        #BxCxHxW
        self.c1 = nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1, bias=False)
        self.bn1= nn.BatchNorm2d(mid_channels)
        self.act = nn.ReLU(inplace=True)
        
        self.c2 = nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

    def forward(self, x, timeEmb):
        
        out = self.act(self.bn1(self.c1(x)))
        t1 = self.time1(timeEmb)
        print('Inside DoubleConv')
        print(f'out:{out.shape}, t1: {t1.shape}')
        out = out + out * t1[:, :,None, None]
        #out = out + out * t1.expand_as(out)
        
        out = self.act(self.bn2(self.c2(out)))
        t2 = self.time2(timeEmb)
        print(f'out:{out.shape},t2: {t2.shape}')
        out = out + out * t2[:, :,None, None]

        return out


class Down(nn.Module):
    """Downscaling with maxpool then double conv"""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            MixPool2d(in_channels),
            #nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels)
        )

    def forward(self, x):
        return self.maxpool_conv(x)


class Up(nn.Module):
    """Upscaling then double conv"""

    def __init__(self, in_channels, out_channels, bilinear=True):
        super().__init__()

        # if bilinear, use the normal convolutions to reduce the number of channels
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1, x2):
        x1 = self.up(x1)
        # input is CHW
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]

        x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2,
                        diffY // 2, diffY - diffY // 2])
        # if you have padding issues, see
        # https://github.com/HaiyongJiang/U-Net-Pytorch-Unstructured-Buggy/commit/0e854509c2cea854e247a9c615f175f76fbb2e3a
        # https://github.com/xiaopeng-liao/Pytorch-UNet/commit/8ebac70e633bac59fc22bb5195e513d5832fb3bd
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class OutConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        return self.conv(x)
