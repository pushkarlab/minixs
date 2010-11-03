"""
Calibration functions
"""

from exposure import Exposure
from itertools import izip
from filter import get_filter_by_name
from constants import *

import numpy as np


def find_maxima(pixels, direction, window_size = 3):
  """
  Find locations of local maxima of `pixels` array in `direction`.

  The location is calculated as the first moment in a window of half width
  `window_size` centered at a local maximum.

  Parameters
  ----------
  pixels : pixel array from an elastic exposure
  direction: minixs.DIRECTION_* indicating dispersive direction
  window_size : size in pixels around max for windowed average

  Returns
  -------
  xy : array of x, y and energy coordinates
  """

  # convert direction to axis (XXX make this a function call somewhere)
  rolldir = direction % 2

  # shorten expressions below by aliasing pixels array
  p = pixels

  # build mask of local maxima locations
  local_max = np.logical_and(p >= np.roll(p,-1,rolldir), p > np.roll(p, 1, rolldir))

  # perform windowed averaging to find average col value in local peak
  colMoment = np.zeros(p.shape)
  norm = np.zeros(p.shape)

  # build vector of indices along column (row) 
  cols = np.arange(0,p.shape[rolldir])
  if direction == VERTICAL:
    cols.shape = (len(cols),1)

  # find first moments about local maxima
  for i in range(-window_size,window_size+1):
    colMoment += local_max * np.roll(cols * p, i, rolldir)
    norm += local_max * np.roll(p, i, rolldir)

  # calculate average
  windowedAvg = colMoment / norm
  windowedAvg[np.isnan(windowedAvg)] = 0

  # we only want the locations of actual maxima
  index = np.where(windowedAvg > 0)
 
  # pull out the pixel locations of the peak centers
  if direction == VERTICAL:
    y = windowedAvg[index]
    x = index[1]
  else:
    x = windowedAvg[index]
    y = index[0]

  # return N x 2 array of peak locations
  return np.vstack([x,y]).T


def find_combined_maxima(exposures, energies, direction):
  """
  Build array of all maxima locations and energies in a list of exposures

  Parameters
  ----------
    exposures: a list of Exposure objects
    energies:  a list of corresponding energies (must be same length as `exposures`)
    direction: the dispersive direction

  Returns
  -------
    Nx3 array with columns giving x,y,energy for each maximum
  """
  points = []

  for exposure, energy in izip(exposures, energies):
    # extract locations of peaks
    xy = find_maxima(exposure.pixels, direction)
    z = energy * np.ones((len(xy), 1))
    xyz = np.hstack([xy,z])
    points.append(xyz)

  return np.vstack(points)


FIT_QUADRATIC = 1
FIT_CUBIC   = 2
FIT_ELLIPSOID = 3

def fit_region(region, points, dest, fit_type = FIT_CUBIC):
  """
  Fit a smooth function to points that lie in region bounded by `region`

  Parameters
  ----------
    region - a rectangle defining the boundary of region to fit: [(x1,y1), (x2,y2)]
    points - an N x 3 array of data points
    dest - an array to store fit data in
    fit_type - type of fit to perform, ether FIT_QUADRATIC or FIT_CUBIC

  Returns
  -------
    Nothing

  The points array should contain three columns giving respectively x,y and z
  values of data points.  The x and y values should be between 0 and the width
  and height of `dest` respectively. They are in units of pixels, but may be
  real valued.  The z values can take any values.

  The entries in `points` with x,y coordinates falling within the bounds
  specified by `region` are fit to the model specified by `fit_type` using linear
  least squares. This model is then evaluated at all integral values of x and y
  in this range, with the result being stored in the corresponding location of
  `dest`.

  This is intended to be called for several different non-overlapping values of
  `region` with the same list of `points` and `dest`.

  Fit Types
  ---------
    FIT_QUADRATIC: z = Ax^2 + By^2 + Cxy + Dx + Ey + F
    FIT_CUBIC: z = Ax^3 + By^3 + Cx^2y + Dxy^2 + Ex^2 + Fy^2 + Gxy + Hx + Iy + J
  """

  # boundary coordinates
  (x1,y1),(x2,y2) = region

  # extract points inside this xtal region
  index = np.where(np.logical_and(
      np.logical_and(
        points[:,0] >= x1,
        points[:,0] < x2),
      np.logical_and(
        points[:,1] >= y1,
        points[:,1] < y2
        )
      ))
  x,y,z = points[index].T

  # if we have no points in this region, we can't fit anything
  # XXX this should pass the warning up to higher level code instead
  #     of printing it out to stdout
  if len(x) == 0:
    print "Warning: No points in region: ", region
    return

  # build points to evaluate fit at
  xx, yy = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
  xx = np.ravel(xx)
  yy = np.ravel(yy)

  if fit_type == FIT_QUADRATIC:
    # fit to quadratic: z = Ax^2 + By^2 + Cxy + Dx + Ey + F
    A = np.vstack([x**2, y**2, x*y, x, y, np.ones(x.shape)]).T
    fit, r = np.linalg.lstsq(A,z)[0:2]

    # calculate residues
    rms_res = np.sqrt(r / len(z))[0]
    lin_res = sum(z - np.dot(A, fit)) / len(z)

    # evaluate at all points
    zz = np.dot(
           np.vstack([xx**2,yy**2,xx*yy,xx,yy,np.ones(xx.shape)]).T,
           fit
         ).T

  elif fit_type == FIT_CUBIC:
    # fit to cubic:
    #   Ax^3 + By^3 + Cx^2y + Dxy^2 + Ex^2 + Fy^2 + Gxy + Hx + Iy + J = z
    A = np.vstack([x**3,y**3,x**2*y,x*y**2,x**2, y**2, x*y, x, y, np.ones(x.shape)]).T
    fit, r = np.linalg.lstsq(A,z)[0:2]

    # calculate residues
    rms_res = np.sqrt(r / len(z))[0]
    lin_res = sum(z - np.dot(A, fit)) / len(z)

    # evaluate at all points
    zz = np.dot(
           np.vstack([
             xx**3, yy**3, xx**2*yy, xx*yy**2,
             xx**2, yy**2, xx*yy,
             xx, yy,
             np.ones(xx.shape)
           ]).T,
           fit
         ).T

  elif fit_type == FIT_ELLIPSOID:
    raise Exception("Fit method not yet implemented.")
    # XXX this doesn't seem to work...
    # Fit to ellipsoid:
    # Ax^2 + By^2 + Cz^2 + Dxy + Eyz + Fzx + Gx + Hy + Iz = 1
    data = np.vstack([
      x*x,
      y*y,
      z*z,
      x*y,
      y*z,
      z*x,
      x,
      y,
      z
      ]).T

    w = np.ones(x.shape)
    fit, r = np.linalg.lstsq(data,w)[0:2]

    #rms_res = np.sqrt(r / len(w))[0]
    lin_res = (w - np.dot(data, fit)).sum() / len(w)
    rms_res = np.sqrt(((w - np.dot(data, fit))**2).sum() / len(w))

    # now solve for z in terms of x and y to evaluate
    A,B,C,D,E,F,G,H,I = fit
    a = C
    b = E*yy + F*xx + I
    c = A*xx**2 + B*yy**2 + D*xx*yy + G*xx + H*yy - 1
    zz = (-b + np.sqrt(b**2 - 4*a*c)) / (2*a)

  # fill the calibration matrix with values from fit
  dest[yy,xx] = zz

  return lin_res, rms_res

def calibrate(filtered_exposures, energies, regions, dispersive_direction, fit_type=FIT_CUBIC, return_diagnostics=False):
  """
  Build calibration matrix from parameters in Calibration object

  Parameters
  ----------
    filtered_exposures: list of loaded and cleaned up Exposure objects
    energies: list of energies corresponding to exposures 
    regions: list of regions containing individual spectra
    dispersive_direction: direction of increasing energy on camera (minixs.const.{DOWN,UP,LEFT,RIGHT})

  Optional Parameters
  -------------------
    fit_type: type of fit (see fit_region() for more)
    return_diagnostics: whether to return extra information (residues and points used for fit)

  Returns
  -------
    calibration_matrix, [lin_res, rms_res, points]

    calibration_matrix: matrix of energies assigned to each pixel

    lin_res: average linear deviation of fit
    rms_res: avg root mean square residue of fit
    points: extracted maxima used for fit

    The last 3 of these are only returned if `return_diagnostics` is True.
  """
  # locate maxima
  points = find_combined_maxima(filtered_exposures, energies, dispersive_direction)

  # create empty calibration matrix
  calibration_matrix = np.zeros(filtered_exposures[0].pixels.shape)

  # fit smooth shape for each crystal, storing fit residues
  lin_res = []
  rms_res = []
  for region in regions:
    lr, rr = fit_region(region, points, calibration_matrix, fit_type)
    lin_res.append(lr)
    rms_res.append(rr)

  if return_diagnostics:
    return (calibration_matrix, (lin_res, rms_res, points))
  else:
    return calibration_matrix

class Calibration:
  """
  A calibration matrix and all corresponding information
  """

  def __init__(self):
    self.dataset_name = ""
    self.dispersive_direction = DOWN
    self.energies = []
    self.exposure_files = []
    self.filters = []
    self.xtals = []
    self.calibration_matrix = np.array([])

    self.filename = None

    self.load_errors = []

  def save(self, filename=None, header_only=False):
    if filename is None:
      filename = self.filename
    else:
      self.filename = filename

    with open(filename, 'w') as f:
      f.write("# minIXS calibration matrix\n#\n")
      f.write("# Dataset: %s\n" % self.dataset_name)
      f.write("# Dispersive Direction: %s\n" % DIRECTION_NAMES[self.dispersive_direction])
      f.write("#\n")
      f.write("# Energies and Exposures:\n")
      for en, ex in izip(self.energies, self.exposure_files):
        f.write("#   %5.2f %s\n" % (en,ex))
      f.write("#\n")

      f.write("# Filters:\n")
      for fltr in self.filters:
        f.write('#   %s: %s\n' % (fltr.name, fltr.get_str()))
      f.write("#\n")

      f.write("# Xtal Boundaries:\n")
      for (x1,y1), (x2,y2) in self.xtals:
        f.write("#   %3d %3d %3d %3d\n" % (x1,y1,x2,y2))
      f.write("#\n")

      if (not header_only and
          self.calibration_matrix is not None and
          len(self.calibration_matrix) > 0 and 
          len(self.calibration_matrix.shape) == 2):
        f.write("# %d x %d matrix follows\n" % self.calibration_matrix.shape)

        np.savetxt(f, self.calibration_matrix, fmt='%.3f')

  def load(self, filename=None, header_only=False):
    """
    Load calibration information from saved file

    Parameters
    ----------
      filename: name of file to load
      header_only: whether to load only the header or full data

    Returns
    -------
      True if load was successful
      False if load encountered an error

      Error messages are stored as strings in the list `Calibration.load_errors`.
    """
    self.load_errors = []

    if filename is None:
      filename = self.filename
    else:
      self.filename = filename

    with open(filename, 'r') as f:
      pos = f.tell()
      line = f.readline()

      if line.strip() != '# minIXS calibration matrix':
        raise InvalidFileError()

      in_exposures = False
      in_filters = False
      in_xtals = False

      while line:
        if line[0] == "#":

          if in_exposures:
            if line[2:].strip() == '':
              in_exposures = False
            else:
              energy, ef = line[2:].split()
              energy = float(energy.strip())
              ef = ef.strip()

              self.energies.append(energy)
              self.exposure_files.append(ef)

          elif in_filters:
            if line[2:].strip() == '':
              in_filters = False
            else:
              name,val = line[2:].split(':')
              name = name.strip()
              fltr = get_filter_by_name(name)
              if fltr == None:
                self.load_errors.append("Unknown Filter: '%s' (Ignoring)" % name)
              else:
                fltr.set_str(val.strip())
                self.filters.append(fltr)

          elif in_xtals:
            if line[2:].strip() == '':
              in_xtals = False
            else:
              x1,y1,x2,y2 = [int(s.strip()) for s in line[2:].split()]
              self.xtals.append([[x1,y1],[x2,y2]])

          elif line[2:10] == 'Dataset:':
            self.dataset_name = line[11:].strip()
          elif line[2:23] == 'Dispersive Direction:':
            dirname = line[24:].strip()
            if dirname in DIRECTION_NAMES:
              self.dispersive_direction = DIRECTION_NAMES.index(dirname)
            else:
              self.load_errors.append("Unknown Dispersive Direction: '%s' (Using default)." % dirname)
          elif line[2:25] == 'Energies and Exposures:':
            self.energies = []
            self.exposure_files = []
            in_exposures = True
          elif line[2:10] == 'Filters:':
            self.filters = []
            in_filters = True
          elif line[2:18] == 'Xtal Boundaries:':
            self.xtals = []
            in_xtals = True
          else:
            pass
        elif header_only:
          break
        else:
          f.seek(pos)
          self.calibration_matrix = np.loadtxt(f)
          if len(self.calibration_matrix.shape) == 1:
            self.calibration_matrix.shape = (1,self.spectrum.shape[0])
          break

        pos = f.tell()
        line = f.readline()

    return len(self.load_errors) == 0

  def calibrate(self, fit_type=FIT_CUBIC):
    # load exposure files
    exposures = [Exposure(f) for f in self.exposure_files]
    
    # apply filters
    for exposure, energy in izip(exposures, self.energies):
      for f in self.filters:
        f.filter(exposure.pixels, energy)

    # calibrate
    self.calibration_matrix, diagnostics = calibrate(exposures,
                                                     self.energies,
                                                     self.xtals,
                                                     self.dispersive_direction,
                                                     fit_type,
                                                     return_diagnostics=True)

    # store diagnostic info
    self.lin_res, self.rms_res, self.fit_points = diagnostics
