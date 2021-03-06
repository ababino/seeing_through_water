# AUTOGENERATED! DO NOT EDIT! File to edit: 00_core.ipynb (unless otherwise specified).

__all__ = ['video_info', 'force_read', 'eager_video_iterator', 'brightest_frame', 'Calibrator', 'BrowserCalibrator',
           'VIDEOS', 'DataSource', 'videos_source', 'xy_fft']

# Cell
import os
from skvideo.io import ffprobe
import cv2
from fastcore.all import *
from tqdm.notebook import tqdm, trange
import ipywidgets as widgets
from ipywidgets import VBox, HBox, Label, Layout, Button
from fastai.data.all import *
from PIL import Image
from scipy.fft import fft
from fastpapers.core import *

# Cell
def video_info(path):
    '''Returns number of frames and frame rate.'''
    video_info = ffprobe(str(path))
    n_frames = int(video_info['video']['@nb_frames'])
    a, b = L(video_info['video']['@r_frame_rate'].split('/')).map(int)
    return n_frames, a/b

# Cell
def force_read(cap):
    '''Read next frame in video.'''
    frame = cap.read()[1]
    return force_read(cap) if frame is None else frame

# Cell
def eager_video_iterator(path):
    '''Iterates over all the frames in a video.'''
    n_frames, _ = video_info(path)
    cap = cv2.VideoCapture(str(path))
    for i in trange(n_frames): yield force_read(cap)
    cap.release()

# Cell
def brightest_frame(path, max_iter=-1):
    '''Returns the brightest frame in a video.'''
    mean_frame, max_frame = -1, None
    for i, frame in enumerate(eager_video_iterator(path)):
        if frame.mean()>mean_frame:
            max_frame= frame
            mean_frame = frame.mean()
        if i>max_iter and max_iter>0: break
    return max_frame

# Cell
class Calibrator:
    """Class to rotate and crop frames."""
    def __init__(self, im, rot=0, min_ct=300, max_ct=600, min_cl=500, max_cl=800, min_sz=400, max_sz=500):
        self.im = im
        self.rot = widgets.FloatSlider(value=rot, min=-5, max=5)
        self.ct = widgets.IntSlider(value=(min_ct+max_ct)/2, min=min_ct, max=max_ct)
        self.cl = widgets.IntSlider(value=(min_cl+max_cl)/2, min=min_cl, max=max_cl)
        self.sz = widgets.IntSlider(value=(min_sz+max_sz)/2, min=min_sz, max=max_sz)

        self.ct.observe(self.refresh_cam, names='value')
        self.rot.observe(self.refresh_cam, names='value')
        self.cl.observe(self.refresh_cam, names='value')
        self.sz.observe(self.refresh_cam, names='value')
        self.cam_out = widgets.Output(wait=True, layout=Layout(width='640px', height='640px'))
        self.refresh_cam(None)

    def refresh_cam(self, event):
        img = Image.fromarray(self.im[:,:,::-1])
        img = img.rotate(self.rot.value, resample=Image.BICUBIC)
        img = img.crop((self.cl.value, self.ct.value, self.cl.value+self.sz.value, self.ct.value+self.sz.value))
        img = img.resize((640, 640))
        self.cam_out.clear_output()
        with self.cam_out: display(img)

    def crop_array(self, frame):
        return frame[self.ct.value:self.ct.value+self.sz.value,self.cl.value:self.cl.value+self.sz.value,:]

    def encode(self, frame, reference=None, ref_sz=640):
        img = Image.fromarray(frame[:,:,::-1])
        img = img.rotate(self.rot.value, resample=Image.BICUBIC)
        img = img.crop((self.cl.value, self.ct.value, self.cl.value+self.sz.value, self.ct.value+self.sz.value))
        if not reference is None:
            refsh = reference.shape
            h, w = int(img.shape[0]*refsh[0]/ref_sz), int(img.shape[1]*refsh[1]/ref_sz)
            top = (img.shape[0]-h)/2
            bottom = img.shape[0]-top
            left = (img.shape[1]-w)/2
            right = img.shape[1] - left
            img = img.crop((left, top, right, bottom))
        return img

    def display(self):
        return VBox([HBox([self.cam_out]),
                     HBox([Label('rotate  '), self.rot]),
                     HBox([Label('crop top'), self.ct]),
                     HBox([Label('crop left'), self.cl]),
                     HBox([Label('size'), self.sz])])

# Cell
class BrowserCalibrator(Calibrator):
    @delegates(Calibrator.__init__)
    def __init__(self, imgs, ref_imgs, reps=1, **kwargs):
        super().__init__(imgs[0], **kwargs)
        self.imgs = imgs
        self.ref_imgs = ref_imgs
        self.reps = reps
        self.idx = 0
        self.next = widgets.Button(description='next')
        self.prev = widgets.Button(description='prev')
        self.next.on_click(self.next_idx)
        self.prev.on_click(self.prev_idx)
        self.ref_img_out = widgets.Output(wait=True, layout=Layout(width='640px', height='640px'))
        self.regresh_ref_img()

    def regresh_ref_img(self):
        img = Image.open(self.ref_imgs[int(self.idx/self.reps)]).crop_pad(640)
        self.ref_img_out.clear_output()
        with self.ref_img_out: display(img)

    def next_idx(self, event):
        self.idx += 1
        self.im = self.imgs[self.idx]
        self.refresh_cam(event)
        self.regresh_ref_img()

    def prev_idx(self, event):
        self.idx -= 1
        self.im = self.imgs[self.idx]
        self.refresh_cam(event)
        self.regresh_ref_img()

    def display(self):
        return VBox([HBox([self.cam_out, self.ref_img_out]),
                     HBox([Label('rotate  '), self.rot]),
                     HBox([Label('crop top'), self.ct]),
                     HBox([Label('crop left'), self.cl]),
                     HBox([Label('size'), self.sz]),
                     HBox([self.prev, self.next])])

# Cell
VIDEOS = Path(os.getenv('STWPATH'))/'videos'
# COCO = Path(os.getenv('STWPATH')) / 'coco'

# Cell
class DataSource:
    def __init__(self, src, extensions='.MP4', folders=['val2017', 'train2017', 'test2017']):
        self.src = VIDEOS
        self.vfiles = get_files(self.src, extensions=extensions, folders=folders)
    def get_subset(self, name):
        subsets = L('train', 'val', 'test')
        assert any(subsets.map(name.startswith)), 'subset name must be one of "train", "val", "test"'
        self.subset = name
        coco_source = download_coco()
        fnames = get_image_files(coco_source[self.subset]).sorted()
        return self.vfiles.filter(lambda x: x.parent.name.startswith(name)), fnames
    def one_video(self):
        subset = getattr(self, 'subset', 'test2017')
        return first(self.vfiles.filter(lambda x: x.parent.name.startswith(subset)))


# Cell
#slow
videos_source = DataSource(VIDEOS)

# Cell
def xy_fft(x, y):
    T = np.diff(x)[0]
    N = len(x)
    xf = np.linspace(0.0, 1.0/(2.0*T), N//2)
    yf = fft(y)
    yf = 2.0/N * np.abs(yf[0:N//2])
    return xf, yf