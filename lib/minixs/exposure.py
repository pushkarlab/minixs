"""
Raw detector exposures
"""
from PIL import Image
import numpy as np

class Exposure:
  """
  Raw detector exposures

  This handles loading and saving exposure files, which are currently assumed
  to be tif files from a Dectris Pilatus detector. Any image file that
  is supported by the Python Imaging Library should load correctly, however,
  unless the image has a single channel, it will most likely not work with
  any of the rest of the minixs code.
  """
  def __init__(self, filename = None):
    self.loaded = False
    if filename is not None:
      self.load(filename)

  def load(self, filename):
    """
    Load a single image file
    """
    self.filename = filename

    self.image = Image.open(filename)
    self.raw = np.asarray(self.image)
    self.pixels = self.raw.copy()
    try:
      self.info = self.parse_description(self.image.tag.get(270))
    except:
      pass
    self.loaded = True

  def load_multi(self, filenames):
    """
    Load several image files summing together their pixel values
    """
    self.filenames = filenames
    self.pixels = None
    for f in filenames:
      im = Image.open(f)
      p = np.asarray(im)
      if self.pixels is None:
        self.pixels = p.copy()
      else:
        self.pixels += p

  def parse_description(self, desc):
    try:
      # split into lines and strip off '#'
      info = [line[2:] for line in desc.split('\r\n')][:-1]
    except:
      info = []
    return info

  def apply_filters(self, energy, filters):
    """
    Apply a set of filters to an exposure

    Each filter in the list `filters` has its `filter` method called
    on this exposure's pixel array.
    """
    for f in filters:
      f.filter(self.pixels, energy)
  
  def filter_low_high(self, low, high):
    """
    DEPRECATED
    """
    if low == None: low = self.pixels.min()
    if high == None: high = self.pixels.max()

    mask = logical_and(self.pixels >= low, self.pixels <= high)
    self.pixels *= mask

  def filter_neighbors(self, cutoff):
    """
    DEPRECATED
    """
    from itertools import product
    nbors = (-1,0,1)
    mask = sum([
      roll(roll(self.pixels>0,i,0),j,1)
      for i,j in product(nbors,nbors)
      if i != 0 or j != 0
      ], 0) >= cutoff
    self.pixels *= mask

  def filter_bad_pixels(self, bad_pixels):
    """
    DEPRECATED
    """
    for x,y in bad_pixels:
      self.pixels[y,x] = 0


