"""
Calibration functions

Classes:
  Calibration - a calibration matrix and associated data

Functions:
  calibrate - main calibration routine
  find_maxima - locate peaks in a pixel array
  find_combined_maxima - locate peaks in series of exposures
  fit_region - fit a smooth function to peaks located with a rectangular region
  evaluate_fit - evaluate the fit returned by fit_region

  load - load a calibration matrix (deprecated)
"""

import minixs as mx
from exposure import Exposure
from emission import EmissionSpectrum, process_spectrum
from itertools import izip
from filter import get_filter_by_name
from gauss import gauss_leastsq
from parser import Parser, STRING, INT, FLOAT, LIST
from filetype import determine_filetype_from_header
from spectrometer import Spectrometer
from progress import ProgressIndicator

import os
import numpy as np

def load(filename):
  """
  Load a calibration matrix from a file
  """
  c = Calibration()
  c.load(filename)
  return c

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
  if direction in [mx.UP, mx.DOWN]:
    cols.shape = (len(cols),1)

  # find first moments about local maxima
  for i in range(-window_size,window_size+1):
    colMoment += local_max * np.roll(cols * p, i, rolldir)
    norm += local_max * np.roll(p, i, rolldir)

  # avoid dividing by zero
  norm[norm==0] = 1
  # calculate average
  windowedAvg = colMoment / norm
  #windowedAvg[np.isnan(windowedAvg)] = 0

  # we only want the locations of actual maxima
  index = np.where(windowedAvg > 0)
 
  # pull out the pixel locations of the peak centers
  if direction in [mx.UP, mx.DOWN]:
    y = windowedAvg[index]
    x = index[1]
  else:
    x = windowedAvg[index]
    y = index[0]

  # return N x 2 array of peak locations
  return np.vstack([x,y]).T


def find_combined_maxima(exposures, energies, direction, progress=None):
  """
  Build array of all maxima locations and energies in a list of exposures

  Parameters
  ----------
    exposures: a list of Exposure objects
    energies:  a list of corresponding energies (must be same length as `exposures`)
    direction: the dispersive direction
    progress: ProgressIndicator

  Returns
  -------
    Nx3 array with columns giving x,y,energy for each maximum
  """
  points = []

  i = 0
  n = len(energies)
  for exposure, energy in izip(exposures, energies):
    if progress:
      msg = "Finding maxima for mono energy %.2f" % energy
      prog = i / float(n)
      progress.update(msg, prog)
      i += 1

    # extract locations of peaks
    xy = find_maxima(exposure.pixels, direction)
    z = energy * np.ones((len(xy), 1))
    xyz = np.hstack([xy,z])
    points.append(xyz)

  return np.vstack(points)


FIT_QUADRATIC = 1
FIT_CUBIC   = 2
FIT_QUARTIC = 3
FIT_ELLIPSOID = 4

def fit_region(region, points, dest, fit_type = FIT_QUARTIC, return_fit=False):
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
  xxd, yyd = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
  xxd = np.ravel(xxd)
  yyd = np.ravel(yyd)
  xx = xxd.astype('double')
  yy = yyd.astype('double')

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

  elif fit_type == FIT_QUARTIC:
    # fit to quartic:
    A = np.vstack([
      x**4,
      y**4,
      x**2 * y**2,
      # intentionally skip all terms with cubes
      x**2 * y,
      x * y**2,
      x**2,
      y**2,
      x * y,
      x,
      y,
      np.ones(x.shape)
      ]).T
    fit, r = np.linalg.lstsq(A,z)[0:2]

    # calculate residues
    rms_res = np.sqrt(r / len(z)) #[0]
    lin_res = sum(z - np.dot(A, fit)) / len(z)

    # evaluate at all points
    zz = np.dot(
           np.vstack([
             xx**4, yy**4, xx**2 * yy**2,
             xx**2 * yy, xx * yy**2,
             xx**2, yy**2, xx * yy,
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
  dest[yyd,xxd] = zz

  if return_fit:
    return lin_res, rms_res, fit
  else:
    return lin_res, rms_res

def evaluate_fit(fit, x, y, fit_type=FIT_QUARTIC):

  if fit_type == FIT_QUARTIC:
    return np.dot(
           np.vstack([
             x**4, y**4, x**2 * y**2,
             x**2 * y, x * y**2,
             x**2, y**2, x * y,
             x, y,
             np.ones(x.shape)
           ]).T,
           fit
         ).T

def calibrate(filtered_exposures, energies, regions, dispersive_direction, fit_type=FIT_QUARTIC, return_diagnostics=False, progress=ProgressIndicator()):
  """
  Build calibration matrix from parameters in Calibration object

  Parameters
  ----------
    filtered_exposures: list of loaded and cleaned up Exposure objects
    energies: list of energies corresponding to exposures 
    regions: list of regions containing individual spectra [((x1,y1), (x2,y2)), ...]
    dispersive_direction: direction of increasing energy on camera (minixs.const.{DOWN,UP,LEFT,RIGHT})
    progress: ProgressIndicator

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

  progress.push_step("Find maxima", 0.5)
  # locate maxima
  points = find_combined_maxima(filtered_exposures, energies, dispersive_direction, progress=progress)
  progress.pop_step()

  # create empty calibration matrix
  calibration_matrix = np.zeros(filtered_exposures[0].pixels.shape)

  # fit smooth shape for each crystal, storing fit residues
  lin_res = []
  rms_res = []
  fits = []

  progress.push_step("Fit smooth surface", 0.5)
  for region in regions:

    ret = fit_region(region, points, calibration_matrix, fit_type, return_fit=True)
    if ret is not None:
      lr, rr, fit = ret
      lin_res.append(lr)
      rms_res.append(rr)
      fits.append(fit)
  progress.pop_step()

  if return_diagnostics:
    return (calibration_matrix, (lin_res, rms_res, points, fits))
  else:
    return calibration_matrix

class Calibration(object):
  """
  A calibration matrix and all corresponding information

  Methods:
    save                  - save to file
    load                  - load from file
    calibrate             - generate calibration matrix
    xtal_mask             - form mask of regions covered by self.xtals
    energy_range          - lowest and highest nonzero energies
    diagnose              - process all caliibration exposures and fit gaussians to elastic peaks
                              (useful for determining spectrometer energy resolution)
    calc_solid_angle_map  - calculate solid angle subtended by each pixel
                              (requires self.spectrometer to be set!)
    calc_residuals        - calculate residuals between fit and detected peaks

  Example usage:

    >>> import minixs as mx
    >>> from matplotlib import pyplot as pt
    >>> c = mx.calibrate.Calibration('example.calib')
    >>> c.xtals
    [[[17, 7], [119, 190]], [[135, 6], [229, 190]], [[249, 7], [343, 187]], [[357, 9], [457, 189]]]
    >>> pt.imshow(c.calibration_matrix, vmin=c.energy_range()[0])
    <matplotlib.image.AxesImage object at 0x424afd0>
    >>> pt.show()

  The first xtal region can be extracted as follows:
    >>> (x1,y1),(x2,y2) = c.xtals[0]
    >>> region1 = c.calibration_matrix[y1:y2,x1:x2]

  The calibration can also be redone after changing filters
    >>> c.filters
    [<minixs.filter.LowFilter object at 0x4252210>, <minixs.filter.NeighborFilter object at 0x4252310>]
    >>> c.filters[0].val
    10
    >>> c.filters[0].val = 5
    >>> c.calibrate()
    >>> c.save('example2.calib')
  """

  def __init__(self, filename=None):
    self.dataset_name = ""
    self.dispersive_direction = mx.DOWN
    self.energies = []
    self.exposure_files = []
    self.filters = []
    self.xtals = []
    self.calibration_matrix = np.array([])
    self.spectrometer = None

    self.filename = None

    self.load_errors = []

    if filename:
      self.load(filename)

  def save(self, filename=None, header_only=False):
    if filename is None:
      filename = self.filename
    else:
      self.filename = filename

    with open(filename, 'w') as f:
      f.write("# miniXS calibration matrix\n#\n")
      if self.spectrometer is not None:
        if self.spectrometer.tag:
          f.write("# Spectrometer: %s\n" % self.spectrometer.tag)
        else:
          f.write("# Spectrometer: %s\n" % self.spectrometer.filename)
      f.write("# Dataset: %s\n" % self.dataset_name)
      f.write("# Dispersive Direction: %s\n" % mx.DIRECTION_NAMES[self.dispersive_direction])
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

    if not os.path.exists(self.filename):
      self.load_errors.append("Unable to load nonexistant file: '%s'"%filename)
      return False

    parser = Parser({
      'Spectrometer': STRING,
      'Dataset': STRING,
      'Dispersive Direction': STRING,
      'Energies and Exposures': (LIST, (FLOAT, STRING)),
      'Filters': (LIST, STRING),
      'Xtal Boundaries': (LIST, (INT, INT, INT, INT)),
      })

    header = []
    with open(filename, 'r') as f:
      line = f.readline()

      if determine_filetype_from_header(line) != mx.filetype.FILE_CALIBRATION:
        self.load_errors.append("'%s' is not a calibration file" % filename)
        return False

      pos = f.tell()
      line = f.readline()
      while line:
        if line[0] == "#":
          header.append(line[2:])
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

    # parse
    parsed = parser.parse(header)
    if parser.errors:
      self.load_errors += parser.errors

    sname = parsed.get('Spectrometer')
    if sname:
      try:
        if sname == os.path.basename(sname):
          spect = Spectrometer(sname)
        else:
          spect = Spectrometer()
          spect.load(sname)

        self.spectrometer = spect
      except Exception as e:
        self.load_errors.append("Error loading spectrometer: %s" % str(e))

    self.dataset = parsed.get('Dataset', '')

    # check dispersive direction
    dirname = parsed.get('Dispersive Direction', mx.DOWN)
    if dirname in mx.DIRECTION_NAMES:
      self.dispersive_direction = mx.DIRECTION_NAMES.index(dirname)
    else:
      self.load_errors.append("Unknown Dispersive Direction: '%s', using default." % dirname)

    # split up energies and exposure files
    key = 'Energies and Exposures'
    if key in parsed.keys():
      self.energies = [ee[0] for ee in parsed[key]]
      self.exposure_files= [ee[1] for ee in parsed[key]]

    # read in filters
    for filter_line in parsed.get('Filters', []):
      name,val = filter_line.split(':')
      name = name.strip()
      fltr = get_filter_by_name(name)
      if fltr == None:
        self.load_errors.append("Unknown Filter: '%s' (Ignoring)" % name)
      else:
        fltr.set_str(val.strip())
        self.filters.append(fltr)

    self.xtals = [
        [[x1,y1],[x2,y2]]
        for x1,y1,x2,y2 in parsed.get('Xtal Boundaries', [])
        ]

    return len(self.load_errors) == 0

  def calibrate(self, fit_type=FIT_QUARTIC, progress=ProgressIndicator()):
    """
    Calculate calibration matrix

    Prerequisites:
      self.exposure_files must be a list of exposure files
      self.energies must be a list of corresponding energies
      self.xtals must be a list of regions exposed by each analyzer crystal
                      each entry must be of the form [[x1,y1],[x2,y2]]
      self.filters may contain a list of mx.filter.Filter descendents to apply to the exposures

    Results:
      self.calibration_matrix contains the calibration matrix
      self.lin_res contains average linear residuals of fit (one for each xtal)
      self.rms_res contains rms residuals of fit (one for each xtal)
      self.fit_points contains all detected peak values as array with columns (x,y,energy)
      self.fits contains a list of fit parameters (one for each xtal)
    """
    # load exposure files
    progress.push_step("Load Exposures", 0.1)
    exposures = [Exposure(f) for f in self.exposure_files]
    progress.pop_step()
    
    # apply filters
    progress.push_step("Apply Filters", 0.3)
    i = 0
    n = len(exposures)
    for exposure, energy in izip(exposures, self.energies):
      progress.update("Filter exposure %d" % (i+1,), i/float(n))
      i += 1
      for f in self.filters:
        f.filter(exposure.pixels, energy)
    progress.pop_step()

    # calibrate
    progress.push_step("Calibrate", 0.6)
    self.calibration_matrix, diagnostics = calibrate(exposures,
                                                     self.energies,
                                                     self.xtals,
                                                     self.dispersive_direction,
                                                     fit_type,
                                                     return_diagnostics=True,
                                                     progress=progress)
    progress.pop_step()

    # store diagnostic info
    self.lin_res, self.rms_res, self.fit_points, self.fits = diagnostics

  def xtal_mask(self):
    """
    Generate a mask of the xtal regions

    Returns
    -------
      An binary array of the same shape as the calibration matrix with 0's outside of xtal regions and 1's inside
    """

    if self.calibration_matrix is None:
      return None

    mask = np.zeros(self.calibration_matrix.shape, dtype=np.bool)
    for (x1,y1),(x2,y2) in self.xtals:
      mask[y1:y2,x1:x2] = 1

    return mask

  def energy_range(self):
    """
    Find min and max energies in calibration matrix

    Returns
    -------
      (min_energy, max_energy)
    """
    return (self.calibration_matrix[np.where(self.calibration_matrix > 0)].min(), self.calibration_matrix.max())

  def diagnose(self, return_spectra=False, filters=None, progress=None):
    """
    Process all calibration exposures and fit to gaussians, returning parameters of fit

    Example:
      >>> import minixs as mx
      >>> from matplotlib import pyplot as pt
      >>> c = mx.calibrate.Calibration('example.calib')
      >>> d, spectra = c.diagnose(return_spectra = True, filters=[mx.filter.HighFilter(1000)])
      >>> d[:,3] # sigma for gaussian fits
      array([ 0.4258905 ,  0.54773887,  0.58000567,  0.57056559,  0.56539868,
        0.58693027,  0.60704443,  0.61898894,  0.62726828,  0.63519546,
        0.65309853,  0.66317984,  0.67826396,  0.69466781,  0.75039033,
        0.78887514,  0.84248593,  0.8974527 ])
      >>> s = spectra[5]
      >>> pt.plot(s.emission, s.intensity, 'o')
      >>> pt.plot(s.emission, mx.gauss.gauss_model(d[5,1:], s.emission))
      >>> pt.show()

    Parameters
    ----------
    return_spectra: whether to return processed calibration spectra

    Returns
    -------
    (diagnostics, [processed_spectra])

    diagnostics: an array with one row for each calibration exposure
                 the columns are:
                   incident beam energy
                   amplitude
                   E0
                   sigma

                 the best Gaussian fit to the data is given by:
                   exp(-(E-E0)**2/(2*sigma**2))

    if `return_spectra` is True, then a list of XES spectra will be returned (one for each calibration exposure)
    """

    emin, emax = self.energy_range()
    emission_energies = np.arange(emin, emax, .2)

    diagnostics = np.zeros((len(self.energies), 4))

    if return_spectra:
      spectra = []

    for i in range(len(self.energies)):
      if progress:
        msg = "Processing calibration exposure %d / %d" % (i, len(self.energies))
        prog = i / float(len(self.energies))
        progress.update(msg, prog)

      energy = self.energies[i]
      exposure = Exposure(self.exposure_files[i])
      if filters is not None:
        exposure.apply_filters(energy, filters)

      s = process_spectrum(self.calibration_matrix, exposure, emission_energies, 1, self.dispersive_direction, self.xtals)
      x = s[:,0]
      y = s[:,1]

      fit, ier = gauss_leastsq((x,y), (y.max(), energy, 1.0))

      if not (0 < ier < 5):
        continue

      diagnostics[i,0] = energy
      diagnostics[i,1:] = fit

      if return_spectra:
        xes = EmissionSpectrum()
        xes.incident_energy = energy
        xes.exposure_files = [exposure.filename]
        xes._set_spectrum(s)
        spectra.append(xes)

    diagnostics = diagnostics[np.where(diagnostics[:,0] != 0)]

    if return_spectra:
      return (diagnostics, spectra)
    else:
      return diagnostics

  def calc_solid_angle_map(self):
    if not self.spectrometer:
      raise Exception("A spectrometer must be set in order to generate a solid angle map")
    bounds = [(x1,y1,x2,y2) for (x1,y1),(x2,y2) in self.xtals]
    return self.spectrometer.solid_angle_map(bounds)
      
  def calc_residuals(self):
    if not hasattr(self, 'fit_points'):
      raise Exception("Fit points are not defined. Make sure you rerun the calibration before trying to calculate residuals.")

    all_res = []
    for i, ((x1,y1),(x2,y2)) in enumerate(self.xtals):
      pts = np.array([(x,y,z) for x,y,z in self.fit_points if x1<=x<x2 and y1<=y<y2])
      fit = evaluate_fit(self.fits[i], pts[:,0], pts[:,1])

      res = fit - pts[:,2]

      # keep track of (xcoord, residual, energy)
      all_res.append(np.vstack([pts[:,0], res, pts[:,2]]).T)

    return all_res
